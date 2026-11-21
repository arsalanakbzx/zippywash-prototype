"""Demo data so the prototype opens in a realistic working state.

Every name, address, card and price below is SAMPLE DATA for the demo, not ZippyWash's real data.
Objects are created through the domain methods, so the seed also follows the business rules.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

from zippywash.common import (BagSize, MachineType, PaymentMethodType, StaffRole, StockMovementType,
                              today_local)
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.repository import Repository, World
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService
from zippywash.services.order_tracking_service import OrderTrackingService

SLOT_TIMES = [time(8, 0), time(12, 0), time(17, 0)]
SLOT_CAPACITY = 4
DAYS_AHEAD = 14


def slot_id(day: date, start: time) -> str:
    return f"SLT-{day:%Y%m%d}-{start:%H}"


def ensure_rolling_slots(world: World, today: date | None = None) -> int:
    """Keep bookable slots for the next DAYS_AHEAD days, each served by every machine.
    Existing slots (and their booked capacity) are never touched. Returns how many were added."""
    today = today or today_local()
    machines = world.all(Machine)
    added = 0
    for d in range(DAYS_AHEAD):
        day = today + timedelta(days=d)
        for t in SLOT_TIMES:
            if world.get(TimeSlot, slot_id(day, t)) is None:
                slot = TimeSlot(slot_id(day, t), day, t, SLOT_CAPACITY)
                for m in machines:
                    slot.contributing_machines.append(m)
                    m.time_slots.append(slot)
                slot.recalculate_capacity()
                world.add(slot)
                added += 1
    return added


def seed(repo: Repository, today: date | None = None) -> None:
    today = today or today_local()
    world = repo.load()

    # ---------------- reference data ----------------
    downtown = Sector("SEC-DT", "Downtown", "H3H,H3G,H3A,H3B,H2Z")
    plateau = Sector("SEC-PL", "Plateau", "H2T,H2J,H2W,H2X")
    driver = StaffMember("STF-DRV1", "Marc Gagnon", "marc.gagnon@zippywash.example", [StaffRole.DRIVER])
    laundry = StaffMember("STF-LDY1", "Sofia Haddad", "sofia.haddad@zippywash.example", [StaffRole.LAUNDRY_STAFF])
    admin = StaffMember("STF-ADM1", "Admin User", "admin@zippywash.example", [StaffRole.ADMINISTRATOR])
    driver.assign_sector(downtown)
    services = [ServiceType("SVC-WF", "Wash & Fold", Decimal("24.99")),
                ServiceType("SVC-DEL", "Delicates", Decimal("34.99")),
                ServiceType("SVC-BED", "Bedding & Linens", Decimal("39.99"))]
    promos = [Promotion("PRM-WELCOME", "WELCOME10", Decimal("10.00")),
              Promotion("PRM-SUMMER", "SUMMER26", Decimal("5.00"), active=False)]
    rewards = [Reward("RWD-FREEBAG", "Free Small Bag", 250, Decimal("24.99")),
               Reward("RWD-5OFF", "$5 off", 100, Decimal("5.00")),
               Reward("RWD-FREEDEL", "Free Large Bag", 600, Decimal("49.98"))]
    rule = LoyaltyRule("LR-STD", Decimal("1"), date(2026, 9, 1))
    LoyaltyRule.register([rule])
    van = Vehicle("VAN-01", 12)
    washer = Machine("MCH-W1", MachineType.WASHER, Decimal("18"), current_cycle="Cold wash")
    dryer = Machine("MCH-D1", MachineType.DRYER, Decimal("15"))
    stock = [InventoryItem("INV-DET", "Detergent (litres)", Decimal("42.5"), Decimal("20")),
             InventoryItem("INV-BAG", "Delivery bags", Decimal("180"), Decimal("50")),
             InventoryItem("INV-SOFT", "Fabric softener (litres)", Decimal("8"), Decimal("5"))]
    world.add(downtown, plateau, driver, laundry, admin, *services, *promos, *rewards, rule, van, washer, dryer,
              *stock)
    for d in range(4):
        driver.schedule_shift(today + timedelta(days=d), time(7, 0), time(15, 0))
        laundry.schedule_shift(today + timedelta(days=d), time(8, 0), time(16, 0))
    ensure_rolling_slots(world, today)

    # ---------------- customers ----------------
    profiles = CustomerProfileService(world)
    lea = Customer("CUS-LEA", "Léa Tremblay", "lea.tremblay@example.com",
                   service_preferences="Unscented detergent, fold shirts")
    omar = Customer("CUS-OMAR", "Omar Benali", "514-555-0142")
    nina = Customer("CUS-NINA", "Nina Côté", "nina.cote@example.com")     # new customer: no orders yet
    world.add(lea, omar, nina)
    lea_home = profiles.add_address(lea, "1450 Rue Sherbrooke O, Apt 8", "H3G 1L3", "Buzz 08; leave with the concierge")
    lea_work = profiles.add_address(lea, "3700 Boul Saint-Laurent", "H2X 2V4", None)
    profiles.add_address(lea, "55 Rue Notre-Dame E, Longueuil", "J4H 1A1", None)    # outside sectors on purpose
    omar_home = profiles.add_address(omar, "2100 Boul de Maisonneuve O", "H3H 1K6", None)
    nina_home = profiles.add_address(nina, "1200 Rue Saint-Denis", "H2X 3J6", None)
    lea_visa = profiles.add_payment_method(lea, "tok_visa_ok_4242", PaymentMethodType.CREDIT_CARD, "Visa ending 4242")
    profiles.add_payment_method(lea, "tok_decline_0002", PaymentMethodType.CREDIT_CARD,
                                "Mastercard ending 0002 (demo: always declined)")
    profiles.add_payment_method(lea, "tok_timeout_7777", PaymentMethodType.DEBIT_CARD,
                                "Debit ending 7777 (demo: payment service times out)")
    omar_debit = profiles.add_payment_method(omar, "tok_debit_ok_9876", PaymentMethodType.DEBIT_CARD,
                                             "Debit ending 9876")
    profiles.add_payment_method(nina, "tok_visa_ok_1881", PaymentMethodType.CREDIT_CARD, "Visa ending 1881")
    for m in lea.payment_methods + omar.payment_methods + nina.payment_methods:
        m.payment_method_id = {"4242": "PM-LEA-VISA", "0002": "PM-LEA-MC", "7777": "PM-LEA-DEB",
                               "9876": "PM-OMR-DEB", "1881": "PM-NIN-VISA"}[m.token[-4:]]
    profiles.join_loyalty(lea).loyalty_account_id = "LA-LEA"
    profiles.join_loyalty(nina).loyalty_account_id = "LA-NINA"

    # ---------------- sample orders, made through the real services ----------------
    booking, tracking = BookingService(world), OrderTrackingService(world)
    t1, t2, t3 = (today + timedelta(days=n) for n in (1, 2, 3))

    def book(customer, home, drop, service, size, p, d, method, promo=None):
        order = booking.start_booking(customer, home, drop, service, size)
        booking.choose_slots(order, world.get(TimeSlot, slot_id(*p)), world.get(TimeSlot, slot_id(*d)))
        if promo:
            booking.apply_promo_code(order, promo)
        outcome = booking.pay(order, method)
        assert outcome.authorized, outcome.message
        return order

    delivered = book(lea, lea_home, lea_home, services[0], BagSize.MEDIUM, (t1, time(8)), (t2, time(17)),
                     lea_visa, "WELCOME10")
    for staff in [driver, laundry, laundry, laundry, driver, driver]:
        tracking.advance_status(delivered, staff)
    washing = book(lea, lea_home, lea_work, services[2], BagSize.LARGE, (t1, time(12)), (t3, time(12)), lea_visa)
    tracking.advance_status(washing, driver)
    tracking.advance_status(washing, laundry)
    tracking.advance_status(washing, laundry, "Two duvets, cold wash")
    book(omar, omar_home, omar_home, services[1], BagSize.SMALL, (t2, time(8)), (t3, time(17)), omar_debit)

    # Léa's opening balance for the UC07 reference case: 420 points.
    account = lea.loyalty_account
    gap = 420 - account.point_balance
    if gap:
        account.correct_points(gap, "Opening balance carried over from the paper loyalty card", admin)

    # A little inventory history (laundry staff use detergent every day).
    stock[0].adjust_quantity(StockMovementType.CONSUMPTION, Decimal("2.5"), laundry)

    repo.commit(world)
