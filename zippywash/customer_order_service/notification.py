"""C08 Notification — a message to exactly one recipient: a Customer XOR a StaffMember."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import DeliveryStatus, DomainError, NotificationType, new_id, now_iso


@dataclass
class Notification:
    notification_id: str
    type: NotificationType
    message: str
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    customer_id: str | None = None
    staff_member_id: str | None = None
    status_update_id: str | None = None
    inventory_item_id: str | None = None
    created_at: str = ""
    payment_id: str | None = None
    machine_id: str | None = None

    @classmethod
    def create(cls, type: NotificationType, message: str, *, customer_id: str | None = None,
               staff_member_id: str | None = None, status_update_id: str | None = None,
               payment_id: str | None = None) -> "Notification":
        if (customer_id is None) == (staff_member_id is None):
            raise DomainError("A notification needs exactly one recipient: a customer or a staff member.")
        return cls(new_id("NTF"), NotificationType(type), message, DeliveryStatus.PENDING,
                   customer_id, staff_member_id, status_update_id, None, now_iso(), payment_id)

    def send(self) -> None:
        # Prototype: the external Notification Service is simulated; sending marks it Sent.
        self.delivery_status = DeliveryStatus.SENT

    def mark_delivered(self) -> None:
        self.delivery_status = DeliveryStatus.DELIVERED
