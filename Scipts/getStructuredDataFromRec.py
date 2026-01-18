import json
import re
from receiptModel import ReceiptData, Item  

dataDir = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\PaddleOCR\inference_results\system_results.txt"

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
        "height": max(ys) - min(ys),
        "center_y": sum(ys) / 4
    }


# =========================
# Entity Extraction Logic
# =========================

def extract_vendor_name(lines, img_height):
    candidates = []
    for l in lines:
        if l["y_min"] < 0.2 * img_height:
            if sum(c.isalpha() for c in l["text"]) > 10:
                candidates.append(l)
    if not candidates:
        return None
    return max(candidates, key=lambda x: x["width"])["text"]


def extract_vendor_gst(lines):
    for l in lines:
        if "GST" in l["text"].upper():
            nums = re.findall(r"\d{6,}", l["text"])
            if nums:
                return nums[0]
    return None


def extract_vendor_phone(lines):
    for l in lines:
        phone = re.findall(r"\+?\d{10,13}", l["text"])
        if phone:
            return phone[0]
    return None


def extract_address(lines):
    ADDRESS_KEYS = ["ROAD", "JALAN", "TAMAN", "NO", "CITY", "SELANGOR", "PIN"]
    address_lines = []
    for l in lines:
        if any(k in l["text"].upper() for k in ADDRESS_KEYS):
            address_lines.append(l["text"])
        elif address_lines:
            break
    return " ".join(address_lines) if address_lines else None


def extract_date_time(lines):
    date, time = None, None
    for l in lines:
        if not date:
            m = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", l["text"])
            if m:
                date = m.group()
        if not time:
            m = re.search(r"\d{2}:\d{2}", l["text"])
            if m:
                time = m.group()
    return date, time


def extract_total_amount(lines, img_height):
    candidates = []
    for l in lines:
        if any(k in l["text"].upper() for k in ["TOTAL", "AMOUNT", "PAYABLE"]):
            nums = re.findall(r"\d+\.\d{2}", l["text"])
            if nums:
                candidates.append(float(nums[-1]))
    return max(candidates) if candidates else None


def extract_items(lines):
    items = []
    for l in lines:
        nums = re.findall(r"\d+\.\d{2}", l["text"])
        if nums and len(l["text"]) > 5:
            items.append(Item(name=l["text"], price=float(nums[-1])))
    return items


# =========================
# Main Parser
# =========================

def parse_ocr_file(file_path):
    receipts = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            img_name, json_data = line.strip().split("\t", 1)
            ocr_lines = json.loads(json_data)

            norm_lines = [normalize_line(l) for l in ocr_lines]
            norm_lines.sort(key=lambda x: x["y_min"])

            img_height = max(l["y_max"] for l in norm_lines)

            receipt = ReceiptData()
            receipt.receipt_id = img_name
            receipt.vendor_name = extract_vendor_name(norm_lines, img_height)
            receipt.vendor_gst = extract_vendor_gst(norm_lines)
            receipt.vendor_phone = extract_vendor_phone(norm_lines)
            receipt.vendor_address = extract_address(norm_lines)
            receipt.date, receipt.time = extract_date_time(norm_lines)
            receipt.total_amount = extract_total_amount(norm_lines, img_height)
            receipt.items = extract_items(norm_lines)

            receipts.append(receipt)

    return receipts

def print_receipt(receipt: ReceiptData):
    print("\n" + "=" * 50)

    # Vendor
    if receipt.vendor_name:
        print(f"{receipt.vendor_name.upper():^50}")
    if receipt.vendor_address:
        print(f"{receipt.vendor_address:^50}")
    if receipt.vendor_phone:
        print(f"Phone: {receipt.vendor_phone:^42}")
    if receipt.vendor_gst:
        print(f"GST: {receipt.vendor_gst:^44}")

    print("-" * 50)

    # Metadata
    if receipt.receipt_id:
        print(f"Receipt ID : {receipt.receipt_id}")
    if receipt.date or receipt.time:
        print(f"Date       : {receipt.date or ''}   Time: {receipt.time or ''}")

    print("-" * 50)

    # Items
    if receipt.items:
        print(f"{'ITEM':25}{'QTY':>5}{'PRICE':>10}")
        print("-" * 50)
        for item in receipt.items:
            print(f"{item.name[:25]:25}{item.quantity:>5}{item.price:>10.2f}")

    print("-" * 50)

    # Amounts
    if receipt.subtotal_amount:
        print(f"{'Subtotal':35}{receipt.subtotal_amount:>10.2f}")
    if receipt.tax_amount:
        print(f"{'Tax':35}{receipt.tax_amount:>10.2f}")
    if receipt.discount_amount:
        print(f"{'Discount':35}{receipt.discount_amount:>10.2f}")
    if receipt.total_amount:
        print(f"{'TOTAL':35}{receipt.total_amount:>10.2f}")

    print("-" * 50)

    # Payment
    if receipt.payment_method:
        print(f"Payment Mode : {receipt.payment_method}")
    if receipt.card_last4:
        print(f"Card (Last4) : {receipt.card_last4}")
    if receipt.transaction_id:
        print(f"Txn ID       : {receipt.transaction_id}")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    results = parse_ocr_file(dataDir)

    for r in results:
        print_receipt(r)
    
   