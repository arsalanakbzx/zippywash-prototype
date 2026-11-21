"""InventoryItem — tracks stock quantity and reorder alerts."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, NotificationType, StockMovementType, link

from zippywash.customer_order_service.notification import Notification
from zippywash.operations_resource.stock_movement import StockMovement

if TYPE_CHECKING:
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class InventoryItem(Entity):
    _pk = "inventory_item_id"

    inventory_item_id: str
    name: str
    quantity_on_hand: Decimal
    reorder_level: Decimal
    movements: list[StockMovement] = field(default_factory=list)       # [0..*]
    notifications: list[Notification] = field(default_factory=list)   # [0..*]
    alert_open: bool = False   # technical: a low-stock alert was raised and stock hasn't recovered yet

    def __post_init__(self):
        self.quantity_on_hand = Decimal(str(self.quantity_on_hand))
        self.reorder_level = Decimal(str(self.reorder_level))
        if self.quantity_on_hand < 0 or self.reorder_level < 0:
            raise DomainError("Stock quantities can't be negative.")

    def adjust_quantity(self, movement_type: StockMovementType, quantity: Decimal,
                        recorded_by: StaffMember | None = None) -> StockMovement:
        """Record a ledger movement; raise a low-stock alert when stock reaches the reorder level."""
        movement = StockMovement.record_movement(self, movement_type, quantity, recorded_by)
        if self.check_reorder_level():
            if not self.alert_open:
                self.raise_low_stock_alert()
        else:
            self.alert_open = False      # stock recovered: a future drop raises a new alert
        return movement

    def check_reorder_level(self) -> bool:
        """True when stock is at or below the reorder level."""
        return self.quantity_on_hand <= self.reorder_level

    def raise_low_stock_alert(self) -> Notification:
        """Notify staff once per low-stock episode; while the alert is open the same one is returned."""
        if not self.check_reorder_level():
            raise DomainError(f"{self.name} is above its reorder level.")
        if self.alert_open:
            for n in reversed(self.notifications):
                if n.type == NotificationType.LOW_STOCK:
                    return n
        recipient = next((m.recorded_by for m in reversed(self.movements) if m.recorded_by is not None), None)
        if recipient is None:
            raise DomainError("No staff member to notify about low stock.")
        alert = Notification.create(NotificationType.LOW_STOCK,
                                    f"Low stock: {self.name} is at {self.quantity_on_hand} "
                                    f"(reorder level {self.reorder_level}).", staff_recipient=recipient)
        alert.inventory_item = self
        link(self.notifications, alert)
        alert.send()
        self.alert_open = True
        return alert
