// UC02 Track Order Status (customer, read-only) + UC06 order history and "Book again".
import React, { useState } from "react";
import { ArrowLeft, ChevronRight, Clock, Package, RefreshCw, Repeat } from "lucide-react";
import { useApp } from "../App.jsx";
import { call } from "../py.js";
import { Banner, Button, Card, ErrorText, KV, Loading, Note, PageTitle, Pill, Stepper, money, slotText, statusTone,
         useApi, when } from "../ui.jsx";

export default function Orders() {
  const { openOrder, setOpenOrder } = useApp();
  return openOrder ? <Detail id={openOrder} back={() => setOpenOrder(null)} /> : <List open={setOpenOrder} />;
}

function List({ open }) {
  const { customerId, go } = useApp();
  const q = useApi("my_orders", { customer_id: customerId });
  if (!q.data && !q.error) return <><PageTitle title="My Orders" /><Loading /></>;
  const orders = q.data;
  const active = orders.filter((o) => !["Delivered", "Cancelled"].includes(o.status));
  const past = orders.filter((o) => ["Delivered", "Cancelled"].includes(o.status));
  if (!orders.length) {
    return (
      <>
        <PageTitle title="My Orders" subtitle="Track your current orders and see your history." />
        <Card>
          <div className="flex flex-col items-center py-10 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-50"><Package className="h-7 w-7 text-brand-600" /></div>
            <div className="mt-4 text-lg font-semibold">No orders yet</div>
            <p className="mt-1 max-w-sm text-sm text-gray-500">Once you book a pickup, you'll be able to follow every step here — from pickup to delivery.</p>
            <Button variant="primary" className="mt-5" onClick={() => go("book")}>Book your first pickup</Button>
          </div>
        </Card>
      </>
    );
  }
  const Row = ({ o }) => (
    <button onClick={() => open(o.id)} className="flex w-full items-center gap-4 rounded-xl px-3 py-3.5 text-left transition hover:bg-gray-50">
      <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-brand-50"><Package className="h-5 w-5 text-brand-600" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{o.id}</span><Pill tone={statusTone(o.status)}>{o.status}</Pill></div>
        <div className="truncate text-sm text-gray-500">{o.service.name} · {o.bag_size} · pickup {slotText(o.pickup_slot)}</div>
      </div>
      <div className="hidden text-right sm:block"><div className="font-semibold">{money(o.price.final_total)}</div><div className="text-xs text-gray-500">{o.payment ? "Paid" : "Not paid"}</div></div>
      <ChevronRight className="h-5 w-5 text-gray-300" />
    </button>
  );
  return (
    <>
      <PageTitle title="My Orders" subtitle="Track your current orders and see your history." right={<Button icon={RefreshCw} onClick={q.reload}>Refresh</Button>} />
      <div className="space-y-5">
        <Card title="In progress" right={<span className="text-sm text-gray-500">{active.length}</span>}>
          {active.length ? <div className="-mx-3 divide-y divide-gray-100">{active.map((o) => <Row key={o.id} o={o} />)}</div>
            : <p className="text-sm text-gray-500">Nothing in progress right now.</p>}
        </Card>
        <Card title="Order history" right={<span className="text-sm text-gray-500">{past.length}</span>}>
          {past.length ? <div className="-mx-3 divide-y divide-gray-100">{past.map((o) => <Row key={o.id} o={o} />)}</div>
            : <p className="text-sm text-gray-500">Completed orders will appear here.</p>}
        </Card>
      </div>
    </>
  );
}

const SHORT = { "Picked Up": "Picked up", "Waiting for Wash": "Queued", "Ready for Pickup": "Ready", "Out for Delivery": "Out for delivery" };

function Detail({ id, back }) {
  const { customerId, setCheckout, go } = useApp();
  const q = useApi("order_status", { customer_id: customerId, order_id: id });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!q.data && !q.error) return <Loading />;
  if (q.error) return <><Button icon={ArrowLeft} onClick={back}>All orders</Button><ErrorText>{q.error}</ErrorText></>;
  const o = q.data;
  const again = async () => {
    setBusy(true); setErr(null);
    try { const r = await call("repeat_booking", { customer_id: customerId, order_id: o.id }); setCheckout({ step: "slots", orderId: r.order_id }); go("book"); }
    catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const cancelled = o.status === "Cancelled";
  return (
    <>
      <button onClick={back} className="mb-3 flex items-center gap-1 text-sm font-medium text-gray-500 hover:text-gray-900"><ArrowLeft className="h-4 w-4" />All orders</button>
      <PageTitle title={`Order ${o.id}`} subtitle={`${o.service.name} · ${o.bag_size} bag`}
        right={<div className="flex gap-2"><Button icon={RefreshCw} onClick={q.reload}>Refresh</Button>
          {["Delivered", "Cancelled"].includes(o.status) && <Button variant="primary" icon={Repeat} loading={busy} onClick={again}>Book again</Button>}</div>} />
      <ErrorText>{err}</ErrorText>
      {cancelled ? <Banner tone="danger" title="This order was cancelled">{o.payment ? "" : "Any payment was refunded to the original method."}</Banner> : (
        <Banner tone={o.status === "Delivered" ? "success" : "info"} title={`Current status: ${o.status}`} pill={o.status} pillTone={statusTone(o.status)}>
          Last updated {when(o.latest?.at)}{o.latest?.notes ? ` · “${o.latest.notes}”` : ""}
        </Banner>
      )}
      {!cancelled && (
        <Card className="mb-5" title="Progress">
          <div className="overflow-x-auto"><div className="min-w-[560px]">
            <Stepper small steps={o.progress.steps.map((s) => SHORT[s] || s)} current={o.progress.index} done={o.status === "Delivered"} />
          </div></div>
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <Card title="Status history" subtitle="Every update recorded by our team.">
          <ol className="relative ml-2 border-l-2 border-gray-100">
            {[...o.history].reverse().map((h, i) => (
              <li key={i} className="mb-5 ml-5 last:mb-0">
                <span className={`absolute -left-[7px] mt-1 h-3 w-3 rounded-full ${i === 0 ? "bg-brand-600 ring-4 ring-brand-100" : "bg-gray-300"}`} />
                <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{h.status}</span><span className="flex items-center gap-1 text-xs text-gray-500"><Clock className="h-3 w-3" />{when(h.at)}</span></div>
                {(h.notes || h.by) && <div className="text-sm text-gray-500">{h.notes}{h.notes && h.by ? " · " : ""}{h.by ? `by ${h.by}` : ""}</div>}
              </li>
            ))}
          </ol>
        </Card>
        <div className="space-y-5">
          <Card title="Order details">
            <KV rows={[["Pickup", slotText(o.pickup_slot)], ["Delivery", slotText(o.delivery_slot)], ["Address", o.pickup_address.label],
                       ["Payment", o.payment ? `${o.payment.status} · ${o.payment.method}` : "—"], o.payment && ["Receipt", o.payment.receipt],
                       o.reward && ["Reward", o.reward.name, "text-violet-700"], o.promotion && ["Promo", o.promotion, "text-green-700"]]}
                total={money(o.price.final_total)} totalLabel="Total" />
          </Card>
          <Note>This page is read-only. Status changes are made by ZippyWash staff and show up here right away.</Note>
        </div>
      </div>
    </>
  );
}
