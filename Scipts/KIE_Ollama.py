import json
import re
import requests
from receiptModel import ReceiptData, Item
import sys

utils_path = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts\LLM_Inference\textToSql"
if utils_path not in sys.path:
    sys.path.append(utils_path)

from db_utils import CATEGORY_ITEMS

def normalize_item_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()

def sanitize_numeric_fields(json_str: str) -> str:
    # quantity → keep digits only
    json_str = re.sub(
        r'("quantity"\s*:\s*)([^,\n}]+)',
        lambda m: f'{m.group(1)}{clean_int(m.group(2))}',
        json_str
    )

    # price → keep digits + dot only
    json_str = re.sub(
        r'("price"\s*:\s*)([^,\n}]+)',
        lambda m: f'{m.group(1)}{clean_float(m.group(2))}',
        json_str
    )

    return json_str

def clean_int(val: str) -> int:
    return int(re.sub(r"[^0-9]", "", val) or 0)

def clean_float(val: str) -> float:
    cleaned = re.sub(r"[^0-9.]", "", val)
    # ensure only one dot
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = parts[0] + "." + "".join(parts[1:])
    return float(cleaned or 0.0)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b-instruct"
TIME_PATTERN = r"\b\d{1,2}[:\.\-]\d{2}([:\.\-]\d{2})?\b"

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

