// UC07 administrator side: point corrections, rewards and promo codes.
import React, { useState } from "react";
import { Lock } from "lucide-react";
import { useApp } from "../App.jsx";
import { Banner, Button, Card, ErrorText, Field, Loading, PageTitle, Pill, inputCls, money, useApi } from "../ui.jsx";
import { useStaffAction } from "./common.jsx";

export default function Admin() {
  const { staffId, people } = useApp();
  const me = people.staff.find((s) => s.id === staffId);
  const isAdmin = me.roles.includes("Administrator");
  const q = useApi("loyalty_admin", { staff_id: staffId });
  const [data, setData] = useState(null);
  const a = useStaffAction((r) => setData(r));
  const [f, setF] = useState({ account_id: "", points: "50", reason: "" });
  if (!q.data && !data) return <><PageTitle title="Loyalty admin" /><Loading /></>;
  const d = data || q.data;
  const acct = f.account_id || d.accounts[0]?.id;
  return (
    <>
      <PageTitle title="Loyalty admin" subtitle="Correct point balances and turn rewards and promo codes on or off." />
      {!isAdmin && <Banner tone="amber" title="View only">Only an administrator can make changes here. Switch to Admin in the account menu.</Banner>}
      {a.msg && <Banner tone="success" title={a.msg} />}
      <ErrorText>{a.err}</ErrorText>
      <div className="mt-3 grid gap-5 lg:grid-cols-2">
        <Card title="Member balances">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs uppercase tracking-wide text-gray-400"><th className="pb-2 font-semibold">Customer</th><th className="pb-2 text-right font-semibold">Balance</th><th className="pb-2 text-right font-semibold">Reserved</th><th className="pb-2 text-right font-semibold">Available</th></tr></thead>
            <tbody className="divide-y divide-gray-100">
              {d.accounts.map((x) => <tr key={x.id}><td className="py-2.5 font-medium">{x.customer}</td><td className="text-right">{x.balance}</td><td className="text-right text-violet-700">{x.reserved}</td><td className="text-right font-semibold">{x.available}</td></tr>)}
            </tbody>
          </table>
          <div className="mt-5 rounded-xl bg-gray-50 p-3.5">
            <div className="mb-3 text-sm font-semibold">Correct points</div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Member"><select className={inputCls} value={acct} onChange={(e) => setF({ ...f, account_id: e.target.value })}>{d.accounts.map((x) => <option key={x.id} value={x.id}>{x.customer}</option>)}</select></Field>
              <Field label="Points (+/−)"><input type="number" className={inputCls} value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} /></Field>
            </div>
            <div className="mt-3"><Field label="Reason (required)"><input className={inputCls} placeholder="e.g. Goodwill for a late delivery" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field></div>
            <Button variant="primary" className="mt-3" disabled={!isAdmin} icon={isAdmin ? null : Lock}
              onClick={() => a.run("correct_points", { account_id: acct, points: f.points, reason: f.reason }, `Correction of ${f.points} points recorded.`).then((r) => r && setF({ ...f, reason: "" }))}>Record correction</Button>
          </div>
        </Card>
        <div className="space-y-5">
          <Card title="Rewards">
            <ul className="divide-y divide-gray-100">
              {d.rewards.map((r) => (
                <li key={r.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <span className="flex-1"><b>{r.name}</b><span className="block text-xs text-gray-500">{r.points} pts · {money(r.discount)} off</span></span>
                  <Pill tone={r.active ? "success" : "grey"}>{r.active ? "Active" : "Off"}</Pill>
                  <Button variant="ghost" className="!px-3 !py-1.5 text-xs" disabled={!isAdmin} onClick={() => a.run("toggle_reward", { reward_id: r.id }, `${r.name} turned ${r.active ? "off" : "on"}.`)}>{r.active ? "Turn off" : "Turn on"}</Button>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Promo codes">
            <ul className="divide-y divide-gray-100">
              {d.promotions.map((p) => (
                <li key={p.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <span className="flex-1"><b className="font-mono">{p.code}</b><span className="block text-xs text-gray-500">{money(p.discount)} off{p.expires ? ` · expires ${p.expires}` : ""}</span></span>
                  <Pill tone={p.active ? "success" : "grey"}>{p.active ? "Active" : "Off"}</Pill>
                  <Button variant="ghost" className="!px-3 !py-1.5 text-xs" disabled={!isAdmin} onClick={() => a.run("toggle_promotion", { promotion_id: p.id }, `${p.code} turned ${p.active ? "off" : "on"}.`)}>{p.active ? "Turn off" : "Turn on"}</Button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
