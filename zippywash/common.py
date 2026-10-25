"""Shared value types and helpers used by every class."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from zippywash.config import CURRENCY_STEP, TIMEZONE

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(TIMEZONE)
except Exception:  # time zone data missing: fall back to the server clock
    _TZ = None


class DomainError(Exception):
    """A business rule was broken. The message is shown to the user as-is."""


# ---------------------------------------------------------------------------
# Enumerations (value types) named in the Milestone 3 class diagram.
# Values marked PLACEHOLDER are not defined in Milestone 3 and can be renamed by the team.
# GeoBoundary is represented as a plain string of postal-code prefixes (see Sector).
# ---------------------------------------------------------------------------

class AccountStatus(str, Enum):
    ACTIVE = "Active"
    DEACTIVATED = "Deactivated"


class PricingUnit(str, Enum):          # PLACEHOLDER values
    PER_BAG = "PerBag"


class PickupRequestType(str, Enum):    # PLACEHOLDER values
    SCHEDULED = "Scheduled"
    LIVE = "Live"


class AddOnType(str, Enum):            # PLACEHOLDER values
    STAIN_TREATMENT = "StainTreatment"
    FABRIC_SOFTENER = "FabricSoftener"
    HYPOALLERGENIC_DETERGENT = "HypoallergenicDetergent"
    HANG_DRY = "HangDry"


class BagSize(str, Enum):
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


class OrderStatus(str, Enum):
    DRAFT = "Draft"
    SCHEDULED = "Scheduled"
    PICKED_UP = "Picked Up"
    WAITING_FOR_WASH = "Waiting for Wash"
    WASHING = "Washing"
    READY_FOR_PICKUP = "Ready for Pickup"
    OUT_FOR_DELIVERY = "Out for Delivery"
    DELIVERED = "Delivered"
    CANCELLED = "Cancelled"


# The approved lifecycle (Milestone 2 activity diagram / Milestone 3 handoff, section 7).
STATUS_SEQUENCE = [
    OrderStatus.SCHEDULED,
    OrderStatus.PICKED_UP,
    OrderStatus.WAITING_FOR_WASH,
    OrderStatus.WASHING,
    OrderStatus.READY_FOR_PICKUP,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
]


class PaymentStatus(str, Enum):
    PENDING = "Pending"
    AUTHORIZED = "Authorized"
    DECLINED = "Declined"
    REFUNDED = "Refunded"


class StaffRole(str, Enum):
    LAUNDRY_STAFF = "LaundryStaff"
    DRIVER = "Driver"
    ADMINISTRATOR = "Administrator"

    @property
    def label(self) -> str:
        """Readable name for messages, e.g. 'laundry staff'."""
        return {"LaundryStaff": "laundry staff", "Driver": "driver",
                "Administrator": "administrator"}[self.value]


class NotificationType(str, Enum):
    BOOKING_CONFIRMED = "BookingConfirmed"
    STATUS_CHANGED = "StatusChanged"
    PAYMENT_RESULT = "PaymentResult"
    LOW_STOCK = "LowStock"
    ROUTE_ASSIGNED = "RouteAssigned"
    MACHINE_FAULT = "MachineFault"


class DeliveryStatus(str, Enum):
    PENDING = "Pending"
    SENT = "Sent"
    DELIVERED = "Delivered"
    FAILED = "Failed"


class LoyaltyStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class LoyaltyTransactionType(str, Enum):
    EARN = "Earn"
    RESERVE = "Reserve"
    REDEEM = "Redeem"
    RESTORE = "Restore"
    ADJUSTMENT = "Adjustment"
    REVERSAL = "Reversal"


class PaymentMethodType(str, Enum):
    CREDIT_CARD = "CreditCard"
    DEBIT_CARD = "DebitCard"
    DIGITAL_WALLET = "DigitalWallet"


class RouteStatus(str, Enum):
    DRAFT = "Draft"
    OPTIMIZED = "Optimized"
    FINALIZED = "Finalized"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"


class StopType(str, Enum):
    PICKUP = "Pickup"
    DELIVERY = "Delivery"


class RouteStopStatus(str, Enum):
    PLANNED = "Planned"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"


class MachineType(str, Enum):
    WASHER = "Washer"
    DRYER = "Dryer"


class MachineStatus(str, Enum):
    OPERATIONAL = "Operational"
    FAULTY = "Faulty"
    UNDER_MAINTENANCE = "UnderMaintenance"
    OUT_OF_SERVICE = "OutOfService"


class MaintenanceStatus(str, Enum):
    REPORTED = "Reported"
    SCHEDULED = "Scheduled"
    IN_REPAIR = "InRepair"
    COMPLETED = "Completed"


class StockMovementType(str, Enum):
    CONSUMPTION = "Consumption"
    RECEIPT = "Receipt"
    ADJUSTMENT = "Adjustment"


class VehicleStatus(str, Enum):        # PLACEHOLDER values
    AVAILABLE = "Available"
    IN_SERVICE = "InService"
    MAINTENANCE = "Maintenance"


class ShiftStatus(str, Enum):          # PLACEHOLDER values
    SCHEDULED = "Scheduled"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def now_local() -> datetime:
    """Current Montréal date and time (naive), whatever time zone the server runs in."""
    return datetime.now(_TZ).replace(tzinfo=None) if _TZ else datetime.now()


def today_local() -> date:
    return now_local().date()


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def money(value) -> Decimal:
    """Exact decimal rounded to cents. Never use float for money."""
    return Decimal(str(value)).quantize(CURRENCY_STEP, rounding=ROUND_HALF_UP)
