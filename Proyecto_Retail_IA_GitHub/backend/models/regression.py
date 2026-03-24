"""

Modulo de Regresion de Stock
Samsung Innovation Campus - Proyecto Academico


"""

import os
import sys
from typing import List, Optional, Tuple

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


class StockRegressor:
    """
    Modelo de regresion para estimar unidades de stock en estante.

    Utiliza RandomForestRegressor por defecto, con opcion de
    cambiar a XGBoost o Regresion Lineal via configuracion.

    Attributes:
        model: Modelo de regresion entrenado (sklearn/xgboost)
        model_type: Tipo de modelo ('random_forest', 'xgboost', 'linear')
        feature_names: Nombres de las features esperadas
        is_fitted: Indica si el modelo ha sido entrenado
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el regresor.

        Crea el modelo segun configuracion. Si existen pesos guardados,
        los carga automaticamente.

        Args:
            config_path: Ruta al archivo de configuracion YAML.
        """
        if config_path is None:
            config_path = os.path.join(ROOT_DIR, "config", "config.yaml")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        reg_config = config.get("regression", {})
        self.model_type: str = reg_config.get("model_type", "random_forest")
        self.n_estimators: int = reg_config.get("n_estimators", 100)
        self.max_depth: int = reg_config.get("max_depth", 10)
        self.random_state: int = reg_config.get("random_state", 42)
        self.feature_names: List[str] = reg_config.get("features", [])
        self.is_fitted: bool = False

        # --- Crear modelo segun tipo ---
        self.model = self._create_model()

        # --- Cargar pesos si existen ---
        weights_path = os.path.join(ROOT_DIR, config["paths"]["regressor_weights"])
        if os.path.exists(weights_path):
            self.load(weights_path)
            print(f"[StockRegressor] Modelo cargado: {weights_path}")
        else:
            print(f"[StockRegressor] Sin modelo entrenado.")
            print(f"  -> Entrenar con: python training/regression_train.py")

    def _create_model(self):
        """Crea el modelo de regresion segun el tipo configurado."""
        if self.model_type == "xgboost":
            try:
                from xgboost import XGBRegressor
                return XGBRegressor(
                    n_estimators=self.n_estimators,
                    max_depth=self.max_depth,
                    random_state=self.random_state,
                    verbosity=0,
                )
            except ImportError:
                print("[WARN] XGBoost no disponible, usando RandomForest")
                self.model_type = "random_forest"

        if self.model_type == "linear":
            from sklearn.linear_model import LinearRegression
            return LinearRegression()

        # Default: random_forest
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> dict:
        """
        Entrena el modelo de regresion.

        Args:
            X: Matriz de features, shape (n_samples, n_features).
            y: Vector de unidades reales, shape (n_samples,).

        Returns:
            Diccionario con metricas de entrenamiento.
        """
        from sklearn.metrics import mean_absolute_error, mean_squared_error

        self.model.fit(X, y)
        self.is_fitted = True

        # Calcular metricas en datos de entrenamiento
        y_pred = self.model.predict(X)
        mae = mean_absolute_error(y, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y, y_pred)))

        metrics = {
            "mae_train": round(mae, 4),
            "rmse_train": round(rmse, 4),
            "n_samples": len(y),
            "model_type": self.model_type,
        }
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predice la cantidad de unidades en el estante.

        Args:
            X: Matriz de features, shape (n_samples, n_features).

        Returns:
            Array de predicciones, shape (n_samples,).
            Cada valor es la cantidad estimada de unidades.
        """
        if not self.is_fitted:
            # Si no esta entrenado, devolver estimacion basada
            # en el conteo de bounding boxes (primera feature)
            print("[WARN] Modelo de regresion no entrenado, usando conteo directo")
            if X.ndim == 1:
                return X[:1].astype(float)  # Solo bbox_count
            return X[:, 0].astype(float)

        predictions = self.model.predict(X)
        # Asegurar que las predicciones sean >= 0
        predictions = np.clip(predictions, 0, None)
        return np.round(predictions).astype(float)

    def save(self, path: Optional[str] = None) -> str:
        """
        Guarda el modelo entrenado en disco.

        Args:
            path: Ruta donde guardar. Si es None, usa la ruta del config.

        Returns:
            Ruta donde se guardo el modelo.
        """
        import joblib

        if path is None:
            path = os.path.join(ROOT_DIR, "data", "weights", "regressor.joblib")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        print(f"[StockRegressor] Modelo guardado: {path}")
        return path

    def load(self, path: str) -> None:
        """
        Carga un modelo previamente entrenado.

        Args:
            path: Ruta al archivo .joblib del modelo.
        """
        import joblib

        if os.path.exists(path):
            self.model = joblib.load(path)
            self.is_fitted = True
        else:
            print(f"[WARN] No se encontro modelo en: {path}")

    def get_feature_importance(self) -> dict:
        """
        Retorna la importancia de cada feature (si el modelo lo soporta).

        Returns:
            Diccionario {nombre_feature: importancia}.
        """
        if not self.is_fitted:
            return {}

        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            if len(self.feature_names) == len(importances):
                return dict(zip(self.feature_names, importances.tolist()))
            return {f"feature_{i}": v for i, v in enumerate(importances)}

        return {}
