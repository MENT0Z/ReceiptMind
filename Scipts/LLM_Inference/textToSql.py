import re
import json
import psycopg2
import numpy as np
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# ===============================
# CONFIGURATION
# ===============================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3"
EMBEDDING_MODEL = "bge-m3:latest"
load_dotenv()

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "receipt_db",
    "user": "postgres",
    "password": os.getenv("DATABASE_PWD")
}

VECTOR_THRESHOLD = 0.5  # similarity threshold for semantic search
FUZZY_DISTANCE = 2      # Levenshtein distance for fuzzy matches

# ===============================
# UTILITY FUNCTIONS
# ===============================
def call_ollama(prompt: str):
    """
    Sends a prompt to local Gemma3 (Ollama) and returns response.
    """
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 1024}
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload)
    resp.raise_for_status()
    return resp.json()["completion"]

def generate_embedding(text: str):
    """
    Generate semantic embedding using local BGE-M3 API
    Returns a 1536-dim list
    """
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text
    }
    resp = requests.post(f"{OLLAMA_URL}/api/embed", json=payload)
    resp.raise_for_status()
    return resp.json()["embedding"]

def sanitize_date(text: str):
    """
    Convert natural language dates to YYYY-MM-DD
    Example: 'this month', 'last week', '2026-01-01'
    """
    today = datetime.today()
    text = text.lower()
    if "this month" in text:
        start = today.replace(day=1)
        end = today
    elif "last month" in text:
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        start = last_day_last_month.replace(day=1)
        end = last_day_last_month
    elif "this week" in text:
        start = today - timedelta(days=today.weekday())
        end = today
    else:
        # fallback: try parsing exact date
        try:
            start = end = datetime.strptime(text, "%Y-%m-%d")
        except:
            start = end = today
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

# ===============================
# CORE PIPELINE
# ===============================
class RAGQueryPipeline:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
        self.cur = self.conn.cursor()

    def extract_intent_filters(self, user_query: str):
        """
        Use LLM to extract:
            - intent (spend_summary, top_items, vendor_spend, category_insight)
            - filters (date_range, vendor_name, payment_method, categories)
        Returns dict
        """
        prompt = f"""
        Analyze the following user question and extract structured intent and filters.
        Respond ONLY as JSON.

        Question: "{user_query}"

        JSON format:
        {{
            "intent": "<intent>",
            "date_filter": "<this month / last week / yyyy-mm-dd>",
            "vendor_name": "<optional vendor name>",
            "payment_method": "<optional cash/card>",
            "category": "<optional category like entertainment, education, groceries, etc>",
            "item_name": "<optional item name>"
        }}
        """
        response = call_ollama(prompt)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            print("LLM response not valid JSON, fallback empty filters")
            return {
                "intent": "spend_summary",
                "date_filter": "this month",
                "vendor_name": None,
                "payment_method": None,
                "category": None,
                "item_name": None
            }

    def build_sql(self, filters: dict):
        """
        Convert extracted filters and intent into a SQL query
        """
        start_date, end_date = sanitize_date(filters.get("date_filter", "this month"))
        sql_parts = ["SELECT SUM(i.price * i.quantity) AS total_spent FROM items i JOIN receipts r ON i.receipt_id = r.receipt_id"]
        where_clauses = [f"r.receipt_date BETWEEN '{start_date}' AND '{end_date}'"]

        # Vendor fuzzy match
        if filters.get("vendor_name"):
            vendor_name = filters["vendor_name"]
            where_clauses.append(
                f"levenshtein(lower(v.name), lower('{vendor_name}')) <= {FUZZY_DISTANCE}"
            )
            sql_parts.append("JOIN vendors v ON r.vendor_id = v.vendor_id")

        # Payment method
        if filters.get("payment_method"):
            method = filters["payment_method"].lower()
            where_clauses.append(f"lower(r.payment_method) = '{method}'")

        # Semantic search for item/category
        if filters.get("item_name") or filters.get("category"):
            search_text = filters.get("item_name") or filters.get("category")
            embedding = generate_embedding(search_text)
            embedding_str = str(embedding)
            where_clauses.append(f"i.name_embed <-> '{embedding_str}'::vector < {VECTOR_THRESHOLD}")

        sql = " ".join(sql_parts) + " WHERE " + " AND ".join(where_clauses) + ";"
        return sql

    def query_to_sql(self, user_query: str):
        """
        Main entry point: user text -> SQL
        """
        filters = self.extract_intent_filters(user_query)
        sql = self.build_sql(filters)
        return sql

# ===============================
# TEST RUN
# ===============================
if __name__ == "__main__":
    pipeline = RAGQueryPipeline(DB_CONFIG)
    user_question = "How much did I spend on coffee this month from Starbucks?"
    sql_query = pipeline.query_to_sql(user_question)
    print("Generated SQL:\n", sql_query)
