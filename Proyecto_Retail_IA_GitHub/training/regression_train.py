"""
Entrenamiento de regresion de stock.
"""

import os
import sys

import numpy as np
import yaml

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def generate_synthetic_regression_data(n_samples: int = 500, seed: int = 42):
    """
    Genera un dataset sintetico de features de deteccion y unidades reales.

    Simula escenarios realistas donde:
    - Mas bounding boxes generalmente implica mas productos
    - Mayor ancho ocupado correlaciona con mas unidades
    - Multiples filas aumentan el conteo
    - Agrega ruido para que no sea trivial

    Args:
        n_samples: Numero de muestras a generar.
        seed: Semilla para reproducibilidad.

    Returns:
        Tupla (X, y, feature_names):
          X: shape (n_samples, 5)
          y: shape (n_samples,)
          feature_names: lista de nombres de features
    """
    np.random.seed(seed)

    feature_names = [
        "bbox_count", "total_width_px", "avg_height_px",
        "num_rows", "shelf_position"
    ]

    # --- Generar features ---
    bbox_count = np.random.randint(1, 15, size=n_samples).astype(float)
    total_width_px = bbox_count * np.random.uniform(40, 120, size=n_samples)
    avg_height_px = np.random.uniform(50, 200, size=n_samples)
    num_rows = np.random.randint(1, 5, size=n_samples).astype(float)
    shelf_position = np.random.uniform(0, 1, size=n_samples)

    X = np.column_stack([
        bbox_count, total_width_px, avg_height_px,
        num_rows, shelf_position
    ])

    # --- Generar target (unidades reales) ---
    # Relacion: unidades ~ bbox_count * num_rows + ruido
    # (cada bbox puede contener 1-3 productos, y hay filas)
    units_per_bbox = np.random.uniform(0.8, 2.5, size=n_samples)
    noise = np.random.normal(0, 1.5, size=n_samples)

    y = bbox_count * units_per_bbox * num_rows * 0.7 + noise
    y = np.clip(y, 1, None).round()  # Minimo 1 unidad

    return X, y, feature_names


def train_regressor():
    """Funcion principal de entrenamiento del regresor de stock."""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split

    # --- Cargar configuracion ---
    config_path = os.path.join(ROOT_DIR, "config", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    reg_config = config["regression"]

    print("Entrenamiento de Regresion de Stock")
    print("-" * 40)

    # --- 1. Generar datos sinteticos ---
    print("\n[1/4] Generando dataset sintetico...")
    X, y, feature_names = generate_synthetic_regression_data(n_samples=500)
    print(f"  Muestras: {X.shape[0]}, Features: {X.shape[1]}")
    print(f"  Features: {feature_names}")
    print(f"  Target range: [{y.min():.0f}, {y.max():.0f}]")

    # --- 2. Split train/test ---
    print("\n[2/4] Dividiendo datos (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=reg_config.get("random_state", 42)
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    # --- 3. Entrenar modelo ---
    print("\n[3/4] Entrenando RandomForestRegressor...")
    model = RandomForestRegressor(
        n_estimators=reg_config.get("n_estimators", 100),
        max_depth=reg_config.get("max_depth", 10),
        random_state=reg_config.get("random_state", 42),
    )
    model.fit(X_train, y_train)

    # --- 4. Evaluar ---
    print("\n[4/4] Evaluando modelo...")

    # Metricas en train
    y_train_pred = model.predict(X_train)
    train_mae = mean_absolute_error(y_train, y_train_pred)
    train_rmse = float(np.sqrt(mean_squared_error(y_train, y_train_pred)))
    train_r2 = r2_score(y_train, y_train_pred)

    # Metricas en test
    y_test_pred = model.predict(X_test)
    test_mae = mean_absolute_error(y_test, y_test_pred)
    test_rmse = float(np.sqrt(mean_squared_error(y_test, y_test_pred)))
    test_r2 = r2_score(y_test, y_test_pred)

    print(f"\n  {'Metrica':<20} {'Train':>10} {'Test':>10}")
    print(f"  {'-'*40}")
    print(f"  {'MAE':<20} {train_mae:>10.3f} {test_mae:>10.3f}")
    print(f"  {'RMSE':<20} {train_rmse:>10.3f} {test_rmse:>10.3f}")
    print(f"  {'R2 Score':<20} {train_r2:>10.3f} {test_r2:>10.3f}")

    # Feature importance
    importances = model.feature_importances_
    print(f"\n  Importancia de Features:")
    for name, imp in sorted(zip(feature_names, importances), key=lambda x: -x[1]):
        bar = "#" * int(imp * 50)
        print(f"    {name:<20} {imp:.3f} {bar}")

    # --- 5. Guardar modelo ---
    import joblib

    weights_path = os.path.join(ROOT_DIR, config["paths"]["regressor_weights"])
    os.makedirs(os.path.dirname(weights_path), exist_ok=True)
    joblib.dump(model, weights_path)

    print(f"\nModelo guardado: {weights_path}")
    print(f"MAE (test): {test_mae:.3f}")
    print(f"RMSE (test): {test_rmse:.3f}")
    print(f"R2 (test): {test_r2:.3f}")


if __name__ == "__main__":
    train_regressor()
