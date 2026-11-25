// UC02 staff side: record each status change; admin can cancel & refund a scheduled order.
import React, { useState } from "react";
import { ArrowRight, Lock, RefreshCw, XCircle } from "lucide-react";
import { useApp } from "../App.jsx";
import { Banner, Button, Card, ErrorText, Loading, PageTitle, Pill, inputCls, money, slotText, statusTone, useApi } from "../ui.jsx";
import { useStaffAction } from "./common.jsx";

const COLUMNS = [["Scheduled"], ["Picked Up", "Waiting for Wash", "Washing"], ["Ready for Pickup", "Out for Delivery"]];
const COL_NAME = ["Waiting for pickup", "At the laundry", "Delivery"];

export default function Board() {
  const { staffId } = useApp();
  const q = useApi("staff_board", { staff_id: staffId });
  const [notes, setNotes] = useState({});
  const a = useStaffAction(() => q.reload());
  if (!q.data && !q.error) return <><PageTitle title="Order board" /><Loading /></>;
  const { orders } = q.data;
  return (
    <>
      <PageTitle title="Order board" subtitle="Record each stage as the laundry moves. Customers see every update in My Orders right away."
        right={<Button icon={RefreshCw} onClick={q.reload}>Refresh</Button>} />
      {a.msg && <Banner tone="success" title={a.msg} />}
      <ErrorText>{a.err}</ErrorText>
      <div className="mt-3 grid gap-5 lg:grid-cols-3">
        {COLUMNS.map((statuses, ci) => {
          const list = orders.filter((o) => statuses.includes(o.status));
          return (
            <div key={ci} className="rounded-2xl bg-gray-100/70 p-3">
              <div className="mb-3 flex items-center justify-between px-1"><span className="text-sm font-semibold text-gray-700">{COL_NAME[ci]}</span><span className="rounded-full bg-white px-2 text-xs font-semibold text-gray-500">{list.length}</span></div>
              <div className="space-y-3">
                {list.map((o) => (
                  <Card key={o.id} className="!p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div><div className="font-semibold">{o.id}</div><div className="text-xs text-gray-500">{o.customer.name} · {o.service.name} · {o.bag_size}</div></div>
                      <Pill tone={statusTone(o.status)}>{o.status}</Pill>
                    </div>
                    <div className="mt-2 text-xs text-gray-500">Pickup {slotText(o.pickup_slot)}{o.pickup_request_type === "Live" ? " · LIVE" : ""}</div>
                    {o.latest?.notes && <div className="mt-1 text-xs italic text-gray-500">“{o.latest.notes}”</div>}
                    {o.next_status && (
                      <>
                        <input className={`${inputCls} mt-3 !py-2 text-xs`} placeholder="Note for the customer (optional)" value={notes[o.id] || ""}
                          onChange={(e) => setNotes({ ...notes, [o.id]: e.target.value })} />
                        {o.can_advance ? (
                          <Button variant="primary" className="mt-2 w-full !py-2" loading={a.isBusy("advance_status", { order_id: o.id, notes: notes[o.id] || null })}
                            onClick={() => a.run("advance_status", { order_id: o.id, notes: notes[o.id] || null }, (r) => { setNotes({ ...notes, [o.id]: "" }); return `${o.id} is now ${r.status}${r.status === "Delivered" ? ` — ${o.customer.name} earned loyalty points` : ""}.`; })}>
                            Mark “{o.next_status}” <ArrowRight className="h-4 w-4" /></Button>
                        ) : (
                          <div className="mt-2 flex items-center gap-1.5 rounded-lg bg-gray-50 px-2.5 py-2 text-xs text-gray-500"><Lock className="h-3.5 w-3.5" />Needs {o.needed_role.replace(/([a-z])([A-Z])/g, "$1 $2")} to mark “{o.next_status}”</div>
                        )}
                      </>
                    )}
                    {o.can_cancel && (
                      <Button variant="danger" className="mt-2 w-full !py-2" icon={XCircle} loading={a.isBusy("cancel_order", { order_id: o.id })}
                        onClick={() => a.run("cancel_order", { order_id: o.id }, `${o.id} cancelled and ${money(o.price.final_total)} refunded.`)}>Cancel & refund</Button>
                    )}
                  </Card>
                ))}
                {!list.length && <p className="px-1 py-4 text-center text-xs text-gray-400">Nothing here</p>}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
