"""Notification — records and sends a message to a customer or a staff member."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from zippywash.common import DeliveryStatus, DomainError, Entity, NotificationType, link, new_id, now_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.customer import Customer
    from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
    from zippywash.customer_order_service.payment import Payment
    from zippywash.operations_resource.inventory_item import InventoryItem
    from zippywash.operations_resource.machine import Machine
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class Notification(Entity):
    _pk = "notification_id"

    notification_id: str
    type: NotificationType
    message: str
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    customer_recipient: Customer | None = None          # [0..1]
    staff_recipient: StaffMember | None = None          # [0..1]
    status_update: OrderStatusUpdate | None = None      # [0..1]
    payment: Payment | None = None                      # [0..1]
    machine: Machine | None = None                      # [0..1]
    inventory_item: InventoryItem | None = None         # [0..1]
    created_at: datetime | None = None                  # technical: when it was created

    def __post_init__(self):
        self.type = NotificationType(self.type)
        self.delivery_status = DeliveryStatus(self.delivery_status)

    @staticmethod
    def create(type: NotificationType, message: str, customer_recipient: Customer | None = None,
               staff_recipient: StaffMember | None = None) -> Notification:
        """A notification needs a message and at least one recipient."""
        if not (message or "").strip():
            raise DomainError("A notification needs a message.")
        if customer_recipient is None and staff_recipient is None:
            raise DomainError("A notification needs at least one recipient.")
        n = Notification(new_id("NTF"), NotificationType(type), message.strip(), DeliveryStatus.PENDING,
                         customer_recipient, staff_recipient, created_at=now_local())
        if customer_recipient is not None:
            link(customer_recipient.notifications, n)
        if staff_recipient is not None:
            link(staff_recipient.notifications, n)
        return n

    def _recipient_contacts(self) -> list[str]:
        people = [p for p in (self.customer_recipient, self.staff_recipient) if p is not None]
        return [p.contact_details for p in people if (p.contact_details or "").strip()]

    def send(self) -> DeliveryStatus:
        """Hand the message to the (simulated) notification service. A recipient with no email or
        phone can't be reached, so the honest result is Failed. Sending twice does nothing more."""
        if self.delivery_status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED):
            return self.delivery_status
        self.delivery_status = DeliveryStatus.SENT if self._recipient_contacts() else DeliveryStatus.FAILED
        return self.delivery_status

    def mark_delivered(self) -> None:
        """Confirm delivery of a sent message. Safe to call more than once."""
        if self.delivery_status == DeliveryStatus.DELIVERED:
            return
        if self.delivery_status != DeliveryStatus.SENT:
            raise DomainError("Only a sent notification can be marked delivered.")
        self.delivery_status = DeliveryStatus.DELIVERED
