"""BookingService — UC-01 booking with UC-05 payment and UC-07 reward redemption at checkout.

Services only orchestrate: they call domain methods in the right order inside one unit of work.
Every business rule lives in the domain classes.

Standard booking (handoff 8.1):
  details -> time slots -> calculate_estimate -> Payment.create_attempt -> authorize -> record_result
  -> AUTHORIZED: reserve both slots + confirm (Scheduled) + receipt + notification
  -> FAILED / TIMED_OUT: order stays Draft, no slot capacity used
Reward booking (handoff 8.2): reserve_points before payment (balance unchanged);
  AUTHORIZED -> redeem_points once; FAILED / TIMED_OUT / cancelled -> restore_points once.
"""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import (BagSize, DomainError, NotificationType, OrderStatus, PaymentStatus,
                              PickupRequestType)
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.payment import Payment
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.repository import World


@dataclass
class PaymentOutcome:
    authorized: bool
    payment: Payment
    message: str
    redeemed: LoyaltyTransaction | None = None
    restored: LoyaltyTransaction | None = None


class BookingService:
    def __init__(self, world: World):
        self.world = world

    # ---------------- WF01 booking details ----------------
    def start_booking(self, customer: Customer, pickup_address: Address, delivery_address: Address,
                      service_type: ServiceType, bag_size: BagSize,
                      pickup_request_type: PickupRequestType = PickupRequestType.SCHEDULED) -> Order:
        """Create a Draft order. Any older unfinished checkout of this customer is closed first,
        so points held for it are released."""
        for old in list(customer.orders):
            if old.status == OrderStatus.DRAFT:
                old.cancel()
        return Order.start(customer, pickup_address, delivery_address, service_type, bag_size,
                           pickup_request_type=pickup_request_type)

    # ---------------- WF02 time slots ----------------
    def open_slots(self, now) -> list[TimeSlot]:
        slots = [s for s in self.world.all(TimeSlot) if not s.has_started(now) and s.check_capacity(1)]
        return sorted(slots, key=lambda s: s.starts_at())

    def choose_slots(self, order: Order, pickup_slot: TimeSlot, delivery_slot: TimeSlot) -> None:
        order.select_time_slots(pickup_slot, delivery_slot)
        order.calculate_estimate()

    # ---------------- WF03 review: promo code ----------------
    def apply_promo_code(self, order: Order, code: str) -> Promotion:
        code = (code or "").strip().upper()
        promo = next((p for p in self.world.all(Promotion) if p.code == code), None)
        if promo is None:
            raise DomainError(f"Promo code '{code}' doesn't exist.")
        order.apply_promotion(promo)
        try:
            order.calculate_estimate()
        except DomainError:
            order.apply_promotion(None)
            order.calculate_estimate()
            raise
        return promo

    def remove_promo_code(self, order: Order) -> None:
        order.apply_promotion(None)
        order.calculate_estimate()

    # ---------------- UC07 WF01/WF02 rewards ----------------
    def reward_options(self, order: Order) -> list[tuple[Reward, str | None]]:
        """Every active reward with the reason it can't be used (None when it can)."""
        account = order.customer.loyalty_account
        options = []
        for reward in sorted(self.world.all(Reward), key=lambda r: r.points_required):
            if not reward.active:
                continue
            reason = ("Join the loyalty program to use rewards." if account is None
                      else reward.ineligibility_reason(account, order))
            options.append((reward, reason))
        return options

    def reserve_reward(self, order: Order, reward: Reward) -> LoyaltyTransaction:
        account = order.customer.loyalty_account
        if account is None:
            raise DomainError("Join the loyalty program to use rewards.")
        reservation = account.reserve_points(reward, order)
        order.calculate_estimate()
        return reservation

    def release_reward(self, order: Order) -> LoyaltyTransaction | None:
        """Cancel the reward at checkout: points restored, reward removed, original total back."""
        account = order.customer.loyalty_account
        restored = None
        if account is not None:
            for reservation in account.open_reservations(order=order):
                restored = account.restore_points(reservation)
        order.calculate_estimate()
        return restored

    # ---------------- WF04 payment ----------------
    def pay(self, order: Order, payment_method: PaymentMethod) -> PaymentOutcome:
        if order.status != OrderStatus.DRAFT:
            raise DomainError("This order is already paid.")
        if payment_method is None or payment_method.customer is not order.customer:
            raise DomainError("Choose one of your saved payment methods.")
        order.calculate_estimate()
        account = order.customer.loyalty_account
        reservation = None
        if account is not None and order.applied_reward is not None:
            held = account.open_reservations(order=order, reward=order.applied_reward)
            reservation = held[0] if held else None

        payment = Payment.create_attempt(order, order.estimated_total, payment_method)
        result = payment.authorize()              # one processor call; status unchanged
        payment.record_result(result)            # the service records the outcome

        if result != PaymentStatus.AUTHORIZED:
            restored = account.restore_points(reservation) if reservation is not None else None
            order.calculate_estimate()            # back to the original total when a reward was released
            self._notify(order, NotificationType.PAYMENT_RESULT,
                         f"Payment for order {order.order_id} was not authorized. Your booking isn't confirmed.",
                         payment=payment)
            reason = payment.failure_reason or "Payment was not authorized."
            if result == PaymentStatus.TIMED_OUT:
                reason = "The payment service didn't answer in time. You weren't charged."
            return PaymentOutcome(False, payment, reason, restored=restored)

        # Authorized: make sure both slots still have room before using any points.
        if not (order.pickup_time_slot.check_capacity(1) and order.delivery_time_slot.check_capacity(1)):
            payment.refund()
            restored = account.restore_points(reservation) if reservation is not None else None
            order.calculate_estimate()
            return PaymentOutcome(False, payment, "A time slot filled up while you were paying. The payment was "
                                                  "refunded and your booking isn't confirmed. Choose another time.",
                                  restored=restored)
        redeemed = account.redeem_points(reservation, payment) if reservation is not None else None
        order.confirm()                            # reserves both slots, status Scheduled
        receipt = payment.generate_receipt()
        update = order.get_current_status()
        n = self._notify(order, NotificationType.BOOKING_CONFIRMED,
                         f"Order {order.order_id} confirmed. Pickup {order.pickup_time_slot.label()}. "
                         f"Receipt {receipt}.", payment=payment)
        n.status_update = update
        update.notifications.append(n)
        return PaymentOutcome(True, payment, f"Order {order.order_id} is booked.", redeemed=redeemed)

    def cancel_checkout(self, order: Order) -> LoyaltyTransaction | None:
        """Leave checkout without paying: release reserved points and close the draft."""
        restored = self.release_reward(order)
        order.cancel()
        return restored

    # ---------------- helpers ----------------
    @staticmethod
    def _notify(order: Order, type_: NotificationType, message: str, payment: Payment | None = None
                ) -> Notification:
        n = Notification.create(type_, message, customer_recipient=order.customer)
        if payment is not None:
            n.payment = payment
            payment.notifications.append(n)
        n.send()
        return n
