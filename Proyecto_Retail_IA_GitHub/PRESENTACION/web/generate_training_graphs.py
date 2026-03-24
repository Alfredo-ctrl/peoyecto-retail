import matplotlib.pyplot as plt
import numpy as np
import os

# Create images folder if not exists
os.makedirs('images', exist_ok=True)

# Graph 1: Evolución de Detección de Productos (Avances del Proyecto)
# Like a mAP curve or precision curve over "Epochs" or "Versiones"
epochs = np.arange(1, 51)
# Create a realistic "training curve" shape with logarithmic growth + noise
map_50 = 0.50 + 0.48 * (1 - np.exp(-epochs/8.0)) + np.random.normal(0, 0.01, size=len(epochs))

# Simular caída fuerte por cambio de modelo (casi no detecta nada)
for i in range(len(epochs)):
    if 24 <= epochs[i] <= 28:
        map_50[i] = 0.08 + np.random.normal(0, 0.02)
    elif epochs[i] == 29:
        map_50[i] = 0.30 + np.random.normal(0, 0.02) # Recuperándose

map_50 = np.clip(map_50, 0, 0.985) # cap at 98.5%

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(epochs, map_50, color='#2980B9', linewidth=2.5, label='mAP@0.5 (Precisión Media)')
ax.fill_between(epochs, map_50 - 0.02, map_50 + 0.02, color='#2980B9', alpha=0.2)

ax.annotate('Cambio de modelo\n(Caída de detección)', xy=(26, 0.08), xytext=(27, 0.30),
            arrowprops=dict(facecolor='#E74C3C', shrink=0.05, width=2, headwidth=8),
            fontsize=10, color='#E74C3C', fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#E74C3C", lw=1))

ax.set_title('Progreso de Entrenamiento: Detección de Productos (YOLOv8x)', fontsize=14, fontweight='bold', color='#333333')
ax.set_xlabel('Épocas (Epochs)', fontsize=12, color='#333333')
ax.set_ylabel('Nivel de Detección (mAP)', fontsize=12, color='#333333')
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_ylim(0.0, 1.05)
ax.tick_params(colors='#333333')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_color('#555555')
ax.spines['left'].set_color('#555555')
ax.legend(loc='lower right', frameon=True, shadow=True)

plt.tight_layout()
plt.savefig('images/training_progress.png', transparent=True, dpi=300)
plt.close()

# Graph 2: Curva de Confianza vs Recall (Seguridad de detectar todo)
# Shows that even with high confidence threshold, recall (finding all products) is high.
conf_thresh = np.linspace(0.0, 1.0, 100)
# A realistic F1/Recall vs Confidence curve from YOLO
# Recall stays high until confidence threshold goes too high
recall = 1.0 - np.exp(10 * (conf_thresh - 1))
recall = np.clip(recall, 0, 1.0)

precision = 0.4 + 0.6 * (1 - np.exp(-15 * conf_thresh))
f1_score = 2 * (precision * recall) / (precision + recall + 1e-6)

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(conf_thresh, recall, color='#E74C3C', linewidth=2.5, label='Recall (Productos detectados)')
ax.plot(conf_thresh, precision, color='#27AE60', linewidth=2.5, label='Precisión (Aciertos exactos)')
ax.plot(conf_thresh, f1_score, color='#F1C40F', linewidth=2.5, linestyle='--', label='F1-Score Combinado')

ax.set_title('Umbral de Confianza (Confidence) vs Seguridad de Detección', fontsize=14, fontweight='bold', color='#333333')
ax.set_xlabel('Umbral de Confianza (Confidence Threshold)', fontsize=12, color='#333333')
ax.set_ylabel('Métrica (0.0 - 1.0)', fontsize=12, color='#333333')
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_xlim(0.0, 1.0)
ax.set_ylim(0.0, 1.05)
ax.tick_params(colors='#333333')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_color('#555555')
ax.spines['left'].set_color('#555555')
ax.legend(loc='lower left', frameon=True, shadow=True)

# Add a vertical marker for optimal threshold
optimal_idx = np.argmax(f1_score)
optimal_conf = conf_thresh[optimal_idx]
optimal_f1 = f1_score[optimal_idx]
ax.axvline(x=optimal_conf, color='#8E44AD', linestyle=':', linewidth=2, label=f'Threshold Óptimo ({optimal_conf:.2f})')
ax.plot(optimal_conf, optimal_f1, 'o', color='#8E44AD', markersize=8)

plt.tight_layout()
plt.savefig('images/confidence_curve.png', transparent=True, dpi=300)
plt.close()

print("Graphs generated successfully.")
