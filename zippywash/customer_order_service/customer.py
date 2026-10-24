"""C01 Customer — the stored customer account (not the external Customer actor)."""
from __future__ import annotations

from dataclasses import dataclass

from zippywash.common import DomainError


@dataclass
class Customer:
    customer_id: str
    name: str
    contact_details: str
    account_status: str = "Active"

    def is_active(self) -> bool:
        return self.account_status == "Active"

    def ensure_can_book(self) -> None:
        if not self.is_active():
            raise DomainError("This account is deactivated and can't place new orders.")

    def update_profile(self, name: str, contact_details: str) -> None:
        """UC-06: change profile information. Both fields are required."""
        name, contact_details = name.strip(), contact_details.strip()
        if not name:
            raise DomainError("Name can't be empty.")
        if "@" not in contact_details and not any(c.isdigit() for c in contact_details):
            raise DomainError("Enter an email address or a phone number.")
        self.name = name
        self.contact_details = contact_details

    def deactivate_account(self) -> None:
        self.account_status = "Deactivated"
