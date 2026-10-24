"""Shared value types and helpers used by every class."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from zippywash.config import CURRENCY_STEP


class DomainError(Exception):
    """A business rule was broken. The message is shown to the user as-is."""


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


class NotificationType(str, Enum):
    BOOKING_CONFIRMED = "BookingConfirmed"
    STATUS_CHANGED = "StatusChanged"
    PAYMENT_RESULT = "PaymentResult"
    LOW_STOCK = "LowStock"
    ROUTE_ASSIGNED = "RouteAssigned"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def money(value) -> Decimal:
    """Exact decimal rounded to cents. Never use float for money."""
    return Decimal(str(value)).quantize(CURRENCY_STEP, rounding=ROUND_HALF_UP)
