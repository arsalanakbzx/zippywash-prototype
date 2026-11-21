"""LoyaltyAccount — owns a customer's point balance and lifecycle.

Every balance change is an immutable LoyaltyTransaction. Available points = point balance minus
points held by reservations that have no terminal result yet (redemption or restoration).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from zippywash.common import (DomainError, Entity, LoyaltyAccountStatus, LoyaltyTransactionType, PaymentStatus,
                              StaffRole, link, today_local, unlink)
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction

if TYPE_CHECKING:
    from zippywash.customer_order_service.customer import Customer
    from zippywash.customer_order_service.order import Order
    from zippywash.customer_order_service.payment import Payment
    from zippywash.customer_order_service.reward import Reward
    from zippywash.operations_resource.staff_member import StaffMember

T = LoyaltyTransactionType


@dataclass
class LoyaltySummary:
    """Technical value object returned by view_loyalty_summary()."""
    status: LoyaltyAccountStatus
    point_balance: int
    reserved_points: int
    available_points: int
    enrolled_date: date
    recent_transactions: list[LoyaltyTransaction]


@dataclass(eq=False, repr=False)
class LoyaltyAccount(Entity):
    _pk = "loyalty_account_id"

    loyalty_account_id: str
    customer: Customer | None = None                                        # [1..1]
    point_balance: int = 0
    status: LoyaltyAccountStatus = LoyaltyAccountStatus.INACTIVE
    enrolled_date: date | None = None
    transactions: list[LoyaltyTransaction] = field(default_factory=list)    # [0..*]

    def __post_init__(self):
        self.status = LoyaltyAccountStatus(self.status)
        if self.point_balance < 0:
            raise DomainError("A point balance can't be negative.")

    # =================================================================
    # Ledger helpers
    # =================================================================
    def _closing_entries(self, reservation: LoyaltyTransaction) -> list[LoyaltyTransaction]:
        return [t for t in self.transactions if t.reservation is reservation
                and t.type in (T.REDEMPTION, T.RESTORATION)]

    def is_closed(self, reservation: LoyaltyTransaction) -> bool:
        return bool(self._closing_entries(reservation))

    def is_reversed(self, entry: LoyaltyTransaction) -> bool:
        return any(t.type == T.REVERSAL and t.reverses is entry for t in self.transactions)

    def open_reservations(self, order: Order | None = None, reward: Reward | None = None
                          ) -> list[LoyaltyTransaction]:
        return [t for t in self.transactions if t.type == T.RESERVATION and not self.is_closed(t)
                and (order is None or t.order is order) and (reward is None or t.reward is reward)]

    def reserved_points(self) -> int:
        return sum(t.points for t in self.open_reservations())

    def available_points(self) -> int:
        return self.point_balance - self.reserved_points()

    def points_committed_to(self, order: Order, reward: Reward) -> int:
        """Points already held or redeemed for this order and reward (they still count toward it)."""
        held = sum(t.points for t in self.open_reservations(order, reward))
        redeemed = sum(t.points for t in self.transactions if t.type == T.REDEMPTION
                       and t.order is order and t.reward is reward and not self.is_reversed(t))
        return held + redeemed

    def _ensure_active(self) -> None:
        if self.status != LoyaltyAccountStatus.ACTIVE:
            raise DomainError("This loyalty membership is not active.")

    # =================================================================
    # Milestone 5 operations
    # =================================================================
    def enroll(self) -> LoyaltyTransaction:
        """Join the program: the account becomes ACTIVE and the enrollment is recorded in the ledger."""
        if self.customer is None or not self.customer.is_active():
            raise DomainError("Only an active customer account can join the loyalty program.")
        if any(t.type == T.ENROLLMENT for t in self.transactions):
            raise DomainError("This customer is already enrolled. Reactivate the membership instead.")
        self.status = LoyaltyAccountStatus.ACTIVE
        self.enrolled_date = today_local()
        entry = LoyaltyTransaction.create(T.ENROLLMENT, 0, self)
        entry.set_context(reason="Joined the loyalty program")
        entry.post()
        return entry

    def reactivate(self) -> None:
        if self.status == LoyaltyAccountStatus.ACTIVE:
            raise DomainError("This loyalty membership is already active.")
        if self.customer is None or not self.customer.is_active():
            raise DomainError("Reactivate the customer account first.")
        self.status = LoyaltyAccountStatus.ACTIVE

    def view_loyalty_summary(self) -> LoyaltySummary:
        recent = sorted(self.transactions, key=lambda t: t.created_at, reverse=True)[:10]
        return LoyaltySummary(self.status, self.point_balance, self.reserved_points(), self.available_points(),
                              self.enrolled_date, recent)

    def award_points(self, order: Order) -> LoyaltyTransaction:
        """Earn points once per order, from the amount actually paid, using the active LoyaltyRule."""
        self._ensure_active()
        if order.customer is not self.customer:
            raise DomainError("That order belongs to another customer.")
        payment = order.authorized_payment()
        if payment is None or payment.status != PaymentStatus.AUTHORIZED:
            raise DomainError("Points are only earned on a paid order.")
        if any(t.type == T.EARN and t.order is order and not self.is_reversed(t) for t in self.transactions):
            raise DomainError("Points for this order were already awarded.")
        rule = LoyaltyRule.current_rule()
        if rule is None:
            raise DomainError("No loyalty rule is active.")
        points = rule.calculate_points(order)
        if points <= 0:
            raise DomainError("This order doesn't earn any points.")
        entry = LoyaltyTransaction.create(T.EARN, points, self, order=order)
        entry.set_context(applied_rule=rule, payment=payment, reason=f"Earned on order {order.order_id}")
        entry.post()
        return entry

    def correct_points(self, points: int, reason: str, authorized_by: StaffMember) -> LoyaltyTransaction:
        """Administrator correction with a written reason (positive adds, negative removes)."""
        if authorized_by is None or not authorized_by.check_authorization(StaffRole.ADMINISTRATOR):
            raise DomainError("Only an administrator can correct loyalty points.")
        if not (reason or "").strip():
            raise DomainError("A correction needs a reason.")
        if not isinstance(points, int) or points == 0:
            raise DomainError("Enter a whole, non-zero number of points.")
        if self.point_balance + points < self.reserved_points():
            raise DomainError("A correction can't take the balance below the points on hold.")
        entry = LoyaltyTransaction.create(T.CORRECTION, points, self)
        entry.set_context(reason=reason.strip(), authorized_by=authorized_by)
        entry.post()
        return entry

    def reserve_points(self, reward: Reward, order: Order) -> LoyaltyTransaction:
        """M5-C04. Hold the reward's points for this checkout. pointBalance does NOT change here;
        payment success later calls redeem_points, failure or cancellation calls restore_points."""
        # 1. Preconditions
        self._ensure_active()
        if reward is None or order is None:
            raise DomainError("Choose a reward for this order.")
        if order.customer is not self.customer:
            raise DomainError("That order belongs to another customer.")
        if order.applied_promotion is not None:
            raise DomainError("An order can use a promo code or a loyalty reward, not both.")
        if order.applied_reward is not None and order.applied_reward is not reward:
            raise DomainError("Another reward is already applied to this order.")
        if self.open_reservations(order=order, reward=reward):
            raise DomainError("This reward is already reserved for this order.")
        if not reward.validate_eligibility(self, order):
            raise DomainError(reward.ineligibility_reason(self, order) or "This reward can't be used here.")
        # 2. Available points = balance - unmatched reservations
        if self.available_points() < reward.points_required:
            raise DomainError("You don't have enough available points for this reward.")
        # 3. One reservation entry: create, validate, post
        reservation = LoyaltyTransaction.create(T.RESERVATION, reward.points_required, self, reward, order)
        if not reservation.validate():
            raise DomainError("The reservation is not valid.")
        reservation.post()
        order.applied_reward = reward
        order.applied_promotion = None
        link(reward.orders, order)
        return reservation

    def redeem_points(self, reservation: LoyaltyTransaction, payment: Payment) -> LoyaltyTransaction:
        """After an AUTHORIZED payment: turn the hold into a permanent deduction, exactly once."""
        self._check_reservation(reservation)
        if payment is None or payment.status != PaymentStatus.AUTHORIZED:
            raise DomainError("Points are redeemed only after the payment is authorized.")
        if payment.order is not reservation.order:
            raise DomainError("That payment is for a different order.")
        entry = LoyaltyTransaction.create(T.REDEMPTION, reservation.points, self, reservation.reward,
                                          reservation.order)
        entry.set_context(reservation=reservation, payment=payment,
                          reason=f"Redeemed '{reservation.reward.name}'")
        entry.post()
        return entry

    def restore_points(self, reservation: LoyaltyTransaction) -> LoyaltyTransaction:
        """After a failed/timed-out payment or a cancelled checkout: release the hold, exactly once,
        and take the reward off the order."""
        self._check_reservation(reservation)
        entry = LoyaltyTransaction.create(T.RESTORATION, reservation.points, self, reservation.reward,
                                          reservation.order)
        entry.set_context(reservation=reservation, reason=f"Released '{reservation.reward.name}'")
        entry.post()
        order = reservation.order
        if order is not None and order.applied_reward is reservation.reward:
            order.applied_reward = None
            unlink(reservation.reward.orders, order)
        return entry

    def _check_reservation(self, reservation: LoyaltyTransaction) -> None:
        if reservation is None or reservation.type != T.RESERVATION or reservation.loyalty_account is not self:
            raise DomainError("That is not a reservation on this account.")
        if self.is_closed(reservation):
            raise DomainError("This reservation was already redeemed or restored.")

    def reverse_points(self, payment: Payment) -> LoyaltyTransaction:
        """After a refund: reverse the points earned with this payment (and give back points redeemed
        with it). Returns the reversal of the earned points when there was one."""
        targets = [t for t in self.transactions if t.payment is payment and t.posted
                   and t.type in (T.EARN, T.REDEMPTION) and not self.is_reversed(t)]
        if not targets:
            raise DomainError("No points to reverse for this payment.")
        targets.sort(key=lambda t: t.type != T.EARN)     # earned points first
        reversals = [t.reverse() for t in targets]
        return reversals[0]

    def deactivate(self) -> LoyaltyTransaction | None:
        """Close the membership. Any points still on hold are released; returns that restoration."""
        if self.status != LoyaltyAccountStatus.ACTIVE:
            raise DomainError("This loyalty membership is already inactive.")
        last = None
        for reservation in self.open_reservations():
            last = self.restore_points(reservation)
        self.status = LoyaltyAccountStatus.INACTIVE
        return last
