from dataclasses import dataclass , field
from typing import List, Optional

@dataclass
class Item:
    name: str
    quantity: int = 1
    price: float = 0.0

@dataclass
class ReceiptData:
    # Vendor details
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_phone: Optional[str] = None
    vendor_gst: Optional[str] = None

    # Receipt metadata
    receipt_id: Optional[str] = None
    date: Optional[str] = None        # e.g. 2025-01-09
    time: Optional[str] = None        # e.g. 14:35
    currency: str = "INR"

    # Items
    items: List[Item] = field(default_factory=list)

    # Amounts
    subtotal_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    discount_amount: Optional[float] = None
    total_amount: Optional[float] = None

    # Payment details
    payment_method: Optional[str] = None   # Cash / UPI / Card
    card_last4: Optional[str] = None
    transaction_id: Optional[str] = None

    # OCR / system metadata
    confidence_score: Optional[float] = None
    source: str = "mobile_capture"