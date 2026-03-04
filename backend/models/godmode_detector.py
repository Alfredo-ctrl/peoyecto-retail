"""
GodModeShelfDetector — Deteccion maxima de productos en estantes.

Estrategia:
  - YOLOv8x @ imgsz=960 con conf=0.10 para recall maximo
  - CLAHE preprocessing para iluminacion dificil
  - Mapeo inteligente COCO → categorias retail mexicano
  - YOLO ya esta entrenado de verdad → usamos SUS clases, no un clasificador separado con pesos random

Esto soluciona el bug de "papas clasificadas como cereal":
  YOLO detecta "bottle" (correcto) pero el clasificador viejo le ponia "Cereal_A" (random).
  Ahora usamos directamente la clase de YOLO mapeada a retail.
"""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.detection import Detection


# ---------------------------------------------------------------
# COCO → Retail Mexicano mapping
# ---------------------------------------------------------------
COCO_TO_RETAIL: Dict[str, str] = {
    # Bebidas
    "bottle": "Botella/Bebida",
    "wine glass": "Copa",
    "cup": "Vaso/Bebida",

    # Alimentos
    "banana": "Banana/Fruta",
    "apple": "Manzana/Fruta",
    "orange": "Naranja/Fruta",
    "sandwich": "Sandwich",
    "broccoli": "Verdura",
    "carrot": "Zanahoria",
    "hot dog": "Hot Dog",
    "pizza": "Pizza",
    "donut": "Dona/Pan",
    "cake": "Pastel/Postre",

    # Contenedores (frecuentes en estantes)
    "bowl": "Bowl/Contenedor",
    "vase": "Envase",

    # Objetos que YOLO detecta en estantes
    "book": "Caja/Cereal",
    "cell phone": "Dispositivo",
    "remote": "Control/Producto",
    "scissors": "Tijeras",
    "toothbrush": "Cepillo/Higiene",
    "clock": "Reloj",
    "potted plant": "Planta",
    "teddy bear": "Juguete",
    "backpack": "Bolsa/Producto",
    "handbag": "Bolsa/Snack",
    "suitcase": "Caja Grande",
    "umbrella": "Paraguas",
    "tie": "Corbata",
    "sports ball": "Pelota",
    "knife": "Cuchillo",
    "spoon": "Cuchara",
    "fork": "Tenedor",
    "dining table": "Mesa/Estante",
    "chair": "Silla",
    "couch": "Sofa",
    "tv": "Pantalla",
    "laptop": "Laptop",
    "mouse": "Mouse",
    "keyboard": "Teclado",
    "oven": "Horno",
    "microwave": "Microondas",
    "refrigerator": "Refrigerador",
    "sink": "Lavabo",
    "toilet": "Sanitario",
}

# Categorias retail para agrupar
RETAIL_CATEGORIES: Dict[str, str] = {
    "Botella/Bebida": "Bebidas",
    "Copa": "Bebidas",
    "Vaso/Bebida": "Bebidas",
    "Banana/Fruta": "Frutas",
    "Manzana/Fruta": "Frutas",
    "Naranja/Fruta": "Frutas",
    "Caja/Cereal": "Cereales/Cajas",
    "Bowl/Contenedor": "Contenedores",
    "Envase": "Envases",
    "Bolsa/Snack": "Snacks",
    "Bolsa/Producto": "Productos",
    "Dona/Pan": "Panaderia",
    "Pastel/Postre": "Panaderia",
    "Cepillo/Higiene": "Higiene",
}


