"""Route — builds and manages a dated pickup/delivery route for one Sector, Vehicle and StaffShift.

No live maps: optimization is a simple, deterministic simulation (stops grouped by postal area,
fixed minutes between stops). It changes the order and arrival times, never which stops exist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import (DomainError, Entity, OrderStatus, PickupRequestType, RouteStatus, StaffRole,
                              StopStatus, StopType, VehicleStatus, link)
from zippywash.config import KM_PER_STOP, MINUTES_PER_STOP
from zippywash.operations_resource.route_stop import RouteStop

if TYPE_CHECKING:
    from zippywash.customer_order_service.address import Address
    from zippywash.customer_order_service.order import Order
    from zippywash.operations_resource.sector import Sector
    from zippywash.operations_resource.staff_shift import StaffShift
    from zippywash.operations_resource.vehicle import Vehicle

LOCKED = (RouteStatus.FINALIZED, RouteStatus.IN_PROGRESS, RouteStatus.COMPLETED)
REQUIRED_SLOTS_PER_ORDER = 1   # current prototype capacity rule: one bag slot per order


@dataclass(eq=False, repr=False)
class Route(Entity):
    _pk = "route_id"

    route_id: str
    route_date: date
    status: RouteStatus = RouteStatus.DRAFT
    total_distance: Decimal = Decimal("0")
    occupied_slots: int = 0
    sector: Sector | None = None                                  # [1..1]
    stops: list[RouteStop] = field(default_factory=list)          # [1..*]
    vehicle: Vehicle | None = None                                # [1..1]
    staff_shift: StaffShift | None = None                         # [1..1]
    flagged_orders: list = field(default_factory=list)            # technical: orders that didn't fit

    def __post_init__(self):
        self.status = RouteStatus(self.status)
        self.total_distance = Decimal(str(self.total_distance))

    # ---------------- helpers ----------------
    def _ensure_editable(self) -> None:
        if self.status in LOCKED:
            raise DomainError("A finalized route can't be changed.")

    def orders(self) -> list[Order]:
        seen = []
        for s in self.stops:
            if s.order not in seen:
                seen.append(s.order)
        return seen

    @staticmethod
    def _eligible(order: Order, route_date: date, sector: Sector) -> bool:
        return (order.status == OrderStatus.SCHEDULED and order.pickup_time_slot is not None
                and order.pickup_time_slot.date == route_date
                and order.pickup_address is not None and order.delivery_address is not None
                and sector.contains_address(order.pickup_address)
                and sector.contains_address(order.delivery_address))

    def _add_order(self, order: Order) -> None:
        RouteStop.create(self, order, order.pickup_address, StopType.PICKUP)
        RouteStop.create(self, order, order.delivery_address, StopType.DELIVERY)
        self.occupied_slots += REQUIRED_SLOTS_PER_ORDER

    def _resequence_and_time(self) -> None:
        start = datetime.combine(self.route_date, self.staff_shift.start_time) if self.staff_shift else None
        for i, s in enumerate(sorted(self.stops, key=lambda s: s.sequence_number), start=1):
            s.sequence_number = i
            s.estimated_arrival_time = start + timedelta(minutes=MINUTES_PER_STOP * i) if start else None
        self.stops.sort(key=lambda s: s.sequence_number)
        changes = sum(1 for a, b in zip(self.stops, self.stops[1:])
                      if a.address.postal_code[:3] != b.address.postal_code[:3])
        self.total_distance = KM_PER_STOP * (len(self.stops) + changes) if self.stops else Decimal("0")

    # ---------------- Milestone 5 operations ----------------
    def build(self, route_date: date, assigned_sector: Sector, assigned_vehicle: Vehicle) -> None:
        """M5-C02. Create one PICKUP and one DELIVERY stop for each eligible scheduled order, as long
        as the vehicle has room. Orders that don't fit are flagged. Doesn't optimize or finalize."""
        # 1. Preconditions
        if route_date is None:
            raise DomainError("Choose a route date.")
        if assigned_sector is None or not assigned_sector.active:
            raise DomainError("Choose an active sector.")
        if (assigned_vehicle is None or assigned_vehicle.status != VehicleStatus.AVAILABLE
                or assigned_vehicle.slot_capacity <= 0):
            raise DomainError("Choose an available vehicle with free capacity.")
        shift = self.staff_shift
        if (shift is None or shift.route is not self or shift.shift_date != route_date
                or not shift.staff_member.check_authorization(StaffRole.DRIVER)):
            raise DomainError("Assign a valid driver shift for that date before building the route.")
        self._ensure_editable()
        if self.stops:
            raise DomainError("This route is already built. Use recalculate() after changes.")

        # 2. References, both ends consistent
        self.route_date, self.sector, self.vehicle = route_date, assigned_sector, assigned_vehicle
        link(assigned_sector.routes, self)
        link(assigned_vehicle.routes, self)

        # 3. Unique eligible candidates found through the sector's addresses
        self.occupied_slots, self.flagged_orders = 0, []
        candidates: list[Order] = []
        for address in assigned_sector.addresses:
            for order in address.pickup_orders + address.delivery_orders:
                if order not in candidates and not order.route_stops and self._eligible(order, route_date,
                                                                                        assigned_sector):
                    candidates.append(order)
        candidates.sort(key=lambda o: (o.pickup_time_slot.start_time, o.created_at))

        # 4-5. Two stops per accepted order; capacity counts orders, not stops
        for order in candidates:
            if not assigned_vehicle.check_capacity(self.occupied_slots + REQUIRED_SLOTS_PER_ORDER):
                self.flagged_orders.append(order)
                continue
            self._add_order(order)

        # 6. No valid-looking empty route
        if not self.stops:
            raise DomainError("No eligible scheduled orders in this sector for that date.")
        self._resequence_and_time()

    def optimize(self) -> None:
        """Order stops by postal area: all pickups first, then deliveries. Membership is unchanged,
        and every pickup stays before its delivery."""
        self._ensure_editable()
        if not self.stops:
            raise DomainError("Build the route before optimizing it.")
        key = lambda s: (s.stop_type != StopType.PICKUP, s.address.postal_code, s.order.order_id)
        for i, s in enumerate(sorted(self.stops, key=key), start=1):
            s.sequence_number = i
        self._resequence_and_time()
        self.status = RouteStatus.OPTIMIZED

    def calculate_available_slots(self) -> int:
        if self.vehicle is None:
            return 0
        return self.vehicle.slot_capacity - self.occupied_slots

    def recalculate_capacity(self) -> int:
        """Recount occupied slots from the orders on the route; returns the free slots."""
        active = {s.order for s in self.stops if s.status != StopStatus.SKIPPED}
        self.occupied_slots = len(active) * REQUIRED_SLOTS_PER_ORDER
        if self.vehicle is not None and not self.vehicle.check_capacity(self.occupied_slots):
            raise DomainError("The route has more orders than the vehicle can carry.")
        return self.calculate_available_slots()

    def insert_live_pickup(self, order: Order, pickup_address: Address) -> bool:
        """Add a live (same-day) pickup request if it's eligible, in sector and fits.
        Returns False and changes nothing when it can't be added."""
        if self.status in LOCKED or not self.stops or self.sector is None or self.vehicle is None:
            return False
        if (order.pickup_request_type != PickupRequestType.LIVE or order.status != OrderStatus.SCHEDULED
                or order.route_stops or pickup_address is not order.pickup_address):
            return False
        if not (self.sector.contains_address(pickup_address)
                and self.sector.contains_address(order.delivery_address)):
            return False
        if not self.vehicle.check_capacity(self.occupied_slots + REQUIRED_SLOTS_PER_ORDER):
            return False
        self._add_order(order)
        self.recalculate()
        return True

    def recalculate(self) -> None:
        """After a change: renumber stops, refresh arrival times, distance and capacity.
        An optimized route is re-optimized so it stays optimized."""
        self._ensure_editable()
        if self.status == RouteStatus.OPTIMIZED:
            self.optimize()
        else:
            self._resequence_and_time()
        self.recalculate_capacity()

    def finalize_route(self) -> None:
        """Lock the plan. Needs stops and an optimized order; afterwards the route rejects changes."""
        self._ensure_editable()
        if not self.stops:
            raise DomainError("An empty route can't be finalized.")
        if self.status != RouteStatus.OPTIMIZED:
            raise DomainError("Optimize the route before finalizing it.")
        self.recalculate_capacity()
        self.status = RouteStatus.FINALIZED
        if self.vehicle is not None:
            self.vehicle.update_availability(VehicleStatus.IN_SERVICE)
