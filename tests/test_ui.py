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
    [b for b in at.button if b.label == label][0].click().run()
    assert not at.exception, [e.message for e in at.exception]


def headings(at):
    return [s.value for s in at.subheader]


def to_review(at):
    click(at, "Continue to Time Slots")
    click(at, "Continue to Review")
    assert headings(at) == ["Review estimate"]


def pay_with(at, method_id):
    at.selectbox(key="wf04_pm").set_value(method_id).run()
    [b for b in at.button if b.label.startswith("Pay ")][0].click().run()
    assert not at.exception


def test_uc01_success_and_failure_paths(at):
    assert headings(at) == ["Book a pickup"]
    to_review(at)
    assert "$34.47" in [m.value for m in at.markdown if "Total" in m.value][-1].replace("\\", "")
    click(at, "Proceed to Payment")
    pay_with(at, "PM-LEA-MC")
    assert headings(at) == ["Payment not authorized"]
    assert "not confirmed" in at.error[0].value and "no time slots were reserved" in at.error[0].value
    click(at, "Retry Payment")
    pay_with(at, "PM-LEA-VISA")
    assert headings(at) == ["Booking confirmed"] and "Scheduled" in at.success[0].value


def test_uc07_reserved_restored_redeemed(at):
    to_review(at)
    click(at, "Use a loyalty reward")
    [r for r in at.radio if r.label == "Reward to apply"][0].set_value("RWD-FREEBAG").run()
    click(at, "Apply Reward")
    assert headings(at) == ["Reward reserved"]
    assert [(m.label, m.value) for m in at.metric] == [("Point balance", "420"), ("Reserved", "250"),
                                                       ("Available", "170")]
    click(at, "Continue to Payment")
    pay_with(at, "PM-LEA-MC")
    assert headings(at) == ["Points restored"] and at.metric[0].value == "420"
    click(at, "Return to Checkout")
    click(at, "Use a loyalty reward")
    [r for r in at.radio if r.label == "Reward to apply"][0].set_value("RWD-FREEBAG").run()
    click(at, "Apply Reward")
    click(at, "Continue to Payment")
    pay_with(at, "PM-LEA-VISA")
    assert headings(at) == ["Reward redeemed"] and at.metric[0].value == "170"
    click(at, "Continue to Confirmation")
    assert headings(at) == ["Booking confirmed"]


def test_uc02_list_detail_and_empty_state(at):
    at.radio(key="nav").set_value("My Orders").run()
    assert headings(at) == ["My orders"]
    [b for b in at.button if b.label == "View Status"][0].click().run()
    assert headings(at) == ["Current order status"]
    assert not [b for b in at.button if "Cancel" in b.label or "Mark" in b.label]   # read-only
    click(at, "Back to My Orders")
    at.selectbox(key="cust").set_value("CUS-NINA").run()
    assert headings(at) == ["No orders yet"]
    click(at, "Book Pickup & Delivery")
    assert headings(at) == ["Book a pickup"]


def test_other_pages_render(at):
    for page in ("Loyalty / Rewards", "Profile"):
        at.radio(key="nav").set_value(page).run()
        assert not at.exception and headings(at) == [page]
    at.radio(key="role").set_value("Staff").run()
    assert not at.exception and [t.label for t in at.tabs] == ["Order board", "Routes", "Machines", "Inventory"]
