"""ZippyWash Prototype 2 — Streamlit user interface.

Run:  streamlit run app.py

The UI only collects input, keeps track of which screen is shown, and displays results.
Every rule runs in the domain classes, called through the services. Screen IDs (WF01 ...)
and the visual design follow the Milestone 6 HCI design: UC01-SC1 booking, UC02-SC1 order
status, UC07-SC2 rewards at checkout.
"""
from __future__ import annotations

from datetime import timedelta

import streamlit as st

from ui_kit import (apply_style, banner, brand, card, e, heading, html, kv, note, page_title, pill, step_count, stepper,
                    user_badge)
from zippywash.common import (STATUS_SEQUENCE, BagSize, DomainError, LoyaltyAccountStatus, LoyaltyTransactionType,
                              MaintenanceStatus, OrderStatus, PickupRequestType, RouteStatus,
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

st.set_page_config(page_title="ZippyWash", page_icon="🧺", layout="wide")
apply_style()


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
    """Plain dollars for HTML, widget labels and metrics."""
    return f"${v:,.2f}"


def md_money(v) -> str:
    """Dollars inside Streamlit markdown ("\\$" stops two amounts being read as a formula)."""
    return money(v).replace("$", "\\$")


def when(dt) -> str:
    return f"{dt:%a, %b %d · %-I:%M %p}"


def slot_text(slot: TimeSlot) -> str:
    return f"{slot.date:%a, %b %d} · {slot.start_time:%-I:%M %p}"


def choose(widget, label: str, objs: list, fmt, **kw):
    """Select a domain object by its ID. Every page run loads fresh objects, so widgets hold IDs."""
    by_id = {getattr(o, o._pk): o for o in objs}
    picked = widget(label, list(by_id), format_func=lambda k: fmt(by_id[k]), **kw)
    return by_id.get(picked) if picked is not None else None


def price_rows(order: Order) -> tuple[list[tuple[str, str]], tuple[str, str]]:
    p = order.price_breakdown()
    rows = [(f"{order.service_type.name} · {order.bag_size.value}", money(p.subtotal))]
    if order.applied_promotion is not None:
        rows.append((f"Promo {order.applied_promotion.code}", "−" + money(p.discount)))
    if order.applied_reward is not None:
        rows.append((f"{order.applied_reward.name} reward", "−" + money(p.discount)))
    rows += [("Pickup & delivery fee", money(p.delivery_fee)), ("GST (5%)", money(p.gst)),
             ("QST (9.975%)", money(p.qst))]
    return rows, ("Estimated total", money(p.total))


def progress(order: Order) -> None:
    """Read-only lifecycle indicator (no controls)."""
    if order.status == OrderStatus.CANCELLED:
        html(pill("Cancelled", "danger"))
        return
    flow = [s.value for s in STATUS_SEQUENCE[1:]]
    stepper(flow.index(order.status.value) + 1, flow, all_done=order.status == OrderStatus.DELIVERED,
            css="zw-prog")


STATUS_KIND = {OrderStatus.SCHEDULED: "info", OrderStatus.DELIVERED: "success", OrderStatus.CANCELLED: "danger"}


def status_pill(status: OrderStatus) -> str:
    return pill(status.value, STATUS_KIND.get(status, "amber"))


# =================================================================
# Sidebar: demo controls (who is using the system)
# =================================================================
st.sidebar.markdown("### Demo controls")
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
with st.sidebar.expander("How to try it"):
    st.markdown("""
1. **Book (UC01):** as Léa, *Book Pickup* → time slots → review → payment.
   *Mastercard 0002* is declined, *Debit 7777* times out, *Visa 4242* works.
2. **Reward (UC07):** on the review screen, *Apply promotion or reward* → *Use a loyalty reward* →
   **Free Small Bag**. 420 points → 250 reserved; total \\$34.47 → \\$5.74 (Small Wash & Fold).
3. **Status (UC02):** *My Orders* → *View Status*. Nina has no orders yet.
4. **Staff:** status updates, routes, machine faults and stock.
""")
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
    if step != "WF01" and (order is None or order.status == OrderStatus.CANCELLED):
        reset_checkout(c)
        step, order = "WF01", None
    {"WF01": wf01_details, "WF02": wf02_slots, "WF03": wf03_review, "WF04": wf04_payment,
     "WF04E": wf04e_not_authorized, "WF05": wf05_confirmation, "R01": uc07_wf01_choose,
     "R02": uc07_wf02_reserved, "R03": uc07_wf03_redeemed, "R03E": uc07_wf03e_restored}[step](c, order)


def footer_buttons(back_label: str | None, step_text: str, next_label: str | None, key: str):
    """Back on the left, 'Step n of 5' in the middle, the one primary action on the right."""
    b1, b2, b3 = st.columns([1, 2, 1.4])
    back = b1.button(back_label, key=f"{key}_back") if back_label else False
    with b2:
        step_count(step_text)
    nxt = b3.button(next_label, type="primary", key=f"{key}_next", use_container_width=True) if next_label else False
    return back, nxt


# ---------------- WF01 Booking Details ----------------
def wf01_details(c: Customer, order: Order | None) -> None:
    page_title("Book Pickup & Delivery", "Choose your laundry service and confirm where we should pick up and deliver.")
    stepper(1)
    if not c.is_active():
        banner("danger", "!", "This account is deactivated",
               "It can't place new orders. Your order history is still in My Orders.")
        return
    serviceable = [a for a in c.addresses if a.validate()]
    if not serviceable:
        banner("info", "i", "Add an address first", "Add an address inside our service area under Profile.")
        return
    services = [s for s in world.all(ServiceType) if s.active]
    with card():
        heading("Booking details", "All fields marked * are required.")
        with st.form("wf01", border=False):
            c1, c2 = st.columns([1.6, 1])
            service = choose(c1.selectbox, "Service type *", services,
                             fmt=lambda s: f"{s.name} ({money(s.base_rate)} per small bag)")
            bag = c2.radio("Bag size *", list(BagSize), format_func=lambda b: b.value, horizontal=True)
            c1, c2 = st.columns(2)
            pickup = choose(c1.selectbox, "Pickup address *", serviceable, fmt=lambda a: a.label())
            delivery = choose(c2.selectbox, "Delivery address *", serviceable, fmt=lambda a: a.label())
            st.caption("Only saved addresses inside a ZippyWash service area can be used.")
            req = st.radio("Pickup request *", list(PickupRequestType), horizontal=True,
                           format_func=lambda t: {"Scheduled": "Scheduled pickup",
                                                  "Live": "Live pickup (same-day route)"}[t.value])
            b1, b2 = st.columns([3, 1.4])
            with b1:
                step_count("Step 1 of 5")
            if b2.form_submit_button("Continue to Time Slots →", type="primary", use_container_width=True):
                try:
                    new = booking.start_booking(c, pickup, delivery, service, bag, req)
                    go(c, "WF02", order=new.order_id)
                    save_and_rerun()
                except DomainError as err:
                    st.error(str(err))


# ---------------- WF02 Select Time Slots ----------------
def _time_picker(col, title: str, slots: list[TimeSlot], key: str) -> TimeSlot | None:
    with col:
        html(f'<div class="zw-section">{e(title)}</div>')
        dates = sorted({s.date for s in slots})
        if not dates:
            st.caption("No available times.")
            return None
        day = st.selectbox("Date", dates, format_func=lambda d: f"{d:%A, %B %d}", key=f"{key}_date")
        options = [s for s in slots if s.date == day]
        with st.container(key=f"chips_{key}"):
            return choose(st.radio, "Available time", options, key=f"{key}_time", horizontal=True,
                          fmt=lambda s: f"{s.start_time:%-I:%M %p} · {s.available_capacity} left")


def wf02_slots(c: Customer, order: Order) -> None:
    page_title("Book Pickup & Delivery", "Choose available times for pickup and delivery.")
    stepper(2)
    slots = booking.open_slots(now_local())
    with card():
        heading("Select pickup and delivery times", "Only currently available times are shown.")
        if not slots:
            st.warning("No time slots are available right now. Try again later.")
            return
        c1, c2 = st.columns(2)
        p_slot = _time_picker(c1, "Pickup time *", slots, "wf02_p")
        d_slot = _time_picker(c2, "Delivery time *", [s for s in slots if p_slot and s.date > p_slot.date],
                              "wf02_d") if p_slot else None
        if p_slot and d_slot:
            note(f"Selected: Pickup {slot_text(p_slot)}  ·  Delivery {slot_text(d_slot)}. "
                 "Times are reserved only after your payment is authorized.")
        back, nxt = footer_buttons("← Back", "Step 2 of 5", "Continue to Review →", "wf02")
    if back:
        booking.cancel_checkout(order)
        reset_checkout(c)
        save_and_rerun()
    if nxt:
        try:
            booking.choose_slots(order, p_slot, d_slot)
            go(c, "WF03")
            save_and_rerun()
        except DomainError as err:
            st.error(str(err))


# ---------------- WF03 Review Estimate ----------------
def booking_summary(order: Order) -> None:
    heading("Booking summary")
    html('<div class="zw-section">Service details</div>')
    kv([("Service", order.service_type.name), ("Bag size", order.bag_size.value)])
    html('<div class="zw-section">Addresses</div>')
    kv([("Pickup", order.pickup_address.label()), ("Delivery", order.delivery_address.label())])
    html('<div class="zw-section">Schedule</div>')
    kv([("Pickup", slot_text(order.pickup_time_slot)), ("Delivery", slot_text(order.delivery_time_slot))])


def wf03_review(c: Customer, order: Order) -> None:
    page_title("Book Pickup & Delivery", "Review your booking details and estimated price before payment.")
    stepper(3)
    show_flash()
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            booking_summary(order)
            note("You can go back and edit these selections before payment.")
    with right:
        with card():
            heading("Estimated price", "Calculated before payment.")
            rows, total = price_rows(order)
            kv(rows, total)
            if order.applied_reward is not None:
                html(f'{pill("Reserved", "purple")} <span class="zw-muted">Points are redeemed only after payment '
                     f'is authorized.</span>')
            with st.expander("🏷️ Apply promotion or reward"):
                if order.applied_reward is not None:
                    st.write(f"**{order.applied_reward.name}** is applied. An order can't also use a promo code.")
                elif order.applied_promotion is not None:
                    st.write(f"Promo **{order.applied_promotion.code}** is applied. An order can't also use a reward.")
                    if st.button("Remove promo code"):
                        booking.remove_promo_code(order)
                        save_and_rerun()
                else:
                    code = st.text_input("Promo code", placeholder="WELCOME10")
                    p1, p2 = st.columns(2)
                    if p1.button("Apply code", use_container_width=True):
                        try:
                            booking.apply_promo_code(order, code)
                            save_and_rerun(("success", "Promo code applied."))
                        except DomainError as err:
                            st.error(str(err))
                    if p2.button("Use a loyalty reward", use_container_width=True):
                        go(c, "R01")
                        st.rerun()
            st.caption("Only one promotion or reward may be applied.")
            if st.button("Proceed to Payment →", type="primary", use_container_width=True):
                go(c, "WF04")
                st.rerun()
    back, _ = footer_buttons("← Back", "Step 3 of 5", None, "wf03")
    if back:
        go(c, "WF02")
        st.rerun()


# ---------------- WF04 Payment / WF04E Payment Not Authorized ----------------
def _method_picker(c: Customer, failed_id: str | None = None):
    methods = [m for m in c.payment_methods if m.active]
    with st.container(key="cards_pm"):
        return choose(st.radio, "Saved payment methods", methods, key="wf04_pm", label_visibility="collapsed",
                      fmt=lambda m: m.label.replace("$", "\\$") + ("  ·  :red[**Failed**]"
                                                                     if m.payment_method_id == failed_id else ""))


def _pay(c: Customer, order: Order, method) -> None:
    try:
        had_reward = order.applied_reward is not None
        outcome = booking.pay(order, method)
        if outcome.authorized:
            go(c, "R03" if outcome.redeemed else "WF05")
        elif had_reward and outcome.restored is not None:
            go(c, "R03E", reason=outcome.message, cause="payment")
        else:
            go(c, "WF04E", reason=outcome.message, failed=method.payment_method_id)
        save_and_rerun()
    except DomainError as err:
        st.error(str(err))


def order_total_card(order: Order) -> None:
    p = order.price_breakdown()
    heading("Order total")
    rows = [(f"{order.service_type.name} · {order.bag_size.value}", money(p.subtotal))]
    if p.discount:
        rows.append(("Discount", "−" + money(p.discount)))
    rows += [("Pickup & delivery fee", money(p.delivery_fee)), ("Taxes", money(p.gst + p.qst))]
    kv(rows, ("Final amount", money(p.total)))
    note(f"Pickup {slot_text(order.pickup_time_slot)} · Delivery {slot_text(order.delivery_time_slot)} · "
         f"{order.pickup_address.street}")


def wf04_payment(c: Customer, order: Order) -> None:
    page_title("Book Pickup & Delivery", "Select a saved payment method and authorize the final amount.")
    stepper(4)
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Payment method", "Choose one of your saved payment methods.")
            method = _method_picker(c)
            note("🔒 Secure online authorization. Your booking is confirmed only after payment is authorized. "
                 "Only the payment provider's secure reference is stored.")
            if order.applied_reward is not None:
                html(f'{pill("Reserved", "purple")} <span class="zw-muted">{e(order.applied_reward.name)}: '
                     f'points are redeemed only if this payment is authorized.</span>')
    with right:
        with card():
            order_total_card(order)
            if st.button(f"Pay {money(order.estimated_total)} & Book →", type="primary", use_container_width=True,
                         disabled=method is None):
                _pay(c, order, method)
            st.caption("One payment attempt will be submitted.")
    back, _ = footer_buttons("← Back to Review", "Step 4 of 5", None, "wf04")
    if back:
        go(c, "WF03")
        st.rerun()


def wf04e_not_authorized(c: Customer, order: Order) -> None:
    state = checkout(c)
    page_title("Book Pickup & Delivery", "Resolve the payment issue to finish your booking.")
    stepper(4)
    banner("danger", "!", "Payment was not authorized",
           f"{state.get('reason', '')} Your booking was not confirmed and the selected time slots were not "
           "reserved. Choose another payment method or retry.")
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Choose a payment method", "The previous attempt was unsuccessful.")
            method = _method_picker(c, state.get("failed"))
            if st.button(f"Retry Payment · {money(order.estimated_total)} →", type="primary",
                         use_container_width=True, disabled=method is None):
                _pay(c, order, method)
    with right:
        with card():
            heading("Booking status")
            html(pill("Not confirmed", "danger"))
            kv([("Order total", money(order.estimated_total)), ("Time slots", "Not reserved"),
                ("Payment", "Not authorized")])
            html('<div class="zw-section">What you can do</div><div class="zw-muted">• Select another saved payment '
                 'method<br>• Retry payment<br>• Return to review your booking</div>')
    back, _ = footer_buttons("← Back to Review", "Step 4 of 5", None, "wf04e")
    if back:
        go(c, "WF03")
        st.rerun()


# ---------------- WF05 Booking Confirmation ----------------
def wf05_confirmation(c: Customer, order: Order) -> None:
    payment = order.authorized_payment()
    page_title("Book Pickup & Delivery", "Your booking has been scheduled and confirmed.")
    stepper(5, all_done=True)
    banner("success", "&#10003;", "Booking confirmed",
           "Payment was authorized, both time slots were reserved, and your order is now scheduled.",
           pill=order.status.value)
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Booking details", right=f'<span class="zw-small">Order ID</span> <b>{e(order.order_id)}</b>')
            kv([("Service", f"{order.service_type.name} · {order.bag_size.value} bag"),
                ("Pickup — reserved", slot_text(order.pickup_time_slot)),
                ("Delivery — reserved", slot_text(order.delivery_time_slot)),
                ("Address", order.pickup_address.label()),
                ("Payment", f"Authorized · {payment.payment_method.label}"),
                ("Receipt", payment.receipt_number)],
               ("Total paid", money(order.final_total)))
    with right:
        with card():
            heading("What happens next")
            html(f'<div class="zw-muted"><b>1 · Confirmation sent</b><br>A notification was sent to '
                 f'{e(c.contact_details)}.<br><br><b>2 · Prepare for pickup</b><br>Have your laundry ready during the '
                 f'pickup window.<br><br><b>3 · Track your order</b><br>View status updates from My Orders.</div>')
            if st.button("View My Order →", type="primary", use_container_width=True):
                st.session_state["nav_next"] = "My Orders"
                st.session_state[f"view_{c.customer_id}"] = order.order_id
                reset_checkout(c)
                st.rerun()
            if st.button("Book another pickup", use_container_width=True):
                reset_checkout(c)
                st.rerun()
    step_count("Step 5 of 5 · Booking complete")


# ---------------- UC07-SC2 ----------------
def uc07_wf01_choose(c: Customer, order: Order) -> None:
    stepper(3)
    page_title("Choose a Reward", "Apply one eligible loyalty reward to this checkout.")
    account = c.loyalty_account
    active = account is not None and account.status == LoyaltyAccountStatus.ACTIVE
    banner("purple", "+", f"{account.available_points() if active else 0} points",
           "Available loyalty balance" if active else "Join the loyalty program under Loyalty / Rewards to use rewards.",
           pill="No promotion applied" if order.applied_promotion is None else "Promotion applied")
    options = booking.reward_options(order)
    eligible = [r for r, why in options if why is None]
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Eligible Rewards", "Rewards shown here are active and available for this order.",
                    right=f'<span class="zw-muted">{len(eligible)} available</span>')
            with st.container(key="cards_reward"):
                choice = choose(st.radio, "Reward to apply", eligible, index=None, label_visibility="collapsed",
                                fmt=lambda r: f"**{r.name}**  ·  {r.points_required} points  ·  "
                                              f"{money(r.discount_amount)} off".replace("$", "\\$")
                                ) if eligible else None
            for reward, why in options:
                if why is not None:
                    st.caption(f"🔒 {reward.name} · {reward.points_required} points — {why}")
            note("Applying temporarily reserves the points. They are redeemed only after payment succeeds, "
                 "and restored if payment fails or checkout is cancelled.")
    with right:
        with card():
            heading("Order impact preview")
            rows = [("Current estimated total", money(order.estimated_total))]
            if choice is not None:
                rows.append(("Selected reward discount", "−" + money(min(choice.discount_amount, order.subtotal))))
            kv(rows)
            if choice is not None and active:
                note(f"If applied: {choice.points_required} will be reserved · "
                     f"{account.available_points() - choice.points_required} available")
            if st.button("Apply Reward →", type="primary", use_container_width=True, disabled=choice is None):
                try:
                    booking.reserve_reward(order, choice)
                    go(c, "R02")
                    save_and_rerun()
                except DomainError as err:
                    st.error(str(err))
            st.caption("Only one promotion or reward may be applied.")
    back, _ = footer_buttons("← Back to Review", "Step 3 of 5", None, "r01")
    if back:
        go(c, "WF03")
        st.rerun()


