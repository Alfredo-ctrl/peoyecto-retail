"""
Deteccion de productos en estantes.
Backend Flask + YOLOv8x
"""

import os
import uuid
import time
from collections import Counter

from flask import Flask, render_template, request, jsonify, url_for
from ultralytics import YOLO
import cv2
import numpy as np

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
RESULT_FOLDER = os.path.join(os.path.dirname(__file__), "static", "resultados")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# YOLOv8x - modelo mas grande y preciso disponible
model = YOLO("yolov8x.pt")

COCO_ES = {
    "person": "Persona", "bicycle": "Bicicleta", "car": "Auto",
    "motorcycle": "Motocicleta", "airplane": "Avion", "bus": "Autobus",
    "train": "Tren", "truck": "Camion", "boat": "Bote",
    "traffic light": "Semaforo", "fire hydrant": "Hidrante",
    "stop sign": "Senal de alto", "parking meter": "Parquimetro",
    "bench": "Banca", "bird": "Ave", "cat": "Gato", "dog": "Perro",
    "horse": "Caballo", "sheep": "Oveja", "cow": "Vaca",
    "elephant": "Elefante", "bear": "Oso", "zebra": "Cebra",
    "giraffe": "Jirafa", "backpack": "Mochila", "umbrella": "Paraguas",
    "handbag": "Bolso", "tie": "Corbata", "suitcase": "Maleta",
    "frisbee": "Frisbee", "skis": "Esquis", "snowboard": "Snowboard",
    "sports ball": "Balon", "kite": "Cometa", "baseball bat": "Bate",
    "baseball glove": "Guante", "skateboard": "Patineta",
    "surfboard": "Tabla de surf", "tennis racket": "Raqueta",
    "bottle": "Botella", "wine glass": "Copa de vino", "cup": "Taza",
    "fork": "Tenedor", "knife": "Cuchillo", "spoon": "Cuchara",
    "bowl": "Tazon", "banana": "Platano", "apple": "Manzana",
    "sandwich": "Sandwich", "orange": "Naranja", "broccoli": "Brocoli",
    "carrot": "Zanahoria", "hot dog": "Hot Dog", "pizza": "Pizza",
    "donut": "Dona", "cake": "Pastel", "chair": "Silla", "couch": "Sofa",
    "potted plant": "Planta", "bed": "Cama", "dining table": "Mesa",
    "toilet": "Inodoro", "tv": "Televisor", "laptop": "Laptop",
    "mouse": "Mouse", "remote": "Control remoto", "keyboard": "Teclado",
    "cell phone": "Celular", "microwave": "Microondas", "oven": "Horno",
    "toaster": "Tostador", "sink": "Lavabo", "refrigerator": "Refrigerador",
    "book": "Libro", "clock": "Reloj", "vase": "Florero",
    "scissors": "Tijeras", "teddy bear": "Oso de peluche",
    "hair drier": "Secador", "toothbrush": "Cepillo de dientes",
}

COLORES = {}


def obtener_color(clase):
    if clase not in COLORES:
        h = hash(clase) % 180
        hsv = np.uint8([[[h, 200, 220]]])
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        COLORES[clase] = (int(bgr[0][0][0]), int(bgr[0][0][1]), int(bgr[0][0][2]))
    return COLORES[clase]


def traducir(nombre_en):
    return COCO_ES.get(nombre_en, nombre_en.capitalize())


def extension_valida(nombre):
    return "." in nombre and nombre.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def detectar_productos(ruta_imagen):
    inicio = time.time()

    results = model.predict(source=ruta_imagen, conf=0.25, verbose=False)
    img = cv2.imread(ruta_imagen)
    if img is None:
        return None, None, 0, 0

    conteo = Counter()

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            confianza = float(box.conf[0])
            clase_id = int(box.cls[0])
            clase_nombre = model.names[clase_id]
            conteo[clase_nombre] += 1

            color = obtener_color(clase_nombre)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            etiqueta = f"{traducir(clase_nombre)} {confianza:.0%}"
            tam = cv2.getTextSize(etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(img, (x1, y1 - tam[1] - 8), (x1 + tam[0] + 4, y1), color, -1)
            cv2.putText(img, etiqueta, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    nombre_resultado = f"resultado_{uuid.uuid4().hex[:8]}.jpg"
    cv2.imwrite(os.path.join(RESULT_FOLDER, nombre_resultado), img)

    resumen = [{"nombre": traducir(c), "cantidad": n} for c, n in conteo.most_common()]
    total = sum(conteo.values())
    tiempo = round(time.time() - inicio, 2)

    return nombre_resultado, resumen, total, tiempo


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/detectar", methods=["POST"])
def detectar():
    if "imagen" not in request.files:
        return jsonify({"error": "No se envio ninguna imagen."}), 400

    archivo = request.files["imagen"]
    if archivo.filename == "" or not extension_valida(archivo.filename):
        return jsonify({"error": "Archivo no valido. Use JPG, PNG, BMP o WEBP."}), 400

    ext = archivo.filename.rsplit(".", 1)[1].lower()
    nombre = f"upload_{uuid.uuid4().hex[:8]}.{ext}"
    ruta = os.path.join(UPLOAD_FOLDER, nombre)
    archivo.save(ruta)

    nombre_resultado, productos, total, tiempo = detectar_productos(ruta)

    try:
        os.remove(ruta)
    except OSError:
        pass

    if nombre_resultado is None:
        return jsonify({"error": "No se pudo procesar la imagen."}), 500

    return jsonify({
        "imagen_resultado": url_for("static", filename=f"resultados/{nombre_resultado}"),
        "productos": productos,
        "total": total,
        "tiempo": tiempo,
    })


if __name__ == "__main__":
    print("Retail Shelf CV | http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
