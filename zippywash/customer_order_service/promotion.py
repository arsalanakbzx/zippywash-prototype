"""C14 Promotion — a promo code worth a fixed dollar discount."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from zippywash.common import DomainError, money


@dataclass
class Promotion:
    promotion_id: str
    code: str
    discount_value: Decimal
    active: bool = True

    def validate_eligibility(self) -> None:
        if not self.active:
            raise DomainError(f"Promo code {self.code} has expired.")

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """The discount can never exceed the subtotal it applies to."""
        self.validate_eligibility()
        return money(min(self.discount_value, subtotal))
