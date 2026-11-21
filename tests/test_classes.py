"""Unit tests for every other Milestone 5 method: happy path, validation and state rules."""
from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from zippywash.common import (AccountStatus, BagSize, DeliveryStatus, DomainError, LoyaltyAccountStatus,
                              LoyaltyTransactionType as T, MachineStatus, MachineType, MaintenanceStatus,
                              NotificationType, OrderStatus, PaymentMethodType, PaymentStatus, PickupRequestType,
                              ShiftStatus, StaffRole, StockMovementType, StopStatus, StopType, VehicleStatus,
                              today_local)
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
from zippywash.customer_order_service.notification import Notification
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
from zippywash.operations_resource.route_stop import RouteStop
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.stock_movement import StockMovement
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.customer_profile_service import CustomerProfileService


# ---------------- Customer ----------------
def test_customer_profile_and_ownership(kit):
    c = kit.customer
    c.update_profile("  New Name ", "514-555-0000", "  ")
    assert (c.name, c.service_preferences) == ("New Name", None)
    with pytest.raises(DomainError):
        c.update_profile("", "a@b.c")
    with pytest.raises(DomainError):
        c.update_profile("Name", "no contact")
    with pytest.raises(DomainError, match="already saved"):
        c.add_address(Address("ADR-DUP", "1 test st", "h3h1k6"))
    with pytest.raises(DomainError, match="another customer"):
        kit.stranger.add_address(kit.home)
    with pytest.raises(DomainError, match="another customer"):
        c.add_payment_method(kit.other_card)
    c.add_payment_method(kit.visa)                      # same object again: no duplicate insertion
    assert c.payment_methods.count(kit.visa) == 1


def test_order_history_only_placed_orders_newest_first(kit):
    first = kit.paid_order()
    kit.order()                                         # a checkout in progress is not history
    second = kit.paid_order(p=(1, 12))
    assert kit.customer.view_order_history() == [second, first]
    assert kit.stranger.view_order_history() == []


def test_deactivate_keeps_history_and_blocks_booking(kit):
    placed = kit.paid_order()
    kit.customer.deactivate_account()
    assert kit.customer.account_status == AccountStatus.DEACTIVATED
    assert kit.customer.view_order_history() == [placed]
    with pytest.raises(DomainError, match="deactivated"):
        kit.order()
    with pytest.raises(DomainError):
        kit.customer.deactivate_account()


# ---------------- Address / Sector ----------------
def test_address_validate_and_assign_sector(kit):
    assert kit.home.validate() and kit.home.sector is kit.sector and kit.home in kit.sector.addresses
    assert not kit.outside.validate() and kit.outside.sector is None
    with pytest.raises(DomainError, match="outside"):
        kit.home.assign_sector(kit.other_sector)
    bad = Address("ADR-B", "", "XYZ")
    assert not bad.validate()
    kit.sector.active = False
    assert not kit.home.validate()


def test_sector_driver_assignment_both_sides(kit):
    kit.sector.assign_driver(kit.driver)
    assert kit.driver.assigned_sector is kit.sector and kit.driver in kit.sector.assigned_drivers
    kit.driver.assign_sector(kit.other_sector)
    assert kit.driver not in kit.sector.assigned_drivers and kit.driver in kit.other_sector.assigned_drivers
    with pytest.raises(DomainError):
        kit.sector.assign_driver(kit.laundry)
    kit.sector.active = False
    with pytest.raises(DomainError):
        kit.sector.assign_driver(kit.driver)


# ---------------- ServiceType / TimeSlot / OrderItem ----------------
def test_service_type_pricing():
    s = ServiceType("S", "Delicates", Decimal("34.99"))
    assert s.calculate_base_price(BagSize.LARGE) == Decimal("69.98")
    with pytest.raises(DomainError):
        s.calculate_base_price("Huge")
    s.deactivate()
    with pytest.raises(DomainError):
        s.calculate_base_price(BagSize.SMALL)
    with pytest.raises(DomainError):
        ServiceType("S2", "Bad", Decimal("-1"))


