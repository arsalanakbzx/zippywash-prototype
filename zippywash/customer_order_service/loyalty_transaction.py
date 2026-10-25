"""C10 LoyaltyTransaction — one entry in a loyalty account's point history."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import LoyaltyTransactionType


@dataclass
class LoyaltyTransaction:
    transaction_id: str
    type: LoyaltyTransactionType
    points: int
    reason: str | None = None        # [0..1]; required for an Administrator adjustment
    created_at: str = ""
    # implementation references (associations)
    loyalty_account_id: str = ""
    order_id: str | None = None
    payment_id: str | None = None
    reward_id: str | None = None
    loyalty_rule_id: str | None = None
    authorized_by_staff_id: str | None = None
