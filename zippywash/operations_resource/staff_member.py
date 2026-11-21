"""StaffMember — operational staff and their authorization roles.

Driver, Laundry Staff and Administrator are roles, not subclasses. name and contactDetails sit
directly on StaffMember (the abstract Person class was removed in Milestone 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, ShiftStatus, StaffRole, new_id, unlink
from zippywash.operations_resource.staff_shift import StaffShift

if TYPE_CHECKING:
    from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
    from zippywash.customer_order_service.notification import Notification
    from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
    from zippywash.operations_resource.maintenance_record import MaintenanceRecord
    from zippywash.operations_resource.sector import Sector
    from zippywash.operations_resource.stock_movement import StockMovement


@dataclass(eq=False, repr=False)
class StaffMember(Entity):
    _pk = "staff_member_id"

    staff_member_id: str
    name: str
    contact_details: str
    roles: list[StaffRole] = field(default_factory=list)                                # [1..*]
    assigned_sector: Sector | None = None                                               # [0..1]
    shifts: list[StaffShift] = field(default_factory=list)                              # [0..*]
    status_updates: list[OrderStatusUpdate] = field(default_factory=list)               # [0..*]
    maintenance_records: list[MaintenanceRecord] = field(default_factory=list)          # [0..*]
    stock_movements: list[StockMovement] = field(default_factory=list)                  # [0..*]
    authorized_loyalty_transactions: list[LoyaltyTransaction] = field(default_factory=list)  # [0..*]
    notifications: list[Notification] = field(default_factory=list)                    # [0..*]

    def __post_init__(self):
        unique = []
        for r in self.roles:
            r = StaffRole(r)
            if r not in unique:
                unique.append(r)
        self.roles = unique
        if not self.roles:
            raise DomainError("A staff member needs at least one role.")

    def assign_role(self, role: StaffRole) -> None:
        role = StaffRole(role)
        if role in self.roles:
            raise DomainError(f"{self.name} already has the {role.label} role.")
        self.roles.append(role)

    def unassign_role(self, role: StaffRole) -> None:
        role = StaffRole(role)
        if role not in self.roles:
            raise DomainError(f"{self.name} doesn't have the {role.label} role.")
        if len(self.roles) == 1:
            raise DomainError("A staff member must keep at least one role.")
        self.roles.remove(role)
        if role == StaffRole.DRIVER and self.assigned_sector is not None:
            unlink(self.assigned_sector.assigned_drivers, self)
            self.assigned_sector = None

    def assign_sector(self, sector: Sector) -> None:
        """Assign this driver to a service sector (both sides stay consistent)."""
        sector.assign_driver(self)

    def schedule_shift(self, shift_date: date, start_time: time, end_time: time) -> StaffShift:
        """Add a valid shift that doesn't overlap another scheduled shift on the same day."""
        if start_time >= end_time:
            raise DomainError("A shift must start before it ends.")
        for s in self.shifts:
            if (s.status != ShiftStatus.CANCELLED and s.shift_date == shift_date
                    and start_time < s.end_time and s.start_time < end_time):
                raise DomainError(f"{self.name} already has a shift {s.start_time:%H:%M}-{s.end_time:%H:%M} "
                                  f"that day.")
        shift = StaffShift(new_id("SHF"), shift_date, start_time, end_time, self)   # links itself to self.shifts
        return shift

    def check_authorization(self, required_role: StaffRole) -> bool:
        """May this staff member perform an action that needs this role? Administrators may do all."""
        return StaffRole(required_role) in self.roles or StaffRole.ADMINISTRATOR in self.roles
