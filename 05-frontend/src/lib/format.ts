/** Indian formatting: ₹ with lakh grouping, day-month dates, nights. */

/** The simulated platform's "today" — matches the dataset (01-dataset) */
export const TODAY = "2026-10-29";

const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });
const num = new Intl.NumberFormat("en-IN");

export const rupees = (v: number | null | undefined, paise = false) =>
  v === null || v === undefined ? "—" : (paise ? inr2 : inr0).format(Number(v));
export const count = (v: number | null | undefined) => (v === null || v === undefined ? "—" : num.format(v));

export const toISO = (d: Date) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
};
const isISODate = (s: unknown): s is string => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);
/** parse "YYYY-MM-DD"; anything malformed falls back to TODAY instead of an Invalid Date */
export const fromISO = (s: string) => new Date(`${isISODate(s) ? s : TODAY}T00:00:00`);
export const addDays = (s: string, n: number) => {
  const d = fromISO(s);
  d.setDate(d.getDate() + n);
  return toISO(d);
};
export const nightsBetween = (a: string, b: string) => Math.round((fromISO(b).getTime() - fromISO(a).getTime()) / 86400000);

export const shortDate = (s: string) => fromISO(s).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
export const longDate = (s: string) =>
  fromISO(s).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Walking minutes at ~4.8 km/h, the way a local would describe distance */
export const walkOrRide = (km: number | null | undefined) => {
  if (km === null || km === undefined) return "nearby";
  if (km < 1.6) return `${Math.max(1, Math.round((km / 4.8) * 60))} min walk`;
  return `${km.toFixed(1)} km · ${Math.round((km / 18) * 60) + 4} min by auto`;
};
