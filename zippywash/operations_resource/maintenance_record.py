"""C20 MaintenanceRecord — one fault and its repair for a Machine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from zippywash.common import MaintenanceStatus


@dataclass
class MaintenanceRecord:
    maintenance_record_id: str
    fault_description: str
    status: MaintenanceStatus = MaintenanceStatus.REPORTED
    scheduled_date: date | None = None   # [0..1]
    # implementation references
    machine_id: str = ""
    managed_by_staff_id: str | None = None

    def schedule(self, on: date) -> None:
        self.scheduled_date = on
        self.status = MaintenanceStatus.SCHEDULED

    def complete(self) -> None:
        self.status = MaintenanceStatus.COMPLETED
