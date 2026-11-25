// UC01-SC1 booking with UC05 payment and UC07-SC2 rewards at checkout (Milestone 6 screens WF01-WF05).
import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, CalendarClock, CreditCard, Gift, Lock, MapPin, Package, Tag, X } from "lucide-react";
import { useApp } from "../App.jsx";
import { call } from "../py.js";
import { Banner, Button, Card, Choice, ErrorText, Field, KV, Loading, Note, PageTitle, Pill, Stepper, clock, day,
         inputCls, money, slotText, useApi } from "../ui.jsx";

const STEPS = ["Details", "Time Slots", "Review", "Payment", "Confirmation"];
const STEP_INDEX = { details: 0, slots: 1, review: 2, reward: 2, reserved: 2, restored: 2, payment: 3, failed: 3,
                     redeemed: 3, confirmed: 4 };

export default function Booking() {
  const { checkout, setCheckout, customerId } = useApp();
  const orderQ = useApi(checkout.orderId ? "order" : null, { customer_id: customerId, order_id: checkout.orderId },
                        [checkout.step]);
  const order = orderQ.data;
  const go = (step, extra = {}) => { setCheckout((c) => ({ ...c, ...extra, step })); window.scrollTo({ top: 0 }); };

  const Screen = { details: Details, slots: Slots, review: Review, reward: ChooseReward, reserved: Reserved,
                   payment: Payment, failed: Failed, redeemed: Redeemed, restored: Restored, confirmed: Confirmed }[checkout.step];
  if (checkout.step !== "details" && !order && orderQ.loading) return <Loading />;
  if (checkout.step !== "details" && !order) return <Details go={go} />;
  return (
    <div>
      <Screen order={order} go={go} reload={orderQ.reload} />
    </div>
  );
}

function Header({ title = "Book Pickup & Delivery", subtitle, step, done }) {
  return (
    <>
      <PageTitle title={title} subtitle={subtitle} />
      <Card className="mb-6" pad={false}><div className="px-3 pt-5 sm:px-8"><Stepper steps={STEPS} current={STEP_INDEX[step]} done={done} /></div></Card>
    </>
  );
}

function Footer({ back, onBack, step, children }) {
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
      {back ? <Button icon={ArrowLeft} onClick={onBack}>{back}</Button> : <span />}
      <span className="hidden text-xs text-gray-400 sm:block">Step {STEP_INDEX[step] + 1} of 5</span>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}

function PriceCard({ order, title = "Estimated price", children, totalLabel = "Estimated total" }) {
  const p = order.price;
  const rows = [[`${order.service.name} · ${order.bag_size}`, money(p.subtotal)]];
  if (order.promotion) rows.push([`Promo ${order.promotion}`, `−${money(p.discount)}`, "text-green-700"]);
  if (order.reward && order.reward_state !== "Redeemed") rows.push([`${order.reward.name} reward`, `−${money(p.discount)}`, "text-violet-700"]);
  if (order.reward && order.reward_state === "Redeemed") rows.push([`${order.reward.name} reward`, `−${money(p.discount)}`, "text-violet-700"]);
  rows.push(["Pickup & delivery fee", money(p.delivery_fee)], ["GST (5%)", money(p.gst)], ["QST (9.975%)", money(p.qst)]);
  return (
    <Card title={title} subtitle="Calculated before payment.">
      <KV rows={rows} total={money(p.total)} totalLabel={totalLabel} />
      {children}
    </Card>
  );
}

function Summary({ order }) {
  return (
    <Card title="Booking summary">
      <div className="space-y-4 text-sm">
        <Section icon={Package} label="Service details" rows={[["Service", order.service.name], ["Bag size", order.bag_size],
          ["Pickup request", order.pickup_request_type === "Live" ? "Live (same-day route)" : "Scheduled"]]} />
        <Section icon={MapPin} label="Addresses" rows={[["Pickup", order.pickup_address.label], ["Delivery", order.delivery_address.label]]} />
        <Section icon={CalendarClock} label="Schedule" rows={[["Pickup", slotText(order.pickup_slot)], ["Delivery", slotText(order.delivery_slot)]]} />
      </div>
    </Card>
  );
}
function Section({ icon: Icon, label, rows }) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500"><Icon className="h-3.5 w-3.5" />{label}</div>
      <KV rows={rows} />
    </div>
  );
}

