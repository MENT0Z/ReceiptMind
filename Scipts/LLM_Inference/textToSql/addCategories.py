import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv()

DB_CONFIG = {
    "dbname": "receipt_db",
    "user": "postgres",
    "password": os.getenv("DATABASE_PWD"),
    "host": "localhost",
    "port": 5432
}

# =====================================================
# CATEGORY SOURCE OF TRUTH
# =====================================================

CATEGORY_ITEMS = {
    "restaurant": [],   # ⬅️ KEEP EXACT DATA YOU SENT
    "groceries": [],
    "cafe_beverages": [],
    "transport": [],
    "shopping": [],
    "utilities": [],
    "health": [],
    "education": [],
    "entertainment": [],
    "electronics": [],
    "household": [],
    "travel": [],
    "finance": [],
    "gifts_donations": [],
    "other": []
}

# =====================================================
# DB
# =====================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# =====================================================
# SEED LOGIC
# =====================================================

def seed_categories():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=DictCursor)

    print("🚀 Seeding categories...\n")

    parent_ids = {}

    # -----------------------------
    # 1️⃣ INSERT PARENT CATEGORIES
    # -----------------------------
    for parent_name in CATEGORY_ITEMS.keys():
        cur.execute("""
            INSERT INTO categories (name, parent_id, is_essential)
            VALUES (%s, NULL, false)
            ON CONFLICT (name) DO NOTHING
            RETURNING category_id;
        """, (parent_name,))

        row = cur.fetchone()
        if row:
            parent_ids[parent_name] = row["category_id"]
        else:
            cur.execute(
                "SELECT category_id FROM categories WHERE name = %s;",
                (parent_name,)
            )
            parent_ids[parent_name] = cur.fetchone()["category_id"]

        print(f"✔ Parent: {parent_name} → ID {parent_ids[parent_name]}")

    # -----------------------------
    # 2️⃣ INSERT CHILD ITEMS
    # -----------------------------
    for parent_name, items in CATEGORY_ITEMS.items():
        parent_id = parent_ids[parent_name]

        for item in items:
            cur.execute("""
                INSERT INTO categories (name, parent_id, is_essential)
                VALUES (%s, %s, false)
                ON CONFLICT (name) DO NOTHING;
            """, (item, parent_id))

        print(f"  └─ {len(items)} items added under '{parent_name}'")

    conn.commit()

    # -----------------------------
    # 3️⃣ VERIFY
    # -----------------------------
    cur.execute("""
        SELECT c.category_id, c.name, p.name AS parent
        FROM categories c
        LEFT JOIN categories p ON c.parent_id = p.category_id
        ORDER BY parent NULLS FIRST, c.category_id;
    """)

    rows = cur.fetchall()

    print("\n📦 CATEGORY TREE:")
    for r in rows:
        print(
            f"{r['category_id']:>3} | {r['name']:<25} | parent = {r['parent']}"
        )

    cur.close()
    conn.close()

    print("\n✅ CATEGORY SEEDING COMPLETE")

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    seed_categories()