class GodModeShelfDetector:
    """
    Maximum-recall shelf detector.

    Pipeline:
      1. CLAHE contrast enhancement (catches dark/shadowed products)
      2. YOLOv8x @ 960px, conf=0.10 (aggressive detection)
      3. COCO → Retail name mapping (correct classification)
      4. Filter non-product classes (person, car, etc.)
      5. Occupancy & shelf metrics calculation

    On CPU: ~8-15s per image (with yolov8x at 960px)
    On GPU: ~1-3s per image
    """

    # COCO classes that should NOT appear on a retail shelf
    EXCLUDE_CLASSES = {
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
        "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe", "frisbee", "skis",
        "snowboard", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bed",
    }

    def __init__(self, config_path: Optional[str] = None) -> None:
        from ultralytics import YOLO

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        gconfig = self.config.get("godmode_detection", {})

        # Load model
        model_path = gconfig.get("model", self.config["paths"].get("yolo_weights", "data/weights/yolov8x.pt"))
        abs_path = os.path.join(ROOT_DIR, model_path) if not os.path.isabs(model_path) else model_path

        if os.path.exists(abs_path):
            self.model = YOLO(abs_path)
            print(f"  [GodMode] Modelo cargado: {abs_path}")
        else:
            self.model = YOLO(os.path.basename(model_path))
            print(f"  [GodMode] Auto-download: {model_path}")

        # Settings
        self.conf_threshold = gconfig.get("conf_threshold", 0.10)
        self.imgsz = gconfig.get("imgsz", 960)
        self.max_det = gconfig.get("max_det", 300)
        self.iou_threshold = gconfig.get("iou_threshold", 0.45)
        self.clahe_enabled = gconfig.get("clahe_enabled", True)
        self.clahe_clip = gconfig.get("clahe_clip", 3.0)

        # CLAHE
        self.clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip, tileGridSize=(8, 8)
        )

        print(f"  [GodMode] conf={self.conf_threshold}, imgsz={self.imgsz}, "
              f"max_det={self.max_det}, CLAHE={self.clahe_enabled}")

    def detect(self, image: np.ndarray) -> List[Detection]:
        """
        Full detection pipeline.
        Returns List[Detection] with retail-mapped class names.
        """
        # 1. CLAHE preprocessing
        if self.clahe_enabled:
            enhanced = self._apply_clahe(image)
        else:
            enhanced = image

        # 2. Run YOLO
        results = self.model.predict(
            source=enhanced,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            max_det=self.max_det,
            imgsz=self.imgsz,
            verbose=False,
        )

        # 3. Process results
        detections = []
        h, w = image.shape[:2]

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                score = float(box.conf[0])
                class_id = int(box.cls[0])
                coco_name = self.model.names.get(class_id, f"object_{class_id}")

                # Filter non-product classes
                if coco_name in self.EXCLUDE_CLASSES:
                    continue

                # Map to retail name
                retail_name = COCO_TO_RETAIL.get(coco_name, coco_name.title())

                # Clamp coordinates
                x1 = max(0, int(x1))
                y1 = max(0, int(y1))
                x2 = min(w, int(x2))
                y2 = min(h, int(y2))

                if x2 - x1 < 5 or y2 - y1 < 5:
                    continue

                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    score=score,
                    class_id=class_id,
                    class_name=retail_name,
                ))

        # Sort by confidence
        detections.sort(key=lambda d: d.score, reverse=True)

        return detections[:self.max_det]

    def _apply_clahe(self, img: np.ndarray) -> np.ndarray:
        """CLAHE on L channel for contrast enhancement."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def get_class_names(self) -> dict:
        return dict(self.model.names)

    def compute_shelf_metrics(
        self, detections: List[Detection], img_h: int, img_w: int
    ) -> Dict[str, Any]:
        """
        Compute shelf-level metrics from detections.
        """
        if not detections:
            return {
                "total_occupancy_pct": 0.0,
                "products_detected": 0,
                "shelf_area_px": img_h * img_w,
                "product_area_px": 0,
            }

        total_area = img_h * img_w
        product_area = sum(
            (d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1])
            for d in detections
        )
        occupancy = min(100.0, (product_area / total_area) * 100)

        return {
            "total_occupancy_pct": round(occupancy, 1),
            "products_detected": len(detections),
            "shelf_area_px": total_area,
            "product_area_px": product_area,
        }

    def compute_per_sku_occupancy(
        self, detections: List[Detection], img_w: int, img_h: int
    ) -> Dict[str, float]:
        """Per-SKU occupancy as % of shelf width."""
        from collections import defaultdict
        sku_widths: Dict[str, float] = defaultdict(float)

        for d in detections:
            w = d.bbox[2] - d.bbox[0]
            sku_widths[d.class_name] += w

        return {
            sku: round((tw / img_w) * 100, 1)
            for sku, tw in sku_widths.items()
        }

    def suggest_action(self, occupancy_pct: float, detection_count: int) -> str:
        """Suggest action based on stock level."""
        if detection_count == 0:
            return "⚠️ Out of Stock - Reponer urgente"
        if occupancy_pct < 15:
            return "🔴 Stock critico - Reponer ahora"
        if occupancy_pct < 30:
            return "🟠 Stock bajo - Reponer pronto"
        if occupancy_pct < 60:
            return "🟡 Stock medio - Monitorear"
        return "🟢 Stock OK"
