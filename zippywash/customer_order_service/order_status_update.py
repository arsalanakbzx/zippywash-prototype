"""C07 OrderStatusUpdate — one entry in an order's status history (never overwritten)."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import OrderStatus, new_id, now_iso


@dataclass
class OrderStatusUpdate:
    status_update_id: str
    order_id: str
    status: OrderStatus
    changed_at: str
    notes: str | None = None
    recorded_by_staff_id: str | None = None

    @classmethod
    def record_status_change(cls, order_id: str, status: OrderStatus,
                             notes: str | None = None, staff_id: str | None = None) -> "OrderStatusUpdate":
        return cls(new_id("OSU"), order_id, OrderStatus(status), now_iso(), notes or None, staff_id)
