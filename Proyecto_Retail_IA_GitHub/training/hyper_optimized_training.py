"""
Hyper-Optimized YOLO Training for Retail Shelf Detection.
Multi-scale, augmentation-heavy, auto-anchor, TTA, evolution.
"""

import os
import sys
from typing import Optional

import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def train_detector(
    dataset_path: Optional[str] = None,
    model_name: str = "yolov8x.pt",
    epochs: int = 100,
    batch_size: int = 8,
    imgsz: int = 960,
    device: str = "",
):
    """
    Train YOLO detector with hyper-optimized settings for retail shelves.

    Features:
    - Auto-anchor optimization for dense small objects
    - Mosaic + MixUp + Copy-Paste augmentation
    - Multi-scale training (random 0.5x-1.5x)
    - Cosine LR annealing
    - Early stopping + best checkpoint
    - CIoU loss
    """
    from ultralytics import YOLO

    if dataset_path is None:
        dataset_path = os.path.join(ROOT_DIR, "data", "synthetic_dataset", "data.yaml")

    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset not found: {dataset_path}")
        print("  Run first: python training/generate_synthetic_dataset.py")
        return

    print("=" * 60)
    print("  Hyper-Optimized YOLO Training")
    print("=" * 60)

    # Load or download base model
    base_weights = os.path.join(ROOT_DIR, "data", "weights", model_name)
    if os.path.exists(base_weights):
        model = YOLO(base_weights)
        print(f"  Base model: {base_weights}")
    else:
        model = YOLO(model_name)
        print(f"  Base model (auto-download): {model_name}")

    # Training config — maximum augmentation for retail
    train_args = {
        "data": dataset_path,
        "epochs": epochs,
        "batch": batch_size,
        "imgsz": imgsz,
        "device": device if device else None,

        # Optimizer
        "optimizer": "AdamW",
        "lr0": 0.001,
        "lrf": 0.01,
        "weight_decay": 0.0005,
        "warmup_epochs": 5,
        "cos_lr": True,  # Cosine annealing

        # Augmentation (aggressive for retail)
        "mosaic": 1.0,        # Mosaic augmentation
        "mixup": 0.15,        # MixUp probability
        "copy_paste": 0.2,    # Copy-Paste augmentation
        "degrees": 5.0,       # Rotation
        "translate": 0.1,
        "scale": 0.5,         # Multi-scale range
        "shear": 2.0,
        "flipud": 0.0,        # No vertical flip (shelves are always upright)
        "fliplr": 0.5,        # Horizontal flip OK
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "erasing": 0.3,       # Random erasing (simulates occlusion)

        # Training settings
        "patience": 20,       # Early stopping patience
        "save_period": 10,    # Checkpoint every N epochs
        "val": True,
        "plots": True,
        "verbose": True,

        # Loss
        "box": 7.5,           # Box loss gain (higher for precision)
        "cls": 0.5,           # Classification loss gain
        "dfl": 1.5,           # Distribution focal loss

        # Detection settings
        "nms": True,
        "max_det": 300,       # Max detections per image (retail can be dense)
        "iou": 0.5,

        # Output
        "project": os.path.join(ROOT_DIR, "data", "training_runs"),
        "name": "retail_shelf_detector",
        "exist_ok": True,
    }

    print(f"\n  Dataset: {dataset_path}")
    print(f"  Epochs: {epochs}")
    print(f"  Image size: {imgsz}")
    print(f"  Batch: {batch_size}")
    print(f"  Augmentation: Mosaic+MixUp+CopyPaste+Erasing")
    print()

    # Train
    results = model.train(**train_args)

    # Save best weights to standard location
    best_weights = os.path.join(
        ROOT_DIR, "data", "training_runs", "retail_shelf_detector", "weights", "best.pt"
    )
    output_path = os.path.join(ROOT_DIR, "data", "weights", "retail_detector_best.pt")

    if os.path.exists(best_weights):
        import shutil
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        shutil.copy2(best_weights, output_path)
        print(f"\n  Best weights saved to: {output_path}")

    print("\n  Training complete!")
    print("=" * 60)

    return results


def train_with_tta_validation(
    dataset_path: Optional[str] = None,
    model_path: Optional[str] = None,
):
    """Validate a trained model with Test-Time Augmentation (TTA)."""
    from ultralytics import YOLO

    if model_path is None:
        model_path = os.path.join(ROOT_DIR, "data", "weights", "retail_detector_best.pt")
    if dataset_path is None:
        dataset_path = os.path.join(ROOT_DIR, "data", "synthetic_dataset", "data.yaml")

    if not os.path.exists(model_path):
        print(f"[ERROR] Model not found: {model_path}")
        return

    model = YOLO(model_path)

    print("  Validating with TTA...")
    results = model.val(
        data=dataset_path,
        imgsz=960,
        batch=4,
        augment=True,  # TTA
        verbose=True,
    )

    print(f"\n  mAP@0.5:     {results.box.map50:.4f}")
    print(f"  mAP@0.5:0.95: {results.box.map:.4f}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--model", type=str, default="yolov8x.pt")
    parser.add_argument("--device", type=str, default="")
    parser.add_argument("--dataset", type=str, default=None)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.validate_only:
        train_with_tta_validation(args.dataset)
    else:
        train_detector(
            dataset_path=args.dataset,
            model_name=args.model,
            epochs=args.epochs,
            batch_size=args.batch,
            imgsz=args.imgsz,
            device=args.device,
        )
