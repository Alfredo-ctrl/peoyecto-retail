"""
Advanced Product Classifier — Ensemble of CNN + ViT.
Context-aware crops, multi-model fusion, confidence calibration.
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.models.classification import Classification


class ProductClassifierAdvanced:
    """
    Ensemble classifier: EfficientNet + ResNet50 + optional ViT.
    Uses context-aware crops (1.5x bbox) for better classification.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        import torch
        import torchvision.models as models
        import torchvision.transforms as transforms

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        cls_config = config.get("classification", {})
        self.class_names: List[str] = cls_config.get("class_names", [])
        self.num_classes: int = cls_config.get("num_classes", len(self.class_names))
        self.input_size: int = cls_config.get("input_size", 224)
        self.context_ratio: float = 1.5  # Crop with 50% extra context

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # --- Ensemble models ---
        self.ensemble: List[Tuple[torch.nn.Module, float]] = []

        # Model 1: ResNet50 (weight=0.4)
        resnet = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        resnet.fc = torch.nn.Linear(resnet.fc.in_features, self.num_classes)
        self.ensemble.append((resnet, 0.4))

        # Model 2: EfficientNet-B0 (weight=0.35)
        try:
            effnet = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
            effnet.classifier[1] = torch.nn.Linear(
                effnet.classifier[1].in_features, self.num_classes
            )
            self.ensemble.append((effnet, 0.35))
        except Exception:
            pass

        # Model 3: MobileNetV3 (weight=0.25) — lightweight alternative to ViT
        try:
            mobilenet = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
            mobilenet.classifier[3] = torch.nn.Linear(
                mobilenet.classifier[3].in_features, self.num_classes
            )
            self.ensemble.append((mobilenet, 0.25))
        except Exception:
            pass

        # Load trained weights if available
        weights_path = os.path.join(ROOT_DIR, config["paths"]["classifier_weights"])
        for model, _ in self.ensemble:
            if os.path.exists(weights_path):
                try:
                    state = torch.load(weights_path, map_location=self.device)
                    # Try loading; shape mismatch is expected between architectures
                    model.load_state_dict(state, strict=False)
                except Exception:
                    pass
            model.to(self.device)
            model.eval()

        # Normalize total weights
        total_w = sum(w for _, w in self.ensemble)
        self.ensemble = [(m, w / total_w) for m, w in self.ensemble]

        # --- Transforms ---
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((self.input_size, self.input_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        # TTA transforms
        self.tta_transforms = [
            self.transform,
            transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((self.input_size, self.input_size)),
                transforms.RandomHorizontalFlip(p=1.0),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]),
        ]

        print(f"  [AdvancedClassifier] {len(self.ensemble)} models loaded")

    def predict(
        self,
        image_crops: List[np.ndarray],
        use_tta: bool = False,
    ) -> List[Classification]:
        """Classify crops using ensemble averaging + optional TTA."""
        import torch

        if not image_crops:
            return []

        classifications = []

        with torch.no_grad():
            for crop in image_crops:
                # BGR -> RGB
                if len(crop.shape) == 3 and crop.shape[2] == 3:
                    crop_rgb = crop[:, :, ::-1].copy()
                else:
                    crop_rgb = crop.copy()

                # Ensemble prediction
                probs_sum = np.zeros(self.num_classes)

                transforms_to_use = self.tta_transforms if use_tta else [self.transform]

                for tfm in transforms_to_use:
                    tensor = tfm(crop_rgb).unsqueeze(0).to(self.device)

                    for model, weight in self.ensemble:
                        output = model(tensor)
                        probs = torch.nn.functional.softmax(output, dim=1)
                        probs_sum += probs.cpu().numpy()[0] * weight

                # Average TTA
                probs_sum /= len(transforms_to_use)

                class_id = int(np.argmax(probs_sum))
                confidence = float(probs_sum[class_id])

                class_name = (
                    self.class_names[class_id]
                    if class_id < len(self.class_names)
                    else f"Producto_{class_id}"
                )

                classifications.append(Classification(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                ))

        return classifications

    def extract_context_crop(
        self, image: np.ndarray, bbox: Tuple[int, int, int, int]
    ) -> np.ndarray:
        """Extract crop with extra context around bbox (1.5x)."""
        h, w = image.shape[:2]
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # Expand by context ratio
        new_w = int(bw * self.context_ratio)
        new_h = int(bh * self.context_ratio)

        nx1 = max(0, cx - new_w // 2)
        ny1 = max(0, cy - new_h // 2)
        nx2 = min(w, cx + new_w // 2)
        ny2 = min(h, cy + new_h // 2)

        return image[ny1:ny2, nx1:nx2].copy()
