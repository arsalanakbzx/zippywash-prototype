"""The JSON API used by the web front end: every screen's action, run in memory like in the browser."""
import json
from datetime import date, timedelta

import pytest

from zippywash.api import ZippyWashAPI
from zippywash.database.repository import InMemoryRepository


@pytest.fixture
def api():
    return ZippyWashAPI(InMemoryRepository())


def ok(res):
    assert res["ok"], res.get("error")
    return res["data"]


def checkout(api, customer="CUS-LEA"):
    opts = ok(api.call("booking_options", {"customer_id": customer}))
    a = opts["addresses"][0]["id"]
    oid = ok(api.call("start_booking", {"customer_id": customer, "pickup_address_id": a, "delivery_address_id": a,
                                         "service_type_id": "SVC-WF", "bag_size": "Small"}))["order_id"]
    slots = ok(api.call("open_slots", {"customer_id": customer, "order_id": oid}))
    p = slots[3]
    d = next(s for s in slots if s["date"] > p["date"])
    order = ok(api.call("choose_slots", {"customer_id": customer, "order_id": oid, "pickup_slot_id": p["id"],
                                          "delivery_slot_id": d["id"]}))
    return oid, order


def test_bootstrap_and_json_string_interface(api):
    data = json.loads(api.call_json("bootstrap", "{}"))["data"]
    assert {c["id"] for c in data["customers"]} == {"CUS-LEA", "CUS-OMAR", "CUS-NINA"}
    assert json.loads(api.call_json("nope"))["ok"] is False


def test_uc01_fail_then_pay(api):
    oid, order = checkout(api)
    assert order["price"]["total"] == "34.47" and order["status"] == "Draft"
    res = ok(api.call("pay", {"customer_id": "CUS-LEA", "order_id": oid, "payment_method_id": "PM-LEA-MC"}))
    assert not res["authorized"] and res["payment_status"] == "Failed" and res["order"]["status"] == "Draft"
    res = ok(api.call("pay", {"customer_id": "CUS-LEA", "order_id": oid, "payment_method_id": "PM-LEA-VISA"}))
    assert res["authorized"] and res["order"]["status"] == "Scheduled" and res["order"]["payment"]["receipt"]


def test_uc07_reserve_restore_redeem(api):
    oid, _ = checkout(api)
    opts = ok(api.call("reward_options", {"customer_id": "CUS-LEA", "order_id": oid}))
    assert opts["loyalty"]["available"] == 420
    o = ok(api.call("reserve_reward", {"customer_id": "CUS-LEA", "order_id": oid, "reward_id": "RWD-FREEBAG"}))
    assert o["reward_state"] == "Reserved" and o["price"]["total"] == "5.74"
    assert (o["loyalty"]["balance"], o["loyalty"]["reserved"], o["loyalty"]["available"]) == (420, 250, 170)
    res = ok(api.call("pay", {"customer_id": "CUS-LEA", "order_id": oid, "payment_method_id": "PM-LEA-MC"}))
    assert res["restored_points"] == 250 and res["order"]["price"]["total"] == "34.47"
    ok(api.call("reserve_reward", {"customer_id": "CUS-LEA", "order_id": oid, "reward_id": "RWD-FREEBAG"}))
    res = ok(api.call("pay", {"customer_id": "CUS-LEA", "order_id": oid, "payment_method_id": "PM-LEA-VISA"}))
    assert res["redeemed_points"] == 250 and res["order"]["reward_state"] == "Redeemed"
    assert res["order"]["loyalty"]["balance"] == 170


def test_errors_come_back_as_messages(api):
    oid, _ = checkout(api)
    res = api.call("apply_promo", {"customer_id": "CUS-LEA", "order_id": oid, "code": "NOPE"})
    assert res["ok"] is False and "doesn't exist" in res["error"]
    res = api.call("order_status", {"customer_id": "CUS-LEA", "order_id": "ZW-NOT-MINE"})
    assert res["ok"] is False


def test_uc02_uc06_pages(api):
    orders = ok(api.call("my_orders", {"customer_id": "CUS-LEA"}))
    assert orders and all(o["customer"]["id"] == "CUS-LEA" for o in orders)
    assert ok(api.call("my_orders", {"customer_id": "CUS-NINA"})) == []
    detail = ok(api.call("order_status", {"customer_id": "CUS-LEA", "order_id": orders[0]["id"]}))
    assert detail["latest"]["status"]
    prof = ok(api.call("add_address", {"customer_id": "CUS-NINA", "street": "1 Test", "postal_code": "H3H 1K6"}))
    assert prof["address"]["serviceable"]
    repeat = ok(api.call("repeat_booking", {"customer_id": "CUS-LEA", "order_id": orders[0]["id"]}))
    assert repeat["order_id"].startswith("ZW-")