def test_time_slot_capacity_rules():
    s = TimeSlot("T", today_local(), time(8), 2)
    assert s.check_capacity(2) and not s.check_capacity(3)
    assert not s.reserve_capacity(3) and s.available_capacity == 2      # all or nothing
    assert s.reserve_capacity(2) and s.available_capacity == 0
    s.release_capacity(1)
    with pytest.raises(DomainError):
        s.release_capacity(5)
    with pytest.raises(DomainError):
        s.check_capacity(0)


def test_time_slot_recalculates_from_machines():
    s = TimeSlot("T", today_local(), time(8), 4)
    w, d = Machine("W", MachineType.WASHER, Decimal("18")), Machine("D", MachineType.DRYER, Decimal("15"))
    for m in (w, d):
        s.contributing_machines.append(m)
        m.time_slots.append(s)
    assert s.recalculate_capacity() == 4
    s.reserve_capacity(1)
    w.update_status(MachineStatus.FAULTY)               # the slot loses one machine's share
    assert (s.capacity_limit, s.available_capacity) == (2, 1)
    w.update_status(MachineStatus.OPERATIONAL)
    assert s.available_capacity == 3


def test_order_item_line_total():
    item = OrderItem("I", 3)
    assert item.calculate_line_total(Decimal("10.005")) == Decimal("30.03") and item.unit_price == Decimal("10.01")
    with pytest.raises(DomainError):
        item.calculate_line_total(Decimal("-1"))
    with pytest.raises(DomainError):
        OrderItem("I2", 0)


# ---------------- Promotion / PaymentMethod ----------------
def test_promotion_eligibility(kit):
    o = kit.order()
    p = Promotion("P", "ten", Decimal("10"), expiry_date=today_local() - timedelta(days=1))
    assert p.code == "TEN" and not p.validate_eligibility(o)
    with pytest.raises(DomainError, match="expired"):
        p.calculate_discount(o)
    assert not Promotion("Q", "OFF", Decimal("5"), active=False).validate_eligibility(o)
    assert Promotion("R", "OK", Decimal("5")).calculate_discount(o) == Decimal("5.00")


def test_payment_method_validate(kit):
    assert kit.visa.validate()
    kit.visa.deactivate()
    assert not kit.visa.validate()
    kit.visa.activate()
    assert not PaymentMethod("X", "4242424242424242", PaymentMethodType.CREDIT_CARD, kit.customer).validate()
    assert not PaymentMethod("Y", "tok_ok", "Cash", kit.customer).validate()


# ---------------- Order ----------------
def test_confirm_needs_authorized_payment_and_reserves_both_slots(kit):
    o = kit.order()
    with pytest.raises(DomainError, match="authorized"):
        o.confirm()
    p = Payment.create_attempt(o, o.estimated_total, kit.visa)
    p.record_result(p.authorize())
    o.confirm()
    assert o.status == OrderStatus.SCHEDULED and o.final_total == Decimal("34.47")
    assert (o.pickup_time_slot.available_capacity, o.delivery_time_slot.available_capacity) == (3, 3)


def test_confirm_is_atomic_when_a_slot_is_full(kit):
    o = kit.order()
    p = Payment.create_attempt(o, o.estimated_total, kit.visa)
    p.record_result(p.authorize())
    o.delivery_time_slot.reserve_capacity(4)
    with pytest.raises(DomainError, match="filled"):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.pickup_time_slot.available_capacity == 4


def test_status_history_append_only_with_roles(kit):
    o = kit.paid_order()
    assert o.get_current_status().status == OrderStatus.SCHEDULED
    with pytest.raises(DomainError, match="driver"):
        o.update_status(OrderStatus.PICKED_UP, kit.laundry)
    with pytest.raises(DomainError, match="Next status"):
        o.update_status(OrderStatus.WASHING, kit.admin)
    with pytest.raises(DomainError, match="staff"):
        o.update_status(OrderStatus.PICKED_UP)
    u = o.update_status(OrderStatus.PICKED_UP, kit.driver, "Bag collected")
    assert o.status == OrderStatus.PICKED_UP and o.get_current_status() is u and u in kit.driver.status_updates
    assert [x.status for x in o.status_history] == [OrderStatus.DRAFT, OrderStatus.SCHEDULED, OrderStatus.PICKED_UP]
    with pytest.raises(DomainError, match="can't be changed"):
        u.notes = "edited"


