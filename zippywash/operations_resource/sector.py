"""C15 Sector — a predefined service area served by assigned drivers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Sector:
    sector_id: str
    name: str
    boundary: str          # GeoBoundary, simplified: comma-separated postal prefixes ("H3H,H3G")
    active: bool = True

    def prefixes(self) -> list[str]:
        return [p.strip().upper() for p in self.boundary.split(",") if p.strip()]

    def contains_address(self, postal_code: str) -> bool:
        """True when the postal code's first three characters (FSA) fall inside this sector."""
        fsa = postal_code.replace(" ", "").upper()[:3]
        return self.active and fsa in self.prefixes()
