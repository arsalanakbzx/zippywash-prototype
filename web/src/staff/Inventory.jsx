// UC03 inventory: record stock movements; a low-stock alert opens at the reorder level.
import React, { useState } from "react";
import { AlertTriangle, Minus, Package, Plus } from "lucide-react";
import { useApp } from "../App.jsx";
import { Banner, Button, Card, ErrorText, Loading, PageTitle, Pill, inputCls, useApi, when } from "../ui.jsx";
import { useStaffAction } from "./common.jsx";

const pretty = (s) => s.replace(/([a-z])([A-Z])/g, "$1 $2");

export default function Inventory() {
  const { staffId } = useApp();
  const q = useApi("inventory", { staff_id: staffId });
  const [data, setData] = useState(null);
  const a = useStaffAction((r) => setData(r));
  if (!q.data && !data) return <><PageTitle title="Inventory" /><Loading /></>;
  const items = data || q.data;
  const low = items.filter((i) => i.low);
  return (
    <>
      <PageTitle title="Inventory" subtitle="Every receipt and use of supplies is recorded. Dropping to the reorder level raises an alert." />
      {low.length > 0 && <Banner tone="amber" title={`Low stock: ${low.map((i) => i.name).join(", ")}`} pill="Reorder">Order more before the next washing shift.</Banner>}
      {a.msg && <Banner tone="success" title={a.msg} />}
      <ErrorText>{a.err}</ErrorText>
      <div className="mt-3 grid gap-5 md:grid-cols-2 lg:grid-cols-3">{items.map((i) => <Item key={i.id} i={i} a={a} />)}</div>
    </>
  );
}

function Item({ i, a }) {
  const [qty, setQty] = useState("1");
  const q = Number(i.quantity), r = Number(i.reorder);
  const pct = Math.min(100, Math.round((q / Math.max(r * 3, 1)) * 100));
  const move = (type) => a.run("record_stock", { item_id: i.id, movement_type: type, quantity: qty }, `${pretty(type)} of ${qty} recorded for ${i.name}.`);
  return (
    <Card title={i.name} right={i.low ? <Pill tone="danger">Low</Pill> : <Pill tone="success">OK</Pill>}>
      <div className="flex items-end justify-between"><div className="text-3xl font-bold">{i.quantity}</div><div className="text-xs text-gray-500">reorder at {i.reorder}</div></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100"><div className={`h-full rounded-full transition-all ${i.low ? "bg-red-500" : "bg-green-500"}`} style={{ width: `${pct}%` }} /></div>
      <div className="mt-4 flex gap-2">
        <input type="number" min="1" className={`${inputCls} w-20`} value={qty} onChange={(e) => setQty(e.target.value)} />
        <Button className="flex-1 !px-2" icon={Minus} onClick={() => move("Consumption")}>Use</Button>
        <Button className="flex-1 !px-2" icon={Plus} onClick={() => move("Receipt")}>Receive</Button>
      </div>
      {i.alert && <p className="mt-2 flex items-center gap-1.5 text-xs text-red-600"><AlertTriangle className="h-3.5 w-3.5" />Reorder alert open</p>}
      <div className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-400">Recent movements</div>
      <ul className="mt-1.5 space-y-1">
        {i.movements.map((m, k) => (
          <li key={k} className="flex items-center gap-2 text-xs text-gray-600"><Package className="h-3 w-3 text-gray-300" /><span className="flex-1">{pretty(m.type)} · {m.quantity}{m.by ? ` · ${m.by}` : ""}</span><span className="text-gray-400">{when(m.at)}</span></li>
        ))}
        {!i.movements.length && <li className="text-xs text-gray-400">None yet</li>}
      </ul>
    </Card>
  );
}
