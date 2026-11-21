"""Sector — a service boundary for addresses, drivers and routes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, StaffRole, link, unlink

if TYPE_CHECKING:
    from zippywash.customer_order_service.address import Address
    from zippywash.operations_resource.route import Route
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class Sector(Entity):
    _pk = "sector_id"

    sector_id: str
    name: str
    boundary: str          # simplified GeoBoundary: comma-separated postal prefixes, e.g. "H3H,H3G"
    active: bool = True
    addresses: list[Address] = field(default_factory=list)            # [0..*]
    assigned_drivers: list[StaffMember] = field(default_factory=list) # [0..*]
    routes: list[Route] = field(default_factory=list)                 # [0..*]

    def prefixes(self) -> list[str]:
        return [p.strip().upper() for p in self.boundary.split(",") if p.strip()]

    def contains_address(self, address: Address) -> bool:
        """Deterministic rule: the postal code's first three characters fall in this active sector."""
        fsa = (address.postal_code or "").replace(" ", "").upper()[:3]
        return self.active and fsa in self.prefixes()

    def assign_driver(self, driver: StaffMember) -> None:
        if not self.active:
            raise DomainError(f"The {self.name} sector is not active.")
        if StaffRole.DRIVER not in driver.roles:
            raise DomainError("Only a driver can be assigned to a service sector.")
        if driver.assigned_sector is not None and driver.assigned_sector is not self:
            unlink(driver.assigned_sector.assigned_drivers, driver)
        driver.assigned_sector = self
        link(self.assigned_drivers, driver)
