/**
 * A hotel page tells the story of the place first, then gets out of the way:
 * rooms are priced live for your dates and booking is never more than one
 * tap away (sticky bar on mobile, sticky card on desktop).
 */
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Poster } from "../art/Poster";
import { StarRule } from "../components/brand";
import { Rating, Stars } from "../components/cards";
import { Photo } from "../components/Photo";
import { ErrorNote, Skeleton } from "../components/feedback";
import { Page, Reveal } from "../components/motion";
import { api, type Availability, type HotelDetail } from "../lib/api";
import { addDays, longDate, nightsBetween, rupees, TODAY, walkOrRide } from "../lib/format";
import { useI18n } from "../lib/i18n";

const CATEGORY_LABEL: Record<string, string> = {
  EXPERIENCE: "The setting", WELLNESS: "Unwind", DINING: "Eat & drink", ESSENTIALS: "Essentials",
  FAMILY: "Families", TRANSPORT: "Getting around", SERVICES: "Services", BUSINESS: "Work",
};
const LANDMARK_ICON: Record<string, string> = {
  HERITAGE: "🏛", BEACH: "🌊", NATURE: "🌿", TEMPLE: "🛕", MARKET: "🛍", LAKE: "💧", LANDMARK: "✦", BUSINESS: "🏢",
};