def extract_vendor_name(lines, img_height):
    VENDOR_KEYS = [
        "MEDICALS","HUB","HARDWARE","DOMINO'S","DOMINOS","FOODWORKS",
        "LTD.","WARMOVEN","KFC","PIZZA HUT","PIZZA-HUT","PIZZA HUT DELIVERY","SUBWAY","MCDONALD'S","MCDONALDS","PIZZA",
        "TACO BELL","BURGER KING","STARBUCKS","COFFEE BEAN","PEET'S COFFEE","DUNKIN' DONUTS","TACO BELL","TACO","CORP",
        "DINERS","DINING","RESTAURANT","CAFE","CAFÉ","BISTRO","DHABA","TRADING","COMPANY","CO","PRIVATE","LIMITED","LTD","LLP","INC","CORP","CORPORATION",
        "MITHAI","NAMKEEN","SWEETS","CONFECTIONERY","CONFECTIONERIES","FOOD","JUICE","SHAKE","TEA","COFFEE","PIZZA","BURGER",
        "SUPER","SUPER MART","SUPER MARKET","HYPER","HYPERMARKET","MALL","PLAZA","TOWER","COMPLEX",
        "PAVILLION", "MALL", "PLAZA", "TOWER", "COMPLEX","Pavillion","PAVILION",
        "BAKINO'S",
        "BAKE","SHOP","SHOWROOM","OUTLET","STORE","STORES","MARKET","MART","SUPERMARKET","HYPERMARKET",
        # Retail
        "STORE", "SHOP", "MART", "SUPERMARKET", "HYPERMARKET",
        "BAZAAR", "BAZAR", "MARKET" ,"GROCERY","GROCERS","GROCER","SDN","BHD",
        "PVT", "LTD", "LIMITED", "LLP", "INC", "CORP", "CORPORATION",
        "PVT.", "LTD.", "LLP.", "INC.", "CORP.", "CORPORATION.",
        "KITCHEN", "GROCERY", "GROCER", "GROCERS", "BAKERY", "PHARMACY", "ELECTRONICS", "MOBILE", "CLOTHING", "FASHION", "JEWELRY", 
        # Food / hospitality
        "HOTEL", "RESTAURANT", "CAFE", "CAFÉ",
        "BISTRO", "DHABA", "BAKERY", "SWEETS","BAKERIES","SWEET","CONFECTIONERY","CONFECTIONERIES","FOOD","JUICE","SHAKE","TEA","COFFEE","PIZZA","BURGER",
        "MEAT", "BUTCHER", "FISH", "POULTRY", "BAKED GOODS",
        "MOBILE", "ELECTRONICS", "HARDWARE",
        "CLOTHING", "FASHION", "APPAREL", "TEXTILES", "GARMENTS",
        "JEWELERS", "JEWELLERS", "JEWELRY", "ACCESSORIES",
        "PHARMACY", "DRUGS", "MEDICAL", "HOSPITAL",
        "SALON", "SPA", "STUDIO", "FITNESS", "GYM",
        "THEATER", "CINEMA", "ENTERTAINMENT",
        "TRAVEL", "TOURISM", "AGENCY",
        "TRANSPORT", "LOGISTICS", "DELIVERY",
        "SERVICE", "SERVICES",
        "DUKAAN","KIRANA","KIRANA STORE","GENERAL STORE",
        "GROCERY STORE","GROCERY STORES",
        "OPEN MART","DAIRY","VEGETABLES","FRUITS","FRUIT","VEG","VEGGIES",
        "CONVENIENCE STORE","CONVENIENCE","RETAIL",
        "PHOTOCOPY","STATIONERY","BOOKS","BOOK STORE","BOOKSTORE",
        "JEWELLERY","JEWELER","JEWELLERS",
        "OPTICALS","OPTICIAN","EYEWEAR",
        "FLORIST","FLOWERS","FLOWER SHOP","FLOWER SHOPPE",
        "TOYS","TOY STORE","TOY SHOP",
        "SPORTS","SPORTS GOODS","SPORTS STORE",
        "AUTOMOTIVE","AUTO PARTS","CAR REPAIR","CAR SERVICE",
        "PET STORE","PET SHOP","PET SUPPLIES",
        "GARDEN CENTER","GARDEN CENTRE","PLANTS","PLANT NURSERY",
        "FURNITURE","HOME DECOR","HOME FURNISHINGS",
        "APPLIANCES","ELECTRICALS",
        # Business entities
        "ENTERPRISE", "ENTERPRISES", "TRADERS", "TRADING",
        "AGENCY", "AGENCIES", "DISTRIBUTORS", "SUPPLIERS",
        "COMPANY", "CO", "PVT", "PRIVATE", "LIMITED", "LTD","KFC","MC DONALDS","MCDONALD'S","DOMINOS","DOMINO'S","PIZZA HUT","PIZZA-HUT","PIZZA HUT DELIVERY",
        "LLP", "INC", "CORP", "CORPORATION","BAR","BBQ","BARBECUE","BAR B Q","BARBECUENATION","MCDONALDS","SUBWAY","SUBWAY","KFC","DOMINOS","DOMINO'S","PIZZA HUT","PIZZA-HUT","PIZZA HUT DELIVERY","SUBWAY","PIZZA","BURGER","COFFEE","TEA","JUICE","SHAKE","RESTAURANT","CAFE","CAFÉ","BAKERY","HOTEL","MOTEL","INN",

        # Services
        "PHARMACY", "MEDICAL", "HOSPITAL",
        "ELECTRONICS", "MOBILES", "HARDWARE",
        "FASHION", "TEXTILES", "GARMENTS",

        # Misc
        "OUTLET", "CENTER", "CENTRE", "DEPOT"
    ]

    BLACKLIST = [
        "TAX", "INVOICE", "CASH", "BILL", "RECEIPT",
        "GST", "TOTAL", "AMOUNT", "DETAILS",
        "PHONE", "MOBILE", "TEL"
    ]

    for l in lines:
        txt = l["text"].upper().strip()

        # Only top 35% of receipt
        if l["y_min"] > 0.30 * img_height:
            continue

        # Skip obvious non-vendor lines
        if any(b in txt for b in BLACKLIST):
            continue

        has_keyword = any(k in txt for k in VENDOR_KEYS)
        if has_keyword:
            return l["text"].strip()
        
    return None

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
    time = None, None

    for l in lines:
        text = l["text"]

        if not time:
            m = re.search(TIME_PATTERN, text)
            if m:
                time = m.group()

        if time:
            break

    return time

def normalize_text(txt: str) -> str:
    txt = txt.upper().strip()

    # Fix common OCR confusions
    txt = txt.replace("N0.", "NO.").replace("N0", "NO")

    # Add space between letters and digits
    txt = re.sub(r"([A-Z])(\d)", r"\1 \2", txt)
    txt = re.sub(r"(\d)([A-Z])", r"\1 \2", txt)

    # Normalize house number formats
    txt = re.sub(r"\bNO[\.\-]?\s*\d+", "NO", txt)

    # Collapse multiple spaces
    txt = re.sub(r"\s+", " ", txt)

    return txt

