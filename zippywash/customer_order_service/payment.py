"""Payment — one payment attempt for an order. An order can have several attempts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

from zippywash.common import DomainError, Entity, PaymentStatus, link, money, new_id, now_local
from zippywash.integrations.payment_processor import MockPaymentProcessor, PaymentProcessor, ProcessorOutcome

if TYPE_CHECKING:
    from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
    from zippywash.customer_order_service.notification import Notification
    from zippywash.customer_order_service.order import Order
    from zippywash.customer_order_service.payment_method import PaymentMethod

RESULTS = (PaymentStatus.AUTHORIZED, PaymentStatus.FAILED, PaymentStatus.TIMED_OUT)


@dataclass(eq=False, repr=False)
class Payment(Entity):
    _pk = "payment_id"

    payment_id: str
    amount: Decimal
    order: Order | None = None                                           # [1..1]
    payment_method: PaymentMethod | None = None                          # [1..1]
    status: PaymentStatus = PaymentStatus.PENDING
    receipt_number: str | None = None                                    # [0..1]
    loyalty_transactions: list[LoyaltyTransaction] = field(default_factory=list)   # [0..*]
    notifications: list[Notification] = field(default_factory=list)                # [0..*]
    created_at: datetime | None = None          # technical
    failure_reason: str | None = None           # technical, not saved: shown to the customer

    def __post_init__(self):
        self.amount = money(self.amount)
        self.status = PaymentStatus(self.status)

    # ---------- processor configuration (technical) ----------
    # The external processor adapter is configured once, so authorize() keeps the
    # argument-free signature from Milestone 5.
    _processor_adapter: ClassVar[PaymentProcessor] = MockPaymentProcessor()

    @classmethod
    def configure_processor(cls, processor: PaymentProcessor) -> None:
        cls._processor_adapter = processor

    def _processor(self) -> PaymentProcessor:
        return type(self)._processor_adapter

    # ---------- Milestone 5 operations ----------
    @staticmethod
    def create_attempt(order: Order, amount: Decimal, payment_method: PaymentMethod) -> Payment:
        """Create a PENDING attempt for the given amount with the customer's own payment method."""
        amount = money(amount)
        if order is None or payment_method is None:
            raise DomainError("A payment needs an order and a payment method.")
        if amount <= 0:
            raise DomainError("The payment amount must be greater than zero.")
        if payment_method.customer is not order.customer:
            raise DomainError("That payment method belongs to another customer.")
        payment = Payment(new_id("PAY"), amount, order, payment_method, created_at=now_local())
        link(order.payment_attempts, payment)
        link(payment_method.payments, payment)
        return payment

    def authorize(self) -> PaymentStatus:
        """M5-C03. Ask the processor once to authorize the stored amount with the stored token.

        Returns AUTHORIZED, FAILED or TIMED_OUT. Does NOT change self.status: the caller then calls
        record_result(result). Never confirms the order, redeems points or issues a receipt."""
        self.failure_reason = None
        if (self.order is None or self.payment_method is None or self.amount <= 0
                or self.status != PaymentStatus.PENDING):
            self.failure_reason = "This payment attempt can't be authorized."
            return PaymentStatus.FAILED
        if not self.payment_method.validate() or self.payment_method.customer is not self.order.customer:
            self.failure_reason = "This payment method can't be used. Choose another one."
            return PaymentStatus.FAILED
        response = self._processor().request_authorization(self.payment_id, self.amount,
                                                           self.payment_method.token)
        if response.outcome == ProcessorOutcome.APPROVED:
            return PaymentStatus.AUTHORIZED
        self.failure_reason = response.message or "Payment was not authorized."
        if response.outcome == ProcessorOutcome.TIMEOUT:
            return PaymentStatus.TIMED_OUT
        return PaymentStatus.FAILED

    def record_result(self, result: PaymentStatus) -> None:
        """Store the outcome of authorize(). A result is recorded once per attempt."""
        result = PaymentStatus(result)
        if result not in RESULTS:
            raise DomainError(f"'{result.value}' is not an authorization result.")
        if self.status != PaymentStatus.PENDING:
            raise DomainError("This payment attempt already has a result.")
        self.status = result

    def generate_receipt(self) -> str:
        """Issue the receipt number once, only for an authorized payment."""
        if self.status not in (PaymentStatus.AUTHORIZED, PaymentStatus.REFUNDED):
            raise DomainError("Receipts are only issued for authorized payments.")
        if self.receipt_number is None:
            self.receipt_number = "RCT-" + self.payment_id.split("-", 1)[1]
        return self.receipt_number

    def refund(self) -> bool:
        """Refund an authorized, not yet refunded payment through the processor."""
        if self.status != PaymentStatus.AUTHORIZED:
            return False
        if not self._processor().request_refund(self.payment_id, self.amount):
            return False
        self.status = PaymentStatus.REFUNDED
        return True
