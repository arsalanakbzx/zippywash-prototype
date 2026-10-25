"""C19 Machine — a washer or dryer with status, capacity and an optional current cycle."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from zippywash.common import MachineStatus, MachineType


@dataclass
class Machine:
    machine_id: str
    type: MachineType
    status: MachineStatus
    capacity: Decimal                 # kg per cycle
    current_cycle: str | None = None  # [0..1]

    def update_status(self, status: MachineStatus) -> None:
        self.status = MachineStatus(status)
        if self.status != MachineStatus.OPERATIONAL:
            self.current_cycle = None

    def calculate_capacity(self) -> Decimal:
        """Only an operational machine contributes processing capacity."""
        return self.capacity if self.status == MachineStatus.OPERATIONAL else Decimal("0")
