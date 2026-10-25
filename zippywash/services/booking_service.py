"""BookingService — coordinates UC-01 (Book Pickup & Delivery) with UC-05 (price + online payment).

Services only orchestrate. Every business rule lives in a domain class method
(Order.calculate_estimate, Order.confirm, TimeSlot.reserve_capacity, Payment.authorize ...).
"""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import BagSize, DomainError, NotificationType, OrderStatus, PickupRequestType, new_id, now_iso
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order, PriceBreakdown
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
from zippywash.customer_order_service.payment import Payment
from zippywash.database.repository import Repository
from zippywash.integrations.payment_processor import MockPaymentProcessor, PaymentProcessor


@dataclass
class BookingResult:
    success: bool
    order: Order
    payment: Payment
    message: str


class BookingService:
    def __init__(self, repo: Repository, processor: PaymentProcessor | None = None):
        self.repo = repo
        self.processor = processor or MockPaymentProcessor()

    # ---------- price preview (no saving) ----------
    def quote(self, customer_id: str, service_type_id: str, bag_size: str,
              promo_code: str | None = None) -> PriceBreakdown:
        preview = Order("PREVIEW", customer_id, BagSize(bag_size), "", "")
        preview.add_item(self._service(service_type_id))
        return preview.calculate_estimate(self._promo(promo_code))

    # ---------- full booking ----------
    def book(self, *, customer_id: str, service_type_id: str, bag_size: str,
             pickup_address_id: str, delivery_address_id: str,
             pickup_slot_id: str, delivery_slot_id: str,
             payment_method_id: str, promo_code: str | None = None) -> BookingResult:
        repo = self.repo
        with repo.conn:   # one transaction: everything is saved, or nothing is
            customer = repo.get_customer(customer_id)
            if customer is None:
                raise DomainError("Customer not found.")
            customer.ensure_can_book()

            pickup, delivery = repo.get_address(pickup_address_id), repo.get_address(delivery_address_id)
            p_slot, d_slot = repo.get_slot(pickup_slot_id), repo.get_slot(delivery_slot_id)
            if None in (pickup, delivery, p_slot, d_slot):
                raise DomainError("Choose a pickup and delivery address and time slot.")
            Order.validate_booking(customer_id, pickup, delivery, p_slot, d_slot)

            order = Order(new_id("ORD"), customer_id, BagSize(bag_size),
                          pickup_address_id, delivery_address_id,
                          pickup_request_type=PickupRequestType.SCHEDULED,
                          pickup_time_slot_id=pickup_slot_id, delivery_time_slot_id=delivery_slot_id,
                          created_at=now_iso())
            order.add_item(self._service(service_type_id))   # the UI books one service per order
            order.calculate_estimate(self._promo(promo_code))
            repo.save_order(order)                      # saved as Draft until payment succeeds
            return self._pay_and_confirm(order, payment_method_id)

    # ---------- retry after a declined payment ----------
    def retry_payment(self, order_id: str, payment_method_id: str) -> BookingResult:
        with self.repo.conn:
            order = self.repo.get_order(order_id)
            if order is None or order.status != OrderStatus.DRAFT:
                raise DomainError("Only an unpaid draft order can be paid again.")
            return self._pay_and_confirm(order, payment_method_id)

    # ---------- shared ----------
    def _pay_and_confirm(self, order: Order, payment_method_id: str) -> BookingResult:
        repo = self.repo
        method = repo.get_payment_method(payment_method_id)
        if method is None:
            raise DomainError("Choose a payment method.")
        method.validate(order.customer_id)

        payment = Payment.create_attempt(order, method)
        approved = payment.authorize(self.processor, method)
        repo.save_payment(payment)

        if not approved:
            self._notify(order.customer_id, NotificationType.PAYMENT_RESULT,
                         f"Payment for order {order.order_id} was declined.", payment_id=payment.payment_id)
            return BookingResult(False, order, payment, payment.decline_reason or "Payment declined.")

        p_slot, d_slot = repo.get_slot(order.pickup_time_slot_id), repo.get_slot(order.delivery_time_slot_id)
        order.confirm(p_slot, d_slot, payment_authorized=True)
        repo.save_slot(p_slot)
        repo.save_slot(d_slot)
        repo.save_order(order)

        update = OrderStatusUpdate.record_status_change(order.order_id, OrderStatus.SCHEDULED,
                                                        "Booked and paid online")
        repo.add_status_update(update)
        order.history.append(update)
        self._notify(order.customer_id, NotificationType.BOOKING_CONFIRMED,
                     f"Order {order.order_id} confirmed. Pickup {p_slot.label()}. "
                     f"Receipt {payment.receipt_number}.", status_update_id=update.status_update_id,
                     payment_id=payment.payment_id)
        return BookingResult(True, order, payment, f"Order {order.order_id} is booked.")

    def _notify(self, customer_id: str, type_: NotificationType, message: str, status_update_id=None,
                payment_id=None):
        n = Notification.create(type_, message, customer_id=customer_id, status_update_id=status_update_id,
                                payment_id=payment_id)
        n.send()
        self.repo.add_notification(n)

    def _service(self, service_type_id: str):
        service = self.repo.get_service_type(service_type_id)
        if service is None:
            raise DomainError("Choose a service.")
        return service

    def _promo(self, code: str | None):
        if not code or not code.strip():
            return None
        promo = self.repo.get_promotion_by_code(code)
        if promo is None:
            raise DomainError(f"Promo code '{code.strip().upper()}' doesn't exist.")
        promo.validate_eligibility()
        return promo
