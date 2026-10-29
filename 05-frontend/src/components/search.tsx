/**
 * The search bar — always one step from booking.
 * Destination is a combobox over cities, landmarks and hotels (one UNION
 * query on the backend); dates are native inputs, which are accessible and
 * fast on phones.
 */
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Destination } from "../lib/api";
import { addDays, TODAY } from "../lib/format";
import { useI18n } from "../lib/i18n";

export type SearchValue = { dest: Destination | null; text: string; checkIn: string; checkOut: string; adults: number };

export const defaultSearch = (): SearchValue => ({
  dest: null, text: "", checkIn: addDays(TODAY, 14), checkOut: addDays(TODAY, 16), adults: 2,
});

function useDebounced<T>(value: T, ms = 160) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

const KIND_ICON: Record<Destination["kind"], string> = { city: "◎", landmark: "✦", hotel: "⌂" };

export function DestinationInput({ value, onChange, autoFocus = false }:
  { value: SearchValue; onChange: (v: Partial<SearchValue>) => void; autoFocus?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const term = useDebounced(value.text);
  const listId = useId();
  const { data = [], isFetching } = useQuery({
    queryKey: ["dest", term],
    queryFn: () => api.destinations(term),
    staleTime: 60_000,
    enabled: open,
  });

  const pick = (d: Destination) => {
    onChange({ dest: d, text: d.label });
    setOpen(false);
  };

  return (
    <div className="relative">
      <label htmlFor={`${listId}-in`} className="eyebrow block">{t("where")}</label>
      <input
        id={`${listId}-in`}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && data[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        autoFocus={autoFocus}
        value={value.text}
        placeholder={t("wherePh")}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onChange={(e) => { onChange({ text: e.target.value, dest: null }); setOpen(true); setActive(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, data.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && open && data[active]) { e.preventDefault(); pick(data[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
        className="mt-1 w-full bg-transparent text-lg text-ink placeholder:text-ink-3 focus:outline-none"
      />
      <AnimatePresence>
        {open && (data.length > 0 || isFetching) && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="absolute left-0 right-0 top-full z-40 mt-3 max-h-80 overflow-auto rounded-2xl border border-line bg-card p-1.5 shadow-2xl sm:-left-4 sm:w-[26rem]"
          >
            {!value.text && <li className="px-3 pb-1 pt-2 text-xs text-ink-3">Popular right now</li>}
            {data.map((d, i) => (
              <li
                key={`${d.kind}-${d.id}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); pick(d); }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 ${i === active ? "bg-paper-2" : ""}`}
              >
                <span className="grid h-8 w-8 place-items-center rounded-full bg-paper-2 text-sindoor">{KIND_ICON[d.kind]}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{d.label}</span>
                  <span className="block truncate text-xs text-ink-3">
                    {d.kind === "landmark" ? `Landmark in ${d.sublabel}` : d.kind === "hotel" ? `Stay in ${d.sublabel}` : d.sublabel}
                  </span>
                </span>
                {d.hotels ? <span className="text-xs text-ink-3 tabular">{d.hotels} stays</span> : null}
              </li>
            ))}
            {isFetching && data.length === 0 && <li className="px-3 py-3 text-sm text-ink-3">Looking…</li>}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

export function searchUrl(v: SearchValue, extra: Record<string, string> = {}) {
  const p = new URLSearchParams(extra);
  if (v.dest?.kind === "city") p.set("city_id", String(v.dest.id));
  if (v.dest?.kind === "landmark") { p.set("landmark_id", String(v.dest.id)); p.set("sort", "distance"); }
  if (!v.dest && v.text.trim()) p.set("q", v.text.trim());
  if (v.dest) p.set("label", v.dest.label);
  if (v.checkIn && v.checkOut) { p.set("check_in", v.checkIn); p.set("check_out", v.checkOut); }
  p.set("adults", String(v.adults));
  return `/stays?${p.toString()}`;
}

export function SearchBar({ initial, variant = "hero" }: { initial?: Partial<SearchValue>; variant?: "hero" | "compact" }) {
  const { t } = useI18n();
  const nav = useNavigate();
  // only take the values that are actually set — an undefined check-in must not wipe the default dates
  const [v, setV] = useState<SearchValue>(() => ({
    ...defaultSearch(),
    ...Object.fromEntries(Object.entries(initial ?? {}).filter(([, x]) => x !== undefined && x !== null && x !== "")),
  }));
  const set = (p: Partial<SearchValue>) => setV((old) => {
    const next = { ...old, ...p };
    if (p.checkIn && next.checkOut <= p.checkIn) next.checkOut = addDays(p.checkIn, 1);
    return next;
  });
  const ref = useRef<HTMLFormElement>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (v.dest?.kind === "hotel") nav(`/stay/${v.dest.id}?check_in=${v.checkIn}&check_out=${v.checkOut}&adults=${v.adults}`);
    else nav(searchUrl(v));
  };

  const field = "rounded-2xl px-4 py-3 transition hover:bg-paper-2/70 focus-within:bg-paper-2/70";
  return (
    <form ref={ref} onSubmit={submit} role="search"
      className={`grid gap-1 rounded-[1.75rem] border border-line bg-card/95 p-2 shadow-[0_30px_60px_-35px_rgb(var(--shadow)/0.6)] backdrop-blur
        ${variant === "hero" ? "sm:grid-cols-[1.6fr_1fr_1fr_0.7fr_auto]" : "sm:grid-cols-[1.6fr_1fr_1fr_0.7fr_auto]"}`}>
      <div className={field}><DestinationInput value={v} onChange={set} /></div>
      <label className={field}>
        <span className="eyebrow block">{t("checkIn")}</span>
        <input type="date" min={TODAY} value={v.checkIn} onChange={(e) => set({ checkIn: e.target.value })}
          className="mt-1 w-full bg-transparent text-base text-ink focus:outline-none" />
      </label>
      <label className={field}>
        <span className="eyebrow block">{t("checkOut")}</span>
        <input type="date" min={addDays(v.checkIn, 1)} value={v.checkOut} onChange={(e) => set({ checkOut: e.target.value })}
          className="mt-1 w-full bg-transparent text-base text-ink focus:outline-none" />
      </label>
      <label className={field}>
        <span className="eyebrow block">{t("guests")}</span>
        <select value={v.adults} onChange={(e) => set({ adults: Number(e.target.value) })}
          className="mt-1 w-full bg-transparent text-base text-ink focus:outline-none">
          {[1, 2, 3, 4, 5, 6, 8, 10, 12].map((n) => <option key={n} value={n}>{n} {n === 1 ? "adult" : "adults"}</option>)}
        </select>
      </label>
      <button type="submit"
        className="m-1 inline-flex items-center justify-center gap-2 rounded-[1.35rem] bg-sindoor px-7 py-4 font-semibold text-sindoor-ink transition hover:brightness-110 active:scale-[0.98]">
        {t("search")} <span aria-hidden>→</span>
      </button>
    </form>
  );
}
