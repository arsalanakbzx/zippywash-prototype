"""C04 TimeSlot — a pickup or delivery window with limited capacity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from zippywash.common import DomainError


@dataclass
class TimeSlot:
    time_slot_id: str
    date: Date
    start_time: str          # "HH:MM"
    available_capacity: int

    def label(self) -> str:
        return f"{self.date:%a %b %d} · {self.start_time}"

    def check_capacity(self) -> bool:
        return self.available_capacity > 0

    def reserve_capacity(self) -> None:
        if not self.check_capacity():
            raise DomainError(f"The {self.label()} slot is full. Pick another time.")
        self.available_capacity -= 1

    def release_capacity(self) -> None:
        self.available_capacity += 1
