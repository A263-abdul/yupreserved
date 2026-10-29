/** Hotel cards: a slow editorial poster card and a fast list row. */
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import type { HotelCard as Hotel } from "../lib/api";
import { rupees, walkOrRide } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { useSession } from "../lib/session";
import { Photo } from "./Photo";

export function Stars({ n }: { n: number }) {
  if (!n) return <span className="text-xs text-ink-3">Unrated</span>;
  return (
    <span className="text-haldi" aria-label={`${n} star`}>
      {"★".repeat(n)}<span className="text-line">{"★".repeat(5 - n)}</span>
    </span>
  );
}

export function Rating({ value, count, size = "sm" }: { value: number | null; count: number; size?: "sm" | "lg" }) {
  if (!value) return <span className="text-sm text-ink-3">New on YupReserved</span>;
  return (
    <span className={`inline-flex items-center gap-2 ${size === "lg" ? "text-base" : "text-sm"}`}>
      <span className="rounded-md bg-peacock px-1.5 py-0.5 font-semibold text-paper tabular">{Number(value).toFixed(1)}</span>
      <span className="text-ink-2">{count.toLocaleString("en-IN")} reviews</span>
    </span>
  );
}

/** Tall poster card, for signature stays */
export function PosterCard({ h, index = 0 }: { h: Hotel; index?: number }) {
  const { t } = useI18n();
  return (
    <motion.div whileHover={{ y: -6 }} transition={{ type: "spring", stiffness: 260, damping: 24 }}>
      <Link to={`/stay/${h.hotel_id}`} className="group block" aria-label={`${h.hotel_name}, ${h.city_name}`}>
        <Photo src={h.photo_url} alt={`${h.hotel_name} — ${h.photo_caption ?? h.city_name}`} credit={h.photo_credit} showCredit
          city={h.city_name} propertyType={h.property_type} seed={h.hotel_id * 97 + index}
          className="aspect-[4/5] w-full rounded-[1.75rem] shadow-[0_24px_50px_-28px_rgb(var(--shadow)/0.55)] [&>img]:transition [&>img]:duration-700 group-hover:[&>img]:scale-[1.04]">
          <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/35 to-transparent" />
          <div className="absolute inset-x-0 top-0 flex items-start justify-between p-4">
            <span className="rounded-full bg-paper/85 px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-ink backdrop-blur">
              {h.city_name}
            </span>
            {h.avg_rating ? (
              <span className="rounded-full bg-ink/70 px-2.5 py-1 text-xs font-semibold text-paper backdrop-blur tabular">★ {Number(h.avg_rating).toFixed(1)}</span>
            ) : null}
          </div>
        </Photo>
        <div className="mt-4 px-1">
          <p className="eyebrow">{h.property_type}{h.locality ? ` · ${h.locality}` : ""}</p>
          <h3 className="display mt-1 text-[1.6rem] leading-tight group-hover:text-sindoor">{h.hotel_name}</h3>
          {h.tagline && <p className="mt-1 text-ink-2">{h.tagline}</p>}
          <p className="mt-2 text-sm text-ink-2">
            <span className="text-ink-3">{t("from")}</span> <span className="font-semibold text-ink tabular">{rupees(h.from_price)}</span> {t("perNight")}
          </p>
        </div>
      </Link>
    </motion.div>
  );
}

/** Compact, fast row for search results (budget travellers scan, they don't linger) */
export function ResultRow({ h, nights }: { h: Hotel; nights: number }) {
  const { compare, toggleCompare } = useSession();
  const inCompare = compare.some((c) => c.hotel_id === h.hotel_id);
  const soldOut = h.free_rooms === 0 && h.stay_total === null && nights > 0;
  return (
    <article className="group grid grid-cols-[96px_1fr] gap-4 rounded-3xl border border-line bg-card p-3 transition hover:border-ink/25 sm:grid-cols-[180px_1fr_auto] sm:p-4">
      <Link to={`/stay/${h.hotel_id}`} className="row-span-2 sm:row-span-1" tabIndex={-1} aria-hidden>
        <Photo src={h.photo_url} alt="" city={h.city_name} propertyType={h.property_type} seed={h.hotel_id * 31}
          className="aspect-square h-full w-full rounded-2xl sm:aspect-[4/3]">
          {h.photo_caption && h.photo_url && (
            <span className="absolute bottom-1.5 left-1.5 max-w-[90%] truncate rounded-md bg-black/45 px-1.5 py-0.5 text-[0.6rem] text-white backdrop-blur">
              {h.photo_caption}
            </span>
          )}
        </Photo>
      </Link>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {h.is_signature && <span className="rounded-full bg-sindoor px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wider text-sindoor-ink">Signature</span>}
          <span className="text-xs text-ink-3">{h.property_type}</span>
          <Stars n={h.star_rating} />
        </div>
        <Link to={`/stay/${h.hotel_id}`}>
          <h3 className="display-tight mt-1 truncate text-xl font-medium group-hover:text-sindoor sm:text-2xl">{h.hotel_name}</h3>
        </Link>
        <p className="truncate text-sm text-ink-2">
          {h.locality ? `${h.locality}, ` : ""}{h.city_name}
          {h.distance_km !== null && h.distance_km !== undefined && <> · <span className="text-peacock">{walkOrRide(h.distance_km)}</span></>}
        </p>
        <div className="mt-2"><Rating value={h.avg_rating} count={h.review_count} /></div>
        {h.highlights?.length ? (
          <p className="mt-2 hidden truncate text-xs text-ink-3 sm:block">{h.highlights.slice(0, 4).join(" · ")}</p>
        ) : null}
      </div>
      <div className="col-start-2 flex items-end justify-between gap-3 sm:col-start-3 sm:flex-col sm:items-end sm:justify-between">
        <label className="flex cursor-pointer items-center gap-2 text-xs text-ink-2">
          <input type="checkbox" checked={inCompare} onChange={() => toggleCompare(h)} className="accent-[var(--sindoor)]" />
          Compare
        </label>
        <div className="text-right">
          {nights > 0 ? (
            soldOut ? <p className="text-sm font-semibold text-sindoor">Sold out for your dates</p> : (
              <>
                <p className="text-xl font-semibold tabular">{rupees(h.stay_total)}</p>
                <p className="text-xs text-ink-3">{nights} night{nights > 1 ? "s" : ""}, incl. GST · {h.free_rooms} rooms left</p>
              </>
            )
          ) : (
            <>
              <p className="text-xs text-ink-3">from</p>
              <p className="text-xl font-semibold tabular">{rupees(h.from_price)}</p>
              <p className="text-xs text-ink-3">per night, before tax</p>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
