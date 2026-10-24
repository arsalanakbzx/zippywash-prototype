"""C11 Payment — ONE payment attempt for an order. An order can have several attempts."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from zippywash.common import DomainError, PaymentStatus, new_id, now_iso
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.integrations.payment_processor import PaymentProcessor


@dataclass
class Payment:
    payment_id: str
    order_id: str
    payment_method_id: str
    amount: Decimal
    status: PaymentStatus = PaymentStatus.PENDING
    receipt_number: str | None = None
    created_at: str = ""
    decline_reason: str | None = None   # not persisted; shown to the customer

    @classmethod
    def calculate_total(cls, order_id: str, method: PaymentMethod, amount: Decimal) -> "Payment":
        """Start a new attempt for the order's final amount."""
        return cls(new_id("PAY"), order_id, method.payment_method_id, amount, created_at=now_iso())

    def authorize(self, processor: PaymentProcessor, method: PaymentMethod) -> bool:
        result = processor.authorize(method.token, self.amount)
        self.record_result(result.approved, result.reason)
        return result.approved

    def record_result(self, approved: bool, reason: str | None = None) -> None:
        if approved:
            self.status = PaymentStatus.AUTHORIZED
            self.generate_receipt()
        else:
            self.status = PaymentStatus.DECLINED
            self.decline_reason = reason

    def generate_receipt(self) -> None:
        if self.status != PaymentStatus.AUTHORIZED:
            raise DomainError("Receipts are only issued for successful payments.")
        self.receipt_number = "RCT-" + self.payment_id.split("-")[1]

    def refund(self, processor: PaymentProcessor) -> None:
        if self.status != PaymentStatus.AUTHORIZED:
            raise DomainError("Only an authorized payment can be refunded.")
        processor.refund(self.payment_id, self.amount)
        self.status = PaymentStatus.REFUNDED
