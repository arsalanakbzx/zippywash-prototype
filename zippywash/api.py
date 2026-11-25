"""ZippyWash API — one JSON entry point for the web front end (technical layer, no business rules).

    api = ZippyWashAPI(InMemoryRepository())      # in the browser (Pyodide)
    api.call("start_booking", {"customer_id": "CUS-LEA", ...})   -> {"ok": True, "data": {...}}

Every call: load the data, run one service/domain action, save, and return plain JSON.
A broken business rule comes back as {"ok": False, "error": "<message for the user>"}.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from zippywash.common import (STATUS_SEQUENCE, PaymentMethodType, money, new_id, BagSize, DomainError, LoyaltyTransactionType, OrderStatus,
                              PickupRequestType, StaffRole, StockMovementType, now_local, today_local)
from zippywash.config import DELIVERY_FEE, GST_RATE, QST_RATE
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
from zippywash.customer_order_service.order import ROLE_FOR_STATUS, Order
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.seed import ensure_rolling_slots, seed
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.maintenance_record import MaintenanceRecord
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.route_stop import RouteStop
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService
from zippywash.services.operations_service import OperationsService
from zippywash.services.order_tracking_service import OrderTrackingService

T = LoyaltyTransactionType
ACTIVITY = {T.RESERVATION: "Reserved", T.REDEMPTION: "Redeemed", T.RESTORATION: "Restored", T.EARN: "Earned",
            T.CORRECTION: "Correction", T.REVERSAL: "Reversed", T.ENROLLMENT: "Joined"}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def m(v) -> str | None:
    return None if v is None else f"{Decimal(v):.2f}"


def iso(v) -> str | None:
    return None if v is None else v.isoformat()


def slot_json(s: TimeSlot | None) -> dict | None:
    if s is None:
        return None
    return {"id": s.time_slot_id, "date": iso(s.date), "start": s.start_time.strftime("%H:%M"),
            "available": s.available_capacity, "limit": s.capacity_limit}


def address_json(a) -> dict:
    return {"id": a.address_id, "street": a.street, "postal_code": a.postal_code, "label": a.label(),
            "access": a.access_instructions, "serviceable": a.serviceable,
            "sector": a.sector.name if a.sector else None}


def method_json(pm: PaymentMethod) -> dict:
    return {"id": pm.payment_method_id, "label": pm.label, "type": pm.type.value, "active": pm.active}


def status_json(u) -> dict:
    return {"status": u.status.value, "at": iso(u.changed_at), "notes": u.notes,
            "by": u.recorded_by.name if u.recorded_by else None}


def account_json(acc: LoyaltyAccount | None) -> dict | None:
    if acc is None:
        return None
    return {"id": acc.loyalty_account_id, "status": acc.status.value, "balance": acc.point_balance,
            "reserved": acc.reserved_points(), "available": acc.available_points(),
            "enrolled": iso(acc.enrolled_date)}


def order_json(o: Order) -> dict:
    p = o.price_breakdown()
    account = o.customer.loyalty_account
    reward_state = None
    if o.applied_reward is not None and account is not None:
        reward_state = "Reserved" if account.open_reservations(order=o, reward=o.applied_reward) else None
    redemption = next((t for t in (account.transactions if account else [])
                       if t.type == T.REDEMPTION and t.order is o), None)
    if redemption is not None:
        reward_state = "Redeemed"
    payment = o.authorized_payment()
    last_attempt = o.payment_attempts[-1] if o.payment_attempts else None
    latest = o.get_current_status()
    flow = [s.value for s in STATUS_SEQUENCE[1:]]
    return {
        "id": o.order_id, "created": iso(o.created_at), "status": o.status.value,
        "customer": {"id": o.customer.customer_id, "name": o.customer.name, "contact": o.customer.contact_details},
        "service": {"id": o.service_type.service_type_id, "name": o.service_type.name},
        "bag_size": o.bag_size.value, "quantity": sum(i.quantity for i in o.order_items),
        "pickup_request_type": o.pickup_request_type.value,
        "pickup_address": address_json(o.pickup_address), "delivery_address": address_json(o.delivery_address),
        "pickup_slot": slot_json(o.pickup_time_slot), "delivery_slot": slot_json(o.delivery_time_slot),
        "price": {"subtotal": m(p.subtotal), "discount": m(p.discount), "delivery_fee": m(p.delivery_fee),
                  "gst": m(p.gst), "qst": m(p.qst), "total": m(p.total), "final_total": m(o.final_total)},
        "promotion": o.applied_promotion.code if o.applied_promotion else None,
        "reward": ({"id": o.applied_reward.reward_id, "name": o.applied_reward.name,
                    "points": o.applied_reward.points_required, "discount": m(o.applied_reward.discount_amount)}
                   if o.applied_reward else
                   ({"id": redemption.reward.reward_id, "name": redemption.reward.name, "points": redemption.points,
                     "discount": m(redemption.reward.discount_amount)} if redemption else None)),
        "reward_state": reward_state,
        "loyalty": account_json(account),
        "payment": ({"id": payment.payment_id, "status": payment.status.value, "amount": m(payment.amount),
                     "method": payment.payment_method.label, "receipt": payment.receipt_number}
                    if payment else None),
        "attempts": len(o.payment_attempts),
        "last_attempt_status": last_attempt.status.value if last_attempt else None,
        "latest": status_json(latest),
        "history": [status_json(u) for u in o.status_history],
        "progress": {"steps": flow, "index": flow.index(o.status.value) if o.status.value in flow else -1},
        "next_status": o.next_status().value if o.next_status() else None,
        "stops": len(o.route_stops),
    }


class ZippyWashAPI:
    def __init__(self, repo):
        self.repo = repo
        world = repo.load()
        if not world.all(Customer):
            seed(repo)

    # ---------------------------------------------------------------------
    def call(self, name: str, payload: dict | str | None = None) -> dict:
        if isinstance(payload, str):
            payload = json.loads(payload or "{}")
        payload = payload or {}
        handler = getattr(self, f"op_{name}", None)
        if handler is None:
            return {"ok": False, "error": f"Unknown action '{name}'."}
        self.world = self.repo.load()
        ensure_rolling_slots(self.world)
        try:
            data = handler(**payload)
            self.repo.commit(self.world)
            return {"ok": True, "data": data}
        except DomainError as err:
            self.repo.commit(self.world)        # keep what the domain already recorded (e.g. a failed attempt)
            return {"ok": False, "error": str(err)}
        except (KeyError, ValueError, TypeError, AttributeError) as err:
            return {"ok": False, "error": f"Something went wrong: {err}"}

    def call_json(self, name: str, payload_json: str = "{}") -> str:
        """String in, string out: the form used from JavaScript."""
        return json.dumps(self.call(name, payload_json))

    # ---------------------------------------------------------------------
    def _get(self, cls, key):
        obj = self.world.get(cls, key)
        if obj is None:
            raise DomainError(f"{cls.__name__} {key} not found.")
        return obj

    def _customer(self, customer_id) -> Customer:
        return self._get(Customer, customer_id)

    def _staff(self, staff_id) -> StaffMember:
        return self._get(StaffMember, staff_id)

    def _order(self, order_id, customer_id=None) -> Order:
        order = next((o for o in self.world.all(Order) if o.order_id == order_id), None)
        if order is None or (customer_id and order.customer.customer_id != customer_id):
            raise DomainError("Order not found.")
        return order

    # =====================================================================
    # General
    # =====================================================================
    def op_reset(self):
        """Throw away every change and reload the sample data."""
        from zippywash.database.repository import InMemoryRepository
        if isinstance(self.repo, InMemoryRepository):
            self.repo.world = None
        else:
            from zippywash.database.db import create_schema, drop_all_tables
            drop_all_tables(self.repo.conn)
            create_schema(self.repo.conn)
        seed(self.repo)
        self.world = self.repo.load()
        return self.op_bootstrap()

    def op_bootstrap(self):
        rank = {StaffRole.DRIVER: 0, StaffRole.LAUNDRY_STAFF: 1, StaffRole.ADMINISTRATOR: 2}
        return {
            "today": iso(today_local()),
            "customers": [{"id": c.customer_id, "name": c.name, "active": c.is_active()}
                          for c in sorted(self.world.all(Customer), key=lambda c: c.name)],
            "staff": [{"id": s.staff_member_id, "name": s.name, "roles": [r.value for r in s.roles]}
                      for s in sorted(self.world.all(StaffMember), key=lambda s: min(rank[r] for r in s.roles))],
        }

    # =====================================================================
    # UC01 / UC05 / UC07 — booking checkout
    # =====================================================================
    def op_booking_options(self, customer_id):
        c = self._customer(customer_id)
        draft = next((o for o in c.orders if o.status == OrderStatus.DRAFT), None)
        return {
            "active": c.is_active(),
            "services": [{"id": s.service_type_id, "name": s.name, "rate": m(s.base_rate),
                          "quotes": {b.value: self._quote(s, b) for b in BagSize}}
                         for s in self.world.all(ServiceType) if s.active],
            "bag_sizes": [b.value for b in BagSize],
            "addresses": [address_json(a) for a in c.addresses if a.validate()],
            "pickup_types": [t.value for t in PickupRequestType],
            "draft": draft.order_id if draft else None,
        }

    @staticmethod
    def _quote(service, size):
        """Price before any discount, with the same rules as Order.calculate_estimate (shown on Step 1)."""
        subtotal = service.calculate_base_price(size)
        taxable = subtotal + DELIVERY_FEE
        gst, qst = money(taxable * GST_RATE), money(taxable * QST_RATE)
        return {"subtotal": m(subtotal), "delivery_fee": m(DELIVERY_FEE), "gst": m(gst), "qst": m(qst),
                "total": m(money(taxable + gst + qst))}

    def op_start_booking(self, customer_id, pickup_address_id, delivery_address_id, service_type_id, bag_size,
                         pickup_request_type="Scheduled"):
        c = self._customer(customer_id)
        addr = {a.address_id: a for a in c.addresses}
        if pickup_address_id not in addr or delivery_address_id not in addr:
            raise DomainError("Choose one of your saved addresses.")
        order = BookingService(self.world).start_booking(
            c, addr[pickup_address_id], addr[delivery_address_id], self._get(ServiceType, service_type_id),
            BagSize(bag_size), PickupRequestType(pickup_request_type))
        return {"order_id": order.order_id}

    def op_order(self, customer_id, order_id):
        return order_json(self._order(order_id, customer_id))

    def op_open_slots(self, customer_id, order_id):
        self._order(order_id, customer_id)
        return [slot_json(s) for s in BookingService(self.world).open_slots(now_local())]

    def op_choose_slots(self, customer_id, order_id, pickup_slot_id, delivery_slot_id):
        o = self._order(order_id, customer_id)
        BookingService(self.world).choose_slots(o, self._get(TimeSlot, pickup_slot_id),
                                                self._get(TimeSlot, delivery_slot_id))
        return order_json(o)

    def op_apply_promo(self, customer_id, order_id, code):
        o = self._order(order_id, customer_id)
        BookingService(self.world).apply_promo_code(o, code)
        return order_json(o)

    def op_remove_promo(self, customer_id, order_id):
        o = self._order(order_id, customer_id)
        BookingService(self.world).remove_promo_code(o)
        return order_json(o)

    def op_reward_options(self, customer_id, order_id):
        o = self._order(order_id, customer_id)
        return {"loyalty": account_json(o.customer.loyalty_account), "promotion": o.applied_promotion is not None,
                "rewards": [{"id": r.reward_id, "name": r.name, "points": r.points_required,
                             "discount": m(r.discount_amount), "eligible": why is None, "reason": why}
                            for r, why in BookingService(self.world).reward_options(o)]}

    def op_reserve_reward(self, customer_id, order_id, reward_id):
        o = self._order(order_id, customer_id)
        BookingService(self.world).reserve_reward(o, self._get(Reward, reward_id))
        return order_json(o)

    def op_release_reward(self, customer_id, order_id):
        o = self._order(order_id, customer_id)
        restored = BookingService(self.world).release_reward(o)
        return {"order": order_json(o), "restored_points": restored.points if restored else 0}

    def op_payment_methods(self, customer_id):
        return [method_json(pm) for pm in self._customer(customer_id).payment_methods if pm.active]

    def op_pay(self, customer_id, order_id, payment_method_id):
        o = self._order(order_id, customer_id)
        method = next((pm for pm in o.customer.payment_methods if pm.payment_method_id == payment_method_id), None)
        if method is None:
            raise DomainError("Choose one of your saved payment methods.")
        outcome = BookingService(self.world).pay(o, method)
        return {"authorized": outcome.authorized, "message": outcome.message,
                "payment_status": outcome.payment.status.value, "method": method.label,
                "redeemed_points": outcome.redeemed.points if outcome.redeemed else 0,
                "restored_points": outcome.restored.points if outcome.restored else 0,
                "order": order_json(o)}

    def op_cancel_checkout(self, customer_id, order_id):
        o = self._order(order_id, customer_id)
        BookingService(self.world).cancel_checkout(o)
        return {"cancelled": True}

    def op_repeat_booking(self, customer_id, order_id):
        """Book again: a new draft with the same details (Order.create_repeat_booking)."""
        o = self._order(order_id, customer_id)
        for old in list(o.customer.orders):
            if old.status == OrderStatus.DRAFT:
                old.cancel()
        repeat = o.create_repeat_booking()
        return {"order_id": repeat.order_id}

    # =====================================================================
    # UC02 / UC06 — my orders, profile
    # =====================================================================
    def op_my_orders(self, customer_id):
        return [order_json(o) for o in OrderTrackingService.my_orders(self._customer(customer_id))]

    def op_order_status(self, customer_id, order_id):
        c = self._customer(customer_id)
        return order_json(OrderTrackingService.order_for(c, order_id))

    def op_profile(self, customer_id):
        c = self._customer(customer_id)
        return {"id": c.customer_id, "name": c.name, "contact": c.contact_details,
                "preferences": c.service_preferences, "active": c.is_active(),
                "addresses": [address_json(a) for a in c.addresses],
                "methods": [method_json(pm) for pm in c.payment_methods],
                "notifications": [{"type": n.type.value, "message": n.message, "at": iso(n.created_at),
                                   "status": n.delivery_status.value}
                                  for n in sorted(c.notifications, key=lambda n: n.created_at, reverse=True)[:12]],
                "orders": len(c.view_order_history())}

    def op_update_profile(self, customer_id, name, contact, preferences=None):
        CustomerProfileService.update_profile(self._customer(customer_id), name, contact, preferences)
        return self.op_profile(customer_id)

    def op_add_address(self, customer_id, street, postal_code, access=None):
        a = CustomerProfileService(self.world).add_address(self._customer(customer_id), street, postal_code, access)
        return {"address": address_json(a), "profile": self.op_profile(customer_id)}

    def op_add_payment_method(self, customer_id, label, kind="CreditCard"):
        """Demo only: the provider's secure form would return a token; here we make a test token."""
        CustomerProfileService.add_payment_method(self._customer(customer_id), f"tok_demo_{new_id('T')}",
                                                  PaymentMethodType(kind), label)
        return self.op_profile(customer_id)

    def op_deactivate_account(self, customer_id):
        CustomerProfileService.deactivate_account(self._customer(customer_id))
        return self.op_profile(customer_id)

    # =====================================================================
    # UC07 — loyalty
    # =====================================================================
    def op_loyalty(self, customer_id):
        c = self._customer(customer_id)
        acc = c.loyalty_account
        rewards = [{"id": r.reward_id, "name": r.name, "points": r.points_required, "discount": m(r.discount_amount)}
                   for r in sorted(self.world.all(Reward), key=lambda r: r.points_required) if r.is_available()]
        if acc is None:
            return {"account": None, "rewards": rewards, "activity": []}
        s = acc.view_loyalty_summary()
        return {"account": account_json(acc), "rewards": rewards,
                "activity": [{"type": ACTIVITY[t.type], "points": t.points, "at": iso(t.created_at),
                              "details": t.reason, "order": t.order.order_id if t.order else None}
                             for t in s.recent_transactions]}

    def op_join_loyalty(self, customer_id):
        CustomerProfileService.join_loyalty(self._customer(customer_id))
        return self.op_loyalty(customer_id)

    # =====================================================================
    # Staff — UC02 status board
    # =====================================================================
    def op_staff_board(self, staff_id):
        s = self._staff(staff_id)
        orders = OrderTrackingService(self.world).active_orders()
        out = []
        for o in orders:
            j = order_json(o)
            nxt = o.next_status()
            needed = ROLE_FOR_STATUS.get(nxt) if nxt else None
            j["can_advance"] = bool(nxt) and (needed is None or s.check_authorization(needed))
            j["needed_role"] = needed.value if needed else None
            j["can_cancel"] = o.status == OrderStatus.SCHEDULED and s.check_authorization(StaffRole.ADMINISTRATOR)
            out.append(j)
        counts = {st.value: sum(1 for o in self.world.all(Order) if o.status == st)
                  for st in STATUS_SEQUENCE[1:] + [OrderStatus.CANCELLED]}
        return {"orders": out, "counts": counts}

    def op_advance_status(self, staff_id, order_id, notes=None):
        o = self._order(order_id)
        OrderTrackingService.advance_status(o, self._staff(staff_id), notes)
        return order_json(o)

    def op_cancel_order(self, staff_id, order_id):
        s = self._staff(staff_id)
        if not s.check_authorization(StaffRole.ADMINISTRATOR):
            raise DomainError("Only an administrator can cancel and refund an order.")
        o = self._order(order_id)
        OrderTrackingService.cancel_order(o, s)
        return order_json(o)

    # =====================================================================
    # Staff — UC04 routes
    # =====================================================================
    def _route_json(self, r: Route) -> dict:
        return {"id": r.route_id, "date": iso(r.route_date), "status": r.status.value,
                "sector": r.sector.name if r.sector else None, "vehicle": r.vehicle.vehicle_id if r.vehicle else None,
                "capacity": r.vehicle.slot_capacity if r.vehicle else 0, "occupied": r.occupied_slots,
                "available": r.calculate_available_slots(), "distance": f"{r.total_distance:.1f}",
                "driver": r.staff_shift.staff_member.name if r.staff_shift else None,
                "flagged": [o.order_id for o in r.flagged_orders],
                "stops": [{"id": x.route_stop_id, "seq": x.sequence_number, "type": x.stop_type.value,
                           "order": x.order.order_id, "customer": x.order.customer.name, "address": x.address.label(),
                           "postal": x.address.postal_code, "eta": x.estimated_arrival_time.strftime("%H:%M")
                           if x.estimated_arrival_time else None, "status": x.status.value}
                          for x in sorted(r.stops, key=lambda x: x.sequence_number)]}

    def op_routes(self, staff_id):
        self._staff(staff_id)
        shifts = [sh for st in self.world.all(StaffMember) for sh in st.shifts
                  if sh.route is None and sh.shift_date >= today_local() and StaffRole.DRIVER in sh.staff_member.roles]
        live = [o for o in OrderTrackingService(self.world).active_orders()
                if o.pickup_request_type == PickupRequestType.LIVE and o.status == OrderStatus.SCHEDULED
                and not o.route_stops]
        scheduled_by_day = {}
        for o in self.world.all(Order):
            if o.status == OrderStatus.SCHEDULED and o.pickup_time_slot and not o.route_stops:
                k = iso(o.pickup_time_slot.date)
                scheduled_by_day[k] = scheduled_by_day.get(k, 0) + 1
        return {"routes": [self._route_json(r) for r in sorted(self.world.all(Route), key=lambda r: r.route_date)],
                "shifts": [{"id": sh.staff_shift_id, "date": iso(sh.shift_date), "start": sh.start_time.strftime("%H:%M"),
                            "end": sh.end_time.strftime("%H:%M"), "driver": sh.staff_member.name,
                            "orders_waiting": scheduled_by_day.get(iso(sh.shift_date), 0)}
                           for sh in sorted(shifts, key=lambda x: x.shift_date)],
                "sectors": [{"id": x.sector_id, "name": x.name, "boundary": x.boundary}
                            for x in self.world.all(Sector) if x.active],
                "vehicles": [{"id": v.vehicle_id, "capacity": v.slot_capacity, "status": v.status.value}
                             for v in self.world.all(Vehicle)],
                "live_orders": [{"id": o.order_id, "customer": o.customer.name} for o in live]}

    def op_build_route(self, staff_id, shift_id, sector_id, vehicle_id):
        self._staff(staff_id)
        shift = self._get(StaffShift, shift_id)
        r = OperationsService(self.world).build_route(shift, self._get(Sector, sector_id),
                                                      self._get(Vehicle, vehicle_id), shift.shift_date)
        return self._route_json(r)

    def op_optimize_route(self, staff_id, route_id):
        r = self._get(Route, route_id)
        r.optimize()
        return self._route_json(r)

    def op_finalize_route(self, staff_id, route_id):
        r = self._get(Route, route_id)
        r.finalize_route()
        return self._route_json(r)

    def op_insert_live_pickup(self, staff_id, route_id, order_id):
        r = self._get(Route, route_id)
        ok = OperationsService.insert_live_pickup(r, self._order(order_id))
        if not ok:
            raise DomainError("That pickup can't be added (sector, vehicle capacity or route status).")
        return self._route_json(r)

    def op_complete_stop(self, staff_id, stop_id):
        stop = self._get(RouteStop, stop_id)
        stop.mark_completed()
        return self._route_json(stop.route)

    # =====================================================================
    # Staff — UC03 machines and inventory
    # =====================================================================
    def op_machines(self, staff_id):
        self._staff(staff_id)
        upcoming = sorted((t for t in self.world.all(TimeSlot) if t.date >= today_local()),
                          key=lambda t: t.starts_at())[:6]
        out = []
        for mc in self.world.all(Machine):
            rec = mc.open_record()
            out.append({"id": mc.machine_id, "type": mc.type.value, "status": mc.status.value,
                        "capacity": f"{mc.calculate_capacity()}", "cycle": mc.current_cycle,
                        "open_record": ({"id": rec.maintenance_record_id, "fault": rec.fault_description,
                                         "status": rec.status.value, "scheduled": iso(rec.scheduled_date),
                                         "details": rec.repair_details,
                                         "managed_by": rec.managed_by.name if rec.managed_by else None}
                                        if rec else None),
                        "history": len(mc.maintenance_history)})
        return {"machines": out, "slots": [slot_json(t) for t in upcoming]}

    def op_report_fault(self, staff_id, machine_id, description):
        OperationsService.report_fault(self._get(Machine, machine_id), description, self._staff(staff_id))
        return self.op_machines(staff_id)

    def op_schedule_repair(self, staff_id, record_id, repair_date=None):
        rec = self._get(MaintenanceRecord, record_id)
        when = date.fromisoformat(repair_date) if repair_date else today_local()
        rec.schedule(when, self._staff(staff_id))
        return self.op_machines(staff_id)

    def op_repair_details(self, staff_id, record_id, details):
        self._get(MaintenanceRecord, record_id).update_repair_details(details)
        return self.op_machines(staff_id)

    def op_complete_repair(self, staff_id, record_id):
        self._get(MaintenanceRecord, record_id).complete()
        return self.op_machines(staff_id)

    def op_inventory(self, staff_id):
        self._staff(staff_id)
        return [{"id": i.inventory_item_id, "name": i.name, "quantity": f"{i.quantity_on_hand}",
                 "reorder": f"{i.reorder_level}", "low": i.check_reorder_level(), "alert": i.alert_open,
                 "movements": [{"type": mv.type.value, "quantity": f"{mv.quantity}", "at": iso(mv.recorded_at),
                                "by": mv.recorded_by.name if mv.recorded_by else None}
                               for mv in sorted(i.movements, key=lambda x: x.recorded_at, reverse=True)[:5]]}
                for i in self.world.all(InventoryItem)]

    def op_record_stock(self, staff_id, item_id, movement_type, quantity):
        OperationsService.record_stock(self._get(InventoryItem, item_id), StockMovementType(movement_type),
                                       Decimal(str(quantity)), self._staff(staff_id))
        return self.op_inventory(staff_id)

    # =====================================================================
    # Staff — loyalty and promotions admin
    # =====================================================================
    def op_loyalty_admin(self, staff_id):
        self._staff(staff_id)
        return {"accounts": [{"customer": a.customer.name, **account_json(a)}
                             for a in self.world.all(LoyaltyAccount)],
                "rewards": [{"id": r.reward_id, "name": r.name, "points": r.points_required,
                             "discount": m(r.discount_amount), "active": r.active,
                             "from": iso(r.available_from), "until": iso(r.expiry_date)}
                            for r in sorted(self.world.all(Reward), key=lambda r: r.points_required)],
                "promotions": [{"id": p.promotion_id, "code": p.code, "discount": m(p.discount_value),
                                "active": p.active, "expires": iso(p.expiry_date)} for p in self.world.all(Promotion)]}

    def op_correct_points(self, staff_id, account_id, points, reason):
        self._get(LoyaltyAccount, account_id).correct_points(int(points), reason, self._staff(staff_id))
        return self.op_loyalty_admin(staff_id)

    def op_toggle_reward(self, staff_id, reward_id):
        s = self._staff(staff_id)
        if not s.check_authorization(StaffRole.ADMINISTRATOR):
            raise DomainError("Only an administrator can change rewards.")
        r = self._get(Reward, reward_id)
        r.deactivate() if r.active else r.activate()
        return self.op_loyalty_admin(staff_id)

    def op_toggle_promotion(self, staff_id, promotion_id):
        s = self._staff(staff_id)
        if not s.check_authorization(StaffRole.ADMINISTRATOR):
            raise DomainError("Only an administrator can change promo codes.")
        p = self._get(Promotion, promotion_id)
        p.active = not p.active
        return self.op_loyalty_admin(staff_id)
