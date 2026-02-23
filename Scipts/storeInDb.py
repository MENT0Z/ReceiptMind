import json
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta
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

from db_utils import CATEGORY_ITEMS, CATEGORY_NAME_TO_ID

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

def safe_numeric(v):
    if v in ("", None):
        return None
    return float(v)

def storeInDB(data):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    try:
        parsed = data.get("parsed_output", {})

        # -------------------------------
        # RECEIPT BASIC FIELDS (SOFT)
        # -------------------------------
        receipt_ts = parse_receipt_ts(parsed.get("date"), None)
        total = parsed.get("total_amount")

        # allow missing total
        if total is None:
            total = ""

        # -------------------------------
        # VENDOR (SOFT)
        # -------------------------------
        vendor_id = None
        vendor_name = safe_str(parsed.get("vendor_name"))

        if vendor_name:
            cur.execute("""
                SELECT vendor_id
                FROM vendors
                WHERE LOWER(name) = LOWER(%s)
                LIMIT 1;
            """, (vendor_name,))

            row = cur.fetchone()
            if row:
                vendor_id = row["vendor_id"]
            else:
                cur.execute("""
                    INSERT INTO vendors (name, address, phone)
                    VALUES (%s,%s,%s)
                    RETURNING vendor_id;
                """, (
                    vendor_name,
                    safe_str(parsed.get("vendor_address")),
                    safe_str(parsed.get("vendor_phone"))
                ))
                vendor_id = cur.fetchone()["vendor_id"]

        # -------------------------------
        # INSERT RECEIPT (NO STRICT CHECKS)
        # -------------------------------
        cur.execute("""
            INSERT INTO receipts (
                vendor_id,
                receipt_datetime,
                total
            )
            VALUES (%s,%s,%s)
            RETURNING receipt_id;
        """, (
            vendor_id,
            receipt_ts,
            total
        ))
        receipt_id = cur.fetchone()["receipt_id"]
        # -------------------------------
        # ITEMS (CATEGORY FROM JSON ONLY)
        # -------------------------------
        for item in parsed.get("items", []):
            name = safe_str(item.get("name"))
            if not name or is_noise_item(name):
                continue

            category_name = safe_str(item.get("category")).lower()
            if not category_name:
                continue

            cur.execute("""
                SELECT category_id
                FROM categories
                WHERE LOWER(name) = %s
                LIMIT 1;
            """, (category_name,))

            cat_row = cur.fetchone()
            if not cat_row:
                continue

            quantity = item.get("quantity") or 1
            unit_price = safe_numeric(item.get("price"))
        

            # insert item and get item_id
            cur.execute("""
                INSERT INTO items (
                    receipt_id,
                    category_id,
                    name,
                    quantity,
                    unit_price
                )
                VALUES (%s,%s,%s,%s,%s)
                RETURNING item_id;
            """, (
                receipt_id,
                cat_row["category_id"],
                name,
                quantity,
                unit_price,
            ))

            item_id = cur.fetchone()["item_id"]

            # insert into item_search with NULL embed
            cur.execute("""
                INSERT INTO item_search (item_id, embed)
                VALUES (%s, NULL);
            """, (item_id,))

        conn.commit()
        return {"status": "ok", "receipt_id": receipt_id}

    except Exception as e:
        conn.rollback()
        print("❌ storeInDB error:", e)
        return {"status": "failed"}

    finally:
        cur.close()
        conn.close()

def _fetch_items_for_receipts(cur, receipt_ids):
    if not receipt_ids:
        return {}

    cur.execute("""
        SELECT
            item_id,
            receipt_id,
            name,
            quantity,
            unit_price,
            total_price
        FROM items
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id;
    """, (receipt_ids,))

    items_map = {}

    for r in cur.fetchall():
        receipt_id = r[1]

        items_map.setdefault(receipt_id, []).append({
            "item_id": r[0],
            "name": r[2],
            "quantity": float(r[3]),
            "unit_price": float(r[4]),
            "total_price": float(r[5]) if r[5] else float(r[3] * r[4])
        })

    return items_map

