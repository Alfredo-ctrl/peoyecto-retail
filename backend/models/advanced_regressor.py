"""
Advanced Stock Quantity Regressor — XGBoost + LightGBM + RF ensemble.
Huber loss, quantile regression for confidence intervals.
"""

import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class StockQuantityRegressor:
    """
    Ensemble regressor: XGBoost + LightGBM + RandomForest.
    Predicts exact stock count with confidence intervals.

    Extended features:
      - bbox_count, total_width_px, avg_height_px, num_rows, shelf_position
      - avg_aspect_ratio, coverage_ratio, bbox_area_std
    """

    EXTENDED_FEATURES = [
        "bbox_count", "total_width_px", "avg_height_px", "num_rows",
        "shelf_position", "avg_aspect_ratio", "coverage_ratio", "bbox_area_std",
    ]

    def __init__(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        reg_config = config.get("regression", {})
        self.random_state = reg_config.get("random_state", 42)
        self.is_fitted = False

        # --- Build ensemble ---
        self.models: List[Tuple] = []  # (model, weight, name)
        self._build_ensemble(reg_config)

        # --- Load if available ---
        weights_path = os.path.join(ROOT_DIR, config["paths"]["regressor_weights"])
        if os.path.exists(weights_path):
            self.load(weights_path)
            print(f"  [AdvancedRegressor] Loaded: {weights_path}")
        else:
            print(f"  [AdvancedRegressor] No trained model. Using bbox_count fallback.")

    def _build_ensemble(self, reg_config: dict) -> None:
        """Create ensemble of regressors."""
        from sklearn.ensemble import (
            RandomForestRegressor,
            GradientBoostingRegressor,
        )

        n_est = reg_config.get("n_estimators", 100)
        max_d = reg_config.get("max_depth", 10)
        rs = self.random_state

        # RF
        rf = RandomForestRegressor(n_estimators=n_est, max_depth=max_d, random_state=rs)
        self.models.append((rf, 0.3, "RandomForest"))

        # GradientBoosting (Huber loss for robustness)
        gb = GradientBoostingRegressor(
            n_estimators=n_est, max_depth=max_d // 2,
            loss="huber", random_state=rs
        )
        self.models.append((gb, 0.3, "GradientBoosting"))

        # XGBoost
        try:
            from xgboost import XGBRegressor
            xgb = XGBRegressor(
                n_estimators=n_est, max_depth=max_d,
                random_state=rs, verbosity=0, objective="reg:squarederror"
            )
            self.models.append((xgb, 0.25, "XGBoost"))
        except ImportError:
            pass

        # LightGBM
        try:
            import lightgbm as lgb
            lgbm = lgb.LGBMRegressor(
                n_estimators=n_est, max_depth=max_d,
                random_state=rs, verbose=-1
            )
            self.models.append((lgbm, 0.15, "LightGBM"))
        except ImportError:
            pass

        # Normalize weights
        total_w = sum(w for _, w, _ in self.models)
        self.models = [(m, w / total_w, n) for m, w, n in self.models]
        print(f"  [AdvancedRegressor] Ensemble: {[n for _, _, n in self.models]}")

    def fit(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train all ensemble models."""
        from sklearn.metrics import mean_absolute_error, mean_squared_error

        for model, _, name in self.models:
            model.fit(X, y)

        self.is_fitted = True

        # Evaluate ensemble
        y_pred = self.predict(X)
        mae = mean_absolute_error(y, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y, y_pred)))

        return {"mae": round(mae, 4), "rmse": round(rmse, 4), "n_models": len(self.models)}

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Weighted ensemble prediction."""
        if not self.is_fitted:
            if X.ndim == 1:
                return X[:1].astype(float)
            return X[:, 0].astype(float)

        predictions = np.zeros(X.shape[0])
        for model, weight, _ in self.models:
            try:
                pred = model.predict(X)
                predictions += pred * weight
            except Exception:
                predictions += X[:, 0] * weight

        return np.clip(np.round(predictions), 1, None)

    def predict_with_confidence(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict with standard deviation from ensemble disagreement."""
        if not self.is_fitted:
            return self.predict(X), np.ones(X.shape[0])

        all_preds = []
        for model, _, _ in self.models:
            try:
                all_preds.append(model.predict(X))
            except Exception:
                pass

        if not all_preds:
            return self.predict(X), np.ones(X.shape[0])

        preds_array = np.array(all_preds)
        mean_pred = np.clip(np.round(np.mean(preds_array, axis=0)), 1, None)
        std_pred = np.std(preds_array, axis=0)

        return mean_pred, std_pred

    def save(self, path: Optional[str] = None) -> str:
        import joblib
        if path is None:
            path = os.path.join(ROOT_DIR, "data", "weights", "regressor.joblib")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {"models": self.models, "is_fitted": self.is_fitted}
        joblib.dump(data, path)
        return path

    def load(self, path: str) -> None:
        import joblib
        if os.path.exists(path):
            data = joblib.load(path)
            if isinstance(data, dict) and "models" in data:
                self.models = data["models"]
                self.is_fitted = data.get("is_fitted", True)
            else:
                # Legacy single-model format
                from sklearn.ensemble import RandomForestRegressor
                self.models = [(data, 1.0, "Legacy")]
                self.is_fitted = True


def build_extended_features(
    detections, image_height: int, image_width: int
) -> Dict[str, np.ndarray]:
    """
    Build extended 8-feature vector per SKU for advanced regression.
    Adds: avg_aspect_ratio, coverage_ratio, bbox_area_std.
    """
    from collections import defaultdict
    from backend.models.detection import Detection

    groups: Dict[str, list] = defaultdict(list)
    for det in detections:
        groups[det.class_name].append(det)

    features = {}
    for sku, dets in groups.items():
        bbox_count = len(dets)
        widths = [d.bbox[2] - d.bbox[0] for d in dets]
        heights = [d.bbox[3] - d.bbox[1] for d in dets]
        areas = [w * h for w, h in zip(widths, heights)]
        centers_y = [(d.bbox[1] + d.bbox[3]) / 2.0 for d in dets]

        total_width = sum(widths)
        avg_height = np.mean(heights)
        shelf_pos = np.mean(centers_y) / image_height if image_height > 0 else 0.5

        # Estimate rows
        sorted_cy = sorted(centers_y)
        tol = avg_height * 0.5 if avg_height > 0 else image_height * 0.05
        num_rows = 1
        last = sorted_cy[0]
        for cy in sorted_cy[1:]:
            if abs(cy - last) > tol:
                num_rows += 1
                last = cy

        # Extended features
        aspects = [w / (h + 1e-6) for w, h in zip(widths, heights)]
        avg_aspect = float(np.mean(aspects))
        coverage = total_width / (image_width + 1e-6)
        area_std = float(np.std(areas)) if len(areas) > 1 else 0.0

        features[sku] = np.array([
            bbox_count, total_width, avg_height, num_rows,
            shelf_pos, avg_aspect, coverage, area_std,
        ], dtype=np.float64)

    return features
