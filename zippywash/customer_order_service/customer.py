"""C01 Customer — the stored customer account (not the external Customer actor).

Customer is a kind of Person: name and contact_details are inherited from C26 Person.
"""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import AccountStatus, DomainError
from zippywash.person import Person


@dataclass
class Customer(Person):
    customer_id: str
    account_status: AccountStatus = AccountStatus.ACTIVE
    service_preferences: str | None = None      # [0..1], e.g. "Unscented detergent"

    def is_active(self) -> bool:
        return self.account_status == AccountStatus.ACTIVE

    def ensure_can_book(self) -> None:
        if not self.is_active():
            raise DomainError("This account is deactivated and can't place new orders.")

    def update_profile(self, name: str, contact_details: str, service_preferences: str | None = None) -> None:
        """UC-06: change profile information and service preferences. Name and contact are required."""
        name, contact_details = name.strip(), contact_details.strip()
        if not name:
            raise DomainError("Name can't be empty.")
        if "@" not in contact_details and not any(c.isdigit() for c in contact_details):
            raise DomainError("Enter an email address or a phone number.")
        self.name = name
        self.contact_details = contact_details
        self.service_preferences = (service_preferences or "").strip() or None

    def deactivate_account(self) -> None:
        self.account_status = AccountStatus.DEACTIVATED
