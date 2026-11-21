"""Customer — the account holder who books and tracks services (Milestone 5, Figure 1a).

name and contactDetails sit directly on Customer: the abstract Person class was removed in Milestone 5.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zippywash.common import AccountStatus, DomainError, Entity, OrderStatus, link

if TYPE_CHECKING:
    from zippywash.customer_order_service.address import Address
    from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
    from zippywash.customer_order_service.notification import Notification
    from zippywash.customer_order_service.order import Order
    from zippywash.customer_order_service.payment_method import PaymentMethod


@dataclass(eq=False, repr=False)
class Customer(Entity):
    _pk = "customer_id"

    customer_id: str
    name: str
    contact_details: str
    account_status: AccountStatus = AccountStatus.ACTIVE
    service_preferences: str | None = None                                       # [0..1]
    addresses: list[Address] = field(default_factory=list)                       # [0..*]
    loyalty_account: LoyaltyAccount | None = None                                # [0..1]
    orders: list[Order] = field(default_factory=list)                            # [0..*]
    payment_methods: list[PaymentMethod] = field(default_factory=list)           # [0..*]
    notifications: list[Notification] = field(default_factory=list)              # [0..*]

    def __post_init__(self):
        self.account_status = AccountStatus(self.account_status)

    # ---------------- helpers ----------------
    def is_active(self) -> bool:
        return self.account_status == AccountStatus.ACTIVE

    def ensure_can_book(self) -> None:
        if not self.is_active():
            raise DomainError("This account is deactivated and can't place new orders.")

    # ---------------- Milestone 5 operations ----------------
    def update_profile(self, name: str, contact_details: str, service_preferences: str | None = None) -> None:
        """Change profile information. Name and contact details are required."""
        name, contact_details = (name or "").strip(), (contact_details or "").strip()
        if not name:
            raise DomainError("Name can't be empty.")
        if "@" not in contact_details and not any(c.isdigit() for c in contact_details):
            raise DomainError("Enter an email address or a phone number.")
        self.name = name
        self.contact_details = contact_details
        self.service_preferences = (service_preferences or "").strip() or None

    def add_address(self, address: Address) -> None:
        """Attach a validated address that belongs to this customer; the same place is never added twice."""
        if address.customer is not None and address.customer is not self:
            raise DomainError("That address belongs to another customer.")
        if not address.has_valid_format():
            raise DomainError(address.format_problem())
        for existing in self.addresses:
            if existing is address:
                return
            if (existing.street.strip().lower() == address.street.strip().lower()
                    and existing.normalized_postal_code() == address.normalized_postal_code()):
                raise DomainError("That address is already saved.")
        address.customer = self
        self.addresses.append(address)

    def add_payment_method(self, payment_method: PaymentMethod) -> None:
        """Attach a tokenized payment method owned by this customer; no duplicates."""
        if payment_method.customer is not None and payment_method.customer is not self:
            raise DomainError("That payment method belongs to another customer.")
        if any(pm is not payment_method and pm.token == payment_method.token for pm in self.payment_methods):
            raise DomainError("That payment method is already saved.")
        payment_method.customer = self
        link(self.payment_methods, payment_method)

    def view_order_history(self) -> list[Order]:
        """This customer's placed orders, newest first. Unpaid checkouts (Draft) are not history."""
        placed = [o for o in self.orders
                  if o.customer is self and o.status != OrderStatus.DRAFT and o.was_placed()]
        return sorted(placed, key=lambda o: o.created_at, reverse=True)

    def deactivate_account(self) -> None:
        """Stop new bookings. Order history, payments and loyalty records are kept."""
        if not self.is_active():
            raise DomainError("This account is already deactivated.")
        self.account_status = AccountStatus.DEACTIVATED
