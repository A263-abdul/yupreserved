/**
 * Search results — built for speed and clarity.
 * Filters live in the URL (shareable, back-button friendly). Common choices
 * are one tap away as quick chips; every active filter is listed with an ✕;
 * the full panel uses plain language ("Budget per night", "At least 4★").
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { ResultRow } from "../components/cards";
import { Empty, ErrorNote, Skeleton } from "../components/feedback";
import { Page } from "../components/motion";
import { SearchBar } from "../components/search";
import { api, type SearchParams } from "../lib/api";
import { count, nightsBetween, rupees, shortDate } from "../lib/format";
import { useI18n } from "../lib/i18n";

const TYPES: [string, string][] = [
  ["Hotel", "🏨"], ["Resort", "🌴"], ["Homestay", "🏡"], ["Guest House", "🛏"], ["Cottage", "🛖"], ["Villa", "🏝"],
  ["Houseboat", "🛶"], ["Palace", "🏰"], ["Haveli", "🕌"], ["Heritage Hotel", "🏛"], ["Tent", "⛺"], ["Service Apartment", "🏢"],
];
const SORTS: [string, string][] = [["recommended", "Recommended"], ["price_asc", "Price: low to high"], ["price_desc", "Price: high to low"], ["rating", "Best rated"], ["distance", "Nearest first"]];
const BUDGETS: [string, number | undefined, number | undefined][] = [
  ["Any", undefined, undefined], ["Under ₹2,000", undefined, 2000], ["₹2,000–5,000", 2000, 5000],
  ["₹5,000–12,000", 5000, 12000], ["₹12,000+", 12000, undefined],
];
const CATEGORY_LABEL: Record<string, string> = {
  ESSENTIALS: "Essentials", DINING: "Food & drink", WELLNESS: "Pool, spa & fitness", FAMILY: "Families & pets",
  TRANSPORT: "Getting around", BUSINESS: "Work", SERVICES: "Services", EXPERIENCE: "The setting",
};
const POPULAR_AMENITIES = ["Free Wi-Fi", "Swimming Pool", "Breakfast Included", "Air Conditioning", "Parking", "Spa", "Family Rooms", "Pet Friendly"];

export default function Search() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const [sheet, setSheet] = useState(false);
  const [moreAmenities, setMoreAmenities] = useState(false);

  const minStars = num(params.get("min_stars"));
  const p: SearchParams = useMemo(() => ({
    city_id: num(params.get("city_id")), landmark_id: num(params.get("landmark_id")),
    q: params.get("q") ?? undefined, mood: params.get("mood") ?? undefined,
    check_in: params.get("check_in") ?? undefined, check_out: params.get("check_out") ?? undefined,
    adults: num(params.get("adults")) ?? 2, min_price: num(params.get("min_price")), max_price: num(params.get("max_price")),
    stars: minStars ? [1, 2, 3, 4, 5].filter((s) => s >= minStars) : [],
    types: params.getAll("types"), amenities: params.getAll("amenities").map(Number),
    signature_only: params.get("signature_only") === "true",
    sort: params.get("sort") ?? (params.get("landmark_id") ? "distance" : "recommended"),
    page: num(params.get("page")) ?? 1, page_size: 18,
  }), [params, minStars]);

  const results = useQuery({ queryKey: ["search", p], queryFn: () => api.search(p), placeholderData: keepPreviousData });
  const amenities = useQuery({ queryKey: ["amenities"], queryFn: api.amenities, staleTime: Infinity });
  const moods = useQuery({ queryKey: ["moods"], queryFn: api.moods, staleTime: Infinity });
  const amenityId = (name: string) => amenities.data?.find((a) => a.amenity_name === name)?.amenity_id;

  const update = (changes: Record<string, string | string[] | undefined>, keepPage = false) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      next.delete(k);
      if (Array.isArray(v)) v.forEach((x) => next.append(k, x));
      else if (v !== undefined && v !== "") next.set(k, v);
    }
    if (!keepPage) next.delete("page");
    setParams(next);
  };
  const toggle = (key: string, value: string) => {
    const cur = params.getAll(key);
    update({ [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] });
  };
  const hasAmenity = (name: string) => { const id = amenityId(name); return id !== undefined && p.amenities!.includes(id); };
  const toggleAmenity = (name: string) => { const id = amenityId(name); if (id !== undefined) toggle("amenities", String(id)); };

  // every active filter as a removable pill
  const active: { label: string; clear: () => void }[] = [];
  if (p.mood) active.push({ label: moods.data?.find((m) => m.key === p.mood)?.label ?? p.mood, clear: () => update({ mood: undefined }) });
  if (p.min_price !== undefined || p.max_price !== undefined)
    active.push({ label: budgetLabel(p.min_price, p.max_price), clear: () => update({ min_price: undefined, max_price: undefined }) });
  if (minStars) active.push({ label: `${minStars}★ & up`, clear: () => update({ min_stars: undefined }) });
  p.types!.forEach((ty) => active.push({ label: ty, clear: () => toggle("types", ty) }));
  p.amenities!.forEach((id) => active.push({ label: amenities.data?.find((a) => a.amenity_id === id)?.amenity_name ?? `#${id}`, clear: () => toggle("amenities", String(id)) }));
  if (p.signature_only) active.push({ label: "Signature stays", clear: () => update({ signature_only: undefined }) });
  const clearAll = () => update({ mood: undefined, min_price: undefined, max_price: undefined, min_stars: undefined, types: [], amenities: [], signature_only: undefined });

  const nights = p.check_in && p.check_out ? nightsBetween(p.check_in, p.check_out) : 0;
  const label = params.get("label") ?? (p.mood ? moods.data?.find((m) => m.key === p.mood)?.label : p.q) ?? "All of India";
  const total = results.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / 18));

  const quick: { label: string; on: boolean; toggle: () => void }[] = [
    { label: "✦ Signature", on: !!p.signature_only, toggle: () => update({ signature_only: p.signature_only ? undefined : "true" }) },
    { label: "Under ₹2,000", on: p.max_price === 2000 && p.min_price === undefined, toggle: () => p.max_price === 2000 ? update({ min_price: undefined, max_price: undefined }) : update({ min_price: undefined, max_price: "2000" }) },
    { label: "4★ & up", on: minStars === 4, toggle: () => update({ min_stars: minStars === 4 ? undefined : "4" }) },
    ...["Swimming Pool", "Breakfast Included", "Free Wi-Fi"].map((n) => ({ label: n.replace(" Included", ""), on: hasAmenity(n), toggle: () => toggleAmenity(n) })),
  ];

  const grouped = useMemo(() => (amenities.data ?? []).filter((a) => a.hotels >= 25).reduce<Record<string, typeof amenities.data>>((acc, a) => {
    (acc[a.category] ??= [] as any).push(a); return acc;
  }, {}), [amenities.data]);

  const panel = (
    <div className="space-y-8">
      <Group title="Budget per night" hint="List price before festival pricing and tax">
        <div className="grid grid-cols-2 gap-2">
          {BUDGETS.map(([l, lo, hi]) => (
            <Choice key={l} on={p.min_price === lo && p.max_price === hi} onClick={() => update({ min_price: lo?.toString(), max_price: hi?.toString() })}>{l}</Choice>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <MoneyInput label="Min" value={p.min_price} onCommit={(v) => update({ min_price: v })} />
          <span className="text-ink-3">to</span>
          <MoneyInput label="Max" value={p.max_price} onCommit={(v) => update({ max_price: v })} />
        </div>
      </Group>

      <Group title="Star rating" hint="Unrated homestays and guest houses are hidden once you pick one">
        <div className="grid grid-cols-5 gap-1.5">
          {[undefined, 2, 3, 4, 5].map((s) => (
            <Choice key={s ?? "any"} on={minStars === s} onClick={() => update({ min_stars: s?.toString() })}>{s ? `${s}★+` : "Any"}</Choice>
          ))}
        </div>
      </Group>

      <Group title="Type of stay">
        <div className="grid grid-cols-2 gap-2">
          {TYPES.map(([ty, icon]) => (
            <Choice key={ty} on={p.types!.includes(ty)} onClick={() => toggle("types", ty)}><span aria-hidden className="mr-1.5">{icon}</span>{ty}</Choice>
          ))}
        </div>
      </Group>

      <Group title="Must have" hint="Stays that have ALL of what you tick">
        <div className="space-y-1">
          {POPULAR_AMENITIES.map((n) => (
            <Check key={n} on={hasAmenity(n)} onChange={() => toggleAmenity(n)}>{n}</Check>
          ))}
        </div>
        <button onClick={() => setMoreAmenities((m) => !m)} className="mt-3 text-sm font-semibold text-sindoor">
          {moreAmenities ? "Fewer options" : "More amenities"}
        </button>
        {moreAmenities && (
          <div className="mt-3 space-y-4">
            {Object.entries(grouped).map(([cat, list]) => (
              <div key={cat}>
                <p className="mb-1 text-xs font-semibold text-ink-3">{CATEGORY_LABEL[cat] ?? cat}</p>
                {list!.filter((a) => !POPULAR_AMENITIES.includes(a.amenity_name)).map((a) => (
                  <Check key={a.amenity_id} on={p.amenities!.includes(a.amenity_id)} onChange={() => toggle("amenities", String(a.amenity_id))}>
                    {a.amenity_name} <span className="text-xs text-ink-3">· {count(a.hotels)}</span>
                  </Check>
                ))}
              </div>
            ))}
          </div>
        )}
      </Group>

      <Group title="Mood">
        <div className="grid grid-cols-2 gap-2">
          {moods.data?.map((m) => (
            <Choice key={m.key} on={p.mood === m.key} onClick={() => update({ mood: p.mood === m.key ? undefined : m.key })}>{m.label}</Choice>
          ))}
        </div>
      </Group>
    </div>
  );

  return (
    <Page className="mx-auto max-w-7xl px-4 pb-10 pt-6 sm:px-6">
      <SearchBar variant="compact" key={params.toString()}
        initial={{ text: params.get("label") ?? p.q ?? "", checkIn: p.check_in, checkOut: p.check_out, adults: p.adults,
          dest: p.city_id ? { kind: "city", id: p.city_id, label: params.get("label") ?? "", sublabel: "", hotels: null }
            : p.landmark_id ? { kind: "landmark", id: p.landmark_id, label: params.get("label") ?? "", sublabel: "", hotels: null } : null }} />

      <div className="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">{nights ? `${shortDate(p.check_in!)} → ${shortDate(p.check_out!)} · ${nights} night${nights > 1 ? "s" : ""} · ${p.adults} adults` : "Any dates — add dates to see exact totals"}</p>
          <h1 className="display mt-1 text-4xl sm:text-5xl">{label}</h1>
          <p className="mt-1 text-ink-2" aria-live="polite">{results.isFetching && !results.data ? "Searching…" : `${count(total)} ${t("results")}`}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink-2">
          {t("sort")}
          <select value={p.sort} onChange={(e) => update({ sort: e.target.value })} className="rounded-full border border-line bg-card px-3 py-2 text-ink">
            {SORTS.filter(([k]) => k !== "distance" || p.landmark_id).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </label>
      </div>

      {/* quick filters: the common choices, one tap away (scrolls sideways on phones) */}
      <div className="sticky top-16 z-20 -mx-4 mt-5 bg-paper/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
          <button onClick={() => setSheet(true)}
            className="flex shrink-0 items-center gap-2 rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper lg:hidden">
            ⚙ {t("filters")}{active.length ? <span className="rounded-full bg-sindoor px-1.5 text-xs text-sindoor-ink">{active.length}</span> : null}
          </button>
          {quick.map((q) => (
            <button key={q.label} aria-pressed={q.on} onClick={q.toggle}
              className={`shrink-0 rounded-full border px-4 py-2 text-sm transition ${q.on ? "border-sindoor bg-sindoor text-sindoor-ink" : "border-line bg-card hover:border-ink/40"}`}>
              {q.label}
            </button>
          ))}
        </div>
        {active.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink-3">Showing:</span>
            {active.map((a) => (
              <button key={a.label} onClick={a.clear} className="flex items-center gap-1.5 rounded-full bg-paper-2 px-3 py-1 hover:bg-line" aria-label={`Remove ${a.label}`}>
                {a.label} <span aria-hidden className="text-ink-3">✕</span>
              </button>
            ))}
            <button onClick={clearAll} className="font-semibold text-sindoor">Clear all</button>
          </div>
        )}
      </div>

      <div className="mt-6 grid gap-10 lg:grid-cols-[290px_1fr]">
        <aside className="hidden lg:block" aria-label="Filters">
          <div className="sticky top-40 max-h-[calc(100vh-11rem)] overflow-y-auto rounded-3xl border border-line bg-card p-5 scrollbar-none">{panel}</div>
        </aside>
        <section aria-label="Results" className={`space-y-3 transition-opacity ${results.isFetching ? "opacity-60" : ""}`}>
          {results.error ? <ErrorNote error={results.error} onRetry={() => results.refetch()} /> :
            !results.data ? Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-40" />) :
            results.data.results.length === 0 ? (
              <Empty title={t("empty")} sub={active.length ? "Try removing a filter — the last one you added is usually the culprit." : t("emptySub")}
                action={active.length ? <button onClick={clearAll} className="rounded-full bg-ink px-5 py-2.5 text-paper">Clear all filters</button> : undefined} />
            ) : (
              <>
                {results.data.results.map((h) => <ResultRow key={h.hotel_id} h={h} nights={nights} />)}
                <nav className="flex items-center justify-center gap-3 pt-6" aria-label="Pages">
                  <button disabled={p.page! <= 1} onClick={() => { update({ page: String(p.page! - 1) }, true); window.scrollTo({ top: 0 }); }}
                    className="rounded-full border border-line px-4 py-2 disabled:opacity-30">← Prev</button>
                  <span className="text-sm text-ink-2 tabular">Page {p.page} of {count(pages)}</span>
                  <button disabled={p.page! >= pages} onClick={() => { update({ page: String(p.page! + 1) }, true); window.scrollTo({ top: 0 }); }}
                    className="rounded-full border border-line px-4 py-2 disabled:opacity-30">Next →</button>
                </nav>
              </>
            )}
        </section>
      </div>

      {/* mobile filter sheet */}
      <AnimatePresence>
        {sheet && (
          <motion.div className="fixed inset-0 z-[65] bg-ink/40 lg:hidden" onClick={() => setSheet(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.div role="dialog" aria-label="Filters" onClick={(e) => e.stopPropagation()} initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 280 }}
              className="absolute inset-x-0 bottom-0 flex max-h-[88vh] flex-col rounded-t-[2rem] bg-card">
              <div className="flex items-center justify-between border-b border-line px-6 py-4">
                <p className="display text-2xl">{t("filters")}</p>
                <button onClick={() => setSheet(false)} className="rounded-full px-3 py-1 text-ink-3" aria-label="Close">✕</button>
              </div>
              <div className="flex-1 overflow-y-auto px-6 py-5">{panel}</div>
              <div className="flex gap-3 border-t border-line px-6 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
                <button onClick={clearAll} className="rounded-full border border-line px-5 py-3">Clear</button>
                <button onClick={() => setSheet(false)} className="flex-1 rounded-full bg-sindoor py-3 font-semibold text-sindoor-ink">
                  {results.isFetching ? "Updating…" : `Show ${count(total)} stays`}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Page>
  );
}