export default function Hotel() {
  const { id } = useParams();
  const hotelId = Number(id);
  const [params, setParams] = useSearchParams();
  const checkIn = params.get("check_in") ?? addDays(TODAY, 14);
  const checkOut = params.get("check_out") ?? addDays(checkIn, 2);
  const adults = Number(params.get("adults") ?? 2);
  const [rooms, setRooms] = useState(1);

  const hotel = useQuery({ queryKey: ["hotel", hotelId], queryFn: () => api.hotel(hotelId) });
  const avail = useQuery({
    queryKey: ["avail", hotelId, checkIn, checkOut, rooms],
    queryFn: () => api.availability(hotelId, checkIn, checkOut, rooms),
    enabled: checkOut > checkIn,
  });

  const setDates = (ci: string, co: string) => {
    const next = new URLSearchParams(params);
    next.set("check_in", ci);
    next.set("check_out", co <= ci ? addDays(ci, 1) : co);
    setParams(next, { replace: true });
  };

  if (hotel.error) return <Page className="mx-auto max-w-3xl p-6"><ErrorNote error={hotel.error} onRetry={() => hotel.refetch()} /></Page>;
  const h = hotel.data;

  return (
    <Page>
      {/* hero */}
      <section className="relative">
        {h?.photo?.photo_url_hd || h?.photo?.photo_url ? (
          <Photo src={h.photo.photo_url_hd ?? h.photo.photo_url} alt={`${h.photo.photo_caption}, near ${h.hotel_name}`} eager
            city={h.city_name} propertyType={h.property_type} seed={hotelId * 97} className="h-[68svh] min-h-[420px] w-full" />
        ) : (
          <Poster city={h?.city_name} propertyType={h?.property_type} seed={hotelId * 97} parallax
            className="h-[68svh] min-h-[420px] w-full" title={h ? `${h.hotel_name}, ${h.city_name}` : undefined} />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-paper via-paper/55 to-transparent" />
        {h?.photo?.photo_credit && (
          <p className="absolute right-4 top-20 max-w-[60%] truncate rounded-full bg-black/35 px-3 py-1 text-[0.65rem] text-white/90 backdrop-blur">
            {h.photo.photo_caption} · Photo: {h.photo.photo_credit}
          </p>
        )}
        <div className="absolute inset-x-0 bottom-0 mx-auto max-w-7xl px-4 pb-8 sm:px-6">
          {h ? (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
              <p className="eyebrow !text-ink-2">
                <Link to={`/stays?city_id=${h.city_id}&label=${encodeURIComponent(h.city_name)}`} className="hover:text-sindoor">{h.city_name}</Link>
                {" · "}{h.state_name} · {h.property_type}
              </p>
              <h1 className="display mt-2 max-w-4xl text-[clamp(2.6rem,7vw,6rem)] leading-[0.95]">{h.hotel_name}</h1>
              <div className="mt-4 flex flex-wrap items-center gap-4">
                <Stars n={h.star_rating} />
                <Rating value={h.avg_rating} count={h.review_count} size="lg" />
                {h.is_signature && <span className="rounded-full bg-sindoor px-3 py-1 text-xs font-bold uppercase tracking-wider text-sindoor-ink">YupReserved Signature</span>}
              </div>
            </motion.div>
          ) : <Skeleton className="h-32 w-2/3" />}
        </div>
      </section>

      <div className="mx-auto grid max-w-7xl gap-14 px-4 pt-10 sm:px-6 lg:grid-cols-[1fr_380px]">
        <div className="min-w-0">
          {!h ? <Skeleton className="h-64" /> : (
            <>
              {/* story */}
              <Reveal>
                {h.tagline && <p className="display text-[clamp(1.6rem,3.4vw,2.4rem)] leading-tight text-sindoor">{h.tagline}</p>}
                <p className="mt-5 max-w-2xl text-lg leading-relaxed text-ink-2 first-letter:float-left first-letter:mr-2 first-letter:font-[var(--font-display)] first-letter:text-6xl first-letter:leading-[0.8] first-letter:text-ink">
                  {h.description}
                </p>
                <p className="mt-5 text-sm text-ink-3">{h.address} · Check-in {h.check_in_time.slice(0, 5)} · Check-out {h.check_out_time.slice(0, 5)}</p>
              </Reveal>

              {/* the neighbourhood in pictures */}
              {h.gallery.length > 0 && (
                <Reveal className="mt-14">
                  <p className="eyebrow">Around here, in pictures</p>
                  <div className="mt-4 flex snap-x gap-4 overflow-x-auto pb-3 scrollbar-none">
                    {h.gallery.map((g) => (
                      <figure key={g.photo_url} className="w-64 shrink-0 snap-start sm:w-72">
                        <Photo src={g.photo_url} alt={g.caption} credit={g.photo_credit} showCredit city={h.city_name}
                          className="aspect-[4/3] rounded-2xl" />
                        <figcaption className="mt-2 text-sm">
                          <span className="font-medium">{g.caption}</span>
                          {g.distance_km !== null && <span className="text-ink-3"> · {walkOrRide(g.distance_km)}</span>}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                  <p className="text-xs text-ink-3">Photos of the neighbourhood from Wikimedia Commons, used under their free licences. Listings in our dataset carry no photos of their own.</p>
                </Reveal>
              )}

              {/* neighbourhood */}
              {h.landmarks.length > 0 && (
                <Reveal className="mt-16">
                  <p className="eyebrow">The neighbourhood</p>
                  <h2 className="display mt-2 text-3xl">What's around {h.locality || h.city_name}</h2>
                  <ol className="mt-6 grid gap-x-8 sm:grid-cols-2">
                    {h.landmarks.map((l) => (
                      <li key={l.landmark_id} className="flex items-center gap-4 border-b border-line py-4">
                        <span className="text-xl" aria-hidden>{LANDMARK_ICON[l.category] ?? "✦"}</span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{l.landmark_name}</span>
                          <span className="text-sm text-ink-3">{walkOrRide(l.distance_km)}</span>
                        </span>
                        <Link to={`/stays?landmark_id=${l.landmark_id}&label=${encodeURIComponent(l.landmark_name)}&sort=distance`}
                          className="text-xs text-ink-3 hover:text-sindoor">stays near →</Link>
                      </li>
                    ))}
                  </ol>
                </Reveal>
              )}

              {/* rooms */}
              <section className="mt-16" id="rooms" aria-label="Rooms">
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <p className="eyebrow">Rooms</p>
                    <h2 className="display mt-2 text-3xl">Choose your room</h2>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <input type="date" aria-label="Check-in" min={TODAY} value={checkIn} onChange={(e) => setDates(e.target.value, checkOut)}
                      className="rounded-full border border-line bg-card px-4 py-2" />
                    <input type="date" aria-label="Check-out" min={addDays(checkIn, 1)} value={checkOut} onChange={(e) => setDates(checkIn, e.target.value)}
                      className="rounded-full border border-line bg-card px-4 py-2" />
                    <select aria-label="Rooms" value={rooms} onChange={(e) => setRooms(Number(e.target.value))}
                      className="rounded-full border border-line bg-card px-4 py-2">
                      {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} room{n > 1 ? "s" : ""}</option>)}
                    </select>
                  </div>
                </div>
                <div className="mt-6 space-y-4">
                  {avail.error ? <ErrorNote error={avail.error} /> : !avail.data
                    ? h.room_types.map((r) => <Skeleton key={r.room_type_id} className="h-36" />)
                    : avail.data.map((a) => (
                      <RoomRow key={a.room_type_id} a={a} hotel={h} checkIn={checkIn} checkOut={checkOut} rooms={rooms} adults={adults} />
                    ))}
                </div>
              </section>

              {/* amenities */}
              <Reveal className="mt-16">
                <p className="eyebrow">What's here</p>
                <div className="mt-6 grid gap-8 sm:grid-cols-2">
                  {Object.entries(groupBy(h.amenities, (a) => a.category)).map(([cat, list]) => (
                    <div key={cat}>
                      <p className="display text-xl">{CATEGORY_LABEL[cat] ?? cat}</p>
                      <ul className="mt-2 space-y-1 text-ink-2">{list.map((a) => <li key={a.amenity_id}>— {a.amenity_name}</li>)}</ul>
                    </div>
                  ))}
                </div>
              </Reveal>

              {/* reviews */}
              <Reviews h={h} />

              {/* multimedia stored in the database */}
              {h.media.length > 0 && (
                <Reveal className="mt-16 flex items-center gap-6 rounded-3xl border border-line p-5">
                  <img src={`/api/lab/media/${h.media[0].media_id}`} alt={h.media[0].title} width={96} height={128} loading="lazy" className="h-32 w-24 rounded-xl" />
                  <p className="text-sm text-ink-2">This poster is stored <b className="text-ink">inside PostgreSQL</b> as binary data (<code className="font-mono">bytea</code>) in
                    <code className="font-mono"> lab.hotel_media</code> and served by the API — a small multimedia-database example.</p>
                </Reveal>
              )}

              {/* nearby */}
              {h.nearby.length > 0 && (
                <Reveal className="mt-16">
                  <StarRule />
                  <p className="eyebrow mt-10">Also in {h.city_name}</p>
                  <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
                    {h.nearby.map((n) => (
                      <Link key={n.hotel_id} to={`/stay/${n.hotel_id}`} className="group">
                        <Photo src={n.photo_url} alt="" city={h.city_name} propertyType={n.property_type} seed={n.hotel_id * 97} className="aspect-[4/5] rounded-2xl" />
                        <p className="mt-2 truncate font-medium group-hover:text-sindoor">{n.hotel_name}</p>
                        <p className="text-sm text-ink-3">from {rupees(n.from_price)}</p>
                      </Link>
                    ))}
                  </div>
                </Reveal>
              )}
            </>
          )}
        </div>

        {/* sticky booking card (desktop) */}
        <aside className="hidden lg:block">
          <div className="sticky top-24 rounded-[1.75rem] border border-line bg-card p-6 shadow-[0_30px_60px_-40px_rgb(var(--shadow)/0.6)]">
            <BookingSummaryCard avail={avail.data} checkIn={checkIn} checkOut={checkOut} rooms={rooms} />
          </div>
        </aside>
      </div>

      {/* sticky booking bar (mobile) */}
      <div className="fixed inset-x-0 bottom-[calc(3.6rem+env(safe-area-inset-bottom))] z-30 border-t border-line bg-card/95 px-4 py-3 backdrop-blur md:bottom-0 lg:hidden">
        <BookingSummaryCard avail={avail.data} checkIn={checkIn} checkOut={checkOut} rooms={rooms} compact />
      </div>
    </Page>
  );
}

function BookingSummaryCard({ avail, checkIn, checkOut, rooms, compact = false }:
  { avail?: Availability[]; checkIn: string; checkOut: string; rooms: number; compact?: boolean }) {
  const { t } = useI18n();
  const nights = nightsBetween(checkIn, checkOut);
  const best = avail?.filter((a) => a.stay_total).sort((a, b) => Number(a.stay_total) - Number(b.stay_total))[0];
  const scroll = () => document.getElementById("rooms")?.scrollIntoView({ behavior: "smooth" });
  if (compact) {
    return (
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-lg font-semibold tabular">{best ? rupees(best.stay_total) : "—"}</p>
          <p className="text-xs text-ink-3">{nights} night{nights > 1 ? "s" : ""} · {rooms} room{rooms > 1 ? "s" : ""} · incl. GST</p>
        </div>
        <button onClick={scroll} className="rounded-full bg-sindoor px-6 py-3 font-semibold text-sindoor-ink">{t("reserve")}</button>
      </div>
    );
  }
  return (
    <>
      <p className="eyebrow">Your stay</p>
      <p className="display mt-2 text-2xl">{longDate(checkIn)}</p>
      <p className="text-ink-3">to {longDate(checkOut)} · {nights} night{nights > 1 ? "s" : ""}</p>
      <div className="my-5 h-px bg-line" />
      {best ? (
        <>
          <p className="text-sm text-ink-3">Best available · {best.type_name}</p>
          <p className="mt-1 text-3xl font-semibold tabular">{rupees(best.stay_total)}</p>
          <p className="text-xs text-ink-3">for {rooms} room{rooms > 1 ? "s" : ""}, all taxes included</p>
        </>
      ) : avail ? <p className="font-medium text-sindoor">Sold out for these dates. Try nearby dates.</p> : <Skeleton className="h-16" />}
      <button onClick={scroll} className="mt-5 w-full rounded-2xl bg-sindoor py-3.5 font-semibold text-sindoor-ink">Choose a room</button>
      <p className="mt-3 text-center text-xs text-ink-3">Free cancellation up to 7 days before check-in</p>
    </>
  );
}

function RoomRow({ a, hotel, checkIn, checkOut, rooms, adults }:
  { a: Availability; hotel: HotelDetail; checkIn: string; checkOut: string; rooms: number; adults: number }) {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const rt = hotel.room_types.find((r) => r.room_type_id === a.room_type_id);
  const enough = a.free_rooms >= rooms;
  const fits = a.max_adults * rooms >= adults;
  const quote = useQuery({
    queryKey: ["quote", a.room_type_id, checkIn, checkOut, rooms],
    queryFn: () => api.quote(a.room_type_id, checkIn, checkOut, rooms),
    enabled: open,
  });
  const book = () => {
    const q = new URLSearchParams({ hotel: String(hotel.hotel_id), room_type: String(a.room_type_id), check_in: checkIn,
      check_out: checkOut, rooms: String(rooms), adults: String(Math.min(adults, a.max_adults * rooms)) });
    nav(`/checkout?${q}`);
  };
  return (
    <article className={`rounded-3xl border p-5 transition ${enough ? "border-line bg-card" : "border-dashed border-line bg-paper-2/40"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="display-tight text-2xl">{a.type_name}</h3>
          <p className="mt-1 text-sm text-ink-2">
            {rt?.bed_type.toLowerCase()} bed · {rt?.area_sqft} sq ft · up to {a.max_adults} adults{a.max_children ? ` + ${a.max_children} child` : ""}
          </p>
          <p className={`mt-2 text-sm font-medium ${enough ? (a.free_rooms <= 2 ? "text-sindoor" : "text-peacock") : "text-ink-3"}`}>
            {enough ? (a.free_rooms <= 2 ? `Only ${a.free_rooms} left for your dates` : `${a.free_rooms} of ${a.total_rooms} free`) : `${a.free_rooms} free — not enough for ${rooms} rooms`}
          </p>
          {!fits && enough && <p className="text-xs text-ink-3">For {adults} adults you'll need more rooms.</p>}
        </div>
        <div className="text-right">
          <p className="text-xs text-ink-3">list price {rupees(a.base_price)} / night</p>
          <p className="text-2xl font-semibold tabular">{a.stay_total ? rupees(a.stay_total) : "—"}</p>
          <p className="text-xs text-ink-3">total incl. GST</p>
          <div className="mt-3 flex justify-end gap-2">
            <button onClick={() => setOpen((o) => !o)} className="rounded-full border border-line px-4 py-2 text-sm" aria-expanded={open}>
              {open ? "Hide" : "Price"} breakdown
            </button>
            <button disabled={!enough} onClick={book} className="rounded-full bg-sindoor px-5 py-2 text-sm font-semibold text-sindoor-ink disabled:opacity-30">
              Reserve
            </button>
          </div>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="mt-5">{quote.error ? <ErrorNote error={quote.error} compact /> : quote.data ? <PriceTable q={quote.data} /> : <Skeleton className="h-28" />}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </article>
  );
}

/** Night-by-night honesty: why tonight costs what it costs */
export function PriceTable({ q }: { q: NonNullable<Awaited<ReturnType<typeof api.quote>>> }) {
  return (
    <div className="overflow-x-auto rounded-2xl bg-paper-2/60 p-4">
      <table className="w-full min-w-[480px] text-sm tabular">
        <thead className="text-left text-xs text-ink-3">
          <tr><th className="pb-2">Night</th><th>Season</th><th className="text-right">List</th><th className="text-right">× season</th>
            <th className="text-right">× weekend</th><th className="text-right">Rate</th><th className="text-right">GST</th></tr>
        </thead>
        <tbody>
          {q.nights.map((n) => (
            <tr key={n.night} className="border-t border-line">
              <td className="py-2">{n.day_name} {n.night.slice(8)}/{n.night.slice(5, 7)}</td>
              <td className="text-ink-2">{n.season_name ?? "—"}</td>
              <td className="text-right">{rupees(n.base_price)}</td>
              <td className={`text-right ${n.season_multiplier > 1 ? "text-sindoor" : n.season_multiplier < 1 ? "text-peacock" : ""}`}>{Number(n.season_multiplier).toFixed(2)}</td>
              <td className="text-right">{Number(n.weekend_multiplier).toFixed(2)}</td>
              <td className="text-right font-medium">{rupees(n.nightly_rate)}</td>
              <td className="text-right text-ink-2">{Math.round(n.gst_rate * 100)}%</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="text-sm">
          <tr className="border-t border-ink/20"><td colSpan={5} className="pt-3 text-ink-2">Room charges × {q.rooms}</td><td colSpan={2} className="pt-3 text-right">{rupees(q.subtotal, true)}</td></tr>
          <tr><td colSpan={5} className="text-ink-2">GST (0% ≤ ₹1,000 · 5% ≤ ₹7,500 · 18% above, per night)</td><td colSpan={2} className="text-right">{rupees(q.tax, true)}</td></tr>
          <tr className="text-base font-semibold"><td colSpan={5} className="pt-2">Total</td><td colSpan={2} className="pt-2 text-right">{rupees(q.total, true)}</td></tr>
        </tfoot>
      </table>
    </div>
  );
}

function Reviews({ h }: { h: HotelDetail }) {
  const total = h.rating_breakdown.reduce((s, r) => s + r.reviews, 0);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    setExpanded(false);
  }, [h.hotel_id]);
  const shown = useMemo(() => (expanded ? h.reviews : h.reviews.slice(0, 3)), [expanded, h.reviews]);
  if (!total) return null;
  return (
    <Reveal className="mt-16">
      <p className="eyebrow">Guests say</p>
      <div className="mt-6 grid gap-10 md:grid-cols-[220px_1fr]">
        <div>
          <p className="display text-6xl">{Number(h.avg_rating).toFixed(1)}</p>
          <p className="text-sm text-ink-3">{total.toLocaleString("en-IN")} verified stays</p>
          <div className="mt-4 space-y-1.5">
            {[5, 4, 3, 2, 1].map((s) => {
              const n = h.rating_breakdown.find((r) => r.rating === s)?.reviews ?? 0;
              return (
                <div key={s} className="flex items-center gap-2 text-xs">
                  <span className="w-3 tabular">{s}</span>
                  <span className="h-1.5 flex-1 rounded-full bg-line"><span className="block h-full rounded-full bg-peacock" style={{ width: `${(n / total) * 100}%` }} /></span>
                  <span className="w-8 text-right text-ink-3 tabular">{n}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="space-y-6">
          {shown.map((r, i) => (
            <blockquote key={i} className="border-l-2 border-haldi pl-5">
              <p className="font-semibold">{"★".repeat(r.rating)} <span className="ml-1">{r.title}</span></p>
              {r.body && <p className="mt-1 text-ink-2">{r.body}</p>}
              <footer className="mt-2 text-xs text-ink-3">{r.first_name} {r.last_initial}.{r.from_city ? ` from ${r.from_city}` : ""} · {r.nights} night{r.nights > 1 ? "s" : ""} · {r.posted}</footer>
            </blockquote>
          ))}
          {h.reviews.length > 3 && <button onClick={() => setExpanded((e) => !e)} className="text-sm font-semibold text-sindoor">{expanded ? "Show fewer" : "Show more reviews"}</button>}
        </div>
      </div>
    </Reveal>
  );
}

function groupBy<T>(list: T[], key: (t: T) => string) {
  return list.reduce<Record<string, T[]>>((acc, x) => ((acc[key(x)] ??= []).push(x), acc), {});
}
