import json
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import os
import requests
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser
import sys

# =====================================================
# PATH SETUP
# =====================================================

utils_path = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts\LLM_Inference\textToSql"
if utils_path not in sys.path:
    sys.path.append(utils_path)

from utils import CATEGORY_ITEMS, CATEGORY_NAME_TO_ID

# =====================================================
# CONFIG
# =====================================================

load_dotenv()

OLLAMA_LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3:1b"

DATA_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\parsed_receipts_new.txt"

DB_CONFIG = {
    "dbname": "receipt_db",
    "user": "postgres",
    "password": os.getenv("DATABASE_PWD"),
    "host": "localhost",
    "port": 5432
}

FUZZY_THRESHOLD = 2

# =====================================================
# CATEGORY LOOKUP
# =====================================================

ITEM_TO_CATEGORY = {
    item.lower(): category
    for category, items in CATEGORY_ITEMS.items()
    for item in items
}

# =====================================================
# HELPERS
# =====================================================

def safe_str(v):
    return v.strip() if isinstance(v, str) else ""

def normalize_item_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()

def parse_receipt_ts(date_raw, time_raw=None):
    if not date_raw:
        return datetime.now(timezone.utc)

    try:
        raw = str(date_raw)
        raw = re.sub(r"[A-Za-z\-]{3,}", " ", raw)
        raw = re.sub(r"(\d)(\d{1,2}:\d{2})", r"\1 \2", raw)

        if time_raw:
            raw = f"{raw} {time_raw}"

        dt = dateparser.parse(raw, dayfirst=True, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception:
        return datetime.now(timezone.utc)

def is_noise_item(name: str) -> bool:
    name = name.lower()
    noise_keywords = [
        "tax", "gst", "total", "amt", "%",
        "subtotal", "discount", "change"
    ]
    return any(k in name for k in noise_keywords)

# =====================================================
# CATEGORY RESOLUTION
# =====================================================

def classify_item_llm(item_name):
    valid_categories = list(CATEGORY_ITEMS.keys())

    prompt = f"""
    Classify the receipt item: "{item_name}"
    Pick ONLY one category from:
    {', '.join(valid_categories)}
    """

    try:
        r = requests.post(
            OLLAMA_LLM_URL,
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
            timeout=10
        )
        r.raise_for_status()
        res = r.json()["response"].strip().lower()
        return res if res in valid_categories else "other"
    except Exception:
        return "other"

def resolve_category(item_name):
    norm = normalize_item_name(item_name)

    if norm in ITEM_TO_CATEGORY:
        return CATEGORY_NAME_TO_ID[ITEM_TO_CATEGORY[norm]]

    cat = classify_item_llm(norm)
    return CATEGORY_NAME_TO_ID.get(cat, CATEGORY_NAME_TO_ID["other"])

# =====================================================
# DB OPERATIONS
# =====================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def get_or_create_vendor(cur, receipt):
    name = safe_str(receipt.get("vendor_name"))
    if not name:
        return None

    cur.execute("""
        SELECT vendor_id
        FROM vendors
        WHERE levenshtein(name_lower, LOWER(%s)) <= %s
        ORDER BY levenshtein(name_lower, LOWER(%s))
        LIMIT 1;
    """, (name, FUZZY_THRESHOLD, name))

    row = cur.fetchone()
    if row:
        return row["vendor_id"]

    cur.execute("""
        INSERT INTO vendors (name, address, phone, gst)
        VALUES (%s,%s,%s,%s)
        RETURNING vendor_id;
    """, (
        name,
        safe_str(receipt.get("vendor_address")),
        safe_str(receipt.get("vendor_phone")),
        safe_str(receipt.get("vendor_gst"))
    ))

    return cur.fetchone()["vendor_id"]

def insert_receipt(cur, receipt, vendor_id):
    receipt_id = safe_str(receipt.get("receipt_id"))
    total = receipt.get("total_amount")

    if not receipt_id or total is None:
        return

    receipt_DateTime = parse_receipt_ts(
        receipt.get("date"),
        receipt.get("time")
    )

    cur.execute("""
        INSERT INTO receipts (
            receipt_id,
            vendor_id,
            receipt_DateTime,
            subtotal,
            tax,
            discount,
            total,
            payment_method,
            card_last4,
            transaction_id
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (receipt_id) DO NOTHING;
    """, (
        receipt_id,
        vendor_id,
        receipt_DateTime,
        receipt.get("subtotal_amount"),
        receipt.get("tax_amount"),
        receipt.get("discount_amount"),
        total,
        safe_str(receipt.get("payment_method")),
        safe_str(receipt.get("card_last4")),
        safe_str(receipt.get("transaction_id"))
    ))

def insert_items(cur, receipt_id, items):
    for item in items:
        name = safe_str(item.get("name"))
        if not name or is_noise_item(name):
            continue

        cur.execute("""
            INSERT INTO items (
                receipt_id,
                category_id,
                name,
                quantity,
                unit_price
            )
            VALUES (%s,%s,%s,%s,%s);
        """, (
            receipt_id,
            resolve_category(name),
            name,
            item.get("quantity") or 1,
            item.get("price") or 0
        ))

# =====================================================
# MAIN
# =====================================================

def ingest():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    inserted, skipped = 0, 0

    if not os.path.exists(DATA_PATH):
        print(f"❌ File not found: {DATA_PATH}")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                receipt = json.loads(line)
                vendor_id = get_or_create_vendor(cur, receipt)
                insert_receipt(cur, receipt, vendor_id)
                insert_items(cur, receipt["receipt_id"], receipt.get("items", []))
                conn.commit()
                inserted += 1

            except Exception as e:
                conn.rollback()
                print(f"[Line {line_no}] ❌ {e}")
                skipped += 1

    cur.close()
    conn.close()

    print(f"\n✅ INGESTION COMPLETE")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")

if __name__ == "__main__":
    ingest()

























# import json
# import psycopg2
# from psycopg2.extras import DictCursor
# from dotenv import load_dotenv
# import os
# import requests

# # =====================================================
# # CONFIG
# # =====================================================

# load_dotenv()

# OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
# EMBED_MODEL = "bge-m3"

# DATA_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\parsed_receipts.txt"

# DB_CONFIG = {
#     "dbname": "receipt_db",
#     "user": "postgres",
#     "password": os.getenv("DATABASE_PWD"),
#     "host": "localhost",
#     "port": 5432
# }

# FUZZY_THRESHOLD = 2

# # =====================================================
# # HELPERS
# # =====================================================

# def safe_str(value):
#     return value.strip() if isinstance(value, str) else ""

# def generate_embedding_safe(text):
#     text = safe_str(text)
#     if not text:
#         return None

#     payload = {
#         "model": EMBED_MODEL,
#         "prompt": text
#     }

#     try:
#         response = requests.post(
#             OLLAMA_EMBED_URL,
#             json=payload,
#             timeout=60
#         )
#         response.raise_for_status()

#         embedding = response.json().get("embedding")
#         if embedding and len(embedding) == 1024:
#             return embedding

#         print("⚠️ Invalid embedding length")
#         return None

#     except Exception as e:
#         print("⚠️ Ollama embedding failed:", e)
#         return None

# # =====================================================
# # DB CONNECTION
# # =====================================================

# def get_connection():
#     return psycopg2.connect(**DB_CONFIG)

# # =====================================================
# # VENDOR UPSERT
# # =====================================================

# def get_or_create_vendor(cur, receipt):
#     name = safe_str(receipt.get("vendor_name"))
#     address = safe_str(receipt.get("vendor_address"))
#     phone = safe_str(receipt.get("vendor_phone"))
#     gst = safe_str(receipt.get("vendor_gst"))

#     if not name:
#         return None

#     cur.execute("""
#         SELECT vendor_id
#         FROM vendors
#         WHERE levenshtein(name_lower, LOWER(%s)) <= %s
#         ORDER BY levenshtein(name_lower, LOWER(%s))
#         LIMIT 1;
#     """, (name, FUZZY_THRESHOLD, name))

#     row = cur.fetchone()
#     if row:
#         return row["vendor_id"]

#     embed = generate_embedding_safe(name)

#     cur.execute("""
#         INSERT INTO vendors (name, address, phone, gst, name_embed)
#         VALUES (%s,%s,%s,%s,%s)
#         RETURNING vendor_id;
#     """, (name, address, phone, gst, embed))

#     return cur.fetchone()["vendor_id"]

# # =====================================================
# # RECEIPT INSERT (RAW STRING ONLY)
# # =====================================================

# def insert_receipt(cur, receipt, vendor_id):
#     cur.execute("""
#         INSERT INTO receipts (
#             receipt_id,
#             vendor_id,
#             receipt_date_raw,
#             receipt_time,
#             subtotal,
#             tax,
#             discount,
#             total,
#             payment_method,
#             card_last4,
#             transaction_id
#         )
#         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         ON CONFLICT (receipt_id) DO NOTHING;
#     """, (
#         safe_str(receipt.get("receipt_id")),
#         vendor_id,
#         safe_str(receipt.get("date")),
#         safe_str(receipt.get("time")),
#         receipt.get("subtotal_amount"),
#         receipt.get("tax_amount"),
#         receipt.get("discount_amount"),
#         receipt.get("total_amount"),
#         safe_str(receipt.get("payment_method")),
#         safe_str(receipt.get("card_last4")),
#         safe_str(receipt.get("transaction_id"))
#     ))

# # =====================================================
# # ITEMS INSERT
# # =====================================================

# def insert_items(cur, receipt_id, items):
#     for item in items:
#         name = safe_str(item.get("name"))
#         embed = generate_embedding_safe(name)

#         cur.execute("""
#             INSERT INTO items (
#                 receipt_id,
#                 name,
#                 quantity,
#                 price,
#                 name_embed
#             )
#             VALUES (%s,%s,%s,%s,%s);
#         """, (
#             receipt_id,
#             name,
#             item.get("quantity"),
#             item.get("price"),
#             embed
#         ))

# # =====================================================
# # MAIN INGESTION
# # =====================================================

# def ingest():
#     conn = get_connection()
#     cur = conn.cursor(cursor_factory=DictCursor)

#     inserted = 0
#     skipped = 0

#     with open(DATA_PATH, "r", encoding="utf-8") as f:
#         for line_no, line in enumerate(f, start=1):
#             if not line.strip():
#                 continue

#             try:
#                 receipt = json.loads(line)
#             except json.JSONDecodeError:
#                 print(f"[Line {line_no}] ❌ Invalid JSON")
#                 skipped += 1
#                 continue

#             try:
#                 vendor_id = get_or_create_vendor(cur, receipt)
#                 insert_receipt(cur, receipt, vendor_id)
#                 insert_items(cur, receipt["receipt_id"], receipt.get("items", []))
#                 inserted += 1

#             except Exception as e:
#                 conn.rollback()
#                 print(f"[Line {line_no}] ❌ DB Error:", e)
#                 skipped += 1

#     conn.commit()
#     cur.close()
#     conn.close()

#     print("===================================")
#     print("✅ Ingestion completed")
#     print(f"Inserted receipts: {inserted}")
#     print(f"Skipped receipts: {skipped}")
#     print("===================================")

# # =====================================================
# # ENTRY POINT
# # =====================================================

# if __name__ == "__main__":
#     ingest()
