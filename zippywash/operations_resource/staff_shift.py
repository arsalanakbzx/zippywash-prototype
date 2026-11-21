"""StaffShift — a staff member's scheduled operating period."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, ShiftStatus, StaffRole, link

if TYPE_CHECKING:
    from zippywash.operations_resource.route import Route
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class StaffShift(Entity):
    _pk = "staff_shift_id"

    staff_shift_id: str
    shift_date: date
    start_time: time
    end_time: time
    staff_member: StaffMember | None = None       # [1..1]
    status: ShiftStatus = ShiftStatus.SCHEDULED
    route: Route | None = None                    # [0..1]

    def __post_init__(self):
        self.status = ShiftStatus(self.status)
        for name in ("start_time", "end_time"):
            if isinstance(getattr(self, name), str):
                setattr(self, name, time.fromisoformat(getattr(self, name)))
        if self.start_time >= self.end_time:
            raise DomainError("A shift must start before it ends.")
        if self.staff_member is not None:
            link(self.staff_member.shifts, self)

    def check_availability(self, route_date: date) -> bool:
        """Can this shift take a route on that date? Same day, not cancelled or finished,
        a driver (or administrator), and no route yet."""
        return (self.shift_date == route_date
                and self.status in (ShiftStatus.SCHEDULED, ShiftStatus.ACTIVE)
                and self.staff_member is not None
                and self.staff_member.check_authorization(StaffRole.DRIVER)
                and self.route is None)

    def assign_route(self, route: Route) -> None:
        if self.route is route:
            return
        if not self.check_availability(route.route_date):
            raise DomainError("This shift can't take that route (date, status, driver role or existing route).")
        if route.staff_shift is not None and route.staff_shift is not self:
            raise DomainError("That route already has a shift.")
        self.route = route
        route.staff_shift = self