def test_staff_flows(api):
    routes = ok(api.call("routes", {"staff_id": "STF-ADM1"}))
    shift = next(s for s in routes["shifts"] if s["orders_waiting"])
    r = ok(api.call("build_route", {"staff_id": "STF-ADM1", "shift_id": shift["id"], "sector_id": "SEC-DT",
                                    "vehicle_id": "VAN-01"}))
    assert r["stops"]
    r = ok(api.call("optimize_route", {"staff_id": "STF-ADM1", "route_id": r["id"]}))
    ok(api.call("complete_stop", {"staff_id": "STF-ADM1", "stop_id": r["stops"][0]["id"]}))
    board = ok(api.call("staff_board", {"staff_id": "STF-DRV1"}))
    scheduled = next(o for o in board["orders"] if o["status"] == "Scheduled")
    assert scheduled["can_advance"]
    ok(api.call("advance_status", {"staff_id": "STF-DRV1", "order_id": scheduled["id"], "notes": "Collected"}))
    mach = ok(api.call("report_fault", {"staff_id": "STF-LDY1", "machine_id": "MCH-W1", "description": "Leak"}))
    rec = next(x for x in mach["machines"] if x["id"] == "MCH-W1")["open_record"]
    assert mach["slots"][0]["limit"] == 2
    ok(api.call("schedule_repair", {"staff_id": "STF-LDY1", "record_id": rec["id"],
                                    "repair_date": (date.today() + timedelta(days=1)).isoformat()}))
    ok(api.call("repair_details", {"staff_id": "STF-LDY1", "record_id": rec["id"], "details": "New seal"}))
    ok(api.call("complete_repair", {"staff_id": "STF-LDY1", "record_id": rec["id"]}))
    inv = ok(api.call("record_stock", {"staff_id": "STF-LDY1", "item_id": "INV-SOFT", "movement_type": "Consumption",
                                       "quantity": "4"}))
    assert next(i for i in inv if i["id"] == "INV-SOFT")["alert"]
    adm = ok(api.call("loyalty_admin", {"staff_id": "STF-ADM1"}))
    acc = adm["accounts"][0]["id"]
    ok(api.call("correct_points", {"staff_id": "STF-ADM1", "account_id": acc, "points": 10, "reason": "Goodwill"}))
    assert api.call("toggle_reward", {"staff_id": "STF-DRV1", "reward_id": "RWD-5OFF"})["ok"] is False


def test_reset_restores_sample_data(api):
    oid, _ = checkout(api)
    ok(api.call("reset"))
    assert ok(api.call("booking_options", {"customer_id": "CUS-LEA"}))["draft"] is None


def test_step1_quote_matches_real_order_price():
    """The price shown on Booking Details must equal what Review computes, for every service and size."""
    api = ZippyWashAPI(InMemoryRepository())
    opts = api.call("booking_options", {"customer_id": "CUS-NINA"})["data"]
    nina_addr = api.call("profile", {"customer_id": "CUS-NINA"})["data"]["addresses"]
    if not nina_addr:
        api.call("add_address", {"customer_id": "CUS-NINA", "street": "1 Test St", "postal_code": "H3G 1L3"})
    addr = [a for a in api.call("booking_options", {"customer_id": "CUS-NINA"})["data"]["addresses"]][0]["id"]
    for svc in opts["services"]:
        for size, quote in svc["quotes"].items():
            r = api.call("start_booking", {"customer_id": "CUS-NINA", "pickup_address_id": addr, "delivery_address_id": addr,
                                           "service_type_id": svc["id"], "bag_size": size})
            oid = r["data"]["order_id"]
            slots = api.call("open_slots", {"customer_id": "CUS-NINA", "order_id": oid})["data"]
            later = next(x for x in slots if x["date"] > slots[0]["date"])
            order = api.call("choose_slots", {"customer_id": "CUS-NINA", "order_id": oid,
                                              "pickup_slot_id": slots[0]["id"], "delivery_slot_id": later["id"]})["data"]
            assert order["price"]["subtotal"] == quote["subtotal"], (svc["name"], size)
            assert order["price"]["total"] == quote["total"], (svc["name"], size)
            api.call("cancel_checkout", {"customer_id": "CUS-NINA", "order_id": order["id"]})
