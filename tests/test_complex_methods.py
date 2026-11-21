"""The four Milestone 5 method contracts (M5-C01..C04)."""
from datetime import time
from decimal import Decimal

import pytest

from zippywash.common import (BagSize, DomainError, LoyaltyTransactionType as T, OrderStatus, PaymentStatus,
                              RouteStatus, StopType, VehicleStatus)
from zippywash.customer_order_service.payment import Payment
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.vehicle import Vehicle


# ---------------- M5-C01 Order.calculateEstimate ----------------
class TestCalculateEstimate:
    def test_reference_price_small_wash_and_fold(self, kit):
        o = kit.order()
        assert o.calculate_estimate() == Decimal("34.47")
        assert (o.subtotal, o.delivery_fee, o.tax_amount, o.discount_amount) == (
            Decimal("24.99"), Decimal("4.99"), Decimal("4.49"), Decimal("0.00"))
        b = o.price_breakdown()
        assert (b.gst, b.qst) == (Decimal("1.50"), Decimal("2.99"))

    def test_lines_summed_once_and_repeat_is_idempotent(self, kit):
        o = kit.order(bag=BagSize.MEDIUM)
        first = o.calculate_estimate()
        assert o.calculate_estimate() == first
        assert o.subtotal == Decimal("37.49")          # 24.99 x 1.5, not added twice
        assert o.order_items[0].unit_price == Decimal("37.49")

    def test_promotion_discount_and_tax_on_post_discount_amount(self, kit):
        o = kit.order()
        o.apply_promotion(Promotion("P", "TEN", Decimal("10")))
        assert o.calculate_estimate() == Decimal("22.97")   # (14.99 + 4.99) x 1.14975
        assert o.discount_amount == Decimal("10.00")

    def test_discount_capped_at_service_subtotal(self, kit):
        o = kit.order()
        o.apply_promotion(Promotion("P", "HUGE", Decimal("500")))
        o.calculate_estimate()
        assert o.discount_amount == Decimal("24.99") and o.estimated_total == Decimal("5.74")

    def test_promotion_and_reward_never_together(self, kit):
        kit.member()
        o = kit.order()
        kit.booking.reserve_reward(o, kit.reward)
        with pytest.raises(DomainError, match="not both"):
            o.apply_promotion(Promotion("P", "TEN", Decimal("10")))
        o.applied_promotion = Promotion("P", "TEN", Decimal("10"))   # force the invalid state
        with pytest.raises(DomainError, match="not both"):
            o.calculate_estimate()

    def test_does_not_confirm_reserve_or_pay(self, kit):
        o = kit.order()
        before = o.pickup_time_slot.available_capacity
        o.calculate_estimate()
        assert o.status == OrderStatus.DRAFT and not o.payment_attempts
        assert o.pickup_time_slot.available_capacity == before

    def test_preconditions(self, kit):
        o = kit.order()
        o.service_type.deactivate()
        with pytest.raises(DomainError):
            o.calculate_estimate()
        o.service_type.activate()
        o.order_items.clear()
        with pytest.raises(DomainError):
            o.calculate_estimate()
        cancelled = kit.order()
        cancelled.cancel()
        with pytest.raises(DomainError):
            cancelled.calculate_estimate()


# ---------------- M5-C02 Route.build ----------------
def _route_for(kit, day=1, capacity=12):
    kit.driver.assign_sector(kit.sector)
    shift = kit.driver.schedule_shift(kit.slots[(day, 8)].date, time(7), time(15))
    route = Route("RTE-T", kit.slots[(day, 8)].date)
    shift.assign_route(route)
    return route, Vehicle("VAN-T", capacity)


class TestRouteBuild:
    def test_two_stops_per_order_pickup_first(self, kit):
        a, b = kit.paid_order(), kit.paid_order(p=(1, 12), d=(3, 8), delivery=kit.work)
        route, van = _route_for(kit)
        route.build(route.route_date, kit.sector, van)
        assert len(route.stops) == 4 and route.occupied_slots == 2
        for order in (a, b):
            mine = [s for s in route.stops if s.order is order]
            assert [s.stop_type for s in sorted(mine, key=lambda s: s.sequence_number)] == [StopType.PICKUP,
                                                                                         StopType.DELIVERY]
        assert sorted(s.sequence_number for s in route.stops) == [1, 2, 3, 4]
        assert route in kit.sector.routes and route in van.routes
        assert route.status == RouteStatus.DRAFT        # not optimized or finalized by build

    def test_capacity_counts_orders_not_stops_and_flags_overflow(self, kit):
        orders = [kit.paid_order(p=(1, h), d=(2, 17)) for h in (8, 12, 17)]
        route, van = _route_for(kit, capacity=2)
        route.build(route.route_date, kit.sector, van)
        assert route.occupied_slots == 2 and len(route.stops) == 4
        assert route.flagged_orders == [orders[2]]

    def test_out_of_sector_and_wrong_date_are_skipped(self, kit):
        kit.paid_order(delivery=kit.far)                  # delivery outside the sector
        kit.paid_order(p=(2, 8), d=(3, 8))                # another day
        route, van = _route_for(kit)
        with pytest.raises(DomainError, match="No eligible"):
            route.build(route.route_date, kit.sector, van)
        assert not route.stops

    def test_preconditions(self, kit):
        kit.paid_order()
        route, van = _route_for(kit)
        van.update_availability(VehicleStatus.MAINTENANCE)
        with pytest.raises(DomainError):
            route.build(route.route_date, kit.sector, van)
        no_shift = Route("RTE-N", route.route_date)
        with pytest.raises(DomainError, match="shift"):
            no_shift.build(route.route_date, kit.sector, Vehicle("V2", 5))


