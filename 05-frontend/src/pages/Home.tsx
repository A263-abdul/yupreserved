import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import { Poster } from "../art/Poster";
import { StarRule } from "../components/brand";
import { PosterCard } from "../components/cards";
import { HeroSlideshow, Photo } from "../components/Photo";
import { ErrorNote, Skeleton } from "../components/feedback";
import { Page, Reveal, SetType } from "../components/motion";
import { SearchBar } from "../components/search";
import { api } from "../lib/api";
import { count, rupees, shortDate } from "../lib/format";
import { useI18n } from "../lib/i18n";

const MOOD_ART: Record<string, { city: string; seed: number }> = {
  heritage: { city: "Udaipur", seed: 11 }, hills: { city: "Shimla", seed: 4 }, beach: { city: "Goa", seed: 8 },
  water: { city: "Alleppey", seed: 21 }, spiritual: { city: "Varanasi", seed: 5 }, workation: { city: "Bangalore", seed: 9 },
  family: { city: "Jaipur", seed: 14 }, budget: { city: "Pondicherry", seed: 3 },
};

export default function Home() {
  const { t, lang } = useI18n();
  const featured = useQuery({ queryKey: ["featured"], queryFn: api.featured });
  const stats = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const moods = useQuery({ queryKey: ["moods"], queryFn: api.moods });

  return (
    <Page>
      {/* ── hero: the Gateway of India at dusk, layers drifting on scroll ── */}
      <section className="relative -mt-16 min-h-[100svh] overflow-hidden md:-mt-16">
        {featured.data?.hero?.length
          ? <HeroSlideshow slides={featured.data.hero} />
          : <Poster city="Mumbai" seed={1912} palette="dusk" parallax className="absolute inset-0" title="The Gateway of India at dusk" />}
        {/* cinematic grade: keeps white type readable on any photo, in light and dark themes */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/55 via-black/25 to-black/70" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-b from-transparent to-paper" />
        <div className="relative mx-auto flex min-h-[100svh] max-w-7xl flex-col justify-end px-4 pb-14 pt-32 sm:px-6">
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }} className="eyebrow !text-white/80">
            {count(stats.data?.hotels)} stays · {count(stats.data?.cities)} cities · {count(stats.data?.states)} states & UTs
          </motion.p>
          <h1 className={`mt-4 max-w-4xl text-[clamp(2.9rem,8.5vw,7.4rem)] leading-[0.92] text-[#FFF6EC] drop-shadow-[0_2px_24px_rgba(0,0,0,0.35)] ${lang === "hi" ? "hindi" : "display"}`}>
            <SetType lines={[t("heroLine1"), <em key="2" className="text-[#F2B544]">{t("heroLine2")}</em>, t("heroLine3")]} />
          </h1>
          <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7, duration: 0.8 }}
            className="mt-5 max-w-xl text-lg text-white/85">
            {t("heroSub")}
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.85, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 mt-8">
            <SearchBar />
          </motion.div>
          <div className="relative z-10 mt-5 hidden flex-wrap gap-2 text-sm text-white/85 sm:flex">
            <span>Try</span>
            {[["near Gateway of India", "/stays?landmark_id=1&label=Gateway%20of%20India&sort=distance"],
              ["heritage palace", "/stays?mood=heritage"], ["quiet hill stay", "/stays?q=quiet%20hill%20stay"],
              ["houseboat", "/stays?mood=water"]].map(([label, to]) => (
              <Link key={to} to={to} className="rounded-full border border-white/30 bg-black/25 px-3 py-1 text-white backdrop-blur transition hover:bg-white hover:text-ink">“{label}”</Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── moods ── */}
      <section className="mx-auto max-w-7xl px-4 pt-16 sm:px-6">
        <Reveal><p className="eyebrow">{t("moods")}</p></Reveal>
        <div className="mt-5 flex gap-4 overflow-x-auto pb-4 scrollbar-none snap-x">
          {(moods.data ?? Array.from({ length: 8 }, (_, i) => ({ key: `s${i}`, label: "" }))).map((m, i) => (
            <Reveal key={m.key} delay={i * 0.05} className="snap-start">
              {m.label ? (
                <Link to={`/stays?mood=${m.key}`} className="group block w-40 shrink-0">
                  <Poster city={MOOD_ART[m.key]?.city} seed={MOOD_ART[m.key]?.seed ?? i}
                    className="aspect-[3/4] rounded-[1.4rem] transition duration-500 group-hover:-translate-y-1 group-hover:rotate-[-1deg]" />
                  <p className="mt-3 font-medium group-hover:text-sindoor">{m.label}</p>
                </Link>
              ) : <Skeleton className="aspect-[3/4] w-40" />}
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── signature stays: slow, editorial ── */}
      <section className="mx-auto max-w-7xl px-4 pt-24 sm:px-6">
        <Reveal className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">{t("signature")}</p>
            <h2 className="display mt-2 max-w-2xl text-[clamp(2.2rem,5vw,3.8rem)] leading-[1]">{t("signatureSub")}</h2>
          </div>
          <Link to="/stays?signature_only=true" className="font-semibold text-sindoor">See all eighteen →</Link>
        </Reveal>
        {featured.error ? <div className="mt-10"><ErrorNote error={featured.error} onRetry={() => featured.refetch()} /></div> : (
          <div className="mt-12 grid gap-x-8 gap-y-14 sm:grid-cols-2 lg:grid-cols-3">
            {(featured.data?.stays.slice(0, 6) ?? Array.from({ length: 6 })).map((h, i) => (
              <Reveal key={i} delay={(i % 3) * 0.08} className={i % 3 === 1 ? "lg:translate-y-16" : ""}>
                {h ? <PosterCard h={h as any} index={i} /> : <Skeleton className="aspect-[4/5]" />}
              </Reveal>
            ))}
          </div>
        )}
      </section>

      {/* ── a quote-sized pause ── */}
      <section className="mx-auto max-w-4xl px-4 pt-40 text-center sm:px-6">
        <Reveal>
          <StarRule className="mx-auto max-w-xs" />
          <p className="display mt-10 text-[clamp(1.8rem,4vw,3rem)] leading-tight">
            “Filter coffee on a verandah, the Arabian Sea in front, and a ferry horn somewhere to the left.”
          </p>
          <p className="mt-6 text-ink-3">— a guest at Samudra Mahal, Colaba</p>
        </Reveal>
      </section>

      {/* ── cities ── */}
      <section className="mx-auto max-w-7xl px-4 pt-32 sm:px-6">
        <Reveal><p className="eyebrow">{t("cities")}</p></Reveal>
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {(featured.data?.cities ?? Array.from({ length: 8 })).map((c: any, i) => (
            <Reveal key={c?.city_id ?? i} delay={(i % 4) * 0.06}>
              {c ? (
                <Link to={`/stays?city_id=${c.city_id}&label=${encodeURIComponent(c.city_name)}`} className="group relative block overflow-hidden rounded-[1.5rem]">
                  <Photo src={c.photo_url} alt={c.city_name} credit={c.photo_credit} city={c.city_name} seed={c.city_id * 13}
                    className="aspect-[5/6] [&>img]:transition [&>img]:duration-700 group-hover:[&>img]:scale-[1.05]" />
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/80 to-transparent p-4 pt-12 text-paper">
                    <p className="display text-2xl text-[#FFF6EC]">{c.city_name}</p>
                    <p className="text-xs text-[#FFF6EC]/80">{c.hotels} stays · from {rupees(c.from_price)}</p>
                  </div>
                </Link>
              ) : <Skeleton className="aspect-[5/6]" />}
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── festival calendar: honest about price rises ── */}
      <section className="mx-auto max-w-7xl px-4 pt-32 sm:px-6">
        <div className="grid gap-10 rounded-[2rem] bg-ink p-8 text-paper sm:p-12 lg:grid-cols-[1fr_1.4fr]">
          <Reveal>
            <p className="eyebrow !text-paper/60">{t("festive")}</p>
            <h2 className="display mt-3 text-4xl leading-tight text-paper">{t("festiveSub")}</h2>
            <p className="mt-4 text-paper/70">
              Every price is built night by night: list price × season × weekend, then GST at the slab for that night’s tariff.
              No surprises at checkout.
            </p>
          </Reveal>
          <div className="grid gap-3 sm:grid-cols-2">
            {(featured.data?.seasons ?? []).map((s, i) => (
              <Reveal key={s.season_name} delay={i * 0.06}>
                <div className="ticket-edge rounded-2xl bg-paper/[0.07] p-5">
                  <p className="text-sm text-paper/60">{shortDate(s.start_date)} – {shortDate(s.end_date)}</p>
                  <p className="display mt-1 text-2xl text-paper">{s.season_name.replace(/ 20\d\d$/, "")}</p>
                  <p className={`mt-3 text-sm font-semibold ${s.multiplier > 1 ? "text-haldi" : "text-[#7fd1c7]"}`}>
                    {s.multiplier > 1 ? `Prices × ${s.multiplier}` : `Save ${Math.round((1 - s.multiplier) * 100)}%`}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── trust strip ── */}
      <section className="mx-auto grid max-w-7xl gap-8 px-4 pt-24 sm:grid-cols-3 sm:px-6">
        {[["UPI first", "Pay with any UPI app. Cards, net banking and pay-at-hotel too."],
          ["Price, explained", "Season, weekend and GST shown for every single night before you pay."],
          ["Free cancellation", "Full refund up to 7 days before check-in, half up to 2 days."]].map(([h, p], i) => (
          <Reveal key={h} delay={i * 0.08}>
            <p className="display text-2xl">{h}</p>
            <p className="mt-2 text-ink-2">{p}</p>
          </Reveal>
        ))}
      </section>
    </Page>
  );
}
