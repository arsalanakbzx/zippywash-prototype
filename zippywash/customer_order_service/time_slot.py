"""C04 TimeSlot — a pickup or delivery window with limited capacity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, time

from zippywash.common import DomainError


@dataclass
class TimeSlot:
    time_slot_id: str
    date: Date
    start_time: str          # "HH:MM"
    available_capacity: int

    def label(self) -> str:
        return f"{self.date:%a %b %d} · {self.start_time}"

    def starts_at(self) -> datetime:
        return datetime.combine(self.date, time.fromisoformat(self.start_time))

    def has_started(self, now: datetime) -> bool:
        """True once the slot's start time has passed; such a slot can't be booked any more."""
        return self.starts_at() <= now

    def check_capacity(self) -> bool:
        return self.available_capacity > 0

    def reserve_capacity(self) -> None:
        if not self.check_capacity():
            raise DomainError(f"The {self.label()} slot is full. Pick another time.")
        self.available_capacity -= 1

    def release_capacity(self) -> None:
        self.available_capacity += 1
