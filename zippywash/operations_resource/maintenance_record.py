"""MaintenanceRecord — tracks a machine fault through repair completion."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, MachineStatus, MaintenanceStatus, StaffRole, link, today_local

if TYPE_CHECKING:
    from zippywash.operations_resource.machine import Machine
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class MaintenanceRecord(Entity):
    _pk = "maintenance_record_id"

    maintenance_record_id: str
    fault_description: str
    machine: Machine | None = None                  # [1..1]
    status: MaintenanceStatus = MaintenanceStatus.REPORTED
    repair_details: str | None = None               # [0..1]
    scheduled_date: date | None = None              # [0..1]
    managed_by: StaffMember | None = None           # [0..1]

    def __post_init__(self):
        self.status = MaintenanceStatus(self.status)

    def schedule(self, repair_date: date, managed_by: StaffMember | None = None) -> None:
        if self.status not in (MaintenanceStatus.REPORTED, MaintenanceStatus.SCHEDULED):
            raise DomainError(f"A record that is {self.status.value} can't be rescheduled.")
        if repair_date is None or repair_date < today_local():
            raise DomainError("The repair date can't be in the past.")
        if managed_by is not None:
            if not managed_by.check_authorization(StaffRole.LAUNDRY_STAFF):
                raise DomainError("Only laundry staff or an administrator can manage repairs.")
            self.managed_by = managed_by
            link(managed_by.maintenance_records, self)
        self.scheduled_date = repair_date
        self.status = MaintenanceStatus.SCHEDULED
        self.machine.update_status(MachineStatus.UNDER_MAINTENANCE)

    def update_repair_details(self, repair_details: str) -> None:
        if self.status == MaintenanceStatus.COMPLETED:
            raise DomainError("This repair is already completed.")
        if not (repair_details or "").strip():
            raise DomainError("Describe the repair work.")
        self.repair_details = repair_details.strip()
        self.status = MaintenanceStatus.IN_REPAIR
        if self.machine.status == MachineStatus.FAULTY:
            self.machine.update_status(MachineStatus.UNDER_MAINTENANCE)

    def complete(self) -> None:
        """Close the record. The machine goes back to Operational only if no other repair is open."""
        if self.status == MaintenanceStatus.COMPLETED:
            raise DomainError("This repair is already completed.")
        if not self.repair_details:
            raise DomainError("Add the repair details before completing the repair.")
        self.status = MaintenanceStatus.COMPLETED
        if self.machine.open_record() is None:
            self.machine.update_status(MachineStatus.OPERATIONAL)
