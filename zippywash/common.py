"""Shared value types and helpers used by every domain class.

The enumerations below are the value types named in the Milestone 5 implementation class diagram.
They are technical support code, not problem-domain classes.
"""
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
    """A business rule was broken. The message is written for the person using the app."""


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class AccountStatus(str, Enum):
    ACTIVE = "Active"
    DEACTIVATED = "Deactivated"


class PricingUnit(str, Enum):
    PER_BAG = "PerBag"


class PickupRequestType(str, Enum):
    SCHEDULED = "Scheduled"
    LIVE = "Live"


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


# The approved order lifecycle, one step at a time.
STATUS_SEQUENCE = [
    OrderStatus.DRAFT,
    OrderStatus.SCHEDULED,
    OrderStatus.PICKED_UP,
    OrderStatus.WAITING_FOR_WASH,
    OrderStatus.WASHING,
    OrderStatus.READY_FOR_PICKUP,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
]


class DisputeStatus(str, Enum):
    OPEN = "Open"
    UNDER_REVIEW = "UnderReview"
    RESOLVED = "Resolved"


class PaymentStatus(str, Enum):
    PENDING = "Pending"
    AUTHORIZED = "Authorized"
    FAILED = "Failed"
    TIMED_OUT = "TimedOut"
    REFUNDED = "Refunded"


class PaymentMethodType(str, Enum):
    CREDIT_CARD = "CreditCard"
    DEBIT_CARD = "DebitCard"
    DIGITAL_WALLET = "DigitalWallet"


class StaffRole(str, Enum):
    LAUNDRY_STAFF = "LaundryStaff"
    DRIVER = "Driver"
    ADMINISTRATOR = "Administrator"

    @property
    def label(self) -> str:
        return {"LaundryStaff": "laundry staff", "Driver": "driver",
                "Administrator": "administrator"}[self.value]


class NotificationType(str, Enum):
    BOOKING_CONFIRMED = "BookingConfirmed"
    STATUS_CHANGED = "StatusChanged"
    PAYMENT_RESULT = "PaymentResult"
    LOYALTY_UPDATE = "LoyaltyUpdate"
    LOW_STOCK = "LowStock"
    ROUTE_ASSIGNED = "RouteAssigned"
    MACHINE_FAULT = "MachineFault"


class DeliveryStatus(str, Enum):
    PENDING = "Pending"
    SENT = "Sent"
    DELIVERED = "Delivered"
    FAILED = "Failed"


class LoyaltyAccountStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class LoyaltyTransactionType(str, Enum):
    ENROLLMENT = "Enrollment"     # records joining the program (0 points)
    EARN = "Earn"                 # points earned on a paid, delivered order
    CORRECTION = "Correction"     # administrator correction with a reason
    RESERVATION = "Reservation"   # points held for a reward during checkout
    REDEMPTION = "Redemption"     # held points permanently used after authorized payment
    RESTORATION = "Restoration"   # held points released after failure or cancellation
    REVERSAL = "Reversal"         # opposite entry that cancels an earlier entry


class RouteStatus(str, Enum):
    DRAFT = "Draft"
    OPTIMIZED = "Optimized"
    FINALIZED = "Finalized"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"


class StopType(str, Enum):
    PICKUP = "Pickup"
    DELIVERY = "Delivery"


class StopStatus(str, Enum):
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
    RECEIPT = "Receipt"                    # stock received (+)
    CONSUMPTION = "Consumption"            # stock used (-)
    ADJUSTMENT_IN = "AdjustmentIn"         # count correction up (+), staff only
    ADJUSTMENT_OUT = "AdjustmentOut"       # count correction down (-), staff only

    @property
    def sign(self) -> int:
        return 1 if self in (StockMovementType.RECEIPT, StockMovementType.ADJUSTMENT_IN) else -1


class VehicleStatus(str, Enum):
    AVAILABLE = "Available"
    IN_SERVICE = "InService"
    MAINTENANCE = "Maintenance"


class ShiftStatus(str, Enum):
    SCHEDULED = "Scheduled"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def now_local() -> datetime:
    """Current Montréal date and time (naive), whatever time zone the server runs in."""
    return datetime.now(_TZ).replace(tzinfo=None) if _TZ else datetime.now()


def today_local() -> date:
    return now_local().date()


def money(value) -> Decimal:
    """Exact decimal rounded to cents. Never use float for money."""
    return Decimal(str(value)).quantize(CURRENCY_STEP, rounding=ROUND_HALF_UP)


def link(collection: list, item) -> None:
    """Add item to a relationship collection once (no duplicate insertion)."""
    if not any(existing is item for existing in collection):
        collection.append(item)


def unlink(collection: list, item) -> None:
    for i, existing in enumerate(collection):
        if existing is item:
            del collection[i]
            return


class Entity:
    """Short repr for domain objects (their relationships form cycles, so the default repr would loop)."""
    _pk = ""

    def __repr__(self) -> str:
        return f"{type(self).__name__}({getattr(self, self._pk, '?')})"


class Immutable:
    """Mixin for ledger/audit records: once sealed, their recorded fields can't be edited.

    Relationship collections (lists) can still receive new related objects."""
    _sealed = False
    _frozen_fields: tuple[str, ...] = ()

    def seal(self) -> None:
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name, value):
        if self._sealed and name in self._frozen_fields:
            raise DomainError(f"{type(self).__name__} records can't be changed once recorded.")
        object.__setattr__(self, name, value)
