"""CustomerProfileService — UC-06 (Manage Customer Profile & Order History)."""
from __future__ import annotations

from zippywash.common import DomainError, new_id
from zippywash.customer_order_service.address import Address
from zippywash.customer_order_service.customer import Customer
from zippywash.database.repository import Repository


class CustomerProfileService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def update_profile(self, customer_id: str, name: str, contact_details: str) -> Customer:
        with self.repo.conn:
            customer = self.repo.get_customer(customer_id)
            if customer is None:
                raise DomainError("Customer not found.")
            customer.update_profile(name, contact_details)
            self.repo.save_customer(customer)
            return customer

    def add_address(self, customer_id: str, street: str, postal_code: str) -> Address:
        """Saves the address and tells the customer whether ZippyWash serves it."""
        with self.repo.conn:
            address = Address(new_id("ADR"), customer_id, street.strip(), postal_code.strip().upper())
            address.assign_sector(self.repo.list_sectors())
            self.repo.save_address(address)
            return address

    def view_order_history(self, customer_id: str):
        """Every non-draft order with its payment attempts, newest first."""
        return [(o, self.repo.list_payments(o.order_id)) for o in self.repo.list_orders_for_customer(customer_id)]
