"""C13 Reward — a loyalty reward that can be redeemed for a fixed discount."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from zippywash.common import DomainError, money


@dataclass
class Reward:
    reward_id: str
    name: str
    points_required: int
    discount_amount: Decimal
    active: bool = True
    expiry_date: date | None = None     # [0..1]

    def validate_eligibility(self, on: date | None = None) -> None:
        on = on or date.today()
        if not self.active:
            raise DomainError(f"Reward '{self.name}' is not available.")
        if self.expiry_date is not None and on > self.expiry_date:
            raise DomainError(f"Reward '{self.name}' expired on {self.expiry_date:%b %d, %Y}.")

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """A reward discount never exceeds the subtotal it applies to."""
        self.validate_eligibility()
        return money(min(self.discount_amount, subtotal))

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
