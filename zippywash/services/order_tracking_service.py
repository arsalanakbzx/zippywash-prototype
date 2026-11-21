"""OrderTrackingService — UC-02: the customer views status (read-only); staff record status changes."""
from __future__ import annotations

from zippywash.common import (DomainError, LoyaltyAccountStatus, NotificationType, OrderStatus, PaymentStatus)
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
from zippywash.database.repository import World
from zippywash.operations_resource.staff_member import StaffMember


class OrderTrackingService:
    def __init__(self, world: World):
        self.world = world

    # ---------------- customer, read-only ----------------
    @staticmethod
    def my_orders(customer: Customer) -> list[Order]:
        return customer.view_order_history()

    @staticmethod
    def order_for(customer: Customer, order_id: str) -> Order:
        """Only the signed-in customer's own placed orders can be opened."""
        for order in customer.view_order_history():
            if order.order_id == order_id:
                return order
        raise DomainError("Order not found.")

    @staticmethod
    def current_status(customer: Customer, order_id: str) -> OrderStatusUpdate:
        return OrderTrackingService.order_for(customer, order_id).get_current_status()

    # ---------------- staff ----------------
    def active_orders(self) -> list[Order]:
        live = [o for o in self.world.all(Order)
                if o.status not in (OrderStatus.DRAFT, OrderStatus.DELIVERED, OrderStatus.CANCELLED)]
        return sorted(live, key=lambda o: o.created_at)

    @staticmethod
    def advance_status(order: Order, staff: StaffMember, notes: str | None = None) -> OrderStatusUpdate:
        """Record the next status. On delivery, the customer earns loyalty points."""
        target = order.next_status()
        if target is None:
            raise DomainError(f"Order {order.order_id} is {order.status.value}; nothing left to update.")
        update = order.update_status(target, staff, notes)
        n = Notification.create(NotificationType.STATUS_CHANGED, f"Order {order.order_id}: {target.value}.",
                                customer_recipient=order.customer)
        n.status_update = update
        update.notifications.append(n)
        n.send()
        account = order.customer.loyalty_account
        if (target == OrderStatus.DELIVERED and account is not None
                and account.status == LoyaltyAccountStatus.ACTIVE):
            try:
                earned = account.award_points(order)
                Notification.create(NotificationType.LOYALTY_UPDATE,
                                    f"You earned {earned.points} points on order {order.order_id}.",
                                    customer_recipient=order.customer).send()
            except DomainError:
                pass   # no active rule or nothing to earn: the delivery itself still counts
        return update

    @staticmethod
    def cancel_order(order: Order, staff: StaffMember | None = None) -> bool:
        """Cancel before pickup: frees both slots, restores held points and refunds the payment."""
        if not order.cancel():
            raise DomainError(f"An order that is {order.status.value} can no longer be cancelled.")
        refunded = None
        for payment in order.payment_attempts:
            if payment.status == PaymentStatus.AUTHORIZED and payment.refund():
                refunded = payment
        account = order.customer.loyalty_account
        if refunded is not None and account is not None:
            try:
                account.reverse_points(refunded)    # gives back points redeemed with this payment
            except DomainError:
                pass
        Notification.create(NotificationType.STATUS_CHANGED,
                            f"Order {order.order_id} was cancelled" + (" and refunded." if refunded else "."),
                            customer_recipient=order.customer).send()
        return True
