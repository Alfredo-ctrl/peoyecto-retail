"""
Synthetic Shelf Dataset Generator.
Generates YOLO-format annotated shelf images by compositing product patches
onto shelf backgrounds with realistic augmentation.
"""

import os
import sys
import json
import random
import shutil
from typing import List, Tuple

import cv2
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def generate_shelf_background(
    width: int = 1280, height: int = 720, n_shelves: int = 4
) -> Tuple[np.ndarray, List[int]]:
    """Generate a synthetic shelf background with horizontal lines."""
    bg = np.random.randint(180, 220, (height, width, 3), dtype=np.uint8)

    # Add slight gradient
    for y in range(height):
        factor = 0.9 + 0.1 * (y / height)
        bg[y] = np.clip(bg[y] * factor, 0, 255).astype(np.uint8)

    # Draw shelf lines
    shelf_ys = []
    spacing = height // (n_shelves + 1)
    for i in range(1, n_shelves + 1):
        y = i * spacing + random.randint(-10, 10)
        shelf_ys.append(y)

        # Shelf surface (darker stripe)
        cv2.rectangle(bg, (0, y - 3), (width, y + 5), (130, 125, 120), -1)
        # Edge highlight
        cv2.line(bg, (0, y - 3), (width, y - 3), (160, 155, 150), 1)

    return bg, shelf_ys


def generate_product_patch(
    width: int, height: int, class_id: int, n_classes: int
) -> np.ndarray:
    """Generate a synthetic product patch with distinct color/pattern per class."""
    # Base color per class (HSV for variety)
    hue = int(180 * class_id / n_classes)
    sat = random.randint(120, 255)
    val = random.randint(140, 240)
    base_color = np.array([hue, sat, val], dtype=np.uint8).reshape(1, 1, 3)
    patch_hsv = np.tile(base_color, (height, width, 1))

    # Add pattern variation
    for y in range(height):
        for x in range(width):
            patch_hsv[y, x, 0] = (patch_hsv[y, x, 0] + random.randint(-5, 5)) % 180
            patch_hsv[y, x, 1] = np.clip(patch_hsv[y, x, 1] + random.randint(-20, 20), 0, 255)
            patch_hsv[y, x, 2] = np.clip(patch_hsv[y, x, 2] + random.randint(-20, 20), 0, 255)

    patch_bgr = cv2.cvtColor(patch_hsv, cv2.COLOR_HSV2BGR)

    # Add "label" rectangle (white area with text-like pattern)
    lx1, ly1 = width // 4, height // 3
    lx2, ly2 = 3 * width // 4, 2 * height // 3
    cv2.rectangle(patch_bgr, (lx1, ly1), (lx2, ly2), (240, 240, 240), -1)

    # Simulate text lines
    for t in range(3):
        ty = ly1 + 5 + t * (ly2 - ly1) // 4
        tw = random.randint(lx2 - lx1 - 20, lx2 - lx1 - 5)
        cv2.line(patch_bgr, (lx1 + 5, ty), (lx1 + 5 + tw, ty), (60, 60, 60), 1)

    # Add edge shadow
    cv2.rectangle(patch_bgr, (0, 0), (width - 1, height - 1), (100, 100, 100), 1)

    return patch_bgr


def place_products_on_shelf(
    background: np.ndarray,
    shelf_ys: List[int],
    n_classes: int,
    products_per_row: Tuple[int, int] = (3, 10),
    product_w_range: Tuple[int, int] = (40, 100),
    product_h_range: Tuple[int, int] = (50, 120),
) -> Tuple[np.ndarray, List[dict]]:
    """Place products on shelf background, return annotated image + bboxes."""
    img = background.copy()
    h, w = img.shape[:2]
    annotations = []

    for shelf_idx, shelf_y in enumerate(shelf_ys):
        n_products = random.randint(*products_per_row)
        row_y_bottom = shelf_y - 2  # Just above shelf line

        # Available width with margins
        margin = 20
        avail_width = w - 2 * margin

        # Calculate product placement
        x_cursor = margin + random.randint(0, 15)

        for p in range(n_products):
            pw = random.randint(*product_w_range)
            ph = random.randint(*product_h_range)
            class_id = random.randint(0, n_classes - 1)

            # Position
            x1 = x_cursor
            y1 = row_y_bottom - ph
            x2 = x1 + pw
            y2 = row_y_bottom

            if x2 > w - margin:
                break

            # Generate and place product
            product = generate_product_patch(pw, ph, class_id, n_classes)

            # Random brightness variation
            brightness = random.uniform(0.7, 1.3)
            product = np.clip(product * brightness, 0, 255).astype(np.uint8)

            img[y1:y2, x1:x2] = product

            # YOLO format: class_id, x_center, y_center, w, h (normalized)
            xc = (x1 + x2) / 2.0 / w
            yc = (y1 + y2) / 2.0 / h
            bw = pw / w
            bh = ph / h

            annotations.append({
                "class_id": class_id,
                "x_center": round(xc, 6),
                "y_center": round(yc, 6),
                "width": round(bw, 6),
                "height": round(bh, 6),
                "bbox_abs": [x1, y1, x2, y2],
            })

            x_cursor = x2 + random.randint(1, 10)

    return img, annotations


