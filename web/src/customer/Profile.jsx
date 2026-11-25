// UC06 Manage Customer Profile & Order History.
import React, { useEffect, useState } from "react";
import { Bell, CreditCard, MapPin, Plus, UserRound } from "lucide-react";
import { useApp } from "../App.jsx";
import { call } from "../py.js";
import { Banner, Button, Card, ErrorText, Field, Loading, Note, PageTitle, Pill, inputCls, useApi, when } from "../ui.jsx";

export default function Profile() {
  const { customerId, go } = useApp();
  const q = useApi("profile", { customer_id: customerId });
  const [p, setP] = useState(null);
  useEffect(() => { if (q.data) setP(q.data); }, [q.data]);
  if (!p) return <><PageTitle title="Profile" /><Loading /></>;
  return (
    <>
      <PageTitle title="Profile" subtitle="Your details, saved addresses, payment methods and notifications."
        right={<Button onClick={() => go("orders")}>Order history ({p.orders})</Button>} />
      {!p.active && <Banner tone="danger" title="This account is deactivated">You can still see your history, but you can't place new orders.</Banner>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Details p={p} setP={setP} />
        <Addresses p={p} setP={setP} />
        <Methods p={p} setP={setP} />
        <Notifications p={p} />
      </div>
      {p.active && <Deactivate setP={setP} />}
    </>
  );
}

function useAction(setP) {
  const { customerId } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [ok, setOk] = useState(null);
  const run = async (name, payload, done) => {
    setBusy(true); setErr(null); setOk(null);
    try { const r = await call(name, { customer_id: customerId, ...payload }); setP(r.profile || r); done?.(r); return true; }
    catch (e) { setErr(e.message); return false; } finally { setBusy(false); }
  };
  return { run, busy, err, ok, setOk };
}

function Details({ p, setP }) {
  const [f, setF] = useState({ name: p.name, contact: p.contact, preferences: p.preferences || "" });
  const a = useAction(setP);
  return (
    <Card title="Personal details" right={<UserRound className="h-5 w-5 text-gray-300" />}>
      <div className="space-y-3.5">
        <Field label="Full name"><input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Email or phone"><input className={inputCls} value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} /></Field>
        <Field label="Laundry preferences" hint="Our team sees these on every order."><textarea rows={2} className={inputCls} value={f.preferences} onChange={(e) => setF({ ...f, preferences: e.target.value })} /></Field>
      </div>
      <ErrorText>{a.err}</ErrorText>
      {a.ok && <p className="mt-3 text-sm font-medium text-green-700">{a.ok}</p>}
      <Button variant="primary" className="mt-4" loading={a.busy} disabled={!p.active}
        onClick={() => a.run("update_profile", f, () => a.setOk("Profile saved."))}>Save changes</Button>
    </Card>
  );
}

function Addresses({ p, setP }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ street: "", postal_code: "", access: "" });
  const [msg, setMsg] = useState(null);
  const a = useAction(setP);
  const add = () => a.run("add_address", f, (r) => {
    setMsg(r.address.serviceable ? { tone: "ok", text: `Added. ${r.address.sector} delivers there.` } : { tone: "warn", text: "Saved, but it's outside our service area, so it can't be used for bookings yet." });
    setF({ street: "", postal_code: "", access: "" }); setOpen(false);
  });
  return (
    <Card title="Saved addresses" right={<Button variant="ghost" icon={Plus} disabled={!p.active} onClick={() => setOpen(!open)}>Add</Button>}>
      <ul className="space-y-2">
        {p.addresses.map((x) => (
          <li key={x.id} className="flex items-start gap-3 rounded-xl border border-gray-200 p-3">
            <MapPin className={`mt-0.5 h-4 w-4 flex-none ${x.serviceable ? "text-brand-600" : "text-gray-300"}`} />
            <div className="min-w-0 flex-1"><div className="text-sm font-medium">{x.label}</div>{x.access && <div className="text-xs text-gray-500">{x.access}</div>}</div>
            {x.serviceable ? <Pill tone="success">{x.sector}</Pill> : <Pill tone="danger">Outside area</Pill>}
          </li>
        ))}
      </ul>
      {msg && <div className="mt-3"><Note tone={msg.tone === "ok" ? "info" : "grey"}>{msg.text}</Note></div>}
      {open && (
        <div className="fade-in mt-4 space-y-3 rounded-xl bg-gray-50 p-3.5">
          <Field label="Street"><input className={inputCls} placeholder="1455 De Maisonneuve Blvd W" value={f.street} onChange={(e) => setF({ ...f, street: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Postal code"><input className={inputCls} placeholder="H3G 1M8" value={f.postal_code} onChange={(e) => setF({ ...f, postal_code: e.target.value })} /></Field>
            <Field label="Access notes"><input className={inputCls} placeholder="Buzz 12" value={f.access} onChange={(e) => setF({ ...f, access: e.target.value })} /></Field>
          </div>
          <ErrorText>{a.err}</ErrorText>
          <Button variant="primary" loading={a.busy} onClick={add}>Save address</Button>
        </div>
      )}
    </Card>
  );
}

function Methods({ p, setP }) {
  const [label, setLabel] = useState("");
  const [open, setOpen] = useState(false);
  const a = useAction(setP);
  return (
    <Card title="Payment methods" right={<Button variant="ghost" icon={Plus} disabled={!p.active} onClick={() => setOpen(!open)}>Add</Button>}>
      <ul className="space-y-2">
        {p.methods.map((m) => (
          <li key={m.id} className="flex items-center gap-3 rounded-xl border border-gray-200 p-3">
            <CreditCard className="h-4 w-4 text-gray-400" /><span className="flex-1 text-sm font-medium">{m.label}</span>
            <span className="text-xs text-gray-500">{m.type.replace(/([a-z])([A-Z])/g, "$1 $2")}</span>
          </li>
        ))}
      </ul>
      {open && (
        <div className="fade-in mt-4 space-y-3 rounded-xl bg-gray-50 p-3.5">
          <Note>In the real app the payment provider's secure form collects the card. ZippyWash stores only a token — this demo creates a test one.</Note>
          <Field label="Card nickname"><input className={inputCls} placeholder="Visa ending 1111" value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
          <ErrorText>{a.err}</ErrorText>
          <Button variant="primary" loading={a.busy} disabled={!label.trim()} onClick={() => a.run("add_payment_method", { label }, () => { setLabel(""); setOpen(false); })}>Save test card</Button>
        </div>
      )}
    </Card>
  );
}

function Notifications({ p }) {
  return (
    <Card title="Notifications" subtitle="Confirmations and status updates we've sent you." right={<Bell className="h-5 w-5 text-gray-300" />}>
      {p.notifications.length ? (
        <ul className="max-h-80 divide-y divide-gray-100 overflow-y-auto">
          {p.notifications.map((n, i) => (
            <li key={i} className="py-2.5"><div className="text-sm">{n.message}</div><div className="mt-0.5 text-xs text-gray-500">{n.type} · {when(n.at)}</div></li>
          ))}
        </ul>
      ) : <p className="text-sm text-gray-500">No notifications yet.</p>}
    </Card>
  );
}

function Deactivate({ setP }) {
  const [confirm, setConfirm] = useState(false);
  const a = useAction(setP);
  return (
    <Card className="mt-5" title="Deactivate account" subtitle="Stops new bookings. Your order history is kept.">
      {confirm ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-700">Are you sure?</span>
          <Button variant="danger" loading={a.busy} onClick={() => a.run("deactivate_account", {})}>Yes, deactivate</Button>
          <Button variant="ghost" onClick={() => setConfirm(false)}>Keep my account</Button>
        </div>
      ) : <Button variant="danger" onClick={() => setConfirm(true)}>Deactivate account</Button>}
      <ErrorText>{a.err}</ErrorText>
    </Card>
  );
}
