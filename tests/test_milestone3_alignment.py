"""Checks that the code matches the finalized Milestone 3 class diagram (C01-C26, October 26, 2026).

Run with:  python -m pytest -q
"""
import dataclasses
import importlib
from abc import ABC
import pkgutil
import sqlite3
from datetime import time, timedelta
from decimal import Decimal

import pytest

import zippywash
from zippywash.common import (today_local, AccountStatus, AddOnType, DomainError, LoyaltyStatus, LoyaltyTransactionType,
                              MachineStatus, MachineType, MaintenanceStatus, PaymentMethodType, PaymentStatus,
                              PickupRequestType, PricingUnit, RouteStatus, RouteStopStatus, ShiftStatus, StaffRole,
                              StockMovementType, StopType, VehicleStatus, BagSize, OrderStatus, NotificationType)
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
from zippywash.database.db import SCHEMA_VERSION, connect, create_schema
from zippywash.database.repository import Repository
from zippywash.database.seed import seed
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
from zippywash.person import Person

# Every Milestone 3 class, with the attributes the class diagram gives it (in Python snake_case).
MODEL = {
    "C01": (Customer, ["customer_id", "account_status", "service_preferences", "name", "contact_details"]),
    "C02": (Address, ["address_id", "street", "postal_code", "access_instructions", "serviceable"]),
    "C03": (ServiceType, ["service_type_id", "name", "pricing_unit", "base_rate", "active"]),
    "C04": (TimeSlot, ["time_slot_id", "date", "start_time", "available_capacity"]),
    "C05": (LoyaltyAccount, ["loyalty_account_id", "point_balance", "status", "enrolled_date"]),
    "C06": (Order, ["order_id", "bag_size", "status", "pickup_request_type", "subtotal", "delivery_fee",
                    "tax_amount", "discount_amount", "estimated_total", "final_total"]),
    "C07": (OrderStatusUpdate, ["status_update_id", "status", "changed_at", "notes"]),
    "C08": (Notification, ["notification_id", "type", "message", "delivery_status"]),
    "C09": (LoyaltyRule, ["loyalty_rule_id", "points_per_dollar", "effective_from", "active"]),
    "C10": (LoyaltyTransaction, ["transaction_id", "type", "points", "reason", "created_at"]),
    "C11": (Payment, ["payment_id", "amount", "status", "receipt_number"]),
    "C12": (PaymentMethod, ["payment_method_id", "token", "type", "active"]),
    "C13": (Reward, ["reward_id", "name", "points_required", "discount_amount", "active", "expiry_date"]),
    "C14": (Promotion, ["promotion_id", "code", "discount_value", "active", "expiry_date"]),
    "C15": (Sector, ["sector_id", "name", "boundary", "active"]),
    "C16": (StaffMember, ["staff_member_id", "roles", "name", "contact_details"]),
    "C17": (Route, ["route_id", "route_date", "status", "total_distance", "occupied_slots"]),
    "C18": (RouteStop, ["route_stop_id", "sequence_number", "stop_type", "status"]),
    "C19": (Machine, ["machine_id", "type", "status", "capacity", "current_cycle"]),
    "C20": (MaintenanceRecord, ["maintenance_record_id", "fault_description", "status", "scheduled_date"]),
    "C21": (InventoryItem, ["inventory_item_id", "name", "quantity_on_hand", "reorder_level"]),
    "C22": (StockMovement, ["stock_movement_id", "type", "quantity", "recorded_at"]),
    "C23": (OrderItem, ["order_item_id", "quantity", "unit_price", "selected_add_ons", "line_total"]),
    "C24": (Vehicle, ["vehicle_id", "slot_capacity", "status"]),
    "C25": (StaffShift, ["staff_shift_id", "shift_date", "start_time", "end_time", "status"]),
    "C26": (Person, ["name", "contact_details"]),
}

TODAY = today_local()


@pytest.fixture
def conn():
    c = connect(":memory:")
    create_schema(c)
    return c


def staff(roles=(StaffRole.DRIVER,)):
    return StaffMember(name="Test Driver", contact_details="t@example.com", staff_member_id="S1", roles=list(roles))


# ---------------------------------------------------------------- classes and attributes
def test_model_has_exactly_26_classes_c01_to_c26():
    assert sorted(MODEL) == [f"C{n:02d}" for n in range(1, 27)]


@pytest.mark.parametrize("cid", sorted(MODEL))
def test_every_class_has_its_milestone3_attributes(cid):
    cls, attrs = MODEL[cid]
    fields = {f.name for f in dataclasses.fields(cls)}
    missing = [a for a in attrs if a not in fields]
    assert not missing, f"{cid} {cls.__name__} is missing {missing}"


