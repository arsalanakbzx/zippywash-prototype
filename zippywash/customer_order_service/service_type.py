"""ServiceType — an active laundry service and its price basis."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import BagSize, DomainError, Entity, PricingUnit, money
from zippywash.config import BAG_SIZE_MULTIPLIER

if TYPE_CHECKING:
    from zippywash.customer_order_service.order import Order


@dataclass(eq=False, repr=False)
class ServiceType(Entity):
    _pk = "service_type_id"

    service_type_id: str
    name: str
    base_rate: Decimal
    pricing_unit: PricingUnit = PricingUnit.PER_BAG
    active: bool = True
    orders: list[Order] = field(default_factory=list)     # [0..*]

    def __post_init__(self):
        self.base_rate = money(self.base_rate)
        self.pricing_unit = PricingUnit(self.pricing_unit)
        if self.base_rate < 0:
            raise DomainError("A service rate can't be negative.")

    def calculate_base_price(self, bag_size: BagSize) -> Decimal:
        """Unit price for one bag of this size: base rate (per small bag) x bag-size multiplier."""
        if not self.active:
            raise DomainError(f"'{self.name}' is not currently offered.")
        try:
            size = BagSize(bag_size)
        except ValueError:
            raise DomainError(f"'{bag_size}' is not a supported bag size.") from None
        if self.pricing_unit != PricingUnit.PER_BAG or size.value not in BAG_SIZE_MULTIPLIER:
            raise DomainError(f"'{self.name}' can't be priced for a {size.value} bag.")
        return money(self.base_rate * BAG_SIZE_MULTIPLIER[size.value])

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
