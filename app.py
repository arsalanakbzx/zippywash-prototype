"""ZippyWash Prototype 2 — Streamlit user interface.

Run:  streamlit run app.py

The UI only collects input, keeps track of which screen is shown, and displays results.
Every rule runs in the domain classes, called through the services. Screen IDs (WF01 ...)
match the Milestone 6 HCI design: UC01-SC1 booking, UC02-SC1 order status, UC07-SC2 rewards.
"""
from __future__ import annotations

from datetime import timedelta

import streamlit as st

from zippywash.common import (STATUS_SEQUENCE, BagSize, DomainError, LoyaltyAccountStatus, LoyaltyTransactionType,
                              MachineStatus, MaintenanceStatus, OrderStatus, PickupRequestType, RouteStatus,
                              StaffRole, StockMovementType, now_local, today_local)
from zippywash.customer_order_service.customer import Customer
from zippywash.customer_order_service.order import Order
from zippywash.customer_order_service.reward import Reward
from zippywash.customer_order_service.service_type import ServiceType
from zippywash.customer_order_service.time_slot import TimeSlot
from zippywash.database.db import connect, create_schema, drop_all_tables, is_empty
from zippywash.database.repository import Repository
from zippywash.database.seed import ensure_rolling_slots, seed
from zippywash.operations_resource.inventory_item import InventoryItem
from zippywash.operations_resource.machine import Machine
from zippywash.operations_resource.route import Route
from zippywash.operations_resource.sector import Sector
from zippywash.operations_resource.staff_member import StaffMember
from zippywash.operations_resource.vehicle import Vehicle
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService
from zippywash.services.operations_service import OperationsService
from zippywash.services.order_tracking_service import OrderTrackingService

REPO_URL = "https://github.com/arsalanakbzx/zippywash-prototype"
NAV = ["Book Pickup", "My Orders", "Loyalty / Rewards", "Profile"]

st.set_page_config(page_title="ZippyWash", page_icon="🧺", layout="centered")
st.markdown("""
<style>
.zw-steps{display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 14px}
.zw-step{padding:3px 10px;border-radius:999px;font-size:.8rem;border:1px solid rgba(128,128,128,.35);opacity:.55}
.zw-step.done{opacity:1;background:rgba(47,125,79,.15);border-color:rgba(47,125,79,.6)}
.zw-step.now{opacity:1;background:rgba(15,124,147,.18);border-color:#0f7c93;font-weight:600}
.zw-step.cancel{opacity:1;background:rgba(180,84,26,.15);border-color:#b4541a;font-weight:600}
.zw-chip{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:600}
.zw-chip.Reserved{background:rgba(201,138,0,.18);color:#8a5d00}
.zw-chip.Redeemed{background:rgba(47,125,79,.18);color:#1f6b3f}
.zw-chip.Restored{background:rgba(15,124,147,.18);color:#0b5f71}
</style>""", unsafe_allow_html=True)


# =================================================================
# Setup: one database connection; every page run loads the data, then saves what changed.
# =================================================================
@st.cache_resource
def get_repo() -> Repository:
    conn = connect()
    create_schema(conn)
    repo = Repository(conn)
    if is_empty(conn):
        seed(repo)
    return repo


repo = get_repo()
world = repo.load()
if ensure_rolling_slots(world):          # bookable slots always cover the next 14 days
    repo.commit(world)
booking, tracking = BookingService(world), OrderTrackingService(world)
profiles, operations = CustomerProfileService(world), OperationsService(world)


def save_and_rerun(flash: tuple[str, str] | None = None) -> None:
    repo.commit(world)
    if flash:
        st.session_state["flash"] = flash
    st.rerun()


def show_flash() -> None:
    if "flash" in st.session_state:
        kind, text = st.session_state.pop("flash")
        getattr(st, kind)(text)


def money(v) -> str:
    return f"${v:,.2f}".replace("$", "\\$")   # "\$" stops Streamlit reading two amounts as a formula


def chip(state: str) -> str:
    return f'<span class="zw-chip {state}">{state}</span>'


def steps(current: int, labels=("Details", "Time slots", "Review", "Payment", "Confirmation")) -> None:
    html = []
    for i, label in enumerate(labels, start=1):
        cls = "done" if i < current else "now" if i == current else ""
        html.append(f'<span class="zw-step {cls}">{i} · {label}</span>')
    st.markdown(f'<div class="zw-steps">{"".join(html)}</div>', unsafe_allow_html=True)


