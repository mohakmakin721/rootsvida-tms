"use client";

import { useState } from "react";

const inputCls =
  "w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none";

export function ChangePasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (next.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }
    if (next !== confirm) {
      setError("New passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/v1/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      if (res.ok) {
        setDone(true);
        setCurrent("");
        setNext("");
        setConfirm("");
      } else {
        const d = await res.json().catch(() => null);
        setError(typeof d?.detail === "string" ? d.detail : `Could not change password (${res.status}).`);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-neutral-800">Change password</h2>
      <label className="block">
        <span className="text-xs text-neutral-500">Current password</span>
        <input type="password" autoComplete="current-password" className={`mt-1 ${inputCls}`} value={current} onChange={(e) => setCurrent(e.target.value)} required />
      </label>
      <label className="block">
        <span className="text-xs text-neutral-500">New password</span>
        <input type="password" autoComplete="new-password" className={`mt-1 ${inputCls}`} value={next} onChange={(e) => setNext(e.target.value)} required />
      </label>
      <label className="block">
        <span className="text-xs text-neutral-500">Confirm new password</span>
        <input type="password" autoComplete="new-password" className={`mt-1 ${inputCls}`} value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
      </label>

      {error && <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {done && <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Password changed.</p>}

      <button type="submit" disabled={busy} className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50">
        {busy ? "Saving…" : "Change password"}
      </button>
    </form>
  );
}