def test_all_classes_can_be_instantiated_with_finalized_attributes():
    objects = [
        Customer(name="A", contact_details="a@x.com", customer_id="C1", service_preferences="Unscented"),
        Address("A1", "C1", "1 Rue X", "H3H 1K6", access_instructions="Buzz 2"),
        ServiceType("S1", "Wash", Decimal("10"), pricing_unit=PricingUnit.PER_BAG),
        TimeSlot("T1", TODAY, "08:00", 4),
        LoyaltyAccount("L1", 0, LoyaltyStatus.ACTIVE, TODAY),
        Order("O1", "C1", BagSize.SMALL, "A1", "A1", pickup_request_type=PickupRequestType.LIVE),
        OrderStatusUpdate("U1", "O1", OrderStatus.SCHEDULED, "2026-10-26T09:00:00"),
        Notification("N1", NotificationType.STATUS_CHANGED, "Hi", customer_id="C1"),
        LoyaltyRule("R1", Decimal("1"), TODAY),
        LoyaltyTransaction("LT1", LoyaltyTransactionType.EARN, 10, None, "2026-10-26T09:00:00"),
        Payment("P1", "O1", "PM1", Decimal("10")),
        PaymentMethod("PM1", "C1", "tok_x", PaymentMethodType.CREDIT_CARD, "Visa"),
        Reward("RW1", "Free bag", 100, Decimal("10"), expiry_date=TODAY),
        Promotion("PR1", "CODE", Decimal("5"), expiry_date=TODAY),
        Sector("SEC", "Downtown", "H3H"),
        staff(),
        Route("RT1", TODAY, RouteStatus.DRAFT, Decimal("0"), 0),
        RouteStop("RS1", 1, StopType.PICKUP, RouteStopStatus.PLANNED),
        Machine("M1", MachineType.WASHER, MachineStatus.OPERATIONAL, Decimal("18")),
        MaintenanceRecord("MR1", "Leaks", MaintenanceStatus.REPORTED),
        InventoryItem("I1", "Detergent", Decimal("10"), Decimal("5")),
        StockMovement("SM1", StockMovementType.RECEIPT, Decimal("5"), "2026-10-26T09:00:00"),
        OrderItem("OI1", Decimal("1"), Decimal("10"), [AddOnType.HANG_DRY]),
        Vehicle("V1", 10, VehicleStatus.AVAILABLE),
        StaffShift("SH1", TODAY, time(8), time(16), ShiftStatus.SCHEDULED),
    ]
    assert len(objects) == 25          # plus the abstract Person = 26 classes


def test_all_modules_import():
    for mod in pkgutil.walk_packages(zippywash.__path__, "zippywash."):
        importlib.import_module(mod.name)


# ---------------------------------------------------------------- generalization
def test_customer_and_staff_member_inherit_from_person():
    assert issubclass(Customer, Person)
    assert issubclass(StaffMember, Person)


def test_person_is_abstract():
    assert issubclass(Person, ABC)
    with pytest.raises(TypeError):
        Person(name="X", contact_details="x@example.com")


def test_staff_member_has_no_direct_availability_attribute():
    assert "availability" not in {f.name for f in dataclasses.fields(StaffMember)}


# ---------------------------------------------------------------- SupplyOrder removal
def test_no_supply_order_class_exists():
    for mod in pkgutil.walk_packages(zippywash.__path__, "zippywash."):
        assert not hasattr(importlib.import_module(mod.name), "SupplyOrder")


