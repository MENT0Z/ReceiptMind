import os
import json
import pandas as pd
from shapely.geometry import Polygon
import Levenshtein

# ==============================
# CONFIG
# ==============================

BASE_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\get results comparison normal vs ft"

GT_FILE = os.path.join(BASE_PATH, "Label.txt")
MODEL1_FILE = os.path.join(BASE_PATH, "normal.txt")
MODEL2_FILE = os.path.join(BASE_PATH, "ft.txt")

IOU_THRESHOLD = 0.5


# ==============================
# DISPLAY SETTINGS (IMPORTANT)
# ==============================

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 2000)
pd.set_option('display.expand_frame_repr', False)


# ==============================
# UTIL FUNCTIONS
# ==============================

def normalize_text(text):
    return text.lower().strip()


def polygon_from_points(points):
    return Polygon(points)


def compute_iou(poly1, poly2):
    if not poly1.is_valid or not poly2.is_valid:
        return 0.0
    inter = poly1.intersection(poly2).area
    union = poly1.union(poly2).area
    if union == 0:
        return 0.0
    return inter / union


def load_file(filepath, is_gt=False):
    data = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue

            img_name = parts[0]
            if is_gt:
                img_name = img_name.replace("img/", "")

            annotations = json.loads(parts[1])
            data[img_name] = annotations

    return data


# ==============================
# EVALUATION
# ==============================

def evaluate_model(gt_data, pred_data):

    det_TP = 0
    det_FP = 0
    det_FN = 0

    rec_correct = 0
    total_matched = 0
    total_edit_distance = 0
    total_chars = 0

    e2e_correct = 0

    for img_name in gt_data:

        gt_boxes = gt_data.get(img_name, [])
        pred_boxes = pred_data.get(img_name, [])

        gt_polys = [polygon_from_points(obj["points"]) for obj in gt_boxes]
        gt_texts = [normalize_text(obj["transcription"]) for obj in gt_boxes]

        matched_gt = set()

        for pred in pred_boxes:

            pred_poly = polygon_from_points(pred["points"])
            pred_text = normalize_text(pred["transcription"])

            best_iou = 0
            best_gt_idx = -1

            for i, gt_poly in enumerate(gt_polys):
                if i in matched_gt:
                    continue

                iou = compute_iou(pred_poly, gt_poly)
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = i

            if best_iou >= IOU_THRESHOLD:
                det_TP += 1
                matched_gt.add(best_gt_idx)

                gt_text = gt_texts[best_gt_idx]
                total_matched += 1

                # Recognition exact match
                if pred_text == gt_text:
                    rec_correct += 1
                    e2e_correct += 1

                # Character accuracy
                edit_dist = Levenshtein.distance(pred_text, gt_text)
                total_edit_distance += edit_dist
                total_chars += max(len(gt_text), 1)

            else:
                det_FP += 1

        det_FN += len(gt_boxes) - len(matched_gt)

    # ==============================
    # METRICS
    # ==============================

    det_precision = det_TP / (det_TP + det_FP + 1e-8)
    det_recall = det_TP / (det_TP + det_FN + 1e-8)
    det_f1 = 2 * det_precision * det_recall / (det_precision + det_recall + 1e-8)

    rec_accuracy = rec_correct / (total_matched + 1e-8)
    char_accuracy = 1 - (total_edit_distance / (total_chars + 1e-8))
    avg_edit_distance = total_edit_distance / (total_matched + 1e-8)

    e2e_precision = e2e_correct / (det_TP + det_FP + 1e-8)
    e2e_recall = e2e_correct / (det_TP + det_FN + 1e-8)
    e2e_f1 = 2 * e2e_precision * e2e_recall / (e2e_precision + e2e_recall + 1e-8)

    return {
        "Det Precision": det_precision,
        "Det Recall": det_recall,
        "Det F1": det_f1,
        "Rec Exact Accuracy": rec_accuracy,
        "Char Accuracy": char_accuracy,
        "Avg Edit Distance": avg_edit_distance,
        "E2E Precision": e2e_precision,
        "E2E Recall": e2e_recall,
        "E2E F1": e2e_f1
    }


# ==============================
# MAIN
# ==============================

def main():

    print("Loading files...")
    gt_data = load_file(GT_FILE, is_gt=True)
    model1_data = load_file(MODEL1_FILE)
    model2_data = load_file(MODEL2_FILE)

    print("Evaluating Model 1 (normal)...")
    results_model1 = evaluate_model(gt_data, model1_data)

    print("Evaluating Model 2 (ft)...")
    results_model2 = evaluate_model(gt_data, model2_data)

    df = pd.DataFrame([results_model1, results_model2],
                      index=["Model1_FineTuned", "Model2_BaseModel"])

    print("\n================ FULL COMPARISON TABLE ================\n")
    print(df.round(4))

    # Save CSV
    output_csv = os.path.join(BASE_PATH, "model_comparison_results.csv")
    df.to_csv(output_csv)

    print(f"\nResults saved to: {output_csv}")


if __name__ == "__main__":
    main()
