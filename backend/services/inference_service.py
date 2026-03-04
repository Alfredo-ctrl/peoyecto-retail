"""

GodMode Inference Service — Pipeline de Inferencia v3.0
Samsung Innovation Campus


Pipeline:
  1. GodModeShelfDetector (YOLO @ 960px, CLAHE, conf=0.10)
  2. YOLO class names mapeados a retail (NO clasificador separado)
  3. Regresion de stock (ensemble o fallback)
  4. Clustering de comportamiento (KMeans++)
  5. Shelf metrics (occupancy, acciones, OOS detection)

FIX PRINCIPAL: La clasificacion ahora usa las clases de YOLO
directamente (que SI estan entrenadas) en vez de un ResNet con
pesos random que clasificaba "papas" como "cereal".

"""

import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.godmode_detector import GodModeShelfDetector
from backend.models.detection import Detection
from backend.services.postprocessing import (
    build_response_v3,
    draw_detections,
    image_to_base64,
)
from backend.services.preprocessing import preprocess_image

import yaml


class InferenceService:
    """
    GodMode inference — maximum detection with correct classification.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        print("=" * 60)
        print("  Inicializando Pipeline GodMode v3.0")
        print("=" * 60)

        self.config_path = config_path
        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        # 1. GodMode Detector
        print("\n[1/3] Cargando GodModeShelfDetector...")
        self.detector = GodModeShelfDetector(config_path)

        # 2. Regressor (load legacy model if available)
        print("\n[2/3] Cargando regresor de stock...")
        self.regressor = None
        self.regressor_fitted = False
        try:
            reg_path = os.path.join(ROOT_DIR, self.config["paths"]["regressor_weights"])
            if os.path.exists(reg_path):
                import joblib
                data = joblib.load(reg_path)
                self.regressor = data
                self.regressor_fitted = True
                print(f"  Regresor cargado: {reg_path}")
            else:
                print("  Sin regresor entrenado. Usando fallback bbox_count.")
        except Exception as e:
            print(f"  Regresor no disponible: {e}. Usando fallback.")

        # 3. Clustering
        print("\n[3/3] Cargando clustering...")
        self.clusterer = None
        self.cluster_labels = {0: "Alta rotacion", 1: "Estable", 2: "Baja rotacion"}
        try:
            clus_path = os.path.join(ROOT_DIR, self.config["paths"]["clustering_weights"])
            if os.path.exists(clus_path):
                import joblib
                data = joblib.load(clus_path)
                self.clusterer = data.get("model") if isinstance(data, dict) else data
                self.cluster_scaler = data.get("scaler") if isinstance(data, dict) else None
                if isinstance(data, dict) and "cluster_labels" in data:
                    self.cluster_labels = {int(k): str(v) for k, v in data["cluster_labels"].items()}
                print(f"  Clustering cargado: {clus_path}")
            else:
                print("  Sin clustering entrenado. Usando asignacion fija.")
        except Exception as e:
            print(f"  Clustering no disponible: {e}")

        print("\n" + "=" * 60)
        print("  Pipeline GodMode v3.0 LISTO")
        print("=" * 60)

    def run_pipeline(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Pipeline completo:
          1. Decode + preprocess
          2. GodMode detect (YOLO @ 960, CLAHE, retail mapping)
          3. Group by SKU + estimate quantities
          4. Assign clusters
          5. Calculate shelf metrics
          6. Build enriched JSON
        """
        start_time = time.time()

        # --- 1. Decode ---
        image = preprocess_image(image_bytes)
        h, w = image.shape[:2]

        # --- 2. Detect ---
        detections = self.detector.detect(image)

        if not detections:
            return {
                "success": True,
                "processing_time_seconds": 0.0,
                "total_detections": 0,
                "unique_skus": 0,
                "annotated_image_base64": image_to_base64(image),
                "products": [],
                "summary": [],
                "shelf_metrics": {
                    "total_occupancy_pct": 0.0,
                    "out_of_stock_zones": 0,
                    "low_stock_skus": 0,
                },
            }

        # --- 3. Group by retail name + estimate quantity ---
        sku_groups: Dict[str, List[Detection]] = defaultdict(list)
        for det in detections:
            sku_groups[det.class_name].append(det)

        regression_results: Dict[str, float] = {}
        for sku_name, dets in sku_groups.items():
            # Smart quantity estimation
            count = len(dets)
            avg_area = np.mean([(d.bbox[2]-d.bbox[0]) * (d.bbox[3]-d.bbox[1]) for d in dets])
            total_width = sum(d.bbox[2]-d.bbox[0] for d in dets)

            # Try trained regressor
            if self.regressor_fitted and self.regressor is not None:
                try:
                    features = self._build_features(dets, h, w)
                    X = features.reshape(1, -1)
                    if isinstance(self.regressor, dict) and "models" in self.regressor:
                        # Advanced ensemble format
                        pred = 0
                        for model, weight, name in self.regressor["models"]:
                            try:
                                p = model.predict(X)[0]
                                pred += p * weight
                            except Exception:
                                pred += count * weight
                        regression_results[sku_name] = float(max(1, round(pred)))
                    else:
                        pred = self.regressor.predict(X)[0]
                        regression_results[sku_name] = float(max(1, round(pred)))
                except Exception:
                    regression_results[sku_name] = float(count)
            else:
                # Fallback: count directly
                regression_results[sku_name] = float(count)

        # --- 4. Assign clusters ---
        cluster_results: Dict[str, int] = {}
        for sku_name, units in regression_results.items():
            cluster_id = self._assign_cluster(units)
            cluster_results[sku_name] = cluster_id

        # --- 5. Shelf metrics ---
        shelf_metrics = self.detector.compute_shelf_metrics(detections, h, w)
        per_sku_occ = self.detector.compute_per_sku_occupancy(detections, w, h)

        # --- 6. Draw + build response ---
        sku_names = [d.class_name for d in detections]
        annotated = draw_detections(image, detections, sku_names)
        annotated_b64 = image_to_base64(annotated)

        processing_time = round(time.time() - start_time, 2)

        response = build_response_v3(
            detections=detections,
            regression_results=regression_results,
            cluster_results=cluster_results,
            cluster_labels=self.cluster_labels,
            per_sku_occupancy=per_sku_occ,
            shelf_metrics=shelf_metrics,
            annotated_image_b64=annotated_b64,
            processing_time=processing_time,
            suggest_action_fn=self.detector.suggest_action,
        )

        return response

    def _build_features(self, dets: List[Detection], img_h: int, img_w: int) -> np.ndarray:
        """Build 5-feature vector for regressor."""
        count = len(dets)
        total_width = sum(d.bbox[2]-d.bbox[0] for d in dets)
        heights = [d.bbox[3]-d.bbox[1] for d in dets]
        avg_height = float(np.mean(heights))
        centers_y = [(d.bbox[1]+d.bbox[3])/2.0 for d in dets]
        shelf_pos = float(np.mean(centers_y) / img_h) if img_h > 0 else 0.5

        sorted_cy = sorted(centers_y)
        tol = avg_height * 0.5 if avg_height > 0 else img_h * 0.05
        num_rows = 1
        last = sorted_cy[0]
        for cy in sorted_cy[1:]:
            if abs(cy - last) > tol:
                num_rows += 1
                last = cy

        return np.array([count, total_width, avg_height, num_rows, shelf_pos], dtype=np.float64)

    def _assign_cluster(self, units: float) -> int:
        """Assign cluster based on estimated stock level."""
        if self.clusterer is not None and self.cluster_scaler is not None:
            try:
                np.random.seed(int(units * 100) % 2**31)
                avg_stock = max(0, units + np.random.normal(0, 1))
                stock_var = max(0, np.random.exponential(scale=max(1, 10-units)))
                low_pct = max(0, min(1, 0.5 - units*0.05 + np.random.normal(0, 0.1)))
                alert_freq = max(0, min(1, stock_var*0.1 + np.random.normal(0, 0.05)))
                features = np.array([[avg_stock, stock_var, low_pct, alert_freq]])
                X_scaled = self.cluster_scaler.transform(features)
                return int(self.clusterer.predict(X_scaled)[0])
            except Exception:
                pass

        # Fallback: rule-based
        if units <= 2:
            return 0  # Alta rotacion
        elif units <= 5:
            return 1  # Estable
        return 2  # Baja rotacion
