"""Schema and repository: clean initialization, full round trip, Decimal/date/enum values, migration."""
import sqlite3
from decimal import Decimal

from zippywash.common import BagSize, MachineStatus, StaffRole
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.db import SCHEMA_PATH, SCHEMA_VERSION, connect, create_schema
from zippywash.database.mapping import BY_CLASS, JOIN_TABLE, MAPPINGS, render_schema
from zippywash.database.repository import Repository
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.staff_member import StaffMember


def test_schema_file_matches_the_mapping():
    assert SCHEMA_PATH.read_text() == render_schema(SCHEMA_VERSION)
    assert len(MAPPINGS) == 25


def test_empty_database_initializes_cleanly(tmp_path):
    conn = connect(tmp_path / "fresh.db")
    assert create_schema(conn) is False
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {m.table for m in MAPPINGS} | {JOIN_TABLE}
    assert "order_item_add_ons" not in tables
    assert Repository(conn).load().all(Customer) == []


def test_old_prototype1_database_is_rebuilt(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("PRAGMA user_version = 2; CREATE TABLE order_item_add_ons (x TEXT); "
                      "CREATE TABLE customers (customer_id TEXT);")
    old.close()
    conn = connect(path)
    assert create_schema(conn) is True
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "order_item_add_ons" not in tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_round_trip_every_class_and_relationship(repo, world):
    again = repo.load()
    for m in MAPPINGS:
        assert len(again.all(m.cls)) == len(world.all(m.cls)), m.table
        for obj in world.all(m.cls):
            twin = again.get(m.cls, getattr(obj, m.pk))
            for c in m.cols:
                assert getattr(twin, c.attr) == getattr(obj, c.attr), (m.table, c.attr)
            for r in m.refs:
                a, b = getattr(obj, r.attr), getattr(twin, r.attr)
                key = BY_CLASS[r.target].pk
                assert (a and getattr(a, key)) == (b and getattr(b, key)), (m.table, r.attr)


def test_values_keep_their_types(world):
    lea = world.get(Customer, "CUS-LEA")
    order = lea.view_order_history()[0]
    assert isinstance(order.estimated_total, Decimal) and isinstance(order.bag_size, BagSize)
    assert isinstance(world.get(StaffMember, "STF-ADM1").roles[0], StaffRole)
    slot = world.all(TimeSlot)[0]
    assert slot.contributing_machines and slot in slot.contributing_machines[0].time_slots
    assert all(isinstance(o.customer, Customer) for o in world.all(Order))     # typed, not raw IDs


def test_unchanged_world_writes_nothing_and_changes_are_saved(repo):
    world = repo.load()
    assert repo.commit(world) == 0
    machine = world.get(Machine, "MCH-W1")
    machine.update_status(MachineStatus.OUT_OF_SERVICE)
    assert repo.commit(world) > 1                 # machine + its time slots' recalculated capacity
    again = repo.load()
    assert again.get(Machine, "MCH-W1").status == MachineStatus.OUT_OF_SERVICE
    assert all(s.capacity_limit == 2 for s in again.all(TimeSlot) if s.booked_count() == 0)


def test_no_database_file_is_committed():
    import subprocess
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if f.endswith((".db", ".sqlite"))]
