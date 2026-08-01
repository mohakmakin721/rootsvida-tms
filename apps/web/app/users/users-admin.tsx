"use client";

import { useState } from "react";

import type { CurrentUser } from "@/lib/types";

const ROLES = ["owner", "ops_manager", "sales", "accounts", "readonly"];

const ROLE_HELP: Record<string, string> = {
  owner: "Full access, incl. managing users",
  ops_manager: "Pricing, issuing quotes, invoicing, costing",
  sales: "Build itineraries, price & send proposals",
  accounts: "Invoicing & credit notes",
  readonly: "View only",
};

const inputCls =
  "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none";

export function UsersAdmin({
  initialUsers,
  meId,
}: {
  initialUsers: CurrentUser[];
  meId: string | null;
}) {
  const [users, setUsers] = useState<CurrentUser[]>(initialUsers);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ email: "", password: "", name: "", role: "readonly" });

  async function refresh() {
    const res = await fetch("/api/v1/auth/users", { cache: "no-store" });
    if (res.ok) setUsers((await res.json()) as CurrentUser[]);
  }

  async function addUser() {
    if (!draft.email.trim() || draft.password.length < 6) {
      setError("Enter an email and a password of at least 6 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/auth/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: draft.email.trim(),
          password: draft.password,
          name: draft.name.trim() || null,
          role: draft.role,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setError(typeof d?.detail === "string" ? d.detail : `Could not add user (${res.status}).`);
      } else {
        await refresh();
        setDraft({ email: "", password: "", name: "", role: "readonly" });
      }
    } finally {
      setBusy(false);
    }
  }

  async function patchUser(id: string, patch: { role?: string; is_active?: boolean }) {
    setError(null);
    const res = await fetch(`/api/v1/auth/users/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (res.ok) {
      const updated = (await res.json()) as CurrentUser;
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)));
    } else {
      const d = await res.json().catch(() => null);
      setError(typeof d?.detail === "string" ? d.detail : `Could not update user (${res.status}).`);
    }
  }

  return (
    <div className="space-y-5">
      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-neutral-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2 font-medium">User</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {users.map((u) => {
              const isSelf = u.id === meId;
              return (
                <tr key={u.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-neutral-900">
                      {u.name || u.email}
                      {isSelf && <span className="ml-2 text-xs text-neutral-400">(you)</span>}
                    </div>
                    {u.name && <div className="text-xs text-neutral-500">{u.email}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className={inputCls}
                      value={u.role}
                      disabled={isSelf}
                      title={isSelf ? "You can't change your own role" : ROLE_HELP[u.role]}
                      onChange={(e) => patchUser(u.id, { role: e.target.value })}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? (
                      <button
                        disabled={isSelf}
                        onClick={() => patchUser(u.id, { is_active: false })}
                        className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700 disabled:opacity-60"
                        title={isSelf ? "You can't deactivate yourself" : "Click to deactivate"}
                      >
                        Active
                      </button>
                    ) : (
                      <button
                        onClick={() => patchUser(u.id, { is_active: true })}
                        className="rounded-full bg-neutral-200 px-2.5 py-0.5 text-xs font-medium text-neutral-500"
                        title="Click to reactivate"
                      >
                        Inactive
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-neutral-800">Add a user</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          <input className={inputCls} placeholder="Email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
          <input className={inputCls} placeholder="Name (optional)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <input className={inputCls} type="password" placeholder="Temporary password (min 6)" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
          <select className={inputCls} value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r} — {ROLE_HELP[r]}</option>
            ))}
          </select>
        </div>
        <button
          onClick={addUser}
          disabled={busy}
          className="mt-3 inline-flex rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add user"}
        </button>
      </div>
    </div>
  );
}
