"""RouteStop — one pickup or delivery event within a route."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from zippywash.common import DomainError, Entity, RouteStatus, StopStatus, StopType, link, new_id

if TYPE_CHECKING:
    from zippywash.customer_order_service.address import Address
    from zippywash.customer_order_service.order import Order
    from zippywash.operations_resource.route import Route


@dataclass(eq=False, repr=False)
class RouteStop(Entity):
    _pk = "route_stop_id"

    route_stop_id: str
    sequence_number: int
    stop_type: StopType
    route: Route | None = None                      # [1..1]
    order: Order | None = None                      # [1..1]
    address: Address | None = None                  # [1..1]
    status: StopStatus = StopStatus.PLANNED
    estimated_arrival_time: datetime | None = None  # [0..1]

    def __post_init__(self):
        self.stop_type = StopType(self.stop_type)
        self.status = StopStatus(self.status)

    def partner(self) -> RouteStop | None:
        """The other stop (pickup <-> delivery) of the same order on the same route."""
        for s in self.route.stops:
            if s is not self and s.order is self.order:
                return s
        return None

    @staticmethod
    def create(route: Route, order: Order, address: Address, stop_type: StopType) -> RouteStop:
        """Add a stop at the end of the route. A delivery needs the order's pickup on the route first."""
        stop_type = StopType(stop_type)
        if route.status in (RouteStatus.FINALIZED, RouteStatus.IN_PROGRESS, RouteStatus.COMPLETED):
            raise DomainError("A finalized route can't be changed.")
        expected = order.pickup_address if stop_type == StopType.PICKUP else order.delivery_address
        if address is not expected:
            raise DomainError(f"A {stop_type.value.lower()} stop must use the order's "
                              f"{stop_type.value.lower()} address.")
        same = [s for s in route.stops if s.order is order]
        if any(s.stop_type == stop_type for s in same):
            raise DomainError(f"Order {order.order_id} already has a {stop_type.value.lower()} stop here.")
        if stop_type == StopType.DELIVERY and not any(s.stop_type == StopType.PICKUP for s in same):
            raise DomainError("A delivery can't be scheduled before its pickup.")
        if len(order.route_stops) >= 2:
            raise DomainError(f"Order {order.order_id} already has its two stops.")
        stop = RouteStop(new_id("STP"), len(route.stops) + 1, stop_type, route, order, address)
        route.stops.append(stop)
        link(order.route_stops, stop)
        link(address.route_stops, stop)
        return stop

    def change_sequence(self, new_position: int) -> None:
        """Move this stop to a new position; numbers stay 1..n and unique; pickup stays before delivery."""
        stops = self.route.stops
        if self.route.status in (RouteStatus.FINALIZED, RouteStatus.IN_PROGRESS, RouteStatus.COMPLETED):
            raise DomainError("A finalized route can't be changed.")
        if not isinstance(new_position, int) or not 1 <= new_position <= len(stops):
            raise DomainError(f"Position must be between 1 and {len(stops)}.")
        ordered = sorted(stops, key=lambda s: s.sequence_number)
        ordered.remove(self)
        ordered.insert(new_position - 1, self)
        pos = {s: i for i, s in enumerate(ordered)}
        for s in ordered:
            p = s.partner()
            if s.stop_type == StopType.DELIVERY and p is not None and pos[p] > pos[s]:
                raise DomainError("A delivery can't come before its pickup.")
        for i, s in enumerate(ordered, start=1):
            s.sequence_number = i
        stops.sort(key=lambda s: s.sequence_number)

    def mark_completed(self) -> None:
        """Record the stop as done. Calling it again changes nothing. A delivery can't be completed
        before its pickup."""
        if self.status == StopStatus.COMPLETED:
            return
        if self.stop_type == StopType.DELIVERY:
            p = self.partner()
            if p is not None and p.status != StopStatus.COMPLETED:
                raise DomainError("Complete the pickup before the delivery.")
        self.status = StopStatus.COMPLETED