def points_card(title: str, rows: list[tuple[str, str]], total: tuple[str, str]) -> None:
    heading(title)
    kv(rows, total)


def uc07_wf02_reserved(c: Customer, order: Order) -> None:
    account = c.loyalty_account
    stepper(3)
    page_title("Reward Reserved", "Review the updated checkout total before continuing to payment.")
    banner("purple", "&#10003;", f"{order.applied_reward.name} is reserved for this checkout",
           f"The {order.applied_reward.points_required} points are not permanently redeemed until payment is "
           "authorized.", pill="Reserved")
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Updated Order Review", right='<span class="zw-muted">No promotion applied</span>')
            rows, total = price_rows(order)
            kv(rows, ("Updated estimated total", total[1]))
            note(f"Scheduled · Pickup {slot_text(order.pickup_time_slot)} · Delivery "
                 f"{slot_text(order.delivery_time_slot)} · {order.pickup_address.street}")
    with right:
        with card():
            points_card("Loyalty Point Status",
                        [("Total balance", f"{account.point_balance} points"),
                         ("Reserved", f"{account.reserved_points()} points")],
                        ("Available now", f"{account.available_points()} points"))
            st.caption("Reserved points can't be reused.")
            if st.button("Continue to Payment →", type="primary", use_container_width=True):
                go(c, "WF04")
                st.rerun()
            if st.button("Cancel Checkout", use_container_width=True):
                booking.release_reward(order)
                go(c, "R03E", cause="cancel", reason="Checkout was cancelled before payment.")
                save_and_rerun()
            st.caption(f"Cancel Checkout releases the reservation and restores all "
                       f"{order.applied_reward.points_required} points.")


