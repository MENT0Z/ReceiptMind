import os
import sys
import json
import cv2
import numpy as np
from flask import Flask, request, jsonify

# ============================================================
# CONFIG
# ============================================================
PADDLE_OCR_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR"
sys.path.insert(0, PADDLE_OCR_DIR)

DET_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\infer_det_pre"
REC_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\en_PP-OCRv4_rec_infer"

DATA_PATH = os.path.join(
    PADDLE_OCR_DIR,
    "inference_results",
    "system_results.txt"
)

os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)

# ============================================================
# IMPORTS (after sys.path fix)
# ============================================================
import tools.infer.utility as utility
from tools.infer.predict_system import TextSystem
from ppocr.utils.utility import get_image_file_list

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__)

# ============================================================
# OCR INITIALIZATION (GPU ONCE)
# ============================================================
def init_ocr():
    args = utility.parse_args()

    args.det_algorithm = "DB++"
    args.det_model_dir = DET_MODEL_DIR
    args.rec_model_dir = REC_MODEL_DIR
    args.rec_char_dict_path = os.path.join(PADDLE_OCR_DIR, "ppocr/utils/en_dict.txt")

    args.use_gpu = True
    args.use_angle_cls = False
    args.use_mp = False
    args.ir_optim = True

    args.show_log = False
    args.drop_score = 0.5
    args.det_box_type = "quad"

    return TextSystem(args)

print("Initializing PaddleOCR (GPU warm-up)...")
text_sys = init_ocr()
print("PaddleOCR ready ✅")

# ============================================================
# OCR CORE FUNCTION
# ============================================================
def run_ocr(img):
    """
    Returns PaddleOCR-style result list:
    [{"transcription": text, "points": [[x,y]...]}]
    """
    if img is None:
        return []

    dt_boxes, rec_res, _ = text_sys(img)

    results = []
    for box, rec in zip(dt_boxes, rec_res):
        text, score = rec
        results.append({
            "transcription": text,
            "points": np.array(box).astype(int).tolist()
        })

    return results

# ============================================================
# SAVE RESULTS TO FILE (APPEND MODE)
# ============================================================
def save_results(image_name, results):
    line = f"{image_name}\t{json.dumps(results, ensure_ascii=False)}\n"
    with open(DATA_PATH, "a", encoding="utf-8") as f:
        f.write(line)

# ============================================================
# API: SINGLE IMAGE
# ============================================================
@app.route("/predict", methods=["POST"])
def predict_image():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    img_array = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    results = run_ocr(img)
    save_results(file.filename, results)

    return jsonify({
        "image": file.filename,
        "num_texts": len(results),
        "results": results
    })

# ============================================================
# API: PROCESS LOCAL FOLDER
# ============================================================
@app.route("/predict_folder", methods=["POST"])
def predict_folder():
    data = request.get_json()
    folder_path = data.get("folder_path")

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"error": "Invalid folder path"}), 400

    image_files = get_image_file_list(folder_path)
    if not image_files:
        return jsonify({"error": "No images found"}), 400

    folder_results = {}

    for img_path in image_files:
        img = cv2.imread(img_path)
        if img is None:
            continue

        image_name = os.path.basename(img_path)
        results = run_ocr(img)

        save_results(image_name, results)
        folder_results[image_name] = results

    return jsonify({
        "folder": folder_path,
        "num_images": len(folder_results),
        "results": folder_results
    })

# ============================================================
# RUN SERVER
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
