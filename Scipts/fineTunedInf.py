import os
import json
import time
import subprocess
import sys

# ---------------- CONFIG ----------------
IMAGE_FOLDER = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\testImages"
OUTPUT_FILE = "finetuned_results_new_ft.json"

PADDLE_CMD_TEMPLATE = [
    r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\paddleOcr_old_version\Scripts\python.exe",
    "tools/infer/predict_system.py",
    "--det_algorithm=DB++",
    "--det_model_dir=C:\\Users\\Madan Raj Upadhyay\\Downloads\\Paddle\\infer_db++",
    "--rec_model_dir=C:\\Users\\Madan Raj Upadhyay\\Downloads\\Paddle\\en_PP-OCRv4_rec_infer",
    "--rec_char_dict_path=ppocr/utils/en_dict.txt",
    "--use_gpu=True"
]
# ----------------------------------------

image_extensions = (".jpg", ".jpeg", ".png", ".bmp")
files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(image_extensions)]

all_results = {}

print(f"Starting fine-tuned OCR batch on {len(files)} images...")
print(f"Using interpreter: {sys.executable}")

for filename in files:
    img_path = os.path.join(IMAGE_FOLDER, filename)
    print(f"Processing: {filename}")

    try:
        start_time = time.time()

        cmd = PADDLE_CMD_TEMPLATE + [f"--image_dir={img_path}"]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )

        latency = time.time() - start_time

        all_results[filename] = {
            "metadata": {
                "latency_sec": round(latency, 3),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "return_code": result.returncode
            },
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except Exception as e:
        all_results[filename] = {
            "error": str(e)
        }

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=4)

print("-" * 40)
print(f"DONE! Results saved to: {OUTPUT_FILE}")
