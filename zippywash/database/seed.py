"""Demo data so the prototype opens in a realistic working state.

Every name, address and price below is SAMPLE DATA for the demo, not ZippyWash's real data.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from zippywash.common import StaffRole
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.customer_order_service.promotion import Promotion
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.repository import Repository
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.services.booking_service import BookingService
from zippywash.services.order_tracking_service import OrderTrackingService

SLOT_TIMES = ["08:00", "12:00", "17:00"]
SLOT_CAPACITY = 4
DAYS_AHEAD = 14


def seed(repo: Repository, today: date | None = None) -> None:
    today = today or date.today()
    with repo.conn:
        sectors = [
            Sector("SEC-DT", "Downtown", "H3H,H3G,H3A,H3B,H2Z"),
            Sector("SEC-PL", "Plateau", "H2T,H2J,H2W,H2X"),
        ]
        for s in sectors:
            repo.save_sector(s)

        for s in [
            StaffMember("STF-DRV1", "Marc Gagnon (Driver)", [StaffRole.DRIVER], sector_id="SEC-DT"),
            StaffMember("STF-LDY1", "Sofia Haddad (Laundry)", [StaffRole.LAUNDRY_STAFF]),
            StaffMember("STF-ADM1", "Admin User", [StaffRole.ADMINISTRATOR]),
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

        for d in range(DAYS_AHEAD):
            day = today + timedelta(days=d)
            for t in SLOT_TIMES:
                repo.save_slot(TimeSlot(f"SLT-{day:%m%d}-{t[:2]}", day, t, SLOT_CAPACITY))

        customers = [
            (Customer("CUS-LEA", "Léa Tremblay", "lea.tremblay@example.com"),
             [("ADR-LEA1", "1450 Rue Sherbrooke O, Apt 8", "H3G 1L3"),
              ("ADR-LEA2", "3700 Boul Saint-Laurent", "H2X 2V4"),
              ("ADR-LEA3", "55 Rue Notre-Dame E, Longueuil", "J4H 1A1")]),   # outside sectors on purpose
            (Customer("CUS-OMAR", "Omar Benali", "514-555-0142"),
             [("ADR-OMR1", "2100 Boul de Maisonneuve O", "H3H 1K6")]),
        ]
        for customer, addresses in customers:
            repo.save_customer(customer)
            for aid, street, postal in addresses:
                a = Address(aid, customer.customer_id, street, postal)
                a.assign_sector(sectors)
                repo.save_address(a)

        for pm in [
            PaymentMethod("PM-LEA-VISA", "CUS-LEA", "tok_visa_ok_4242", "CreditCard", "Visa ending 4242"),
            PaymentMethod("PM-LEA-MC", "CUS-LEA", "tok_decline_0002", "CreditCard",
                          "Mastercard ending 0002 (demo: always declined)"),
            PaymentMethod("PM-OMR-DEB", "CUS-OMAR", "tok_debit_ok_9876", "DebitCard", "Debit ending 9876"),
        ]:
            repo.save_payment_method(pm)

    # A few orders made through the real services, so history and tracking have content.
    booking, tracking = BookingService(repo), OrderTrackingService(repo)
    t1, t2, t3 = (today + timedelta(days=n) for n in (1, 2, 3))

    def slot(d, h):
        return f"SLT-{d:%m%d}-{h}"

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
