"""C16 StaffMember — a ZippyWash employee. Driver, Laundry Staff and Administrator are roles, not subclasses.

StaffMember is a kind of Person: name and contact_details are inherited from C26 Person.
Scheduled availability is represented by C25 StaffShift, not by an attribute here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from zippywash.common import DomainError, StaffRole, new_id
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.person import Person


@dataclass
class StaffMember(Person):
    staff_member_id: str
    roles: list[StaffRole] = field(default_factory=list)   # StaffRole [1..*]
    sector_id: str | None = None                           # only when the Driver role applies

    def __post_init__(self):
        self.roles = [StaffRole(r) for r in self.roles]
        if not self.roles:
            raise DomainError("A staff member needs at least one role.")

    # ---- role management ----
    def assign_role(self, role: StaffRole) -> None:
        role = StaffRole(role)
        if role not in self.roles:
            self.roles.append(role)

    def unassign_role(self, role: StaffRole) -> None:
        role = StaffRole(role)
        if role in self.roles and len(self.roles) == 1:
            raise DomainError("A staff member must keep at least one role.")
        if role in self.roles:
            self.roles.remove(role)
        if role == StaffRole.DRIVER:
            self.sector_id = None

    def assign_sector(self, sector_id: str) -> None:
        if StaffRole.DRIVER not in self.roles:
            raise DomainError("Only a driver can be assigned to a service sector.")
        self.sector_id = sector_id

    def schedule_shift(self, shift_date: date, start: time, end: time) -> StaffShift:
        return StaffShift(new_id("SHF"), shift_date, start, end, staff_member_id=self.staff_member_id)

    # ---- authorization ----
    def has_role(self, role: StaffRole) -> bool:
        """Internal helper: administrators may act in any role."""
        return StaffRole(role) in self.roles or StaffRole.ADMINISTRATOR in self.roles

    def check_authorization(self, required_role: StaffRole) -> bool:
        """Public operation from the class diagram: may this staff member do a role-specific action?"""
        return self.has_role(required_role)