// ---------------- WF01 Booking Details ----------------
function Details({ go }) {
  const { customerId } = useApp();
  const opts = useApi("booking_options", { customer_id: customerId });
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (opts.data && !form) {
      const a = opts.data.addresses[0]?.id;
      setForm({ service: opts.data.services[0]?.id, bag: "Small", pickup: a, delivery: a, type: "Scheduled" });
    }
  }, [opts.data, form]);
  if (opts.loading || !form) return <><Header step="details" subtitle="Choose your laundry service and confirm where we should pick up and deliver." /><Loading /></>;
  const o = opts.data;
  if (!o.active) return <><Header step="details" /><Banner tone="danger" title="This account is deactivated">It can't place new orders. Your history is still in My Orders.</Banner></>;
  if (!o.addresses.length) return <><Header step="details" /><Banner tone="info" title="Add an address first">Add an address inside our service area under Profile.</Banner></>;
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));
  const service = o.services.find((x) => x.id === form.service);
  const quote = service?.quotes[form.bag];
  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await call("start_booking", { customer_id: customerId, pickup_address_id: form.pickup, delivery_address_id: form.delivery,
                                               service_type_id: form.service, bag_size: form.bag, pickup_request_type: form.type });
      go("slots", { orderId: r.order_id });
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <Header step="details" subtitle="Choose your laundry service and confirm where we should pick up and deliver." />
      <Card title="Booking details" subtitle="All fields marked * are required.">
        <div className="grid gap-5 md:grid-cols-[1.4fr_1fr]">
          <Field label="Service type *">
            <select className={inputCls} value={form.service} onChange={set("service")}>
              {o.services.map((s) => <option key={s.id} value={s.id}>{s.name} ({money(s.rate)} per small bag)</option>)}
            </select>
          </Field>
          <Field label="Bag size *">
            <Choice columns={3} value={form.bag} onChange={set("bag")} options={o.bag_sizes.map((b) => ({ value: b, label: b }))}
              render={(x) => <><span className="block font-medium leading-tight">{x.label}</span><span className="block text-xs text-gray-500">{money(service?.quotes[x.value].subtotal)}</span></>} />
          </Field>
          <Field label="Pickup address *">
            <select className={inputCls} value={form.pickup} onChange={set("pickup")}>{o.addresses.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select>
          </Field>
          <Field label="Delivery address *" hint="Only saved addresses inside a ZippyWash service area can be used.">
            <select className={inputCls} value={form.delivery} onChange={set("delivery")}>{o.addresses.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select>
          </Field>
          <div className="md:col-span-2">
            <Field label="Pickup request *">
              <Choice columns={2} value={form.type} onChange={set("type")} options={[
                { value: "Scheduled", label: "Scheduled pickup", sub: "Pick a time window" },
                { value: "Live", label: "Live pickup", sub: "Added to today's driver route if there's room" }]}
                render={(x) => <><span className="font-medium">{x.label}</span><span className="block text-xs text-gray-500">{x.sub}</span></>} />
            </Field>
          </div>
        </div>
        {quote && (
          <div className="fade-in mt-6 flex flex-wrap items-end justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3.5" key={`${form.service}-${form.bag}`}>
            <div className="text-sm text-gray-600">
              <div className="font-medium text-gray-900">{service.name} · {form.bag} bag</div>
              {money(quote.subtotal)} + {money(quote.delivery_fee)} pickup & delivery + {money(Number(quote.gst) + Number(quote.qst))} taxes (GST + QST)
            </div>
            <div className="sm:text-right">
              <div className="text-xs font-medium uppercase tracking-wide text-brand-700">Estimated total</div>
              <div className="text-2xl font-bold text-gray-900">{money(quote.total)}</div>
            </div>
          </div>
        )}
        <p className="mt-2 text-xs text-gray-500">Promo codes and loyalty rewards can be applied at Review.</p>
        <ErrorText>{err}</ErrorText>
        <Footer step="details">
          <Button variant="primary" loading={busy} onClick={submit}>Continue to Time Slots <ArrowRight className="h-4 w-4" /></Button>
        </Footer>
      </Card>
    </>
  );
}