def lifecycle(order: Order) -> None:
    """Read-only progress indicator (no controls)."""
    if order.status == OrderStatus.CANCELLED:
        st.markdown('<div class="zw-steps"><span class="zw-step cancel">Cancelled</span></div>',
                    unsafe_allow_html=True)
        return
    flow = STATUS_SEQUENCE[1:]
    current = flow.index(order.status)
    html = [f'<span class="zw-step {"done" if i < current else "now" if i == current else ""}">{s.value}</span>'
            for i, s in enumerate(flow)]
    st.markdown(f'<div class="zw-steps">{"".join(html)}</div>', unsafe_allow_html=True)


def price_table(order: Order) -> None:
    p = order.price_breakdown()
    rows = [(f"{order.service_type.name}, {order.bag_size.value} bag", money(p.subtotal))]
    if order.applied_promotion is not None:
        rows.append((f"Promo {order.applied_promotion.code}", "−" + money(p.discount)))
    if order.applied_reward is not None:
        rows.append((f"Reward: {order.applied_reward.name}", "−" + money(p.discount)))
    rows += [("Delivery fee", money(p.delivery_fee)), ("GST 5%", money(p.gst)), ("QST 9.975%", money(p.qst)),
             ("**Total**", f"**{money(p.total)}**")]
    st.markdown("| | Amount |\n|---|---:|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows))


def choose(widget, label: str, objs: list, fmt, **kw):
    """Select a domain object by its ID. Every page run loads fresh objects, so widgets hold IDs."""
    by_id = {getattr(o, o._pk): o for o in objs}
    picked = widget(label, list(by_id), format_func=lambda k: fmt(by_id[k]), **kw)
    return by_id.get(picked) if picked is not None else None


def when(dt) -> str:
    return f"{dt:%a %b %d, %H:%M}"


# =================================================================
# Sidebar: who is using the system
# =================================================================
st.sidebar.title("🧺 ZippyWash")
st.sidebar.caption("Prototype 2 · BTM 495 Team 5")
role = st.sidebar.radio("Sign in as", ["Customer", "Staff"], key="role", horizontal=True)
if role == "Customer":
    customers = sorted(world.all(Customer), key=lambda c: c.name)
    customer = choose(st.sidebar.selectbox, "Customer account", customers, key="cust",
                      fmt=lambda c: c.name + ("" if c.is_active() else " (deactivated)"))
else:
    rank = {StaffRole.DRIVER: 0, StaffRole.LAUNDRY_STAFF: 1, StaffRole.ADMINISTRATOR: 2}
    staff_list = sorted(world.all(StaffMember), key=lambda s: min(rank[r] for r in s.roles))
    staff = choose(st.sidebar.selectbox, "Staff member", staff_list, key="staff",
                   fmt=lambda s: f"{s.name} · {', '.join(r.label for r in s.roles)}")
st.sidebar.divider()
st.sidebar.caption("All people, addresses and cards are sample data. Everyone testing this link shares the "
                   "same data. No real payments happen.")
with st.sidebar.expander("Reset demo data"):
    st.write("Deletes every change made by testers and restores the original sample data.")
    if st.button("Reset demo data", disabled=not st.checkbox("Yes, reset everything", key="reset_ok")):
        drop_all_tables(repo.conn)
        create_schema(repo.conn)
        seed(repo)
        st.session_state.clear()
        st.rerun()
st.sidebar.markdown(f"[Source code on GitHub]({REPO_URL})")


# =================================================================
# UC01-SC1 · UC07-SC2: booking checkout (state per customer)
# =================================================================
def checkout(c: Customer) -> dict:
    return st.session_state.setdefault(f"co_{c.customer_id}", {"step": "WF01", "order": None})


def go(c: Customer, step: str, **extra) -> None:
    state = checkout(c)
    state["step"] = step
    state.update(extra)


def current_order(c: Customer) -> Order | None:
    oid = checkout(c).get("order")
    return next((o for o in c.orders if o.order_id == oid), None) if oid else None


def reset_checkout(c: Customer) -> None:
    st.session_state[f"co_{c.customer_id}"] = {"step": "WF01", "order": None}


def book_pickup(c: Customer) -> None:
    state = checkout(c)
    order = current_order(c)
    step = state["step"]
    if step != "WF01" and (order is None or (order.status == OrderStatus.CANCELLED)):
        reset_checkout(c)
        step, order = "WF01", None
    {"WF01": wf01_details, "WF02": wf02_slots, "WF03": wf03_review, "WF04": wf04_payment,
     "WF04E": wf04e_not_authorized, "WF05": wf05_confirmation, "R01": uc07_wf01_choose,
     "R02": uc07_wf02_reserved, "R03": uc07_wf03_redeemed, "R03E": uc07_wf03e_restored}[step](c, order)


def wf01_details(c: Customer, order: Order | None) -> None:
    st.subheader("Book a pickup")
    steps(1)
    if not c.is_active():
        st.info("This account is deactivated, so it can't place new orders. Your history is still in My Orders.")
        return
    serviceable = [a for a in c.addresses if a.validate()]
    if not serviceable:
        st.info("Add an address inside our service area under Profile first.")
        return
    services = [s for s in world.all(ServiceType) if s.active]
    with st.form("wf01"):
        c1, c2 = st.columns(2)
        service = choose(c1.selectbox, "Service type", services, fmt=lambda s: f"{s.name} (${s.base_rate:,.2f} / small bag)")
        bag = c2.radio("Bag size", list(BagSize), format_func=lambda b: b.value, horizontal=True)
        pickup = choose(c1.selectbox, "Pickup address", serviceable, fmt=lambda a: a.label())
        delivery = choose(c2.selectbox, "Delivery address", serviceable, fmt=lambda a: a.label())
        req = st.radio("Pickup request", list(PickupRequestType), horizontal=True,
                       format_func=lambda t: {"Scheduled": "Scheduled pickup", "Live": "Live pickup (same day)"}[t.value],
                       help="A live pickup can be added to today's driver route if there's room.")
        st.caption("Addresses outside our service area aren't listed.")
        if st.form_submit_button("Continue to Time Slots", type="primary"):
            try:
                new = booking.start_booking(c, pickup, delivery, service, bag, req)
                go(c, "WF02", order=new.order_id)
                save_and_rerun()
            except DomainError as e:
                st.error(str(e))


def wf02_slots(c: Customer, order: Order) -> None:
    st.subheader("Select time slots")
    steps(2)
    slots = booking.open_slots(now_local())
    if not slots:
        st.warning("No time slots are available right now. Try again later.")
        return
    fmt = lambda s: f"{s.label()}  ({s.available_capacity} left)"
    c1, c2 = st.columns(2)
    p_slot = choose(c1.selectbox, "Pickup time", slots, fmt, key="wf02_p")
    d_choices = [s for s in slots if s.date > p_slot.date]
    d_slot = choose(c2.selectbox, "Delivery time", d_choices, fmt, key="wf02_d",
                          help="Delivery is at least one day after pickup.")
    st.caption("Choosing a time doesn't reserve it yet. Both times are reserved only after your payment is authorized.")
    b1, b2 = st.columns([1, 2])
    if b1.button("Back"):
        go(c, "WF01")
        st.rerun()
    if b2.button("Continue to Review", type="primary", disabled=d_slot is None):
        try:
            booking.choose_slots(order, p_slot, d_slot)
            go(c, "WF03")
            save_and_rerun()
        except DomainError as e:
            st.error(str(e))


def wf03_review(c: Customer, order: Order) -> None:
    st.subheader("Review estimate")
    steps(3)
    show_flash()
    st.markdown(f"**Service:** {order.service_type.name}, {order.bag_size.value} bag  \n"
                f"**Pickup:** {order.pickup_time_slot.label()} at {order.pickup_address.label()}  \n"
                f"**Delivery:** {order.delivery_time_slot.label()} at {order.delivery_address.label()}")
    price_table(order)
    if order.applied_reward is not None:
        st.markdown(f"Reward {chip('Reserved')} — points are redeemed only after payment is authorized.",
                    unsafe_allow_html=True)

    with st.expander("Apply promotion or reward", expanded=False):
        if order.applied_reward is not None:
            st.write(f"Reward **{order.applied_reward.name}** is applied. An order can't also use a promo code.")
        elif order.applied_promotion is not None:
            st.write(f"Promo code **{order.applied_promotion.code}** is applied. An order can't also use a reward.")
            if st.button("Remove promo code"):
                booking.remove_promo_code(order)
                save_and_rerun()
        else:
            c1, c2 = st.columns([2, 1])
            code = c1.text_input("Promo code", placeholder="WELCOME10", label_visibility="collapsed")
            if c2.button("Apply code"):
                try:
                    booking.apply_promo_code(order, code)
                    save_and_rerun(("success", "Promo code applied."))
                except DomainError as e:
                    st.error(str(e))
            if st.button("Use a loyalty reward"):
                go(c, "R01")
                st.rerun()

    b1, b2 = st.columns([1, 2])
    if b1.button("Edit booking details"):
        booking.cancel_checkout(order)
        reset_checkout(c)
        save_and_rerun()
    if b2.button("Proceed to Payment", type="primary"):
        go(c, "WF04")
        st.rerun()


def wf04_payment(c: Customer, order: Order) -> None:
    st.subheader("Payment")
    steps(4)
    methods = [m for m in c.payment_methods if m.active]
    st.markdown(f"Amount to authorize: **{money(order.estimated_total)}**")
    if order.applied_reward is not None:
        st.markdown(f"{order.applied_reward.name} {chip('Reserved')}", unsafe_allow_html=True)
    method = choose(st.selectbox, "Payment method", methods, lambda m: m.label, key="wf04_pm")
    st.caption("Payment is authorized online before the booking is confirmed. The driver never collects payment.")
    b1, b2 = st.columns([1, 2])
    if b1.button("Back to Review"):
        go(c, "WF03")
        st.rerun()
    if b2.button(f"Pay ${order.estimated_total:,.2f}", type="primary", disabled=method is None):
        try:
            had_reward = order.applied_reward is not None
            outcome = booking.pay(order, method)
            if outcome.authorized:
                go(c, "R03" if outcome.redeemed else "WF05")
            elif had_reward and outcome.restored is not None:
                go(c, "R03E", reason=outcome.message, cause="payment")
            else:
                go(c, "WF04E", reason=outcome.message)
            save_and_rerun()
        except DomainError as e:
            st.error(str(e))


def wf04e_not_authorized(c: Customer, order: Order) -> None:
    st.subheader("Payment not authorized")
    steps(4)
    st.error(f"{checkout(c).get('reason', 'Payment was not authorized.')}  \n"
             "Your booking was **not confirmed** and **no time slots were reserved**.")
    b1, b2 = st.columns(2)
    if b1.button("Retry Payment", type="primary"):
        go(c, "WF04")
        st.rerun()
    if b2.button("Back to Review"):
        go(c, "WF03")
        st.rerun()


def wf05_confirmation(c: Customer, order: Order) -> None:
    st.subheader("Booking confirmed")
    steps(5)
    payment = order.authorized_payment()
    st.success(f"Order **{order.order_id}** is **{order.status.value}**. A confirmation was sent to "
               f"{c.contact_details}.")
    st.markdown(f"**Service:** {order.service_type.name}, {order.bag_size.value} bag  \n"
                f"**Pickup:** {order.pickup_time_slot.label()} · {order.pickup_address.label()}  \n"
                f"**Delivery:** {order.delivery_time_slot.label()} · {order.delivery_address.label()}  \n"
                f"**Payment:** Authorized · receipt {payment.receipt_number}  \n"
                f"**Total paid:** {money(order.final_total)}")
    st.caption("Next: the driver picks up your bag in the pickup window. Follow each step in My Orders.")
    b1, b2 = st.columns(2)
    if b1.button("Track in My Orders", type="primary"):
        st.session_state["nav_next"] = "My Orders"
        st.session_state[f"view_{c.customer_id}"] = order.order_id
        reset_checkout(c)
        st.rerun()
    if b2.button("Book another pickup"):
        reset_checkout(c)
        st.rerun()


# ---------------- UC07-SC2 ----------------
def uc07_wf01_choose(c: Customer, order: Order) -> None:
    st.subheader("Choose a reward")
    steps(3)
    account = c.loyalty_account
    if account is None or account.status != LoyaltyAccountStatus.ACTIVE:
        st.info("Join the loyalty program under Loyalty / Rewards to use rewards.")
    else:
        m1, m2 = st.columns(2)
        m1.metric("Current points", account.point_balance)
        m2.metric("Available points", account.available_points())
    options = booking.reward_options(order)
    eligible = [r for r, why in options if why is None]
    for reward, why in options:
        line = f"**{reward.name}** · {reward.points_required} points · {money(reward.discount_amount)} off"
        st.markdown(line if why is None else f"{line}  \n:gray[Not available: {why}]")
    choice = choose(st.radio, "Reward to apply", eligible, lambda r: r.name, index=None,
                      disabled=not eligible) if eligible else None
    b1, b2 = st.columns([1, 2])
    if b1.button("Back to Review"):
        go(c, "WF03")
        st.rerun()
    if b2.button("Apply Reward", type="primary", disabled=choice is None):
        try:
            booking.reserve_reward(order, choice)
            go(c, "R02")
            save_and_rerun()
        except DomainError as e:
            st.error(str(e))


def uc07_wf02_reserved(c: Customer, order: Order) -> None:
    st.subheader("Reward reserved")
    steps(3)
    account = c.loyalty_account
    st.markdown(f"**{order.applied_reward.name}** {chip('Reserved')}", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Point balance", account.point_balance)
    m2.metric("Reserved", account.reserved_points())
    m3.metric("Available", account.available_points())
    price_table(order)
    st.caption("Your points are on hold, not used yet. They're redeemed only if the payment is authorized.")
    b1, b2 = st.columns([1, 2])
    if b1.button("Cancel Checkout"):
        booking.release_reward(order)
        go(c, "R03E", cause="cancel", reason="Checkout was cancelled before payment.")
        save_and_rerun()
    if b2.button("Continue to Payment", type="primary"):
        go(c, "WF04")
        st.rerun()


def uc07_wf03_redeemed(c: Customer, order: Order) -> None:
    st.subheader("Reward redeemed")
    steps(4)
    account = c.loyalty_account
    redemption = next(t for t in reversed(account.transactions)
                      if t.type == LoyaltyTransactionType.REDEMPTION and t.order is order)
    st.markdown(f"**{redemption.reward.name}** {chip('Redeemed')}", unsafe_allow_html=True)
    st.success(f"Payment authorized. {redemption.points} points were redeemed.")
    m1, m2 = st.columns(2)
    m1.metric("Point balance", account.point_balance)
    m2.metric("Paid", f"${order.final_total:,.2f}")
    if st.button("Continue to Confirmation", type="primary"):
        go(c, "WF05")
        st.rerun()


def uc07_wf03e_restored(c: Customer, order: Order) -> None:
    st.subheader("Points restored")
    state = checkout(c)
    if state.get("cause") == "payment":
        st.error(f"Payment not authorized: {state.get('reason')}  \n"
                 "Your booking was not confirmed and no time slots were reserved.")
    else:
        st.info(state.get("reason", "Checkout was cancelled."))
    account = c.loyalty_account
    st.markdown(f"Reserved points {chip('Restored')}", unsafe_allow_html=True)
    m1, m2 = st.columns(2)
    m1.metric("Available points", account.available_points())
    m2.metric("Checkout total", f"${order.estimated_total:,.2f}")
    st.caption("The reward was removed from this checkout. No points were used.")
    if st.button("Return to Checkout", type="primary"):
        go(c, "WF03")
        st.rerun()


# =================================================================
# UC02-SC1: My Orders (read-only)
# =================================================================
def my_orders(c: Customer) -> None:
    key = f"view_{c.customer_id}"
    orders = tracking.my_orders(c)
    if not orders:                                  # WF01E
        st.subheader("No orders yet")
        st.write("When you book a pickup, your orders and their progress show up here.")
        if st.button("Book Pickup & Delivery", type="primary"):
            st.session_state["nav_next"] = "Book Pickup"
            st.rerun()
        return
    selected = st.session_state.get(key)
    if selected:                                    # WF02
        try:
            order = tracking.order_for(c, selected)
        except DomainError as e:
            st.error(str(e))
            st.session_state.pop(key)
            return
        latest = order.get_current_status()
        st.subheader("Current order status")
        st.markdown(f"**Order {order.order_id}** · {order.service_type.name}, {order.bag_size.value} bag")
        lifecycle(order)
        m1, m2 = st.columns(2)
        m1.metric("Latest status", latest.status.value)
        m2.metric("Updated", when(latest.changed_at))
        st.markdown(f"**Note:** {latest.notes or 'No note available'}")
        st.caption("This view is read-only.")
        if st.button("Back to My Orders"):
            st.session_state.pop(key)
            st.rerun()
        return
    st.subheader("My orders")                        # WF01
    for order in orders:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{order.order_id}** · {order.created_at:%b %d, %Y}  \n"
                        f"{order.service_type.name}, {order.bag_size.value} bag · "
                        f"**{order.get_current_status().status.value}**")
            if c2.button("View Status", key=f"vs_{order.order_id}"):
                st.session_state[key] = order.order_id
                st.rerun()


# =================================================================
# Loyalty / Rewards and Profile (UC06)
# =================================================================
STATE_LABEL = {LoyaltyTransactionType.RESERVATION: "Reserved", LoyaltyTransactionType.REDEMPTION: "Redeemed",
               LoyaltyTransactionType.RESTORATION: "Restored", LoyaltyTransactionType.EARN: "Earned",
               LoyaltyTransactionType.CORRECTION: "Correction", LoyaltyTransactionType.REVERSAL: "Reversed",
               LoyaltyTransactionType.ENROLLMENT: "Joined"}


def loyalty_page(c: Customer) -> None:
    st.subheader("Loyalty / Rewards")
    show_flash()
    account = c.loyalty_account
    if account is None or account.status != LoyaltyAccountStatus.ACTIVE:
        st.write("Earn 1 point for every dollar paid once your order is delivered, and use points for rewards.")
        if st.button("Join the loyalty program" if account is None else "Reactivate membership", type="primary",
                     disabled=not c.is_active()):
            try:
                profiles.join_loyalty(c)
                save_and_rerun(("success", "Welcome to ZippyWash Rewards."))
            except DomainError as e:
                st.error(str(e))
        return
    s = account.view_loyalty_summary()
    m1, m2, m3 = st.columns(3)
    m1.metric("Point balance", s.point_balance)
    m2.metric("Reserved", s.reserved_points)
    m3.metric("Available", s.available_points)
    st.markdown("**Rewards**")
    for r in sorted(world.all(Reward), key=lambda r: r.points_required):
        if r.is_available():
            st.write(f"🎁 {r.name} · {r.points_required} points · {money(r.discount_amount)} off")
    st.caption("Use a reward at checkout: Book Pickup → Review estimate → Apply promotion or reward.")
    st.markdown("**Recent activity**")
    st.table([{"When": when(t.created_at), "Activity": STATE_LABEL[t.type], "Points": t.points,
               "Details": t.reason or ""} for t in s.recent_transactions])


def profile_page(c: Customer) -> None:
    st.subheader("Profile")
    show_flash()
    with st.form("profile"):
        name = st.text_input("Name", c.name)
        contact = st.text_input("Email or phone", c.contact_details)
        prefs = st.text_input("Service preferences (optional)", c.service_preferences or "",
                              placeholder="e.g. Unscented detergent")
        if st.form_submit_button("Save profile"):
            try:
                profiles.update_profile(c, name, contact, prefs)
                save_and_rerun(("success", "Profile saved."))
            except DomainError as e:
                st.error(str(e))
    st.markdown("**Saved addresses**")
    for a in c.addresses:
        st.write(("✅ " if a.serviceable else "⚠️ ") + a.label() +
                 ("" if a.serviceable else " — outside our service area") +
                 (f"  \n_Access: {a.access_instructions}_" if a.access_instructions else ""))
    with st.form("add_address", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        street = c1.text_input("Street address")
        postal = c2.text_input("Postal code", placeholder="H3H 1K6")
        access = st.text_input("Access instructions (optional)", placeholder="e.g. Buzz 08, leave with concierge")
        if st.form_submit_button("Add address"):
            try:
                a = profiles.add_address(c, street, postal, access)
                save_and_rerun(("success", "Address saved.") if a.serviceable
                               else ("warning", "Address saved, but we don't serve that area yet."))
            except DomainError as e:
                st.error(str(e))
    st.markdown("**Saved payment methods**")
    for m in c.payment_methods:
        st.write("💳 " + m.label)
    st.caption("Only the payment processor's token is stored, never a card number.")
    st.markdown("**Notifications**")
    for n in sorted(c.notifications, key=lambda n: n.created_at, reverse=True)[:8]:
        st.write(f"`{n.created_at:%b %d %H:%M}` {n.message}")
    if c.is_active():
        with st.expander("Deactivate account"):
            st.write("You won't be able to book new pickups. Your order history is kept.")
            if st.button("Deactivate my account", disabled=not st.checkbox("I understand", key="deact_ok")):
                profiles.deactivate_account(c)
                save_and_rerun(("info", "Your account is deactivated."))


# =================================================================
# Staff (operations)
# =================================================================
def staff_orders(s: StaffMember) -> None:
    show_flash()
    orders = tracking.active_orders()
    if not orders:
        st.info("No active orders right now.")
    for order in orders:
        nxt = order.next_status()
        with st.container(border=True):
            st.markdown(f"**{order.order_id}** · {order.customer.name} · {order.service_type.name}, "
                        f"{order.bag_size.value} · pickup {order.pickup_time_slot.label()}"
                        + (" · **live pickup**" if order.pickup_request_type == PickupRequestType.LIVE else ""))
            lifecycle(order)
            if nxt is None:
                continue
            c1, c2 = st.columns([3, 2])
            note = c1.text_input("Note", key=f"n_{order.order_id}", label_visibility="collapsed",
                                 placeholder="Note for the customer (optional)")
            if c2.button(f"Mark '{nxt.value}'", key=f"b_{order.order_id}", use_container_width=True):
                try:
                    tracking.advance_status(order, s, note)
                    save_and_rerun(("success", f"{order.order_id}: {nxt.value}."))
                except DomainError as e:
                    st.error(str(e))
            if order.status == OrderStatus.SCHEDULED and s.check_authorization(StaffRole.ADMINISTRATOR):
                if st.button("Cancel and refund", key=f"cx_{order.order_id}"):
                    tracking.cancel_order(order, s)
                    save_and_rerun(("info", f"{order.order_id} cancelled and refunded."))


def staff_routes(s: StaffMember) -> None:
    show_flash()
    routes = sorted(world.all(Route), key=lambda r: r.route_date, reverse=True)
    for route in routes:
        with st.container(border=True):
            st.markdown(f"**{route.route_id}** · {route.route_date:%a %b %d} · {route.sector.name} · "
                        f"{route.vehicle.vehicle_id} · driver {route.staff_shift.staff_member.name} · "
                        f"**{route.status.value}** · {route.occupied_slots}/{route.vehicle.slot_capacity} slots · "
                        f"{route.total_distance} km")
            st.table([{"#": x.sequence_number, "Stop": x.stop_type.value, "Order": x.order.order_id,
                       "Address": x.address.label(),
                       "ETA": f"{x.estimated_arrival_time:%H:%M}" if x.estimated_arrival_time else "-",
                       "Status": x.status.value} for x in route.stops])
            if route.flagged_orders:
                st.caption("Didn't fit the vehicle: " + ", ".join(o.order_id for o in route.flagged_orders))
            b1, b2, b3 = st.columns(3)
            try:
                if route.status == RouteStatus.DRAFT and b1.button("Optimize", key=f"opt_{route.route_id}"):
                    route.optimize()
                    save_and_rerun(("success", "Route optimized."))
                if route.status == RouteStatus.OPTIMIZED and b2.button("Finalize", key=f"fin_{route.route_id}"):
                    route.finalize_route()
                    save_and_rerun(("success", "Route finalized. It can't be changed now."))
                live = [o for o in tracking.active_orders() if o.pickup_request_type == PickupRequestType.LIVE
                        and o.status == OrderStatus.SCHEDULED and not o.route_stops]
                if live and route.status not in (RouteStatus.FINALIZED, RouteStatus.COMPLETED):
                    pick = choose(b3.selectbox, "Live pickup", live, key=f"lp_{route.route_id}",
                                  fmt=lambda o: o.order_id, label_visibility="collapsed")
                    if b3.button("Insert live pickup", key=f"ins_{route.route_id}"):
                        ok = operations.insert_live_pickup(route, pick)
                        save_and_rerun(("success", "Live pickup added.") if ok else
                                       ("warning", "That pickup can't be added (sector, capacity or status)."))
            except DomainError as e:
                st.error(str(e))
    st.markdown("**Build a route**")
    shifts = [sh for st_ in world.all(StaffMember) for sh in st_.shifts if sh.route is None
              and sh.shift_date >= today_local() and sh.staff_member.check_authorization(StaffRole.DRIVER)
              and StaffRole.DRIVER in sh.staff_member.roles]
    if not shifts:
        st.caption("No free driver shifts.")
        return
    with st.form("build_route"):
        shift = choose(st.selectbox, "Driver shift", sorted(shifts, key=lambda x: x.shift_date),
                       fmt=lambda x: f"{x.shift_date:%a %b %d} {x.start_time:%H:%M}-{x.end_time:%H:%M} · "
                                                   f"{x.staff_member.name}")
        sector = choose(st.selectbox, "Sector", [x for x in world.all(Sector) if x.active], fmt=lambda x: x.name)
        vehicle = choose(st.selectbox, "Vehicle", world.all(Vehicle),
                         fmt=lambda v: f"{v.vehicle_id} · {v.slot_capacity} slots · {v.status.value}")
        if st.form_submit_button("Build route", type="primary"):
            try:
                route = operations.build_route(shift, sector, vehicle, shift.shift_date)
                save_and_rerun(("success", f"Route {route.route_id} built with {len(route.stops)} stops."))
            except DomainError as e:
                st.error(str(e))


def staff_machines(s: StaffMember) -> None:
    show_flash()
    for m in world.all(Machine):
        with st.container(border=True):
            st.markdown(f"**{m.machine_id}** · {m.type.value} · {m.status.value} · "
                        f"capacity {m.calculate_capacity()} kg/cycle")
            record = m.open_record()
            try:
                if record is None:
                    c1, c2 = st.columns([3, 1])
                    desc = c1.text_input("Fault", key=f"f_{m.machine_id}", label_visibility="collapsed",
                                         placeholder="Describe a fault to report it")
                    if c2.button("Report fault", key=f"rf_{m.machine_id}"):
                        operations.report_fault(m, desc, s)
                        save_and_rerun(("warning", f"{m.machine_id} reported faulty. Time-slot capacity updated."))
                else:
                    st.write(f"Open repair: {record.fault_description} · {record.status.value}"
                             + (f" · scheduled {record.scheduled_date:%b %d}" if record.scheduled_date else ""))
                    c1, c2, c3 = st.columns(3)
                    if record.status == MaintenanceStatus.REPORTED and c1.button("Schedule tomorrow",
                                                                                 key=f"sc_{m.machine_id}"):
                        record.schedule(today_local() + timedelta(days=1), s)
                        save_and_rerun()
                    details = c2.text_input("Repair details", key=f"rd_{m.machine_id}", label_visibility="collapsed",
                                            placeholder="Repair details")
                    if c2.button("Save details", key=f"sd_{m.machine_id}"):
                        record.update_repair_details(details)
                        save_and_rerun()
                    if c3.button("Complete repair", key=f"cr_{m.machine_id}"):
                        record.complete()
                        save_and_rerun(("success", f"{m.machine_id} repair completed."))
            except DomainError as e:
                st.error(str(e))
    upcoming = sorted((t for t in world.all(TimeSlot) if t.date >= today_local()), key=lambda t: t.starts_at())[:3]
    st.caption("Next slots: " + " · ".join(f"{t.label()} {t.available_capacity}/{t.capacity_limit} free"
                                           for t in upcoming))


def staff_inventory(s: StaffMember) -> None:
    show_flash()
    for item in world.all(InventoryItem):
        low = item.check_reorder_level()
        with st.container(border=True):
            st.markdown(f"**{item.name}** · {item.quantity_on_hand} on hand · reorder at {item.reorder_level}"
                        + (" · ⚠️ **low stock**" if low else ""))
            c1, c2, c3 = st.columns([2, 1, 1])
            kind = c1.selectbox("Movement", list(StockMovementType), key=f"k_{item.inventory_item_id}",
                                format_func=lambda k: k.value, label_visibility="collapsed")
            qty = c2.number_input("Qty", min_value=0.0, step=1.0, key=f"q_{item.inventory_item_id}",
                                  label_visibility="collapsed")
            if c3.button("Record", key=f"r_{item.inventory_item_id}"):
                try:
                    operations.record_stock(item, kind, str(qty), s)
                    save_and_rerun(("warning", f"Low stock alert sent for {item.name}.") if item.alert_open and
                                   item.check_reorder_level() else ("success", "Movement recorded."))
                except DomainError as e:
                    st.error(str(e))


# =================================================================
# Page
# =================================================================
with st.expander("👋 New here? How to try Prototype 2", expanded="seen_guide" not in st.session_state):
    st.session_state["seen_guide"] = True
    st.markdown("""
**ZippyWash** is a Montréal laundry pickup-and-delivery service. This is Prototype 2 of its order system,
built by BTM 495 Team 5 (Concordia, Fall 2026) from our Milestone 5 class design and Milestone 6 screens.

1. **Book (UC01):** as **Léa**, open *Book Pickup* → details → time slots → review → payment.
   *Mastercard 0002* is declined on purpose and *Debit 7777* times out; *Visa 4242* works.
2. **Reward (UC07):** on *Review estimate*, open *Apply promotion or reward* → *Use a loyalty reward* →
   **Free Small Bag**. Léa has 420 points: 250 become **Reserved**, the total drops from \\$34.47 to \\$5.74
   (Small Wash & Fold). Pay with the declined card to see points **Restored**, or Visa to see them **Redeemed**.
3. **Status (UC02):** *My Orders* → *View Status*. Switch to **Nina** to see the empty state.
4. **Staff:** sign in as staff to record status changes, build routes, report machine faults and record stock.

No real payments happen. Nothing here is real customer data.
""")

if role == "Customer":
    st.title(f"Hi, {customer.name.split()[0]}")
    st.session_state.setdefault("nav", NAV[0])
    if "nav_next" in st.session_state:            # a button asked to switch pages
        st.session_state["nav"] = st.session_state.pop("nav_next")
    page = st.radio("Menu", NAV, key="nav", horizontal=True, label_visibility="collapsed")
    {"Book Pickup": book_pickup, "My Orders": my_orders, "Loyalty / Rewards": loyalty_page,
     "Profile": profile_page}[page](customer)
else:
    st.title("Operations")
    t1, t2, t3, t4 = st.tabs(["Order board", "Routes", "Machines", "Inventory"])
    with t1:
        staff_orders(staff)
    with t2:
        staff_routes(staff)
    with t3:
        staff_machines(staff)
    with t4:
        staff_inventory(staff)
