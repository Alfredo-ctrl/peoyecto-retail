"""

Modulo de Clustering de Comportamiento de Stock
Samsung Innovation Campus - Proyecto Academico


"""

import os
import sys
from typing import Dict, List, Optional

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class SKUClustering:
    """
    Clustering de SKUs por comportamiento de stock.

    Attributes:
        model: Modelo KMeans de scikit-learn
        scaler: StandardScaler para normalizar features
        n_clusters: Numero de clusters (default 3)
        cluster_labels: Diccionario {cluster_id: descripcion}
        is_fitted: Si el modelo ha sido entrenado
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el modelo de clustering.

        Args:
            config_path: Ruta al archivo de configuracion YAML.
        """
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        clust_config = config.get("clustering", {})
        self.n_clusters: int = clust_config.get("n_clusters", 3)
        self.random_state: int = clust_config.get("random_state", 42)
        self.feature_names: List[str] = clust_config.get("features", [])

        # Etiquetas descriptivas para cada cluster
        labels_raw = clust_config.get("cluster_labels", {})
        self.cluster_labels: Dict[int, str] = {
            int(k): v for k, v in labels_raw.items()
        }

        # --- Crear modelo K-Means ---
        # NOTA: Para cambiar a otro algoritmo de clustering:
        #   from sklearn.cluster import DBSCAN
        #   self.model = DBSCAN(eps=0.5, min_samples=3)
        #
        #   from sklearn.cluster import AgglomerativeClustering
        #   self.model = AgglomerativeClustering(n_clusters=self.n_clusters)
        #
        #   from sklearn.mixture import GaussianMixture
        #   self.model = GaussianMixture(n_components=self.n_clusters)
        self.model = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=10,
        )

        # Scaler para normalizar features antes de clustering
        self.scaler = StandardScaler()
        self.is_fitted: bool = False

        # --- Cargar modelo si existe ---
        weights_path = os.path.join(ROOT_DIR, config["paths"]["clustering_weights"])
        if os.path.exists(weights_path):
            self.load(weights_path)
            print(f"[SKUClustering] Modelo cargado: {weights_path}")
        else:
            print(f"[SKUClustering] Sin modelo entrenado.")
            print(f"  -> Entrenar con: python training/clustering_train.py")

    def fit(self, X: np.ndarray) -> dict:
        """
        Entrena el modelo de clustering.

        Args:
            X: Matriz de features, shape (n_samples, n_features).

        Returns:
            Diccionario con estadisticas del entrenamiento.
        """
        # Normalizar features
        X_scaled = self.scaler.fit_transform(X)

        # Entrenar K-Means
        self.model.fit(X_scaled)
        self.is_fitted = True

        # Estadisticas
        labels = self.model.labels_
        stats = {
            "n_clusters": self.n_clusters,
            "n_samples": len(X),
            "inertia": round(float(self.model.inertia_), 2),
            "cluster_sizes": {},
        }
        for c in range(self.n_clusters):
            mask = labels == c
            stats["cluster_sizes"][c] = int(mask.sum())

        return stats

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Asigna cluster a nuevas muestras.

        Args:
            X: Matriz de features, shape (n_samples, n_features).

        Returns:
            Array de IDs de cluster, shape (n_samples,).
        """
        if not self.is_fitted:
            print("[WARN] Clustering no entrenado, asignando cluster 0")
            return np.zeros(X.shape[0], dtype=int)

        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict_single(self, features: np.ndarray) -> int:
        """
        Asigna cluster a una unica muestra.

        Args:
            features: Vector de features, shape (n_features,).

        Returns:
            ID del cluster asignado.
        """
        X = features.reshape(1, -1)
        return int(self.predict(X)[0])

    def get_cluster_label(self, cluster_id: int) -> str:
        """
        Retorna la etiqueta descriptiva de un cluster.

        Args:
            cluster_id: ID del cluster.

        Returns:
            Etiqueta descriptiva (ej: "Alta rotacion").
        """
        return self.cluster_labels.get(cluster_id, f"Cluster {cluster_id}")

    def describe_clusters(self) -> List[dict]:
        """
        Retorna estadisticas descriptivas de cada cluster.

        Returns:
            Lista de diccionarios con info por cluster:
              - cluster_id, label, size, center (medias de features)
        """
        if not self.is_fitted:
            return []

        descriptions = []
        centers = self.scaler.inverse_transform(self.model.cluster_centers_)

        for c in range(self.n_clusters):
            center = centers[c]
            feature_dict = {}
            for i, name in enumerate(self.feature_names):
                if i < len(center):
                    feature_dict[name] = round(float(center[i]), 2)

            desc = {
                "cluster_id": c,
                "label": self.get_cluster_label(c),
                "size": int((self.model.labels_ == c).sum()),
                "center": feature_dict,
            }
            descriptions.append(desc)

        return descriptions

    def save(self, path: Optional[str] = None) -> str:
        """
        Guarda el modelo y el scaler en disco.

        Args:
            path: Ruta donde guardar. Si es None, usa la del config.

        Returns:
            Ruta donde se guardo.
        """
        import joblib

        if path is None:
            path = os.path.join(ROOT_DIR, "data", "weights", "clustering.joblib")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "model": self.model,
            "scaler": self.scaler,
            "cluster_labels": self.cluster_labels,
            "feature_names": self.feature_names,
        }
        joblib.dump(data, path)
        print(f"[SKUClustering] Modelo guardado: {path}")
        return path

    def load(self, path: str) -> None:
        """
        Carga modelo y scaler previamente guardados.

        Args:
            path: Ruta al archivo .joblib.
        """
        import joblib

        if os.path.exists(path):
            data = joblib.load(path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.cluster_labels = data.get("cluster_labels", self.cluster_labels)
            self.feature_names = data.get("feature_names", self.feature_names)
            self.is_fitted = True
        else:
            print(f"[WARN] No se encontro modelo en: {path}")
