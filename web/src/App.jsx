// App shell: loading screen, top bar (logo, navigation, role and account switch), pages, demo guide.
import React, { createContext, useContext, useEffect, useState } from "react";
import { ChevronDown, PlayCircle, RotateCcw, Users, Wrench } from "lucide-react";
import { call, loadPython } from "./py.js";
import { Button } from "./ui.jsx";
import Booking from "./customer/Booking.jsx";
import Orders from "./customer/Orders.jsx";
import Loyalty from "./customer/Loyalty.jsx";
import Profile from "./customer/Profile.jsx";
import Overview from "./staff/Overview.jsx";
import Board from "./staff/Board.jsx";
import RoutesPage from "./staff/Routes.jsx";
import Machines from "./staff/Machines.jsx";
import Inventory from "./staff/Inventory.jsx";
import Admin from "./staff/Admin.jsx";
import DemoGuide from "./DemoGuide.jsx";

export const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

const CUSTOMER_PAGES = [["book", "Book Pickup"], ["orders", "My Orders"], ["loyalty", "Loyalty / Rewards"], ["profile", "Profile"]];
const STAFF_PAGES = [["overview", "Overview"], ["board", "Order board"], ["routes", "Routes"], ["machines", "Machines"],
                     ["inventory", "Inventory"], ["admin", "Loyalty admin"]];

export function Logo({ size = 36 }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex items-center justify-center rounded-[10px] bg-brand-600" style={{ width: size, height: size }}>
        <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" fill="#fff" /></svg>
      </div>
      <span className="text-lg font-bold tracking-tight">ZippyWash</span>
    </div>
  );
}

function Splash({ text, error }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-5 px-6 text-center">
      <Logo size={48} />
      {error ? <p className="max-w-md text-sm text-red-600">{error}</p> : (
        <>
          <div className="h-1.5 w-56 overflow-hidden rounded-full bg-brand-100"><div className="h-full w-1/3 animate-[slide_1.2s_ease-in-out_infinite] rounded-full bg-brand-600" /></div>
          <p className="text-sm text-gray-500">{text}</p>
          <p className="max-w-sm text-xs text-gray-400">The ZippyWash order system runs right in your browser. The first visit takes a few seconds.</p>
        </>
      )}
      <style>{"@keyframes slide{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}"}</style>
    </div>
  );
}

class Boundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
        <div className="font-semibold">This screen hit a problem.</div>
        <div className="mt-1">{String(this.state.error.message || this.state.error)}</div>
        <button className="mt-3 rounded-lg bg-white px-3 py-1.5 font-semibold text-red-700 ring-1 ring-red-200" onClick={() => this.setState({ error: null })}>Try again</button>
      </div>
    );
  }
}

