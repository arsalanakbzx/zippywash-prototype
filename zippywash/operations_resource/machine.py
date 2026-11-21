"""Machine — processing equipment (washer or dryer) that contributes time-slot capacity."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import (DomainError, Entity, MachineStatus, MachineType, MaintenanceStatus,
                              NotificationType, StaffRole, link, new_id)

from zippywash.customer_order_service.notification import Notification
from zippywash.operations_resource.maintenance_record import MaintenanceRecord

if TYPE_CHECKING:
    from zippywash.customer_order_service.time_slot import TimeSlot
    from zippywash.operations_resource.staff_member import StaffMember


@dataclass(eq=False, repr=False)
class Machine(Entity):
    _pk = "machine_id"

    machine_id: str
    type: MachineType
    capacity: Decimal                                                       # kg per cycle
    status: MachineStatus = MachineStatus.OPERATIONAL
    current_cycle: str | None = None                                        # [0..1]
    time_slots: list[TimeSlot] = field(default_factory=list)                # [0..*]
    maintenance_history: list[MaintenanceRecord] = field(default_factory=list)  # [0..*]
    notifications: list[Notification] = field(default_factory=list)        # [0..*]

    def __post_init__(self):
        self.type = MachineType(self.type)
        self.status = MachineStatus(self.status)
        self.capacity = Decimal(str(self.capacity))
        if self.capacity <= 0:
            raise DomainError("A machine needs a positive capacity.")

    def open_record(self) -> MaintenanceRecord | None:
        for r in self.maintenance_history:
            if r.status != MaintenanceStatus.COMPLETED:
                return r
        return None

    def update_status(self, new_status: MachineStatus) -> None:
        """Change the status; a machine that isn't operational stops its cycle and gives up
        its time-slot capacity."""
        self.status = MachineStatus(new_status)
        if self.status != MachineStatus.OPERATIONAL:
            self.current_cycle = None
        for slot in self.time_slots:
            slot.recalculate_capacity()

    def report_fault(self, fault_description: str, reported_by: StaffMember) -> MaintenanceRecord:
        """Open one maintenance record, mark the machine Faulty, recalculate capacity and notify staff."""
        if not (fault_description or "").strip():
            raise DomainError("Describe the fault.")
        if reported_by is None or not (reported_by.check_authorization(StaffRole.LAUNDRY_STAFF)):
            raise DomainError("Only laundry staff or an administrator can report a machine fault.")
        if self.open_record() is not None:
            raise DomainError(f"{self.machine_id} already has an open maintenance record.")
        record = MaintenanceRecord(new_id("MNT"), fault_description.strip(), self, managed_by=reported_by)
        self.maintenance_history.append(record)
        link(reported_by.maintenance_records, record)
        self.update_status(MachineStatus.FAULTY)
        alert = Notification.create(NotificationType.MACHINE_FAULT,
                                    f"{self.type.value} {self.machine_id} reported faulty: {record.fault_description}",
                                    staff_recipient=reported_by)
        alert.machine = self
        link(self.notifications, alert)
        alert.send()
        return record

    def calculate_capacity(self) -> Decimal:
        """Only an operational machine contributes processing capacity (kg per cycle)."""
        return self.capacity if self.status == MachineStatus.OPERATIONAL else Decimal("0")
