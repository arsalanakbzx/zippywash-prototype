"""C22 StockMovement — one recorded change to an InventoryItem's quantity."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from zippywash.common import StockMovementType


@dataclass
class StockMovement:
    stock_movement_id: str
    type: StockMovementType
    quantity: Decimal
    recorded_at: str
    # implementation references
    inventory_item_id: str = ""
    recorded_by_staff_id: str | None = None
