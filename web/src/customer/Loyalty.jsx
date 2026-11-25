// UC07 Manage Loyalty Rewards — summary, available rewards, activity.
import React, { useState } from "react";
import { Award, Gift, Sparkles } from "lucide-react";
import { useApp } from "../App.jsx";
import { call } from "../py.js";
import { Button, Card, ErrorText, Loading, PageTitle, Pill, Stat, money, useApi, when } from "../ui.jsx";

const TONE = { Earned: "success", Redeemed: "purple", Reserved: "amber", Restored: "info", Correction: "grey", Reversed: "danger", Joined: "info" };

export default function Loyalty() {
  const { customerId, go } = useApp();
  const q = useApi("loyalty", { customer_id: customerId });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  if (!q.data && !q.error) return <><PageTitle title="Loyalty / Rewards" /><Loading /></>;
  const { account, rewards, activity } = q.data;
  const join = async () => {
    setBusy(true); setErr(null);
    try { await call("join_loyalty", { customer_id: customerId }); q.reload(); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  if (!account) {
    return (
      <>
        <PageTitle title="Loyalty / Rewards" subtitle="Earn points on every order and turn them into discounts." />
        <Card>
          <div className="flex flex-col items-center py-10 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-violet-100"><Sparkles className="h-7 w-7 text-violet-600" /></div>
            <div className="mt-4 text-lg font-semibold">Join ZippyWash Rewards</div>
            <p className="mt-1 max-w-sm text-sm text-gray-500">Earn 1 point for every dollar you spend. Use points for free bags and discounts at checkout.</p>
            <Button variant="primary" className="mt-5" loading={busy} onClick={join}>Join for free</Button>
            <ErrorText>{err}</ErrorText>
          </div>
        </Card>
      </>
    );
  }
  return (
    <>
      <PageTitle title="Loyalty / Rewards" subtitle="Your points, the rewards you can use, and every change to your balance." />
      <div className="mb-5 overflow-hidden rounded-2xl bg-gradient-to-br from-brand-600 to-violet-600 p-6 text-white shadow-card">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-sm text-white/80">Available points</div>
            <div className="text-5xl font-bold tracking-tight">{account.available}</div>
            <div className="mt-1 text-sm text-white/80">Member since {account.enrolled} · {account.status}</div>
          </div>
          <Award className="h-14 w-14 text-white/30" />
        </div>
      </div>
      <div className="mb-5 grid grid-cols-3 gap-3">
        <Stat label="Balance" value={account.balance} />
        <Stat label="Reserved" value={account.reserved} tone="text-violet-700" sub="Held for a checkout" />
        <Stat label="Available" value={account.available} tone="text-brand-700" />
      </div>
      <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
        <Card title="Rewards" subtitle="Apply one at checkout, under Review.">
          <div className="space-y-2.5">
            {rewards.map((r) => {
              const ok = account.available >= r.points;
              const pct = Math.min(100, Math.round((account.available / r.points) * 100));
              return (
                <div key={r.id} className="rounded-xl border border-gray-200 p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5"><Gift className={`h-5 w-5 ${ok ? "text-violet-600" : "text-gray-300"}`} /><div><div className="font-semibold">{r.name}</div><div className="text-xs text-gray-500">{r.points} points · {money(r.discount)} off</div></div></div>
                    {ok ? <Pill tone="purple">Eligible</Pill> : <span className="text-xs text-gray-500">{r.points - account.available} more</span>}
                  </div>
                  <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-gray-100"><div className={`h-full rounded-full ${ok ? "bg-violet-500" : "bg-gray-300"}`} style={{ width: `${pct}%` }} /></div>
                </div>
              );
            })}
          </div>
          <Button variant="primary" className="mt-4 w-full" onClick={() => go("book")}>Book & use a reward</Button>
        </Card>
        <Card title="Points activity" subtitle="Most recent first.">
          {activity.length ? (
            <ul className="divide-y divide-gray-100">
              {activity.map((t, i) => (
                <li key={i} className="flex items-center gap-3 py-3">
                  <Pill tone={TONE[t.type] || "grey"}>{t.type}</Pill>
                  <div className="min-w-0 flex-1"><div className="truncate text-sm">{t.details || (t.order ? `Order ${t.order}` : "—")}</div><div className="text-xs text-gray-500">{when(t.at)}</div></div>
                  <Points t={t} />
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-gray-500">No activity yet.</p>}
        </Card>
      </div>
    </>
  );
}

// Reserved points are held (not spent), so they show as "held"; redemptions and reversals are deductions.
function Points({ t }) {
  const n = Math.abs(t.points);
  if (t.type === "Reserved") return <div className="text-sm font-semibold text-amber-600">{n} held</div>;
  if (t.type === "Restored") return <div className="text-sm font-semibold text-teal-700">{n} released</div>;
  const minus = ["Redeemed", "Reversed"].includes(t.type) || t.points < 0;
  return <div className={`text-sm font-semibold ${minus ? "text-red-600" : n ? "text-green-700" : "text-gray-500"}`}>{minus ? "−" : n ? "+" : ""}{n}</div>;
}