# ---------------- M5-C03 Payment.authorize ----------------
class TestAuthorize:
    def test_one_call_and_status_unchanged(self, kit, processor):
        o = kit.order()
        p = Payment.create_attempt(o, o.estimated_total, kit.visa)
        assert p.authorize() == PaymentStatus.AUTHORIZED
        assert p.status == PaymentStatus.PENDING and len(processor.authorization_calls) == 1
        p.record_result(PaymentStatus.AUTHORIZED)
        assert p.status == PaymentStatus.AUTHORIZED and p.receipt_number is None
        assert o.status == OrderStatus.DRAFT

    def test_declined_and_timeout(self, kit):
        o = kit.order()
        assert Payment.create_attempt(o, o.estimated_total, kit.declined).authorize() == PaymentStatus.FAILED
        assert Payment.create_attempt(o, o.estimated_total, kit.timeout).authorize() == PaymentStatus.TIMED_OUT

    def test_invalid_method_fails_without_calling_processor(self, kit, processor):
        o = kit.order()
        p = Payment.create_attempt(o, o.estimated_total, kit.visa)
        kit.visa.deactivate()
        assert p.authorize() == PaymentStatus.FAILED and processor.authorization_calls == []

    def test_not_pending_fails(self, kit, processor):
        o = kit.order()
        p = Payment.create_attempt(o, o.estimated_total, kit.visa)
        p.record_result(PaymentStatus.FAILED)
        assert p.authorize() == PaymentStatus.FAILED and processor.authorization_calls == []

    def test_factory_rules(self, kit):
        o = kit.order()
        with pytest.raises(DomainError):
            Payment.create_attempt(o, Decimal("0"), kit.visa)
        with pytest.raises(DomainError, match="another customer"):
            Payment.create_attempt(o, Decimal("5"), kit.other_card)
        p = Payment.create_attempt(o, Decimal("5"), kit.visa)
        assert p.status == PaymentStatus.PENDING and p in o.payment_attempts and p in kit.visa.payments


# ---------------- M5-C04 LoyaltyAccount.reservePoints ----------------
class TestReservePoints:
    def test_reference_case(self, kit):
        account = kit.member(420)
        o = kit.order()
        assert o.estimated_total == Decimal("34.47")
        r = account.reserve_points(kit.reward, o)
        o.calculate_estimate()
        assert r.type == T.RESERVATION and r.points == 250 and r.posted
        assert (account.point_balance, account.reserved_points(), account.available_points()) == (420, 250, 170)
        assert o.applied_reward is kit.reward and o.applied_promotion is None
        assert o.estimated_total == Decimal("5.74")
        assert r in account.transactions and r in o.loyalty_transactions and r in kit.reward.transactions

    def test_redeem_once_after_authorization(self, kit):
        account = kit.member(420)
        o = kit.order()
        r = account.reserve_points(kit.reward, o)
        o.calculate_estimate()
        p = Payment.create_attempt(o, o.estimated_total, kit.visa)
        with pytest.raises(DomainError):
            account.redeem_points(r, p)                  # still pending
        p.record_result(p.authorize())
        account.redeem_points(r, p)
        assert account.point_balance == 170 and account.available_points() == 170
        with pytest.raises(DomainError):
            account.redeem_points(r, p)
        with pytest.raises(DomainError):
            account.restore_points(r)

    def test_restore_once(self, kit):
        account = kit.member(420)
        o = kit.order()
        r = account.reserve_points(kit.reward, o)
        account.restore_points(r)
        assert account.point_balance == 420 and account.available_points() == 420 and o.applied_reward is None
        with pytest.raises(DomainError):
            account.restore_points(r)

    def test_rejections(self, kit):
        account = kit.member(200)
        o = kit.order()
        with pytest.raises(DomainError, match="points"):
            account.reserve_points(kit.reward, o)
        account.correct_points(300, "top up", kit.admin)
        promo_order = kit.order()
        promo_order.apply_promotion(Promotion("P", "TEN", Decimal("10")))
        with pytest.raises(DomainError, match="not both"):
            account.reserve_points(kit.reward, promo_order)
        o2 = kit.order()
        account.reserve_points(kit.reward, o2)
        with pytest.raises(DomainError, match="already reserved"):
            account.reserve_points(kit.reward, o2)
        account.deactivate()
        with pytest.raises(DomainError, match="not active"):
            account.reserve_points(kit.reward, kit.order())

    def test_inactive_or_unavailable_reward(self, kit):
        account = kit.member(1000)
        future = Reward("RWD-F", "Later", 10, Decimal("1"))
        future.schedule_availability(kit.today.replace(year=kit.today.year + 1))
        with pytest.raises(DomainError):
            account.reserve_points(future, kit.order())
