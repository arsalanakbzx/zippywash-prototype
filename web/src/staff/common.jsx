import { useState } from "react";
import { useApp } from "../App.jsx";
import { call } from "../py.js";

// Runs one staff action and keeps the busy flag, error and a short success message.
export function useStaffAction(onData) {
  const { staffId } = useApp();
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const run = async (name, payload, success) => {
    setBusy(name + JSON.stringify(payload)); setErr(null); setMsg(null);
    try {
      const r = await call(name, { staff_id: staffId, ...payload });
      onData?.(r);
      if (success) setMsg(typeof success === "function" ? success(r) : success);
      return r;
    } catch (e) { setErr(e.message); return null; } finally { setBusy(null); }
  };
  const isBusy = (name, payload) => busy === name + JSON.stringify(payload);
  return { run, busy, isBusy, err, msg, setErr };
}
