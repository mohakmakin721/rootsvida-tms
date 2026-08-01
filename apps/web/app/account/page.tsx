import Link from "next/link";

import { getMe } from "@/lib/api";

import { ChangePasswordForm } from "./change-password-form";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const me = await getMe();
  return (
    <main className="mx-auto max-w-md px-6 py-10">
      <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
        ← RootsVida TMS
      </Link>
      <h1 className="mt-1 text-2xl font-semibold">Your account</h1>
      {me && (
        <p className="mt-1 text-sm text-neutral-600">
          {me.email} · <span className="capitalize">{me.role}</span>
        </p>
      )}
      <div className="mt-6">
        <ChangePasswordForm />
      </div>
    </main>
  );
}
