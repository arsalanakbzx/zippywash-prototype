// UC03 Manage Laundry Resources: machine faults and repairs, and how they change time-slot capacity.
import React, { useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, Wrench } from "lucide-react";
import { useApp } from "../App.jsx";
import { Banner, Button, Card, ErrorText, Loading, Note, PageTitle, Pill, inputCls, slotText, useApi } from "../ui.jsx";
import { useStaffAction } from "./common.jsx";

const M_TONE = { Operational: "success", Faulty: "danger", UnderMaintenance: "amber", OutOfService: "grey" };
const pretty = (s) => s.replace(/([a-z])([A-Z])/g, "$1 $2");

export default function Machines() {
  const { staffId } = useApp();
  const q = useApi("machines", { staff_id: staffId });
  const [data, setData] = useState(null);
  const a = useStaffAction((r) => setData(r));
  if (!q.data && !data) return <><PageTitle title="Machines" /><Loading /></>;
  const d = data || q.data;
  return (
    <>
      <PageTitle title="Machines" subtitle="Report faults and track repairs. A machine that's down lowers the number of bookings each time slot can take." />
      {a.msg && <Banner tone="success" title={a.msg} />}
      <ErrorText>{a.err}</ErrorText>
      <div className="mt-3 grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-4">{d.machines.map((m) => <MachineCard key={m.id} m={m} a={a} />)}</div>
        <Card title="Upcoming slot capacity" subtitle="Bookings each slot can still take.">
          <ul className="space-y-2.5">
            {d.slots.map((s) => {
              const pct = s.limit ? Math.round((s.available / s.limit) * 100) : 0;
              return (
                <li key={s.id}>
                  <div className="flex justify-between text-sm"><span>{slotText(s)}</span><span className={`font-semibold ${s.available === 0 ? "text-red-600" : ""}`}>{s.available}/{s.limit}</span></div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100"><div className={`h-full rounded-full transition-all ${pct === 0 ? "bg-red-500" : pct < 50 ? "bg-amber-500" : "bg-green-500"}`} style={{ width: `${pct}%` }} /></div>
                </li>
              );
            })}
          </ul>
          <div className="mt-4"><Note>Capacity = working machines × 2 orders per slot, capped by the slot limit. Customers only see slots with room.</Note></div>
        </Card>
      </div>
    </>
  );
}

function MachineCard({ m, a }) {
  const [fault, setFault] = useState("");
  const [details, setDetails] = useState("");
  const rec = m.open_record;
  return (
    <Card title={`${m.id} · ${m.type}`} subtitle={`Capacity ${m.capacity} kg · cycle ${m.cycle || "—"} · ${m.history} past records`} right={<Pill tone={M_TONE[m.status]}>{pretty(m.status)}</Pill>}>
      {!rec && m.status === "Operational" && (
        <div className="flex gap-2">
          <input className={inputCls} placeholder="Describe the fault, e.g. Door won't lock" value={fault} onChange={(e) => setFault(e.target.value)} />
          <Button variant="danger" icon={AlertTriangle} disabled={!fault.trim()} loading={a.isBusy("report_fault", { machine_id: m.id, description: fault })}
            onClick={() => a.run("report_fault", { machine_id: m.id, description: fault }, `Fault reported on ${m.id}. Its slot capacity is now removed.`).then(() => setFault(""))}>Report fault</Button>
        </div>
      )}
      {rec && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5">
          <div className="flex flex-wrap items-center gap-2 text-sm"><Wrench className="h-4 w-4 text-amber-600" /><b>{rec.fault}</b><Pill tone="amber">{pretty(rec.status)}</Pill></div>
          <div className="mt-1 text-xs text-gray-600">{rec.scheduled ? `Repair scheduled ${rec.scheduled}` : "Not scheduled yet"}{rec.managed_by ? ` · ${rec.managed_by}` : ""}{rec.details ? ` · ${rec.details}` : ""}</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {rec.status === "Reported" && <Button icon={CalendarClock} loading={a.isBusy("schedule_repair", { record_id: rec.id })} onClick={() => a.run("schedule_repair", { record_id: rec.id }, "Repair scheduled for today.")}>Schedule repair</Button>}
            {rec.status !== "Reported" && (
              <div className="flex w-full gap-2">
                <input className={inputCls} placeholder="Repair notes, e.g. Replaced door latch" value={details} onChange={(e) => setDetails(e.target.value)} />
                <Button disabled={!details.trim()} onClick={() => a.run("repair_details", { record_id: rec.id, details }, "Repair notes saved.").then(() => setDetails(""))}>Save</Button>
              </div>
            )}
            {rec.status !== "Reported" && <Button variant="primary" icon={CheckCircle2} loading={a.isBusy("complete_repair", { record_id: rec.id })} onClick={() => a.run("complete_repair", { record_id: rec.id }, `${m.id} repaired and back in service. Slot capacity restored.`)}>Mark repaired</Button>}
          </div>
        </div>
      )}
    </Card>
  );
}