def uc07_wf03_redeemed(c: Customer, order: Order) -> None:
    account = c.loyalty_account
    redemption = next(t for t in reversed(account.transactions)
                      if t.type == LoyaltyTransactionType.REDEMPTION and t.order is order)
    payment = order.authorized_payment()
    stepper(4)
    page_title("Reward Redeemed", "Payment authorization converted the temporary reservation into a completed "
                                  "redemption.")
    banner("success", "&#10003;", "Payment authorized and reward redeemed",
           f"{redemption.reward.name} used {redemption.points} points and applied a "
           f"{money(redemption.reward.discount_amount)} discount to this order.", pill="Redeemed")
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Redemption Details", right=f'<span class="zw-muted">Order {e(order.order_id)}</span>')
            html(f'<b>{e(redemption.reward.name)}</b> {pill("Complete", "success")}<br><span class="zw-muted">'
                 f'{redemption.points} points redeemed · {e(money(redemption.reward.discount_amount))} discount</span>')
            kv([("Payment status", f"Authorized · {payment.payment_method.label}")],
               ("Total paid", money(order.final_total)))
            note("The temporary reservation has been consumed. No points remain reserved for this checkout.")
    with right:
        with card():
            points_card("Updated Point Balance",
                        [("Balance before", f"{account.point_balance + redemption.points} points"),
                         ("Redeemed", f"−{redemption.points} points"),
                         ("Reserved now", f"{account.reserved_points()} points")],
                        ("Current balance", f"{account.point_balance} points"))
            if st.button("Continue to Confirmation →", type="primary", use_container_width=True):
                go(c, "WF05")
                st.rerun()
            st.caption("Continue to the shared booking confirmation.")


