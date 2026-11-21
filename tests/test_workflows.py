"""End-to-end scenarios from Milestone 6, run through the services against the seeded database."""
from datetime import time, timedelta
from decimal import Decimal

import pytest

from zippywash.common import (BagSize, DomainError, LoyaltyTransactionType as T, OrderStatus, PaymentStatus,
                              RouteStatus, now_local, today_local)
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.seed import slot_id
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.booking_service import BookingService
from zippywash.services.operations_service import OperationsService
from zippywash.services.order_tracking_service import OrderTrackingService


def checkout(world, customer_id="CUS-LEA", day=4, hour=8):
    lea = world.get(Customer, customer_id)
    booking = BookingService(world)
    home = lea.addresses[0]
    order = booking.start_booking(lea, home, home, world.get(ServiceType, "SVC-WF"), BagSize.SMALL)
    d = today_local() + timedelta(days=day)
    booking.choose_slots(order, world.get(TimeSlot, slot_id(d, time(hour))),
                         world.get(TimeSlot, slot_id(d + timedelta(days=1), time(17))))
    return lea, booking, order


# ---------------- UC01-SC1 ----------------
def test_uc01_authorized_booking_is_saved(repo, world):
    lea, booking, order = checkout(world)
    slot = order.pickup_time_slot
    outcome = booking.pay(order, world.get(PaymentMethod, "PM-LEA-VISA"))
    assert outcome.authorized and order.status == OrderStatus.SCHEDULED
    assert outcome.payment.status == PaymentStatus.AUTHORIZED and outcome.payment.receipt_number
    assert slot.available_capacity == 3
    assert any("confirmed" in n.message for n in lea.notifications)
    repo.commit(world)
    again = repo.load()
    saved = next(o for o in again.get(Customer, "CUS-LEA").orders if o.order_id == order.order_id)
    assert saved.status == OrderStatus.SCHEDULED and saved.pickup_time_slot.available_capacity == 3
    assert saved.final_total == Decimal("34.47") and saved.get_current_status().status == OrderStatus.SCHEDULED


@pytest.mark.parametrize("method_id,status", [("PM-LEA-MC", PaymentStatus.FAILED),
                                              ("PM-LEA-DEB", PaymentStatus.TIMED_OUT)])
def test_uc01_failed_payment_confirms_nothing_and_retry_works(world, method_id, status):
    lea, booking, order = checkout(world)
    before = order.pickup_time_slot.available_capacity
    outcome = booking.pay(order, world.get(PaymentMethod, method_id))
    assert not outcome.authorized and outcome.payment.status == status
    assert order.status == OrderStatus.DRAFT and order.pickup_time_slot.available_capacity == before
    assert order not in lea.view_order_history()
    retry = booking.pay(order, world.get(PaymentMethod, "PM-LEA-VISA"))
    assert retry.authorized and len(order.payment_attempts) == 2


def test_uc01_slot_full_after_authorization_refunds(world):
    lea, booking, order = checkout(world)
    order.delivery_time_slot.available_capacity = 0
    outcome = booking.pay(order, world.get(PaymentMethod, "PM-LEA-VISA"))
    assert not outcome.authorized and outcome.payment.status == PaymentStatus.REFUNDED
    assert order.status == OrderStatus.DRAFT


def test_uc01_cannot_use_another_customers_card(world):
    lea, booking, order = checkout(world)
    with pytest.raises(DomainError):
        booking.pay(order, world.get(PaymentMethod, "PM-OMR-DEB"))


# ---------------- UC02-SC1 ----------------
def test_uc02_own_orders_only_and_read_only(world):
    lea, omar = world.get(Customer, "CUS-LEA"), world.get(Customer, "CUS-OMAR")
    mine = OrderTrackingService.my_orders(lea)
    assert mine and all(o.customer is lea for o in mine)
    omar_order = OrderTrackingService.my_orders(omar)[0]
    with pytest.raises(DomainError):
        OrderTrackingService.order_for(lea, omar_order.order_id)
    order = mine[0]
    history = list(order.status_history)
    latest = OrderTrackingService.current_status(lea, order.order_id)
    assert latest is order.status_history[-1] and order.status_history == history


def test_uc02_empty_state_for_new_customer(world):
    assert OrderTrackingService.my_orders(world.get(Customer, "CUS-NINA")) == []


def test_uc02_note_shown_when_present(world):
    lea = world.get(Customer, "CUS-LEA")
    washing = next(o for o in lea.orders if o.status == OrderStatus.WASHING)
    assert OrderTrackingService.current_status(lea, washing.order_id).notes == "Two duvets, cold wash"


