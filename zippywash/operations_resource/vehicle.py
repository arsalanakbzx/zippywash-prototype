"""Vehicle — provides route capacity (bag slots) and availability."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, VehicleStatus

if TYPE_CHECKING:
    from zippywash.operations_resource.route import Route


@dataclass(eq=False, repr=False)
class Vehicle(Entity):
    _pk = "vehicle_id"

    vehicle_id: str
    slot_capacity: int
    status: VehicleStatus = VehicleStatus.AVAILABLE
    routes: list[Route] = field(default_factory=list)     # [0..*]

    def __post_init__(self):
        self.status = VehicleStatus(self.status)
        if not isinstance(self.slot_capacity, int) or self.slot_capacity <= 0:
            raise DomainError("A vehicle needs a positive slot capacity.")

    def check_capacity(self, required_slots: int) -> bool:
        """True if this many occupied order slots fit in the vehicle (counts orders, not stops)."""
        if not isinstance(required_slots, int) or required_slots < 0:
            raise DomainError("Required slots must be zero or more.")
        return required_slots <= self.slot_capacity

    def update_availability(self, new_status: VehicleStatus) -> None:
        self.status = VehicleStatus(new_status)
