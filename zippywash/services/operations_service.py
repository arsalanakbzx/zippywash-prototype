"""OperationsService — UC-03 machines and inventory, UC-04 routes (staff side)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from zippywash.common import DomainError, StockMovementType, new_id
from zippywash.customer_order_service.order import Order
from zippywash.database.repository import World
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.operations_resource.vehicle import Vehicle


class OperationsService:
    def __init__(self, world: World):
        self.world = world

    # ---------------- routes ----------------
    def build_route(self, shift: StaffShift, sector: Sector, vehicle: Vehicle, route_date: date) -> Route:
        route = Route(new_id("RTE"), route_date)
        shift.assign_route(route)
        try:
            route.build(route_date, sector, vehicle)
        except DomainError:
            shift.route, route.staff_shift = None, None   # nothing half-built is kept
            raise
        return route

    @staticmethod
    def insert_live_pickup(route: Route, order: Order) -> bool:
        return route.insert_live_pickup(order, order.pickup_address)

    # ---------------- machines ----------------
    @staticmethod
    def report_fault(machine: Machine, description: str, staff: StaffMember):
        return machine.report_fault(description, staff)

    # ---------------- inventory ----------------
    @staticmethod
    def record_stock(item: InventoryItem, movement_type: StockMovementType, quantity: Decimal,
                     staff: StaffMember):
        return item.adjust_quantity(StockMovementType(movement_type), Decimal(str(quantity)), staff)
