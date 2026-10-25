"""C26 Person — abstract superclass of Customer and StaffMember.

Holds the attributes both kinds of people share. It has no database table of its own:
the inherited attributes are stored in the customers and staff_members tables.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass


@dataclass
class Person(ABC):
    name: str
    contact_details: str

    def __new__(cls, *args, **kwargs):
        if cls is Person:
            raise TypeError("Person is abstract; create a Customer or a StaffMember.")
        return super().__new__(cls)