def uc07_wf03e_restored(c: Customer, order: Order) -> None:
    state = checkout(c)
    account = c.loyalty_account
    restored = next((t for t in reversed(account.transactions)
                     if t.type == LoyaltyTransactionType.RESTORATION and t.order is order), None)
    points = restored.points if restored else 0
    stepper(3)
    page_title("Points Restored", "The checkout did not complete, so the temporary reward reservation was released.")
    if state.get("cause") == "payment":
        banner("danger", "!", "Payment was not authorized",
               f"{state.get('reason', '')} Your booking was not confirmed and no time slots were reserved.")
    banner("success", "←", f"All {points} reserved points are available again",
           "No reward was redeemed and your loyalty balance is unchanged.", pill="Restored")
    left, right = st.columns([1.5, 1])
    with left:
        with card():
            heading("Restoration Details", right=f'<span class="zw-muted">{e(restored.reward.name if restored else "")}</span>')
            note("Checkout outcome: " + ("payment was not authorized." if state.get("cause") == "payment"
                                         else "checkout was cancelled before payment."))
            kv([("Reservation result", "Released and restored"), ("Reward result", "Not redeemed")],
               ("Checkout price", money(order.estimated_total)))
            st.caption("The reward discount was removed; the original estimated total is restored.")
    with right:
        with card():
            points_card("Loyalty Point Status",
                        [("Available while reserved", f"{account.available_points() - points} points"),
                         ("Restored", f"+{points} points"),
                         ("Reserved now", f"{account.reserved_points()} points")],
                        ("Available balance", f"{account.available_points()} points"))
            if st.button("Return to Checkout →", type="primary", use_container_width=True):
                go(c, "WF03")
                st.rerun()
            st.caption("Review the order or begin another payment attempt.")


