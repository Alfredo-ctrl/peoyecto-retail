"""

Modulo de Clasificacion de Productos (SKU)
Samsung Innovation Campus - Proyecto Academico


"""

import os
import sys
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@dataclass
class Classification:
    """Resultado de clasificacion de un producto."""
    class_id: int       # Indice de la clase predicha
    class_name: str     # Nombre legible del SKU
    confidence: float   # Confianza de la prediccion [0, 1]


class ProductClassifier:
    """
    Clasificador de productos basado en ResNet18.

    Utiliza transfer learning: ResNet18 pre-entrenado en ImageNet
    con la ultima capa fully-connected reemplazada para el numero
    de clases SKU configurado.

    Attributes:
        model: Red neuronal PyTorch (ResNet18 modificado)
        class_names: Lista de nombres de las clases SKU
        device: Dispositivo de computo (CPU/GPU)
        transform: Transformaciones de preprocesamiento
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el clasificador.

        Carga un ResNet18 pre-entrenado y ajusta la capa de salida
        al numero de clases configurado. Si existen pesos entrenados,
        los carga; si no, usa los pesos de ImageNet como base.

        Args:
            config_path: Ruta al archivo de configuracion YAML.
        """
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
        backbone_name: str = cls_config.get("backbone", "resnet18")

        # --- Dispositivo de computo ---
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # --- Construir modelo ---
        # Se usa ResNet18 por defecto; se puede cambiar a resnet50
        # o efficientnet_b0 editando config.yaml.
        if backbone_name == "resnet18":
            self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            num_features = self.model.fc.in_features
            self.model.fc = torch.nn.Linear(num_features, self.num_classes)
        elif backbone_name == "resnet50":
            self.model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
            num_features = self.model.fc.in_features
            self.model.fc = torch.nn.Linear(num_features, self.num_classes)
        else:
            # Fallback a resnet18
            self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            num_features = self.model.fc.in_features
            self.model.fc = torch.nn.Linear(num_features, self.num_classes)

        # --- Cargar pesos entrenados si existen ---
        # NOTA: Aqui se cargan pesos finetuneados. Si no existen,
        # el modelo usara pesos de ImageNet + capa FC aleatoria.
        # Para produccion, entrenar con training/classification_train.py
        weights_path = os.path.join(ROOT_DIR, config["paths"]["classifier_weights"])
        if os.path.exists(weights_path):
            self.model.load_state_dict(torch.load(weights_path, map_location=self.device))
            print(f"[ProductClassifier] Pesos cargados: {weights_path}")
        else:
            print(f"[ProductClassifier] Sin pesos entrenados. Usando inicializacion base.")
            print(f"  -> Entrenar con: python training/classification_train.py")

        self.model.to(self.device)
        self.model.eval()

        # --- Transformaciones de preprocesamiento ---
        # Las mismas normalizaciones que ImageNet
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((self.input_size, self.input_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def predict(self, image_crops: List[np.ndarray]) -> List[Classification]:
        """
        Clasifica una lista de crops de productos.

        Args:
            image_crops: Lista de imagenes recortadas (BGR, numpy).
                         Cada una es el crop de un producto detectado.

        Returns:
            Lista de objetos Classification con class_id, class_name
            y confidence para cada crop.
        """
        import torch

        if not image_crops:
            return []

        classifications: List[Classification] = []

        with torch.no_grad():
            for crop in image_crops:
                # Convertir BGR -> RGB
                if len(crop.shape) == 3 and crop.shape[2] == 3:
                    crop_rgb = crop[:, :, ::-1].copy()
                else:
                    crop_rgb = crop.copy()

                # Aplicar transformaciones y agregar dimension de batch
                tensor = self.transform(crop_rgb).unsqueeze(0).to(self.device)

                # Inferencia
                output = self.model(tensor)
                probabilities = torch.nn.functional.softmax(output, dim=1)
                confidence, predicted_idx = torch.max(probabilities, dim=1)

                class_id = predicted_idx.item()
                conf = confidence.item()

                # Obtener nombre de clase
                if class_id < len(self.class_names):
                    class_name = self.class_names[class_id]
                else:
                    class_name = f"Producto_{class_id}"

                classifications.append(Classification(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=conf,
                ))

        return classifications

    def predict_single(self, crop: np.ndarray) -> Classification:
        """
        Clasifica un unico crop de producto.

        Args:
            crop: Imagen recortada (BGR, numpy).

        Returns:
            Objeto Classification con la prediccion.
        """
        results = self.predict([crop])
        return results[0] if results else Classification(0, "Desconocido", 0.0)
