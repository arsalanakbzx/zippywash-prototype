"""Object-relational mapping for the 25 domain classes (technical code, not part of the class diagram).

Each mapping lists the scalar columns and the to-one references (foreign keys). The matching
collections on the other side (for example Customer.orders) are rebuilt from those foreign keys
when the data is loaded, so the domain objects always hold typed relationships, never raw IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from zippywash import common as C
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.order_item import OrderItem
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
from zippywash.customer_order_service.payment import Payment
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.maintenance_record import MaintenanceRecord
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.route_stop import RouteStop
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.operations_resource.stock_movement import StockMovement
from zippywash.operations_resource.vehicle import Vehicle


@dataclass
class Col:
    attr: str
    kind: object            # str | int | bool | Decimal | date | time | datetime | an Enum class | "roles"
    null: bool = False


@dataclass
class Ref:
    attr: str               # to-one attribute on this class, stored as <attr>_id
    target: type
    inverse: str | None     # attribute on the target that points back
    inverse_many: bool = True   # True: a list on the target; False: a single attribute
    null: bool = True


@dataclass
class Mapping:
    cls: type
    table: str
    pk: str
    cols: list[Col] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)


S, I, B, D, DT, TM, DTM = str, int, bool, Decimal, date, time, datetime

MAPPINGS: list[Mapping] = [
    Mapping(Sector, "sectors", "sector_id", [Col("name", S), Col("boundary", S), Col("active", B)]),
    Mapping(Customer, "customers", "customer_id",
            [Col("name", S), Col("contact_details", S), Col("account_status", C.AccountStatus),
             Col("service_preferences", S, True)]),
    Mapping(StaffMember, "staff_members", "staff_member_id",
            [Col("name", S), Col("contact_details", S), Col("roles", "roles")],
            [Ref("assigned_sector", Sector, "assigned_drivers")]),
    Mapping(Address, "addresses", "address_id",
            [Col("street", S), Col("postal_code", S), Col("access_instructions", S, True), Col("serviceable", B)],
            [Ref("customer", Customer, "addresses", null=False), Ref("sector", Sector, "addresses")]),
    Mapping(ServiceType, "service_types", "service_type_id",
            [Col("name", S), Col("pricing_unit", C.PricingUnit), Col("base_rate", D), Col("active", B)]),
    Mapping(Machine, "machines", "machine_id",
            [Col("type", C.MachineType), Col("status", C.MachineStatus), Col("capacity", D),
             Col("current_cycle", S, True)]),
    Mapping(TimeSlot, "time_slots", "time_slot_id",
            [Col("date", DT), Col("start_time", TM), Col("available_capacity", I), Col("capacity_limit", I)]),
    Mapping(Promotion, "promotions", "promotion_id",
            [Col("code", S), Col("discount_value", D), Col("active", B), Col("expiry_date", DT, True)]),
    Mapping(Reward, "rewards", "reward_id",
            [Col("name", S), Col("points_required", I), Col("discount_amount", D), Col("active", B),
             Col("available_from", DT, True), Col("expiry_date", DT, True)]),
    Mapping(LoyaltyRule, "loyalty_rules", "loyalty_rule_id",
            [Col("points_per_dollar", D), Col("effective_from", DT), Col("active", B)]),
    Mapping(LoyaltyAccount, "loyalty_accounts", "loyalty_account_id",
            [Col("point_balance", I), Col("status", C.LoyaltyAccountStatus), Col("enrolled_date", DT, True)],
            [Ref("customer", Customer, "loyalty_account", inverse_many=False, null=False)]),
    Mapping(PaymentMethod, "payment_methods", "payment_method_id",
            [Col("token", S), Col("type", C.PaymentMethodType), Col("active", B), Col("label", S)],
            [Ref("customer", Customer, "payment_methods", null=False)]),
    Mapping(Order, "orders", "order_id",
            [Col("created_at", DTM), Col("bag_size", C.BagSize), Col("status", C.OrderStatus),
             Col("pickup_request_type", C.PickupRequestType), Col("subtotal", D), Col("delivery_fee", D),
             Col("tax_amount", D), Col("discount_amount", D), Col("estimated_total", D),
             Col("final_total", D, True), Col("dispute_status", C.DisputeStatus, True)],
            [Ref("customer", Customer, "orders", null=False),
             Ref("pickup_address", Address, "pickup_orders", null=False),
             Ref("delivery_address", Address, "delivery_orders", null=False),
             Ref("service_type", ServiceType, "orders", null=False),
             Ref("pickup_time_slot", TimeSlot, "pickup_orders"),
             Ref("delivery_time_slot", TimeSlot, "delivery_orders"),
             Ref("applied_promotion", Promotion, "orders"),
             Ref("applied_reward", Reward, "orders")]),
    Mapping(OrderItem, "order_items", "order_item_id",
            [Col("quantity", I), Col("unit_price", D), Col("line_total", D)],
            [Ref("order", Order, "order_items", null=False)]),
    Mapping(OrderStatusUpdate, "order_status_updates", "status_update_id",
            [Col("status", C.OrderStatus), Col("changed_at", DTM), Col("notes", S, True)],
            [Ref("order", Order, "status_history", null=False), Ref("recorded_by", StaffMember, "status_updates")]),
    Mapping(Payment, "payments", "payment_id",
            [Col("amount", D), Col("status", C.PaymentStatus), Col("receipt_number", S, True),
             Col("created_at", DTM, True)],
            [Ref("order", Order, "payment_attempts", null=False),
             Ref("payment_method", PaymentMethod, "payments", null=False)]),
    Mapping(LoyaltyTransaction, "loyalty_transactions", "transaction_id",
            [Col("type", C.LoyaltyTransactionType), Col("points", I), Col("reason", S, True),
             Col("created_at", DTM), Col("posted", B)],
            [Ref("loyalty_account", LoyaltyAccount, "transactions", null=False),
             Ref("order", Order, "loyalty_transactions"), Ref("reward", Reward, "transactions"),
             Ref("applied_rule", LoyaltyRule, "transactions"), Ref("payment", Payment, "loyalty_transactions"),
             Ref("authorized_by", StaffMember, "authorized_loyalty_transactions"),
             Ref("reservation", LoyaltyTransaction, None), Ref("reverses", LoyaltyTransaction, None)]),
    Mapping(Vehicle, "vehicles", "vehicle_id", [Col("slot_capacity", I), Col("status", C.VehicleStatus)]),
    Mapping(StaffShift, "staff_shifts", "staff_shift_id",
            [Col("shift_date", DT), Col("start_time", TM), Col("end_time", TM), Col("status", C.ShiftStatus)],
            [Ref("staff_member", StaffMember, "shifts", null=False)]),
    Mapping(Route, "routes", "route_id",
            [Col("route_date", DT), Col("status", C.RouteStatus), Col("total_distance", D),
             Col("occupied_slots", I)],
            [Ref("sector", Sector, "routes"), Ref("vehicle", Vehicle, "routes"),
             Ref("staff_shift", StaffShift, "route", inverse_many=False)]),
    Mapping(RouteStop, "route_stops", "route_stop_id",
            [Col("sequence_number", I), Col("stop_type", C.StopType), Col("status", C.StopStatus),
             Col("estimated_arrival_time", DTM, True)],
            [Ref("route", Route, "stops", null=False), Ref("order", Order, "route_stops", null=False),
             Ref("address", Address, "route_stops", null=False)]),
    Mapping(MaintenanceRecord, "maintenance_records", "maintenance_record_id",
            [Col("fault_description", S), Col("repair_details", S, True), Col("status", C.MaintenanceStatus),
             Col("scheduled_date", DT, True)],
            [Ref("machine", Machine, "maintenance_history", null=False),
             Ref("managed_by", StaffMember, "maintenance_records")]),
    Mapping(InventoryItem, "inventory_items", "inventory_item_id",
            [Col("name", S), Col("quantity_on_hand", D), Col("reorder_level", D), Col("alert_open", B)]),
    Mapping(StockMovement, "stock_movements", "stock_movement_id",
            [Col("type", C.StockMovementType), Col("quantity", D), Col("recorded_at", DTM)],
            [Ref("inventory_item", InventoryItem, "movements", null=False),
             Ref("recorded_by", StaffMember, "stock_movements")]),
    Mapping(Notification, "notifications", "notification_id",
            [Col("type", C.NotificationType), Col("message", S), Col("delivery_status", C.DeliveryStatus),
             Col("created_at", DTM, True)],
            [Ref("customer_recipient", Customer, "notifications"), Ref("staff_recipient", StaffMember, "notifications"),
             Ref("status_update", OrderStatusUpdate, "notifications"), Ref("payment", Payment, "notifications"),
             Ref("machine", Machine, "notifications"), Ref("inventory_item", InventoryItem, "notifications")]),
]

BY_CLASS = {m.cls: m for m in MAPPINGS}

# Many-to-many: TimeSlot.contributing_machines <-> Machine.time_slots
JOIN_TABLE = "time_slot_machines"

# How collections are ordered after loading.
SORT_KEYS = {
    (Order, "status_history"): lambda u: u.changed_at,
    (Route, "stops"): lambda s: s.sequence_number,
    (LoyaltyAccount, "transactions"): lambda t: t.created_at,
}


# ---------------------------------------------------------------------------
# Value conversion
# ---------------------------------------------------------------------------
def to_db(kind, value):
    if value is None:
        return None
    if kind == "roles":
        return ",".join(r.value for r in value)
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(value).value
    if kind is bool:
        return 1 if value else 0
    if kind in (Decimal,):
        return str(value)
    if kind in (date, time, datetime):
        return value.isoformat()
    return value


def from_db(kind, value):
    if value is None:
        return None
    if kind == "roles":
        return [C.StaffRole(v) for v in value.split(",") if v]
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(value)
    if kind is bool:
        return bool(value)
    if kind is Decimal:
        return Decimal(value)
    if kind is date:
        return date.fromisoformat(value)
    if kind is time:
        return time.fromisoformat(value)
    if kind is datetime:
        return datetime.fromisoformat(value)
    return value


SQL_TYPE = {str: "TEXT", int: "INTEGER", bool: "INTEGER", Decimal: "TEXT", date: "TEXT", time: "TEXT",
            datetime: "TEXT", "roles": "TEXT"}


def render_schema(version: int) -> str:
    """The SQL schema, generated from the mappings so code and database can't drift apart."""
    out = ["-- ZippyWash Prototype 2 schema (generated from zippywash/database/mapping.py).",
           "-- Money and quantities are stored as exact decimal TEXT, never as binary floats.",
           f"PRAGMA user_version = {version};", ""]
    for m in MAPPINGS:
        lines = [f"    {m.pk} TEXT PRIMARY KEY"]
        for c in m.cols:
            sql = SQL_TYPE.get(c.kind, "TEXT")
            lines.append(f"    {c.attr} {sql}{'' if c.null else ' NOT NULL'}")
        for r in m.refs:
            lines.append(f"    {r.attr}_id TEXT{'' if r.null else ' NOT NULL'} "
                         f"REFERENCES {BY_CLASS[r.target].table}({BY_CLASS[r.target].pk})")
        out.append(f"CREATE TABLE IF NOT EXISTS {m.table} (\n" + ",\n".join(lines) + "\n);")
    out.append(f"CREATE TABLE IF NOT EXISTS {JOIN_TABLE} (\n"
               "    time_slot_id TEXT NOT NULL REFERENCES time_slots(time_slot_id),\n"
               "    machine_id TEXT NOT NULL REFERENCES machines(machine_id),\n"
               "    PRIMARY KEY (time_slot_id, machine_id)\n);")
    return "\n".join(out) + "\n"