def test_record_status_change_validates_transition(kit):
    o = kit.paid_order()
    with pytest.raises(DomainError):
        OrderStatusUpdate.record_status_change(o, OrderStatus.DELIVERED, kit.admin)
    assert len(o.status_history) == 2


def test_cancel_rules(kit):
    o = kit.paid_order()
    assert o.cancel() is True
    assert o.status == OrderStatus.CANCELLED and o.pickup_time_slot.available_capacity == 4
    later = kit.paid_order(p=(1, 12))
    later.update_status(OrderStatus.PICKED_UP, kit.driver)
    assert later.cancel() is False and later.status == OrderStatus.PICKED_UP


def test_repeat_booking_copies_details_only(kit):
    o = kit.paid_order(bag=BagSize.LARGE, delivery=kit.work, pickup_request_type=PickupRequestType.LIVE)
    r = o.create_repeat_booking()
    assert r.order_id != o.order_id and r.status == OrderStatus.DRAFT
    assert (r.customer, r.pickup_address, r.delivery_address, r.service_type, r.bag_size, r.pickup_request_type) == (
        o.customer, o.pickup_address, o.delivery_address, o.service_type, o.bag_size, o.pickup_request_type)
    assert not r.payment_attempts and r.pickup_time_slot is None and len(r.status_history) == 1
    assert r.order_items[0] is not o.order_items[0]
    with pytest.raises(DomainError):
        r.create_repeat_booking()


def test_calculate_final_total_needs_payment(kit):
    o = kit.order()
    with pytest.raises(DomainError):
        o.calculate_final_total()


# ---------------- Notification ----------------
def test_notification_create_send_deliver(kit):
    with pytest.raises(DomainError):
        Notification.create(NotificationType.STATUS_CHANGED, "  ", kit.customer)
    with pytest.raises(DomainError):
        Notification.create(NotificationType.STATUS_CHANGED, "Hi")
    n = Notification.create(NotificationType.STATUS_CHANGED, "Hi", kit.customer)
    assert n in kit.customer.notifications
    with pytest.raises(DomainError):
        n.mark_delivered()
    assert n.send() == DeliveryStatus.SENT
    n.mark_delivered()
    n.mark_delivered()                                  # idempotent
    assert n.delivery_status == DeliveryStatus.DELIVERED
    unreachable = StaffMember("S", "No Contact", " ", [StaffRole.DRIVER])
    assert Notification.create(NotificationType.ROUTE_ASSIGNED, "Route", staff_recipient=unreachable).send() \
        == DeliveryStatus.FAILED


# ---------------- Payment ----------------
def test_payment_result_receipt_refund(kit, processor):
    o = kit.order()
    p = Payment.create_attempt(o, o.estimated_total, kit.visa)
    with pytest.raises(DomainError):
        p.generate_receipt()
    assert p.refund() is False
    with pytest.raises(DomainError):
        p.record_result(PaymentStatus.REFUNDED)
    p.record_result(PaymentStatus.AUTHORIZED)
    with pytest.raises(DomainError):
        p.record_result(PaymentStatus.FAILED)
    receipt = p.generate_receipt()
    assert p.generate_receipt() == receipt                # generated once
    assert p.refund() is True and p.status == PaymentStatus.REFUNDED and len(processor.refund_calls) == 1
    assert p.refund() is False


# ---------------- Loyalty ----------------
def test_loyalty_lifecycle(kit):
    account = kit.member(0)
    assert account.status == LoyaltyAccountStatus.ACTIVE and account.transactions[0].type == T.ENROLLMENT
    with pytest.raises(DomainError):
        account.enroll()
    s = account.view_loyalty_summary()
    assert (s.point_balance, s.available_points) == (0, 0)
    account.deactivate()
    with pytest.raises(DomainError):
        account.deactivate()
    account.reactivate()
    with pytest.raises(DomainError):
        account.reactivate()


