"""Business-rule tests. Run with:  python -m pytest -q"""
from datetime import timedelta
from decimal import Decimal

import pytest

from zippywash.common import DomainError, OrderStatus, PaymentStatus, today_local
from zippywash.database.db import connect, create_schema
from zippywash.database.repository import Repository
from zippywash.database.seed import ensure_rolling_slots, seed, slot_id
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService
from zippywash.services.order_tracking_service import OrderTrackingService

TODAY = today_local()


def slot(days, hour):
    return slot_id(TODAY + timedelta(days=days), hour)


@pytest.fixture
def repo():
    conn = connect(":memory:")
    create_schema(conn)
    r = Repository(conn)
    seed(r)
    return r


def book(repo, **overrides):
    args = dict(customer_id="CUS-LEA", service_type_id="SVC-WF", bag_size="Small",
                pickup_address_id="ADR-LEA1", delivery_address_id="ADR-LEA1",
                pickup_slot_id=slot(4, "08"), delivery_slot_id=slot(5, "08"),
                payment_method_id="PM-LEA-VISA")
    args.update(overrides)
    return BookingService(repo).book(**args)


def test_price_breakdown_with_promo_and_quebec_taxes(repo):
    p = BookingService(repo).quote("CUS-LEA", "SVC-WF", "Medium", "welcome10")
    assert p.service_price == Decimal("37.49")    # 24.99 x 1.5
    assert p.discount == Decimal("10.00")
    assert p.gst == Decimal("1.62")               # 5% of 32.48
    assert p.qst == Decimal("3.24")               # 9.975% of 32.48
    assert p.total == Decimal("37.34")


def test_successful_booking_schedules_order_reserves_slots_and_issues_receipt(repo):
    before = repo.get_slot(slot(4, "08")).available_capacity
    r = book(repo)
    assert r.success and r.order.status == OrderStatus.SCHEDULED
    assert repo.get_slot(slot(4, "08")).available_capacity == before - 1
    assert r.payment.status == PaymentStatus.AUTHORIZED and r.payment.receipt_number
    assert [u.status for u in repo.get_order(r.order.order_id).history] == [OrderStatus.SCHEDULED]


def test_declined_payment_keeps_order_draft_and_retry_creates_second_attempt(repo):
    r = book(repo, payment_method_id="PM-LEA-MC")
    assert not r.success and r.order.status == OrderStatus.DRAFT
    assert repo.get_slot(slot(4, "08")).available_capacity == 4     # nothing reserved
    r2 = BookingService(repo).retry_payment(r.order.order_id, "PM-LEA-VISA")
    assert r2.success
    assert [p.status for p in repo.list_payments(r.order.order_id)] == [PaymentStatus.DECLINED,
                                                                       PaymentStatus.AUTHORIZED]


def test_address_outside_service_sectors_is_rejected(repo):
    with pytest.raises(DomainError, match="outside our service sectors"):
        book(repo, pickup_address_id="ADR-LEA3")


def test_cannot_use_another_customers_address(repo):
    with pytest.raises(DomainError, match="does not belong"):
        book(repo, pickup_address_id="ADR-OMR1")


def test_delivery_must_be_after_pickup_day(repo):
    with pytest.raises(DomainError, match="at least one day"):
        book(repo, delivery_slot_id=slot(4, "17"))


def test_full_slot_is_rejected(repo):
    for _ in range(4):
        book(repo, delivery_slot_id=slot(6, "08"))
    with pytest.raises(DomainError, match="full"):
        book(repo, delivery_slot_id=slot(7, "08"))


def test_expired_and_unknown_promo_codes_are_rejected(repo):
    with pytest.raises(DomainError, match="expired"):
        book(repo, promo_code="SUMMER26")
    with pytest.raises(DomainError, match="doesn't exist"):
        book(repo, promo_code="FREE100")


def test_status_moves_one_step_and_respects_roles(repo):
    order = book(repo).order
    t = OrderTrackingService(repo)
    with pytest.raises(DomainError, match="driver role"):
        t.advance_status(order.order_id, "STF-LDY1")             # laundry staff can't mark Picked Up
    assert t.advance_status(order.order_id, "STF-DRV1").status == OrderStatus.PICKED_UP
    assert t.advance_status(order.order_id, "STF-LDY1").status == OrderStatus.WAITING_FOR_WASH
    assert t.advance_status(order.order_id, "STF-ADM1").status == OrderStatus.WASHING   # admin can do any


