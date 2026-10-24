"""ZippyWash prototype — Streamlit user interface.

Run:  streamlit run app.py

The UI only collects input and displays results. All rules run in the domain
classes, called through the services (BookingService, OrderTrackingService,
CustomerProfileService).
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from zippywash.common import STATUS_SEQUENCE, DomainError, OrderStatus, PaymentStatus
from zippywash.database.db import connect, create_schema, is_empty
from zippywash.database.repository import Repository
from zippywash.database.seed import seed
from zippywash.services.booking_service import BookingService
from zippywash.services.customer_profile_service import CustomerProfileService
from zippywash.services.order_tracking_service import ROLE_FOR_STATUS, OrderTrackingService

st.set_page_config(page_title="ZippyWash", page_icon="🧺", layout="centered")

st.markdown("""
<style>
.zw-timeline{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 10px}
.zw-step{padding:3px 10px;border-radius:999px;font-size:.8rem;border:1px solid rgba(128,128,128,.35);opacity:.55}
.zw-step.done{opacity:1;background:rgba(47,125,79,.15);border-color:rgba(47,125,79,.6)}
.zw-step.now{opacity:1;background:rgba(15,124,147,.18);border-color:#0f7c93;font-weight:600}
.zw-step.cancel{opacity:1;background:rgba(180,84,26,.15);border-color:#b4541a;font-weight:600}
</style>""", unsafe_allow_html=True)


# ---------------- setup ----------------
@st.cache_resource
def get_repo() -> Repository:
    conn = connect()
    create_schema(conn)
    repo = Repository(conn)
    if is_empty(conn):
        seed(repo)
    return repo


repo = get_repo()
booking, tracking, profiles = BookingService(repo), OrderTrackingService(repo), CustomerProfileService(repo)


def money(v) -> str:
    return f"${v:,.2f}"


def timeline(order) -> None:
    html = []
    if order.status == OrderStatus.CANCELLED:
        html.append('<span class="zw-step cancel">Cancelled</span>')
    else:
        current = STATUS_SEQUENCE.index(order.status)
        for i, s in enumerate(STATUS_SEQUENCE):
            cls = "done" if i < current else "now" if i == current else ""
            html.append(f'<span class="zw-step {cls}">{s.value}</span>')
    st.markdown(f'<div class="zw-timeline">{"".join(html)}</div>', unsafe_allow_html=True)


def history_table(order) -> None:
    staff = {s.staff_member_id: s.name for s in repo.list_staff()}
    st.table([{"When": u.changed_at.replace("T", " "), "Status": u.status.value,
               "Recorded by": staff.get(u.recorded_by_staff_id, "System"), "Notes": u.notes or ""}
              for u in order.history])


# ---------------- sidebar: who is using the system ----------------
st.sidebar.title("🧺 ZippyWash")
st.sidebar.caption("Order & Operations prototype · BTM 495 Team 5")
role = st.sidebar.radio("Sign in as", ["Customer", "Staff"], key="role")

if role == "Customer":
    customers = repo.list_customers()
    customer = st.sidebar.selectbox("Customer account", customers, format_func=lambda c: c.name, key="cust")
else:
    staff_list = repo.list_staff()
    staff_member = st.sidebar.selectbox(
        "Staff member", staff_list, key="staff",
        format_func=lambda s: f"{s.name} · {', '.join(r.value for r in s.roles)}")

st.sidebar.divider()
st.sidebar.caption("Demo data only. Delete zippywash.db to reset.")


# =================================================================
# CUSTOMER INTERFACE
# =================================================================
def booking_tab(customer):
    st.subheader("Book a pickup")
    st.caption("UC-01 Book Pickup & Delivery · UC-05 Calculate Price & Pay Online")

    # A previous attempt was declined: let the customer retry on the same order.
    pending = st.session_state.get("pending_order")
    if pending and pending["customer"] == customer.customer_id:
        order = repo.get_order(pending["order_id"])
        if order and order.status == OrderStatus.DRAFT:
            st.warning(f"Order {order.order_id} isn't booked yet: {pending['message']}")
            methods = repo.list_payment_methods(customer.customer_id)
            pm = st.selectbox("Try another payment method", methods, format_func=lambda m: m.label, key="retry_pm")
            if st.button(f"Pay {money(order.estimated_total)} and confirm", type="primary"):
                try:
                    result = booking.retry_payment(order.order_id, pm.payment_method_id)
                    if result.success:
                        st.session_state.pop("pending_order")
                        st.session_state["just_booked"] = result.order.order_id
                    else:
                        st.session_state["pending_order"]["message"] = result.message
                    st.rerun()
                except DomainError as e:
                    st.error(str(e))
            if st.button("Discard this order"):
                st.session_state.pop("pending_order")
                st.rerun()
            return

    if st.session_state.get("just_booked"):
        o = repo.get_order(st.session_state["just_booked"])
        pay = repo.list_payments(o.order_id)[-1]
        st.success(f"Booked. Order **{o.order_id}** is Scheduled. Receipt **{pay.receipt_number}**, "
                   f"paid {money(pay.amount)}. Track it under *My orders*.")
        if st.button("Book another pickup"):
            st.session_state.pop("just_booked")
            st.rerun()
        return

    services = repo.list_service_types()
    addresses = repo.list_addresses(customer.customer_id)
    slots = [s for s in repo.list_open_slots(date.today()) if s.check_capacity()]
    methods = repo.list_payment_methods(customer.customer_id)

    st.markdown("**1 · Service and bag size**")
    c1, c2 = st.columns(2)
    service = c1.selectbox("Service", services, key="svc",
                           format_func=lambda s: f"{s.name} ({money(s.base_rate)} / small bag)")
    bag = c2.radio("Bag size", ["Small", "Medium", "Large"], horizontal=True, key="bag")

    st.markdown("**2 · Addresses**")
    if not addresses:
        st.info("Add an address under *Profile* first.")
        return
    fmt = lambda a: a.label() + ("" if a.serviceable else "  ⚠ outside service area")
    c1, c2 = st.columns(2)
    pickup = c1.selectbox("Pickup address", addresses, format_func=fmt, key="pa")
    delivery = c2.selectbox("Delivery address", addresses, format_func=fmt, key="da")

    st.markdown("**3 · Time slots**")
    c1, c2 = st.columns(2)
    slot_fmt = lambda s: f"{s.label()}  ({s.available_capacity} left)"
    p_slot = c1.selectbox("Pickup time", slots, format_func=slot_fmt, key="ps")
    d_choices = [s for s in slots if p_slot and s.date > p_slot.date]
    d_slot = c2.selectbox("Delivery time", d_choices, format_func=slot_fmt, key="ds",
                          help="Delivery is at least one day after pickup.")

    st.markdown("**4 · Price**")
    promo = st.text_input("Promo code (optional)", key="promo", placeholder="WELCOME10").strip()
    try:
        price = booking.quote(customer.customer_id, service.service_type_id, bag, promo or None)
    except DomainError as e:
        st.error(str(e))
        return
    rows = [("Service", money(price.service_price))]
    if price.discount:
        rows.append((f"Promo {promo.upper()}", "−" + money(price.discount)))
    rows += [("Delivery fee", money(price.delivery_fee)), ("GST 5%", money(price.gst)),
             ("QST 9.975%", money(price.qst)), ("**Total**", f"**{money(price.total)}**")]
    st.markdown("| Item | Amount |\n|---|---:|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows))

    st.markdown("**5 · Pay and confirm**")
    pm = st.selectbox("Payment method", methods, format_func=lambda m: m.label, key="pm")
    st.caption("Payment is authorized online before the order is released. The driver never collects payment.")

    if st.button(f"Pay {money(price.total)} and book", type="primary", disabled=d_slot is None):
        try:
            result = booking.book(customer_id=customer.customer_id, service_type_id=service.service_type_id,
                                  bag_size=bag, pickup_address_id=pickup.address_id,
                                  delivery_address_id=delivery.address_id, pickup_slot_id=p_slot.time_slot_id,
                                  delivery_slot_id=d_slot.time_slot_id, payment_method_id=pm.payment_method_id,
                                  promo_code=promo or None)
        except DomainError as e:
            st.error(str(e))
            return
        if result.success:
            st.session_state["just_booked"] = result.order.order_id
        else:
            st.session_state["pending_order"] = {"order_id": result.order.order_id,
                                                 "customer": customer.customer_id, "message": result.message}
        st.rerun()


def orders_tab(customer):
    st.subheader("My orders")
    st.caption("UC-02 Track Order Status · UC-06 Order History")
    history = profiles.view_order_history(customer.customer_id)
    if not history:
        st.info("No orders yet. Book your first pickup in the *Book a pickup* tab.")
        return
    services = {s.service_type_id: s.name for s in repo.list_service_types(active_only=False)}
    for order, payments in history:
        p_slot = repo.get_slot(order.pickup_time_slot_id)
        title = f"{order.order_id} · {services[order.service_type_id]}, {order.bag_size.value} · {order.status.value}"
        with st.expander(title, expanded=order.status not in (OrderStatus.DELIVERED, OrderStatus.CANCELLED)):
            timeline(order)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total", money(order.estimated_total))
            c2.metric("Pickup", p_slot.label() if p_slot else "-")
            paid = [p for p in payments if p.status in (PaymentStatus.AUTHORIZED, PaymentStatus.REFUNDED)]
            c3.metric("Receipt", paid[-1].receipt_number if paid else "-")
            st.caption("Payment attempts: " + ", ".join(
                f"{p.status.value} {money(p.amount)}" for p in payments))
            history_table(order)
            if order.can_cancel() and st.button("Cancel order and refund", key=f"cx_{order.order_id}"):
                try:
                    tracking.cancel_order(order.order_id, customer.customer_id)
                    st.rerun()
                except DomainError as e:
                    st.error(str(e))


def profile_tab(customer):
    st.subheader("Profile")
    st.caption("UC-06 Manage Customer Profile")
    with st.form("profile"):
        name = st.text_input("Name", customer.name)
        contact = st.text_input("Email or phone", customer.contact_details)
        if st.form_submit_button("Save profile"):
            try:
                profiles.update_profile(customer.customer_id, name, contact)
                st.success("Profile saved.")
            except DomainError as e:
                st.error(str(e))

    st.markdown("**Saved addresses**")
    for a in repo.list_addresses(customer.customer_id):
        st.write(("✅ " if a.serviceable else "⚠️ ") + a.label() +
                 ("" if a.serviceable else " — outside our service sectors"))
    with st.form("add_address", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        street = c1.text_input("Street address")
        postal = c2.text_input("Postal code", placeholder="H3H 1K6")
        if st.form_submit_button("Add address"):
            try:
                a = profiles.add_address(customer.customer_id, street, postal)
                (st.success if a.serviceable else st.warning)(
                    "Address saved." if a.serviceable else "Saved, but we don't serve that area yet.")
            except DomainError as e:
                st.error(str(e))

    st.markdown("**Saved payment methods**")
    for m in repo.list_payment_methods(customer.customer_id):
        st.write("💳 " + m.label)
    st.caption("Only the processor's token is stored, never the card number.")

    st.markdown("**Notifications**")
    for n in repo.list_notifications(customer.customer_id, 8):
        st.write(f"`{n['created_at'][5:16].replace('T', ' ')}` {n['message']}")


# =================================================================
# STAFF INTERFACE
# =================================================================
def staff_board(staff):
    st.subheader("Order board")
    st.caption("UC-02 Update Order Status · drivers record pickup and delivery, laundry staff record washing")
    orders = repo.list_active_orders()
    if not orders:
        st.info("No active orders right now.")
        return
    services = {s.service_type_id: s.name for s in repo.list_service_types(active_only=False)}
    for order in orders:
        customer = repo.get_customer(order.customer_id)
        nxt = order.next_status()
        with st.container(border=True):
            st.markdown(f"**{order.order_id}** · {customer.name} · {services[order.service_type_id]}, "
                        f"{order.bag_size.value}")
            timeline(order)
            if nxt is None:
                continue
            allowed = staff.has_role(ROLE_FOR_STATUS[nxt])
            c1, c2 = st.columns([3, 2])
            note = c1.text_input("Note (optional)", key=f"n_{order.order_id}", label_visibility="collapsed",
                                 placeholder="Note for this update (optional)")
            if c2.button(f"Mark '{nxt.value}'", key=f"b_{order.order_id}", disabled=not allowed,
                         type="primary", use_container_width=True):
                try:
                    tracking.advance_status(order.order_id, staff.staff_member_id, note)
                    st.rerun()
                except DomainError as e:
                    st.error(str(e))
            if not allowed:
                st.caption(f"Waiting on a {ROLE_FOR_STATUS[nxt].value} for this step.")


# ---------------- page ----------------
if role == "Customer":
    st.title(f"Hi, {customer.name.split()[0]}")
    t1, t2, t3 = st.tabs(["Book a pickup", "My orders", "Profile"])
    with t1:
        booking_tab(customer)
    with t2:
        orders_tab(customer)
    with t3:
        profile_tab(customer)
else:
    st.title("Operations")
    staff_board(staff_member)
