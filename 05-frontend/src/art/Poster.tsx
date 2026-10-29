/**
 * Poster — procedural "vintage railway poster" scenes of Indian places.
 *
 * Flat layered silhouettes (sky → sun → far hills → landmark → foreground),
 * drawn as SVG so they weigh a few kB, stay crisp at any size and load
 * instantly on a slow connection. Each city has a motif; each hotel gets its
 * own seed so no two cards look identical. The hero version moves its layers
 * at different speeds on scroll (parallax), and stays still for
 * prefers-reduced-motion.
 */
import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";

// ── palettes: time of day / weather ────────────────────────────────────────
type Palette = { sky: [string, string]; sun: string; far: string; mid: string; near: string; water: string; accent: string; ink: string };
export const PALETTES = {
  dawn:    { sky: ["#F5C9A8", "#FBE7CF"], sun: "#F7F0E0", far: "#E3A98C", mid: "#C97B63", near: "#7E4A47", water: "#E8B9A0", accent: "#F2B544", ink: "#3B2430" },
  noon:    { sky: ["#F2C14E", "#F8E2A6"], sun: "#FFF6E0", far: "#E6A55A", mid: "#C4472B", near: "#6E2F2A", water: "#2F6F73", accent: "#1F6F6B", ink: "#2A1A1A" },
  dusk:    { sky: ["#C4472B", "#F2A65A"], sun: "#FCE3B0", far: "#8E3B46", mid: "#5A2A4A", near: "#2B1B33", water: "#7A3B4E", accent: "#F2B544", ink: "#1E1226" },
  monsoon: { sky: ["#7D8FB3", "#C9D3E3"], sun: "#EEF2F7", far: "#92A5C4", mid: "#4F6E8A", near: "#1F3B4D", water: "#5E7F99", accent: "#2F8A7E", ink: "#13222E" },
  night:   { sky: ["#141833", "#2B3266"], sun: "#F3E7C9", far: "#2C3466", mid: "#1D2350", near: "#0E1130", water: "#232A5C", accent: "#F0B847", ink: "#080A1E" },
  teal:    { sky: ["#BFE0D6", "#EAF4EC"], sun: "#FFF8E8", far: "#8CC3B4", mid: "#2F8A7E", near: "#14504B", water: "#3E9C93", accent: "#E3A72F", ink: "#0E2E2B" },
} satisfies Record<string, Palette>;
export type PaletteName = keyof typeof PALETTES;

// ── motif per city ─────────────────────────────────────────────────────────
type Motif = "gateway" | "charminar" | "palace" | "beach" | "fort" | "ghats" | "backwater" | "tea" | "lake"
  | "desert" | "indiagate" | "pines" | "bridge" | "river" | "colonial" | "city";

const CITY_MOTIF: Record<string, Motif> = {
  Mumbai: "gateway", "Navi Mumbai": "gateway", Hyderabad: "charminar", Udaipur: "palace", Goa: "beach",
  Puri: "beach", Gokarna: "beach", Kovalam: "beach", Varkala: "beach", "Port Blair": "beach", Havelock: "beach",
  Jaipur: "fort", Jodhpur: "fort", Chittorgarh: "fort", Gwalior: "fort", Varanasi: "ghats", Haridwar: "ghats",
  Ujjain: "ghats", Pushkar: "ghats", Alleppey: "backwater", Kumarakom: "backwater", Kochi: "backwater",
  Munnar: "tea", Darjeeling: "tea", Wayanad: "tea", Coorg: "tea", Chikmagalur: "tea", Srinagar: "lake",
  Nainital: "lake", Kodaikanal: "lake", Ooty: "lake", Jaisalmer: "desert", Bikaner: "desert", Delhi: "indiagate",
  "New Delhi": "indiagate", Shimla: "pines", Manali: "pines", Mussoorie: "pines", Dharamshala: "pines",
  Gangtok: "pines", Leh: "pines", Kolkata: "bridge", Rishikesh: "river", Pondicherry: "colonial",
  Agra: "palace", Mysore: "palace", Amritsar: "palace",
};

