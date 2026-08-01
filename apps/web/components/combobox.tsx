"use client";

import { useEffect, useRef, useState } from "react";

export interface ComboOption {
  value: string;
  label: string;
  sublabel?: string;
}

const inputCls =
  "w-full rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-900 focus:border-neutral-500 focus:outline-none";

/** A lightweight type-ahead: filter a provided option list as you type, click to
 *  select. Options should be passed already sorted. */
export function Combobox({
  options,
  value,
  onChange,
  placeholder,
  allowClear = true,
}: {
  options: ComboOption[];
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
  allowClear?: boolean;
}) {
  const selected = options.find((o) => o.value === value) ?? null;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? options.filter(
        (o) =>
          o.label.toLowerCase().includes(q) ||
          (o.sublabel ?? "").toLowerCase().includes(q),
      )
    : options;

  return (
    <div ref={ref} className="relative">
      <input
        className={inputCls}
        placeholder={placeholder}
        value={open ? query : selected?.label ?? ""}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
      />
      {selected && allowClear && !open && (
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-label="Clear"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-neutral-400 hover:text-neutral-700"
        >
          ✕
        </button>
      )}
      {open && (
        <ul className="absolute z-30 mt-1 max-h-56 w-full overflow-auto rounded-md border border-neutral-200 bg-white text-sm shadow-lg">
          {filtered.length === 0 && (
            <li className="px-3 py-2 text-neutral-400">No matches</li>
          )}
          {filtered.map((o) => (
            <li key={o.value}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left hover:bg-neutral-50"
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                  setQuery("");
                }}
              >
                <span className="text-neutral-800">{o.label}</span>
                {o.sublabel && <span className="text-xs text-neutral-400">{o.sublabel}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