# =================================================================
# UC02-SC1: My Orders (read-only)
# =================================================================
def my_orders(c: Customer) -> None:
    key = f"view_{c.customer_id}"
    orders = tracking.my_orders(c)
    if not orders:                                  # WF01E No Orders Yet
        page_title("My Orders", "View the latest recorded status of your orders.")
        with card():
            html('<div style="text-align:center;padding:18px 0 6px"><div style="font-size:2.4rem">🧺</div>'
                 '<div class="zw-h" style="font-size:1.3rem">No orders yet</div><div class="zw-muted">Once you book '
                 'a pickup and delivery, its latest status will appear here.</div></div>')
            _, mid, _ = st.columns([1, 1.2, 1])
            if mid.button("Book Pickup & Delivery →", type="primary", use_container_width=True):
                st.session_state["nav_next"] = "Book Pickup"
                st.rerun()
            st.caption("Only orders belonging to your signed-in account will be shown.")
        return
    selected = st.session_state.get(key)
    if selected:                                    # WF02 Current Order Status
        try:
            order = tracking.order_for(c, selected)
        except DomainError as err:
            st.error(str(err))
            st.session_state.pop(key)
            return
        if st.button("← Back to My Orders"):
            st.session_state.pop(key)
            st.rerun()
        latest = order.get_current_status()
        page_title("Current Order Status", f"Latest recorded information for Order {order.order_id}.")
        html(f'<div style="text-align:right;margin-top:-56px;margin-bottom:24px">{pill("Read-only view", "grey")}</div>')
        banner("amber" if latest.status not in STATUS_KIND else STATUS_KIND[latest.status], "◷",
               latest.status.value, f"Latest update recorded {when(latest.changed_at)}. "
                                    f"Latest note: {latest.notes or 'No note available'}")
        with card():
            heading("Order Progress", right=f'<span class="zw-muted">Current recorded stage: '
                                            f'{e(latest.status.value)}</span>')
            progress(order)
            st.caption("Future stages remain incomplete until a new status is recorded.")
        with card():
            heading("Order Reference")
            kv([("Order ID", order.order_id), ("Service", f"{order.service_type.name} · {order.bag_size.value} bag"),
                ("Pickup", slot_text(order.pickup_time_slot)), ("Delivery", slot_text(order.delivery_time_slot))])
        st.caption("ⓘ Viewing this page does not change the order or its recorded status information.")
        return
    page_title("My Orders", "Select an order to view its latest recorded status.")   # WF01 My Orders
    for order in orders:
        latest = order.get_current_status()
        with card():
            heading(order.order_id, right=status_pill(latest.status))
            kv([("Service", f"{order.service_type.name} · {order.bag_size.value} bag"),
                ("Pickup", slot_text(order.pickup_time_slot)), ("Delivery", slot_text(order.delivery_time_slot))])
            progress(order)
            n1, n2 = st.columns([3, 1])
            with n1:
                note(f"Latest note: {latest.notes or 'No note available'} · Updated {when(latest.changed_at)}")
            if n2.button("View Status →", key=f"vs_{order.order_id}", type="primary", use_container_width=True):
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
    page_title("Loyalty / Rewards", "Earn 1 point for every dollar paid once your order is delivered.")
    show_flash()
    account = c.loyalty_account
    if account is None or account.status != LoyaltyAccountStatus.ACTIVE:
        with card():
            heading("Join ZippyWash Rewards", "Use points for discounts at checkout.")
            if st.button("Join the loyalty program" if account is None else "Reactivate membership", type="primary",
                         disabled=not c.is_active()):
                try:
                    profiles.join_loyalty(c)
                    save_and_rerun(("success", "Welcome to ZippyWash Rewards."))
                except DomainError as err:
                    st.error(str(err))
        return
    s = account.view_loyalty_summary()
    m1, m2, m3 = st.columns(3)
    for col, label, value in ((m1, "Point balance", s.point_balance), (m2, "Reserved", s.reserved_points),
                              (m3, "Available", s.available_points)):
        with col:
            with card():
                st.metric(label, value)
    left, right = st.columns([1, 1.4])
    with left:
        with card():
            heading("Rewards", "Use a reward at checkout from the review screen.")
            for r in sorted(world.all(Reward), key=lambda r: r.points_required):
                if r.is_available():
                    kv([(r.name, f"{r.points_required} pts · {money(r.discount_amount)} off")])
    with right:
        with card():
            heading("Recent activity")
            st.dataframe([{"When": when(t.created_at), "Activity": STATE_LABEL[t.type], "Points": t.points,
                           "Details": t.reason or ""} for t in s.recent_transactions],
                         hide_index=True, use_container_width=True)


