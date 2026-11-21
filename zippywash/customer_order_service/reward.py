"""Reward — a points-based fixed-dollar discount that can be reserved and redeemed."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, LoyaltyAccountStatus, OrderStatus, money, today_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
    from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
    from zippywash.customer_order_service.order import Order


@dataclass(eq=False, repr=False)
class Reward(Entity):
    _pk = "reward_id"

    reward_id: str
    name: str
    points_required: int
    discount_amount: Decimal
    active: bool = True
    available_from: date | None = None                                   # [0..1]
    expiry_date: date | None = None                                      # [0..1]
    orders: list[Order] = field(default_factory=list)                    # [0..*]
    transactions: list[LoyaltyTransaction] = field(default_factory=list) # [0..*]

    def __post_init__(self):
        self.discount_amount = money(self.discount_amount)
        if not isinstance(self.points_required, int) or self.points_required <= 0:
            raise DomainError("A reward needs a positive number of points.")
        if self.discount_amount < 0:
            raise DomainError("A reward discount can't be negative.")

    def is_available(self, on: date | None = None) -> bool:
        on = on or today_local()
        return (self.active and (self.available_from is None or on >= self.available_from)
                and (self.expiry_date is None or on <= self.expiry_date))

    def ineligibility_reason(self, account: LoyaltyAccount, order: Order) -> str | None:
        """Why this reward can't be used on this order right now (None when it can)."""
        if not self.is_available():
            return "This reward isn't available right now."
        if account is None or account.status != LoyaltyAccountStatus.ACTIVE:
            return "Your loyalty membership isn't active."
        if order.customer is not account.customer:
            return "That order belongs to another customer."
        if order.status not in (OrderStatus.DRAFT, OrderStatus.SCHEDULED):
            return "Rewards can only be used at checkout."
        if order.applied_promotion is not None:
            return "A promo code is already applied. An order can't use both."
        if order.applied_reward is not None and order.applied_reward is not self:
            return "Another reward is already applied to this order."
        # Points already held (or redeemed) for this same order and reward still count toward it.
        usable = account.available_points() + account.points_committed_to(order, self)
        if usable < self.points_required:
            return f"Needs {self.points_required} points. You have {account.available_points()} available."
        return None

    def validate_eligibility(self, account: LoyaltyAccount, order: Order) -> bool:
        return self.ineligibility_reason(account, order) is None

    def schedule_availability(self, start_date: date, expiry_date: date | None = None) -> None:
        if start_date is None:
            raise DomainError("Choose a start date.")
        if expiry_date is not None and expiry_date < start_date:
            raise DomainError("The expiry date can't be before the start date.")
        self.available_from, self.expiry_date = start_date, expiry_date

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
