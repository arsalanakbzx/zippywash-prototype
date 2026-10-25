"""C21 InventoryItem — a consumable supply with a reorder level."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class InventoryItem:
    inventory_item_id: str
    name: str
    quantity_on_hand: Decimal
    reorder_level: Decimal

    def check_reorder_level(self) -> bool:
        """True when stock has reached or fallen below the reorder level."""
        return self.quantity_on_hand <= self.reorder_level
