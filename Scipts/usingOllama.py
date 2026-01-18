import json
import requests

def extract_transcriptions_only(file_path):
    """
    Returns:
        List[str]  → OCR text lines only (reading order)
    """
    texts = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            _, json_data = line.strip().split("\t", 1)
            ocr_lines = json.loads(json_data)

            # keep reading order (top → bottom)
            ocr_lines.sort(key=lambda x: min(p[1] for p in x["points"]))

            for l in ocr_lines:
                txt = l["transcription"].strip()
                if txt:
                    texts.append(txt)

    return texts

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:1b"
DATA_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR\inference_results\system_results.txt"

def build_prompt(receipt_text: str) -> str:
    return f"""
    You are an information extraction engine.
    Return ONLY valid JSON. No explanations.

    Schema:
    {{
    "vendor_name": string | null,
    "vendor_address": string | null,
    "vendor_phone": string | null,
    "vendor_gst": string | null,

    "receipt_id": string | null,
    "date": string | null,
    "time": string | null,
    "currency": string,

    "items": [
        {{
        "name": string,
        "quantity": number,
        "price": number
        }}
    ],

    "subtotal_amount": number | null,
    "tax_amount": number | null,
    "discount_amount": number | null,
    "total_amount": number | null,

    "payment_method": string | null,
    "card_last4": string | null,
    "transaction_id": string | null,

    "confidence_score": number | null,
    "source": string
    }}

    Rules:
    - Do not invent data
    - Use null if missing
    - Numbers must be numbers
    - Join address lines
    - Items empty if unclear
    - currency = "INR" if not mentioned
    - source = "mobile_capture"

    Receipt text:
    {receipt_text}
    """.strip()

def call_ollama(prompt: str) -> dict:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_gpu": 1
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw_output = response.json()["response"].strip()

    # STRICT JSON parse
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON:\n{raw_output}") from e

def pretty_print_receipt(data: dict):
    print("\n" + "=" * 50)

    if data.get("vendor_name"):
        print(data["vendor_name"].center(50))
    if data.get("vendor_address"):
        print(data["vendor_address"].center(50))
    if data.get("vendor_gst"):
        print(f"GST: {data['vendor_gst']}".center(50))

    print("-" * 50)

    if data.get("date") or data.get("time"):
        print(f"Date: {data.get('date')}   Time: {data.get('time')}")

    print("-" * 50)

    if data["items"]:
        print(f"{'ITEM':25}{'QTY':>5}{'PRICE':>10}")
        print("-" * 50)
        for i in data["items"]:
            print(f"{i['name'][:25]:25}{i['quantity']:>5}{i['price']:>10.2f}")

    print("-" * 50)

    if data.get("total_amount") is not None:
        print(f"{'TOTAL':35}{data['total_amount']:>10.2f}")

    print("=" * 50 + "\n")


def call_ollama(prompt: str) -> dict:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw_output = response.json()["response"].strip()
    print(raw_output)

    # STRICT JSON parse
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON:\n{raw_output}") from e

if __name__ == "__main__":
    print("[INFO] Reading OCR results...")
    lines = extract_transcriptions_only(DATA_PATH)

    receipt_text = "\n".join(lines)

    print("[INFO] Sending to Ollama")
    prompt = build_prompt(receipt_text)

    receipt_json = call_ollama(prompt)

    print("[INFO] Structured JSON output:\n")
    print(json.dumps(receipt_json, indent=2))

    print("\n[INFO] Pretty receipt view:")
    pretty_print_receipt(receipt_json)