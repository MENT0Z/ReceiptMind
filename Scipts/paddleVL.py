# import os
# import json
# import time
# import paddlex as pdx

# # Disable model source check BEFORE pipeline creation
# os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

# # Create OCR pipeline
# pipeline = pdx.create_pipeline("OCR")

# image_folder = "testImages"
# output_file = "all_ocr_results_vl.json"

# image_extensions = (".jpg", ".jpeg", ".png", ".bmp")
# files = [f for f in os.listdir(image_folder) if f.lower().endswith(image_extensions)]

# all_results = {}

# print(f"Starting PaddleX OCR on {len(files)} images...")

# for filename in files:
#     img_path = os.path.join(image_folder, filename)
#     print(f"Processing: {filename}")

#     try:
#         start_time = time.time()

#         # IMPORTANT: predict() returns a generator
#         outputs = pipeline.predict(input=img_path)

#         latency = time.time() - start_time
#         image_data = []

#         for res in outputs:
#             data = res.json  # <-- THIS is the OCR result dict

#             texts = data.get("rec_texts", [])
#             scores = data.get("rec_scores", [])
#             boxes = data.get("rec_polys", [])

#             for t, s, b in zip(texts, scores, boxes):
#                 image_data.append({
#                     "box": b,                 # already converted to list by PaddleX
#                     "text": t,
#                     "score": round(float(s), 4)
#                 })

#         all_results[filename] = {
#             "metadata": {
#                 "latency_sec": round(latency, 3),
#                 "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
#                 "engine": "PaddleX OCR"
#             },
#             "content": image_data
#         }

#     except Exception as e:
#         print(f"Failed to process {filename}: {e}")

# with open(output_file, "w", encoding="utf-8") as f:
#     json.dump(all_results, f, ensure_ascii=False, indent=4)

# print("-" * 40)
# print(f"DONE! Results saved to: {output_file}")


import os
import time
import paddlex as pdx

os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

pipeline = pdx.create_pipeline("OCR")

image_dir = "testImages"
out_dir = "paddlex_output"
os.makedirs(out_dir, exist_ok=True)

image_exts = (".jpg", ".png", ".jpeg")

start_total = time.time()

for img in os.listdir(image_dir):
    if not img.lower().endswith(image_exts):
        continue

    img_path = os.path.join(image_dir, img)
    print(f"OCR: {img}")

    start = time.time()

    for res in pipeline.predict(img_path):
        # PaddleX knows best — let it dump everything
        res.save_to_json(out_dir)

    print(f"Time: {round(time.time() - start, 2)} sec")

print("TOTAL TIME:", round(time.time() - start_total, 2), "sec")