def test_cancel_refunds_and_releases_slots_only_before_pickup(repo):
    order = book(repo).order
    t = OrderTrackingService(repo)
    t.cancel_order(order.order_id, "CUS-LEA")
    assert repo.get_order(order.order_id).status == OrderStatus.CANCELLED
    assert repo.get_slot(slot(4, "08")).available_capacity == 4
    assert repo.list_payments(order.order_id)[0].status == PaymentStatus.REFUNDED

    picked = book(repo).order
    t.advance_status(picked.order_id, "STF-DRV1")
    with pytest.raises(DomainError, match="no longer be cancelled"):
        t.cancel_order(picked.order_id, "CUS-LEA")


def test_every_status_change_notifies_exactly_one_recipient(repo):
    order = book(repo).order
    OrderTrackingService(repo).advance_status(order.order_id, "STF-DRV1")
    rows = repo.conn.execute("SELECT customer_id, staff_member_id FROM notifications").fetchall()
    assert rows and all((c is None) != (s is None) for c, s in rows)


def test_new_address_gets_sector_or_is_flagged(repo):
    p = CustomerProfileService(repo)
    assert p.add_address("CUS-OMAR", "1 Av Mont-Royal E", "h2t 1n1").sector_id == "SEC-PL"
    assert not p.add_address("CUS-OMAR", "10 Rue Principale", "J4H 2B2").serviceable
    with pytest.raises(DomainError, match="postal code"):
        p.add_address("CUS-OMAR", "10 Rue X", "12345")


def test_database_rejects_promotion_and_reward_together(repo):
    import sqlite3
    repo.conn.execute("INSERT INTO rewards (reward_id, name, points_required, discount_amount, active) "
                      "VALUES ('RW1','Free bag',100,'10.00',1)")
    with pytest.raises(sqlite3.IntegrityError):
        repo.conn.execute("UPDATE orders SET promotion_id='PRM-WELCOME', reward_id='RW1'")


def test_slots_keep_rolling_forward_without_resetting_bookings(repo):
    booked = book(repo).order                                   # takes one seat in slot(4, "08")
    later = TODAY + timedelta(days=30)
    added = ensure_rolling_slots(repo, later)
    assert added == 14 * 3                                     # a new two-week window appeared
    assert repo.get_slot(slot_id(later, "08")) is not None
    assert ensure_rolling_slots(repo, later) == 0              # running again adds nothing
    assert repo.get_slot(slot(4, "08")).available_capacity == 3   # booked seat still taken
    assert repo.get_order(booked.order_id).status == OrderStatus.SCHEDULED


# ---------------- Montréal time and past slots ----------------
def test_slot_that_already_started_cannot_be_booked():
    from datetime import datetime
    from zippywash.customer_order_service.time_slot import TimeSlot
    slot = TimeSlot("S", TODAY, "08:00", 4)
    assert slot.has_started(datetime.combine(TODAY, datetime.min.time()).replace(hour=9))
    assert not slot.has_started(datetime.combine(TODAY, datetime.min.time()).replace(hour=7))


def test_booking_a_pickup_time_that_has_passed_is_rejected(repo, monkeypatch):
    from datetime import datetime
    import zippywash.customer_order_service.order as order_module
    # Pretend it is already 8 p.m. on the pickup day: the 08:00 slot has passed.
    evening = datetime.combine(TODAY + timedelta(days=4), datetime.min.time()).replace(hour=20)
    monkeypatch.setattr(order_module, "now_local", lambda: evening)
    with pytest.raises(DomainError, match="already passed"):
        book(repo)


def test_today_follows_montreal_not_the_server_clock():
    from zoneinfo import ZoneInfo
    from datetime import datetime
    from zippywash.common import now_local
    expected = datetime.now(ZoneInfo("America/Toronto")).replace(tzinfo=None)
    assert abs((now_local() - expected).total_seconds()) < 5


def test_role_names_read_naturally():
    from zippywash.common import StaffRole
    assert StaffRole.LAUNDRY_STAFF.label == "laundry staff"
    assert StaffRole.DRIVER.label == "driver"