def extract_address(lines, vendor_name):
    ADDRESS_KEYS = [
        # Road / location
        "NO", "NO.", "ROAD", "RD", "ST", "STREET", "LANE", "LN",
        "AVENUE", "AVE", "CROSS", "CIR", "CIRCLE",
        "HIGHWAY", "HWY", "BYPASS", "MAIN","LOT","L0T",
        "JUNCTION", "JCT", "INTERSECTION",
        "SQUARE", "PLAZA", "MARKET", "MARKETPLACE",
        "PARK", "PARKWAY", "EXPRESSWAY", "EXPY",
        "BRIDGE", "TUNNEL","N0","N0.",
        "EXIT", "ENTRANCE",
        "NORTH", "SOUTH", "EAST", "WEST",
        "N", "S", "E", "W",
        "UPPER", "LOWER", "INNER", "OUTER",
        "EASTERN", "WESTERN", "NORTHERN", "SOUTHERN",
        "CENTRAL",
        "ROADWAY", "ALLEE", "ALLEY", "ALY", "WAY",
        "PATH", "TRAIL", "TR", "CRESCENT", "CRES",
        "DRIVE", "DR", "TERRACE", "TER",
        "PLACE", "PL", "COURT", "CT",
        "FLOOR", "FL", "BUILDING", "BLDG",
        "BLOCK", "SECTOR",
        "PHASE", "ZONE",
        "ESTATE", "GARDENS", "GDN", "GARDEN",
        "VISTA",
        "HEIGHTS", "HEIGHT",
        "VIEW",
        "BAY",
        "COVE",
        "SHORE",
        "DUBAI",
        "POINT","PLOT","BRIDGE","TUNNEL","ROAD","BUILDINGS","STREET","ST","LANE","LN","AVENUE","AVE","CROSS","CIR","CIRCLE","HIGHWAY","HWY","BYPASS","MAIN",
        "DELHI","LAYOUT","VILLAGE","VIL","PO","POST OFFICE","TEHSIL","PS","NEAR","OPP","OPPOSITE","BEHIND",
        "FLOOR","NEW DELHI","OLD DELHI","JANAKPURI","SECTOR","COLONY","NAGAR","TALUK","MANDAL","DISTRICT","CITY","TOWN",
        "TAMIL NADU", "TELANGANA", "ANDHRA PRADESH", "KERALA", "KARNATAKA", "MAHARASHTRA", "GUJARAT",
        "RAJASTHAN", "PUNJAB", "HARYANA", "BIHAR", "UTTAR PRADESH", "UTTARAKHAND", "CHHATTISGARH", "ODISHA", "WEST BENGAL", "ASSAM", "NAGALAND", "MANIPUR", "MIZORAM", "TRIPURA", "MEGHALAYA", "ARUNACHAL PRADESH", "SIKKIM",
        "JHARKHAND", "JAMMU AND KASHMIR", "LADAKH", "HIMACHAL PRADESH",
        "DELHI", "NCT",
        "NATIONAL CAPITAL TERRITORY",
        "ANDAMAN AND NICOBAR ISLANDS", "PUDUCHERRY", "DAMAN AND DIU", "LAKSHADWEEP",
        "CHENNAI", "HYDERABAD", "BENGALURU", "BANGALORE", "MUMBAI", "DELHI",
        "KOLKATA", "LUCKNOW", "JAIPUR", "AHMEDABAD", "SURAT",
        "NEPAL","KATHMANDU","DHANGADHI","POKHARA","BIRATNAGAR","BHAIRAWA","LUMBINI",
        "INDIA","INDIAN",
        # Area / locality
        "AREA", "LOCALITY", "COLONY", "NAGAR", "LAYOUT",
        "SECTOR", "BLOCK", "PHASE", "ZONE",
        "TOWN", "CITY", "DISTRICT", "TALUK", "MANDAL",

        # Building / premises
        "BLDG", "BUILDING", "COMPLEX", "PLAZA", "TOWER",
        "FLOOR", "FL", "SHOP", "UNIT", "SUITE", "ROOM",
        "APARTMENT", "APT", "FLAT",

        # Indian specific
        "VILLAGE", "VIL", "PO", "POST OFFICE",
        "TEHSIL", "PS",
        "NEAR", "OPP", "OPPOSITE", "BEHIND",

        # State / country
        "STATE", "PROVINCE", "INDIA",

        # Postal
        "PIN", "PINCODE", "POSTCODE", "ZIP"
    ]

    address_lines = []
    start_collecting = False
    address_started = False

    vendor_words = normalize_text(vendor_name).split() if vendor_name else []

    for l in lines:
        #if(len(address_lines)>=2): break
        raw_text = l["text"]
        txt = normalize_text(raw_text)

        #print("Address line check:", vendor_words, txt)

        # Detect vendor line
        if vendor_name and any(w in txt for w in vendor_words):
            start_collecting = True
            continue
        #print("  Start collecting:", start_collecting)
        if not start_collecting:
            continue

        has_key = any(k in txt for k in ADDRESS_KEYS)
        #print("  Has address key:", has_key,txt)
        has_pin = re.search(r"\b\d{5,6}\b", txt)
        has_house_no = re.search(r"\b(NO\s*\d+|\d{1,4}[/\-]\d{1,4})\b", txt)

        is_address_like = has_key or has_pin or has_house_no

        # 🟢 Start address only when first valid line appears
        if is_address_like and not address_started:
            address_lines.append(raw_text)
            address_started = True
            continue

        # 🟡 Allow ONE continuation line after address started
        if address_started and len(address_lines) < 2:
            address_lines.append(raw_text)
            break

        # ❌ Ignore junk BEFORE address starts
        if not address_started:
            continue

        break

    return " ".join(address_lines).strip() if address_lines else None

