"""Streamlit screens for the three Milestone 6 scenarios, driven with Streamlit's AppTest."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.setenv("ZIPPYWASH_DB", str(tmp_path / "ui.db"))   # a fresh demo database per test
    import streamlit as st
    st.cache_resource.clear()
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    assert not app.exception
    return app


def click(at, label):
    """Click the button whose label starts with `label` (labels may end with an arrow)."""
    [b for b in at.button if b.label.startswith(label)][0].click().run()
    assert not at.exception, [e.message for e in at.exception]


def page(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def to_review(at):
    click(at, "Continue to Time Slots")
    click(at, "Continue to Review")
    assert "Booking summary" in page(at) and "$34.47" in page(at)


def pick_reward(at):
    click(at, "Use a loyalty reward")
    [r for r in at.radio if r.label == "Reward to apply"][0].set_value("RWD-FREEBAG").run()
    click(at, "Apply Reward")


def pay_with(at, method_id):
    at.radio(key="wf04_pm").set_value(method_id).run()
    click(at, "Pay ") if any(b.label.startswith("Pay ") for b in at.button) else click(at, "Retry Payment")


def test_uc01_success_and_failure_paths(at):
    assert "Book Pickup &amp; Delivery" in page(at) and "Booking details" in page(at)
    to_review(at)
    click(at, "Proceed to Payment")
    pay_with(at, "PM-LEA-MC")
    text = page(at)
    assert "Payment was not authorized" in text and "Not confirmed" in text and "Not reserved" in text
    pay_with(at, "PM-LEA-VISA")
    assert "Booking confirmed" in page(at) and "Scheduled" in page(at)


def test_uc01_timeout(at):
    to_review(at)
    click(at, "Proceed to Payment")
    pay_with(at, "PM-LEA-DEB")
    assert "didn&#x27;t answer in time" in page(at) or "didn't answer in time" in page(at)


def test_uc07_reserved_restored_redeemed(at):
    to_review(at)
    pick_reward(at)
    text = page(at)
    assert "Reward Reserved" in text and "420 points" in text and "250 points" in text and "170 points" in text
    assert "$5.74" in text
    click(at, "Continue to Payment")
    pay_with(at, "PM-LEA-MC")
    text = page(at)
    assert "Points Restored" in text and "420 points" in text and "$34.47" in text
    click(at, "Return to Checkout")
    pick_reward(at)
    click(at, "Cancel Checkout")
    assert "Points Restored" in page(at) and "cancelled before payment" in page(at)
    click(at, "Return to Checkout")
    pick_reward(at)
    click(at, "Continue to Payment")
    pay_with(at, "PM-LEA-VISA")
    text = page(at)
    assert "Reward Redeemed" in text and "170 points" in text and "$5.74" in text
    click(at, "Continue to Confirmation")
    assert "Booking confirmed" in page(at)


def test_uc02_list_detail_and_empty_state(at):
    at.radio(key="nav").set_value("My Orders").run()
    assert "My Orders" in page(at)
    click(at, "View Status")
    text = page(at)
    assert "Current Order Status" in text and "Order Progress" in text
    assert not [b for b in at.button if "Cancel" in b.label or "Mark" in b.label]   # read-only
    click(at, "← Back to My Orders")
    at.selectbox(key="cust").set_value("CUS-NINA").run()
    assert "No orders yet" in page(at)
    click(at, "Book Pickup & Delivery")
    assert "Booking details" in page(at)


def test_other_pages_render(at):
    for name in ("Loyalty / Rewards", "Profile"):
        at.radio(key="nav").set_value(name).run()
        assert not at.exception and name in page(at)
    at.radio(key="role").set_value("Staff").run()
    assert not at.exception and [t.label for t in at.tabs] == ["Order board", "Routes", "Machines", "Inventory"]