def test_award_points_once_from_paid_amount(kit):
    account = kit.member(0)
    o = kit.paid_order()
    earned = account.award_points(o)
    assert earned.points == 34 and account.point_balance == 34 and earned.applied_rule is kit.rule
    with pytest.raises(DomainError, match="already"):
        account.award_points(o)
    with pytest.raises(DomainError, match="paid"):
        account.award_points(kit.order(p=(1, 12)))


def test_correct_points_needs_admin_and_reason(kit):
    account = kit.member(100)
    with pytest.raises(DomainError):
        account.correct_points(10, "reason", kit.laundry)
    with pytest.raises(DomainError):
        account.correct_points(10, " ", kit.admin)
    with pytest.raises(DomainError):
        account.correct_points(-500, "too much", kit.admin)
    t = account.correct_points(-40, "Duplicate award", kit.admin)
    assert account.point_balance == 60 and t.authorized_by is kit.admin
    assert t in kit.admin.authorized_loyalty_transactions


def test_reverse_points_after_refund(kit):
    account = kit.member(0)
    o = kit.paid_order()
    earned = account.award_points(o)
    reversal = account.reverse_points(o.authorized_payment())
    assert reversal.type == T.REVERSAL and reversal.reverses is earned and account.point_balance == 0
    with pytest.raises(DomainError):
        account.reverse_points(o.authorized_payment())


def test_deactivate_restores_held_points(kit):
    account = kit.member(420)
    o = kit.order()
    account.reserve_points(kit.reward, o)
    restored = account.deactivate()
    assert restored.type == T.RESTORATION and account.reserved_points() == 0 and o.applied_reward is None


def test_ledger_entries_are_immutable_and_post_once(kit):
    account = kit.member(0)
    t = account.transactions[0]
    with pytest.raises(DomainError):
        t.post()
    with pytest.raises(DomainError):
        t.points = 999
    bad = LoyaltyTransaction.create(T.EARN, 10, account)          # no order or rule
    assert not bad.validate()
    with pytest.raises(DomainError):
        bad.post()
    with pytest.raises(DomainError):
        t.reverse()                                               # enrollment can't be reversed


def test_reward_rules(kit):
    account = kit.member(300)
    r = Reward("R", "Thing", 100, Decimal("5"))
    with pytest.raises(DomainError):
        r.schedule_availability(date(2026, 5, 1), date(2026, 4, 1))
    r.schedule_availability(today_local() - timedelta(days=1), today_local() + timedelta(days=1))
    assert r.validate_eligibility(account, kit.order())
    r.deactivate()
    assert not r.validate_eligibility(account, kit.order())
    r.activate()
    with pytest.raises(DomainError):
        Reward("Z", "Zero", 0, Decimal("1"))


def test_loyalty_rule(kit):
    rule = LoyaltyRule("LR2", Decimal("0"), today_local())
    assert not rule.validate()
    with pytest.raises(DomainError):
        rule.activate()
    assert rule.calculate_points(kit.paid_order()) == 0
    kit.rule.deactivate()
    assert LoyaltyRule.current_rule() is None
    kit.rule.activate()
    assert LoyaltyRule.current_rule() is kit.rule


# ---------------- Staff / shifts / vehicles ----------------
def test_staff_roles_and_shifts(kit):
    d = kit.driver
    with pytest.raises(DomainError):
        d.assign_role(StaffRole.DRIVER)
    d.assign_role(StaffRole.LAUNDRY_STAFF)
    d.unassign_role(StaffRole.LAUNDRY_STAFF)
    with pytest.raises(DomainError):
        d.unassign_role(StaffRole.DRIVER)
    with pytest.raises(DomainError):
        StaffMember("S", "N", "c", [])
    day = today_local()
    shift = d.schedule_shift(day, time(7), time(15))
    assert shift in d.shifts and shift.staff_member is d
    with pytest.raises(DomainError, match="already has a shift"):
        d.schedule_shift(day, time(14), time(18))
    with pytest.raises(DomainError):
        d.schedule_shift(day, time(18), time(17))
    assert d.check_authorization(StaffRole.DRIVER) and not d.check_authorization(StaffRole.ADMINISTRATOR)
    assert kit.admin.check_authorization(StaffRole.DRIVER)


