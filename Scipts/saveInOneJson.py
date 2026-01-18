import os
import json

json_dir = "paddlex_output"
final_output = "combined_ocr_results.json"

combined = {}

for file in os.listdir(json_dir):
    if file.endswith(".json"):
        with open(os.path.join(json_dir, file), "r", encoding="utf-8") as f:
            data = json.load(f)

        # PaddleX already includes image name internally
        combined[file.replace(".json", "")] = data

with open(final_output, "w", encoding="utf-8") as f:
    json.dump(combined, f, ensure_ascii=False, indent=4)

print("Merged JSON saved to:", final_output)
