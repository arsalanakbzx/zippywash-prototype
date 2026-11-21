"""Order — owns the booking, estimate, status, payment and fulfillment relationships."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from zippywash.common import (STATUS_SEQUENCE, BagSize, DisputeStatus, DomainError, Entity, OrderStatus,
                              PaymentStatus, PickupRequestType, StaffRole, link, money, new_id, now_local,
                              unlink)
from zippywash.config import DELIVERY_FEE, GST_RATE, MIN_TURNAROUND_DAYS, QST_RATE
from zippywash.customer_order_service.order_item import OrderItem
from zippywash.customer_order_service.order_status_update import OrderStatusUpdate

if TYPE_CHECKING:
    from zippywash.customer_order_service.address import Address
    from zippywash.customer_order_service.customer import Customer
    from zippywash.customer_order_service.loyalty_transaction import LoyaltyTransaction
    from zippywash.customer_order_service.payment import Payment
    from zippywash.customer_order_service.promotion import Promotion
    from zippywash.customer_order_service.reward import Reward
    from zippywash.customer_order_service.service_type import ServiceType
    from zippywash.customer_order_service.time_slot import TimeSlot
    from zippywash.operations_resource.route_stop import RouteStop
    from zippywash.operations_resource.staff_member import StaffMember

# Which staff role may record each status after booking (administrators may record any).
ROLE_FOR_STATUS = {
    OrderStatus.PICKED_UP: StaffRole.DRIVER,
    OrderStatus.WAITING_FOR_WASH: StaffRole.LAUNDRY_STAFF,
    OrderStatus.WASHING: StaffRole.LAUNDRY_STAFF,
    OrderStatus.READY_FOR_PICKUP: StaffRole.LAUNDRY_STAFF,
    OrderStatus.OUT_FOR_DELIVERY: StaffRole.DRIVER,
    OrderStatus.DELIVERED: StaffRole.DRIVER,
}
CANCELLABLE = (OrderStatus.DRAFT, OrderStatus.SCHEDULED)


@dataclass
class PriceBreakdown:
    """Technical value object for the review screen (not a problem-domain class)."""
    subtotal: Decimal
    discount: Decimal
    delivery_fee: Decimal
    gst: Decimal
    qst: Decimal
    total: Decimal


@dataclass(eq=False, repr=False)
class Order(Entity):
    _pk = "order_id"

    order_id: str
    created_at: datetime
    bag_size: BagSize
    customer: Customer | None = None                                        # [1..1]
    pickup_address: Address | None = None                                  # [1..1]
    delivery_address: Address | None = None                                # [1..1]
    service_type: ServiceType | None = None                                # [1..1]
    status: OrderStatus = OrderStatus.DRAFT
    pickup_request_type: PickupRequestType = PickupRequestType.SCHEDULED
    subtotal: Decimal = Decimal("0.00")
    delivery_fee: Decimal = DELIVERY_FEE
    tax_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    estimated_total: Decimal = Decimal("0.00")
    final_total: Decimal | None = None                                      # [0..1]
    dispute_status: DisputeStatus | None = None                             # [0..1]
    pickup_time_slot: TimeSlot | None = None                                # [0..1]
    delivery_time_slot: TimeSlot | None = None                              # [0..1]
    order_items: list[OrderItem] = field(default_factory=list)              # [1..*]
    status_history: list[OrderStatusUpdate] = field(default_factory=list)   # [1..*]
    payment_attempts: list[Payment] = field(default_factory=list)           # [0..*]
    applied_promotion: Promotion | None = None                              # [0..1]
    applied_reward: Reward | None = None                                    # [0..1]
    loyalty_transactions: list[LoyaltyTransaction] = field(default_factory=list)  # [0..*]
    route_stops: list[RouteStop] = field(default_factory=list)              # [0..2]

    def __post_init__(self):
        self.bag_size = BagSize(self.bag_size)
        self.status = OrderStatus(self.status)
        self.pickup_request_type = PickupRequestType(self.pickup_request_type)
        if self.dispute_status is not None:
            self.dispute_status = DisputeStatus(self.dispute_status)
        for name in ("subtotal", "delivery_fee", "tax_amount", "discount_amount", "estimated_total"):
            setattr(self, name, money(getattr(self, name)))
        if self.final_total is not None:
            self.final_total = money(self.final_total)

    # =================================================================
    # Creation (technical factory used by the booking service)
    # =================================================================
    @staticmethod
    def start(customer: Customer, pickup_address: Address, delivery_address: Address,
              service_type: ServiceType, bag_size: BagSize, quantity: int = 1,
              pickup_request_type: PickupRequestType = PickupRequestType.SCHEDULED) -> Order:
        """Create a Draft order with one OrderItem and its first status-history entry."""
        customer.ensure_can_book()
        for addr, role in ((pickup_address, "Pickup"), (delivery_address, "Delivery")):
            if addr is None or addr.customer is not customer:
                raise DomainError(f"{role} address does not belong to this customer.")
            if not addr.validate():
                raise DomainError(f"{role} address {addr.postal_code} is outside our service sectors.")
        if service_type is None or not service_type.active:
            raise DomainError("Choose a service that is currently offered.")
        created = now_local()
        order = Order(f"ZW-{created:%Y%m%d}-{new_id('X')[-4:]}", created, BagSize(bag_size), customer, pickup_address,
                      delivery_address, service_type, pickup_request_type=PickupRequestType(pickup_request_type))
        order.order_items.append(OrderItem(new_id("OIT"), quantity, order))
        first = OrderStatusUpdate(new_id("OSU"), OrderStatus.DRAFT, order.created_at, order, "Checkout started")
        first.seal()
        order.status_history.append(first)
        order._link_references()
        return order

    def _link_references(self) -> None:
        """Keep both ends of each association consistent."""
        link(self.customer.orders, self)
        link(self.pickup_address.pickup_orders, self)
        link(self.delivery_address.delivery_orders, self)
        link(self.service_type.orders, self)

    # =================================================================
    # Helpers used by services and the UI
    # =================================================================
    def was_placed(self) -> bool:
        return any(u.status == OrderStatus.SCHEDULED for u in self.status_history)

    def authorized_payment(self) -> Payment | None:
        for p in reversed(self.payment_attempts):
            if p.status in (PaymentStatus.AUTHORIZED, PaymentStatus.REFUNDED):
                return p
        return None

    def select_time_slots(self, pickup_slot: TimeSlot, delivery_slot: TimeSlot) -> None:
        """Choose the slots shown at checkout. This is not a capacity reservation yet."""
        if self.status != OrderStatus.DRAFT:
            raise DomainError("Time slots can only be changed before the order is paid.")
        if pickup_slot is None or delivery_slot is None:
            raise DomainError("Choose a pickup and a delivery time.")
        if pickup_slot.has_started(now_local()):
            raise DomainError("That pickup time has already passed. Pick a later slot.")
        if (delivery_slot.date - pickup_slot.date).days < MIN_TURNAROUND_DAYS:
            raise DomainError("Delivery must be at least one day after pickup.")
        for slot, role in ((pickup_slot, "pickup"), (delivery_slot, "delivery")):
            if not slot.check_capacity(1):
                raise DomainError(f"The {role} slot {slot.label()} is full. Pick another time.")
        if self.pickup_time_slot is not None:
            unlink(self.pickup_time_slot.pickup_orders, self)
        if self.delivery_time_slot is not None:
            unlink(self.delivery_time_slot.delivery_orders, self)
        self.pickup_time_slot, self.delivery_time_slot = pickup_slot, delivery_slot
        link(pickup_slot.pickup_orders, self)
        link(delivery_slot.delivery_orders, self)

    def apply_promotion(self, promotion: Promotion | None) -> None:
        """Attach (or remove, with None) a promo code; never together with a reward."""
        if promotion is not None and not promotion.validate_eligibility(self):
            raise DomainError(promotion.ineligibility_reason(self))
        if self.applied_promotion is not None:
            unlink(self.applied_promotion.orders, self)
        self.applied_promotion = promotion
        if promotion is not None:
            link(promotion.orders, self)

    def price_breakdown(self) -> PriceBreakdown:
        """Split the stored tax amount into GST and QST for display."""
        taxable = self.subtotal - self.discount_amount + self.delivery_fee
        gst = money(taxable * GST_RATE)
        return PriceBreakdown(self.subtotal, self.discount_amount, self.delivery_fee, gst,
                              money(self.tax_amount - gst), self.estimated_total)

    # =================================================================
    # Milestone 5 operations
    # =================================================================
    def calculate_estimate(self) -> Decimal:
        """M5-C01. Price the order from its stored state and return estimatedTotal.

        Does not confirm the order, reserve slots, authorize payment or create a receipt.
        Repeating it with unchanged state gives the same result (nothing is applied twice)."""
        # 1. Preconditions
        if None in (self.customer, self.service_type, self.pickup_address, self.delivery_address):
            raise DomainError("An order needs a customer, a service and pickup and delivery addresses.")
        if not self.order_items:
            raise DomainError("An order needs at least one service line.")
        if any(item.quantity <= 0 for item in self.order_items):
            raise DomainError("Every quantity must be greater than zero.")
        if self.delivery_fee < 0 or GST_RATE < 0 or QST_RATE < 0:
            raise DomainError("Fees and taxes can't be negative.")
        if not self.service_type.active:
            raise DomainError(f"'{self.service_type.name}' is not currently offered.")
        if self.status == OrderStatus.CANCELLED:
            raise DomainError("A cancelled order can't be priced.")
        if self.applied_promotion is not None and self.applied_reward is not None:
            raise DomainError("An order can use a promo code or a loyalty reward, not both.")

        # 2-3. Unit price once, then each line exactly once
        unit_price = self.service_type.calculate_base_price(self.bag_size)
        subtotal = money(sum((item.calculate_line_total(unit_price) for item in self.order_items), Decimal("0")))
        self.subtotal = subtotal

        # 4. At most one discount, capped at the service subtotal
        discount = Decimal("0.00")
        if self.applied_promotion is not None:
            if not self.applied_promotion.validate_eligibility(self):
                raise DomainError(self.applied_promotion.ineligibility_reason(self))
            discount = self.applied_promotion.calculate_discount(self)
        elif self.applied_reward is not None:
            account = self.customer.loyalty_account
            if account is None or not self.applied_reward.validate_eligibility(account, self):
                raise DomainError(f"The reward '{self.applied_reward.name}' can't be used on this order.")
            discount = self.applied_reward.discount_amount
        discount = money(min(discount, subtotal))

        # 5. Quebec taxes on the post-discount amount (service after discount + delivery fee)
        taxable = subtotal - discount + self.delivery_fee
        gst = money(taxable * GST_RATE)
        qst = money(taxable * QST_RATE)

        # 6-7. Store and return
        total = money(taxable + gst + qst)
        if min(subtotal, discount, gst, qst, total) < 0:
            raise DomainError("The price can't be negative.")
        self.discount_amount, self.tax_amount, self.estimated_total = discount, money(gst + qst), total
        return self.estimated_total

    def calculate_final_total(self) -> Decimal:
        """The amount actually charged: the authorized payment for this order."""
        payment = self.authorized_payment()
        if payment is None:
            raise DomainError("There is no authorized payment for this order yet.")
        self.final_total = money(payment.amount)
        return self.final_total

    def confirm(self) -> None:
        """Release the order for service. Needs an authorized payment for the estimated total and
        successful capacity in both time slots (reserved together, or not at all)."""
        if self.status != OrderStatus.DRAFT:
            raise DomainError(f"Order {self.order_id} is already {self.status.value}.")
        payment = self.authorized_payment()
        if payment is None or payment.status != PaymentStatus.AUTHORIZED:
            raise DomainError("Payment must be authorized before the order is confirmed.")
        if payment.amount != self.estimated_total:
            raise DomainError("The authorized amount doesn't match the order total.")
        if self.pickup_time_slot is None or self.delivery_time_slot is None:
            raise DomainError("Choose a pickup and a delivery time.")
        if not self.pickup_time_slot.reserve_capacity(1):
            raise DomainError(f"The pickup slot {self.pickup_time_slot.label()} just filled up.")
        if not self.delivery_time_slot.reserve_capacity(1):
            self.pickup_time_slot.release_capacity(1)
            raise DomainError(f"The delivery slot {self.delivery_time_slot.label()} just filled up.")
        self.calculate_final_total()
        self.update_status(OrderStatus.SCHEDULED, None, "Booked and paid online")

    def get_current_status(self) -> OrderStatusUpdate:
        """The latest entry in the status history."""
        if not self.status_history:
            raise DomainError("This order has no status history.")
        return max(enumerate(self.status_history), key=lambda pair: (pair[1].changed_at, pair[0]))[1]

    def check_transition(self, new_status: OrderStatus, recorded_by: StaffMember | None) -> None:
        """Statuses move one step forward at a time. Cancelling is allowed only before pickup.
        Steps after booking are recorded by staff who hold the matching role."""
        new_status = OrderStatus(new_status)
        if new_status == OrderStatus.CANCELLED:
            if self.status not in CANCELLABLE:
                raise DomainError(f"An order that is {self.status.value} can no longer be cancelled.")
            return
        if self.status not in STATUS_SEQUENCE or self.status == STATUS_SEQUENCE[-1]:
            raise DomainError(f"Order is {self.status.value}; its status can't change any more.")
        expected = STATUS_SEQUENCE[STATUS_SEQUENCE.index(self.status) + 1]
        if new_status != expected:
            raise DomainError(f"Next status must be '{expected.value}', not '{new_status.value}'.")
        needed = ROLE_FOR_STATUS.get(new_status)
        if needed is not None:
            if recorded_by is None:
                raise DomainError(f"'{new_status.value}' must be recorded by a staff member.")
            if not recorded_by.check_authorization(needed):
                raise DomainError(f"Only staff with the {needed.label} role can mark an order "
                                  f"'{new_status.value}'.")

    def next_status(self) -> OrderStatus | None:
        if self.status not in STATUS_SEQUENCE or self.status == STATUS_SEQUENCE[-1]:
            return None
        return STATUS_SEQUENCE[STATUS_SEQUENCE.index(self.status) + 1]

    def update_status(self, new_status: OrderStatus, recorded_by: StaffMember | None = None,
                      notes: str | None = None) -> OrderStatusUpdate:
        """Record one status change in the append-only history."""
        return OrderStatusUpdate.record_status_change(self, new_status, recorded_by, notes)

    def create_repeat_booking(self) -> Order:
        """A new Draft order with the same customer, addresses, service, bag size and quantities.
        It gets new IDs, status, timestamps and no payments, slots or discounts."""
        if self.status == OrderStatus.DRAFT:
            raise DomainError("Only a placed order can be booked again.")
        repeat = Order.start(self.customer, self.pickup_address, self.delivery_address, self.service_type,
                             self.bag_size, self.order_items[0].quantity, self.pickup_request_type)
        for item in self.order_items[1:]:
            repeat.order_items.append(OrderItem(new_id("OIT"), item.quantity, repeat))
        return repeat

    def cancel(self) -> bool:
        """Cancel a Draft or Scheduled order and give back what it holds: slot capacity and any
        reserved loyalty points. Returns False (and changes nothing) when it's too late to cancel.
        Refunding a captured payment is done by the service through Payment.refund()."""
        if self.status not in CANCELLABLE:
            return False
        if self.status == OrderStatus.SCHEDULED:
            self.pickup_time_slot.release_capacity(1)
            self.delivery_time_slot.release_capacity(1)
        account = self.customer.loyalty_account if self.customer else None
        if account is not None:
            for reservation in account.open_reservations(order=self):
                account.restore_points(reservation)
        self.update_status(OrderStatus.CANCELLED, None, "Cancelled")
        return True