def apply_realistic_augmentation(img: np.ndarray) -> np.ndarray:
    """Apply realistic augmentations: noise, blur, lighting, color jitter."""
    result = img.copy()

    # Random brightness/contrast
    alpha = random.uniform(0.7, 1.3)
    beta = random.randint(-30, 30)
    result = cv2.convertScaleAbs(result, alpha=alpha, beta=beta)

    # Gaussian noise
    if random.random() < 0.4:
        noise = np.random.normal(0, random.uniform(5, 15), result.shape).astype(np.int16)
        result = np.clip(result.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Blur
    if random.random() < 0.3:
        ksize = random.choice([3, 5])
        result = cv2.GaussianBlur(result, (ksize, ksize), 0)

    # Color jitter (HSV)
    if random.random() < 0.5:
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + random.randint(-10, 10)) % 180
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] + random.randint(-30, 30), 0, 255)
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # Perspective warp (slight)
    if random.random() < 0.3:
        h, w = result.shape[:2]
        offset = random.randint(5, 20)
        src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst_pts = np.float32([
            [random.randint(0, offset), random.randint(0, offset)],
            [w - random.randint(0, offset), random.randint(0, offset)],
            [w - random.randint(0, offset), h - random.randint(0, offset)],
            [random.randint(0, offset), h - random.randint(0, offset)],
        ])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        result = cv2.warpPerspective(result, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

    return result


def generate_dataset(
    output_dir: str,
    n_images: int = 5000,
    n_classes: int = 10,
    img_sizes: List[Tuple[int, int]] = None,
    train_ratio: float = 0.8,
):
    """
    Generate training dataset in YOLO format.

    Structure:
      output_dir/
        images/train/ images/val/
        labels/train/ labels/val/
        data.yaml
    """
    if img_sizes is None:
        img_sizes = [(1280, 720), (960, 640), (800, 600), (1920, 1080)]

    splits = {"train": int(n_images * train_ratio), "val": n_images - int(n_images * train_ratio)}

    # Create directories
    for split in ["train", "val"]:
        os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)

    # Class names
    class_names = [f"product_{i}" for i in range(n_classes)]

    total_generated = 0
    stats = {"total": 0, "total_objects": 0}

    for split, count in splits.items():
        for idx in range(count):
            # Random image size
            w, h = random.choice(img_sizes)
            n_shelves = random.randint(2, 5)

            bg, shelf_ys = generate_shelf_background(w, h, n_shelves)
            img, annotations = place_products_on_shelf(bg, shelf_ys, n_classes)

            # Augmentation
            img = apply_realistic_augmentation(img)

            # Save image
            img_name = f"shelf_{split}_{idx:05d}.jpg"
            img_path = os.path.join(output_dir, "images", split, img_name)
            cv2.imwrite(img_path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])

            # Save YOLO labels
            lbl_name = f"shelf_{split}_{idx:05d}.txt"
            lbl_path = os.path.join(output_dir, "labels", split, lbl_name)
            with open(lbl_path, "w") as f:
                for ann in annotations:
                    f.write(
                        f"{ann['class_id']} {ann['x_center']} {ann['y_center']} "
                        f"{ann['width']} {ann['height']}\n"
                    )

            total_generated += 1
            stats["total_objects"] += len(annotations)

            if total_generated % 500 == 0:
                print(f"  Generated {total_generated}/{n_images} images...")

    stats["total"] = total_generated

    # Write data.yaml for YOLO training
    data_yaml = {
        "path": os.path.abspath(output_dir),
        "train": "images/train",
        "val": "images/val",
        "nc": n_classes,
        "names": class_names,
    }

    with open(os.path.join(output_dir, "data.yaml"), "w") as f:
        yaml.dump(data_yaml, f)

    # Also write JSON metadata
    with open(os.path.join(output_dir, "dataset_meta.json"), "w") as f:
        json.dump({
            "n_images": total_generated,
            "n_classes": n_classes,
            "class_names": class_names,
            "total_objects": stats["total_objects"],
            "img_sizes": img_sizes,
        }, f, indent=2)

    return stats


if __name__ == "__main__":
    import yaml

    output = os.path.join(ROOT_DIR, "data", "synthetic_dataset")
    print("=" * 60)
    print("  Generador de Dataset Sintetico para Retail Shelves")
    print("=" * 60)

    n = 5000
    if len(sys.argv) > 1:
        n = int(sys.argv[1])

    print(f"\n  Generando {n} imagenes...")
    stats = generate_dataset(output, n_images=n, n_classes=10)

    print(f"\n  Dataset generado en: {output}")
    print(f"  Total imagenes: {stats['total']}")
    print(f"  Total objetos: {stats['total_objects']}")
    print(f"  Promedio objetos/imagen: {stats['total_objects']/(stats['total']+1e-6):.1f}")
    print("=" * 60)
