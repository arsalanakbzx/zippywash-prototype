"""LoyaltyTransaction — an immutable loyalty ledger entry.

Effect on the point balance when posted:
  ENROLLMENT 0 · EARN +points · CORRECTION +/-points · RESERVATION 0 (a hold) ·
  REDEMPTION -points · RESTORATION 0 (releases a hold) · REVERSAL undoes the entry it reverses.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, Immutable, LoyaltyTransactionType, link, new_id, now_local

if TYPE_CHECKING:
    from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
    from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
    from zippywash.customer_order_service.order import Order
    from zippywash.customer_order_service.payment import Payment
    from zippywash.customer_order_service.reward import Reward
    from zippywash.operations_resource.staff_member import StaffMember

T = LoyaltyTransactionType
TERMINAL = (T.REDEMPTION, T.RESTORATION, T.REVERSAL)


@dataclass(eq=False, repr=False)
class LoyaltyTransaction(Immutable, Entity):
    _pk = "transaction_id"
    _frozen_fields = ("transaction_id", "type", "points", "reason", "created_at", "loyalty_account", "order",
                      "reward", "applied_rule", "payment", "authorized_by", "reservation", "reverses")

    transaction_id: str
    type: LoyaltyTransactionType
    points: int
    created_at: datetime
    loyalty_account: LoyaltyAccount | None = None   # [1..1]
    reason: str | None = None                       # [0..1]
    order: Order | None = None                      # [0..1]
    reward: Reward | None = None                    # [0..1]
    applied_rule: LoyaltyRule | None = None         # [0..1]
    payment: Payment | None = None                  # [0..1]
    authorized_by: StaffMember | None = None        # [0..1]
    # Technical links kept in the ledger: which reservation a redemption/restoration closes,
    # and which entry a reversal cancels.
    reservation: LoyaltyTransaction | None = None
    reverses: LoyaltyTransaction | None = None
    posted: bool = False

    def __post_init__(self):
        object.__setattr__(self, "type", LoyaltyTransactionType(self.type))

    # ---------------- helpers ----------------
    def balance_effect(self) -> int:
        if self.type in (T.EARN, T.CORRECTION):
            return self.points
        if self.type == T.REDEMPTION:
            return -self.points
        if self.type == T.REVERSAL and self.reverses is not None:
            return -self.reverses.balance_effect()
        return 0

    def set_context(self, **links) -> None:
        """Fill optional references before posting (payment, rule, staff, reason, reservation)."""
        if self.posted:
            raise DomainError("A posted loyalty entry can't be changed.")
        for name, value in links.items():
            object.__setattr__(self, name, value)

    # ---------------- Milestone 5 operations ----------------
    @staticmethod
    def create(type: LoyaltyTransactionType, points: int, account: LoyaltyAccount, reward: Reward | None = None,
               order: Order | None = None) -> LoyaltyTransaction:
        return LoyaltyTransaction(new_id("LTX"), LoyaltyTransactionType(type), points, now_local(), account,
                                  order=order, reward=reward)

    def validate(self) -> bool:
        """Check the entry before it is posted."""
        if self.loyalty_account is None or not isinstance(self.points, int) or isinstance(self.points, bool):
            return False
        if self.type == T.ENROLLMENT:
            return self.points == 0
        if self.type == T.CORRECTION:
            return (self.points != 0 and bool((self.reason or "").strip()) and self.authorized_by is not None
                    and self.loyalty_account.point_balance + self.points >= self.loyalty_account.reserved_points())
        if self.points <= 0:
            return False
        if self.type == T.EARN:
            return self.order is not None and self.applied_rule is not None
        if self.type == T.RESERVATION:
            return (self.reward is not None and self.order is not None
                    and self.points == self.reward.points_required)
        if self.type in (T.REDEMPTION, T.RESTORATION):
            r = self.reservation
            return (r is not None and r.type == T.RESERVATION and r.loyalty_account is self.loyalty_account
                    and r.points == self.points and not self.loyalty_account.is_closed(r)
                    and (self.type == T.RESTORATION or self.payment is not None))
        if self.type == T.REVERSAL:
            o = self.reverses
            return (o is not None and o.posted and o.type in (T.EARN, T.REDEMPTION, T.CORRECTION)
                    and o.points == self.points and not self.loyalty_account.is_reversed(o))
        return False

    def post(self) -> None:
        """Apply the entry to the account once and attach it to every related object."""
        if self.posted:
            raise DomainError("This loyalty entry is already posted.")
        if not self.validate():
            raise DomainError("This loyalty entry is not valid and was not posted.")
        account = self.loyalty_account
        new_balance = account.point_balance + self.balance_effect()
        if new_balance < 0:
            raise DomainError("The point balance can't go below zero.")
        account.point_balance = new_balance
        object.__setattr__(self, "posted", True)
        self.seal()
        link(account.transactions, self)
        for owner, attr in ((self.order, "loyalty_transactions"), (self.reward, "transactions"),
                            (self.applied_rule, "transactions"), (self.payment, "loyalty_transactions"),
                            (self.authorized_by, "authorized_loyalty_transactions")):
            if owner is not None:
                link(getattr(owner, attr), self)

    def reverse(self) -> LoyaltyTransaction:
        """Cancel this posted entry with a new opposite REVERSAL entry (history is never edited)."""
        if not self.posted:
            raise DomainError("Only a posted entry can be reversed.")
        if self.type not in (T.EARN, T.REDEMPTION, T.CORRECTION):
            raise DomainError(f"A {self.type.value} entry can't be reversed.")
        if self.loyalty_account.is_reversed(self):
            raise DomainError("This entry was already reversed.")
        reversal = LoyaltyTransaction(new_id("LTX"), T.REVERSAL, self.points, now_local(), self.loyalty_account,
                                      reason=f"Reverses {self.type.value.lower()} {self.transaction_id}",
                                      order=self.order, payment=self.payment, reverses=self)
        reversal.post()
        return reversal
