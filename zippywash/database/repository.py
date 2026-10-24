"""Repository: the only place that turns database rows into domain objects and back.

Domain classes hold the business rules; this file only loads and saves them.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal

from zippywash.common import BagSize, OrderStatus, PaymentStatus, StaffRole
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.notification import Notification
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate
from zippywash.customer_order_service.payment import Payment
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    def _all(self, sql, *args):
        return self.conn.execute(sql, args).fetchall()

    # ---------------- Customer / Address ----------------
    def get_customer(self, customer_id: str) -> Customer | None:
        r = self._one("SELECT * FROM customers WHERE customer_id=?", customer_id)
        return Customer(r["customer_id"], r["name"], r["contact_details"], r["account_status"]) if r else None

    def list_customers(self) -> list[Customer]:
        return [Customer(r["customer_id"], r["name"], r["contact_details"], r["account_status"])
                for r in self._all("SELECT * FROM customers ORDER BY name")]

    def save_customer(self, c: Customer) -> None:
        self.conn.execute(
            "INSERT INTO customers VALUES (?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET "
            "name=excluded.name, contact_details=excluded.contact_details, account_status=excluded.account_status",
            (c.customer_id, c.name, c.contact_details, c.account_status))

    @staticmethod
    def _address(r) -> Address:
        return Address(r["address_id"], r["customer_id"], r["street"], r["postal_code"],
                       bool(r["serviceable"]), r["sector_id"])

    def get_address(self, address_id: str) -> Address | None:
        r = self._one("SELECT * FROM addresses WHERE address_id=?", address_id)
        return self._address(r) if r else None

    def list_addresses(self, customer_id: str) -> list[Address]:
        return [self._address(r) for r in self._all(
            "SELECT * FROM addresses WHERE customer_id=? ORDER BY street", customer_id)]

    def save_address(self, a: Address) -> None:
        self.conn.execute(
            "INSERT INTO addresses VALUES (?,?,?,?,?,?) ON CONFLICT(address_id) DO UPDATE SET "
            "street=excluded.street, postal_code=excluded.postal_code, "
            "serviceable=excluded.serviceable, sector_id=excluded.sector_id",
            (a.address_id, a.customer_id, a.street, a.postal_code.upper(), int(a.serviceable), a.sector_id))

    # ---------------- Sector / Staff ----------------
    def list_sectors(self) -> list[Sector]:
        return [Sector(r["sector_id"], r["name"], r["boundary"], bool(r["active"]))
                for r in self._all("SELECT * FROM sectors")]

    def save_sector(self, s: Sector) -> None:
        self.conn.execute("INSERT OR REPLACE INTO sectors VALUES (?,?,?,?)",
                          (s.sector_id, s.name, s.boundary, int(s.active)))

    def get_staff(self, staff_id: str) -> StaffMember | None:
        r = self._one("SELECT * FROM staff_members WHERE staff_member_id=?", staff_id)
        if not r:
            return None
        roles = [StaffRole(x["role"]) for x in self._all(
            "SELECT role FROM staff_roles WHERE staff_member_id=?", staff_id)]
        return StaffMember(r["staff_member_id"], r["name"], roles, r["availability"], r["sector_id"])

    def list_staff(self) -> list[StaffMember]:
        return [self.get_staff(r["staff_member_id"]) for r in self._all(
            "SELECT staff_member_id FROM staff_members ORDER BY name")]

    def save_staff(self, s: StaffMember) -> None:
        self.conn.execute("INSERT OR REPLACE INTO staff_members VALUES (?,?,?,?)",
                          (s.staff_member_id, s.name, s.availability, s.sector_id))
        self.conn.execute("DELETE FROM staff_roles WHERE staff_member_id=?", (s.staff_member_id,))
        self.conn.executemany("INSERT INTO staff_roles VALUES (?,?)",
                              [(s.staff_member_id, role.value) for role in s.roles])

    # ---------------- Catalogue ----------------
    def list_service_types(self, active_only: bool = True) -> list[ServiceType]:
        sql = "SELECT * FROM service_types" + (" WHERE active=1" if active_only else "") + " ORDER BY base_rate"
        return [ServiceType(r["service_type_id"], r["name"], Decimal(r["base_rate"]), bool(r["active"]))
                for r in self._all(sql)]

    def get_service_type(self, sid: str) -> ServiceType | None:
        r = self._one("SELECT * FROM service_types WHERE service_type_id=?", sid)
        return ServiceType(r["service_type_id"], r["name"], Decimal(r["base_rate"]), bool(r["active"])) if r else None

    def save_service_type(self, s: ServiceType) -> None:
        self.conn.execute("INSERT OR REPLACE INTO service_types VALUES (?,?,?,?)",
                          (s.service_type_id, s.name, str(s.base_rate), int(s.active)))

    def get_promotion_by_code(self, code: str) -> Promotion | None:
        r = self._one("SELECT * FROM promotions WHERE code=?", code.strip().upper())
        return self._promo(r) if r else None

    def get_promotion(self, pid: str) -> Promotion | None:
        r = self._one("SELECT * FROM promotions WHERE promotion_id=?", pid)
        return self._promo(r) if r else None

    @staticmethod
    def _promo(r) -> Promotion:
        return Promotion(r["promotion_id"], r["code"], Decimal(r["discount_value"]), bool(r["active"]))

    def save_promotion(self, p: Promotion) -> None:
        self.conn.execute("INSERT OR REPLACE INTO promotions VALUES (?,?,?,?)",
                          (p.promotion_id, p.code.upper(), str(p.discount_value), int(p.active)))

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
            self.conn.execute("INSERT OR IGNORE INTO time_slots VALUES (?,?,?,?)",
                              (s.time_slot_id, s.date.isoformat(), s.start_time, s.available_capacity))

    def save_slot(self, s: TimeSlot) -> None:
        self.conn.execute(
            "INSERT INTO time_slots VALUES (?,?,?,?) ON CONFLICT(time_slot_id) DO UPDATE SET "
            "available_capacity=excluded.available_capacity",
            (s.time_slot_id, s.date.isoformat(), s.start_time, s.available_capacity))

    # ---------------- Orders ----------------
    def _order(self, r) -> Order:
        o = Order(r["order_id"], r["customer_id"], r["service_type_id"], BagSize(r["bag_size"]),
                  r["pickup_address_id"], r["delivery_address_id"], OrderStatus(r["status"]),
                  Decimal(r["estimated_total"]), r["pickup_time_slot_id"], r["delivery_time_slot_id"],
                  r["promotion_id"], r["reward_id"], r["created_at"])
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
        self.conn.execute(
            """INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(order_id) DO UPDATE SET status=excluded.status,
               estimated_total=excluded.estimated_total, pickup_time_slot_id=excluded.pickup_time_slot_id,
               delivery_time_slot_id=excluded.delivery_time_slot_id, promotion_id=excluded.promotion_id,
               reward_id=excluded.reward_id""",
            (o.order_id, o.customer_id, o.service_type_id, o.bag_size.value, o.status.value,
             str(o.estimated_total), o.pickup_address_id, o.delivery_address_id,
             o.pickup_time_slot_id, o.delivery_time_slot_id, o.promotion_id, o.reward_id, o.created_at))

    def list_status_updates(self, order_id: str) -> list[OrderStatusUpdate]:
        return [OrderStatusUpdate(r["status_update_id"], r["order_id"], OrderStatus(r["status"]),
                                  r["changed_at"], r["notes"], r["recorded_by_staff_id"])
                for r in self._all("SELECT * FROM order_status_updates WHERE order_id=? "
                                   "ORDER BY changed_at, rowid", order_id)]

    def add_status_update(self, u: OrderStatusUpdate) -> None:
        self.conn.execute("INSERT INTO order_status_updates VALUES (?,?,?,?,?,?)",
                          (u.status_update_id, u.order_id, u.status.value, u.changed_at, u.notes,
                           u.recorded_by_staff_id))

    # ---------------- Payments ----------------
    def list_payment_methods(self, customer_id: str) -> list[PaymentMethod]:
        return [PaymentMethod(r["payment_method_id"], r["customer_id"], r["token"], r["type"], r["label"],
                              bool(r["active"]))
                for r in self._all("SELECT * FROM payment_methods WHERE customer_id=? AND active=1", customer_id)]

    def get_payment_method(self, pmid: str) -> PaymentMethod | None:
        r = self._one("SELECT * FROM payment_methods WHERE payment_method_id=?", pmid)
        return PaymentMethod(r["payment_method_id"], r["customer_id"], r["token"], r["type"], r["label"],
                             bool(r["active"])) if r else None

    def save_payment_method(self, m: PaymentMethod) -> None:
        self.conn.execute("INSERT OR REPLACE INTO payment_methods VALUES (?,?,?,?,?,?)",
                          (m.payment_method_id, m.customer_id, m.token, m.type, m.label, int(m.active)))

    def list_payments(self, order_id: str) -> list[Payment]:
        return [Payment(r["payment_id"], r["order_id"], r["payment_method_id"], Decimal(r["amount"]),
                        PaymentStatus(r["status"]), r["receipt_number"], r["created_at"])
                for r in self._all("SELECT * FROM payments WHERE order_id=? ORDER BY created_at, rowid", order_id)]

    def save_payment(self, p: Payment) -> None:
        self.conn.execute(
            "INSERT INTO payments VALUES (?,?,?,?,?,?,?) ON CONFLICT(payment_id) DO UPDATE SET "
            "status=excluded.status, receipt_number=excluded.receipt_number",
            (p.payment_id, p.order_id, p.payment_method_id, str(p.amount), p.status.value,
             p.receipt_number, p.created_at))

    # ---------------- Notifications ----------------
    def add_notification(self, n: Notification) -> None:
        self.conn.execute("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?)",
                          (n.notification_id, n.type.value, n.message, n.delivery_status, n.customer_id,
                           n.staff_member_id, n.status_update_id, n.inventory_item_id, n.created_at))

    def list_notifications(self, customer_id: str, limit: int = 20):
        return self._all("SELECT * FROM notifications WHERE customer_id=? ORDER BY created_at DESC, rowid DESC "
                         "LIMIT ?", customer_id, limit)
