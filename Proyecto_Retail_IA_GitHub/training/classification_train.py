"""
Entrenamiento de clasificacion de productos (SKU).
"""

import os
import sys

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def create_synthetic_dataset(class_names, num_per_class=50, img_size=224):
    """
    Crea un dataset sintetico para demostrar el pipeline de entrenamiento.

    Genera imagenes de colores aleatorios con patrones simples
    que representen distintas clases de productos.

    NOTA: Para datos reales, reemplazar esta funcion por un
    ImageFolder de torchvision apuntando a data/raw/classification/

    Args:
        class_names: Lista de nombres de clase.
        num_per_class: Numero de imagenes sinteticas por clase.
        img_size: Tamano de las imagenes generadas.

    Returns:
        Tupla (images, labels) como listas.
    """
    import cv2

    images = []
    labels = []

    for class_idx, class_name in enumerate(class_names):
        # Generar color base unico por clase
        np.random.seed(class_idx * 42)
        base_color = np.random.randint(50, 200, size=3)

        for i in range(num_per_class):
            # Crear imagen con variaciones de color
            noise = np.random.randint(-30, 30, size=3)
            color = np.clip(base_color + noise, 0, 255).astype(np.uint8)

            img = np.full((img_size, img_size, 3), color, dtype=np.uint8)

            # Agregar patrones geometricos unicos por clase
            pattern_seed = class_idx * 1000 + i
            np.random.seed(pattern_seed)

            # Rectangulos internos
            for _ in range(class_idx + 1):
                x1 = np.random.randint(10, img_size // 2)
                y1 = np.random.randint(10, img_size // 2)
                x2 = np.random.randint(img_size // 2, img_size - 10)
                y2 = np.random.randint(img_size // 2, img_size - 10)
                rect_color = np.random.randint(0, 255, size=3).tolist()
                cv2.rectangle(img, (x1, y1), (x2, y2), rect_color, 2)

            # Agregar ruido gaussiano
            noise_img = np.random.normal(0, 10, img.shape).astype(np.int16)
            img = np.clip(img.astype(np.int16) + noise_img, 0, 255).astype(np.uint8)

            images.append(img)
            labels.append(class_idx)

    return images, labels


def train_classifier():
    """Funcion principal de entrenamiento del clasificador."""
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torchvision.models as models
    import torchvision.transforms as transforms
    from torch.utils.data import DataLoader, TensorDataset

    # --- Cargar configuracion ---
    config_path = os.path.join(ROOT_DIR, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    cls_config = config["classification"]
    class_names = cls_config["class_names"]
    num_classes = cls_config["num_classes"]
    input_size = cls_config["input_size"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Dispositivo: {device}")
    print(f"Clases: {class_names}")
    print(f"Numero de clases: {num_classes}")

    # --- 1. Crear dataset sintetico ---
    print("\n[1/5] Generando dataset sintetico...")
    images, labels = create_synthetic_dataset(
        class_names, num_per_class=60, img_size=input_size
    )
    print(f"  Total de imagenes: {len(images)}")

    # --- 2. Transformaciones y Data Augmentation ---
    print("[2/5] Preparando augmentaciones...")
    transform_train = transforms.Compose([
        transforms.ToPILImage(),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.RandomResizedCrop(input_size, scale=(0.85, 1.0)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    transform_val = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((input_size, input_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # Convertir imagenes BGR a RGB y aplicar transformaciones
    all_tensors = []
    for img in images:
        img_rgb = img[:, :, ::-1].copy()
        tensor = transform_train(img_rgb)
        all_tensors.append(tensor)

    X = torch.stack(all_tensors)
    y = torch.tensor(labels, dtype=torch.long)

    # Split train/val (80/20)
    n_total = len(X)
    n_train = int(n_total * 0.8)
    indices = torch.randperm(n_total)

    X_train, y_train = X[indices[:n_train]], y[indices[:n_train]]
    X_val, y_val = X[indices[n_train:]], y[indices[n_train:]]

    train_dataset = TensorDataset(X_train, y_train)
    val_dataset = TensorDataset(X_val, y_val)

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)

    print(f"  Train: {len(train_dataset)}, Val: {len(val_dataset)}")

    # --- 3. Construir modelo ---
    print("[3/5] Construyendo modelo ResNet18...")
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

    # Congelar capas iniciales (transfer learning)
    for param in model.parameters():
        param.requires_grad = False

    # Descongelar las ultimas capas
    for param in model.layer4.parameters():
        param.requires_grad = True

    # Reemplazar capa FC
    num_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(num_features, num_classes),
    )

    model = model.to(device)

    # --- 4. Entrenamiento ---
    print("[4/5] Entrenando modelo...")
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=0.001,
    )
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)

    num_epochs = 15
    best_val_acc = 0.0
    best_model_state = None

    for epoch in range(num_epochs):
        # --- Train ---
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            train_correct += (predicted == targets).sum().item()
            train_total += targets.size(0)

        scheduler.step()

        train_acc = train_correct / train_total if train_total > 0 else 0

        # --- Validation ---
        model.eval()
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                _, predicted = torch.max(outputs, 1)
                val_correct += (predicted == targets).sum().item()
                val_total += targets.size(0)

        val_acc = val_correct / val_total if val_total > 0 else 0

        print(f"  Epoch {epoch+1:02d}/{num_epochs}: "
              f"Loss={train_loss/train_total:.4f}, "
              f"Train Acc={train_acc:.1%}, Val Acc={val_acc:.1%}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_state = model.state_dict().copy()

    # --- 5. Guardar modelo ---
    print("[5/5] Guardando modelo...")
    weights_path = os.path.join(ROOT_DIR, config["paths"]["classifier_weights"])
    os.makedirs(os.path.dirname(weights_path), exist_ok=True)

    if best_model_state:
        torch.save(best_model_state, weights_path)
    else:
        torch.save(model.state_dict(), weights_path)

    print(f"\nEntrenamiento completado")
    print(f"Mejor Val Accuracy: {best_val_acc:.1%}")
    print(f"Pesos guardados en: {weights_path}")


if __name__ == "__main__":
    train_classifier()
