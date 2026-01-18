import re
import os
import json
import difflib

GT_DIR = "Gt/boxes"
PADDLEX_OUT_DIR = "paddlex_output"
MISMATCH_FILE = "paddlex_vl_mismatches.json"




def load_gt_boxes(path):
    gt = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            coords = list(map(int, parts[:8]))
            text = ",".join(parts[8:])

            box = [
                [coords[0], coords[1]],
                [coords[2], coords[3]],
                [coords[4], coords[5]],
                [coords[6], coords[7]],
            ]

            gt.append({"box": box, "text": text})
    return gt


def load_paddlex_vl_boxes(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    preds = []
    polys = data.get("rec_polys", [])
    texts = data.get("rec_texts", [])

    for poly, text in zip(polys, texts):
        preds.append({
            "box": poly,
            "text": text
        })

    return preds


def get_gt_path(image_name):
    return os.path.join(GT_DIR, image_name.replace(".jpg", ".txt"))


def poly_to_bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def iou(box1, box2):
    x1_min, y1_min, x1_max, y1_max = poly_to_bbox(box1)
    x2_min, y2_min, x2_max, y2_max = poly_to_bbox(box2)

    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)

    if inter_xmax <= inter_xmin or inter_ymax <= inter_ymin:
        return 0.0

    inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)

    return inter_area / (area1 + area2 - inter_area)


def detection_metrics(gt_boxes, pred_boxes, iou_thresh=0.5):
    matched_gt = set()
    matched_pred = set()

    for i, gt in enumerate(gt_boxes):
        for j, pred in enumerate(pred_boxes):
            if iou(gt["box"], pred["box"]) >= iou_thresh:
                matched_gt.add(i)
                matched_pred.add(j)
                break

    TP = len(matched_gt)
    FP = len(pred_boxes) - len(matched_pred)
    FN = len(gt_boxes) - len(matched_gt)

    precision = TP / (TP + FP + 1e-6)
    recall = TP / (TP + FN + 1e-6)
    f1 = 2 * precision * recall / (precision + recall + 1e-6)

    return precision, recall, f1


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9./ ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def cer(gt, pred):
    gt = normalize(gt)
    pred = normalize(pred)

    sm = difflib.SequenceMatcher(None, gt, pred)
    edits = sum(
        (i2 - i1) if tag != "equal" else 0
        for tag, i1, i2, _, _ in sm.get_opcodes()
    )
    return edits / max(len(gt), 1)


def recognition_accuracy(gt_boxes, pred_boxes, image_name, mismatches, iou_thresh=0.5):
    total_cer = 0.0
    count = 0

    for gt in gt_boxes:
        best_iou = 0.0
        best_pred = None

        for pred in pred_boxes:
            score = iou(gt["box"], pred["box"])
            if score > best_iou:
                best_iou = score
                best_pred = pred

        if best_iou >= iou_thresh:
            c = cer(gt["text"], best_pred["text"])
            total_cer += c
            count += 1

            if c > 0:
                mismatches.append({
                    "image": image_name,
                    "gt": gt["text"],
                    "pred": best_pred["text"],
                    "cer": round(c, 4)
                })

    avg_cer = total_cer / max(count, 1)
    return 1 - avg_cer, avg_cer



if __name__ == "__main__":

    det_p, det_r, det_f = [], [], []
    rec_accs, rec_cers = [], []
    mismatches = []

    for file in os.listdir(PADDLEX_OUT_DIR):
        if not file.endswith("_res.json"):
            continue

        image_name = file.replace("_res.json", ".jpg")
        gt_path = get_gt_path(image_name)

        if not os.path.exists(gt_path):
            continue

        gt_boxes = load_gt_boxes(gt_path)
        pred_boxes = load_paddlex_vl_boxes(os.path.join(PADDLEX_OUT_DIR, file))

        p, r, f1 = detection_metrics(gt_boxes, pred_boxes)
        acc, avg_cer = recognition_accuracy(gt_boxes, pred_boxes, image_name, mismatches)

        det_p.append(p)
        det_r.append(r)
        det_f.append(f1)

        rec_accs.append(acc)
        rec_cers.append(avg_cer)

    print("\n===== PADDLEX-VL OVERALL AVERAGES =====")
    print("Detection Precision:", sum(det_p) / len(det_p))
    print("Detection Recall   :", sum(det_r) / len(det_r))
    print("Detection F1       :", sum(det_f) / len(det_f))
    print("Recognition Acc    :", sum(rec_accs) / len(rec_accs))
    print("Recognition CER    :", sum(rec_cers) / len(rec_cers))

    with open(MISMATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(mismatches, f, indent=2, ensure_ascii=False)
