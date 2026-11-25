// Staff home: today's numbers and anything that needs attention.
import React from "react";
import { AlertTriangle, ArrowRight, Boxes, ClipboardList, Route as RouteIcon, WashingMachine } from "lucide-react";
import { useApp } from "../App.jsx";
import { Card, Loading, PageTitle, Pill, Stat, statusTone, useApi } from "../ui.jsx";

export default function Overview() {
  const { staffId, go, people } = useApp();
  const me = people.staff.find((s) => s.id === staffId);
  const board = useApi("staff_board", { staff_id: staffId });
  const routes = useApi("routes", { staff_id: staffId });
  const machines = useApi("machines", { staff_id: staffId });
  const inv = useApi("inventory", { staff_id: staffId });
  if ([board, routes, machines, inv].some((q) => !q.data)) return <><PageTitle title="Operations overview" /><Loading /></>;
  const c = board.data.counts;
  const inProcess = ["Picked Up", "Waiting for Wash", "Washing", "Ready for Pickup", "Out for Delivery"].reduce((s, k) => s + (c[k] || 0), 0);
  const down = machines.data.machines.filter((m) => m.status !== "Operational");
  const low = inv.data.filter((i) => i.low);
  const alerts = [
    ...down.map((m) => ({ icon: WashingMachine, text: `${m.id} (${m.type}) is ${m.status}`, page: "machines" })),
    ...low.map((i) => ({ icon: Boxes, text: `${i.name} is low: ${i.quantity} left (reorder at ${i.reorder})`, page: "inventory" })),
    ...routes.data.live_orders.map((o) => ({ icon: RouteIcon, text: `Live pickup ${o.id} (${o.customer}) needs a route`, page: "routes" })),
  ];
  const tiles = [
    { icon: ClipboardList, label: "Order board", sub: "Move orders through each stage", page: "board" },
    { icon: RouteIcon, label: "Routes", sub: "Build and optimize driver routes", page: "routes" },
    { icon: WashingMachine, label: "Machines", sub: "Faults, repairs, slot capacity", page: "machines" },
    { icon: Boxes, label: "Inventory", sub: "Stock movements and alerts", page: "inventory" },
  ];
  return (
    <>
      <PageTitle title={`Good day, ${me.name.split(" ")[0]}`} subtitle={`Signed in as ${me.roles.join(", ").replace(/([a-z])([A-Z])/g, "$1 $2")}. Here's where operations stand.`} />
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Scheduled" value={c.Scheduled || 0} tone="text-brand-700" sub="Waiting for pickup" />
        <Stat label="In process" value={inProcess} tone="text-amber-600" sub="Picked up → out for delivery" />
        <Stat label="Delivered" value={c.Delivered || 0} tone="text-green-700" />
        <Stat label="Routes" value={routes.data.routes.length} sub={`${routes.data.shifts.length} driver shifts open`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card title="Needs attention" right={<Pill tone={alerts.length ? "amber" : "success"}>{alerts.length ? `${alerts.length} item${alerts.length > 1 ? "s" : ""}` : "All clear"}</Pill>}>
          {alerts.length ? (
            <ul className="space-y-2">
              {alerts.map((a, i) => (
                <li key={i}><button onClick={() => go(a.page)} className="flex w-full items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-left text-sm hover:bg-amber-100">
                  <AlertTriangle className="h-4 w-4 flex-none text-amber-600" /><span className="flex-1">{a.text}</span><ArrowRight className="h-4 w-4 text-amber-600" /></button></li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-500">No machine faults, low stock or unassigned live pickups.</p>}
          <div className="mt-5 text-xs font-semibold uppercase tracking-wide text-gray-400">Active orders</div>
          <ul className="mt-2 divide-y divide-gray-100">
            {board.data.orders.slice(0, 5).map((o) => (
              <li key={o.id} className="flex items-center gap-3 py-2.5 text-sm"><span className="font-semibold">{o.id}</span><span className="flex-1 truncate text-gray-500">{o.customer.name}</span><Pill tone={statusTone(o.status)}>{o.status}</Pill></li>
            ))}
          </ul>
        </Card>
        <div className="grid grid-cols-2 gap-3 self-start">
          {tiles.map((t) => (
            <button key={t.page} onClick={() => go(t.page)} className="rounded-2xl border border-gray-200 bg-white p-4 text-left shadow-card transition hover:-translate-y-0.5 hover:border-brand-200">
              <t.icon className="h-6 w-6 text-brand-600" /><div className="mt-3 font-semibold">{t.label}</div><div className="text-xs text-gray-500">{t.sub}</div>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
