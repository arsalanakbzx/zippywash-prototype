// Guided demo: a floating panel that walks the 15-minute presentation story, one use case at a time.
import React from "react";
import { ChevronLeft, ChevronRight, PlayCircle, RotateCcw, X } from "lucide-react";
import { useApp } from "./App.jsx";

const STEPS = [
  { uc: "Intro", title: "Meet ZippyWash", where: ["book", { role: "customer", customerId: "CUS-LEA" }],
    say: "Laundry pickup and delivery in Montréal. The whole order system — 25 classes from our Milestone 5 design — runs live in this browser.",
    do: ["We're signed in as Léa, a loyalty member with 420 points."] },
  { uc: "UC01", title: "Book a pickup", where: ["book", { role: "customer", customerId: "CUS-LEA" }],
    say: "A customer picks a service, bag size and saved addresses, then chooses times that still have capacity.",
    do: ["Choose Wash & Fold, Large bag", "Continue → pick a pickup and a delivery time", "Continue to Review — see GST + QST computed"] },
  { uc: "UC07", title: "Reserve a reward", where: ["book", { role: "customer", customerId: "CUS-LEA" }],
    say: "Points are only reserved at checkout — not spent — until payment succeeds.",
    do: ["Open “Apply promotion or reward”", "Use a loyalty reward → Free Small Bag → Apply", "Point out: 250 reserved, 170 available"] },
  { uc: "UC05", title: "Payment fails → points restored", where: ["book", { role: "customer", customerId: "CUS-LEA" }],
    say: "Alternate flow: the bank declines. Nothing is booked, no slot is taken, and the reserved points come back automatically.",
    do: ["Continue to Payment", "Pick the Mastercard (bank declines it) → Pay", "Points Restored screen appears"] },
  { uc: "UC05", title: "Retry → redeemed & confirmed", where: ["book", { role: "customer", customerId: "CUS-LEA" }],
    say: "Main flow: authorization turns the reservation into a redemption and confirms the booking.",
    do: ["Return to Checkout → apply the reward again", "Pay with Visa → Reward Redeemed", "Continue to Confirmation — note the order ID"] },
  { uc: "UC02", title: "Track the order", where: ["orders", { role: "customer", customerId: "CUS-LEA" }],
    say: "Customers see a read-only timeline. Only staff can change a status.",
    do: ["Open the new order — status Scheduled", "Open the Washing order to show notes from staff"] },
  { uc: "UC02", title: "Staff update the status", where: ["board", { role: "staff", staffId: "STF-DRV1" }],
    say: "Each stage needs the right role: the driver marks Picked Up, laundry staff handle washing. Delivered earns points.",
    do: ["As Marc (driver): Mark “Picked Up” on the new order", "Show the locked button that needs Laundry Staff", "Switch to Léa → My Orders: the update is there"] },
  { uc: "UC04", title: "Plan the driver's route", where: ["routes", { role: "staff", staffId: "STF-DRV1" }],
    say: "A shift becomes a route: orders in the sector are pulled in, capacity is checked, stops are ordered.",
    do: ["Build route from Marc's shift", "Optimize → distance and order update", "Finalize → mark a stop Done"] },
  { uc: "UC03", title: "A machine breaks", where: ["machines", { role: "staff", staffId: "STF-LDY1" }],
    say: "Resources drive capacity: when a washer goes down, every upcoming slot can take fewer bookings.",
    do: ["As Sofia: report a fault on MCH-W1", "Watch the slot capacity bars drop", "Schedule repair → Mark repaired → capacity back"] },
  { uc: "UC03", title: "Low stock alert", where: ["inventory", { role: "staff", staffId: "STF-LDY1" }],
    say: "Every supply movement is recorded; reaching the reorder level opens an alert.",
    do: ["Fabric softener: use 4", "Low-stock banner appears", "Receive 20 → alert clears"] },
  { uc: "UC06", title: "Manage profile & history", where: ["profile", { role: "customer", customerId: "CUS-LEA" }],
    say: "Customers keep their details, addresses and cards up to date, and can rebook from history.",
    do: ["Add an address with postal code J4H 1A1 → flagged outside the area", "Notifications list shows every confirmation", "Order history → a delivered order → Book again"] },
  { uc: "Wrap-up", title: "Admin & close", where: ["admin", { role: "staff", staffId: "STF-ADM1" }],
    say: "Admins correct balances and switch rewards and promo codes. Built on our M5 classes, M6 screens, 170+ automated tests.",
    do: ["Show Léa's balance after the redemption", "Reset sample data before the next run"] },
];

export default function DemoGuide() {
  const { guide, setGuide, go, reset } = useApp();
  if (!guide.open) {
    return (
      <button onClick={() => setGuide({ ...guide, open: true })}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-gray-900 px-4 py-3 text-sm font-semibold text-white shadow-xl transition hover:bg-gray-800">
        <PlayCircle className="h-5 w-5" />Guided demo
      </button>
    );
  }
  const i = guide.step;
  const s = STEPS[i];
  const set = (n) => setGuide({ open: true, step: Math.max(0, Math.min(STEPS.length - 1, n)) });
  return (
    <div className="fade-in fixed inset-x-3 bottom-3 z-40 rounded-2xl border border-gray-200 bg-white shadow-2xl sm:inset-x-auto sm:bottom-5 sm:right-5 sm:w-[380px]">
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <span className="rounded-md bg-brand-600 px-2 py-0.5 text-[11px] font-bold text-white">{s.uc}</span>
        <span className="flex-1 truncate text-sm font-semibold">{s.title}</span>
        <span className="text-xs text-gray-400">{i + 1}/{STEPS.length}</span>
        <button onClick={() => setGuide({ ...guide, open: false })} className="rounded-lg p-1 text-gray-400 hover:bg-gray-100" aria-label="Close guide"><X className="h-4 w-4" /></button>
      </div>
      <div className="h-1 bg-gray-100"><div className="h-full bg-brand-600 transition-all" style={{ width: `${((i + 1) / STEPS.length) * 100}%` }} /></div>
      <div className="max-h-[45vh] overflow-y-auto px-4 py-3">
        <p className="text-sm text-gray-700">{s.say}</p>
        <ol className="mt-3 space-y-1.5">
          {s.do.map((d, k) => <li key={k} className="flex gap-2 text-sm"><span className="mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-brand-50 text-[11px] font-bold text-brand-700">{k + 1}</span><span className="text-gray-600">{d}</span></li>)}
        </ol>
      </div>
      <div className="flex items-center gap-2 border-t border-gray-100 px-4 py-3">
        <button onClick={() => set(i - 1)} disabled={i === 0} className="rounded-lg border border-gray-200 p-2 disabled:opacity-30" aria-label="Previous"><ChevronLeft className="h-4 w-4" /></button>
        <button onClick={() => go(...s.where)} className="flex-1 rounded-lg bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-100">Take me there</button>
        {i === STEPS.length - 1
          ? <button onClick={async () => { await reset(); set(0); go(...STEPS[0].where); }} className="flex items-center gap-1.5 rounded-lg bg-gray-900 px-3 py-2 text-sm font-semibold text-white"><RotateCcw className="h-4 w-4" />Reset</button>
          : <button onClick={() => { set(i + 1); go(...STEPS[i + 1].where); }} className="flex items-center gap-1 rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white">Next<ChevronRight className="h-4 w-4" /></button>}
      </div>
    </div>
  );
}
