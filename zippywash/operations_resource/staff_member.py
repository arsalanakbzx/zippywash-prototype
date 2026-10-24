"""C16 StaffMember — drivers, laundry staff and administrators are roles, not subclasses."""
from __future__ import annotations

from dataclasses import dataclass, field

from zippywash.common import StaffRole


@dataclass
class StaffMember:
    staff_member_id: str
    name: str
    roles: list[StaffRole] = field(default_factory=list)   # StaffRole [1..*]
    availability: str = "Available"
    sector_id: str | None = None

    def has_role(self, role: StaffRole) -> bool:
        return role in self.roles or StaffRole.ADMINISTRATOR in self.roles

    def update_availability(self, availability: str) -> None:
        if availability not in ("Available", "Busy", "Off"):
            raise ValueError(f"Unknown availability: {availability}")
        self.availability = availability
