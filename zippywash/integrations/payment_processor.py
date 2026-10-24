"""Adapter for the external Payment Processor actor.

The real processor (e.g. Stripe) sits behind this interface. The prototype uses
MockPaymentProcessor: any token starting with "tok_decline" is declined, so the
demo can show a failed attempt followed by a successful retry.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class AuthorizationResult:
    approved: bool
    reason: str | None = None


class PaymentProcessor:
    def authorize(self, token: str, amount: Decimal) -> AuthorizationResult:
        raise NotImplementedError

    def refund(self, payment_id: str, amount: Decimal) -> None:
        raise NotImplementedError


class MockPaymentProcessor(PaymentProcessor):
    def authorize(self, token: str, amount: Decimal) -> AuthorizationResult:
        if amount <= 0:
            return AuthorizationResult(False, "Amount must be greater than zero.")
        if token.startswith("tok_decline"):
            return AuthorizationResult(False, "Card declined by the bank. Try another payment method.")
        return AuthorizationResult(True)

    def refund(self, payment_id: str, amount: Decimal) -> None:
        return None
