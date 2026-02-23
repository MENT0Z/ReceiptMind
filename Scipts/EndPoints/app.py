import os
import sys
import json
import cv2
import numpy as np
from flask import Flask, request, jsonify
import logging
from flask_cors import CORS

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    force=True)
logger = logging.getLogger(__name__)
# ============================================================
# PATH SETUP
# ============================================================
PADDLE_OCR_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR"
KIE_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts"
TEXT_TO_SQL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts\LLM_Inference\textToSql"

sys.path.insert(0, PADDLE_OCR_DIR)
sys.path.insert(0, KIE_DIR)
sys.path.insert(0, TEXT_TO_SQL_DIR)

# ============================================================
# IMPORTS
# ============================================================
import tools.infer.utility as utility
from tools.infer.predict_system import TextSystem
from KIE_Ollama import getParsedOutput   # 👈 IMPORTED CLEANLY
from storeInDb import storeInDB
from textToSqlAgent import AgentTextToSql

# ============================================================
# MODEL PATHS
# ============================================================
DET_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\infer_det_pre"
REC_MODEL_DIR = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\en_PP-OCRv4_rec_infer"

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
CORS(app)
# ============================================================
# OCR INITIALIZATION (CPU ONLY)
# ============================================================


def get_agent():
    print("🚀 Initializing Agent...")
    agent = AgentTextToSql()
    print("✅ Agent Ready")
    return agent

agent = get_agent() 

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

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        if not data or "message" not in data:
            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400

        user_query = data["message"]

        print(f"\n🔍 Processing: {user_query}")

        result = agent.process_request_with_execution(user_query)

        if result.get("success"):
            return jsonify({
                "success": True,
                "response": result.get("final_answer", ""),
                "sql_query": result.get("sql_query"),
                "attempts": result.get("attempts", 1)
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Unknown error")
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/dashboard-stats", methods=["GET"])
def dashboard_stats():
    try:
        from storeInDb import getDashboardStats

        # Read query param (?time_filter=last_30_days)
        time_filter = request.args.get("time_filter", "all_time")

        # Whitelist allowed values (important for safety)
        allowed_filters = {
            "all_time",
            "last_year",
            "last_30_days",
            "last_7_days"
        }

        if time_filter not in allowed_filters:
            time_filter = "all_time"

        result = getDashboardStats(time_filter=time_filter)

        return jsonify({
            "success": True,
            "time_filter": time_filter,
            "data": result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/receipts", methods=["GET"])
def all_receipts():
    try:
        from storeInDb import getAllReceipts
        return jsonify({"success": True, "data": getAllReceipts()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