def test_shift_availability_and_route_assignment(kit):
    shift = kit.driver.schedule_shift(today_local(), time(7), time(15))
    assert shift.check_availability(today_local()) and not shift.check_availability(today_local() + timedelta(1))
    route = Route("R1", today_local())
    shift.assign_route(route)
    assert route.staff_shift is shift and not shift.check_availability(today_local())
    with pytest.raises(DomainError):
        shift.assign_route(Route("R2", today_local()))
    laundry_shift = kit.laundry.schedule_shift(today_local(), time(8), time(16))
    assert not laundry_shift.check_availability(today_local())
    shift.status = ShiftStatus.CANCELLED
    assert not shift.check_availability(today_local())


def test_vehicle_capacity():
    v = Vehicle("V", 3)
    assert v.check_capacity(3) and not v.check_capacity(4)
    v.update_availability(VehicleStatus.MAINTENANCE)
    assert v.status == VehicleStatus.MAINTENANCE
    with pytest.raises(DomainError):
        Vehicle("V0", 0)


# ---------------- Route operations / RouteStop ----------------
def _built_route(kit, n=2, capacity=12):
    orders = [kit.paid_order(p=(1, h), d=(2, 17), delivery=kit.work if h == 12 else kit.home)
              for h in (8, 12, 17)[:n]]
    shift = kit.driver.schedule_shift(kit.slots[(1, 8)].date, time(7), time(15))
    route = Route("RTE", kit.slots[(1, 8)].date)
    shift.assign_route(route)
    route.build(route.route_date, kit.sector, Vehicle("V", capacity))
    return route, orders


def test_optimize_keeps_membership_and_pickup_first(kit):
    route, _ = _built_route(kit)
    members = {s.route_stop_id for s in route.stops}
    route.optimize()
    assert {s.route_stop_id for s in route.stops} == members
    for s in route.stops:
        if s.stop_type == StopType.DELIVERY:
            assert s.partner().sequence_number < s.sequence_number
    assert all(s.estimated_arrival_time for s in route.stops) and route.total_distance > 0


def test_finalize_locks_route(kit):
    route, _ = _built_route(kit)
    with pytest.raises(DomainError, match="Optimize"):
        route.finalize_route()
    route.optimize()
    route.finalize_route()
    with pytest.raises(DomainError, match="finalized"):
        route.optimize()
    with pytest.raises(DomainError, match="finalized"):
        route.stops[0].change_sequence(2)
    assert route.vehicle.status == VehicleStatus.IN_SERVICE


def test_available_slots_and_recalculate_capacity(kit):
    route, _ = _built_route(kit, n=2, capacity=5)
    assert route.calculate_available_slots() == 3
    route.occupied_slots = 0
    assert route.recalculate_capacity() == 3 and route.occupied_slots == 2


def test_insert_live_pickup(kit):
    route, _ = _built_route(kit, n=1, capacity=2)
    scheduled = kit.paid_order(p=(1, 12))
    assert route.insert_live_pickup(scheduled, scheduled.pickup_address) is False      # not a live request
    live = kit.paid_order(p=(1, 17), pickup_request_type=PickupRequestType.LIVE)
    assert route.insert_live_pickup(live, kit.work) is False                          # wrong address
    assert route.insert_live_pickup(live, live.pickup_address) is True
    assert route.occupied_slots == 2 and len(live.route_stops) == 2
    another = kit.paid_order(p=(1, 17), d=(3, 8), pickup_request_type=PickupRequestType.LIVE)
    assert route.insert_live_pickup(another, another.pickup_address) is False         # vehicle full


