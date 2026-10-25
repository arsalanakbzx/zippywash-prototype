"""C06 Order — the central class: booking details, price estimate and current status."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from zippywash.common import STATUS_SEQUENCE, BagSize, DomainError, OrderStatus, PickupRequestType, money
from zippywash.config import DELIVERY_FEE, GST_RATE, MIN_TURNAROUND_DAYS, QST_RATE
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.order_item import OrderItem
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot


@dataclass
class PriceBreakdown:
    """Supporting value object (not a Milestone 3 class): the price lines shown before paying.

    Maps onto Order's pricing attributes: subtotal = service_price, discount_amount = discount,
    delivery_fee = delivery_fee, tax_amount = gst + qst, estimated_total = total."""
    service_price: Decimal
    discount: Decimal
    delivery_fee: Decimal
    gst: Decimal
    qst: Decimal
    total: Decimal


@dataclass
class Order:
    order_id: str
    customer_id: str
    bag_size: BagSize
    pickup_address_id: str
    delivery_address_id: str
    status: OrderStatus = OrderStatus.DRAFT
    pickup_request_type: PickupRequestType = PickupRequestType.SCHEDULED
    subtotal: Decimal = Decimal("0.00")
    delivery_fee: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    estimated_total: Decimal = Decimal("0.00")
    final_total: Decimal | None = None            # [0..1], set once payment is authorized
    # implementation references (associations)
    pickup_time_slot_id: str | None = None
    delivery_time_slot_id: str | None = None
    promotion_id: str | None = None
    reward_id: str | None = None
    created_at: str = ""
    items: list[OrderItem] = field(default_factory=list)   # OrderItem [1..*] (aggregation)
    history: list = field(default_factory=list)            # OrderStatusUpdate records, oldest first

    # ---------- items ----------
    def add_item(self, service: ServiceType, quantity: Decimal = Decimal("1")) -> OrderItem:
        item = OrderItem.for_service(self.order_id, service, self.bag_size, quantity)
        self.items.append(item)
        return item

    # ---------- calculateEstimate() ----------
    def calculate_estimate(self, promotion: Promotion | None = None) -> PriceBreakdown:
        """Price every OrderItem, apply one promotion, add the delivery fee and Quebec taxes."""
        if not self.items:
            raise DomainError("An order needs at least one service.")
        if promotion is not None and self.reward_id is not None:
            raise DomainError("An order can use a promo code or a loyalty reward, not both.")
        subtotal = money(sum((item.calculate_line_total() for item in self.items), Decimal("0")))
        discount = promotion.calculate_discount(subtotal) if promotion else money(0)
        taxable = subtotal - discount + DELIVERY_FEE
        gst = money(taxable * GST_RATE)
        qst = money(taxable * QST_RATE)
        total = money(taxable + gst + qst)

        self.subtotal, self.discount_amount = subtotal, discount
        self.delivery_fee, self.tax_amount = money(DELIVERY_FEE), money(gst + qst)
        self.estimated_total = total
        self.promotion_id = promotion.promotion_id if promotion else None
        return PriceBreakdown(subtotal, discount, money(DELIVERY_FEE), gst, qst, total)

    # ---------- calculateFinalTotal() ----------
    def calculate_final_total(self) -> Decimal:
        """The amount actually charged. In Prototype 1 it equals the confirmed estimate."""
        self.final_total = money(self.subtotal - self.discount_amount + self.delivery_fee + self.tax_amount)
        return self.final_total

    # ---------- booking rules checked before confirm() ----------
    @staticmethod
    def validate_booking(customer_id: str, pickup: Address, delivery: Address,
                         pickup_slot: TimeSlot, delivery_slot: TimeSlot) -> None:
        for addr, role in ((pickup, "Pickup"), (delivery, "Delivery")):
            if addr.customer_id != customer_id:
                raise DomainError(f"{role} address does not belong to this customer.")
            if not addr.serviceable:
                raise DomainError(f"{role} address {addr.postal_code} is outside our service sectors.")
        if pickup_slot.date < date.today():
            raise DomainError("Pickup can't be in the past.")
        gap = (delivery_slot.date - pickup_slot.date).days
        if gap < MIN_TURNAROUND_DAYS:
            raise DomainError("Delivery must be at least one day after pickup.")
        for slot, role in ((pickup_slot, "pickup"), (delivery_slot, "delivery")):
            if not slot.check_capacity():
                raise DomainError(f"The {role} slot {slot.label()} is full. Pick another time.")

    # ---------- confirm() ----------
    def confirm(self, pickup_slot: TimeSlot, delivery_slot: TimeSlot, payment_authorized: bool) -> None:
        """Only an order with a successful payment authorization is released for service."""
        if self.status != OrderStatus.DRAFT:
            raise DomainError(f"Order {self.order_id} is already {self.status.value}.")
        if not payment_authorized:
            raise DomainError("Payment must be authorized before the order is confirmed.")
        pickup_slot.reserve_capacity()
        delivery_slot.reserve_capacity()
        self.pickup_time_slot_id = pickup_slot.time_slot_id
        self.delivery_time_slot_id = delivery_slot.time_slot_id
        self.status = OrderStatus.SCHEDULED
        self.calculate_final_total()

    # ---------- updateStatus() ----------
    def next_status(self) -> OrderStatus | None:
        if self.status not in STATUS_SEQUENCE:
            return None
        i = STATUS_SEQUENCE.index(self.status)
        return STATUS_SEQUENCE[i + 1] if i + 1 < len(STATUS_SEQUENCE) else None

    def update_status(self, new_status: OrderStatus) -> None:
        """Statuses move one step forward at a time; no skipping, no going back."""
        expected = self.next_status()
        if expected is None:
            raise DomainError(f"Order is {self.status.value}; its status can't change any more.")
        if OrderStatus(new_status) != expected:
            raise DomainError(f"Next status must be '{expected.value}', not '{OrderStatus(new_status).value}'.")
        self.status = expected

    # ---------- cancel() ----------
    def can_cancel(self) -> bool:
        return self.status == OrderStatus.SCHEDULED

    def cancel(self, pickup_slot: TimeSlot, delivery_slot: TimeSlot) -> None:
        """Cancellable until the driver picks up the bag; frees both time slots."""
        if not self.can_cancel():
            raise DomainError(f"An order that is {self.status.value} can no longer be cancelled.")
        pickup_slot.release_capacity()
        delivery_slot.release_capacity()
        self.status = OrderStatus.CANCELLED
