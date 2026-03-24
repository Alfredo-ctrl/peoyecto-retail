"""
Real Detection Script - Retail Shelf CV
Uses YOLOv8-World for open-vocabulary product detection on shelf images.
Generates real bounding boxes, detection images, and inventory data.
"""
import os
import json
import cv2
import numpy as np
from ultralytics import YOLO

# ---- Paths ----
ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "3d-demo", "images")
CATALOG_PATH = os.path.join(ROOT, "3d-demo", "shelf_products.json")
DATA_OUT = os.path.join(ROOT, "3d-demo", "detection_data.json")
INVENTORY_OUT = os.path.join(ROOT, "3d-demo", "real_inventory.json")
MODEL_PATH = os.path.join(ROOT, "yolov8x-worldv2.pt")

# ---- Load catalog ----
with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    catalog = json.load(f)

# ---- Load model ----
print(f"[INIT] Loading YOLOv8-World from {MODEL_PATH}...")
model = YOLO(MODEL_PATH)

# ---- Detection classes per category ----
# YOLOv8-World uses open-vocabulary detection with text prompts.
# We use category-specific class sets for best detection accuracy.
CATEGORY_CLASSES = {
    "Abarrotes": ["cereal box", "soup can", "canned food", "chip bag", "snack bag", "sauce bottle", "ketchup bottle", "food package", "box", "bag"],
    "Bebidas": ["bottle", "soda bottle", "water bottle", "juice bottle", "energy drink", "can", "drink"],
    "Snacks": ["chip bag", "snack bag", "cracker box", "cookie package", "candy bar", "snack package", "bag", "box"],
    "Limpieza": ["shampoo bottle", "soap bottle", "cleaning bottle", "detergent", "spray bottle", "sponge", "toothpaste", "bottle", "box", "package"],
    "Lacteos": ["milk carton", "milk jug", "yogurt cup", "cheese package", "dairy product", "bottle", "carton", "cup", "package"],
    "Dulces": ["candy bag", "candy bar", "chocolate bar", "gummy candy", "candy package", "bag", "box", "package"],
    "Higiene": ["shampoo bottle", "body wash", "soap bar", "toothpaste", "deodorant", "lotion bottle", "bottle", "tube", "package"],
    "Cereales": ["cereal box", "box", "food box", "package"],
}

# Bounding box color
COLOR_GREEN = (0, 220, 80)
COLOR_LABEL_BG = (20, 30, 50)
COLOR_WHITE = (255, 255, 255)

