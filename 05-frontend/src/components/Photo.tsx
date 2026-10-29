/**
 * Real photos (Wikimedia Commons, free licences) with the poster art as a
 * graceful fallback: while loading, if offline, or if a place has no photo.
 */
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Poster } from "../art/Poster";

type PhotoProps = {
  src?: string | null;
  alt: string;
  credit?: string | null;
  city?: string;
  propertyType?: string;
  seed?: number;
  className?: string;
  showCredit?: boolean;
  eager?: boolean;
  children?: ReactNode;
};

export function Photo({ src, alt, credit, city, propertyType, seed = 7, className = "", showCredit = false, eager = false, children }: PhotoProps) {
  const [state, setState] = useState<"loading" | "ok" | "error">(src ? "loading" : "error");
  useEffect(() => setState(src ? "loading" : "error"), [src]);

  return (
    <div className={`relative overflow-hidden bg-paper-2 ${className}`}>
      {state !== "ok" && <Poster city={city} propertyType={propertyType} seed={seed} className="absolute inset-0" />}
      {src && state !== "error" && (
        <img
          src={src}
          alt={alt}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          onLoad={() => setState("ok")}
          onError={() => setState("error")}
          className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${state === "ok" ? "opacity-100" : "opacity-0"}`}
        />
      )}
      {showCredit && credit && state === "ok" && <Credit text={credit} />}
      {children}
    </div>
  );
}

export function Credit({ text, className = "" }: { text: string; className?: string }) {
  return (
    <span className={`pointer-events-none absolute bottom-1.5 right-2 max-w-[70%] truncate text-[0.6rem] text-white/80 drop-shadow ${className}`}
      title={`Photo: ${text}`}>
      Photo: {text}
    </span>
  );
}

export type HeroSlide = { landmark_id: number; landmark_name: string; city_name: string; city_id: number; photo_url_hd: string; photo_credit: string };

/** Full-bleed HD slideshow: crossfade + slow zoom ("Ken Burns"), calm under reduced motion. */
export function HeroSlideshow({ slides, interval = 6500 }: { slides: HeroSlide[]; interval?: number }) {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);
  const [ready, setReady] = useState<Set<number>>(new Set());

  // preload the next slide so every transition is instant
  useEffect(() => {
    slides.forEach((s, k) => {
      if (k > i + 1 || ready.has(k)) return;
      const img = new Image();
      img.onload = () => setReady((r) => new Set(r).add(k));
      img.src = s.photo_url_hd;
    });
  }, [i, slides]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (slides.length < 2) return;
    const id = setInterval(() => setI((x) => {
      const next = (x + 1) % slides.length;
      return ready.has(next) ? next : x;            // wait for the next photo rather than show a blank
    }), reduce ? interval * 1.6 : interval);
    return () => clearInterval(id);
  }, [slides.length, interval, reduce, ready]);

  const s = slides[i];
  return (
    <div className="absolute inset-0 overflow-hidden bg-ink" aria-hidden={false}>
      <Poster city="Mumbai" seed={1912} palette="dusk" className="absolute inset-0" />
      <AnimatePresence initial={false}>
        {s && ready.has(i) && (
          <motion.img
            key={s.landmark_id}
            src={s.photo_url_hd}
            alt={`${s.landmark_name}, ${s.city_name}`}
            className="absolute inset-0 h-full w-full object-cover"
            initial={{ opacity: 0, scale: reduce ? 1 : 1.12 }}
            animate={{ opacity: 1, scale: reduce ? 1 : 1.0 }}
            exit={{ opacity: 0 }}
            transition={{ opacity: { duration: 1.4 }, scale: { duration: interval / 1000 + 2, ease: "linear" } }}
          />
        )}
      </AnimatePresence>
      {s && (
        <div className="absolute bottom-5 right-5 z-10 hidden text-right sm:block">
          <Link to={`/stays?city_id=${s.city_id}&label=${encodeURIComponent(s.city_name)}`}
            className="pointer-events-auto rounded-full bg-black/35 px-3 py-1.5 text-xs font-medium text-white backdrop-blur hover:bg-black/55">
            {s.landmark_name} · {s.city_name} →
          </Link>
          <p className="mt-1 text-[0.6rem] text-white/70">Photo: {s.photo_credit}</p>
        </div>
      )}
      <div className="absolute bottom-5 left-1/2 z-10 flex -translate-x-1/2 gap-1.5 sm:left-auto sm:right-5 sm:top-24 sm:bottom-auto sm:translate-x-0 sm:flex-col">
        {slides.map((x, k) => (
          <button key={x.landmark_id} onClick={() => ready.has(k) && setI(k)} aria-label={`Show ${x.landmark_name}`}
            className={`h-1.5 rounded-full transition-all sm:h-6 sm:w-1.5 ${k === i ? "w-6 bg-white sm:h-10" : "w-1.5 bg-white/45 hover:bg-white/80"}`} />
        ))}
      </div>
    </div>
  );
}
