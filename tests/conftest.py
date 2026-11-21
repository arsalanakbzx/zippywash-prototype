"""Shared fixtures: a fresh seeded database per test, and helpers that build objects in memory."""
from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal

import pytest

from zippywash.common import BagSize, PaymentMethodType, StaffRole, today_local
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.payment import Payment
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.db import connect, create_schema
from zippywash.database.repository import Repository
from zippywash.database.seed import seed, slot_id
from zippywash.integrations.payment_processor import MockPaymentProcessor
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService


@pytest.fixture(autouse=True)
def processor():
    """A fresh mock processor per test, so calls can be counted."""
    p = MockPaymentProcessor()
    Payment.configure_processor(p)
    return p


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    r = Repository(conn)
    seed(r)
    return r


@pytest.fixture
def world(repo):
    return repo.load()


class Kit:
    """Small in-memory ZippyWash for unit tests (no database)."""

    def __init__(self):
        self.sector = Sector("SEC-T", "Test", "H3H,H3G")
        self.other_sector = Sector("SEC-O", "Other", "H2X")
        self.customer = Customer("CUS-T", "Test Customer", "test@example.com")
        self.stranger = Customer("CUS-X", "Someone Else", "x@example.com")
        profiles = CustomerProfileService(_FakeWorld([self.sector, self.other_sector]))
        self.home = profiles.add_address(self.customer, "1 Test St", "H3H 1K6", None)
        self.work = profiles.add_address(self.customer, "2 Test St", "H3G 1L3", None)
        self.far = profiles.add_address(self.customer, "9 Far Rd", "H2X 2V4", None)
        self.outside = profiles.add_address(self.customer, "Longueuil", "J4H 1A1", None)
        self.visa = profiles.add_payment_method(self.customer, "tok_visa_ok", PaymentMethodType.CREDIT_CARD, "Visa")
        self.declined = profiles.add_payment_method(self.customer, "tok_decline_x", PaymentMethodType.CREDIT_CARD,
                                                    "Declined")
        self.timeout = profiles.add_payment_method(self.customer, "tok_timeout_x", PaymentMethodType.DEBIT_CARD,
                                                   "Timeout")
        self.other_card = profiles.add_payment_method(self.stranger, "tok_other", PaymentMethodType.CREDIT_CARD,
                                                      "Other")
        self.wash = ServiceType("SVC-WF", "Wash & Fold", Decimal("24.99"))
        self.reward = Reward("RWD-FREEBAG", "Free Small Bag", 250, Decimal("24.99"))
        self.rule = LoyaltyRule("LR", Decimal("1"), today_local() - timedelta(days=30))
        LoyaltyRule.register([self.rule])
        self.driver = StaffMember("STF-D", "Driver", "d@example.com", [StaffRole.DRIVER])
        self.laundry = StaffMember("STF-L", "Laundry", "l@example.com", [StaffRole.LAUNDRY_STAFF])
        self.admin = StaffMember("STF-A", "Admin", "a@example.com", [StaffRole.ADMINISTRATOR])
        self.today = today_local()
        self.slots = {}
        for d in range(1, 5):
            day = self.today + timedelta(days=d)
            for h in (8, 12, 17):
                s = TimeSlot(slot_id(day, time(h)), day, time(h), 4)
                self.slots[(d, h)] = s
        self.booking = BookingService(_FakeWorld(list(self.slots.values()) + [self.reward]))

    def order(self, bag=BagSize.SMALL, pickup=None, delivery=None, p=(1, 8), d=(2, 17), **kw):
        o = self.booking.start_booking(self.customer, pickup or self.home, delivery or self.home, self.wash, bag, **kw)
        self.booking.choose_slots(o, self.slots[p], self.slots[d])
        return o

    def paid_order(self, **kw):
        o = self.order(**kw)
        outcome = self.booking.pay(o, self.visa)
        assert outcome.authorized
        return o

    def member(self, points=420):
        account = CustomerProfileService.join_loyalty(self.customer)
        if points:
            account.correct_points(points, "Test balance", self.admin)
        return account


class _FakeWorld:
    def __init__(self, objs):
        self.objs = objs

    def all(self, cls):
        return [o for o in self.objs if isinstance(o, cls)]


@pytest.fixture
def kit():
    return Kit()
