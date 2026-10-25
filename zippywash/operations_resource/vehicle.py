"""C24 Vehicle — a delivery vehicle with a fixed number of bag slots."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import VehicleStatus


@dataclass
class Vehicle:
    vehicle_id: str
    slot_capacity: int
    status: VehicleStatus = VehicleStatus.AVAILABLE

    def __post_init__(self):
        if self.slot_capacity < 0:
            raise ValueError("Slot capacity can't be negative.")

    def check_capacity(self, occupied_slots: int) -> bool:
        """True while the vehicle still has a free slot."""
        return occupied_slots < self.slot_capacity

    def update_availability(self, status: VehicleStatus) -> None:
        self.status = VehicleStatus(status)
