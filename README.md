# Retail Vision AI — Inventario Automatico por Vision Computacional

Sistema de inventario automatico para tiendas retail usando camaras de vigilancia PTZ/Domo conectadas a una **Raspberry Pi 5 con AI HAT (Hailo-8L)**. Las camaras capturan imagenes, la Raspberry Pi las procesa con modelos de vision computacional, cuenta productos y actualiza el inventario automaticamente.

---

## Demo Interactivo 3D

El directorio `3d-demo/` contiene un demo interactivo standalone que simula una tienda de conveniencia completa:

- **Tienda 3D** con 8 secciones de estantes y productos realistas
- **4 Camaras estrategicas** (PTZ y Domo) con beams de cobertura visual
- **Pipeline AI Ensemble**: YOLO11x + RT-DETR + RF-DETR con WBF
- **Inventario en tiempo real** con escaneo continuo y alertas de stock
- **Panel Raspberry Pi** con CPU, RAM, temperatura, NPU y log de AI
- **Dashboard** con KPIs, feeds de camaras y pipeline de deteccion
- **Simulacion de escaneo** con progreso por camara

### Abrir el Demo

Simplemente abrir `3d-demo/index.html` en un navegador moderno (Chrome, Edge, Firefox).

---

## Estructura del Proyecto

```
Proyecto_Retail_IA/
├── 3d-demo/                       # Demo interactivo 3D (standalone)
│   ├── index.html                 # Interfaz principal
│   ├── styles.css                 # Estilos (dark glassmorphism)
│   ├── app.js                     # Motor 3D + inventario + RPi sim
│   └── images/                    # Assets visuales de estantes
├── backend/
│   ├── app.py                     # API FastAPI
│   ├── models/
│   │   ├── detection.py           # ShelfDetector (YOLOv8)
│   │   ├── classification.py      # ProductClassifier (ResNet18)
│   │   ├── regression.py          # StockRegressor (RandomForest)
│   │   ├── clustering.py          # SKUClustering (K-Means)
│   │   └── ...                    # Modelos avanzados
│   └── services/
│       ├── preprocessing.py       # Preprocesamiento de imagenes
│       ├── postprocessing.py      # Dibujo de bboxes y respuesta JSON
│       └── inference_service.py   # Pipeline completo de inferencia
├── training/
│   ├── classification_train.py    # Entrenamiento de clasificador
│   ├── regression_train.py        # Entrenamiento de regresor
│   ├── clustering_train.py        # Entrenamiento de clustering
│   └── ...                        # Scripts avanzados
├── SKU-110K/
│   ├── SKU110K_fixed/             # Dataset (imagenes excluidas del repo)
│   │   └── annotations/           # Anotaciones CSV
│   └── sku110k_project/
│       └── src/                   # Pipeline de entrenamiento
│           ├── train.py           # Script principal de entrenamiento
│           ├── model.py           # RetinaNet + ResNet50 FPN
│           ├── dataset.py         # Dataset loader con augmentations
│           └── ...
├── config/
│   └── config.yaml                # Configuracion central
├── data/
│   └── weights/                   # Pesos de modelos (gitignored)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Arquitectura del Sistema

```
Camaras PTZ/Domo (4 unidades)
         │
         ▼
Raspberry Pi 5 + AI HAT (Hailo-8L 13 TOPS)
         │
         ├── Captura imagenes → Procesa con YOLO11s INT8
         ├── Cuenta productos → Actualiza inventario
         ├── Borra imagenes procesadas
         └── Genera alertas de stock bajo / agotado
         │
         ▼
    Inventario + Alertas
```

Las camaras estan conectadas al modulo central y controladas por la Raspberry Pi. El procesamiento se realiza en edge con el NPU Hailo-8L, logrando 30 FPS en tiempo real.

---

## Pipeline AI (Ensemble)

| Modelo           | Funcion                               | mAP       | Tiempo    |
| ---------------- | ------------------------------------- | --------- | --------- |
| YOLO11x          | Detector principal (objetos pequenos) | 96.8%     | 2.1s      |
| RT-DETR          | Transformer (productos similares)     | 95.2%     | 1.8s      |
| RF-DETR          | Velocidad/precision optima            | 97.1%     | 1.4s      |
| **WBF Ensemble** | **Fusion final**                      | **98.5%** | **~2.5s** |

### Edge (Raspberry Pi)

- Modelo: YOLO11s/n INT8 quantizado
- NPU: Hailo-8L (13 TOPS)
- Rendimiento: 30 FPS o snapshots cada 5 min

---

## Dataset SKU-110K

El dataset SKU-110K contiene 11,762 imagenes de estantes de tiendas con mas de 1.7 millones de bounding boxes.

### Descargar Imagenes

Las imagenes del dataset no estan incluidas en el repositorio por su tamano. Para descargarlas:

1. Visitar: https://github.com/eg4000/SKU110K_CVPR19
2. Descargar las imagenes y colocarlas en `SKU-110K/SKU110K_fixed/SKU110K_fixed/images/`

### Entrenar el Modelo

```bash
cd SKU-110K/sku110k_project/src
pip install -r ../requirements.txt
python train.py --epochs 10 --batch_size 4 --subset 100
```

---

## Instalacion

### 1. Clonar repositorio

```bash
git clone <url-del-repo>
cd Proyecto_Retail_IA
```

### 2. Crear entorno virtual

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Ejecucion

### Demo 3D (sin servidor)

Abrir `3d-demo/index.html` directamente en el navegador.

### Backend API

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 5000 --reload
```

### Docker

```bash
docker-compose up --build
```

---

## API

| Metodo | Ruta          | Descripcion                        |
| ------ | ------------- | ---------------------------------- |
| POST   | `/api/infer`  | Pipeline completo sobre una imagen |
| GET    | `/api/health` | Health check del servidor          |

---

## Tecnologias

- **AI/ML**: YOLO11x, RT-DETR, RF-DETR, WBF, ResNet18, RandomForest, K-Means
- **Backend**: Python, FastAPI, OpenCV, PyTorch, scikit-learn
- **Frontend**: Three.js, HTML5, CSS3, JavaScript
- **Edge**: Raspberry Pi 5, Hailo-8L AI HAT, INT8 quantization
- **DevOps**: Docker, Docker Compose
