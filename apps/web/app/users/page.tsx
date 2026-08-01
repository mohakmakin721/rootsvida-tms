import Link from "next/link";

import { getMe, listUsers } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";

import { UsersAdmin } from "./users-admin";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const me = await getMe();
  let users: CurrentUser[] = [];
  let denied = false;
  try {
    users = await listUsers();
  } catch {
    denied = true; // the API returns 403 to non-owners
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
        ← RootsVida TMS
      </Link>
      <h1 className="mt-1 text-2xl font-semibold">Users</h1>
      <p className="mt-1 text-sm text-neutral-600">
        Add teammates and set their role. Roles decide who can change pricing, issue
        quotes, invoice, and see margins.
      </p>

      {denied ? (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          Only an <b>owner</b> can manage users.
        </div>
      ) : (
        <div className="mt-6">
          <UsersAdmin initialUsers={users} meId={me?.id ?? null} />
        </div>
      )}
    </main>
  );
}
