"""C14 Promotion — a promo code worth a fixed dollar discount."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from zippywash.common import DomainError, money


@dataclass
class Promotion:
    promotion_id: str
    code: str
    discount_value: Decimal
    active: bool = True
    expiry_date: date | None = None   # [0..1]

    def validate_eligibility(self, on: date | None = None) -> None:
        on = on or date.today()
        if not self.active:
            raise DomainError(f"Promo code {self.code} has expired.")
        if self.expiry_date is not None and on > self.expiry_date:
            raise DomainError(f"Promo code {self.code} expired on {self.expiry_date:%b %d, %Y}.")

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """The discount can never exceed the subtotal it applies to."""
        self.validate_eligibility()
        return money(min(self.discount_value, subtotal))
