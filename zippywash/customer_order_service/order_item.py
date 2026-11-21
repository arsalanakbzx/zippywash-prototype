"""OrderItem — one priced quantity within an Order. (selectedAddOns was removed in Milestone 5.)"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, money

if TYPE_CHECKING:
    from zippywash.customer_order_service.order import Order


@dataclass(eq=False, repr=False)
class OrderItem(Entity):
    _pk = "order_item_id"

    order_item_id: str
    quantity: int
    order: Order | None = None                      # [1..1]
    unit_price: Decimal = Decimal("0.00")
    line_total: Decimal = Decimal("0.00")

    def __post_init__(self):
        self.unit_price, self.line_total = money(self.unit_price), money(self.line_total)
        if not isinstance(self.quantity, int) or isinstance(self.quantity, bool) or self.quantity <= 0:
            raise DomainError("Quantity must be a whole number greater than zero.")

    def calculate_line_total(self, unit_price: Decimal) -> Decimal:
        """Store the unit price and lineTotal = quantity x unitPrice, and return the line total."""
        unit_price = money(unit_price)
        if unit_price < 0:
            raise DomainError("Unit price can't be negative.")
        if self.quantity <= 0:
            raise DomainError("Quantity must be greater than zero.")
        self.unit_price = unit_price
        self.line_total = money(unit_price * self.quantity)
        return self.line_total