def profile_page(c: Customer) -> None:
    page_title("Profile", "Your details, saved addresses and payment methods.")
    show_flash()
    left, right = st.columns(2)
    with left:
        with card():
            heading("Personal details")
            with st.form("profile", border=False):
                name = st.text_input("Name", c.name)
                contact = st.text_input("Email or phone", c.contact_details)
                prefs = st.text_input("Service preferences (optional)", c.service_preferences or "",
                                      placeholder="e.g. Unscented detergent")
                if st.form_submit_button("Save profile", type="primary"):
                    try:
                        profiles.update_profile(c, name, contact, prefs)
                        save_and_rerun(("success", "Profile saved."))
                    except DomainError as err:
                        st.error(str(err))
        with card():
            heading("Saved payment methods", "Only the payment provider's token is stored, never a card number.")
            for m in c.payment_methods:
                st.write("💳 " + m.label)
    with right:
        with card():
            heading("Saved addresses")
            for a in c.addresses:
                st.write(("✅ " if a.serviceable else "⚠️ ") + a.label() +
                         ("" if a.serviceable else " — outside our service area") +
                         (f"  \n_Access: {a.access_instructions}_" if a.access_instructions else ""))
            with st.form("add_address", clear_on_submit=True, border=False):
                c1, c2 = st.columns([3, 1.3])
                street = c1.text_input("Street address")
                postal = c2.text_input("Postal code", placeholder="H3H 1K6")
                access = st.text_input("Access instructions (optional)",
                                       placeholder="e.g. Buzz 08, leave with concierge")
                if st.form_submit_button("Add address"):
                    try:
                        a = profiles.add_address(c, street, postal, access)
                        save_and_rerun(("success", "Address saved.") if a.serviceable
                                       else ("warning", "Address saved, but we don't serve that area yet."))
                    except DomainError as err:
                        st.error(str(err))
        with card():
            heading("Notifications")
            for n in sorted(c.notifications, key=lambda n: n.created_at, reverse=True)[:6]:
                st.caption(f"{n.created_at:%b %d, %-I:%M %p} · {n.message}")
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
        with card():
            st.markdown(f"**{order.order_id}** · {order.customer.name} · {order.service_type.name}, "
                        f"{order.bag_size.value} · pickup {order.pickup_time_slot.label()}"
                        + (" · **live pickup**" if order.pickup_request_type == PickupRequestType.LIVE else ""))
            progress(order)
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
        with card():
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
        with card():
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
        with card():
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
# Page: top bar (logo · navigation · signed-in user), then the selected screen
# =================================================================
top_l, top_m, top_r = st.columns([1.2, 3.4, 0.9], vertical_alignment="center")
with top_l:
    brand()
if role == "Customer":
    st.session_state.setdefault("nav", NAV[0])
    if "nav_next" in st.session_state:            # a button asked to switch pages
        st.session_state["nav"] = st.session_state.pop("nav_next")
    with top_m:
        with st.container(key="navbar"):
            page = st.radio("Menu", NAV, key="nav", horizontal=True, label_visibility="collapsed")
    with top_r:
        user_badge(customer.name)
    st.divider()
    {"Book Pickup": book_pickup, "My Orders": my_orders, "Loyalty / Rewards": loyalty_page,
     "Profile": profile_page}[page](customer)
else:
    with top_r:
        user_badge(staff.name)
    st.divider()
    page_title("Operations", "Staff tools: order status, routes, machines and inventory.")
    t1, t2, t3, t4 = st.tabs(["Order board", "Routes", "Machines", "Inventory"])
    with t1:
        staff_orders(staff)
    with t2:
        staff_routes(staff)
    with t3:
        staff_machines(staff)
    with t4:
        staff_inventory(staff)
