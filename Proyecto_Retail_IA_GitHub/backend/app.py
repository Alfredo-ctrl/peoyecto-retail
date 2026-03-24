"""
API Backend - FastAPI
Servidor principal con endpoints REST para inferencia de vision computacional.
"""

import os
import sys
import time
from typing import Optional

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


CONFIG_PATH = os.path.join(ROOT_DIR, "config", "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

ALLOWED_EXTENSIONS = set(config.get("api", {}).get("allowed_extensions", [
    "png", "jpg", "jpeg", "bmp", "webp"
]))


for folder_key in ["upload_folder", "results_folder"]:
    folder_path = os.path.join(ROOT_DIR, config["paths"].get(folder_key, "data/raw/uploads"))
    os.makedirs(folder_path, exist_ok=True)

os.makedirs(os.path.join(ROOT_DIR, "data", "weights"), exist_ok=True)


app = FastAPI(
    title="Retail Shelf CV - Inventario Automatico",
    description="API de vision computacional para inventario automatico en estantes de retail.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


frontend_dir = os.path.join(ROOT_DIR, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend_static")

inference_service = None


@app.on_event("startup")
async def startup_event():
    """Carga todos los modelos al iniciar el servidor."""
    global inference_service
    from backend.services.inference_service import InferenceService
    inference_service = InferenceService(CONFIG_PATH)
    print("\n[API] Servidor listo en http://0.0.0.0:5000")
    print("[API] Frontend en http://0.0.0.0:5000/static/index.html")


def _is_valid_extension(filename: str) -> bool:
    """Verifica si la extension del archivo es valida."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.get("/api/health")
async def health_check():
    """
    Endpoint de health check.

    Retorna el estado del servidor y si los modelos estan cargados.
    """
    return {
        "status": "ok",
        "models_loaded": inference_service is not None,
        "version": "1.0.0",
    }


@app.post("/api/infer")
async def infer(image: UploadFile = File(...)):
    """Pipeline completo de inferencia sobre una imagen de estante."""
    if inference_service is None:
        raise HTTPException(
            status_code=503,
            detail="Los modelos aun se estan cargando. Espere un momento.",
        )


    if not image.filename:
        raise HTTPException(status_code=400, detail="No se envio nombre de archivo.")

    if not _is_valid_extension(image.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )


    try:
        image_bytes = await image.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="El archivo esta vacio.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer imagen: {str(e)}")


    try:
        result = inference_service.run_pipeline(image_bytes)
        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el pipeline de inferencia: {str(e)}",
        )


@app.get("/")
async def root():
    """Redirige a la interfaz web."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


if __name__ == "__main__":
    import uvicorn

    host = config.get("api", {}).get("host", "0.0.0.0")
    port = config.get("api", {}).get("port", 5000)

    print(f"Retail Shelf CV | http://{host}:{port}")

    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        reload=True,
    )
