"""Repository: the only place that turns database rows into domain objects and back.

Domain classes hold the business rules; this file only loads and saves them.
Prototype 1 has load/save methods for the classes the screens use, plus simple save methods
for the operations classes so the sample data shows the full Milestone 3 schema in use.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from zippywash.common import (AccountStatus, AddOnType, BagSize, DeliveryStatus, NotificationType, OrderStatus,
                              PaymentMethodType, PaymentStatus, PickupRequestType, PricingUnit, StaffRole)
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
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
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.operations_resource.vehicle import Vehicle


def _dec(v) -> str | None:
    return None if v is None else str(v)


def _date(v) -> str | None:
    return None if v is None else v.isoformat()


def _opt_date(v) -> date | None:
    return date.fromisoformat(v) if v else None


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    def _all(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()

    def _upsert(self, table: str, key: str, row: dict) -> None:
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        updates = ", ".join(f"{c}=excluded.{c}" for c in row if c != key)
        self.conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks}) "
                          f"ON CONFLICT({key}) DO UPDATE SET {updates}", tuple(row.values()))

    # ---------------- Customer / Address ----------------
    @staticmethod
    def _customer(r) -> Customer:
        return Customer(name=r["name"], contact_details=r["contact_details"], customer_id=r["customer_id"],
                        account_status=AccountStatus(r["account_status"]),
                        service_preferences=r["service_preferences"])

    def get_customer(self, customer_id: str) -> Customer | None:
        r = self._one("SELECT * FROM customers WHERE customer_id=?", customer_id)
        return self._customer(r) if r else None

    def list_customers(self) -> list[Customer]:
        return [self._customer(r) for r in self._all("SELECT * FROM customers ORDER BY name")]

    def save_customer(self, c: Customer) -> None:
        self._upsert("customers", "customer_id", {
            "customer_id": c.customer_id, "name": c.name, "contact_details": c.contact_details,
            "account_status": AccountStatus(c.account_status).value,
            "service_preferences": c.service_preferences})

    @staticmethod
    def _address(r) -> Address:
        return Address(r["address_id"], r["customer_id"], r["street"], r["postal_code"],
                       bool(r["serviceable"]), r["sector_id"], r["access_instructions"])

    def get_address(self, address_id: str) -> Address | None:
        r = self._one("SELECT * FROM addresses WHERE address_id=?", address_id)
        return self._address(r) if r else None

    def list_addresses(self, customer_id: str) -> list[Address]:
        return [self._address(r) for r in self._all(
            "SELECT * FROM addresses WHERE customer_id=? ORDER BY street", customer_id)]

    def save_address(self, a: Address) -> None:
        self._upsert("addresses", "address_id", {
            "address_id": a.address_id, "customer_id": a.customer_id, "street": a.street,
            "postal_code": a.postal_code.upper(), "access_instructions": a.access_instructions,
            "serviceable": int(a.serviceable), "sector_id": a.sector_id})

    # ---------------- Sector / Staff ----------------
    def list_sectors(self) -> list[Sector]:
        return [Sector(r["sector_id"], r["name"], r["boundary"], bool(r["active"]))
                for r in self._all("SELECT * FROM sectors")]

    def save_sector(self, s: Sector) -> None:
        self._upsert("sectors", "sector_id", {"sector_id": s.sector_id, "name": s.name,
                                              "boundary": s.boundary, "active": int(s.active)})

    def get_staff(self, staff_id: str) -> StaffMember | None:
        r = self._one("SELECT * FROM staff_members WHERE staff_member_id=?", staff_id)
        if not r:
            return None
        roles = [StaffRole(x["role"]) for x in self._all(
            "SELECT role FROM staff_roles WHERE staff_member_id=?", staff_id)]
        return StaffMember(name=r["name"], contact_details=r["contact_details"],
                           staff_member_id=r["staff_member_id"], roles=roles, sector_id=r["sector_id"])

    def list_staff(self) -> list[StaffMember]:
        return [self.get_staff(r["staff_member_id"]) for r in self._all(
            "SELECT staff_member_id FROM staff_members ORDER BY name")]

    def save_staff(self, s: StaffMember) -> None:
        self._upsert("staff_members", "staff_member_id", {
            "staff_member_id": s.staff_member_id, "name": s.name, "contact_details": s.contact_details,
            "sector_id": s.sector_id})
        self.conn.execute("DELETE FROM staff_roles WHERE staff_member_id=?", (s.staff_member_id,))
        self.conn.executemany("INSERT INTO staff_roles (staff_member_id, role) VALUES (?,?)",
                              [(s.staff_member_id, StaffRole(role).value) for role in s.roles])

    def save_staff_shift(self, sh: StaffShift) -> None:
        self._upsert("staff_shifts", "staff_shift_id", {
            "staff_shift_id": sh.staff_shift_id, "staff_member_id": sh.staff_member_id,
            "shift_date": _date(sh.shift_date), "start_time": sh.start_time.strftime("%H:%M"),
            "end_time": sh.end_time.strftime("%H:%M"), "status": sh.status.value})

    # ---------------- Catalogue ----------------
    @staticmethod
    def _service(r) -> ServiceType:
        return ServiceType(r["service_type_id"], r["name"], Decimal(r["base_rate"]), bool(r["active"]),
                           PricingUnit(r["pricing_unit"]))

    def list_service_types(self, active_only: bool = True) -> list[ServiceType]:
        sql = "SELECT * FROM service_types" + (" WHERE active=1" if active_only else "") + " ORDER BY base_rate"
        return [self._service(r) for r in self._all(sql)]

    def get_service_type(self, sid: str) -> ServiceType | None:
        r = self._one("SELECT * FROM service_types WHERE service_type_id=?", sid)
        return self._service(r) if r else None

    def save_service_type(self, s: ServiceType) -> None:
        self._upsert("service_types", "service_type_id", {
            "service_type_id": s.service_type_id, "name": s.name, "pricing_unit": s.pricing_unit.value,
            "base_rate": _dec(s.base_rate), "active": int(s.active)})

    @staticmethod
    def _promo(r) -> Promotion:
        return Promotion(r["promotion_id"], r["code"], Decimal(r["discount_value"]), bool(r["active"]),
                         _opt_date(r["expiry_date"]))

    def get_promotion_by_code(self, code: str) -> Promotion | None:
        r = self._one("SELECT * FROM promotions WHERE code=?", code.strip().upper())
        return self._promo(r) if r else None

    def get_promotion(self, pid: str) -> Promotion | None:
        r = self._one("SELECT * FROM promotions WHERE promotion_id=?", pid)
        return self._promo(r) if r else None

    def save_promotion(self, p: Promotion) -> None:
        self._upsert("promotions", "promotion_id", {
            "promotion_id": p.promotion_id, "code": p.code.upper(), "discount_value": _dec(p.discount_value),
            "active": int(p.active), "expiry_date": _date(p.expiry_date)})

    def save_reward(self, rw: Reward) -> None:
        self._upsert("rewards", "reward_id", {
            "reward_id": rw.reward_id, "name": rw.name, "points_required": rw.points_required,
            "discount_amount": _dec(rw.discount_amount), "active": int(rw.active),
            "expiry_date": _date(rw.expiry_date)})

    # ---------------- Loyalty ----------------
    def save_loyalty_account(self, a: LoyaltyAccount) -> None:
        self._upsert("loyalty_accounts", "loyalty_account_id", {
            "loyalty_account_id": a.loyalty_account_id, "customer_id": a.customer_id,
            "point_balance": a.point_balance, "status": a.status.value, "enrolled_date": _date(a.enrolled_date)})

    def save_loyalty_rule(self, rule: LoyaltyRule) -> None:
        self._upsert("loyalty_rules", "loyalty_rule_id", {
            "loyalty_rule_id": rule.loyalty_rule_id, "points_per_dollar": _dec(rule.points_per_dollar),
            "effective_from": _date(rule.effective_from), "active": int(rule.active)})

    # ---------------- Time slots ----------------
    @staticmethod
    def _slot(r) -> TimeSlot:
        return TimeSlot(r["time_slot_id"], date.fromisoformat(r["date"]), r["start_time"], r["available_capacity"])

    def get_slot(self, slot_id: str) -> TimeSlot | None:
        r = self._one("SELECT * FROM time_slots WHERE time_slot_id=?", slot_id)
        return self._slot(r) if r else None

    def list_open_slots(self, from_date: date) -> list[TimeSlot]:
        return [self._slot(r) for r in self._all(
            "SELECT * FROM time_slots WHERE date>=? ORDER BY date, start_time", from_date.isoformat())]

    def add_slot_if_missing(self, s: TimeSlot) -> None:
        """Create a slot only if none exists for that date and time, so booked capacity is never reset."""
        exists = self._one("SELECT 1 FROM time_slots WHERE date=? AND start_time=?",
                           s.date.isoformat(), s.start_time)
        if not exists:
            self.conn.execute("INSERT OR IGNORE INTO time_slots (time_slot_id, date, start_time, available_capacity) "
                              "VALUES (?,?,?,?)", (s.time_slot_id, s.date.isoformat(), s.start_time,
                                                   s.available_capacity))

    def save_slot(self, s: TimeSlot) -> None:
        self._upsert("time_slots", "time_slot_id", {
            "time_slot_id": s.time_slot_id, "date": s.date.isoformat(), "start_time": s.start_time,
            "available_capacity": s.available_capacity})

    # ---------------- Orders ----------------
    def _order(self, r) -> Order:
        o = Order(r["order_id"], r["customer_id"], BagSize(r["bag_size"]),
                  r["pickup_address_id"], r["delivery_address_id"], OrderStatus(r["status"]),
                  PickupRequestType(r["pickup_request_type"]),
                  Decimal(r["subtotal"]), Decimal(r["delivery_fee"]), Decimal(r["tax_amount"]),
                  Decimal(r["discount_amount"]), Decimal(r["estimated_total"]),
                  Decimal(r["final_total"]) if r["final_total"] is not None else None,
                  r["pickup_time_slot_id"], r["delivery_time_slot_id"],
                  r["promotion_id"], r["reward_id"], r["created_at"])
        o.items = self.list_order_items(o.order_id)
        o.history = self.list_status_updates(o.order_id)
        return o

    def get_order(self, order_id: str) -> Order | None:
        r = self._one("SELECT * FROM orders WHERE order_id=?", order_id)
        return self._order(r) if r else None

    def list_orders_for_customer(self, customer_id: str) -> list[Order]:
        return [self._order(r) for r in self._all(
            "SELECT * FROM orders WHERE customer_id=? AND status<>'Draft' ORDER BY created_at DESC", customer_id)]

    def list_active_orders(self) -> list[Order]:
        return [self._order(r) for r in self._all(
            "SELECT * FROM orders WHERE status NOT IN ('Draft','Delivered','Cancelled') ORDER BY created_at")]

    def save_order(self, o: Order) -> None:
        """Saves the order and its OrderItems (items are written once, when the order is created)."""
        self._upsert("orders", "order_id", {
            "order_id": o.order_id, "customer_id": o.customer_id, "bag_size": o.bag_size.value,
            "status": o.status.value, "pickup_request_type": o.pickup_request_type.value,
            "subtotal": _dec(o.subtotal), "delivery_fee": _dec(o.delivery_fee), "tax_amount": _dec(o.tax_amount),
            "discount_amount": _dec(o.discount_amount), "estimated_total": _dec(o.estimated_total),
            "final_total": _dec(o.final_total),
            "pickup_address_id": o.pickup_address_id, "delivery_address_id": o.delivery_address_id,
            "pickup_time_slot_id": o.pickup_time_slot_id, "delivery_time_slot_id": o.delivery_time_slot_id,
            "promotion_id": o.promotion_id, "reward_id": o.reward_id, "created_at": o.created_at})
        for item in o.items:
            self._upsert("order_items", "order_item_id", {
                "order_item_id": item.order_item_id, "order_id": o.order_id,
                "service_type_id": item.service_type_id, "quantity": _dec(item.quantity),
                "unit_price": _dec(item.unit_price), "line_total": _dec(item.line_total)})
            self.conn.execute("DELETE FROM order_item_add_ons WHERE order_item_id=?", (item.order_item_id,))
            self.conn.executemany("INSERT INTO order_item_add_ons (order_item_id, add_on) VALUES (?,?)",
                                  [(item.order_item_id, a.value) for a in item.selected_add_ons])

    def list_order_items(self, order_id: str) -> list[OrderItem]:
        items = []
        for r in self._all("SELECT * FROM order_items WHERE order_id=? ORDER BY rowid", order_id):
            add_ons = [AddOnType(x["add_on"]) for x in self._all(
                "SELECT add_on FROM order_item_add_ons WHERE order_item_id=?", r["order_item_id"])]
            items.append(OrderItem(r["order_item_id"], Decimal(r["quantity"]), Decimal(r["unit_price"]),
                                   add_ons, Decimal(r["line_total"]), r["order_id"], r["service_type_id"]))
        return items

    def list_status_updates(self, order_id: str) -> list[OrderStatusUpdate]:
        return [OrderStatusUpdate(r["status_update_id"], r["order_id"], OrderStatus(r["status"]),
                                  r["changed_at"], r["notes"], r["recorded_by_staff_id"])
                for r in self._all("SELECT * FROM order_status_updates WHERE order_id=? "
                                   "ORDER BY changed_at, rowid", order_id)]

    def add_status_update(self, u: OrderStatusUpdate) -> None:
        self.conn.execute("INSERT INTO order_status_updates (status_update_id, order_id, status, changed_at, "
                          "notes, recorded_by_staff_id) VALUES (?,?,?,?,?,?)",
                          (u.status_update_id, u.order_id, u.status.value, u.changed_at, u.notes,
                           u.recorded_by_staff_id))

    # ---------------- Payments ----------------
    @staticmethod
    def _method(r) -> PaymentMethod:
        return PaymentMethod(r["payment_method_id"], r["customer_id"], r["token"], PaymentMethodType(r["type"]),
                             r["label"], bool(r["active"]))

    def list_payment_methods(self, customer_id: str) -> list[PaymentMethod]:
        return [self._method(r) for r in self._all(
            "SELECT * FROM payment_methods WHERE customer_id=? AND active=1", customer_id)]

    def get_payment_method(self, pmid: str) -> PaymentMethod | None:
        r = self._one("SELECT * FROM payment_methods WHERE payment_method_id=?", pmid)
        return self._method(r) if r else None

    def save_payment_method(self, m: PaymentMethod) -> None:
        self._upsert("payment_methods", "payment_method_id", {
            "payment_method_id": m.payment_method_id, "customer_id": m.customer_id, "token": m.token,
            "type": PaymentMethodType(m.type).value, "label": m.label, "active": int(m.active)})

    def list_payments(self, order_id: str) -> list[Payment]:
        return [Payment(r["payment_id"], r["order_id"], r["payment_method_id"], Decimal(r["amount"]),
                        PaymentStatus(r["status"]), r["receipt_number"], r["created_at"])
                for r in self._all("SELECT * FROM payments WHERE order_id=? ORDER BY created_at, rowid", order_id)]

    def save_payment(self, p: Payment) -> None:
        self._upsert("payments", "payment_id", {
            "payment_id": p.payment_id, "order_id": p.order_id, "payment_method_id": p.payment_method_id,
            "amount": _dec(p.amount), "status": p.status.value, "receipt_number": p.receipt_number,
            "created_at": p.created_at})

    # ---------------- Notifications ----------------
    def add_notification(self, n: Notification) -> None:
        self.conn.execute(
            "INSERT INTO notifications (notification_id, type, message, delivery_status, customer_id, "
            "staff_member_id, status_update_id, payment_id, machine_id, inventory_item_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (n.notification_id, NotificationType(n.type).value, n.message, DeliveryStatus(n.delivery_status).value,
             n.customer_id, n.staff_member_id, n.status_update_id, n.payment_id, n.machine_id,
             n.inventory_item_id, n.created_at))

    def list_notifications(self, customer_id: str, limit: int = 20):
        return self._all("SELECT * FROM notifications WHERE customer_id=? ORDER BY created_at DESC, rowid DESC "
                         "LIMIT ?", customer_id, limit)

    # ---------------- Operations (sample data for Prototype 1; screens come in Prototype 2) ----------------
    def save_vehicle(self, v: Vehicle) -> None:
        self._upsert("vehicles", "vehicle_id", {"vehicle_id": v.vehicle_id, "slot_capacity": v.slot_capacity,
                                                "status": v.status.value})

    def save_route(self, rt: Route) -> None:
        self._upsert("routes", "route_id", {
            "route_id": rt.route_id, "sector_id": rt.sector_id, "vehicle_id": rt.vehicle_id,
            "staff_shift_id": rt.staff_shift_id, "route_date": _date(rt.route_date), "status": rt.status.value,
            "total_distance": _dec(rt.total_distance), "occupied_slots": rt.occupied_slots})

    def save_machine(self, m: Machine) -> None:
        self._upsert("machines", "machine_id", {
            "machine_id": m.machine_id, "type": m.type.value, "status": m.status.value,
            "capacity": _dec(m.capacity), "current_cycle": m.current_cycle})

    def save_inventory_item(self, i: InventoryItem) -> None:
        self._upsert("inventory_items", "inventory_item_id", {
            "inventory_item_id": i.inventory_item_id, "name": i.name,
            "quantity_on_hand": _dec(i.quantity_on_hand), "reorder_level": _dec(i.reorder_level)})

    def table_counts(self) -> dict[str, int]:
        names = [r["name"] for r in self._all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: self._one(f'SELECT COUNT(*) FROM "{n}"')[0] for n in names}
