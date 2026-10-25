"""OrderTrackingService — UC-02 (Track & Update Order Status), plus customer cancellation."""
from __future__ import annotations

from zippywash.common import DomainError, NotificationType, OrderStatus, PaymentStatus, StaffRole
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
from zippywash.database.repository import Repository
from zippywash.integrations.payment_processor import MockPaymentProcessor, PaymentProcessor

# Who is allowed to record each status (role-based access from the use-case diagram).
# Administrators can record any status.
ROLE_FOR_STATUS = {
    OrderStatus.PICKED_UP: StaffRole.DRIVER,
    OrderStatus.WAITING_FOR_WASH: StaffRole.LAUNDRY_STAFF,
    OrderStatus.WASHING: StaffRole.LAUNDRY_STAFF,
    OrderStatus.READY_FOR_PICKUP: StaffRole.LAUNDRY_STAFF,
    OrderStatus.OUT_FOR_DELIVERY: StaffRole.DRIVER,
    OrderStatus.DELIVERED: StaffRole.DRIVER,
}


class OrderTrackingService:
    def __init__(self, repo: Repository, processor: PaymentProcessor | None = None):
        self.repo = repo
        self.processor = processor or MockPaymentProcessor()

    def advance_status(self, order_id: str, staff_id: str, notes: str | None = None) -> Order:
        repo = self.repo
        with repo.conn:
            order, staff = repo.get_order(order_id), repo.get_staff(staff_id)
            if order is None or staff is None:
                raise DomainError("Order or staff member not found.")
            target = order.next_status()
            if target is None:
                raise DomainError(f"Order {order_id} is {order.status.value}; nothing left to update.")
            needed = ROLE_FOR_STATUS[target]
            if not staff.check_authorization(needed):
                raise DomainError(f"Only a {needed.value} can mark an order '{target.value}'.")

            order.update_status(target)
            repo.save_order(order)
            update = OrderStatusUpdate.record_status_change(order_id, target, notes, staff_id)
            repo.add_status_update(update)
            order.history.append(update)

            n = Notification.create(NotificationType.STATUS_CHANGED,
                                    f"Order {order_id}: {target.value}.",
                                    customer_id=order.customer_id, status_update_id=update.status_update_id)
            n.send()
            repo.add_notification(n)
            return order

    def cancel_order(self, order_id: str, customer_id: str) -> Order:
        repo = self.repo
        with repo.conn:
            order = repo.get_order(order_id)
            if order is None or order.customer_id != customer_id:
                raise DomainError("Order not found.")
            p_slot, d_slot = repo.get_slot(order.pickup_time_slot_id), repo.get_slot(order.delivery_time_slot_id)
            order.cancel(p_slot, d_slot)
            repo.save_slot(p_slot)
            repo.save_slot(d_slot)
            repo.save_order(order)

            refunded = None
            for payment in repo.list_payments(order_id):
                if payment.status == PaymentStatus.AUTHORIZED:
                    payment.refund(self.processor)
                    repo.save_payment(payment)
                    refunded = payment

            update = OrderStatusUpdate.record_status_change(
                order_id, OrderStatus.CANCELLED,
                f"Cancelled by customer; refund {refunded.receipt_number}" if refunded else "Cancelled by customer")
            repo.add_status_update(update)
            order.history.append(update)
            n = Notification.create(NotificationType.STATUS_CHANGED,
                                    f"Order {order_id} was cancelled and refunded.",
                                    customer_id=customer_id, status_update_id=update.status_update_id)
            n.send()
            repo.add_notification(n)
            return order
