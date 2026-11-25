// Shared visual components in the Milestone 6 style (presentation only, no business rules).
import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, Check, CheckCircle2, Info, Loader2, RotateCcw, Sparkles } from "lucide-react";
import { call } from "./py.js";

export const money = (v) => (v == null ? "—" : `$${Number(v).toFixed(2)}`);
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function day(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return `${DAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}
export function clock(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}
export const slotText = (s) => (s ? `${day(s.date)} · ${clock(s.start)}` : "—");
export function when(isoDateTime) {
  if (!isoDateTime) return "—";
  const [d, t] = isoDateTime.split("T");
  return `${day(d)} · ${clock(t.slice(0, 5))}`;
}

// ---------- data hook ----------
export function useApi(name, payload, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true, forKey: null });
  const key = JSON.stringify(payload);
  const fullKey = JSON.stringify([name, key, deps]);
  const load = useCallback(() => {
    if (!name) return;
    setState((s) => ({ ...s, loading: true }));
    call(name, payload)
      .then((data) => setState({ data, error: null, loading: false, forKey: fullKey }))
      .catch((e) => setState({ data: null, error: e.message, loading: false, forKey: fullKey }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullKey]);
  useEffect(load, [load]);
  // Data loaded for different inputs counts as still loading, so a screen never renders stale data.
  const stale = state.forKey !== fullKey;
  return { data: stale ? null : state.data, error: stale ? null : state.error, loading: state.loading || stale, reload: load };
}

// ---------- layout ----------
export function PageTitle({ title, subtitle, right }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Card({ title, subtitle, right, children, className = "", pad = true }) {
  return (
    <section className={`rounded-2xl border border-gray-200 bg-white shadow-card ${pad ? "p-5 sm:p-6" : ""} ${className}`}>
      {(title || right) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-[15px] font-semibold text-gray-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Button({ children, variant = "secondary", className = "", loading, icon: Icon, ...props }) {
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm disabled:bg-brand-200",
    secondary: "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 disabled:text-gray-300",
    ghost: "text-gray-600 hover:bg-gray-100",
    danger: "bg-white text-red-600 border border-red-200 hover:bg-red-50",
  };
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

const PILL = {
  info: "bg-brand-100 text-brand-700", success: "bg-green-100 text-green-700", danger: "bg-red-100 text-red-700",
  amber: "bg-amber-100 text-amber-700", purple: "bg-violet-100 text-violet-700", grey: "bg-gray-100 text-gray-600",
};
export function Pill({ children, tone = "grey" }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${PILL[tone]}`}>{children}</span>;
}
export const STATUS_TONE = { Scheduled: "info", Delivered: "success", Cancelled: "danger", Draft: "grey" };
export const statusTone = (s) => STATUS_TONE[s] || "amber";

const BANNER = {
  success: ["bg-green-50 border-green-200", "bg-green-600", CheckCircle2],
  danger: ["bg-red-50 border-red-200", "bg-red-600", AlertCircle],
  purple: ["bg-violet-50 border-violet-200", "bg-violet-600", Sparkles],
  info: ["bg-brand-50 border-brand-200", "bg-brand-600", Info],
  amber: ["bg-amber-50 border-amber-200", "bg-amber-500", Info],
  restored: ["bg-teal-50 border-teal-200", "bg-teal-600", RotateCcw],
};
export function Banner({ tone = "info", title, children, pill, pillTone }) {
  const [bg, icBg, Icon] = BANNER[tone];
  return (
    <div className={`fade-in mb-5 flex items-center gap-4 rounded-2xl border px-5 py-4 ${bg}`}>
      <div className={`flex h-10 w-10 flex-none items-center justify-center rounded-full text-white ${icBg}`}><Icon className="h-5 w-5" /></div>
      <div className="min-w-0 flex-1">
        <div className="font-semibold text-gray-900">{title}</div>
        {children && <div className="text-sm text-gray-600">{children}</div>}
      </div>
      {pill && <Pill tone={pillTone || (tone === "restored" ? "success" : tone)}>{pill}</Pill>}
    </div>
  );
}