def test_no_supply_orders_table(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "supply_orders" not in tables


# ---------------------------------------------------------------- schema
def test_schema_creates_new_tables(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"order_items", "order_item_add_ons", "vehicles", "staff_shifts"} <= tables


def test_schema_has_new_columns(conn):
    def cols(table):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    assert "service_preferences" in cols("customers")
    assert "access_instructions" in cols("addresses")
    assert "pricing_unit" in cols("service_types")
    assert "expiry_date" in cols("promotions") and "expiry_date" in cols("rewards")
    assert {"pickup_request_type", "subtotal", "delivery_fee", "tax_amount",
            "discount_amount", "final_total"} <= cols("orders")
    assert "current_cycle" in cols("machines")
    assert {"vehicle_id", "staff_shift_id", "occupied_slots"} <= cols("routes")
    assert "staff_member_id" not in cols("routes")          # driver is reached through StaffShift
    assert "availability" not in cols("staff_members")
    assert "service_type_id" not in cols("orders")          # selected service lives in OrderItem


def test_routes_reference_vehicle_and_staff_shift(conn):
    fks = {(r["table"], r["from"]) for r in conn.execute("PRAGMA foreign_key_list(routes)")}
    assert ("vehicles", "vehicle_id") in fks and ("staff_shifts", "staff_shift_id") in fks


def test_fresh_database_seeds_every_part_of_the_model(conn):
    repo = Repository(conn)
    seed(repo)
    counts = repo.table_counts()
    for table in ["customers", "staff_members", "orders", "order_items", "payments", "vehicles",
                  "staff_shifts", "routes", "machines", "inventory_items", "loyalty_accounts", "rewards"]:
        assert counts[table] > 0, table
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_old_demo_database_is_rebuilt_automatically(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE supply_orders (supply_order_id TEXT)")   # an old-version database
    old.commit()
    old.close()
    c = connect(path)
    assert create_schema(c) is True
    assert c.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "supply_orders" not in tables and "order_items" in tables
    assert create_schema(c) is False                                  # current database is kept


# ---------------------------------------------------------------- Payment correction
def test_payment_uses_create_attempt_not_calculate_total():
    assert hasattr(Payment, "create_attempt")
    assert not hasattr(Payment, "calculate_total")


def test_booked_order_is_priced_through_order_items(conn):
    repo = Repository(conn)
    seed(repo)
    for order in repo.list_orders_for_customer("CUS-LEA"):
        assert len(order.items) >= 1
        assert order.subtotal == sum(i.line_total for i in order.items)
        assert order.final_total == order.estimated_total
        assert order.estimated_total == (order.subtotal - order.discount_amount
                                         + order.delivery_fee + order.tax_amount)


# ---------------------------------------------------------------- business constraints
def test_staff_member_requires_at_least_one_role():
    with pytest.raises(DomainError):
        staff(roles=())
    s = staff()
    with pytest.raises(DomainError):
        s.unassign_role(StaffRole.DRIVER)


def test_staff_check_authorization():
    assert staff().check_authorization(StaffRole.DRIVER)
    assert not staff().check_authorization(StaffRole.LAUNDRY_STAFF)
    assert staff([StaffRole.ADMINISTRATOR]).check_authorization(StaffRole.DRIVER)


def test_order_item_calculates_line_total():
    item = OrderItem("OI1", Decimal("2"), Decimal("24.99"))
    assert item.calculate_line_total() == Decimal("49.98")
    with pytest.raises(DomainError):
        OrderItem("OI2", Decimal("0"), Decimal("24.99")).calculate_line_total()


def test_promotion_eligibility_checks_active_and_expiry():
    Promotion("P", "OK", Decimal("5"), expiry_date=TODAY).validate_eligibility()
    with pytest.raises(DomainError):
        Promotion("P", "OFF", Decimal("5"), active=False).validate_eligibility()
    with pytest.raises(DomainError):
        Promotion("P", "OLD", Decimal("5"), expiry_date=TODAY - timedelta(days=1)).validate_eligibility()


def test_reward_eligibility_checks_active_and_expiry():
    Reward("R", "Free bag", 100, Decimal("10")).validate_eligibility()
    with pytest.raises(DomainError):
        Reward("R", "Free bag", 100, Decimal("10"), active=False).validate_eligibility()
    with pytest.raises(DomainError):
        Reward("R", "Free bag", 100, Decimal("10"), expiry_date=TODAY - timedelta(days=1)).validate_eligibility()


def test_route_occupied_slots_cannot_exceed_vehicle_capacity():
    van = Vehicle("V1", 2)
    route = Route("RT1", TODAY, RouteStatus.DRAFT, Decimal("0"), 0, vehicle_id="V1")
    route.update_slot_count(2, van)
    assert route.calculate_available_slots(van) == 0
    with pytest.raises(DomainError):
        route.update_slot_count(1, van)


def test_staff_shift_start_must_precede_end():
    StaffShift("SH", TODAY, time(8), time(16))
    with pytest.raises(ValueError):
        StaffShift("SH", TODAY, time(16), time(8))


def test_machine_current_cycle_is_optional():
    assert Machine("M", MachineType.DRYER, MachineStatus.OPERATIONAL, Decimal("15")).current_cycle is None
    assert Machine("M", MachineType.WASHER, MachineStatus.OPERATIONAL, Decimal("18"), "Cold").current_cycle == "Cold"


def test_notification_has_exactly_one_recipient():
    with pytest.raises(DomainError):
        Notification.create(NotificationType.STATUS_CHANGED, "x")
    with pytest.raises(DomainError):
        Notification.create(NotificationType.STATUS_CHANGED, "x", customer_id="C", staff_member_id="S")


def test_promotion_and_reward_are_mutually_exclusive(conn):
    order = Order("O1", "C1", BagSize.SMALL, "A1", "A1", reward_id="RW1")
    order.add_item(ServiceType("S1", "Wash", Decimal("20")))
    with pytest.raises(DomainError):
        order.calculate_estimate(Promotion("P", "CODE", Decimal("5")))
    repo = Repository(conn)
    seed(repo)
    repo.save_reward(Reward("RW-X", "Free bag", 100, Decimal("10")))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE orders SET promotion_id='PRM-WELCOME', reward_id='RW-X'")
