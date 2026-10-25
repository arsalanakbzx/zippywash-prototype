"""Demo data so the prototype opens in a realistic working state.

Every name, address and price below is SAMPLE DATA for the demo, not ZippyWash's real data.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

from zippywash.common import LoyaltyStatus, MachineStatus, MachineType, RouteStatus, StaffRole, today_local
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
from zippywash.customer_order_service.loyalty_rule import LoyaltyRule
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.repository import Repository
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.staff_shift import StaffShift
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.booking_service import BookingService
from zippywash.services.order_tracking_service import OrderTrackingService

SLOT_TIMES = ["08:00", "12:00", "17:00"]
SLOT_CAPACITY = 4
DAYS_AHEAD = 14


def slot_id(day: date, start_time: str) -> str:
    return f"SLT-{day:%Y%m%d}-{start_time[:2]}"


def ensure_rolling_slots(repo: Repository, today: date | None = None) -> int:
    """Keep bookable slots for the next DAYS_AHEAD days. Safe to run every time the app starts:
    existing slots (and their booked capacity) are never touched. Returns how many were added."""
    today = today or today_local()
    before = repo.conn.execute("SELECT COUNT(*) FROM time_slots").fetchone()[0]
    for d in range(DAYS_AHEAD):
        day = today + timedelta(days=d)
        for t in SLOT_TIMES:
            repo.add_slot_if_missing(TimeSlot(slot_id(day, t), day, t, SLOT_CAPACITY))
    repo.conn.commit()
    return repo.conn.execute("SELECT COUNT(*) FROM time_slots").fetchone()[0] - before


def seed(repo: Repository, today: date | None = None) -> None:
    today = today or today_local()
    with repo.conn:
        sectors = [
            Sector("SEC-DT", "Downtown", "H3H,H3G,H3A,H3B,H2Z"),
            Sector("SEC-PL", "Plateau", "H2T,H2J,H2W,H2X"),
        ]
        for s in sectors:
            repo.save_sector(s)

        for s in [
            StaffMember(name="Marc Gagnon (Driver)", contact_details="marc.gagnon@zippywash.example",
                        staff_member_id="STF-DRV1", roles=[StaffRole.DRIVER], sector_id="SEC-DT"),
            StaffMember(name="Sofia Haddad (Laundry)", contact_details="sofia.haddad@zippywash.example",
                        staff_member_id="STF-LDY1", roles=[StaffRole.LAUNDRY_STAFF]),
            StaffMember(name="Admin User", contact_details="admin@zippywash.example",
                        staff_member_id="STF-ADM1", roles=[StaffRole.ADMINISTRATOR]),
        ]:
            repo.save_staff(s)

        for st in [
            ServiceType("SVC-WF", "Wash & Fold", Decimal("24.99")),
            ServiceType("SVC-DEL", "Delicates", Decimal("34.99")),
            ServiceType("SVC-BED", "Bedding & Linens", Decimal("39.99")),
        ]:
            repo.save_service_type(st)

        repo.save_promotion(Promotion("PRM-WELCOME", "WELCOME10", Decimal("10.00")))
        repo.save_promotion(Promotion("PRM-SUMMER", "SUMMER26", Decimal("5.00"), active=False))
        repo.save_reward(Reward("RWD-FREEBAG", "Free small bag", 250, Decimal("24.99")))
        repo.save_loyalty_rule(LoyaltyRule("LR-STD", Decimal("1"), date(2026, 9, 1)))

        ensure_rolling_slots(repo, today)

        customers = [
            (Customer(name="Léa Tremblay", contact_details="lea.tremblay@example.com", customer_id="CUS-LEA",
                      service_preferences="Unscented detergent, fold shirts"),
             [("ADR-LEA1", "1450 Rue Sherbrooke O, Apt 8", "H3G 1L3", "Buzz 08; leave with the concierge"),
              ("ADR-LEA2", "3700 Boul Saint-Laurent", "H2X 2V4", None),
              ("ADR-LEA3", "55 Rue Notre-Dame E, Longueuil", "J4H 1A1", None)]),   # outside sectors on purpose
            (Customer(name="Omar Benali", contact_details="514-555-0142", customer_id="CUS-OMAR"),
             [("ADR-OMR1", "2100 Boul de Maisonneuve O", "H3H 1K6", None)]),
        ]
        for customer, addresses in customers:
            repo.save_customer(customer)
            for aid, street, postal, access in addresses:
                a = Address(aid, customer.customer_id, street, postal, access_instructions=access)
                a.assign_sector(sectors)
                repo.save_address(a)

        for pm in [
            PaymentMethod("PM-LEA-VISA", "CUS-LEA", "tok_visa_ok_4242", "CreditCard", "Visa ending 4242"),
            PaymentMethod("PM-LEA-MC", "CUS-LEA", "tok_decline_0002", "CreditCard",
                          "Mastercard ending 0002 (demo: always declined)"),
            PaymentMethod("PM-OMR-DEB", "CUS-OMAR", "tok_debit_ok_9876", "DebitCard", "Debit ending 9876"),
        ]:
            repo.save_payment_method(pm)

        repo.save_loyalty_account(LoyaltyAccount("LA-LEA", 120, LoyaltyStatus.ACTIVE, date(2026, 9, 15), "CUS-LEA"))

        # Operations sample data (UC-03 / UC-04 screens come in Prototype 2).
        van = Vehicle("VAN-01", slot_capacity=12)
        repo.save_vehicle(van)
        shift = StaffShift("SHF-DRV1-D1", today, time(7, 0), time(15, 0), staff_member_id="STF-DRV1")
        repo.save_staff_shift(shift)
        repo.save_staff_shift(StaffShift("SHF-LDY1-D1", today, time(8, 0), time(16, 0), staff_member_id="STF-LDY1"))
        repo.save_route(Route("RTE-DT-D1", today, RouteStatus.DRAFT, Decimal("0"), 0,
                              sector_id="SEC-DT", vehicle_id=van.vehicle_id, staff_shift_id=shift.staff_shift_id))
        repo.save_machine(Machine("MCH-W1", MachineType.WASHER, MachineStatus.OPERATIONAL, Decimal("18"), "Cold wash"))
        repo.save_machine(Machine("MCH-D1", MachineType.DRYER, MachineStatus.OPERATIONAL, Decimal("15")))
        repo.save_inventory_item(InventoryItem("INV-DET", "Detergent (litres)", Decimal("42.5"), Decimal("20")))
        repo.save_inventory_item(InventoryItem("INV-BAG", "Delivery bags", Decimal("180"), Decimal("50")))

    # A few orders made through the real services, so history and tracking have content.
    booking, tracking = BookingService(repo), OrderTrackingService(repo)
    t1, t2, t3 = (today + timedelta(days=n) for n in (1, 2, 3))

    def slot(d, h):
        return slot_id(d, h)

    done = booking.book(customer_id="CUS-LEA", service_type_id="SVC-WF", bag_size="Medium",
                        pickup_address_id="ADR-LEA1", delivery_address_id="ADR-LEA1",
                        pickup_slot_id=slot(t1, "08"), delivery_slot_id=slot(t2, "17"),
                        payment_method_id="PM-LEA-VISA", promo_code="WELCOME10").order
    for staff in ["STF-DRV1", "STF-LDY1", "STF-LDY1", "STF-LDY1", "STF-DRV1", "STF-DRV1"]:
        tracking.advance_status(done.order_id, staff)

    washing = booking.book(customer_id="CUS-LEA", service_type_id="SVC-BED", bag_size="Large",
                           pickup_address_id="ADR-LEA1", delivery_address_id="ADR-LEA2",
                           pickup_slot_id=slot(t1, "12"), delivery_slot_id=slot(t3, "12"),
                           payment_method_id="PM-LEA-VISA").order
    for staff in ["STF-DRV1", "STF-LDY1", "STF-LDY1"]:
        tracking.advance_status(washing.order_id, staff, "Two duvets, cold wash" if staff == "STF-LDY1" else None)

    booking.book(customer_id="CUS-OMAR", service_type_id="SVC-DEL", bag_size="Small",
                 pickup_address_id="ADR-OMR1", delivery_address_id="ADR-OMR1",
                 pickup_slot_id=slot(t2, "08"), delivery_slot_id=slot(t3, "17"),
                 payment_method_id="PM-OMR-DEB")
