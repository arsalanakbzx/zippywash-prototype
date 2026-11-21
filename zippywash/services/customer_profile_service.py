"""CustomerProfileService — UC-06 profile, addresses, payment methods, order history; UC-07 membership."""
from __future__ import annotations

from zippywash.common import DomainError, LoyaltyAccountStatus, PaymentMethodType, new_id
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.loyalty_account import LoyaltyAccount
from zippywash.customer_order_service.payment_method import PaymentMethod
from zippywash.database.repository import World
from zippywash.operations_resource.sector import Sector


class CustomerProfileService:
    def __init__(self, world: World):
        self.world = world

    @staticmethod
    def update_profile(customer: Customer, name: str, contact: str, prefs: str | None) -> None:
        customer.update_profile(name, contact, prefs)

    def add_address(self, customer: Customer, street: str, postal_code: str, access: str | None) -> Address:
        address = Address(new_id("ADR"), street, postal_code, access_instructions=access)
        customer.add_address(address)
        for sector in self.world.all(Sector):
            if sector.contains_address(address):
                address.assign_sector(sector)
                break
        return address

    @staticmethod
    def add_payment_method(customer: Customer, token: str, type_: PaymentMethodType, label: str) -> PaymentMethod:
        method = PaymentMethod(new_id("PM"), token, type_, label=label)
        customer.add_payment_method(method)
        return method

    @staticmethod
    def deactivate_account(customer: Customer) -> None:
        customer.deactivate_account()

    # ---------------- loyalty membership ----------------
    @staticmethod
    def join_loyalty(customer: Customer) -> LoyaltyAccount:
        account = customer.loyalty_account
        if account is None:
            account = LoyaltyAccount(new_id("LA"), customer)
            customer.loyalty_account = account
            account.enroll()
        elif account.status == LoyaltyAccountStatus.INACTIVE:
            account.reactivate()
        else:
            raise DomainError("You're already a loyalty member.")
        return account
