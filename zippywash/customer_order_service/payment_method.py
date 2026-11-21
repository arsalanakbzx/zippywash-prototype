"""PaymentMethod — a tokenized customer payment option. Raw card data is never stored."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zippywash.common import Entity, PaymentMethodType

if TYPE_CHECKING:
    from zippywash.customer_order_service.customer import Customer
    from zippywash.customer_order_service.payment import Payment


@dataclass(eq=False, repr=False)
class PaymentMethod(Entity):
    _pk = "payment_method_id"

    payment_method_id: str
    token: str
    type: PaymentMethodType
    customer: Customer | None = None                        # [1..1]
    active: bool = True
    payments: list[Payment] = field(default_factory=list)   # [0..*]
    label: str = ""   # display text only, e.g. "Visa ending 4242" (technical, not a model attribute)

    def __post_init__(self):
        try:
            self.type = PaymentMethodType(self.type)
        except ValueError:
            pass   # validate() reports an unsupported type

    def validate(self) -> bool:
        """Nonblank processor token, supported type, active, and owned by its customer."""
        return (bool(self.token and self.token.strip().startswith("tok_"))
                and isinstance(self.type, PaymentMethodType)
                and self.active
                and self.customer is not None
                and any(pm is self for pm in self.customer.payment_methods))

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