# ---------------- UC07-SC2 (reference case: 420 points, $34.47 -> $5.74) ----------------
def test_uc07_reserve_then_redeem(repo, world):
    lea, booking, order = checkout(world)
    account = lea.loyalty_account
    assert account.point_balance == 420 and order.estimated_total == Decimal("34.47")
    booking.reserve_reward(order, world.get(Reward, "RWD-FREEBAG"))
    assert (account.point_balance, account.reserved_points(), account.available_points()) == (420, 250, 170)
    assert order.estimated_total == Decimal("5.74")
    outcome = booking.pay(order, world.get(PaymentMethod, "PM-LEA-VISA"))
    assert outcome.authorized and outcome.redeemed.type == T.REDEMPTION
    assert outcome.payment.amount == Decimal("5.74") and account.point_balance == 170
    repo.commit(world)
    assert repo.load().get(Customer, "CUS-LEA").loyalty_account.point_balance == 170


def test_uc07_restore_on_failed_payment(world):
    lea, booking, order = checkout(world)
    account = lea.loyalty_account
    booking.reserve_reward(order, world.get(Reward, "RWD-FREEBAG"))
    outcome = booking.pay(order, world.get(PaymentMethod, "PM-LEA-MC"))
    assert not outcome.authorized and outcome.restored.type == T.RESTORATION
    assert account.available_points() == 420 and order.applied_reward is None
    assert order.estimated_total == Decimal("34.47")


def test_uc07_restore_on_cancelled_checkout(world):
    lea, booking, order = checkout(world)
    account = lea.loyalty_account
    booking.reserve_reward(order, world.get(Reward, "RWD-FREEBAG"))
    restored = booking.release_reward(order)
    assert restored.type == T.RESTORATION and account.available_points() == 420
    assert order.estimated_total == Decimal("34.47")
    assert len([t for t in account.transactions if t.reservation is not None]) == 1   # exactly one terminal


def test_uc07_ineligible_rewards_explain_why(world):
    lea, booking, order = checkout(world)
    reasons = {r.reward_id: why for r, why in booking.reward_options(order)}
    assert reasons["RWD-FREEBAG"] is None and "Needs 600 points" in reasons["RWD-FREEDEL"]
    booking.apply_promo_code(order, "welcome10")
    assert all(why for why in dict(booking.reward_options(order)).values())


def test_abandoned_checkout_releases_points(world):
    lea, booking, order = checkout(world)
    booking.reserve_reward(order, world.get(Reward, "RWD-FREEBAG"))
    _, _, newer = checkout(world, day=5)            # starting again closes the old draft
    assert order.status == OrderStatus.CANCELLED and lea.loyalty_account.available_points() == 420


# ---------------- staff side ----------------
def test_delivery_earns_points_and_cancel_refunds(world):
    lea, booking, order = checkout(world)
    booking.pay(order, world.get(PaymentMethod, "PM-LEA-VISA"))
    driver, laundry = world.get(StaffMember, "STF-DRV1"), world.get(StaffMember, "STF-LDY1")
    for staff in [driver, laundry, laundry, laundry, driver, driver]:
        OrderTrackingService.advance_status(order, staff)
    assert order.status == OrderStatus.DELIVERED and lea.loyalty_account.point_balance == 420 + 34
    _, booking2, order2 = checkout(world, day=6)
    booking2.reserve_reward(order2, world.get(Reward, "RWD-FREEBAG"))
    booking2.pay(order2, world.get(PaymentMethod, "PM-LEA-VISA"))
    OrderTrackingService.cancel_order(order2)
    assert order2.status == OrderStatus.CANCELLED and order2.payment_attempts[-1].status == PaymentStatus.REFUNDED
    assert lea.loyalty_account.point_balance == 454            # redeemed points given back


def test_route_build_optimize_finalize_through_service(repo, world):
    omar_order = OrderTrackingService.my_orders(world.get(Customer, "CUS-OMAR"))[0]
    day = omar_order.pickup_time_slot.date
    driver = world.get(StaffMember, "STF-DRV1")
    shift = next(s for s in driver.shifts if s.shift_date == day)
    route = OperationsService(world).build_route(shift, world.get(Sector, "SEC-DT"), world.get(Vehicle, "VAN-01"), day)
    assert omar_order in route.orders() and route.occupied_slots == len(route.orders())
    route.optimize()
    route.finalize_route()
    repo.commit(world)
    saved = next(r for r in repo.load().all(type(route)))
    assert saved.status == RouteStatus.FINALIZED and len(saved.stops) == 2 * len(route.orders())
    assert saved.staff_shift.route is saved
