// UC04 Plan Driver Routes: build from a shift, optimize, finalize, insert a live pickup, complete stops.
import React, { useEffect, useState } from "react";
import { CheckCircle2, Flag, MapPin, Plus, Route as RouteIcon, Sparkles, Truck } from "lucide-react";
import { useApp } from "../App.jsx";
import { Banner, Button, Card, ErrorText, Field, KV, Loading, Note, PageTitle, Pill, clock, day, inputCls, useApi } from "../ui.jsx";
import { useStaffAction } from "./common.jsx";

const ROUTE_TONE = { Draft: "grey", Optimized: "info", Finalized: "success", InProgress: "amber", Completed: "success" };

export default function RoutesPage() {
  const { staffId } = useApp();
  const q = useApi("routes", { staff_id: staffId });
  const [sel, setSel] = useState(null);
  const a = useStaffAction((r) => { q.reload(); if (r?.id) setSel(r.id); });
  if (!q.data && !q.error) return <><PageTitle title="Driver routes" /><Loading /></>;
  const d = q.data;
  const route = d.routes.find((r) => r.id === sel) || d.routes[d.routes.length - 1];
  return (
    <>
      <PageTitle title="Driver routes" subtitle="Turn a driver's shift into an ordered list of pickups and deliveries." />
      {a.msg && <Banner tone="success" title={a.msg} />}
      <ErrorText>{a.err}</ErrorText>
      <div className="mt-3 grid gap-5 lg:grid-cols-[1fr_1.6fr]">
        <div className="space-y-5">
          <Build d={d} a={a} />
          {d.routes.length > 0 && (
            <Card title="Routes">
              <div className="space-y-2">
                {d.routes.map((r) => (
                  <button key={r.id} onClick={() => setSel(r.id)} className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm ${route?.id === r.id ? "border-brand-600 bg-brand-50" : "border-gray-200 hover:bg-gray-50"}`}>
                    <Truck className="h-4 w-4 text-gray-400" /><span className="flex-1"><b>{r.driver}</b><span className="block text-xs text-gray-500">{day(r.date)} · {r.sector} · {r.stops.length} stops</span></span>
                    <Pill tone={ROUTE_TONE[r.status]}>{r.status}</Pill>
                  </button>
                ))}
              </div>
            </Card>
          )}
        </div>
        {route ? <RouteView r={route} live={d.live_orders} a={a} /> : (
          <Card><div className="flex flex-col items-center py-14 text-center text-sm text-gray-500"><RouteIcon className="mb-3 h-10 w-10 text-gray-200" />No routes yet. Build one from a driver's shift.</div></Card>
        )}
      </div>
    </>
  );
}

function Build({ d, a }) {
  const [f, setF] = useState({ shift_id: "", sector_id: "", vehicle_id: "" });
  useEffect(() => {
    setF((x) => ({ shift_id: x.shift_id && d.shifts.some((s) => s.id === x.shift_id) ? x.shift_id : (d.shifts.find((s) => s.orders_waiting > 0) || d.shifts[0])?.id || "",
                   sector_id: x.sector_id || d.sectors[0]?.id || "", vehicle_id: x.vehicle_id || d.vehicles[0]?.id || "" }));
  }, [d]);
  if (!d.shifts.length) return <Card title="Build a route"><p className="text-sm text-gray-500">Every open driver shift already has a route.</p></Card>;
  const shift = d.shifts.find((s) => s.id === f.shift_id);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <Card title="Build a route" subtitle="Pulls in every scheduled order for that day inside the sector.">
      <div className="space-y-3">
        <Field label="Driver shift"><select className={inputCls} value={f.shift_id} onChange={set("shift_id")}>
          {d.shifts.map((s) => <option key={s.id} value={s.id}>{s.driver} · {day(s.date)} {clock(s.start)}–{clock(s.end)} ({s.orders_waiting} order{s.orders_waiting === 1 ? "" : "s"} waiting)</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Sector"><select className={inputCls} value={f.sector_id} onChange={set("sector_id")}>{d.sectors.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
          <Field label="Vehicle"><select className={inputCls} value={f.vehicle_id} onChange={set("vehicle_id")}>{d.vehicles.map((v) => <option key={v.id} value={v.id}>{v.id} ({v.capacity} slots)</option>)}</select></Field>
        </div>
      </div>
      <Button variant="primary" className="mt-4 w-full" icon={RouteIcon} loading={a.isBusy("build_route", f)}
        onClick={() => a.run("build_route", f, (r) => `Route built for ${r.driver}: ${r.stops.length} stops.`)}>Build route</Button>
      {shift && shift.orders_waiting === 0 && <p className="mt-2 text-xs text-gray-500">No scheduled orders that day yet — the route will start empty.</p>}
    </Card>
  );
}

function RouteView({ r, live, a }) {
  const [liveId, setLiveId] = useState("");
  const editable = ["Draft", "Optimized"].includes(r.status);
  const pct = r.capacity ? Math.round((r.occupied / r.capacity) * 100) : 0;
  return (
    <Card title={`${r.driver} · ${day(r.date)}`} subtitle={`${r.sector} sector · vehicle ${r.vehicle}`} right={<Pill tone={ROUTE_TONE[r.status]}>{r.status}</Pill>}>
      <div className="mb-4 grid grid-cols-3 gap-3 text-center">
        <div className="rounded-xl bg-gray-50 p-3"><div className="text-xl font-bold">{r.stops.length}</div><div className="text-xs text-gray-500">Stops</div></div>
        <div className="rounded-xl bg-gray-50 p-3"><div className="text-xl font-bold">{r.distance} km</div><div className="text-xs text-gray-500">Estimated</div></div>
        <div className="rounded-xl bg-gray-50 p-3"><div className="text-xl font-bold">{r.available}</div><div className="text-xs text-gray-500">Free slots</div></div>
      </div>
      <div className="mb-1 flex justify-between text-xs text-gray-500"><span>Vehicle load</span><span>{r.occupied}/{r.capacity}</span></div>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-gray-100"><div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} /></div>
      {r.flagged.length > 0 && <div className="mb-4"><Note><span className="flex items-center gap-2"><Flag className="h-4 w-4 text-amber-600" />Didn't fit the vehicle, flagged for another route: {r.flagged.join(", ")}</span></Note></div>}
      <ol className="space-y-2">
        {r.stops.map((s) => (
          <li key={s.id} className={`flex items-center gap-3 rounded-xl border p-3 ${s.status === "Completed" ? "border-green-200 bg-green-50/50" : "border-gray-200"}`}>
            <span className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-bold ${s.status === "Completed" ? "bg-green-600 text-white" : "bg-brand-100 text-brand-700"}`}>{s.status === "Completed" ? <CheckCircle2 className="h-4 w-4" /> : s.seq}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-sm"><b>{s.type}</b><span className="text-gray-500">{s.customer} · {s.order}</span></div>
              <div className="flex items-center gap-1 truncate text-xs text-gray-500"><MapPin className="h-3 w-3" />{s.address}{s.eta ? ` · ETA ${clock(s.eta)}` : ""}</div>
            </div>
            {["Finalized", "InProgress"].includes(r.status) && s.status === "Planned" &&
              <Button className="!px-3 !py-1.5 text-xs" loading={a.isBusy("complete_stop", { stop_id: s.id })} onClick={() => a.run("complete_stop", { stop_id: s.id }, `Stop ${s.seq} completed.`)}>Done</Button>}
          </li>
        ))}
        {!r.stops.length && <p className="py-6 text-center text-sm text-gray-400">No stops yet.</p>}
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        {editable && <Button icon={Sparkles} loading={a.isBusy("optimize_route", { route_id: r.id })} onClick={() => a.run("optimize_route", { route_id: r.id }, (x) => `Optimized: ${x.distance} km, stops re-ordered by area.`)}>Optimize</Button>}
        {editable && <Button variant="primary" icon={CheckCircle2} loading={a.isBusy("finalize_route", { route_id: r.id })} onClick={() => a.run("finalize_route", { route_id: r.id }, "Route finalized and sent to the driver.")}>Finalize</Button>}
      </div>
      {r.status !== "Completed" && live.length > 0 && (
        <div className="mt-5 rounded-xl bg-amber-50 p-3.5">
          <div className="mb-2 text-sm font-semibold text-amber-800">Insert a live pickup</div>
          <div className="flex gap-2">
            <select className={inputCls} value={liveId} onChange={(e) => setLiveId(e.target.value)}>
              <option value="">Choose a live order…</option>{live.map((o) => <option key={o.id} value={o.id}>{o.id} · {o.customer}</option>)}</select>
            <Button icon={Plus} disabled={!liveId} loading={a.isBusy("insert_live_pickup", { route_id: r.id, order_id: liveId })}
              onClick={() => a.run("insert_live_pickup", { route_id: r.id, order_id: liveId }, `Live pickup ${liveId} added to the route.`)}>Add</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
