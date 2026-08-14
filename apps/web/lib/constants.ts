// Shared pricing-input constants used by the builder and the quote view.

// Indian GST state codes (buyer's state → tax split). Seller is 05, Uttarakhand.
export const GST_STATES: { code: string; name: string }[] = [
  { code: "01", name: "Jammu & Kashmir" }, { code: "02", name: "Himachal Pradesh" },
  { code: "03", name: "Punjab" }, { code: "04", name: "Chandigarh" },
  { code: "05", name: "Uttarakhand" }, { code: "06", name: "Haryana" },
  { code: "07", name: "Delhi" }, { code: "08", name: "Rajasthan" },
  { code: "09", name: "Uttar Pradesh" }, { code: "10", name: "Bihar" },
  { code: "11", name: "Sikkim" }, { code: "12", name: "Arunachal Pradesh" },
  { code: "13", name: "Nagaland" }, { code: "14", name: "Manipur" },
  { code: "15", name: "Mizoram" }, { code: "16", name: "Tripura" },
  { code: "17", name: "Meghalaya" }, { code: "18", name: "Assam" },
  { code: "19", name: "West Bengal" }, { code: "20", name: "Jharkhand" },
  { code: "21", name: "Odisha" }, { code: "22", name: "Chhattisgarh" },
  { code: "23", name: "Madhya Pradesh" }, { code: "24", name: "Gujarat" },
  { code: "26", name: "Dadra & Nagar Haveli and Daman & Diu" },
  { code: "27", name: "Maharashtra" }, { code: "29", name: "Karnataka" },
  { code: "30", name: "Goa" }, { code: "31", name: "Lakshadweep" },
  { code: "32", name: "Kerala" }, { code: "33", name: "Tamil Nadu" },
  { code: "34", name: "Puducherry" }, { code: "35", name: "Andaman & Nicobar" },
  { code: "36", name: "Telangana" }, { code: "37", name: "Andhra Pradesh" },
  { code: "38", name: "Ladakh" }, { code: "97", name: "Other territory" },
];

// Kept in ascending order for tidy pickers.
export const CURRENCIES = ["AED", "AUD", "CAD", "CHF", "EUR", "GBP", "INR", "JPY", "NZD", "SGD", "USD"];

/** Format an INR amount for display. */
export function inr(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

/** Room occupancy for stay/hotel rates — one constant shared by the Days rate picker,
 *  the vendor & rate browser, and the bulk-import template. Values match the DB
 *  `occupancy` enum (single|double|triple|extra_adult|twin). */
export const OCCUPANCIES = ["single", "double", "triple", "extra_adult", "twin"] as const;
export const OCCUPANCY_LABEL: Record<string, string> = {
  single: "single",
  double: "double",
  triple: "triple",
  extra_adult: "extra bed",
  twin: "twin bed",
};

/** Accommodation tiers — the canonical stay `category` vocabulary, shared by the AI
 *  "Accommodation" preference and the stay-vendor Category field so everything lines
 *  up (and the vendor-browser Category filter stays clean once data is normalized). */
export const ACCOMMODATION_TIERS = [
  "Homestays",
  "Hostels",
  "2 Star",
  "3 Star",
  "4 Star",
  "5 Star",
  "7 Star",
] as const;
