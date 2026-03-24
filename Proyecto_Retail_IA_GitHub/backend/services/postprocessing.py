"""

Servicio de Postprocesamiento
Samsung Innovation Campus - Proyecto Academico


Funciones para dibujar resultados sobre imagenes y
construir la respuesta JSON final.

"""

import base64
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.detection import Detection


def _sanitize(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


# Colores por clase (cache para consistencia visual)
_COLOR_CACHE: Dict[str, Tuple[int, int, int]] = {}


def _get_color(class_name: str) -> Tuple[int, int, int]:
    """Genera un color unico y consistente para cada clase."""
    if class_name not in _COLOR_CACHE:
        h = hash(class_name) % 180
        hsv = np.uint8([[[h, 200, 220]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        _COLOR_CACHE[class_name] = (
            int(bgr[0][0][0]),
            int(bgr[0][0][1]),
            int(bgr[0][0][2]),
        )
    return _COLOR_CACHE[class_name]


def draw_detections(
    image: np.ndarray,
    detections: List[Detection],
    sku_names: Optional[List[str]] = None,
    show_confidence: bool = True,
) -> np.ndarray:
    """
    Dibuja bounding boxes y etiquetas sobre la imagen.

    Args:
        image: Imagen original (BGR).
        detections: Lista de detecciones.
        sku_names: Nombres de SKU clasificados (mismo orden que detections).
                   Si es None, usa class_name de la deteccion.
        show_confidence: Si True, muestra la confianza en la etiqueta.

    Returns:
        Imagen con las detecciones dibujadas (BGR).
    """
    result = image.copy()

    for i, det in enumerate(detections):
        x1, y1, x2, y2 = det.bbox

        # Determinar nombre a mostrar
        name = det.class_name
        if sku_names and i < len(sku_names):
            name = sku_names[i]

        color = _get_color(name)

        # Dibujar bounding box
        cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

        # Etiqueta con nombre y confianza
        if show_confidence:
            label = f"{name} {det.score:.0%}"
        else:
            label = name

        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]

        # Fondo de la etiqueta
        cv2.rectangle(
            result,
            (x1, y1 - text_size[1] - 8),
            (x1 + text_size[0] + 4, y1),
            color,
            -1,
        )

        # Texto
        cv2.putText(
            result,
            label,
            (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return result


def image_to_base64(image: np.ndarray, quality: int = 85) -> str:
    """
    Convierte una imagen numpy a string base64 (JPEG).

    Args:
        image: Imagen BGR.
        quality: Calidad JPEG (0-100).

    Returns:
        String base64 de la imagen codificada.
    """
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode(".jpg", image, encode_params)
    return base64.b64encode(buffer).decode("utf-8")


def build_response(
    detections: List[Detection],
    sku_names: List[str],
    sku_confidences: List[float],
    regression_results: Dict[str, float],
    cluster_results: Dict[str, int],
    cluster_labels: Dict[int, str],
    annotated_image_b64: str,
    processing_time: float,
) -> Dict[str, Any]:
    """
    Construye la respuesta JSON completa para el endpoint /api/infer.

    Args:
        detections: Lista de detecciones.
        sku_names: Nombres de SKU clasificados (por deteccion).
        sku_confidences: Confianzas de clasificacion.
        regression_results: {sku_name: estimated_units}.
        cluster_results: {sku_name: cluster_id}.
        cluster_labels: {cluster_id: descripcion}.
        annotated_image_b64: Imagen anotada en base64.
        processing_time: Tiempo de procesamiento en segundos.

    Returns:
        Diccionario con la respuesta completa.
    """
    # --- Lista de productos detectados ---
    products = []
    for i, det in enumerate(detections):
        sku_name = sku_names[i] if i < len(sku_names) else det.class_name
        sku_conf = sku_confidences[i] if i < len(sku_confidences) else det.score
        cluster_id = cluster_results.get(sku_name, 0)

        products.append(_sanitize({
            "sku_id": f"SKU-{det.class_id:03d}",
            "sku_name": sku_name,
            "bbox": list(det.bbox),
            "detection_confidence": round(float(det.score), 3),
            "classification_confidence": round(float(sku_conf), 3),
            "estimated_units": float(regression_results.get(sku_name, 1.0)),
            "cluster_id": int(cluster_id),
            "cluster_label": str(cluster_labels.get(int(cluster_id), "Sin cluster")),
        }))

    # --- Resumen por SKU ---
    sku_summary: Dict[str, Dict] = {}
    for p in products:
        name = p["sku_name"]
        if name not in sku_summary:
            sku_summary[name] = {
                "sku_id": p["sku_id"],
                "sku_name": name,
                "detection_count": 0,
                "total_estimated_units": p["estimated_units"],
                "cluster_id": p["cluster_id"],
                "cluster_label": p["cluster_label"],
            }
        sku_summary[name]["detection_count"] += 1

    summary_list = sorted(
        sku_summary.values(),
        key=lambda x: x["detection_count"],
        reverse=True,
    )

    # --- Respuesta final ---
    response = _sanitize({
        "success": True,
        "processing_time_seconds": round(float(processing_time), 2),
        "total_detections": len(detections),
        "unique_skus": len(sku_summary),
        "annotated_image_base64": annotated_image_b64,
        "products": products,
        "summary": summary_list,
    })

    return response


def build_response_v3(
    detections: List[Detection],
    regression_results: Dict[str, float],
    cluster_results: Dict[str, int],
    cluster_labels: Dict[int, str],
    per_sku_occupancy: Dict[str, float],
    shelf_metrics: Dict[str, Any],
    annotated_image_b64: str,
    processing_time: float,
    suggest_action_fn=None,
) -> Dict[str, Any]:
    """
    Enriched response builder v3 for GodMode pipeline.
    Uses YOLO class names directly (no separate classifier).
    """
    # Cluster descriptions
    CLUSTER_DESCS = {
        0: "SKU de alta rotacion, se agota rapido. Priorizar reposicion.",
        1: "SKU estable, stock consistente. Monitoreo normal.",
        2: "SKU de baja rotacion, stock duradero. Revision periodica.",
    }

    # --- Products ---
    products = []
    for det in detections:
        sku_name = det.class_name
        cluster_id = int(cluster_results.get(sku_name, 0))
        occ = float(per_sku_occupancy.get(sku_name, 0.0))

        products.append(_sanitize({
            "sku_id": f"SKU-{det.class_id:03d}",
            "sku_name": sku_name,
            "bbox": [int(x) for x in det.bbox],
            "detection_confidence": round(float(det.score), 3),
            "classification_confidence": round(float(det.score), 3),
            "estimated_units": float(regression_results.get(sku_name, 1.0)),
            "cluster_id": cluster_id,
            "cluster_label": str(cluster_labels.get(cluster_id, "Sin cluster")),
            "occupancy_pct": occ,
        }))

    # --- Summary by SKU ---
    from collections import defaultdict
    sku_groups: Dict[str, Dict] = {}
    for p in products:
        name = p["sku_name"]
        if name not in sku_groups:
            occ = float(per_sku_occupancy.get(name, 0.0))
            cluster_id = int(p["cluster_id"])
            action = ""
            if suggest_action_fn:
                action = suggest_action_fn(occ, 0)

            # Simulated rotation rate
            units = float(regression_results.get(name, 1.0))
            rotation = round(max(0.1, units * 0.3 + np.random.uniform(-0.2, 0.2)), 1)

            sku_groups[name] = {
                "sku_id": p["sku_id"],
                "sku_name": name,
                "detection_count": 0,
                "total_estimated_units": float(regression_results.get(name, 1.0)),
                "cluster_id": cluster_id,
                "cluster_label": str(cluster_labels.get(cluster_id, "Sin cluster")),
                "cluster_desc": CLUSTER_DESCS.get(cluster_id, ""),
                "occupancy_pct": occ,
                "action": action,
                "rotation_rate": f"{rotation} und/h",
            }
        sku_groups[name]["detection_count"] += 1

    # Recalculate action based on actual detection count
    for name, s in sku_groups.items():
        occ = float(per_sku_occupancy.get(name, 0.0))
        if suggest_action_fn:
            s["action"] = suggest_action_fn(occ, s["detection_count"])

    summary_list = sorted(
        sku_groups.values(),
        key=lambda x: x["detection_count"],
        reverse=True,
    )

    # Low stock count
    low_stock = sum(1 for s in summary_list if s["detection_count"] <= 2)

    # --- Response ---
    response = _sanitize({
        "success": True,
        "processing_time_seconds": round(float(processing_time), 2),
        "total_detections": len(detections),
        "unique_skus": len(sku_groups),
        "annotated_image_base64": annotated_image_b64,
        "products": products,
        "summary": summary_list,
        "shelf_metrics": {
            "total_occupancy_pct": float(shelf_metrics.get("total_occupancy_pct", 0)),
            "out_of_stock_zones": 0,
            "low_stock_skus": low_stock,
        },
    })

    return response