const TYPE_MOTIF: Record<string, Motif> = {
  Houseboat: "backwater", "Luxury Yacht": "backwater", "Beach Hut": "beach", Palace: "palace",
  Haveli: "fort", "Heritage Hotel": "palace", Tent: "pines", Cottage: "pines", "Farm Stay": "tea",
};

export function motifFor(city?: string, propertyType?: string): Motif {
  return (city && CITY_MOTIF[city]) || (propertyType && TYPE_MOTIF[propertyType]) || "city";
}

const MOTIF_PALETTE: Record<Motif, PaletteName> = {
  gateway: "dusk", charminar: "noon", palace: "dawn", beach: "teal", fort: "noon", ghats: "dusk",
  backwater: "teal", tea: "teal", lake: "monsoon", desert: "noon", indiagate: "dawn", pines: "monsoon",
  bridge: "dusk", river: "teal", colonial: "dawn", city: "dawn",
};

// ── seeded randomness ──────────────────────────────────────────────────────
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** a smooth ridge line across the canvas (drawn wide, so it also fills landscape posters) */
function ridge(r: () => number, base: number, amp: number, peaks: number, bottom = 500) {
  const pts: [number, number][] = [];
  const n = peaks * 3;
  for (let i = 0; i <= n; i++) pts.push([-400 + (i / n) * 1200, base - r() * amp]);
  let d = `M-400 ${bottom} L-400 ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1];
    const [x1, y1] = pts[i];
    const mx = (x0 + x1) / 2;
    d += ` C${mx} ${y0} ${mx} ${y1} ${x1} ${y1}`;
  }
  return `${d} L800 ${bottom} Z`;
}

const waves = (y: number, color: string, opacity = 0.35, n = 7) => (
  <g stroke={color} strokeWidth="1.6" fill="none" opacity={opacity} strokeLinecap="round">
    {Array.from({ length: n }, (_, i) => (
      <path key={i} d={`M${20 + (i * 53) % 360} ${y + (i % 3) * 14} q8 -5 16 0 t16 0`} />
    ))}
  </g>
);

const palm = (x: number, y: number, s: number, c: string, lean = 1) => (
  <g transform={`translate(${x} ${y}) scale(${s * lean} ${s})`} fill={c}>
    <path d="M0 0 C4 -40 10 -80 22 -118 L26 -117 C16 -80 10 -40 6 0 Z" />
    {[-60, -25, 10, 45, 80, 130].map((a, i) => (
      <path key={i} transform={`translate(24 -118) rotate(${a})`} d="M0 0 C18 -10 40 -6 56 8 C38 0 18 0 0 4 Z" />
    ))}
  </g>
);

const pine = (x: number, y: number, s: number, c: string, key?: number) => (
  <path key={key} transform={`translate(${x} ${y}) scale(${s})`} fill={c}
    d="M0 0 L-3 0 L-3 -8 L-16 -8 L-4 -22 L-12 -22 L-2 -36 L-8 -36 L0 -52 L8 -36 L2 -36 L12 -22 L4 -22 L16 -8 L3 -8 L3 0 Z" />
);

const boat = (x: number, y: number, s: number, c: string) => (
  <g transform={`translate(${x} ${y}) scale(${s})`} fill={c}>
    <path d="M-26 0 Q0 10 26 0 L20 6 Q0 12 -20 6 Z" />
    <path d="M0 -2 L0 -34 L16 -6 Z" opacity=".85" />
  </g>
);

// ── motifs (mid-ground landmark silhouettes) ───────────────────────────────
function MotifShape({ motif, p, r }: { motif: Motif; p: Palette; r: () => number }) {
  switch (motif) {
    case "gateway":
      return (
        <g fill={p.mid}>
          <rect x="120" y="250" width="160" height="120" />
          <path d="M175 370 L175 300 Q200 268 225 300 L225 370 Z" fill={p.sky[1]} opacity=".9" />
          {[120, 160, 240, 280].map((x, i) => (
            <g key={i}><rect x={x - 9} y={i % 3 === 0 ? 220 : 236} width="18" height="40" /><circle cx={x} cy={i % 3 === 0 ? 218 : 234} r="10" /></g>
          ))}
          <rect x="110" y="246" width="180" height="8" />
          <path d="M185 250 Q200 226 215 250 Z" />
        </g>
      );
    case "charminar":
      return (
        <g fill={p.mid}>
          <rect x="135" y="270" width="130" height="110" />
          {[150, 200, 250].map((x) => <path key={x} d={`M${x - 16} 380 L${x - 16} 330 Q${x} 300 ${x + 16} 330 L${x + 16} 380 Z`} fill={p.sky[1]} opacity=".85" />)}
          {[132, 268].map((x) => (
            <g key={x}><rect x={x - 8} y="170" width="16" height="210" /><circle cx={x} cy="166" r="11" /><rect x={x - 1} y="140" width="2" height="18" />
              {[210, 250, 290].map((y) => <rect key={y} x={x - 12} y={y} width="24" height="4" />)}</g>
          ))}
          <rect x="130" y="262" width="140" height="10" />
        </g>
      );
    case "palace":
      return (
        <g fill={p.mid}>
          <rect x="70" y="300" width="260" height="70" />
          <rect x="120" y="262" width="160" height="44" />
          {[100, 160, 240, 300].map((x) => <g key={x}><rect x={x - 12} y="282" width="24" height="22" /><path d={`M${x - 14} 284 Q${x} 258 ${x + 14} 284 Z`} /></g>)}
          <path d="M170 264 Q200 214 230 264 Z" />
          <rect x="198" y="204" width="4" height="14" />
          {[90, 130, 170, 210, 250, 290].map((x) => <rect key={x} x={x} y="320" width="10" height="16" rx="5" fill={p.sky[1]} opacity=".7" />)}
        </g>
      );
    case "fort":
      return (
        <g fill={p.mid}>
          <path d={ridge(r, 330, 30, 4, 420)} fill={p.far} />
          <path d="M40 340 L40 290 L360 270 L360 340 Z" />
          {Array.from({ length: 16 }, (_, i) => <rect key={i} x={40 + i * 20} y={286 - i * 1.25 - 10} width="10" height="12" />)}
          {[90, 200, 310].map((x, i) => <g key={x}><rect x={x - 16} y={248 - i * 6} width="32" height="60" /><path d={`M${x - 18} ${250 - i * 6} Q${x} ${222 - i * 6} ${x + 18} ${250 - i * 6} Z`} /></g>)}
        </g>
      );
    case "ghats":
      return (
        <g fill={p.mid}>
          {[0, 1, 2, 3, 4, 5].map((i) => <rect key={i} x={-400} y={330 + i * 8} width="1200" height="4" opacity=".55" />)}
          {[60, 140, 230, 320].map((x, i) => (
            <g key={x}><rect x={x - 22} y={250 - (i % 2) * 20} width="44" height={90 + (i % 2) * 20} />
              <path d={`M${x - 20} ${252 - (i % 2) * 20} Q${x} ${190 - (i % 2) * 30} ${x + 20} ${252 - (i % 2) * 20} Z`} />
              <rect x={x - 1} y={180 - (i % 2) * 32} width="2" height="16" /><path d={`M${x + 1} ${180 - (i % 2) * 32} l10 4 l-10 4 Z`} fill={p.accent} /></g>
          ))}
        </g>
      );
    case "indiagate":
      return (
        <g fill={p.mid}>
          <rect x="140" y="210" width="120" height="170" />
          <path d="M175 380 L175 290 Q200 254 225 290 L225 380 Z" fill={p.sky[1]} opacity=".9" />
          <rect x="132" y="200" width="136" height="14" />
          <rect x="160" y="184" width="80" height="18" />
          <path d="M180 186 Q200 168 220 186 Z" />
        </g>
      );
    case "bridge":
      return (
        <g fill="none" stroke={p.mid} strokeWidth="6">
          <path d="M-400 330 L800 330" strokeWidth="10" />
          <path d="M90 330 L90 190 M310 330 L310 190" strokeWidth="12" />
          <path d="M0 290 Q90 180 200 300 Q310 180 400 290" />
          {Array.from({ length: 14 }, (_, i) => <path key={i} d={`M${20 + i * 26} 330 L${20 + i * 26} ${300 - Math.abs(Math.sin(i / 2.2)) * 60}`} strokeWidth="2" />)}
        </g>
      );
    case "colonial":
      return (
        <g fill={p.mid}>
          {[0, 1, 2].map((i) => (
            <g key={i}><rect x={30 + i * 120} y={250 + (i % 2) * 14} width="110" height="130" />
              {[0, 1, 2].map((w) => <rect key={w} x={44 + i * 120 + w * 30} y={276 + (i % 2) * 14} width="18" height="34" rx="2" fill={p.sky[1]} opacity=".75" />)}
              <rect x={24 + i * 120} y={244 + (i % 2) * 14} width="122" height="8" /></g>
          ))}
          {[60, 180, 300].map((x) => <circle key={x} cx={x} cy={250} r={18} fill={p.accent} opacity=".9" />)}
        </g>
      );
    case "city":
      return (
        <g fill={p.mid}>
          {Array.from({ length: 31 }, (_, i) => {
            const h = 60 + r() * 110;
            return <rect key={i} x={-390 + i * 38} y={350 - h} width={30 + r() * 8} height={h} />;
          })}
          <circle cx="90" cy="300" r="42" fill={p.near} opacity=".9" />
          <circle cx="320" cy="296" r="50" fill={p.near} opacity=".9" />
        </g>
      );
    default:
      return null;
  }
}

// ── scene ──────────────────────────────────────────────────────────────────
type Layers = { sky: ReactNode; far: ReactNode; mid: ReactNode; near: ReactNode };

function scene(motif: Motif, p: Palette, seed: number, uid: string): Layers {
  const r = rng(seed);
  const sunX = 70 + r() * 260, sunY = 120 + r() * 70, sunR = 38 + r() * 26;
  const sky = (
    <>
      <defs>
        <linearGradient id={`${uid}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={p.sky[0]} /><stop offset="1" stopColor={p.sky[1]} />
        </linearGradient>
      </defs>
      <rect x="-400" width="1200" height="500" fill={`url(#${uid}-sky)`} />
      <circle cx={sunX} cy={sunY} r={sunR * 1.9} fill={p.sun} opacity=".18" />
      <circle cx={sunX} cy={sunY} r={sunR} fill={p.sun} />
      {/* railway-poster sun rays: thin horizontal bands */}
      <g fill={p.sky[1]} opacity=".55">
        {[0, 1, 2, 3].map((i) => <rect key={i} x={sunX - sunR - 6} y={sunY + sunR * 0.15 + i * 9} width={sunR * 2 + 12} height="2.2" />)}
      </g>
      {motif === "lake" || motif === "pines" ? (
        <g fill={p.sun} opacity=".5">{[0, 1, 2].map((i) => <ellipse key={i} cx={60 + i * 130 + r() * 30} cy={80 + r() * 50} rx={36 + r() * 20} ry="9" />)}</g>
      ) : null}
    </>
  );

  const far = (() => {
    if (["pines", "lake", "river", "tea"].includes(motif))
      return (<><path d={ridge(r, 250, 120, 5)} fill={p.far} /><path d="M140 170 l26 -40 l26 40 Z M260 190 l20 -30 l20 30 Z" fill={p.sun} opacity={motif === "pines" || motif === "lake" ? 0.7 : 0} /></>);
    if (motif === "desert") return <path d={ridge(r, 330, 40, 3)} fill={p.far} />;
    if (["beach", "backwater", "gateway"].includes(motif)) return <path d={ridge(r, 330, 20, 6)} fill={p.far} opacity=".7" />;
    return <path d={ridge(r, 320, 60, 5)} fill={p.far} opacity=".85" />;
  })();

  const water = (y: number) => (
    <>
      <rect x="-400" y={y} width="1200" height={500 - y} fill={p.water} />
      {waves(y + 24, p.sun, 0.45)}
      {waves(y + 70, p.sun, 0.25, 5)}
    </>
  );

  const mid = (() => {
    switch (motif) {
      case "tea":
        return (<g>{[0, 1, 2].map((i) => (
          <g key={i}><path d={ridge(r, 300 + i * 50, 40, 3)} fill={i === 2 ? p.near : p.mid} opacity={1 - i * 0.12} />
            {Array.from({ length: 9 }, (_, k) => <path key={k} d={`M${k * 50 - 20} ${330 + i * 50} q50 -26 100 0`} stroke={p.sky[1]} strokeWidth="2" fill="none" opacity=".25" />)}</g>))}</g>);
      case "lake":
        return (<g><path d={ridge(r, 320, 50, 4)} fill={p.mid} />{water(350)}
          {boat(200, 400, 1.3, p.near)}<rect x="196" y="370" width="2" height="30" fill={p.near} /></g>);
      case "pines":
        return (<g><path d={ridge(r, 330, 60, 4)} fill={p.mid} />
          {Array.from({ length: 30 }, (_, i) => pine(-390 + i * 40 + r() * 10, 360 + r() * 30, 0.9 + r() * 0.8, p.near, i))}
          <g fill={p.near}><rect x="250" y="330" width="44" height="34" /><path d="M244 332 l28 -22 l28 22 Z" /><rect x="266" y="344" width="10" height="12" fill={p.accent} /></g></g>);
      case "desert":
        return (<g><MotifShape motif="fort" p={p} r={r} /><path d={ridge(r, 400, 40, 3)} fill={p.accent} opacity=".85" />
          <path transform="translate(110 392) scale(1.1)" fill={p.near} d="M0 0 l4 -18 q6 -6 12 0 l10 -6 q8 -2 10 6 l4 12 l-4 0 l-2 -8 l-6 8 l-4 0 l2 -8 l-14 0 l-4 14 l-4 0 Z M30 -24 q4 -12 10 -10 l2 4 l-6 2 Z" /></g>);
      case "beach":
        return (<g>{water(330)}<path d="M-400 440 Q200 380 800 430 L800 500 L-400 500 Z" fill={p.accent} opacity=".9" />
          <g fill={p.near}><path d="M300 400 l30 -26 l30 26 Z" /><rect x="308" y="400" width="44" height="22" /></g></g>);
      case "backwater":
        return (<g>{water(340)}
          <g fill={p.near}><path d="M110 372 Q200 392 290 372 L280 386 Q200 400 120 386 Z" />
            <path d="M130 372 Q200 330 270 372 Z" opacity=".92" /><rect x="150" y="356" width="100" height="4" fill={p.accent} /></g></g>);
      case "river":
        return (<g><path d={ridge(r, 330, 70, 4)} fill={p.mid} />{water(370)}
          <path d="M0 330 Q200 380 400 330" stroke={p.near} strokeWidth="3" fill="none" />
          {Array.from({ length: 15 }, (_, i) => <path key={i} d={`M${i * 28} ${330 + Math.sin((i / 14) * Math.PI) * 25} l0 -18`} stroke={p.near} strokeWidth="1.5" />)}
          <rect x="0" y="300" width="10" height="60" fill={p.near} /><rect x="390" y="300" width="10" height="60" fill={p.near} /></g>);
      case "gateway":
        return (<g><MotifShape motif={motif} p={p} r={r} />{water(370)}{boat(90, 420, 1, p.near)}{boat(310, 440, 0.8, p.near)}</g>);
      case "palace":
        return (<g><MotifShape motif={motif} p={p} r={r} />{water(370)}
          <g transform="translate(0 740) scale(1 -1)" opacity=".18"><MotifShape motif={motif} p={p} r={rng(seed)} /></g></g>);
      default:
        return <MotifShape motif={motif} p={p} r={r} />;
    }
  })();

  const near = (() => {
    switch (motif) {
      case "beach": return (<>{palm(-160, 480, 1.6, p.near)}{palm(30, 480, 1.4, p.near)}{palm(370, 470, 1.1, p.near, -1)}{palm(560, 485, 1.5, p.near, -1)}</>);
      case "backwater": return (<>{palm(-140, 480, 1.7, p.near)}{palm(20, 470, 1.5, p.near)}{palm(60, 460, 1, p.near)}{palm(380, 470, 1.3, p.near, -1)}{palm(540, 480, 1.6, p.near, -1)}</>);
      case "charminar": case "fort": case "indiagate": case "colonial": case "city":
        return <path d="M-400 380 L800 380 L800 500 L-400 500 Z" fill={p.near} />;
      case "ghats":
        return (<>{water(380)}{boat(120, 430, 1.1, p.near)}{boat(300, 410, 0.9, p.near)}
          <g fill={p.accent}>{[80, 150, 210, 270, 340].map((x, i) => <circle key={x} cx={x} cy={392 + (i % 2) * 8} r="2.5" />)}</g></>);
      case "bridge": return water(334);
      default: return null;
    }
  })();

  return { sky, far, mid, near };
}

