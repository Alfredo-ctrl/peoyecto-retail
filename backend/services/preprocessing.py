"""

Servicio de Preprocesamiento
Samsung Innovation Campus - Proyecto Academico


Funciones para preparar imagenes y extraer features
para los modelos de clasificacion y regresion.

"""

import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple

import cv2
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Importamos el tipo Detection del modulo de deteccion
from backend.models.detection import Detection


def preprocess_image(raw_bytes: bytes) -> np.ndarray:
    """
    Convierte bytes de imagen a un array numpy BGR (OpenCV).

    Args:
        raw_bytes: Bytes crudos de la imagen subida.

    Returns:
        Imagen como numpy array (BGR, uint8).

    Raises:
        ValueError: Si la imagen no se puede decodificar.
    """
    nparr = np.frombuffer(raw_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("No se pudo decodificar la imagen. Verifique el formato.")
    return image


def extract_crops(
    image: np.ndarray,
    detections: List[Detection],
    min_size: int = 10,
) -> List[np.ndarray]:
    """
    Extrae crops (recortes) de la imagen para cada deteccion.

    Args:
        image: Imagen original (BGR).
        detections: Lista de detecciones con bounding boxes.
        min_size: Tamano minimo del crop en pixeles.

    Returns:
        Lista de crops (imagenes recortadas) en el mismo orden
        que las detecciones.
    """
    h, w = image.shape[:2]
    crops: List[np.ndarray] = []

    for det in detections:
        x1, y1, x2, y2 = det.bbox
        # Clamp a los limites de la imagen
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        crop = image[y1:y2, x1:x2]

        if crop.shape[0] < min_size or crop.shape[1] < min_size:
            # Crop demasiado pequeno, redimensionar
            crop = cv2.resize(crop, (min_size, min_size))

        crops.append(crop)

    return crops


def build_regression_features(
    detections: List[Detection],
    image_height: int,
    image_width: int,
) -> Dict[str, np.ndarray]:
    """
    Construye el vector de features para regresion agrupado por SKU.

    Para cada SKU unico detectado, calcula:
      - bbox_count:     Numero de bounding boxes
      - total_width_px: Ancho total ocupado (suma de anchos de bbox)
      - avg_height_px:  Altura promedio de las detecciones
      - num_rows:       Numero de filas estimado (apilamiento vertical)
      - shelf_position: Posicion vertical normalizada (0=arriba, 1=abajo)

    Args:
        detections: Lista de detecciones.
        image_height: Altura de la imagen original.
        image_width: Ancho de la imagen original.

    Returns:
        Diccionario {sku_name: feature_vector (np.ndarray shape (5,))}
    """
    # Agrupar detecciones por nombre de clase
    groups: Dict[str, List[Detection]] = defaultdict(list)
    for det in detections:
        groups[det.class_name].append(det)

    features_per_sku: Dict[str, np.ndarray] = {}

    for sku_name, dets in groups.items():
        # 1. Conteo de bounding boxes
        bbox_count = len(dets)

        # 2. Ancho total ocupado en pixeles
        total_width = sum(d.bbox[2] - d.bbox[0] for d in dets)

        # 3. Altura promedio de las detecciones
        heights = [d.bbox[3] - d.bbox[1] for d in dets]
        avg_height = np.mean(heights) if heights else 0.0

        # 4. Numero de filas estimado
        # Se estima contando centros y cuantas de las detecciones
        # se considera que estan en la misma fila (dentro de un
        # margen vertical)
        num_rows = _estimate_rows(dets, image_height)

        # 5. Posicion en el estante (normalizada 0-1)
        # Promedio de las coordenadas Y centrales, normalizado
        centers_y = [(d.bbox[1] + d.bbox[3]) / 2.0 for d in dets]
        shelf_position = np.mean(centers_y) / image_height if image_height > 0 else 0.5

        features_per_sku[sku_name] = np.array([
            bbox_count,
            total_width,
            avg_height,
            num_rows,
            shelf_position,
        ], dtype=np.float64)

    return features_per_sku


def _estimate_rows(detections: List[Detection], image_height: int) -> int:
    """
    Estima el numero de filas de productos apilados.

    Agrupa las detecciones por su coordenada Y central,
    considerando un margen de tolerancia.
    """
    if not detections:
        return 0

    # Centros Y de cada deteccion
    centers_y = sorted([(d.bbox[1] + d.bbox[3]) / 2.0 for d in detections])

    # Margen de tolerancia: 15% de la altura promedio del bbox
    avg_h = np.mean([d.bbox[3] - d.bbox[1] for d in detections])
    tolerance = avg_h * 0.5 if avg_h > 0 else image_height * 0.05

    rows = 1
    last_y = centers_y[0]
    for cy in centers_y[1:]:
        if abs(cy - last_y) > tolerance:
            rows += 1
            last_y = cy

    return rows


def build_clustering_features_from_history(
    stock_history: List[float],
    low_stock_threshold: float = 2.0,
) -> np.ndarray:
    """
    Construye features de comportamiento para clustering.

    Features:
      - avg_stock:       Promedio de stock
      - stock_variance:  Varianza del stock
      - low_stock_pct:   % de observaciones con stock bajo
      - alert_frequency: Frecuencia de alertas (transiciones a bajo stock)

    Args:
        stock_history: Lista de valores de stock estimado en el tiempo.
        low_stock_threshold: Umbral para considerar stock bajo.

    Returns:
        Vector de features, shape (4,).
    """
    if not stock_history:
        return np.array([0.0, 0.0, 1.0, 0.0])

    arr = np.array(stock_history, dtype=np.float64)

    avg_stock = float(np.mean(arr))
    stock_variance = float(np.var(arr))

    low_count = int(np.sum(arr < low_stock_threshold))
    low_stock_pct = low_count / len(arr)

    # Contar transiciones de stock normal a stock bajo
    alerts = 0
    for i in range(1, len(arr)):
        if arr[i] < low_stock_threshold and arr[i - 1] >= low_stock_threshold:
            alerts += 1
    alert_frequency = alerts / len(arr)

    return np.array([avg_stock, stock_variance, low_stock_pct, alert_frequency])
