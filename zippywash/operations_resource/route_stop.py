"""C18 RouteStop — one ordered pickup or delivery stop on a Route."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import RouteStopStatus, StopType


@dataclass
class RouteStop:
    route_stop_id: str
    sequence_number: int
    stop_type: StopType
    status: RouteStopStatus = RouteStopStatus.PLANNED
    # implementation references
    route_id: str = ""
    order_id: str = ""
    address_id: str = ""

    def change_sequence(self, new_sequence: int) -> None:
        if new_sequence < 1:
            raise ValueError("Sequence numbers start at 1.")
        self.sequence_number = new_sequence

    def mark_completed(self) -> None:
        self.status = RouteStopStatus.COMPLETED