def build_receipt_text(lines):
    return "\n".join(l["text"] for l in lines if l["text"])

def build_llm_prompt(receipt_text: str) -> str:
    valid_categories = list(CATEGORY_ITEMS.keys())
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
            "date": string | null,
            "total_amount": number | null,
            "items": [
                {{"name": string, 
                "quantity": number, 
                "price": number,
                "category":"Classify this item and Pick ONLY one category from:{', '.join(valid_categories)}"
                }}
            ]
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

    raw = re.sub(r"^```json", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^```", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output:\n{raw}")

    json_str = match.group()

    try:
        # Fix invalid numeric values like 2.95S → 2.95
        json_str = match.group()

        json_str = sanitize_numeric_fields(json_str)

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON returned by LLM:\n{json_str}"
        ) from e

def receipt_to_dict(r: ReceiptData) -> dict:
    return {
        "receipt_id": r.receipt_id,
        "vendor_name": r.vendor_name,
        "vendor_address": r.vendor_address,
        "vendor_phone": r.vendor_phone,
        "vendor_gst": r.vendor_gst,
        "date": r.date,
        "time": r.time,
        "subtotal_amount": r.subtotal_amount,
        "tax_amount": r.tax_amount,
        "discount_amount": r.discount_amount,
        "total_amount": r.total_amount,
        "payment_method": r.payment_method,
        "card_last4": r.card_last4,
        "transaction_id": r.transaction_id,
        "items": [
            {
                "name": i.name,
                "quantity": i.quantity,
                "price": i.price
            }
            for i in (r.items or [])
        ]
    }

def getParsedOutput(rawData:str):
    img_name, json_data = rawData.strip().split("\t", 1)
    ocr_lines = json.loads(json_data)

    lines = [normalize_line(l) for l in ocr_lines]
    
    lines.sort(key=lambda x: x["y_min"])
    #print("Sorted lines:", len(lines) , lines)
    img_height = max(l["y_max"] for l in lines)

    receipt = ReceiptData()
    receipt.receipt_id = img_name

    # RULE-BASED
    receipt.vendor_name = extract_vendor_name(lines, img_height)
    receipt.vendor_phone = extract_vendor_phone(lines)
    receipt.vendor_address = extract_address(lines, receipt.vendor_name)
    receipt.time = extract_date_time(lines)
    # LLM ONLY FOR REST
    receipt_text = build_receipt_text(lines)
    llm_data = call_ollama(build_llm_prompt(receipt_text))
    receipt.total_amount = llm_data.get("total_amount")
    receipt.date = llm_data.get("date")
    items_data = llm_data.get("items", [])
    receipt.items = [
        Item(
            name=i.get("name", "").strip(),
            quantity=i.get("quantity", 1),
            price=i.get("price", 0.0),
            category=i.get("category", None)
        )
        for i in items_data
        if i.get("name") and i.get("price") is not None
    ]
    return receipt

# if __name__ == "__main__":
#     output = getParsedOutput("""X51005444041.jpg	[{"transcription": "B.I.G", "points": [[223, 181], [560, 186], [558, 302], [222, 296]]}, {"transcription": "BENS INDEPENDENT GROCER SDN.BHD", "points": [[105, 459], [697, 459], [697, 489], [105, 489]]}, {"transcription": "913144-A)", "points": [[317, 495], [488, 495], [488, 523], [317, 523]]}, {"transcription": "Lot 6,Jalan Batai,", "points": [[270, 530], [535, 530], [535, 559], [270, 559]]}, {"transcription": "Plaza Batai, Damansara Heights", "points": [[169, 564], [634, 564], [634, 594], [169, 594]]}, {"transcription": "50490,Kuala Lumpur", "points": [[241, 596], [560, 600], [559, 630], [241, 626]]}, {"transcription": "T03-20937358F:03-20937359", "points": [[138, 632], [667, 632], [667, 662], [138, 662]]}, {"transcription": "GSTREGNO000243941376)", "points": [[179, 668], [623, 668], [623, 698], [179, 698]]}, {"transcription": "Tax Invoice", "points": [[60, 735], [206, 735], [206, 758], [60, 758]]}, {"transcription": "BAT01201803080169", "points": [[243, 730], [525, 730], [525, 758], [243, 758]]}, {"transcription": "08/03/18", "points": [[625, 728], [749, 728], [749, 758], [625, 758]]}, {"transcription": "Cashier:Sharol N", "points": [[58, 771], [307, 771], [307, 801], [58, 801]]}, {"transcription": "18:20:41", "points": [[623, 769], [749, 769], [749, 799], [623, 799]]}, {"transcription": "Dole Pineapple Pcs", "points": [[56, 835], [296, 835], [296, 871], [56, 871]]}, {"transcription": "8809069300708", "points": [[66, 869], [284, 869], [284, 899], [66, 899]]}, {"transcription": "7.90*3", "points": [[490, 867], [582, 867], [582, 897], [490, 897]]}, {"transcription": "23.70Z", "points": [[632, 867], [747, 867], [747, 897], [632, 897]]}, {"transcription": "Farmhouse Fresh Milk Twin Pack 2x1L", "points": [[58, 929], [537, 929], [537, 959], [58, 959]]}, {"transcription": "9556040440548", "points": [[68, 963], [286, 963], [286, 991], [68, 991]]}, {"transcription": "19.90*1", "points": [[473, 961], [582, 961], [582, 991], [473, 991]]}, {"transcription": "19.90S", "points": [[632, 961], [747, 961], [747, 991], [632, 991]]}, {"transcription": "Fresh Cut Hone", "points": [[54, 1023], [259, 1025], [259, 1055], [53, 1053]]}, {"transcription": "kfruit Peeled 400g", "points": [[317, 1025], [551, 1025], [551, 1055], [317, 1055]]}, {"transcription": "1430018201", "points": [[68, 1057], [235, 1057], [235, 1085], [68, 1085]]}, {"transcription": "8.90*3", "points": [[486, 1055], [582, 1055], [582, 1085], [486, 1085]]}, {"transcription": "26.70Z", "points": [[632, 1055], [747, 1055], [747, 1085], [632, 1085]]}, {"transcription": "Nestle Bliss Yog Drink Strawberry 700g", "points": [[52, 1112], [560, 1117], [559, 1153], [51, 1149]]}, {"transcription": "9556001030290", "points": [[68, 1151], [286, 1151], [286, 1179], [68, 1179]]}, {"transcription": "5.80*1", "points": [[486, 1149], [582, 1149], [582, 1179], [486, 1179]]}, {"transcription": "5.80S", "points": [[646, 1147], [747, 1147], [747, 1179], [646, 1179]]}, {"transcription": "VitagenAssorted 5x125ml", "points": [[58, 1213], [391, 1213], [391, 1243], [58, 1243]]}, {"transcription": "9557305000118", "points": [[68, 1245], [286, 1245], [286, 1275], [68, 1275]]}, {"transcription": "4.90*1", "points": [[486, 1243], [582, 1243], [582, 1273], [486, 1273]]}, {"transcription": "4.90S", "points": [[646, 1241], [747, 1241], [747, 1273], [646, 1273]]}, {"transcription": "Item5", "points": [[53, 1320], [154, 1320], [154, 1352], [53, 1352]]}, {"transcription": "Totawith GST @6%", "points": [[286, 1318], [562, 1318], [562, 1345], [286, 1345]]}, {"transcription": "81.00", "points": [[665, 1320], [747, 1320], [747, 1352], [665, 1352]]}, {"transcription": "Qty9", "points": [[51, 1363], [155, 1358], [157, 1396], [53, 1401]]}, {"transcription": "Rounding", "points": [[439, 1358], [568, 1363], [567, 1399], [438, 1394]]}, {"transcription": "0.00", "points": [[679, 1362], [747, 1362], [747, 1394], [679, 1394]]}, {"transcription": "Total Saving", "points": [[56, 1407], [218, 1407], [218, 1437], [56, 1437]]}, {"transcription": "0.00", "points": [[253, 1407], [317, 1407], [317, 1437], [253, 1437]]}, {"transcription": "Total", "points": [[494, 1405], [566, 1405], [566, 1437], [494, 1437]]}, {"transcription": "81.00", "points": [[665, 1405], [747, 1405], [747, 1437], [665, 1437]]}, {"transcription": "Tender", "points": [[474, 1445], [568, 1450], [567, 1482], [473, 1477]]}, {"transcription": "Pmpcdebit)0012App:578149", "points": [[154, 1495], [566, 1495], [566, 1525], [154, 1525]]}, {"transcription": "81.00", "points": [[667, 1495], [747, 1495], [747, 1525], [667, 1525]]}, {"transcription": "Change", "points": [[466, 1537], [566, 1542], [565, 1574], [464, 1569]]}, {"transcription": "0.00", "points": [[683, 1540], [749, 1540], [749, 1572], [683, 1572]]}, {"transcription": "GST Analysis", "points": [[58, 1589], [230, 1589], [230, 1619], [58, 1619]]}, {"transcription": "Goods", "points": [[290, 1587], [374, 1587], [374, 1619], [290, 1619]]}, {"transcription": "Tax Amount", "points": [[405, 1589], [568, 1589], [568, 1619], [405, 1619]]}, {"transcription": "S=6%", "points": [[82, 1629], [191, 1629], [191, 1666], [82, 1666]]}, {"transcription": "28.86", "points": [[292, 1631], [374, 1631], [374, 1663], [292, 1663]]}, {"transcription": "1.74", "points": [[504, 1629], [568, 1629], [568, 1663], [504, 1663]]}, {"transcription": "Z=0%", "points": [[86, 1678], [189, 1678], [189, 1708], [86, 1708]]}, {"transcription": "50.40", "points": [[294, 1676], [374, 1676], [374, 1708], [294, 1708]]}, {"transcription": "0.00", "points": [[500, 1678], [566, 1678], [566, 1708], [500, 1708]]}, {"transcription": "BIG.COM.MY", "points": [[325, 1745], [490, 1745], [490, 1775], [325, 1775]]}, {"transcription": "FACEBOOK.COM/THEBIGGROUP", "points": [[202, 1777], [611, 1777], [611, 1804], [202, 1804]]}, {"transcription": "EXCHANGE &REFUND MAY BE ALLOWED", "points": [[146, 1836], [669, 1836], [669, 1866], [146, 1866]]}, {"transcription": "WITHIN 3DAYS WITH ORIGINAL TAXINVOICE", "points": [[113, 1868], [704, 1868], [704, 1896], [113, 1896]]}, {"transcription": "THANK YOU,PLEASE COME AGAIN", "points": [[185, 1898], [630, 1898], [630, 1928], [185, 1928]]}]""")
#     print(output)