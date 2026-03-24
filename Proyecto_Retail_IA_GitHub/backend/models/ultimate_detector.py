"""
UltimateShelfDetector — Maximum-performance product detector.
Ensemble of multiple YOLO models + WBF fusion + multi-scale +
section-based detection + shelf-aware post-processing.
"""

import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.detection import Detection
from backend.services.advanced_preprocessing import AdvancedPreprocessor, ImageSection
from backend.services.shelf_analysis import ShelfAnalyzer


class UltimateShelfDetector:
    """
    Maximum-recall product detector using:
    - Multi-model ensemble (YOLOv8x + YOLOv8n + optional YOLO11/RT-DETR)
    - Multi-scale inference (640, 960, 1280)
    - CLAHE + section-based scanning
    - Weighted Boxes Fusion (WBF)
    - Shelf-line contextual refinement

    Quality modes:
      FAST:     1 model, 1 scale, full image only
      BALANCED: 2 models, 2 scales, sections
      MAXIMUM:  all models, 3 scales, sections + full + CLAHE variants
    """

    QUALITY_FAST = "fast"
    QUALITY_BALANCED = "balanced"
    QUALITY_MAXIMUM = "maximum"

    def __init__(self, config_path: Optional[str] = None) -> None:
        from ultralytics import YOLO

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        uconfig = config.get("ultimate_detection", {})
        self.quality = uconfig.get("quality_mode", self.QUALITY_BALANCED)

        # --- Load models ---
        model_paths = uconfig.get("models", [
            config["paths"].get("yolo_weights", "data/weights/yolov8n.pt")
        ])

        self.models: List[Any] = []
        self.model_names: List[str] = []
        for mp in model_paths:
            abs_path = os.path.join(ROOT_DIR, mp) if not os.path.isabs(mp) else mp
            if os.path.exists(abs_path):
                self.models.append(YOLO(abs_path))
                self.model_names.append(os.path.basename(mp))
                print(f"  [UltimateDetector] Loaded: {mp}")
            else:
                # Try auto-download via ultralytics
                try:
                    model_name = os.path.basename(mp)
                    self.models.append(YOLO(model_name))
                    self.model_names.append(model_name)
                    print(f"  [UltimateDetector] Auto-downloaded: {model_name}")
                except Exception as e:
                    print(f"  [UltimateDetector] SKIP {mp}: {e}")

        if not self.models:
            raise RuntimeError("No models loaded. Check config paths.")

        # --- Config ---
        self.scales = uconfig.get("scales", self._default_scales())
        self.conf_thresholds = uconfig.get("conf_thresholds", self._default_confs())
        self.wbf_iou = uconfig.get("wbf_iou_threshold", 0.55)
        self.wbf_skip = uconfig.get("wbf_skip_box_threshold", 0.01)
        self.use_sections = uconfig.get("use_sections", self.quality != self.QUALITY_FAST)
        self.n_sections = uconfig.get("n_sections", 3)
        self.section_overlap = uconfig.get("section_overlap", 0.15)
        self.use_tta = uconfig.get("use_tta", self.quality == self.QUALITY_MAXIMUM)
        self.max_det = uconfig.get("max_detections", 300)

        # --- Preprocessing ---
        self.preprocessor = AdvancedPreprocessor(
            clahe_clip=uconfig.get("clahe_clip_limit", 3.0),
            enable_clahe=uconfig.get("clahe_enabled", True),
            enable_denoise=uconfig.get("denoise_enabled", False),
            enable_perspective=uconfig.get("perspective_enabled", True),
            n_sections=self.n_sections,
            section_overlap=self.section_overlap,
        )

        # --- Shelf analysis ---
        self.shelf_analyzer = ShelfAnalyzer()

        print(f"  [UltimateDetector] Quality={self.quality}, "
              f"Models={len(self.models)}, Scales={self.scales}")

    def _default_scales(self) -> List[int]:
        if self.quality == self.QUALITY_FAST:
            return [640]
        elif self.quality == self.QUALITY_BALANCED:
            return [640, 960]
        return [640, 960, 1280]

    def _default_confs(self) -> List[float]:
        if self.quality == self.QUALITY_FAST:
            return [0.15]
        elif self.quality == self.QUALITY_BALANCED:
            return [0.05, 0.15]
        return [0.01, 0.05, 0.15]

    def detect(self, image: np.ndarray) -> List[Detection]:
        """
        Full detection pipeline:
        1. Preprocess (CLAHE, perspective, sections)
        2. Multi-model multi-scale inference
        3. WBF fusion
        4. Shelf-aware refinement
        """
        h, w = image.shape[:2]

        # 1. Preprocess
        enhanced = self.preprocessor.full_pipeline(image)

        # 2. Build image variants (full image + sections)
        variants = self._build_variants(enhanced)

        # 3. Run all models on all variants at all scales
        all_boxes: List[List[List[float]]] = []
        all_scores: List[List[float]] = []
        all_labels: List[List[int]] = []

        models_to_use = self.models if self.quality != self.QUALITY_FAST else self.models[:1]

        for model in models_to_use:
            for variant in variants:
                for imgsz in self.scales:
                    for conf in self.conf_thresholds:
                        boxes, scores, labels = self._run_single_inference(
                            model, variant, imgsz, conf, w, h
                        )
                        if boxes:
                            all_boxes.append(boxes)
                            all_scores.append(scores)
                            all_labels.append(labels)

        if not all_boxes:
            return []

        # 4. Weighted Boxes Fusion
        fused_boxes, fused_scores, fused_labels = self._fuse_wbf(
            all_boxes, all_scores, all_labels
        )

        # 5. Build Detection objects
        detections = []
        for i in range(len(fused_boxes)):
            x1 = int(fused_boxes[i][0] * w)
            y1 = int(fused_boxes[i][1] * h)
            x2 = int(fused_boxes[i][2] * w)
            y2 = int(fused_boxes[i][3] * h)

            # Clamp
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 - x1 < 5 or y2 - y1 < 5:
                continue

            class_id = int(fused_labels[i])
            class_name = self._get_class_name(class_id)

            detections.append(Detection(
                bbox=(x1, y1, x2, y2),
                score=float(fused_scores[i]),
                class_id=class_id,
                class_name=class_name,
            ))

        # 6. Shelf-aware refinement
        shelf_lines = self.shelf_analyzer.detect_shelf_lines(image)
        if shelf_lines:
            detections = self.shelf_analyzer.refine_detections(
                detections, shelf_lines, h, w
            )

        # 7. Final confidence filter
        detections = [d for d in detections if d.score >= self.wbf_skip]

        # Sort by score descending
        detections.sort(key=lambda d: d.score, reverse=True)

        return detections[:self.max_det]

    def _build_variants(self, image: np.ndarray) -> List[ImageSection]:
        """Build image variants: full + sections + optionally CLAHE variants."""
        h, w = image.shape[:2]
        variants = [
            ImageSection(image=image, offset_x=0, offset_y=0,
                         original_w=w, original_h=h)
        ]

        if self.use_sections:
            sections = self.preprocessor.split_sections(image)
            variants.extend(sections)

        if self.quality == self.QUALITY_MAXIMUM:
            # Add CLAHE-enhanced full image
            clahe_img = self.preprocessor.apply_clahe_sections(image)
            variants.append(
                ImageSection(image=clahe_img, offset_x=0, offset_y=0,
                             original_w=w, original_h=h)
            )

        return variants

    def _run_single_inference(
        self,
        model: Any,
        variant: ImageSection,
        imgsz: int,
        conf: float,
        global_w: int,
        global_h: int,
    ) -> Tuple[List[List[float]], List[float], List[int]]:
        """Run a single inference pass and remap coordinates to global."""
        try:
            results = model.predict(
                source=variant.image,
                conf=conf,
                iou=0.5,
                max_det=self.max_det,
                imgsz=imgsz,
                verbose=False,
                augment=self.use_tta,
            )
        except Exception:
            return [], [], []

        boxes, scores, labels = [], [], []
        sec_h, sec_w = variant.image.shape[:2]

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                score = float(box.conf[0])
                cls_id = int(box.cls[0])

                # Remap to global coordinates (normalized 0-1)
                gx1 = (x1 + variant.offset_x) / global_w
                gy1 = (y1 + variant.offset_y) / global_h
                gx2 = (x2 + variant.offset_x) / global_w
                gy2 = (y2 + variant.offset_y) / global_h

                # Clamp to [0, 1]
                gx1 = max(0.0, min(1.0, gx1))
                gy1 = max(0.0, min(1.0, gy1))
                gx2 = max(0.0, min(1.0, gx2))
                gy2 = max(0.0, min(1.0, gy2))

                if gx2 - gx1 > 0.003 and gy2 - gy1 > 0.003:
                    boxes.append([gx1, gy1, gx2, gy2])
                    scores.append(score)
                    labels.append(cls_id)

        return boxes, scores, labels

    def _fuse_wbf(
        self,
        all_boxes: List[List[List[float]]],
        all_scores: List[List[float]],
        all_labels: List[List[int]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Weighted Boxes Fusion to combine multi-model detections.
        Falls back to custom NMS if ensemble_boxes not installed.
        """
        try:
            from ensemble_boxes import weighted_boxes_fusion
            fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
                all_boxes, all_scores, all_labels,
                iou_thr=self.wbf_iou,
                skip_box_thr=self.wbf_skip,
                weights=None,
            )
            return fused_boxes, fused_scores, fused_labels
        except ImportError:
            return self._fallback_fusion(all_boxes, all_scores, all_labels)

    def _fallback_fusion(
        self,
        all_boxes: List[List[List[float]]],
        all_scores: List[List[float]],
        all_labels: List[List[int]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Fallback: concatenate all + soft-NMS."""
        concat_boxes = []
        concat_scores = []
        concat_labels = []

        for boxes, scores, labels in zip(all_boxes, all_scores, all_labels):
            concat_boxes.extend(boxes)
            concat_scores.extend(scores)
            concat_labels.extend(labels)

        if not concat_boxes:
            return np.array([]), np.array([]), np.array([])

        boxes_arr = np.array(concat_boxes)
        scores_arr = np.array(concat_scores)
        labels_arr = np.array(concat_labels)

        # Per-class soft-NMS
        unique_labels = np.unique(labels_arr)
        final_boxes, final_scores, final_labels = [], [], []

        for lbl in unique_labels:
            mask = labels_arr == lbl
            cls_boxes = boxes_arr[mask]
            cls_scores = scores_arr[mask]

            keep = self._soft_nms(cls_boxes, cls_scores, sigma=0.5, thresh=self.wbf_skip)

            final_boxes.extend(cls_boxes[keep].tolist())
            final_scores.extend(cls_scores[keep].tolist())
            final_labels.extend([int(lbl)] * len(keep))

        return (
            np.array(final_boxes) if final_boxes else np.array([]),
            np.array(final_scores) if final_scores else np.array([]),
            np.array(final_labels) if final_labels else np.array([]),
        )

    @staticmethod
    def _soft_nms(
        boxes: np.ndarray,
        scores: np.ndarray,
        sigma: float = 0.5,
        thresh: float = 0.01,
    ) -> List[int]:
        """Soft-NMS with Gaussian penalty."""
        N = len(boxes)
        if N == 0:
            return []

        indices = list(range(N))
        s = scores.copy()
        keep = []

        sorted_idx = np.argsort(-s)

        for i in range(N):
            max_idx = sorted_idx[i]
            if s[max_idx] < thresh:
                continue

            keep.append(max_idx)
            max_box = boxes[max_idx]

            for j in range(i + 1, N):
                idx = sorted_idx[j]
                if s[idx] < thresh:
                    continue
                iou = UltimateShelfDetector._compute_iou(max_box, boxes[idx])
                s[idx] *= np.exp(-(iou ** 2) / sigma)

        return keep

    @staticmethod
    def _compute_iou(box1: np.ndarray, box2: np.ndarray) -> float:
        """Compute IoU between two boxes [x1, y1, x2, y2]."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter

        return inter / (union + 1e-6)

    def _get_class_name(self, class_id: int) -> str:
        """Get class name from first loaded model."""
        if self.models:
            names = self.models[0].names
            return names.get(class_id, f"product_{class_id}")
        return f"product_{class_id}"

    def get_class_names(self) -> dict:
        """Return class name mapping from primary model."""
        if self.models:
            return dict(self.models[0].names)
        return {}

    def get_detection_stats(self) -> dict:
        """Return info about the detector configuration."""
        return {
            "quality_mode": self.quality,
            "num_models": len(self.models),
            "model_names": self.model_names,
            "scales": self.scales,
            "conf_thresholds": self.conf_thresholds,
            "use_sections": self.use_sections,
            "n_sections": self.n_sections,
            "use_tta": self.use_tta,
        }
