"""
Entrenamiento de clustering de comportamiento de stock.
"""

import os
import sys

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def generate_synthetic_behavior_data(n_samples: int = 300, seed: int = 42):
    """
    Genera un dataset sintetico de comportamiento de stock.

    Simula 3 perfiles de comportamiento distintos:
    - Alta rotacion: bajo stock promedio, alta varianza, muchas alertas
    - Estable: stock medio, baja varianza, pocas alertas
    - Baja rotacion: alto stock, muy baja varianza, sin alertas

    Args:
        n_samples: Numero total de muestras.
        seed: Semilla para reproducibilidad.

    Returns:
        Tupla (X, sku_ids, feature_names):
          X: shape (n_samples, 4)
          sku_ids: lista de IDs de SKU simulados
          feature_names: nombres de features
    """
    np.random.seed(seed)

    feature_names = [
        "avg_stock", "stock_variance", "low_stock_pct", "alert_frequency"
    ]

    n_per_group = n_samples // 3
    remainder = n_samples - 3 * n_per_group

    # --- Grupo 1: Alta rotacion ---
    # Bajo stock, alta varianza, frecuentes alertas
    g1_avg_stock = np.random.uniform(1, 4, n_per_group)
    g1_variance = np.random.uniform(3, 8, n_per_group)
    g1_low_pct = np.random.uniform(0.4, 0.8, n_per_group)
    g1_alerts = np.random.uniform(0.3, 0.7, n_per_group)

    # --- Grupo 2: Estable ---
    # Stock medio, baja varianza, pocas alertas
    g2_avg_stock = np.random.uniform(5, 10, n_per_group)
    g2_variance = np.random.uniform(0.5, 2, n_per_group)
    g2_low_pct = np.random.uniform(0.05, 0.2, n_per_group)
    g2_alerts = np.random.uniform(0.01, 0.1, n_per_group)

    # --- Grupo 3: Baja rotacion ---
    # Alto stock, muy baja varianza, sin alertas
    g3_size = n_per_group + remainder
    g3_avg_stock = np.random.uniform(10, 20, g3_size)
    g3_variance = np.random.uniform(0.1, 1, g3_size)
    g3_low_pct = np.random.uniform(0, 0.05, g3_size)
    g3_alerts = np.random.uniform(0, 0.02, g3_size)

    # Combinar
    X = np.vstack([
        np.column_stack([g1_avg_stock, g1_variance, g1_low_pct, g1_alerts]),
        np.column_stack([g2_avg_stock, g2_variance, g2_low_pct, g2_alerts]),
        np.column_stack([g3_avg_stock, g3_variance, g3_low_pct, g3_alerts]),
    ])

    # Generar IDs de SKU simulados
    sku_ids = [f"SKU-{i:03d}" for i in range(len(X))]

    # Mezclar para que no esten en orden de grupo
    shuffle_idx = np.random.permutation(len(X))
    X = X[shuffle_idx]
    sku_ids = [sku_ids[i] for i in shuffle_idx]

    return X, sku_ids, feature_names


def train_clustering():
    """Funcion principal de entrenamiento del modelo de clustering."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score
    import joblib

    # --- Cargar configuracion ---
    config_path = os.path.join(ROOT_DIR, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    clust_config = config["clustering"]
    n_clusters = clust_config.get("n_clusters", 3)
    random_state = clust_config.get("random_state", 42)

    labels_raw = clust_config.get("cluster_labels", {})
    cluster_labels = {int(k): v for k, v in labels_raw.items()}

    print("Entrenamiento de Clustering de Stock")
    print("-" * 40)

    # --- 1. Generar datos sinteticos ---
    print("\n[1/4] Generando dataset de comportamiento sintetico...")
    X, sku_ids, feature_names = generate_synthetic_behavior_data(n_samples=300)
    print(f"  Muestras: {X.shape[0]}, Features: {X.shape[1]}")
    print(f"  Features: {feature_names}")

    # --- 2. Normalizar ---
    print("\n[2/4] Normalizando features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # --- 3. Entrenar K-Means ---
    print(f"\n[3/4] Entrenando K-Means (k={n_clusters})...")
    model = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=10,
    )
    model.fit(X_scaled)

    labels = model.labels_
    silhouette = silhouette_score(X_scaled, labels)
    print(f"  Silhouette Score: {silhouette:.3f}")
    print(f"  Inertia: {model.inertia_:.2f}")

    # --- 4. Describir clusters ---
    print(f"\n[4/4] Descripcion de clusters:")
    print(f"\n  {'Cluster':<20} {'Label':<18} {'Size':>6} ", end="")
    for fn in feature_names:
        print(f" {fn:>15}", end="")
    print()
    print(f"  {'-'*100}")

    centers = scaler.inverse_transform(model.cluster_centers_)
    for c in range(n_clusters):
        mask = labels == c
        size = mask.sum()
        label = cluster_labels.get(c, f"Cluster {c}")
        print(f"  {f'Cluster {c}':<20} {label:<18} {size:>6} ", end="")
        for j in range(len(feature_names)):
            print(f" {centers[c][j]:>15.2f}", end="")
        print()

    # --- 5. Guardar modelo ---
    weights_path = os.path.join(ROOT_DIR, config["paths"]["clustering_weights"])
    os.makedirs(os.path.dirname(weights_path), exist_ok=True)

    data = {
        "model": model,
        "scaler": scaler,
        "cluster_labels": cluster_labels,
        "feature_names": feature_names,
    }
    joblib.dump(data, weights_path)

    print(f"\nModelo guardado: {weights_path}")
    print(f"Clusters: {n_clusters}")
    print(f"Silhouette: {silhouette:.3f}")
    for c in range(n_clusters):
        label = cluster_labels.get(c, f"Cluster {c}")
        size = (labels == c).sum()
        print(f"  Cluster {c}: {label} ({size} SKUs)")


if __name__ == "__main__":
    train_clustering()
