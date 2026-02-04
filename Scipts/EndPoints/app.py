import os
import sys
import json
import cv2
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS


# ============================================================
# PATH SETUP
# ============================================================
PADDLE_OCR_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR"
KIE_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts"

sys.path.insert(0, PADDLE_OCR_DIR)
sys.path.insert(0, KIE_DIR)

# ============================================================
# IMPORTS
# ============================================================
import tools.infer.utility as utility
from tools.infer.predict_system import TextSystem
from KIE_Ollama import getParsedOutput   # 👈 IMPORTED CLEANLY
from storeInDb import storeInDB

# ============================================================
# MODEL PATHS
# ============================================================
DET_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\infer_det_pre"
REC_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\en_PP-OCRv4_rec_infer"

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__)
CORS(app)
# ============================================================
# OCR INITIALIZATION (CPU ONLY)
# ============================================================
def init_ocr():
    args = utility.parse_args()

    args.det_algorithm = "DB++"
    args.det_model_dir = DET_MODEL_DIR
    args.rec_model_dir = REC_MODEL_DIR
    args.rec_char_dict_path = os.path.join(
        PADDLE_OCR_DIR, "ppocr/utils/en_dict.txt"
    )

    args.use_gpu = False          # 🔥 CPU ONLY
    args.use_angle_cls = False
    args.use_mp = False
    args.ir_optim = False
    args.show_log = False
    args.drop_score = 0.5
    args.det_box_type = "quad"

    return TextSystem(args)

# 🔥 LOAD OCR ONCE
text_sys = init_ocr()

# ============================================================
# OCR CORE
# ============================================================
def run_ocr(image_name, img):
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
    return f"{image_name}\t{json.dumps(results, ensure_ascii=False)}\n"

# ============================================================
# API ENDPOINT
# ============================================================
@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]

    img_array = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    raw_ocr = run_ocr(file.filename, img)
    print(raw_ocr)
    parsed_output = getParsedOutput(raw_ocr)
    print("\n[PARSED OUTPUT]\n", parsed_output, "\n")
    return jsonify({
        "image": file.filename,
        "parsed_output": parsed_output
    })

@app.route("/store-receipt", methods=["POST"])
def store_receipt():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({
                "status": "failed",
                "error": "Empty JSON body"
            }), 400

        result = storeInDB(data)

        return jsonify(result), 200

    except Exception as e:
        print("❌ API error:", e)
        return jsonify({
            "status": "failed",
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
