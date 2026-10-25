"""C03 ServiceType — a laundry service, priced by its pricing unit (per bag in Prototype 1)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from zippywash.common import BagSize, DomainError, PricingUnit, money
from zippywash.config import BAG_SIZE_MULTIPLIER


@dataclass
class ServiceType:
    service_type_id: str
    name: str
    base_rate: Decimal
    active: bool = True
    pricing_unit: PricingUnit = PricingUnit.PER_BAG

    def calculate_base_price(self, bag_size: BagSize) -> Decimal:
        if not self.active:
            raise DomainError(f"'{self.name}' is not currently offered.")
        return money(self.base_rate * BAG_SIZE_MULTIPLIER[BagSize(bag_size).value])

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
