"""C17 Route — a pickup/delivery route for one Sector, Vehicle and StaffShift."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from zippywash.common import DomainError, RouteStatus
from zippywash.operations_resource.vehicle import Vehicle


@dataclass
class Route:
    route_id: str
    route_date: date
    status: RouteStatus
    total_distance: Decimal
    occupied_slots: int = 0
    # implementation references: the driver is reached through StaffShift
    sector_id: str = ""
    vehicle_id: str = ""
    staff_shift_id: str = ""

    def calculate_available_slots(self, vehicle: Vehicle) -> int:
        return vehicle.slot_capacity - self.occupied_slots

    def update_slot_count(self, change: int, vehicle: Vehicle) -> None:
        """Occupied slots stay between 0 and the vehicle's slot capacity."""
        new_count = self.occupied_slots + change
        if new_count < 0:
            raise DomainError("Occupied slots can't go below zero.")
        if new_count > vehicle.slot_capacity:
            raise DomainError(f"Vehicle {vehicle.vehicle_id} has only {vehicle.slot_capacity} slots.")
        self.occupied_slots = new_count