const num = (v: string | null) => (v === null || v === "" || Number.isNaN(Number(v)) ? undefined : Number(v));

function budgetLabel(lo?: number, hi?: number) {
  if (lo !== undefined && hi !== undefined) return `${rupees(lo)}–${rupees(hi)}`;
  if (hi !== undefined) return `Under ${rupees(hi)}`;
  return `${rupees(lo)}+`;
}

function Group({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset>
      <legend className="font-semibold">{title}</legend>
      {hint && <p className="mb-3 mt-0.5 text-xs text-ink-3">{hint}</p>}
      <div className={hint ? "" : "mt-3"}>{children}</div>
    </fieldset>
  );
}

function Choice({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick}
      className={`rounded-xl border px-3 py-2 text-left text-sm transition ${on ? "border-ink bg-ink text-paper" : "border-line text-ink-2 hover:border-ink/40"}`}>
      {children}
    </button>
  );
}

function Check({ on, onChange, children }: { on: boolean; onChange: () => void; children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg px-1 py-1.5 text-sm hover:bg-paper-2">
      <input type="checkbox" checked={on} onChange={onChange} className="h-4 w-4 accent-[var(--sindoor)]" />
      <span>{children}</span>
    </label>
  );
}

function MoneyInput({ label, value, onCommit }: { label: string; value?: number; onCommit: (v: string | undefined) => void }) {
  const [v, setV] = useState(value?.toString() ?? "");
  const commit = () => onCommit(v.replace(/\D/g, "") || undefined);
  return (
    <label className="flex flex-1 items-center gap-1 rounded-xl border border-line px-3 py-2 focus-within:border-ink">
      <span className="text-ink-3">₹</span>
      <input inputMode="numeric" aria-label={`${label} price`} placeholder={label} value={v}
        onChange={(e) => setV(e.target.value.replace(/\D/g, ""))} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()}
        className="w-full bg-transparent focus:outline-none tabular" />
    </label>
  );
}
