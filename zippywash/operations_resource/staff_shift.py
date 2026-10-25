"""C25 StaffShift — one scheduled work shift for a StaffMember (StaffMember 1 ◇── 0..* StaffShift)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from zippywash.common import ShiftStatus


@dataclass
class StaffShift:
    staff_shift_id: str
    shift_date: date
    start_time: time
    end_time: time
    status: ShiftStatus = ShiftStatus.SCHEDULED
    staff_member_id: str = ""          # implementation reference

    def __post_init__(self):
        if self.start_time >= self.end_time:
            raise ValueError("A shift must start before it ends.")

    def check_availability(self, on: date, at: time) -> bool:
        """True if this shift covers the given date and time and isn't cancelled."""
        return (self.status != ShiftStatus.CANCELLED and self.shift_date == on
                and self.start_time <= at < self.end_time)
