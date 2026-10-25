"""Business settings for the prototype.

PLACEHOLDERS: the team has not confirmed ZippyWash's real prices yet
(open decision #4 "Pricing inputs" in the Milestone 3 handoff). Change the
numbers here only; every price in the app reads from this file.
"""
from decimal import Decimal

# Bag size multiplies the service type's base rate (one "Small" bag = base rate).
BAG_SIZE_MULTIPLIER = {
    "Small": Decimal("1.0"),
    "Medium": Decimal("1.5"),
    "Large": Decimal("2.0"),
}

DELIVERY_FEE = Decimal("4.99")

# Quebec sales taxes, applied to (subtotal - discount + delivery fee).
GST_RATE = Decimal("0.05")      # federal GST 5%
QST_RATE = Decimal("0.09975")   # Quebec QST 9.975%

# Delivery must be on a later day than pickup (next-day turnaround at minimum).
MIN_TURNAROUND_DAYS = 1

CURRENCY_STEP = Decimal("0.01")

# ZippyWash operates in Montréal: "today" and "now" use this time zone, not the server's.
TIMEZONE = "America/Toronto"
