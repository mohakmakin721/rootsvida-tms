import Link from "next/link";

import { getMe, listPermissions, listRoles, listUsers } from "@/lib/api";
import type { CurrentUser, Permission, Role } from "@/lib/types";

import { UsersAdmin } from "./users-admin";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const me = await getMe();
  let users: CurrentUser[] = [];
  let roles: Role[] = [];
  let permissions: Permission[] = [];
  let denied = false;
  try {
    [users, roles, permissions] = await Promise.all([
      listUsers(),
      listRoles(),
      listPermissions(),
    ]);
  } catch {
    denied = true; // the API returns 403 to callers without users.manage
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
        ← RootsVida TMS
      </Link>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">Users &amp; roles</h1>
      <p className="mt-1 border-b border-neutral-200 pb-5 text-sm text-neutral-600">
        Add teammates and set their role. Create roles and choose exactly which
        permissions each one grants — who can change pricing, issue quotes, invoice,
        and see margins.
      </p>

      {denied ? (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          You need the <b>Manage users &amp; roles</b> permission to see this page.
        </div>
      ) : (
        <div className="mt-6">
          <UsersAdmin
            initialUsers={users}
            initialRoles={roles}
            permissionCatalog={permissions}
            meId={me?.id ?? null}
          />
        </div>
      )}
    </main>
  );
}
