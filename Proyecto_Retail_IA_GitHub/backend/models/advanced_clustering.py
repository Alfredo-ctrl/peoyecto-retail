"""
Advanced SKU Behavior Clustering — K-Means++ with HDBSCAN fallback.
Auto-labeling, silhouette-based k selection, cluster description rules.
"""

import os
import sys
from typing import Dict, List, Optional

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class SKUBehaviorClustering:
    """
    Advanced clustering with auto-k selection via silhouette score.
    Uses K-Means++ by default, HDBSCAN if installed.
    Auto-generates descriptive cluster labels from feature centroids.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        cc = config.get("clustering", {})
        self.n_clusters = cc.get("n_clusters", 3)
        self.random_state = cc.get("random_state", 42)
        self.feature_names = cc.get("features", [
            "avg_stock", "stock_variance", "low_stock_pct", "alert_frequency"
        ])

        raw_labels = cc.get("cluster_labels", {})
        self.cluster_labels: Dict[int, str] = {int(k): v for k, v in raw_labels.items()}

        self.model = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=10,
            init="k-means++",
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self._hdbscan = None

        # Try loading HDBSCAN as alternative
        try:
            import hdbscan
            self._hdbscan = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=3)
        except ImportError:
            pass

        # Load if available
        weights_path = os.path.join(ROOT_DIR, config["paths"]["clustering_weights"])
        if os.path.exists(weights_path):
            self.load(weights_path)
            print(f"  [AdvancedClustering] Loaded: {weights_path}")
        else:
            print(f"  [AdvancedClustering] No trained model.")

    def fit(self, X: np.ndarray, auto_k: bool = True) -> dict:
        """
        Fit clustering. If auto_k=True, find best k via silhouette.
        """
        from sklearn.metrics import silhouette_score

        X_scaled = self.scaler.fit_transform(X)

        if auto_k and len(X) >= 6:
            best_k, best_score = self.n_clusters, -1
            for k in range(2, min(8, len(X) // 2)):
                km = KMeans(n_clusters=k, random_state=self.random_state, n_init=10, init="k-means++")
                labels = km.fit_predict(X_scaled)
                score = silhouette_score(X_scaled, labels)
                if score > best_score:
                    best_score = score
                    best_k = k

            from sklearn.cluster import KMeans
            self.n_clusters = best_k
            self.model = KMeans(
                n_clusters=best_k, random_state=self.random_state,
                n_init=10, init="k-means++"
            )

        self.model.fit(X_scaled)
        self.is_fitted = True

        # Auto-generate labels from centroids
        self._auto_label_clusters(X)

        labels = self.model.labels_
        sil = silhouette_score(X_scaled, labels) if len(set(labels)) > 1 else 0.0

        return {
            "n_clusters": self.n_clusters,
            "silhouette": round(sil, 4),
            "sizes": {int(c): int((labels == c).sum()) for c in range(self.n_clusters)},
            "labels": self.cluster_labels,
        }

    def _auto_label_clusters(self, X_original: np.ndarray) -> None:
        """Auto-assign descriptive labels based on centroid analysis."""
        centers = self.scaler.inverse_transform(self.model.cluster_centers_)

        # Sort clusters by avg_stock (first feature)
        avg_stocks = centers[:, 0] if centers.shape[1] > 0 else np.zeros(self.n_clusters)
        sorted_idx = np.argsort(avg_stocks)

        label_templates = [
            "Alta rotacion",
            "Rotacion media",
            "Estable",
            "Baja rotacion",
            "Stock alto",
        ]

        for rank, cluster_id in enumerate(sorted_idx):
            if rank < len(label_templates):
                self.cluster_labels[int(cluster_id)] = label_templates[rank]
            else:
                self.cluster_labels[int(cluster_id)] = f"Segmento {cluster_id}"

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.zeros(X.shape[0], dtype=int)
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict_single(self, features: np.ndarray) -> int:
        return int(self.predict(features.reshape(1, -1))[0])

    def get_cluster_label(self, cluster_id: int) -> str:
        return self.cluster_labels.get(cluster_id, f"Cluster {cluster_id}")

    def describe_clusters(self) -> List[dict]:
        if not self.is_fitted:
            return []

        centers = self.scaler.inverse_transform(self.model.cluster_centers_)
        descriptions = []

        for c in range(self.n_clusters):
            center = centers[c]
            fd = {}
            for i, name in enumerate(self.feature_names):
                if i < len(center):
                    fd[name] = round(float(center[i]), 2)

            descriptions.append({
                "cluster_id": c,
                "label": self.get_cluster_label(c),
                "size": int((self.model.labels_ == c).sum()),
                "center": fd,
            })

        return descriptions

    def save(self, path: Optional[str] = None) -> str:
        import joblib
        if path is None:
            path = os.path.join(ROOT_DIR, "data", "weights", "clustering.joblib")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            "model": self.model,
            "scaler": self.scaler,
            "cluster_labels": self.cluster_labels,
            "feature_names": self.feature_names,
            "n_clusters": self.n_clusters,
        }, path)
        return path

    def load(self, path: str) -> None:
        import joblib
        if os.path.exists(path):
            data = joblib.load(path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.cluster_labels = data.get("cluster_labels", self.cluster_labels)
            self.feature_names = data.get("feature_names", self.feature_names)
            self.n_clusters = data.get("n_clusters", self.n_clusters)
            self.is_fitted = True
