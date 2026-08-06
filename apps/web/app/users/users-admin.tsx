"use client";

import { useMemo, useState } from "react";

import type { CurrentUser, Permission, Role } from "@/lib/types";

const inputCls =
  "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none";
const btnDark =
  "inline-flex rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50";

export function UsersAdmin({
  initialUsers,
  initialRoles,
  permissionCatalog,
  meId,
}: {
  initialUsers: CurrentUser[];
  initialRoles: Role[];
  permissionCatalog: Permission[];
  meId: string | null;
}) {
  const [users, setUsers] = useState<CurrentUser[]>(initialUsers);
  const [roles, setRoles] = useState<Role[]>(initialRoles);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({ email: "", password: "", name: "", role: "readonly" });
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetPw, setResetPw] = useState("");
  const [resetDone, setResetDone] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const roleByKey = useMemo(
    () => Object.fromEntries(roles.map((r) => [r.key, r])),
    [roles],
  );

  async function deleteUser(id: string) {
    setError(null);
    const res = await fetch(`/api/v1/auth/users/${id}`, { method: "DELETE" });
    if (res.ok) {
      setConfirmDelete(null);
      setUsers((prev) => prev.filter((u) => u.id !== id));
    } else {
      const d = await res.json().catch(() => null);
      setError(typeof d?.detail === "string" ? d.detail : `Could not delete user (${res.status}).`);
    }
  }

  async function resetPassword(id: string) {
    if (resetPw.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }
    setError(null);
    const res = await fetch(`/api/v1/auth/users/${id}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: resetPw }),
    });
    if (res.ok) {
      setResetFor(null);
      setResetPw("");
      setResetDone(id);
      setTimeout(() => setResetDone(null), 3000);
    } else {
      const d = await res.json().catch(() => null);
      setError(typeof d?.detail === "string" ? d.detail : `Could not reset password (${res.status}).`);
    }
  }

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
    <div className="space-y-8">
      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section>
        <div className="overflow-hidden rounded-lg border border-neutral-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Role</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium text-right">Password</th>
                <th className="px-4 py-2 font-medium text-right">Delete</th>
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
                        title={
                          isSelf
                            ? "You can't change your own role"
                            : roleByKey[u.role]?.description ?? ""
                        }
                        onChange={(e) => patchUser(u.id, { role: e.target.value })}
                      >
                        {roles.map((r) => (
                          <option key={r.key} value={r.key}>{r.label}</option>
                        ))}
                        {!roleByKey[u.role] && <option value={u.role}>{u.role}</option>}
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
                    <td className="px-4 py-3 text-right">
                      {resetFor === u.id ? (
                        <span className="inline-flex items-center gap-1">
                          <input
                            type="password"
                            autoComplete="new-password"
                            placeholder="New password"
                            className={`${inputCls} w-36`}
                            value={resetPw}
                            onChange={(e) => setResetPw(e.target.value)}
                          />
                          <button onClick={() => resetPassword(u.id)} className="rounded-md bg-neutral-900 px-2 py-1 text-xs font-medium text-white hover:bg-neutral-800">
                            Save
                          </button>
                          <button onClick={() => { setResetFor(null); setResetPw(""); }} className="text-xs text-neutral-400 hover:text-neutral-700">
                            Cancel
                          </button>
                        </span>
                      ) : resetDone === u.id ? (
                        <span className="text-xs text-emerald-600">Reset ✓</span>
                      ) : (
                        <button
                          onClick={() => { setResetFor(u.id); setResetPw(""); }}
                          className="text-xs text-neutral-500 underline hover:text-neutral-800"
                        >
                          Reset password
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isSelf ? (
                        <span className="text-xs text-neutral-300" title="You can't delete yourself">—</span>
                      ) : confirmDelete === u.id ? (
                        <span className="inline-flex items-center gap-1">
                          <button onClick={() => deleteUser(u.id)} className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700">
                            Delete
                          </button>
                          <button onClick={() => setConfirmDelete(null)} className="text-xs text-neutral-400 hover:text-neutral-700">
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(u.id)}
                          className="text-xs text-neutral-400 underline hover:text-red-600"
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="mt-4 rounded-lg border border-neutral-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-neutral-800">Add a user</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <input className={inputCls} placeholder="Email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            <input className={inputCls} placeholder="Name (optional)" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            <input className={inputCls} type="password" placeholder="Temporary password (min 6)" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
            <select className={inputCls} value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })}>
              {roles.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
          </div>
          <button onClick={addUser} disabled={busy} className={`mt-3 ${btnDark}`}>
            {busy ? "Adding…" : "Add user"}
          </button>
        </div>
      </section>

      <RolesManager
        roles={roles}
        setRoles={setRoles}
        catalog={permissionCatalog}
        onError={setError}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------- //
// Roles & permissions
// ---------------------------------------------------------------------------- //

function RolesManager({
  roles,
  setRoles,
  catalog,
  onError,
}: {
  roles: Role[];
  setRoles: React.Dispatch<React.SetStateAction<Role[]>>;
  catalog: Permission[];
  onError: (msg: string | null) => void;
}) {
  const [creating, setCreating] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newPerms, setNewPerms] = useState<string[]>([]);

  const groups = useMemo(() => {
    const g: Record<string, Permission[]> = {};
    for (const p of catalog) (g[p.group] ??= []).push(p);
    return g;
  }, [catalog]);

  async function patchRole(id: string, patch: { label?: string; permissions?: string[] }) {
    onError(null);
    const res = await fetch(`/api/v1/roles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (res.ok) {
      const updated = (await res.json()) as Role;
      setRoles((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } else {
      const d = await res.json().catch(() => null);
      onError(typeof d?.detail === "string" ? d.detail : `Could not update role (${res.status}).`);
    }
  }

  function togglePerm(role: Role, key: string) {
    // The owner role must keep every permission — the server enforces it too.
    if (role.key === "owner") return;
    const has = role.permissions.includes(key);
    const next = has
      ? role.permissions.filter((p) => p !== key)
      : [...role.permissions, key];
    patchRole(role.id, { permissions: next });
  }

  async function deleteRole(role: Role) {
    onError(null);
    const res = await fetch(`/api/v1/roles/${role.id}`, { method: "DELETE" });
    if (res.ok) {
      setRoles((prev) => prev.filter((r) => r.id !== role.id));
    } else {
      const d = await res.json().catch(() => null);
      onError(typeof d?.detail === "string" ? d.detail : `Could not delete role (${res.status}).`);
    }
  }

  async function createRole() {
    if (!newLabel.trim()) {
      onError("Give the new role a name.");
      return;
    }
    onError(null);
    const res = await fetch("/api/v1/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel.trim(), permissions: newPerms }),
    });
    if (res.ok) {
      const role = (await res.json()) as Role;
      setRoles((prev) => [...prev, role]);
      setCreating(false);
      setNewLabel("");
      setNewPerms([]);
    } else {
      const d = await res.json().catch(() => null);
      onError(typeof d?.detail === "string" ? d.detail : `Could not create role (${res.status}).`);
    }
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-neutral-800">Roles &amp; permissions</h2>
          <p className="text-xs text-neutral-500">
            Click a role’s name to rename it; tick a permission to grant it. The Owner
            role always keeps every permission. Built-in roles can be renamed and
            re-scoped but not deleted; custom roles can also be deleted.
          </p>
        </div>
        <button onClick={() => setCreating((c) => !c)} className={btnDark}>
          {creating ? "Cancel" : "+ New role"}
        </button>
      </div>

      {creating && (
        <div className="mb-4 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
          <input
            className={`${inputCls} mb-2 w-full`}
            placeholder="Role name (e.g. Reservations)"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
          />
          <div className="grid gap-1 sm:grid-cols-2">
            {catalog.map((p) => (
              <label key={p.key} className="flex items-start gap-2 text-xs text-neutral-700">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={newPerms.includes(p.key)}
                  onChange={(e) =>
                    setNewPerms((prev) =>
                      e.target.checked ? [...prev, p.key] : prev.filter((k) => k !== p.key),
                    )
                  }
                />
                <span><b>{p.label}</b> — {p.description}</span>
              </label>
            ))}
          </div>
          <button onClick={createRole} className={`mt-3 ${btnDark}`}>Create role</button>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-neutral-200">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2 font-medium">Role</th>
              {Object.entries(groups).map(([group, perms]) =>
                perms.map((p) => (
                  <th key={p.key} className="px-2 py-2 text-center font-medium" title={`${group} · ${p.description}`}>
                    {p.label}
                  </th>
                )),
              )}
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {roles.map((role) => (
              <tr key={role.id} className="hover:bg-neutral-50">
                <td className="px-4 py-3 align-top">
                  <div className="flex items-center gap-1">
                    <EditableLabel
                      value={role.label}
                      onSave={(label) => patchRole(role.id, { label })}
                    />
                    {role.is_system && <span className="text-[10px] uppercase text-neutral-400">built-in</span>}
                  </div>
                  <div className="text-xs text-neutral-500">
                    {role.user_count} {role.user_count === 1 ? "user" : "users"}
                  </div>
                </td>
                {catalog.map((p) => {
                  const on = role.permissions.includes(p.key);
                  const locked = role.key === "owner";
                  return (
                    <td key={p.key} className="px-2 py-3 text-center align-top">
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={locked}
                        title={locked ? "The owner role always has every permission" : undefined}
                        onChange={() => togglePerm(role, p.key)}
                      />
                    </td>
                  );
                })}
                <td className="px-3 py-3 text-right align-top">
                  {!role.is_system && (
                    <button
                      onClick={() => deleteRole(role)}
                      className="text-xs text-neutral-400 underline hover:text-red-600"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** An inline-editable role name: type to rename, saves on Enter or blur. */
function EditableLabel({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [draft, setDraft] = useState(value);
  // Keep in sync when the parent value changes (e.g. after a refresh).
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setDraft(value);
  }
  function commit() {
    const next = draft.trim();
    if (next && next !== value) onSave(next);
    else setDraft(value);
  }
  return (
    <input
      className="w-40 rounded border border-transparent bg-transparent px-1 py-0.5 text-sm font-medium text-neutral-900 hover:border-neutral-200 focus:border-neutral-400 focus:bg-white focus:outline-none"
      value={draft}
      title="Click to rename this role"
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") { setDraft(value); e.currentTarget.blur(); }
      }}
    />
  );
}
