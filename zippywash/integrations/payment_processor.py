"""Adapter for the external Payment Processor actor (not a problem-domain class).

The real processor (e.g. Stripe) would sit behind this interface. The prototype uses
MockPaymentProcessor with demo tokens:
  tok_decline...  -> the bank declines        (Payment result FAILED)
  tok_timeout...  -> no answer in time        (Payment result TIMED_OUT)
  any other tok_  -> approved                 (Payment result AUTHORIZED)
No real card numbers or credentials are ever used.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ProcessorOutcome(str, Enum):
    APPROVED = "Approved"
    DECLINED = "Declined"
    TIMEOUT = "Timeout"


@dataclass
class ProcessorResponse:
    outcome: ProcessorOutcome
    message: str = ""


class PaymentProcessor(ABC):
    """Interface every processor adapter implements."""

    @abstractmethod
    def request_authorization(self, payment_id: str, amount: Decimal, token: str) -> ProcessorResponse:
        """Ask the processor once to authorize amount on the tokenized method."""

    @abstractmethod
    def request_refund(self, payment_id: str, amount: Decimal) -> bool:
        """Ask the processor to refund an authorized payment; True when accepted."""


class MockPaymentProcessor(PaymentProcessor):
    def __init__(self):
        self.authorization_calls: list[tuple[str, Decimal, str]] = []
        self.refund_calls: list[tuple[str, Decimal]] = []

    def request_authorization(self, payment_id: str, amount: Decimal, token: str) -> ProcessorResponse:
        self.authorization_calls.append((payment_id, amount, token))
        if amount <= 0:
            return ProcessorResponse(ProcessorOutcome.DECLINED, "Amount must be greater than zero.")
        if token.startswith("tok_decline"):
            return ProcessorResponse(ProcessorOutcome.DECLINED, "The bank declined this card.")
        if token.startswith("tok_timeout"):
            return ProcessorResponse(ProcessorOutcome.TIMEOUT, "The payment service didn't answer in time.")
        return ProcessorResponse(ProcessorOutcome.APPROVED)

    def request_refund(self, payment_id: str, amount: Decimal) -> bool:
        self.refund_calls.append((payment_id, amount))
        return True
