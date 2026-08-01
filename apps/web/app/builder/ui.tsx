"use client";

export const inputCls =
  "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-900 focus:border-neutral-500 focus:outline-none disabled:bg-neutral-100";
export const btnDark =
  "inline-flex items-center rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800";
export const btnLight =
  "inline-flex items-center rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-50";

/** Red asterisk marking a field that must be filled before you can move on. */
export function Req() {
  return (
    <span className="text-red-500" aria-label="required" title="Required">
      {" "}
      *
    </span>
  );
}

/** A small ℹ button that reveals help text on hover or keyboard focus. */
export function InfoTip({ children }: { children: React.ReactNode }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label="More information"
        className="flex h-4 w-4 items-center justify-center rounded-full border border-neutral-300 text-[10px] font-semibold text-neutral-500 hover:border-neutral-500 hover:text-neutral-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-400"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-6 z-30 hidden w-72 rounded-md border border-neutral-200 bg-white p-3 text-xs leading-relaxed text-neutral-600 shadow-lg group-hover:block group-focus-within:block"
      >
        {children}
      </span>
    </span>
  );
}

export function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-neutral-500">
        {label}
        {required && <Req />}
      </span>
      {children}
    </label>
  );
}

export function Card({
  title,
  info,
  action,
  children,
}: {
  title: string;
  info?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-neutral-800">
          {title}
          {info && <InfoTip>{info}</InfoTip>}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-neutral-200 px-3 py-3 text-xs text-neutral-400">
      {children}
    </p>
  );
}
