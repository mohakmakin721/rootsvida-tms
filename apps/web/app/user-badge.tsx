"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

export function UserBadge({ email, role }: { email: string; role: string }) {
  const router = useRouter();

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex items-center gap-3 text-sm text-neutral-500">
      <Link href="/account" className="hover:text-neutral-800" title={`${email} · ${role}`}>
        {email} · <span className="capitalize text-neutral-700">{role}</span>
      </Link>
      <button
        onClick={logout}
        className="rounded-md border border-neutral-300 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50"
      >
        Log out
      </button>
    </div>
  );
}
