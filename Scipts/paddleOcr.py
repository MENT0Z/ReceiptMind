import os
import json
import time
from paddleocr import PaddleOCR

os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
# Initialize OCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

image_folder = "testImages"
output_file = "all_ocr_results.json"

all_results = {}

print(f"Starting batch extraction from: {image_folder}...")

image_extensions = (".jpg", ".jpeg", ".png", ".bmp")
files = [f for f in os.listdir(image_folder) if f.lower().endswith(image_extensions)]

for filename in files:
    img_path = os.path.join(image_folder, filename)
    print(f"Processing: {filename}")

    try:
        start_time = time.time()

        # NEW API
        result = ocr.predict(img_path)

        latency = time.time() - start_time

        image_data = []

        if result and len(result) > 0:
            res = result[0]

            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = res.get("rec_polys", [])

            for text, score, box in zip(texts, scores, boxes):
                image_data.append({
                    "box": box.tolist(),       # convert numpy → list
                    "text": text,
                    "score": round(float(score), 4)
                })

        all_results[filename] = {
            "metadata": {
                "latency_sec": round(latency, 3),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "content": image_data
        }

    except Exception as e:
        print(f"Failed to process {filename}: {e}")

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=4)

print("-" * 30)
print(f"DONE! Results for {len(all_results)} images saved to: {output_file}")
