"""Address — a customer location and its service-sector assignment."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, link, unlink

if TYPE_CHECKING:
    from zippywash.customer_order_service.customer import Customer
    from zippywash.customer_order_service.order import Order
    from zippywash.operations_resource.route_stop import RouteStop
    from zippywash.operations_resource.sector import Sector

# Canadian postal code: A1A 1A1
POSTAL_RE = re.compile(r"^[A-Z]\d[A-Z] ?\d[A-Z]\d$")


@dataclass(eq=False, repr=False)
class Address(Entity):
    _pk = "address_id"

    address_id: str
    street: str
    postal_code: str
    customer: Customer | None = None                                   # [1..1]
    access_instructions: str | None = None                             # [0..1]
    serviceable: bool = False
    sector: Sector | None = None                                       # [0..1]
    pickup_orders: list[Order] = field(default_factory=list)           # [0..*]
    delivery_orders: list[Order] = field(default_factory=list)         # [0..*]
    route_stops: list[RouteStop] = field(default_factory=list)         # [0..*]

    def __post_init__(self):
        self.street = (self.street or "").strip()
        self.postal_code = self.normalized_postal_code()
        self.access_instructions = (self.access_instructions or "").strip() or None

    # ---------------- helpers ----------------
    def normalized_postal_code(self) -> str:
        pc = (self.postal_code or "").replace(" ", "").upper()
        return f"{pc[:3]} {pc[3:]}" if len(pc) == 6 else pc

    def label(self) -> str:
        return f"{self.street}, {self.postal_code}"

    def format_problem(self) -> str | None:
        if not self.street:
            return "Street address is required."
        if not POSTAL_RE.match(self.postal_code):
            return f"'{self.postal_code}' is not a valid Canadian postal code (e.g. H3H 1K6)."
        return None

    def has_valid_format(self) -> bool:
        return self.format_problem() is None

    # ---------------- Milestone 5 operations ----------------
    def validate(self) -> bool:
        """True when the required fields are valid AND the address is inside an active service sector."""
        return (self.has_valid_format() and self.customer is not None and self.serviceable
                and self.sector is not None and self.sector.contains_address(self))

    def assign_sector(self, sector: Sector) -> None:
        """Place the address in a sector. Only succeeds when that sector contains the address."""
        if not self.has_valid_format():
            raise DomainError(self.format_problem())
        if not sector.contains_address(self):
            raise DomainError(f"{self.postal_code} is outside the {sector.name} sector.")
        if self.sector is not None and self.sector is not sector:
            unlink(self.sector.addresses, self)
        self.sector = sector
        self.serviceable = True
        link(sector.addresses, self)