export function Stepper({ steps, current, done = false, small = false }) {
  return (
    <ol className={`flex w-full items-start ${small ? "my-2" : "mb-7 mt-1"}`}>
      {steps.map((label, i) => {
        const state = done || i < current ? "done" : i === current ? "now" : "todo";
        return (
          <li key={label} className="relative flex flex-1 flex-col items-center text-center">
            {i > 0 && <span className={`absolute right-1/2 ${small ? "top-[9px]" : "top-[13px]"} h-0.5 w-full ${state === "todo" ? "bg-gray-200" : "bg-brand-600"}`} />}
            <span className={`relative z-10 flex items-center justify-center rounded-full border-2 font-semibold ${small ? "h-5 w-5 text-[10px]" : "h-7 w-7 text-xs"} ${
              state === "done" ? "border-brand-600 bg-brand-600 text-white" : state === "now" ? "border-brand-200 bg-brand-600 text-white ring-4 ring-brand-100" : "border-gray-300 bg-white text-gray-400"}`}>
              {state === "done" ? <Check className={small ? "h-3 w-3" : "h-3.5 w-3.5"} /> : i + 1}
            </span>
            <span className={`mt-1.5 px-0.5 leading-tight ${small ? "text-[10px]" : "text-xs"} ${state === "now" ? "font-semibold text-gray-900" : "text-gray-500"}`}>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function KV({ rows, total, totalLabel }) {
  return (
    <dl className="text-sm">
      {rows.filter(Boolean).map(([k, v, cls]) => (
        <div key={k} className="flex justify-between gap-4 py-1.5">
          <dt className="text-gray-500">{k}</dt>
          <dd className={`text-right font-medium text-gray-900 ${cls || ""}`}>{v}</dd>
        </div>
      ))}
      {total != null && (
        <div className="mt-2 flex items-baseline justify-between border-t border-gray-200 pt-3">
          <dt className="font-semibold text-gray-900">{totalLabel}</dt>
          <dd className="text-2xl font-bold text-gray-900">{total}</dd>
        </div>
      )}
    </dl>
  );
}

export function Note({ children, tone = "grey" }) {
  const t = { grey: "bg-gray-50 border-gray-100 text-gray-600", info: "bg-brand-50 border-brand-100 text-brand-700" }[tone];
  return <div className={`rounded-xl border px-3.5 py-2.5 text-sm ${t}`}>{children}</div>;
}

export function ErrorText({ children }) {
  if (!children) return null;
  return <p className="fade-in mt-3 flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700"><AlertCircle className="mt-0.5 h-4 w-4 flex-none" />{children}</p>;
}

export function Loading({ label = "Loading…" }) {
  return <div className="flex items-center gap-2 py-10 text-sm text-gray-500"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>;
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-gray-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-gray-500">{hint}</span>}
    </label>
  );
}
export const inputCls = "w-full rounded-xl border border-gray-300 bg-white px-3.5 py-2.5 text-sm text-gray-900 shadow-sm outline-none transition focus:border-brand-500 focus:ring-4 focus:ring-brand-100";

export function Choice({ options, value, onChange, columns = 1, render }) {
  return (
    <div className={`grid gap-2 ${columns === 2 ? "sm:grid-cols-2" : columns === 3 ? "grid-cols-3" : ""}`}>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button type="button" key={o.value} disabled={o.disabled} onClick={() => onChange(o.value)}
            className={`flex items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left text-sm transition ${
              o.disabled ? "cursor-not-allowed border-gray-100 bg-gray-50 text-gray-400" :
              selected ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600" : "border-gray-200 bg-white hover:border-gray-300"}`}>
            <span className={`flex h-4 w-4 flex-none items-center justify-center rounded-full border ${selected ? "border-brand-600" : "border-gray-300"}`}>
              {selected && <span className="h-2 w-2 rounded-full bg-brand-600" />}
            </span>
            <span className="min-w-0 flex-1">{render ? render(o) : o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Stat({ label, value, tone = "text-gray-900", sub }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-card">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tone}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}
