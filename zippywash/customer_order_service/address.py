"""C02 Address — a saved pickup/delivery location owned by one Customer."""
from __future__ import annotations

import re
from dataclasses import dataclass

from zippywash.common import DomainError
from zippywash.operations_resource.sector import Sector

# Canadian postal code: A1A 1A1
POSTAL_RE = re.compile(r"^[A-Z]\d[A-Z] ?\d[A-Z]\d$")


@dataclass
class Address:
    address_id: str
    customer_id: str
    street: str
    postal_code: str
    serviceable: bool = False
    sector_id: str | None = None
    access_instructions: str | None = None   # [0..1], e.g. "Buzz 08, leave with concierge"

    def label(self) -> str:
        return f"{self.street}, {self.postal_code}"

    def validate(self) -> None:
        if not self.street.strip():
            raise DomainError("Street address is required.")
        if not POSTAL_RE.match(self.postal_code.strip().upper()):
            raise DomainError(f"'{self.postal_code}' is not a valid Canadian postal code (e.g. H3H 1K6).")

    def assign_sector(self, sectors: list[Sector]) -> None:
        """Mark the address serviceable if a predefined sector contains it."""
        self.validate()
        for sector in sectors:
            if sector.contains_address(self.postal_code):
                self.sector_id = sector.sector_id
                self.serviceable = True
                return
        self.sector_id = None
        self.serviceable = False
