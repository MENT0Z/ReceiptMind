import matplotlib.pyplot as plt
import numpy as np

# Metrics
metrics = [
    "Det Precision", "Det Recall", "Det F1",
    "Rec Exact Acc", "Char Acc", "Avg Edit Dist",
    "E2E Precision", "E2E Recall", "E2E F1"
]

# Values
fine_tuned = [0.9532, 0.9094, 0.9307, 0.6005, 0.9277, 0.8436, 0.5724, 0.5461, 0.5589]
base_model = [0.9786, 0.8574, 0.9140, 0.5773, 0.9199, 0.9489, 0.5650, 0.4950, 0.5277]

# X locations
x = np.arange(len(metrics))
width = 0.35

# Plot
plt.figure(figsize=(14, 6))
plt.bar(x - width/2, fine_tuned, width, label="Fine-Tuned Model")
plt.bar(x + width/2, base_model, width, label="Base Model")

# Labels and styling
plt.xticks(x, metrics, rotation=45, ha='right')
plt.ylabel("Score")
plt.title("OCR Performance Comparison: Fine-Tuned vs Base Model")
plt.legend()
plt.grid(axis='y', linestyle='--', alpha=0.6)

plt.tight_layout()
plt.show()