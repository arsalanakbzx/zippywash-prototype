"""LoyaltyRule — the active points-earning formula."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING, ClassVar

from zippywash.common import DomainError, Entity, PaymentStatus, today_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
    from zippywash.customer_order_service.order import Order


@dataclass(eq=False, repr=False)
class LoyaltyRule(Entity):
    _pk = "loyalty_rule_id"
    # Technical registry: the rules currently loaded, so award_points(order) can find the active one.
    registry: ClassVar[list] = []

    loyalty_rule_id: str
    points_per_dollar: Decimal
    effective_from: date
    active: bool = True
    transactions: list[LoyaltyTransaction] = field(default_factory=list)   # [0..*]

    def __post_init__(self):
        self.points_per_dollar = Decimal(str(self.points_per_dollar))

    @classmethod
    def register(cls, rules: list[LoyaltyRule]) -> None:
        cls.registry = list(rules)

    @classmethod
    def current_rule(cls, on: date | None = None) -> LoyaltyRule | None:
        on = on or today_local()
        valid = [r for r in cls.registry if r.active and r.validate() and r.effective_from <= on]
        return max(valid, key=lambda r: r.effective_from) if valid else None

    def validate(self) -> bool:
        return self.points_per_dollar > 0 and self.effective_from is not None

    def calculate_points(self, order: Order) -> int:
        """Whole points from the amount actually paid (partial points are dropped)."""
        if not self.active or not self.validate():
            return 0
        paid = [p for p in order.payment_attempts if p.status == PaymentStatus.AUTHORIZED]
        if not paid:
            return 0
        return int((paid[-1].amount * self.points_per_dollar).to_integral_value(rounding=ROUND_DOWN))

    def activate(self) -> None:
        if not self.validate():
            raise DomainError("A rule needs a positive earning rate and an effective date.")
        self.active = True

    def deactivate(self) -> None:
        self.active = False