function initials(name = "") {
  return name.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState("Starting…");
  const [loadError, setLoadError] = useState(null);
  const [people, setPeople] = useState(null);
  const [role, setRole] = useState("customer");
  const [customerId, setCustomerId] = useState("CUS-LEA");
  const [staffId, setStaffId] = useState("STF-DRV1");
  const [page, setPage] = useState("book");
  const [version, setVersion] = useState(0);          // bump to refresh every page after a reset
  const [checkouts, setCheckouts] = useState({});      // booking wizard state per customer
  const [viewOrder, setViewOrder] = useState({});      // order opened in My Orders, per customer
  const [guide, setGuide] = useState({ open: false, step: 0 });
  const [menu, setMenu] = useState(false);

  useEffect(() => {
    loadPython(setProgress)
      .then(() => call("bootstrap"))
      .then((d) => { setPeople(d); setReady(true); })
      .catch((e) => setLoadError(`The app couldn't start: ${e.message}. Try reloading the page.`));
  }, []);

  if (!ready) return <Splash text={progress} error={loadError} />;

  const pages = role === "customer" ? CUSTOMER_PAGES : STAFF_PAGES;
  const me = role === "customer" ? people.customers.find((c) => c.id === customerId) : people.staff.find((s) => s.id === staffId);

  const ctx = {
    role, customerId, staffId, version, people,
    go: (p, opts = {}) => {
      if (opts.role) setRole(opts.role);
      if (opts.customerId) setCustomerId(opts.customerId);
      if (opts.staffId) setStaffId(opts.staffId);
      setPage(p);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    checkout: checkouts[customerId] || { step: "details" },
    setCheckout: (next) => setCheckouts((all) => ({ ...all, [customerId]: typeof next === "function" ? next(all[customerId] || { step: "details" }) : next })),
    openOrder: viewOrder[customerId] || null,
    setOpenOrder: (id) => setViewOrder((all) => ({ ...all, [customerId]: id })),
    reset: async () => {
      const d = await call("reset");
      setPeople(d); setCheckouts({}); setViewOrder({}); setVersion((v) => v + 1);
    },
    refresh: () => setVersion((v) => v + 1),
    guide, setGuide,
  };

  const switchRole = (r) => { setRole(r); setPage(r === "customer" ? "book" : "overview"); setMenu(false); };
  const PageEl = { book: Booking, orders: Orders, loyalty: Loyalty, profile: Profile, overview: Overview, board: Board,
                   routes: RoutesPage, machines: Machines, inventory: Inventory, admin: Admin }[page];

  return (
    <AppCtx.Provider value={ctx}>
      <header className="sticky top-0 z-30 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
          <button onClick={() => ctx.go(role === "customer" ? "book" : "overview")}><Logo /></button>
          <nav className="hidden flex-1 justify-center gap-1 md:flex">
            {pages.map(([id, label]) => (
              <button key={id} onClick={() => ctx.go(id)}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${page === id ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"}`}>
                {label}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 md:ml-0">
            <Button variant="ghost" className="hidden px-3 sm:inline-flex" icon={PlayCircle}
              onClick={() => setGuide((g) => ({ ...g, open: !g.open }))}>Demo</Button>
            <div className="relative">
              <button onClick={() => setMenu(!menu)} className="flex items-center gap-2 rounded-xl border border-gray-200 py-1.5 pl-1.5 pr-2.5 hover:bg-gray-50">
                <span className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${role === "customer" ? "bg-brand-100 text-brand-700" : "bg-amber-100 text-amber-700"}`}>{initials(me?.name)}</span>
                <span className="hidden text-left sm:block">
                  <span className="block text-sm font-semibold leading-tight">{me?.name.split(" ")[0]}</span>
                  <span className="block text-[11px] leading-tight text-gray-500">{role === "customer" ? "Customer" : me?.roles.join(", ").replace(/([a-z])([A-Z])/g, "$1 $2")}</span>
                </span>
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </button>
              {menu && (
                <div className="fade-in absolute right-0 mt-2 w-72 rounded-2xl border border-gray-200 bg-white p-2 shadow-xl">
                  <div className="grid grid-cols-2 gap-1 rounded-xl bg-gray-100 p-1">
                    {[["customer", "Customer", Users], ["staff", "Staff", Wrench]].map(([r, label, Icon]) => (
                      <button key={r} onClick={() => switchRole(r)} className={`flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-sm font-medium ${role === r ? "bg-white shadow-sm" : "text-gray-500"}`}>
                        <Icon className="h-4 w-4" />{label}
                      </button>
                    ))}
                  </div>
                  <div className="mt-2 px-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Sign in as</div>
                  {(role === "customer" ? people.customers : people.staff).map((p) => (
                    <button key={p.id} onClick={() => { role === "customer" ? setCustomerId(p.id) : setStaffId(p.id); setMenu(false); }}
                      className={`mt-0.5 flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left text-sm hover:bg-gray-50 ${(role === "customer" ? customerId : staffId) === p.id ? "bg-brand-50" : ""}`}>
                      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gray-100 text-[11px] font-semibold text-gray-600">{initials(p.name)}</span>
                      <span className="flex-1">{p.name}<span className="block text-[11px] text-gray-500">{role === "customer" ? (p.active ? "Customer" : "Deactivated") : p.roles.join(", ").replace(/([a-z])([A-Z])/g, "$1 $2")}</span></span>
                    </button>
                  ))}
                  <div className="my-2 border-t border-gray-100" />
                  <button onClick={() => { setGuide({ open: true, step: 0 }); setMenu(false); }} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-50"><PlayCircle className="h-4 w-4 text-brand-600" />Start guided demo</button>
                  <button onClick={async () => { await ctx.reset(); setMenu(false); }} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-gray-50"><RotateCcw className="h-4 w-4 text-gray-500" />Reset sample data</button>
                </div>
              )}
            </div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
          {pages.map(([id, label]) => (
            <button key={id} onClick={() => ctx.go(id)} className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${page === id ? "bg-brand-50 text-brand-700" : "text-gray-600"}`}>{label}</button>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 pb-24 pt-7 sm:px-6" onClick={() => menu && setMenu(false)}>
        <div key={`${page}-${role}-${customerId}-${staffId}-${version}`} className="fade-in"><Boundary><PageEl /></Boundary></div>
      </main>
      <footer className="border-t border-gray-200 py-6 text-center text-xs text-gray-400">
        ZippyWash · BTM 495 Team 5 final prototype · Sample data only, no real payments ·{" "}
        <a className="underline" href="https://github.com/arsalanakbzx/zippywash-prototype">Source code</a>
      </footer>
      <DemoGuide />
    </AppCtx.Provider>
  );
}