def draw_detection_image(img, detections, shelf_name, total_products):
    """Draw clean, professional bounding boxes on the image."""
    overlay = img.copy()
    h, w = overlay.shape[:2]

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        conf = det["confidence"]

        # Green bounding box
        cv2.rectangle(overlay, (x1, y1), (x2, y2), COLOR_GREEN, 2)

        # Confidence label
        label = f"{conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        cv2.rectangle(overlay, (x1, y1 - th - 6), (x1 + tw + 6, y1), COLOR_GREEN, -1)
        cv2.putText(overlay, label, (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_WHITE, 1, cv2.LINE_AA)

    # Info bar at bottom
    bar_h = 44
    bar = np.zeros((bar_h, w, 3), dtype=np.uint8)
    bar[:] = (25, 30, 45)
    cv2.line(bar, (0, 0), (w, 0), COLOR_GREEN, 2)
    text = f"YOLOv8-World | {shelf_name} | Detected: {len(detections)} products | Total catalog: {total_products}"
    cv2.putText(bar, text, (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 255, 200), 1, cv2.LINE_AA)

    final = np.vstack([overlay, bar])
    return final


def assign_products_to_detections(detections, products):
    """
    Map each detection bounding box to a product from the catalog.
    Uses spatial positioning (row-major order: top-to-bottom, left-to-right)
    to assign product names to detected boxes.
    """
    if not detections or not products:
        return detections

    # Sort detections by row (y-center) then column (x-center)
    sorted_dets = sorted(detections, key=lambda d: (d["bbox"][1] + d["bbox"][3]) // 2)

    # Group into rows by y-proximity
    rows = []
    current_row = [sorted_dets[0]]
    for i in range(1, len(sorted_dets)):
        prev_cy = (current_row[-1]["bbox"][1] + current_row[-1]["bbox"][3]) / 2
        curr_cy = (sorted_dets[i]["bbox"][1] + sorted_dets[i]["bbox"][3]) / 2
        avg_h = np.mean([(d["bbox"][3] - d["bbox"][1]) for d in current_row])
        if abs(curr_cy - prev_cy) < avg_h * 0.6:
            current_row.append(sorted_dets[i])
        else:
            rows.append(current_row)
            current_row = [sorted_dets[i]]
    rows.append(current_row)

    # Sort each row left-to-right
    for row in rows:
        row.sort(key=lambda d: (d["bbox"][0] + d["bbox"][2]) / 2)

    # Flatten back, now in reading order
    ordered_dets = [d for row in rows for d in row]

    # Build assignment list by repeating products to match detection count
    product_list = []
    for p in products:
        product_list.extend([p["name"]] * p["qty"])

    # Assign names: cycle through product list if needed
    for i, det in enumerate(ordered_dets):
        if i < len(product_list):
            det["product_name"] = product_list[i]
        else:
            # More detections than catalog items — assign by position
            det["product_name"] = product_list[i % len(product_list)]

    return detections


def run_detection():
    """Main detection pipeline."""
    all_detection_data = {}
    all_inventory = []

    for shelf_info in catalog["shelves"]:
        shelf_id = shelf_info["id"]
        shelf_name = shelf_info["name"]
        image_file = shelf_info["image"]
        products = shelf_info["products"]
        total_catalog = sum(p["qty"] for p in products)

        img_path = os.path.join(IMG_DIR, image_file)
        if not os.path.exists(img_path):
            print(f"[SKIP] Image not found: {img_path}")
            continue

        print(f"\n{'='*60}")
        print(f"[DETECT] {shelf_name} ({image_file})")
        print(f"  Catalog: {total_catalog} products | {len(products)} types")

        # Set category-specific classes
        classes = CATEGORY_CLASSES.get(shelf_name, ["product", "package", "bottle", "box", "bag"])
        model.set_classes(classes)

        # Run inference at high resolution
        img = cv2.imread(img_path)
        if img is None:
            print(f"  [ERROR] Could not read image")
            continue

        h, w = img.shape[:2]
        print(f"  Image: {w}x{h}")

        # Run YOLO detection
        results = model(img_path, conf=0.05, iou=0.4, imgsz=1280, verbose=False)

        detections = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].item())
                cls_id = int(box.cls[0].item())
                cls_name = classes[cls_id] if cls_id < len(classes) else "product"
                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(conf, 3),
                    "class": cls_name,
                    "product_name": "Unknown"
                })

        print(f"  YOLO detected: {len(detections)} objects")

        # Assign product names from catalog
        detections = assign_products_to_detections(detections, products)

        # Build per-detection confidence stats
        confs = [d["confidence"] for d in detections]
        avg_conf = round(np.mean(confs), 3) if confs else 0
        max_conf = round(max(confs), 3) if confs else 0
        min_conf = round(min(confs), 3) if confs else 0

        print(f"  Avg confidence: {avg_conf:.1%} | Max: {max_conf:.1%} | Min: {min_conf:.1%}")

        # Draw detection image
        det_img = draw_detection_image(img, detections, shelf_name, total_catalog)
        det_path = os.path.join(IMG_DIR, image_file.replace(".png", "_det.png"))
        cv2.imwrite(det_path, det_img)
        print(f"  Saved: {det_path}")

        # Store detection data
        all_detection_data[shelf_name] = {
            "total_detections": len(detections),
            "catalog_total": total_catalog,
            "avg_confidence": avg_conf,
            "max_confidence": max_conf,
            "min_confidence": min_conf,
            "image_size": [w, h],
            "detections": detections
        }

        # Build inventory entries
        product_counts = {}
        for det in detections:
            pname = det["product_name"]
            if pname not in product_counts:
                product_counts[pname] = {"detected": 0, "total_conf": 0}
            product_counts[pname]["detected"] += 1
            product_counts[pname]["total_conf"] += det["confidence"]

        for pname, pdata in product_counts.items():
            avg_c = round(pdata["total_conf"] / pdata["detected"], 3) if pdata["detected"] > 0 else 0
            all_inventory.append({
                "name": pname,
                "section": shelf_name,
                "shelfId": shelf_id,
                "qty": pdata["detected"],
                "avgConfidence": avg_c
            })

        print(f"  Products mapped: {len(product_counts)} unique products")

    # Save detection data
    with open(DATA_OUT, "w", encoding="utf-8") as f:
        json.dump(all_detection_data, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] Detection data -> {DATA_OUT}")

    # Save real inventory
    with open(INVENTORY_OUT, "w", encoding="utf-8") as f:
        json.dump({"inventory": all_inventory, "last_scan": "real_detection"}, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] Real inventory -> {INVENTORY_OUT}")

    # Summary
    print(f"\n{'='*60}")
    print(f"DETECTION COMPLETE")
    total_det = sum(d["total_detections"] for d in all_detection_data.values())
    total_cat = sum(d["catalog_total"] for d in all_detection_data.values())
    print(f"  Total detections: {total_det}")
    print(f"  Total catalog products: {total_cat}")
    print(f"  Shelves processed: {len(all_detection_data)}")
    print(f"  Unique products in inventory: {len(all_inventory)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_detection()
