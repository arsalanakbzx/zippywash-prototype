"""C09 LoyaltyRule — how many points an eligible dollar earns, from a given date."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal


@dataclass
class LoyaltyRule:
    loyalty_rule_id: str
    points_per_dollar: Decimal
    effective_from: date
    active: bool = True

    def calculate_points(self, eligible_amount: Decimal) -> int:
        """Whole points only; partial points are dropped."""
        if not self.active:
            return 0
        return int((eligible_amount * self.points_per_dollar).to_integral_value(rounding=ROUND_DOWN))

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
