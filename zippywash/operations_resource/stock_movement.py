"""StockMovement — an immutable inventory ledger entry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, Immutable, StaffRole, StockMovementType, link, new_id, now_local

if TYPE_CHECKING:
    from zippywash.operations_resource.inventory_item import InventoryItem
    from zippywash.operations_resource.staff_member import StaffMember

ADJUSTMENTS = (StockMovementType.ADJUSTMENT_IN, StockMovementType.ADJUSTMENT_OUT)


@dataclass(eq=False, repr=False)
class StockMovement(Immutable, Entity):
    _pk = "stock_movement_id"
    _frozen_fields = ("stock_movement_id", "type", "quantity", "recorded_at", "inventory_item", "recorded_by")

    stock_movement_id: str
    type: StockMovementType
    quantity: Decimal
    recorded_at: datetime
    inventory_item: InventoryItem | None = None     # [1..1]
    recorded_by: StaffMember | None = None          # [0..1]

    def __post_init__(self):
        object.__setattr__(self, "type", StockMovementType(self.type))
        object.__setattr__(self, "quantity", Decimal(str(self.quantity)))

    @staticmethod
    def record_movement(inventory_item: InventoryItem, movement_type: StockMovementType, quantity: Decimal,
                        recorded_by: StaffMember | None = None) -> StockMovement:
        """Create the entry once and apply its signed effect (+ receipt / adjustment in,
        - consumption / adjustment out). Stock never goes negative."""
        movement_type = StockMovementType(movement_type)
        quantity = Decimal(str(quantity))
        if quantity <= 0:
            raise DomainError("Quantity must be greater than zero.")
        if movement_type in ADJUSTMENTS and recorded_by is None:
            raise DomainError("A count adjustment must be recorded by a staff member.")
        if recorded_by is not None and not recorded_by.check_authorization(StaffRole.LAUNDRY_STAFF):
            raise DomainError("Only laundry staff or an administrator can record stock movements.")
        new_qty = inventory_item.quantity_on_hand + movement_type.sign * quantity
        if new_qty < 0:
            raise DomainError(f"Only {inventory_item.quantity_on_hand} {inventory_item.name} in stock.")
        movement = StockMovement(new_id("STM"), movement_type, quantity, now_local(), inventory_item, recorded_by)
        movement.seal()
        inventory_item.quantity_on_hand = new_qty
        inventory_item.movements.append(movement)
        if recorded_by is not None:
            link(recorded_by.stock_movements, movement)
        return movement
