"""Promotion — a code-based discount available to an eligible order."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, OrderStatus, money, today_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.order import Order


@dataclass(eq=False, repr=False)
class Promotion(Entity):
    _pk = "promotion_id"

    promotion_id: str
    code: str
    discount_value: Decimal
    active: bool = True
    expiry_date: date | None = None                     # [0..1]
    orders: list[Order] = field(default_factory=list)   # [0..*]

    def __post_init__(self):
        self.code = (self.code or "").strip().upper()
        self.discount_value = money(self.discount_value)
        if self.discount_value < 0:
            raise DomainError("A promotion discount can't be negative.")

    def ineligibility_reason(self, order: Order) -> str | None:
        if not self.active:
            return f"Promo code {self.code} is no longer active."
        if self.expiry_date is not None and today_local() > self.expiry_date:
            return f"Promo code {self.code} expired on {self.expiry_date:%b %d, %Y}."
        if order.status not in (OrderStatus.DRAFT,):
            return "A promo code can only be added before the order is paid."
        if order.applied_reward is not None:
            return "An order can use a promo code or a loyalty reward, not both."
        if not order.order_items:
            return "Add a service before using a promo code."
        return None

    def validate_eligibility(self, order: Order) -> bool:
        return self.ineligibility_reason(order) is None

    def calculate_discount(self, order: Order) -> Decimal:
        """Fixed-dollar discount, capped so the service subtotal never goes below zero."""
        reason = self.ineligibility_reason(order)
        if reason:
            raise DomainError(reason)
        subtotal = money(sum((i.line_total for i in order.order_items), Decimal("0")))
        return money(min(self.discount_value, subtotal))
