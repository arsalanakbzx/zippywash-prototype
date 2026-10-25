"""C23 OrderItem — one selected service line inside an Order (Order 1 ◇── 1..* OrderItem)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from zippywash.common import AddOnType, BagSize, DomainError, money, new_id
from zippywash.customer_order_service.service_type import ServiceType


@dataclass
class OrderItem:
    order_item_id: str
    quantity: Decimal
    unit_price: Decimal
    selected_add_ons: list[AddOnType] = field(default_factory=list)   # AddOnType [0..*]
    line_total: Decimal = Decimal("0.00")
    # implementation references (associations)
    order_id: str = ""
    service_type_id: str = ""

    @classmethod
    def for_service(cls, order_id: str, service: ServiceType, bag_size: BagSize,
                    quantity: Decimal = Decimal("1"), add_ons: list[AddOnType] | None = None) -> "OrderItem":
        """Price one line from the selected ServiceType (per-bag rate x bag size)."""
        item = cls(new_id("OIT"), Decimal(quantity), service.calculate_base_price(bag_size),
                   list(add_ons or []), order_id=order_id, service_type_id=service.service_type_id)
        item.calculate_line_total()
        return item

    def calculate_line_total(self) -> Decimal:
        """lineTotal = unitPrice x quantity. Add-ons carry no price in Prototype 1."""
        if self.quantity <= 0:
            raise DomainError("Quantity must be greater than zero.")
        self.line_total = money(self.unit_price * self.quantity)
        return self.line_total
