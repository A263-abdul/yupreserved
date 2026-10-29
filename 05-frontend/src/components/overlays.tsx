/** SQL trace drawer and compare tray. */
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { rupees } from "../lib/format";
import { useSession } from "../lib/session";
import { useTraces } from "../lib/traceStore";

// ── "Under the hood": the SQL behind the last few screens ──────────────────
export function TraceDrawer() {
  const traces = useTraces();
  const [open, setOpen] = useState(false);
  const latest = traces[0];
  return (
    <>
      <button onClick={() => setOpen(true)}
        className="fixed bottom-[4.6rem] right-3 z-40 flex md:bottom-4 md:left-4 md:right-auto items-center gap-2 rounded-full border border-line bg-card/95 px-4 py-2.5 text-sm shadow-lg backdrop-blur hover:border-ink"
        aria-label="Show the SQL behind this page">
        <span className="font-mono text-xs text-peacock">SQL</span>
        <span className="hidden md:inline">Under the hood</span>
        {latest && <span className="hidden rounded-full bg-paper-2 px-2 text-xs tabular text-ink-2 md:inline">{latest.steps.length}</span>}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-[70] flex justify-end bg-ink/30 backdrop-blur-[2px]" onClick={() => setOpen(false)}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <motion.aside role="dialog" aria-label="SQL trace" onClick={(e) => e.stopPropagation()}
              initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 260 }}
              className="h-full w-[min(40rem,100vw)] overflow-y-auto bg-card p-6 shadow-2xl">
              <div className="flex items-start justify-between">
                <div>
                  <p className="eyebrow">Under the hood</p>
                  <h2 className="display mt-1 text-3xl">The SQL behind what you just saw</h2>
                  <p className="mt-1 text-sm text-ink-2">Every screen is plain SQL against PostgreSQL — no ORM. Newest first.</p>
                </div>
                <button onClick={() => setOpen(false)} className="rounded-full px-3 py-1 text-ink-3 hover:bg-paper-2" aria-label="Close">✕</button>
              </div>
              {traces.length === 0 && <p className="mt-10 text-ink-3">Browse a page and its queries will appear here.</p>}
              <div className="mt-6 space-y-6">
                {traces.map((t) => (
                  <section key={t.id}>
                    <p className="text-sm font-semibold">{t.label} <span className="font-normal text-ink-3">· {t.at.toLocaleTimeString("en-IN")}</span></p>
                    {t.steps.map((s, i) => (
                      <div key={i} className="mt-2 overflow-hidden rounded-xl border border-line">
                        <pre className="max-h-72 overflow-auto bg-paper-2/70 p-3 font-mono text-[0.72rem] leading-relaxed text-ink">{s.sql}</pre>
                        <p className="flex justify-between bg-paper px-3 py-1.5 font-mono text-[0.68rem] text-ink-3">
                          <span>{s.rows} row{s.rows === 1 ? "" : "s"}</span><span>{s.ms} ms</span>
                        </p>
                      </div>
                    ))}
                  </section>
                ))}
              </div>
              <Link to="/lab" onClick={() => setOpen(false)} className="mt-8 inline-block text-sm font-semibold text-sindoor">Open the database lab →</Link>
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ── Compare up to three stays side by side ─────────────────────────────────
export function CompareTray() {
  const { compare, toggleCompare, clearCompare } = useSession();
  const [open, setOpen] = useState(false);
  if (compare.length === 0) return null;
  const rows: [string, (h: (typeof compare)[number]) => string][] = [
    ["City", (h) => h.city_name], ["Type", (h) => h.property_type], ["Stars", (h) => (h.star_rating ? `${h.star_rating}★` : "—")],
    ["Rating", (h) => (h.avg_rating ? `${Number(h.avg_rating).toFixed(1)} (${h.review_count})` : "New")],
    ["From / night", (h) => rupees(h.from_price)], ["Your dates", (h) => (h.stay_total ? rupees(h.stay_total) : "—")],
    ["Highlights", (h) => (h.highlights ?? []).slice(0, 3).join(", ") || "—"],
  ];
  return (
    <motion.div initial={{ y: 80 }} animate={{ y: 0 }} className="fixed bottom-20 left-1/2 z-40 w-[min(46rem,calc(100vw-2rem))] -translate-x-1/2 md:bottom-4">
      <div className="rounded-3xl border border-line bg-card p-3 shadow-2xl">
        <div className="flex items-center gap-3">
          <p className="pl-2 text-sm font-semibold">Compare <span className="tabular text-ink-3">{compare.length}/3</span></p>
          <div className="flex min-w-0 flex-1 gap-2 overflow-x-auto scrollbar-none">
            {compare.map((h) => (
              <button key={h.hotel_id} onClick={() => toggleCompare(h)} className="shrink-0 rounded-full bg-paper-2 px-3 py-1 text-xs" title="Remove">
                {h.hotel_name} ✕
              </button>
            ))}
          </div>
          <button onClick={() => setOpen((o) => !o)} disabled={compare.length < 2}
            className="rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper disabled:opacity-40">{open ? "Hide" : "Compare"}</button>
          <button onClick={clearCompare} className="text-xs text-ink-3 hover:text-ink">Clear</button>
        </div>
        <AnimatePresence>
          {open && compare.length >= 2 && (
            <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
              <table className="mt-3 w-full text-left text-sm">
                <thead><tr><th className="w-28" />{compare.map((h) => <th key={h.hotel_id} className="px-2 pb-2 align-bottom font-semibold">{h.hotel_name}</th>)}</tr></thead>
                <tbody>
                  {rows.map(([label, f]) => (
                    <tr key={label} className="border-t border-line">
                      <td className="py-2 pr-2 text-xs text-ink-3">{label}</td>
                      {compare.map((h) => <td key={h.hotel_id} className="px-2 py-2 tabular">{f(h)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
