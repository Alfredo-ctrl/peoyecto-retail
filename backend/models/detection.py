"""
Modulo de deteccion de productos en estantes.
Implementa ShelfDetector usando YOLOv8 (Ultralytics).
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import yaml

# Agregar directorio raiz al path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@dataclass
class Detection:
    """Representa una deteccion individual de un producto."""
    bbox: tuple  # (x1, y1, x2, y2) en pixeles
    score: float  # Confianza de la deteccion [0, 1]
    class_id: int  # ID numerico de la clase
    class_name: str  # Nombre legible de la clase


class ShelfDetector:
    """
    Detector de productos en estantes usando YOLOv8.

    Utiliza un modelo YOLO pre-entrenado para detectar objetos
    en imagenes de estantes de retail. Retorna una lista de
    detecciones con bounding boxes, scores y clases.

    Attributes:
        model: Modelo YOLO cargado
        confidence: Umbral de confianza minima
        iou_threshold: Umbral de IoU para NMS
        max_detections: Numero maximo de detecciones
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el detector cargando el modelo YOLO.

        Args:
            config_path: Ruta al archivo de configuracion YAML.
                         Si es None, usa config/config.yaml desde la raiz.
        """
        from ultralytics import YOLO

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # --- Parametros del config ---
        det_config = config.get("detection", {})
        self.confidence: float = det_config.get("confidence_threshold", 0.25)
        self.iou_threshold: float = det_config.get("iou_threshold", 0.45)
        self.max_detections: int = det_config.get("max_detections", 100)
        self.image_size: int = det_config.get("image_size", 640)

        # --- Cargar modelo YOLO ---
        # NOTA: Aqui se cargan los pesos del modelo. Para produccion,
        # se deberian usar pesos finetuneados en un dataset de estantes retail.
        # Actualmente se usan los pesos pre-entrenados de COCO.
        weights_path = os.path.join(ROOT_DIR, config["paths"]["yolo_weights"])
        if not os.path.exists(weights_path):
            print(f"[WARN] Pesos YOLO no encontrados en {weights_path}")
            print("[WARN] Se descargaran automaticamente pesos por defecto (yolov8n.pt)")
            weights_path = "yolov8n.pt"

        self.model = YOLO(weights_path)
        print(f"[ShelfDetector] Modelo YOLO cargado: {weights_path}")

    def detect(self, image: np.ndarray) -> List[Detection]:
        """
        Detecta productos en una imagen de estante.

        Args:
            image: Imagen en formato numpy (BGR, como OpenCV).

        Returns:
            Lista de objetos Detection con bbox, score, class_id y class_name.
        """
        # Ejecutar inferencia YOLO
        results = self.model.predict(
            source=image,
            conf=self.confidence,
            iou=self.iou_threshold,
            max_det=self.max_detections,
            imgsz=self.image_size,
            verbose=False,
        )

        detections: List[Detection] = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                score = float(box.conf[0])
                class_id = int(box.cls[0])
                class_name = self.model.names.get(class_id, f"clase_{class_id}")

                detections.append(Detection(
                    bbox=(x1, y1, x2, y2),
                    score=score,
                    class_id=class_id,
                    class_name=class_name,
                ))

        return detections

    def get_class_names(self) -> dict:
        """Retorna el diccionario de nombres de clase del modelo YOLO."""
        return dict(self.model.names)
