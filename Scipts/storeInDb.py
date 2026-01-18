from KIE_Ollama import parse_ocr_file
import psycopg2

DATA_PATH = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR\inference_results\system_results.txt"

def get_connection():
    return psycopg2.connect(
        dbname="receipt_db",
        user="postgres",
        password="user",
        host="localhost",
        port="5432"
    )

def insert_receipt(conn, receipt):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO receipts (
                receipt_id, vendor_name, vendor_address, vendor_phone, vendor_gst,
                date, time, currency,
                subtotal_amount, tax_amount, discount_amount, total_amount,
                payment_method, card_last4, transaction_id,
                confidence_score, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (receipt_id) DO NOTHING
        """, (
            receipt.receipt_id,
            receipt.vendor_name,
            receipt.vendor_address,
            receipt.vendor_phone,
            receipt.vendor_gst,
            receipt.date,
            receipt.time,
            receipt.currency,
            receipt.subtotal_amount,
            receipt.tax_amount,
            receipt.discount_amount,
            receipt.total_amount,
            receipt.payment_method,
            receipt.card_last4,
            receipt.transaction_id,
            receipt.confidence_score,
            receipt.source
        ))

def insert_items(conn, receipt_id, items):
    with conn.cursor() as cur:
        for item in items:
            cur.execute("""
                INSERT INTO items (receipt_id, name, quantity, price)
                VALUES (%s, %s, %s, %s)
            """, (
                receipt_id,
                item.name,
                item.quantity,
                item.price
            ))

def store_receipts(receipts):
    conn = get_connection()
    try:
        for receipt in receipts:
            insert_receipt(conn, receipt)
            insert_items(conn, receipt.receipt_id, receipt.items)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    receipts = parse_ocr_file(DATA_PATH)
    store_receipts(receipts)