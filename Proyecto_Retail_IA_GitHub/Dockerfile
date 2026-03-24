# -----------------------------------------------
# Dockerfile - Retail Shelf CV
# Samsung Innovation Campus
# -----------------------------------------------

FROM python:3.11-slim

# Dependencias del sistema para OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Crear directorios necesarios
RUN mkdir -p data/weights data/raw/uploads data/processed/results

# Exponer puerto
EXPOSE 5000

# Comando de inicio
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "5000"]
