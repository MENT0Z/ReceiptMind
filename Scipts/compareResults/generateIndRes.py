import matplotlib.pyplot as plt
import numpy as np

# ---------------- Detection Metrics ----------------
det_metrics = ["Precision", "Recall", "F1"]

fine_det = [0.9532, 0.9094, 0.9307]
base_det = [0.9786, 0.8574, 0.9140]

# ---------------- Recognition Metrics ----------------
rec_metrics = ["Exact Accuracy", "Char Accuracy", "Avg Edit Distance"]

fine_rec = [0.6005, 0.9277, 0.8436]
base_rec = [0.5773, 0.9199, 0.9489]

# ---------------- End-to-End Metrics ----------------
e2e_metrics = ["Precision", "Recall", "F1"]

fine_e2e = [0.5724, 0.5461, 0.5589]
base_e2e = [0.5650, 0.4950, 0.5277]


def plot_graph(metrics, fine, base, title):
    x = np.arange(len(metrics))
    width = 0.35

    plt.figure(figsize=(7,5))
    plt.bar(x - width/2, fine, width, label="Fine-Tuned Model")
    plt.bar(x + width/2, base, width, label="Base Model")

    plt.xticks(x, metrics)
    plt.ylabel("Score")
    plt.title(title)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.6)

    plt.tight_layout()
    plt.show()


# Generate graphs
plot_graph(det_metrics, fine_det, base_det,
           "Detection Performance Comparison")

plot_graph(rec_metrics, fine_rec, base_rec,
           "Recognition Performance Comparison")

plot_graph(e2e_metrics, fine_e2e, base_e2e,
           "End-to-End OCR Performance Comparison")