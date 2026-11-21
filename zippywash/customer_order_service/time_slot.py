"""TimeSlot — a dated pickup/delivery window with limited capacity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime
from datetime import time as Time
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, MachineStatus
from zippywash.config import ORDERS_PER_MACHINE_PER_SLOT

if TYPE_CHECKING:
    from zippywash.customer_order_service.order import Order
    from zippywash.operations_resource.machine import Machine


def _positive(count: int, what: str) -> int:
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise DomainError(f"{what} must be a whole number greater than zero.")
    return count


@dataclass(eq=False, repr=False)
class TimeSlot(Entity):
    _pk = "time_slot_id"

    time_slot_id: str
    date: Date
    start_time: Time
    available_capacity: int
    pickup_orders: list[Order] = field(default_factory=list)             # [0..*]
    delivery_orders: list[Order] = field(default_factory=list)           # [0..*]
    contributing_machines: list[Machine] = field(default_factory=list)   # [0..*]
    # Technical: the most orders this slot can hold (set from configuration or by recalculate_capacity).
    capacity_limit: int | None = None

    def __post_init__(self):
        if isinstance(self.start_time, str):
            self.start_time = Time.fromisoformat(self.start_time)
        if self.available_capacity < 0:
            raise DomainError("Capacity can't be negative.")
        if self.capacity_limit is None:
            self.capacity_limit = self.available_capacity

    # ---------------- helpers ----------------
    def label(self) -> str:
        return f"{self.date:%a %b %d} · {self.start_time:%H:%M}"

    def starts_at(self) -> datetime:
        return datetime.combine(self.date, self.start_time)

    def has_started(self, now: datetime) -> bool:
        return self.starts_at() <= now

    def booked_count(self) -> int:
        return self.capacity_limit - self.available_capacity

    # ---------------- Milestone 5 operations ----------------
    def check_capacity(self, required_slots: int) -> bool:
        return self.available_capacity >= _positive(required_slots, "Required slots")

    def reserve_capacity(self, required_slots: int) -> bool:
        """All-or-nothing: either every requested slot is reserved, or nothing changes."""
        if not self.check_capacity(required_slots):
            return False
        self.available_capacity -= required_slots
        return True

    def release_capacity(self, released_slots: int) -> None:
        _positive(released_slots, "Released slots")
        if self.available_capacity + released_slots > self.capacity_limit:
            raise DomainError("Can't release more capacity than this slot holds.")
        self.available_capacity += released_slots

    def recalculate_capacity(self) -> int:
        """Re-derive the limit from the operational machines linked to this slot and keep existing
        bookings. Returns the new available capacity (never below zero)."""
        if self.contributing_machines:
            working = sum(1 for m in self.contributing_machines if m.status == MachineStatus.OPERATIONAL)
            booked = self.booked_count()
            self.capacity_limit = working * ORDERS_PER_MACHINE_PER_SLOT
            self.available_capacity = max(0, self.capacity_limit - booked)
        return self.available_capacity