// ---------------- WF02 Select Time Slots ----------------
function SlotPicker({ title, slots, value, onChange, after }) {
  const dates = useMemo(() => [...new Set(slots.filter((s) => !after || s.date > after).map((s) => s.date))], [slots, after]);
  const [date, setDate] = useState(null);
  const current = dates.includes(date) ? date : dates[0];
  useEffect(() => {
    const first = slots.find((s) => s.date === current);
    if (current && !slots.some((s) => s.id === value && s.date === current)) onChange(first?.id);
  }, [current]); // eslint-disable-line
  return (
    <div>
      <div className="mb-2 text-sm font-semibold text-gray-900">{title}</div>
      <Field label="Date">
        <select className={inputCls} value={current || ""} onChange={(e) => setDate(e.target.value)}>
          {dates.map((d) => <option key={d} value={d}>{day(d)}</option>)}
        </select>
      </Field>
      <div className="mb-1.5 mt-4 text-sm font-medium text-gray-700">Available time</div>
      <div className="flex flex-wrap gap-2">
        {slots.filter((s) => s.date === current).map((s) => (
          <button key={s.id} onClick={() => onChange(s.id)}
            className={`rounded-xl border px-3.5 py-2 text-sm transition ${value === s.id ? "border-brand-600 bg-brand-50 font-semibold text-brand-700 ring-1 ring-brand-600" : "border-gray-200 bg-white hover:border-gray-300"}`}>
            {clock(s.start)} <span className="text-xs font-normal text-gray-500">· {s.available} left</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Slots({ order, go }) {
  const { customerId } = useApp();
  const q = useApi("open_slots", { customer_id: customerId, order_id: order.id });
  const [p, setP] = useState(order.pickup_slot?.id);
  const [d, setD] = useState(order.delivery_slot?.id);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  if (!q.data && !q.error) return <><Header step="slots" /><Loading /></>;
  const slots = q.data;
  const ps = slots.find((s) => s.id === p);
  const ds = slots.find((s) => s.id === d);
  const back = async () => { await call("cancel_checkout", { customer_id: customerId, order_id: order.id }); go("details", { orderId: null }); };
  const next = async () => {
    setBusy(true); setErr(null);
    try { await call("choose_slots", { customer_id: customerId, order_id: order.id, pickup_slot_id: p, delivery_slot_id: d }); go("review"); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <Header step="slots" subtitle="Choose available times for pickup and delivery." />
      <Card title="Select pickup and delivery times" subtitle="Only currently available times are shown.">
        <div className="grid gap-8 md:grid-cols-2">
          <SlotPicker title="Pickup time *" slots={slots} value={p} onChange={setP} />
          {ps && <SlotPicker title="Delivery time *" slots={slots} value={d} onChange={setD} after={ps.date} key={ps.date} />}
        </div>
        {ps && ds && <div className="mt-6"><Note tone="info">Selected: pickup {slotText(ps)} · delivery {slotText(ds)}. Times are reserved only after your payment is authorized.</Note></div>}
        <ErrorText>{err}</ErrorText>
        <Footer back="Back" onBack={back} step="slots">
          <Button variant="primary" loading={busy} disabled={!ps || !ds} onClick={next}>Continue to Review <ArrowRight className="h-4 w-4" /></Button>
        </Footer>
      </Card>
    </>
  );
}

// ---------------- WF03 Review Estimate ----------------
function Review({ order, go, reload }) {
  const { customerId } = useApp();
  const [code, setCode] = useState("");
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const act = async (name, extra = {}) => {
    setBusy(true); setErr(null);
    try { await call(name, { customer_id: customerId, order_id: order.id, ...extra }); setCode(""); reload(); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <Header step="review" subtitle="Review your booking details and estimated price before payment." />
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-5">
          <Summary order={order} />
          <Note>You can go back and edit these selections before payment.</Note>
        </div>
        <PriceCard order={order}>
          {order.reward_state === "Reserved" && <div className="mt-3 flex items-center gap-2 text-xs text-gray-600"><Pill tone="purple">Reserved</Pill>Points are redeemed only after payment is authorized.</div>}
          <div className="mt-4 rounded-xl border border-gray-200">
            <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3.5 py-3 text-sm font-medium">
              <span className="flex items-center gap-2"><Tag className="h-4 w-4 text-brand-600" />Apply promotion or reward</span>
              <span className="text-xs text-gray-500">{open ? "Hide" : "Show"}</span>
            </button>
            {open && (
              <div className="border-t border-gray-100 p-3.5">
                {order.reward ? (
                  <div className="text-sm text-gray-600"><b>{order.reward.name}</b> is applied. An order can't also use a promo code.
                    <Button variant="ghost" className="mt-2 w-full" onClick={() => act("release_reward")}>Remove reward</Button></div>
                ) : order.promotion ? (
                  <div className="flex items-center justify-between text-sm"><span>Promo <b>{order.promotion}</b> applied</span>
                    <Button variant="ghost" icon={X} onClick={() => act("remove_promo")}>Remove</Button></div>
                ) : (
                  <>
                    <div className="flex gap-2">
                      <input className={inputCls} placeholder="Promo code, e.g. WELCOME10" value={code} onChange={(e) => setCode(e.target.value)} />
                      <Button loading={busy} onClick={() => act("apply_promo", { code })}>Apply</Button>
                    </div>
                    <Button className="mt-2 w-full" icon={Gift} onClick={() => go("reward")}>Use a loyalty reward</Button>
                  </>
                )}
                <ErrorText>{err}</ErrorText>
              </div>
            )}
          </div>
          <p className="mt-2 text-xs text-gray-500">Only one promotion or reward may be applied.</p>
          <Button variant="primary" className="mt-4 w-full" onClick={() => go("payment")}>Proceed to Payment <ArrowRight className="h-4 w-4" /></Button>
        </PriceCard>
      </div>
      <Footer back="Back" onBack={() => go("slots")} step="review" />
    </>
  );
}

// ---------------- UC07 WF01 Choose a Reward ----------------
function ChooseReward({ order, go }) {
  const { customerId } = useApp();
  const q = useApi("reward_options", { customer_id: customerId, order_id: order.id });
  const [pick, setPick] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!q.data && !q.error) return <Loading />;
  const { loyalty, rewards, promotion } = q.data;
  const eligible = rewards.filter((r) => r.eligible);
  const chosen = rewards.find((r) => r.id === pick);
  const apply = async () => {
    setBusy(true); setErr(null);
    try { await call("reserve_reward", { customer_id: customerId, order_id: order.id, reward_id: pick }); go("reserved"); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <Header title="Choose a Reward" subtitle="Apply one eligible loyalty reward to this checkout." step="reward" />
      <Banner tone="purple" title={loyalty ? `${loyalty.available} points` : "Not a loyalty member"} pill={promotion ? "Promotion applied" : "No promotion applied"}>
        {loyalty ? "Available loyalty balance" : "Join under Loyalty / Rewards to use rewards."}
      </Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Eligible rewards" subtitle="Rewards shown here are active and available for this order." right={<span className="text-sm text-gray-500">{eligible.length} available</span>}>
          <Choice value={pick} onChange={setPick} options={rewards.map((r) => ({ ...r, value: r.id, disabled: !r.eligible }))}
            render={(r) => (
              <div className="flex items-center justify-between gap-3">
                <div><div className="font-semibold">{r.name}</div><div className="text-xs text-gray-500">{r.eligible ? `${r.points} points` : r.reason}</div></div>
                <span className={`text-sm font-semibold ${r.eligible ? "text-violet-700" : ""}`}>{money(r.discount)} off</span>
              </div>)} />
          <div className="mt-4"><Note>Applying temporarily reserves the points. They're redeemed only after payment succeeds, and restored if payment fails or checkout is cancelled.</Note></div>
        </Card>
        <Card title="Order impact preview">
          <KV rows={[["Current estimated total", money(order.price.total)], chosen && ["Selected reward discount", `−${money(Math.min(chosen.discount, order.price.subtotal))}`, "text-violet-700"]]} />
          {chosen && loyalty && <div className="mt-3"><Note tone="info">If applied: {chosen.points} reserved · {loyalty.available - chosen.points} available</Note></div>}
          <ErrorText>{err}</ErrorText>
          <Button variant="primary" className="mt-4 w-full" disabled={!pick} loading={busy} onClick={apply}>Apply Reward <ArrowRight className="h-4 w-4" /></Button>
          <p className="mt-2 text-center text-xs text-gray-500">Only one promotion or reward may be applied.</p>
        </Card>
      </div>
      <Footer back="Back to Review" onBack={() => go("review")} step="reward" />
    </>
  );
}

function PointsCard({ title, rows, total, totalLabel }) {
  return <Card title={title}><KV rows={rows} total={total} totalLabel={totalLabel} /></Card>;
}

// ---------------- UC07 WF02 Reward Reserved ----------------
function Reserved({ order, go }) {
  const { customerId } = useApp();
  const l = order.loyalty;
  const [busy, setBusy] = useState(false);
  const cancel = async () => {
    setBusy(true);
    const r = await call("release_reward", { customer_id: customerId, order_id: order.id });
    go("restored", { cause: "cancel", restoredPoints: r.restored_points, message: "Checkout was cancelled before payment." });
  };
  return (
    <>
      <Header title="Reward Reserved" subtitle="Review the updated checkout total before continuing to payment." step="reserved" />
      <Banner tone="purple" title={`${order.reward.name} is reserved for this checkout`} pill="Reserved">
        The {order.reward.points} points are not permanently redeemed until payment is authorized.
      </Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <PriceCard order={order} title="Updated order review" totalLabel="Updated estimated total">
          <div className="mt-3"><Note>Pickup {slotText(order.pickup_slot)} · Delivery {slotText(order.delivery_slot)} · {order.pickup_address.street}</Note></div>
        </PriceCard>
        <div className="space-y-5">
          <PointsCard title="Loyalty point status" rows={[["Total balance", `${l.balance} points`], ["Reserved", `${l.reserved} points`, "text-violet-700"]]}
            total={`${l.available} points`} totalLabel="Available now" />
          <Button variant="primary" className="w-full" onClick={() => go("payment")}>Continue to Payment <ArrowRight className="h-4 w-4" /></Button>
          <Button className="w-full" loading={busy} onClick={cancel}>Cancel Checkout</Button>
          <p className="text-center text-xs text-gray-500">Cancel Checkout releases the reservation and restores all {order.reward.points} points.</p>
        </div>
      </div>
    </>
  );
}

// ---------------- WF04 Payment / WF04E Payment Not Authorized ----------------
function usePay(order, go) {
  const { customerId } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const pay = async (methodId) => {
    setBusy(true); setErr(null);
    const hadReward = order.reward_state === "Reserved";
    try {
      const r = await call("pay", { customer_id: customerId, order_id: order.id, payment_method_id: methodId });
      if (r.authorized) go(r.redeemed_points ? "redeemed" : "confirmed");
      else if (hadReward && r.restored_points) go("restored", { cause: "payment", restoredPoints: r.restored_points, message: r.message, failedMethod: methodId });
      else go("failed", { message: r.message, failedMethod: methodId });
    } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  return { pay, busy, err };
}

function Methods({ value, onChange, failed }) {
  const { customerId } = useApp();
  const q = useApi("payment_methods", { customer_id: customerId });
  useEffect(() => { if (q.data && !value) onChange(q.data[0]?.id); }, [q.data]); // eslint-disable-line
  if (!q.data && !q.error) return <Loading />;
  return (
    <Choice value={value} onChange={onChange} options={q.data.map((m) => ({ ...m, value: m.id }))}
      render={(m) => (
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2.5"><CreditCard className="h-4 w-4 text-gray-400" /><span className="font-medium">{m.label}</span></span>
          {failed === m.id && <Pill tone="danger">Failed</Pill>}
        </div>)} />
  );
}

function TotalCard({ order }) {
  const p = order.price;
  return (
    <Card title="Order total">
      <KV rows={[[`${order.service.name} · ${order.bag_size}`, money(p.subtotal)], Number(p.discount) > 0 && ["Discount", `−${money(p.discount)}`, "text-green-700"],
                 ["Pickup & delivery fee", money(p.delivery_fee)], ["Taxes", money(Number(p.gst) + Number(p.qst))]]}
          total={money(p.total)} totalLabel="Final amount" />
      <div className="mt-3"><Note>Pickup {slotText(order.pickup_slot)} · Delivery {slotText(order.delivery_slot)}</Note></div>
    </Card>
  );
}

function Payment({ order, go }) {
  const [method, setMethod] = useState(null);
  const { pay, busy, err } = usePay(order, go);
  return (
    <>
      <Header step="payment" subtitle="Select a saved payment method and authorize the final amount." />
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Payment method" subtitle="Choose one of your saved payment methods.">
          <Methods value={method} onChange={setMethod} />
          <div className="mt-4"><Note><span className="flex items-start gap-2"><Lock className="mt-0.5 h-4 w-4 flex-none" />Secure online authorization. Your booking is confirmed only after payment is authorized. Only the payment provider's secure token is stored — never a card number.</span></Note></div>
          {order.reward_state === "Reserved" && <div className="mt-3 flex items-center gap-2 text-xs text-gray-600"><Pill tone="purple">Reserved</Pill>{order.reward.name}: points are redeemed only if this payment is authorized.</div>}
        </Card>
        <div className="space-y-4">
          <TotalCard order={order} />
          <ErrorText>{err}</ErrorText>
          <Button variant="primary" className="w-full py-3" loading={busy} disabled={!method} onClick={() => pay(method)}>Pay {money(order.price.total)} & Book</Button>
          <p className="text-center text-xs text-gray-500">One payment attempt will be submitted.</p>
        </div>
      </div>
      <Footer back="Back to Review" onBack={() => go(order.reward_state === "Reserved" ? "reserved" : "review")} step="payment" />
    </>
  );
}

function Failed({ order, go }) {
  const { checkout } = useApp();
  const [method, setMethod] = useState(null);
  const { pay, busy, err } = usePay(order, go);
  return (
    <>
      <Header step="failed" subtitle="Resolve the payment issue to finish your booking." />
      <Banner tone="danger" title="Payment was not authorized">
        {checkout.message} Your booking was <b>not confirmed</b> and the selected time slots were <b>not reserved</b>.
      </Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Choose a payment method" subtitle="The previous attempt was unsuccessful.">
          <Methods value={method} onChange={setMethod} failed={checkout.failedMethod} />
          <ErrorText>{err}</ErrorText>
          <Button variant="primary" className="mt-4 w-full" loading={busy} disabled={!method} onClick={() => pay(method)}>Retry Payment · {money(order.price.total)}</Button>
        </Card>
        <Card title="Booking status" right={<Pill tone="danger">Not confirmed</Pill>}>
          <KV rows={[["Order total", money(order.price.total)], ["Time slots", "Not reserved"], ["Payment", "Not authorized"], ["Attempts", order.attempts]]} />
          <div className="mt-4 text-sm text-gray-600"><div className="mb-1 font-semibold text-gray-900">What you can do</div>• Select another saved payment method<br />• Retry payment<br />• Return to review your booking</div>
        </Card>
      </div>
      <Footer back="Back to Review" onBack={() => go("review")} step="failed" />
    </>
  );
}

// ---------------- UC07 WF03 / WF03E ----------------
function Redeemed({ order, go }) {
  const l = order.loyalty;
  return (
    <>
      <Header title="Reward Redeemed" subtitle="Payment authorization turned the temporary reservation into a completed redemption." step="redeemed" />
      <Banner tone="success" title="Payment authorized and reward redeemed" pill="Redeemed">
        {order.reward.name} used {order.reward.points} points and applied a {money(order.reward.discount)} discount to this order.
      </Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Redemption details" right={<span className="text-sm text-gray-500">Order {order.id}</span>}>
          <div className="mb-3 flex items-center gap-2"><Gift className="h-5 w-5 text-violet-600" /><b>{order.reward.name}</b><Pill tone="success">Complete</Pill></div>
          <KV rows={[["Points redeemed", order.reward.points], ["Discount", money(order.reward.discount)], ["Payment", `Authorized · ${order.payment.method}`]]}
              total={money(order.price.final_total)} totalLabel="Total paid" />
          <div className="mt-3"><Note>The reservation has been used. No points remain on hold for this checkout.</Note></div>
        </Card>
        <div className="space-y-4">
          <PointsCard title="Updated point balance" rows={[["Balance before", `${l.balance + order.reward.points} points`], ["Redeemed", `−${order.reward.points} points`, "text-violet-700"], ["Reserved now", `${l.reserved} points`]]}
            total={`${l.balance} points`} totalLabel="Current balance" />
          <Button variant="primary" className="w-full" onClick={() => go("confirmed")}>Continue to Confirmation <ArrowRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </>
  );
}

function Restored({ order, go }) {
  const { checkout } = useApp();
  const pts = checkout.restoredPoints || 0;
  const l = order.loyalty;
  return (
    <>
      <Header title="Points Restored" subtitle="The checkout didn't complete, so the temporary reward reservation was released." step="restored" />
      {checkout.cause === "payment" && <Banner tone="danger" title="Payment was not authorized">{checkout.message} Your booking was not confirmed and no time slots were reserved.</Banner>}
      <Banner tone="restored" title={`All ${pts} reserved points are available again`} pill="Restored">No reward was redeemed and your loyalty balance is unchanged.</Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Restoration details">
          <KV rows={[["Checkout outcome", checkout.cause === "payment" ? "Payment not authorized" : "Checkout cancelled"], ["Reservation", "Released and restored"], ["Reward", "Not redeemed"]]}
              total={money(order.price.total)} totalLabel="Checkout price" />
          <p className="mt-3 text-xs text-gray-500">The reward discount was removed and the original estimated total is back.</p>
        </Card>
        <div className="space-y-4">
          <PointsCard title="Loyalty point status" rows={[["While reserved", `${l.available - pts} points`], ["Restored", `+${pts} points`, "text-teal-700"], ["Reserved now", `${l.reserved} points`]]}
            total={`${l.available} points`} totalLabel="Available balance" />
          <Button variant="primary" className="w-full" onClick={() => go("review")}>Return to Checkout <ArrowRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </>
  );
}

// ---------------- WF05 Booking Confirmation ----------------
function Confirmed({ order, go }) {
  const { setOpenOrder, go: nav } = useApp();
  return (
    <>
      <Header step="confirmed" done subtitle="Your booking has been scheduled and confirmed." />
      <Banner tone="success" title="Booking confirmed" pill={order.status} pillTone="info">
        Payment was authorized, both time slots were reserved, and your order is now scheduled.
      </Banner>
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Booking details" right={<span className="text-sm"><span className="text-gray-500">Order ID </span><b>{order.id}</b></span>}>
          <KV rows={[["Service", `${order.service.name} · ${order.bag_size} bag`], ["Pickup — reserved", slotText(order.pickup_slot)],
                     ["Delivery — reserved", slotText(order.delivery_slot)], ["Address", order.pickup_address.label],
                     ["Payment", `Authorized · ${order.payment.method}`], ["Receipt", order.payment.receipt],
                     order.reward && ["Reward", `${order.reward.name} (Redeemed)`, "text-violet-700"]]}
              total={money(order.price.final_total)} totalLabel="Total paid" />
        </Card>
        <Card title="What happens next">
          <ol className="space-y-4 text-sm">
            {[["Confirmation sent", `A notification was sent to ${order.customer.contact}.`], ["Prepare for pickup", "Have your laundry ready during the pickup window."],
              ["Track your order", "Follow every status update in My Orders."]].map(([t, d], i) => (
              <li key={t} className="flex gap-3"><span className="flex h-6 w-6 flex-none items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">{i + 1}</span><span><b>{t}</b><span className="block text-gray-500">{d}</span></span></li>
            ))}
          </ol>
          <Button variant="primary" className="mt-5 w-full" onClick={() => { setOpenOrder(order.id); go("details", { orderId: null }); nav("orders"); }}>View My Order <ArrowRight className="h-4 w-4" /></Button>
          <Button className="mt-2 w-full" onClick={() => go("details", { orderId: null })}>Book another pickup</Button>
        </Card>
      </div>
    </>
  );
}
