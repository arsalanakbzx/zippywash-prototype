"""OrderStatusUpdate — an immutable audit entry for one order status change."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, Immutable, OrderStatus, link, new_id, now_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.notification import Notification
    from zippywash.customer_order_service.order import Order
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class OrderStatusUpdate(Immutable, Entity):
    _pk = "status_update_id"
    _frozen_fields = ("status_update_id", "status", "changed_at", "notes", "order", "recorded_by")

    status_update_id: str
    status: OrderStatus
    changed_at: datetime
    order: Order | None = None                                      # [1..1]
    notes: str | None = None                                        # [0..1]
    recorded_by: StaffMember | None = None                          # [0..1]
    notifications: list[Notification] = field(default_factory=list) # [0..*]

    def __post_init__(self):
        object.__setattr__(self, "status", OrderStatus(self.status))

    @staticmethod
    def record_status_change(order: Order, new_status: OrderStatus, recorded_by: StaffMember | None = None,
                             notes: str | None = None) -> OrderStatusUpdate:
        """Validate the transition, create exactly one timestamped entry, append it to the order's
        history and move the order to the new status. Older entries are never edited."""
        new_status = OrderStatus(new_status)
        order.check_transition(new_status, recorded_by)
        update = OrderStatusUpdate(new_id("OSU"), new_status, now_local(), order,
                                   (notes or "").strip() or None, recorded_by)
        update.seal()
        order.status_history.append(update)
        order.status = new_status
        if recorded_by is not None:
            link(recorded_by.status_updates, update)
        return update