def getDashboardStats(time_filter="all_time"):
    """
    time_filter:
        - "all_time" (default)
        - "last_year"
        - "last_30_days"
        - "last_7_days"
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        result = {}

        # ----------------------------
        # Build date condition
        # ----------------------------
        date_condition = ""
        params = ()

        if time_filter == "last_year":
            start_date = datetime.now() - timedelta(days=365)
            date_condition = "WHERE receipt_datetime >= %s"
            params = (start_date,)

        elif time_filter == "last_30_days":
            start_date = datetime.now() - timedelta(days=30)
            date_condition = "WHERE receipt_datetime >= %s"
            params = (start_date,)

        elif time_filter == "last_7_days":
            start_date = datetime.now() - timedelta(days=7)
            date_condition = "WHERE receipt_datetime >= %s"
            params = (start_date,)

        # ----------------------------
        # 1️⃣ Total spent
        # ----------------------------
        cur.execute(
            f"SELECT COALESCE(SUM(total), 0) FROM receipts {date_condition};",
            params
        )
        result["total_spent"] = float(cur.fetchone()[0])

        # ----------------------------
        # 2️⃣ Total receipts
        # ----------------------------
        cur.execute(
            f"SELECT COUNT(*) FROM receipts {date_condition};",
            params
        )
        result["total_receipts"] = cur.fetchone()[0]

        # ----------------------------
        # 3️⃣ Avg spent per receipt
        # ----------------------------
        cur.execute(
            f"SELECT COALESCE(AVG(total), 0) FROM receipts {date_condition};",
            params
        )
        result["avg_spent_per_receipt"] = float(cur.fetchone()[0])

        # ----------------------------
        # 4️⃣ Top categories
        # ----------------------------
        cur.execute(f"""
            SELECT 
                c.category_id,
                c.name,
                SUM(i.total_price)
            FROM items i
            JOIN categories c ON i.category_id = c.category_id
            JOIN receipts r ON i.receipt_id = r.receipt_id
            {date_condition.replace("receipt_datetime", "r.receipt_datetime")}
            GROUP BY c.category_id, c.name
            ORDER BY SUM(i.total_price) DESC;
        """, params)

        result["top_categories"] = [
            {
                "category_id": r[0],
                "category_name": r[1],
                "total_spent": float(r[2])
            }
            for r in cur.fetchall()
        ]

        # ----------------------------
        # 5️⃣ Year-wise spending
        # ----------------------------
        cur.execute(f"""
            SELECT 
                EXTRACT(YEAR FROM receipt_datetime),
                SUM(total)
            FROM receipts
            {date_condition}
            GROUP BY 1
            ORDER BY 1;
        """, params)

        result["yearly_spending"] = [
            {
                "year": int(r[0]),
                "total_spent": float(r[1])
            }
            for r in cur.fetchall()
        ]

        # ----------------------------
        # 6️⃣ Recent 5 receipts
        # ----------------------------
        cur.execute(f"""
            SELECT receipt_id, receipt_datetime, total
            FROM receipts
            {date_condition}
            ORDER BY receipt_datetime DESC
            LIMIT 5;
        """, params)

        recent_rows = cur.fetchall()
        recent_ids = [r[0] for r in recent_rows]

        recent_items = _fetch_items_for_receipts(cur, recent_ids)

        result["recent_receipts"] = [
            {
                "receipt_id": r[0],
                "receipt_datetime": r[1].isoformat(),
                "total": float(r[2]),
                "items": recent_items.get(r[0], [])
            }
            for r in recent_rows
        ]

        return result

    except Exception as e:
        print("❌ getDashboardStats error:", e)
        return None

    finally:
        cur.close()
        conn.close()

def getAllReceipts():
    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1️⃣ Receipts with vendor info
        cur.execute("""
            SELECT
                r.receipt_id,
                r.receipt_datetime,
                r.total,
                v.name AS vendor_name,
                v.address AS vendor_address
            FROM receipts r
            LEFT JOIN vendors v ON r.vendor_id = v.vendor_id
            ORDER BY r.receipt_datetime DESC;
        """)

        receipts = cur.fetchall()
        receipt_ids = [r[0] for r in receipts]

        # 2️⃣ Items per receipt
        cur.execute("""
            SELECT
                i.receipt_id,
                i.name,
                i.quantity,
                i.total_price
            FROM items i
            WHERE i.receipt_id = ANY(%s)
            ORDER BY i.item_id;
        """, (receipt_ids,))

        items_map = {}
        for rid, name, qty, price in cur.fetchall():
            items_map.setdefault(rid, []).append({
                "name": name,
                "quantity": float(qty),
                "total_price": float(price)
            })

        # 3️⃣ Final shape
        return [
            {
                "receipt_id": r[0],
                "receipt_datetime": r[1].isoformat() if r[1] else None,
                "total": float(r[2]),
                "vendor_name": r[3],
                "vendor_address": r[4],
                "items": items_map.get(r[0], [])
            }
            for r in receipts
        ]

    finally:
        cur.close()
        conn.close()
# if __name__ == "__main__":
#      result = getDashboardStats()
#      print("Dashboard Stats:", result)






















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
