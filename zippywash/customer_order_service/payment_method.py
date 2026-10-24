"""C12 PaymentMethod — a saved, tokenized payment method. No card numbers are stored."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import DomainError


@dataclass
class PaymentMethod:
    payment_method_id: str
    customer_id: str
    token: str
    type: str
    label: str
    active: bool = True

    def validate(self, customer_id: str) -> None:
        if self.customer_id != customer_id:
            raise DomainError("That payment method belongs to another customer.")
        if not self.active:
            raise DomainError(f"{self.label} is no longer active.")
