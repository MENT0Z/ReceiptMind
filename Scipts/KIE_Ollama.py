import json
import re
import requests
from receiptModel import ReceiptData, Item

# =====================================================
# CONFIG
# =====================================================

DATA_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR\inference_results\system_results.txt"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3"

# =====================================================
# OCR NORMALIZATION
# =====================================================

def normalize_line(line):
    xs = [p[0] for p in line["points"]]
    ys = [p[1] for p in line["points"]]

    return {
        "text": line["transcription"].strip(),
        "x_min": min(xs),
        "y_min": min(ys),
        "x_max": max(xs),
        "y_max": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys)
    }

# =====================================================
# RULE-BASED EXTRACTION (STRONG)
# =====================================================

def extract_vendor_name(lines, img_height):
    keywords = ["STORE", "SHOP", "MART", "SUPERMARKET", "HOTEL", "RESTAURANT", "ENTERPRISE"]
    candidates = []

    for l in lines:
        txt = l["text"].upper()
        if l["y_min"] < 0.25 * img_height:
            if any(k in txt for k in keywords) or sum(c.isalpha() for c in txt) > 12:
                candidates.append(l)

    return max(candidates, key=lambda x: x["width"])["text"] if candidates else None


def extract_vendor_phone(lines):
    for l in lines:
        m = re.findall(r"(\+91[-\s]?)?\d{10}", l["text"])
        if m:
            return m[0].replace(" ", "").replace("-", "")
    return None


def extract_vendor_gst(lines):
    for l in lines:
        m = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]\b", l["text"])
        if m:
            return m.group()
    return None


def extract_date_time(lines):
    date, time = None, None

    for l in lines:
        if not date:
            m = re.search(r"\b\d{2}[/-]\d{2}[/-]\d{4}\b", l["text"])
            if m:
                date = m.group()

        if not time:
            m = re.search(r"\b\d{2}:\d{2}(:\d{2})?\b", l["text"])
            if m:
                time = m.group()

    return date, time


def extract_address(lines, vendor_name):
    ADDRESS_KEYS = [
        "NO.", "ROAD", "RD", "JALAN", "TAMAN",
        "STREET", "AREA", "CITY", "STATE",
        "PIN", "POSTCODE"
    ]

    start_collecting = False
    address_lines = []

    for l in lines:
        txt = l["text"].upper()

        # start AFTER vendor name
        if vendor_name and vendor_name.upper() in txt:
            start_collecting = True
            continue

        if not start_collecting:
            continue

        if any(k in txt for k in ADDRESS_KEYS) or re.search(r"\b\d{5,6}\b", txt):
            address_lines.append(l["text"])
        elif address_lines:
            break

    return " ".join(address_lines) if address_lines else None


# =====================================================
# LLM (ONLY FOR ITEMS & AMOUNTS)
# =====================================================

def build_receipt_text(lines):
    return "\n".join(l["text"] for l in lines if l["text"])


def build_llm_prompt(receipt_text: str) -> str:
    return f"""
    Task:
        Extract ONLY items and payment amounts from the receipt text.
        Return ONLY valid JSON. No text.
        Rules (STRICT):
        - Copy values EXACTLY from text
        - Do NOT calculate or infer
        - Do NOT guess missing values
        - If a value is not explicitly present, use null
        - Item name MUST appear verbatim in text
        - Quantity = 1 unless explicitly stated
        - Price MUST appear next to item or on same line
        - Choose the LARGEST total as total_amount

        Schema:
            {{
            "total_amount": number | null,
            "items": [
                {{"name": string, "quantity": number, "price": number}}
            ],
            "subtotal_amount": number | null,
            "tax_amount": number | null,
            "discount_amount": number | null,
            }}

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
        }
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=240)
    res.raise_for_status()

    raw = res.json().get("response", "").strip()

    print("\n[RAW LLM OUTPUT]\n", raw, "\n")

    # -------------------------------
    # 1️⃣ Remove markdown fences
    # -------------------------------
    raw = re.sub(r"^```json", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^```", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    # -------------------------------
    # 2️⃣ Extract first JSON object
    # -------------------------------
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output:\n{raw}")

    json_str = match.group()

    # -------------------------------
    # 3️⃣ Parse safely
    # -------------------------------
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON returned by LLM:\n{json_str}"
        ) from e

# =====================================================
# MAIN PARSER
# =====================================================

def parse_ocr_file(path):
    receipts = []

    with open(path, "r", encoding="utf-8") as f:
        for row in f:
            img_name, json_data = row.strip().split("\t", 1)
            ocr_lines = json.loads(json_data)

            lines = [normalize_line(l) for l in ocr_lines]
            lines.sort(key=lambda x: x["y_min"])

            img_height = max(l["y_max"] for l in lines)

            receipt = ReceiptData()
            receipt.receipt_id = img_name

            # RULE-BASED
            receipt.vendor_name = extract_vendor_name(lines, img_height)
            receipt.vendor_phone = extract_vendor_phone(lines)
            receipt.vendor_gst = extract_vendor_gst(lines)
            receipt.vendor_address = extract_address(lines, receipt.vendor_name)
            receipt.date, receipt.time = extract_date_time(lines)

            # LLM ONLY FOR REST
            receipt_text = build_receipt_text(lines)
            llm_data = call_ollama(build_llm_prompt(receipt_text))

            receipt.subtotal_amount = llm_data.get("subtotal_amount")
            receipt.tax_amount = llm_data.get("tax_amount")
            receipt.discount_amount = llm_data.get("discount_amount")
            receipt.total_amount = llm_data.get("total_amount")
            receipt.payment_method = llm_data.get("payment_method")
            receipt.card_last4 = llm_data.get("card_last4")
            receipt.transaction_id = llm_data.get("transaction_id")


            items_data = llm_data.get("items", [])

            receipt.items = [
                Item(
                    name=i.get("name", "").strip(),
                    quantity=i.get("quantity", 1),
                    price=i.get("price", 0.0)
                )
                for i in items_data
                if i.get("name") and i.get("price") is not None
            ]

            receipts.append(receipt)

    return receipts

# =====================================================
# PRINT
# =====================================================

def print_receipt(r: ReceiptData):
    print(r)
    """
    print("\n" + "=" * 50)
    if r.vendor_name:
        print(r.vendor_name.center(50))
    if r.vendor_address:
        print(r.vendor_address.center(50))
    if r.vendor_phone:
        print(f"Phone: {r.vendor_phone}".center(50))
    if r.vendor_gst:
        print(f"GST: {r.vendor_gst}".center(50))

    print("-" * 50)
    print(f"Date: {r.date}   Time: {r.time}")
    print("-" * 50)

    if r.items:
        print(f"{'ITEM':25}{'QTY':>5}{'PRICE':>10}")
        print("-" * 50)
        for i in r.items:
            print(f"{i.name[:25]:25}{i.quantity:>5}{i.price:>10.2f}")

    print("-" * 50)
    if r.total_amount:
        print(f"{'TOTAL':35}{r.total_amount:>10.2f}")
    print("=" * 50)
    """


if __name__ == "__main__":
    receipts = parse_ocr_file(DATA_PATH)
    for r in receipts:
        print_receipt(r)