type PosterProps = {
  city?: string;
  propertyType?: string;
  seed?: number;
  palette?: PaletteName;
  className?: string;
  title?: string;
  parallax?: boolean;
  /** force the landscape composition; by default it is chosen from the container's shape */
  wide?: boolean;
  children?: ReactNode;
};

export function Poster({ city, propertyType, seed = 7, palette, className = "", title, parallax = false, wide = false, children }: PosterProps) {
  const uid = useId().replace(/:/g, "");
  const motif = motifFor(city, propertyType);
  // cards vary their time of day by seed, so a page of results doesn't repeat itself
  const VARIANTS: PaletteName[] = [MOTIF_PALETTE[motif], "dawn", "dusk", MOTIF_PALETTE[motif], "night", "monsoon"];
  const p = PALETTES[palette ?? VARIANTS[seed % VARIANTS.length]];
  const layers = useMemo(() => scene(motif, p, seed, uid), [motif, p, seed, uid]);
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  // landscape containers get the wide composition (wider horizon, landmark centred)
  const [landscape, setLandscape] = useState(wide);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setLandscape(wide || e.contentRect.width > e.contentRect.height * 1.15));
    ro.observe(el);
    return () => ro.disconnect();
  }, [wide]);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  // always four hooks in the same order; the distance is 0 when parallax is off
  const move = (dist: number): MotionValue<number> =>
    useTransform(scrollYProgress, [0, 1], [0, parallax && !reduce ? dist : 0]);
  const ySky = move(30), yFar = move(70), yMid = move(120), yNear = move(170);

  return (
    <div ref={ref} className={`${/\b(absolute|fixed)\b/.test(className) ? "" : "relative"} overflow-hidden ${className}`} role={title ? "img" : undefined} aria-label={title}>
      <svg viewBox={landscape ? "-250 40 900 460" : "0 0 400 500"} preserveAspectRatio="xMidYMax slice" className="absolute inset-0 h-full w-full" aria-hidden>
        <motion.g style={{ y: ySky }}>{layers.sky}</motion.g>
        <motion.g style={{ y: yFar }}>{layers.far}</motion.g>
        <motion.g style={{ y: yMid }}>{layers.mid}</motion.g>
        <motion.g style={{ y: yNear }}>{layers.near}</motion.g>
      </svg>
      {children}
    </div>
  );
}
