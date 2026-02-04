from dataclasses import dataclass , field
from typing import List, Optional

@dataclass
class Item:
    name: str
    quantity: int = 1
    price: float = 0.0
    category: Optional[str] = None

@dataclass
class ReceiptData:
    # Vendor details
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_phone: Optional[str] = None

    date: Optional[str] = None        
    time: Optional[str] = None        

    # Items
    items: List[Item] = field(default_factory=list)
    total_amount: Optional[float] = None