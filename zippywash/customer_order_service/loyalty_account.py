"""C05 LoyaltyAccount — a customer's loyalty membership (Customer 1 ◇── 0..1 LoyaltyAccount).

Prototype 1: attributes and simple membership methods. Point flows (UC-07) come in Prototype 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from zippywash.common import DomainError, LoyaltyStatus


@dataclass
class LoyaltyAccount:
    loyalty_account_id: str
    point_balance: int
    status: LoyaltyStatus
    enrolled_date: date
    customer_id: str = ""          # implementation reference

    def view_balance(self) -> int:
        return self.point_balance

    def deactivate(self) -> None:
        self.status = LoyaltyStatus.INACTIVE

    def reactivate(self) -> None:
        if self.status == LoyaltyStatus.ACTIVE:
            raise DomainError("This loyalty membership is already active.")
        self.status = LoyaltyStatus.ACTIVE