def test_route_stop_rules(kit):
    route, orders = _built_route(kit)
    pickup = next(s for s in route.stops if s.order is orders[0] and s.stop_type == StopType.PICKUP)
    delivery = pickup.partner()
    with pytest.raises(DomainError, match="before its pickup"):
        delivery.change_sequence(1)
    with pytest.raises(DomainError):
        pickup.change_sequence(99)
    with pytest.raises(DomainError, match="pickup before the delivery"):
        delivery.mark_completed()
    pickup.mark_completed()
    pickup.mark_completed()                                  # idempotent
    delivery.mark_completed()
    assert delivery.status == StopStatus.COMPLETED
    with pytest.raises(DomainError, match="already has"):
        RouteStop.create(route, orders[0], orders[0].pickup_address, StopType.PICKUP)
    o = kit.paid_order(p=(1, 17))
    with pytest.raises(DomainError, match="before its pickup"):
        RouteStop.create(route, o, o.delivery_address, StopType.DELIVERY)
    with pytest.raises(DomainError, match="address"):
        RouteStop.create(route, o, kit.work, StopType.PICKUP)


# ---------------- Machines and maintenance ----------------
def test_report_fault_and_repair(kit):
    m = Machine("W", MachineType.WASHER, Decimal("18"), current_cycle="Cold")
    with pytest.raises(DomainError):
        m.report_fault("Leaking", kit.driver)
    with pytest.raises(DomainError):
        m.report_fault(" ", kit.laundry)
    rec = m.report_fault("Leaking door", kit.laundry)
    assert m.status == MachineStatus.FAULTY and m.calculate_capacity() == 0 and m.current_cycle is None
    assert rec.status == MaintenanceStatus.REPORTED and m.notifications[0].type == NotificationType.MACHINE_FAULT
    with pytest.raises(DomainError, match="open"):
        m.report_fault("Again", kit.laundry)
    with pytest.raises(DomainError):
        rec.schedule(today_local() - timedelta(days=1))
    rec.schedule(today_local() + timedelta(days=1), kit.admin)
    assert m.status == MachineStatus.UNDER_MAINTENANCE and rec.managed_by is kit.admin
    with pytest.raises(DomainError, match="details"):
        rec.complete()
    rec.update_repair_details("Replaced door seal")
    rec.complete()
    assert rec.status == MaintenanceStatus.COMPLETED and m.status == MachineStatus.OPERATIONAL
    assert m.calculate_capacity() == Decimal("18")
    with pytest.raises(DomainError):
        rec.complete()


# ---------------- Inventory ----------------
def test_inventory_movements_and_alerts(kit):
    item = InventoryItem("I", "Detergent", Decimal("25"), Decimal("20"))
    with pytest.raises(DomainError):
        item.adjust_quantity(StockMovementType.CONSUMPTION, Decimal("30"), kit.laundry)    # can't go negative
    with pytest.raises(DomainError):
        item.adjust_quantity(StockMovementType.ADJUSTMENT_OUT, Decimal("1"))               # needs staff
    with pytest.raises(DomainError):
        item.adjust_quantity(StockMovementType.RECEIPT, Decimal("0"), kit.laundry)
    with pytest.raises(DomainError):
        item.raise_low_stock_alert()
    mv = item.adjust_quantity(StockMovementType.CONSUMPTION, Decimal("6"), kit.laundry)
    assert item.quantity_on_hand == Decimal("19") and mv in item.movements and mv in kit.laundry.stock_movements
    assert item.alert_open and len(item.notifications) == 1
    item.adjust_quantity(StockMovementType.CONSUMPTION, Decimal("1"), kit.laundry)
    assert len(item.notifications) == 1                     # no duplicate while still low
    assert item.raise_low_stock_alert() is item.notifications[0]
    item.adjust_quantity(StockMovementType.RECEIPT, Decimal("50"), kit.laundry)
    assert not item.alert_open and not item.check_reorder_level()
    with pytest.raises(DomainError):
        mv.quantity = Decimal("1")


def test_stock_movement_static_factory(kit):
    item = InventoryItem("I", "Bags", Decimal("10"), Decimal("2"))
    mv = StockMovement.record_movement(item, StockMovementType.ADJUSTMENT_IN, Decimal("5"), kit.admin)
    assert item.quantity_on_hand == Decimal("15") and mv.inventory_item is item
    with pytest.raises(DomainError):
        StockMovement.record_movement(item, StockMovementType.RECEIPT, Decimal("1"), kit.driver)
