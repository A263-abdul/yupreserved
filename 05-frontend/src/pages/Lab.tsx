/**
 * "Under the hood" — the DBMS lab. Everything here runs against the live
 * database through /api/lab, always inside a transaction that is rolled back.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ErrorNote, Skeleton } from "../components/feedback";
import { Page } from "../components/motion";
import { api, type LabEntry } from "../lib/api";
import { count } from "../lib/format";

const TABS = [
  ["overview", "Overview & ER"], ["tables", "15 tables"], ["queries", "Query library"],
  ["plans", "Query plans"], ["why", "Why can't I…?"], ["txn", "Transactions"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function Lab() {
  const [sp, setSp] = useSearchParams();
  const tab = (sp.get("tab") as Tab) || "overview";
  return (
    <Page className="mx-auto max-w-7xl px-4 pb-16 pt-8 sm:px-6">
      <p className="eyebrow">Under the hood · DBMS lab</p>
      <h1 className="display mt-2 text-5xl">The database behind YupReserved</h1>
      <p className="mt-2 max-w-3xl text-ink-2">PostgreSQL 16 · 15 tables · real hotel listings from 543 cities. Every button here runs real SQL
        against the live database, inside a transaction that is rolled back, so nothing you try can change the data.</p>
      <div role="tablist" className="mt-8 flex gap-1 overflow-x-auto border-b border-line scrollbar-none">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setSp({ tab: k })}
            className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium transition ${tab === k ? "border-sindoor text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}>
            {l}
          </button>
        ))}
      </div>
      <div className="mt-8">
        {tab === "overview" && <Overview />}
        {tab === "tables" && <Tables initial={sp.get("table") ?? "hotels"} />}
        {tab === "queries" && <Runner kind="queries" />}
        {tab === "plans" && <Runner kind="plans" />}
        {tab === "why" && <Runner kind="why" />}
        {tab === "txn" && <Transactions />}
      </div>
    </Page>
  );
}

// ── overview ───────────────────────────────────────────────────────────────
function Overview() {
  const o = useQuery({ queryKey: ["lab-overview"], queryFn: api.lab.overview });
  const [, setSp] = useSearchParams();
  const totals = useMemo(() => o.data?.reduce((a, t) => ({ rows: a.rows + Number(t.approx_rows), fk: a.fk + Number(t.foreign_keys),
    uq: a.uq + Number(t.unique_keys), ck: a.ck + Number(t.checks) }), { rows: 0, fk: 0, uq: 0, ck: 0 }), [o.data]);
  if (o.error) return <ErrorNote error={o.error} />;
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        {[["Tables", 15], ["Rows", totals?.rows], ["Primary keys", 15], ["Foreign keys", totals?.fk], ["CHECK / EXCLUDE", totals?.ck]].map(([l, v]) => (
          <div key={l as string} className="rounded-2xl border border-line bg-card p-4">
            <p className="text-xs text-ink-3">{l}</p><p className="display mt-1 text-3xl tabular">{v === undefined ? "…" : count(v as number)}</p>
          </div>
        ))}
      </div>
      <figure className="overflow-hidden rounded-3xl border border-line bg-[#FBF7F0] p-4">
        <img src="/er-diagram.svg" alt="ER diagram of the 15 tables" className="mx-auto w-full" loading="lazy" />
        <figcaption className="mt-2 text-center text-xs text-[#7B7F8F]">Relational schema: every arrow is a foreign key (child → parent). Generated with Graphviz from the live catalog.</figcaption>
      </figure>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {!o.data ? Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-28" />) : o.data.map((t) => (
          <button key={t.table_name} onClick={() => setSp({ tab: "tables", table: t.table_name })}
            className="rounded-2xl border border-line bg-card p-4 text-left transition hover:border-ink/40">
            <p className="eyebrow">{t.group}</p>
            <p className="mt-1 font-mono text-lg font-semibold">{t.table_name}</p>
            <p className="mt-1 text-sm text-ink-2">PK ({t.primary_key}) · {t.foreign_keys} FK · {t.unique_keys} UNIQUE · {t.checks} CHECK</p>
            <p className="mt-1 text-xs text-ink-3 tabular">{count(Number(t.approx_rows))} rows · {t.size}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── table browser ──────────────────────────────────────────────────────────
const TABLE_NAMES = ["states", "cities", "landmarks", "hotels", "hotel_landmarks", "amenities", "hotel_amenities",
  "room_types", "rooms", "seasons", "guests", "bookings", "booking_rooms", "payments", "reviews"];

function Tables({ initial }: { initial: string }) {
  const [name, setName] = useState(TABLE_NAMES.includes(initial) ? initial : "hotels");
  const [page, setPage] = useState(1);
  const rows = useQuery({ queryKey: ["lab-table", name, page], queryFn: () => api.lab.table(name, page) });
  const schema = useQuery({ queryKey: ["lab-schema", name], queryFn: () => api.lab.schema(name) });
  return (
    <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
      <nav className="flex gap-1 overflow-x-auto lg:flex-col scrollbar-none" aria-label="Tables">
        {TABLE_NAMES.map((t, i) => (
          <button key={t} onClick={() => { setName(t); setPage(1); }}
            className={`shrink-0 rounded-xl px-3 py-2 text-left font-mono text-sm ${t === name ? "bg-ink text-paper" : "text-ink-2 hover:bg-paper-2"}`}>
            <span className="opacity-50">{String(i + 1).padStart(2, "0")}</span> {t}
          </button>
        ))}
      </nav>
      <div className="min-w-0 space-y-6">
        {schema.data && (
          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-line bg-card p-4">
              <p className="eyebrow">Columns</p>
              <table className="mt-2 w-full font-mono text-xs">
                <tbody>{schema.data.columns.map((c: any) => (
                  <tr key={c.column_name} className="border-t border-line">
                    <td className="py-1.5 pr-2 font-semibold">{c.column_name}</td><td className="text-ink-2">{c.data_type}</td>
                    <td className="text-right text-ink-3">{c.generated ? "GENERATED" : c.nullable ? "NULL" : "NOT NULL"}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            <div className="space-y-2 rounded-2xl border border-line bg-card p-4">
              <p className="eyebrow">Constraints</p>
              {schema.data.constraints.map((c: any) => (
                <div key={c.name} className="font-mono text-xs"><span className="mr-2 rounded bg-paper-2 px-1.5 py-0.5 font-semibold">{c.kind}</span>
                  <span className="text-ink-2">{c.definition}</span></div>
              ))}
              {schema.data.referenced_by.length > 0 && <p className="eyebrow pt-3">Referenced by</p>}
              {schema.data.referenced_by.map((r: any) => <p key={r.name} className="font-mono text-xs text-ink-2">{r.child_table} → {r.definition}</p>)}
              {schema.data.triggers.length > 0 && <p className="eyebrow pt-3">Triggers</p>}
              {schema.data.triggers.map((t: any) => <p key={t.name} className="font-mono text-xs text-ink-2">{t.name}</p>)}
            </div>
          </div>
        )}
        {rows.error ? <ErrorNote error={rows.error} /> : !rows.data ? <Skeleton className="h-96" /> : (
          <div>
            <pre className="overflow-x-auto rounded-xl bg-paper-2/70 p-3 font-mono text-xs">{rows.data.sql};</pre>
            <ResultTable columns={rows.data.columns} rows={rows.data.rows} />
            <div className="mt-3 flex items-center justify-between text-sm">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-full border border-line px-4 py-1.5 disabled:opacity-30">← Prev</button>
              <span className="text-ink-3 tabular">page {page} · ~{count(rows.data.approx_total)} rows</span>
              <button disabled={rows.data.rows.length < rows.data.page_size} onClick={() => setPage(page + 1)} className="rounded-full border border-line px-4 py-1.5 disabled:opacity-30">Next →</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ResultTable({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
  return (
    <div className="mt-3 max-h-[32rem] overflow-auto rounded-2xl border border-line">
      <table className="w-full text-left font-mono text-xs">
        <thead className="sticky top-0 bg-card"><tr>{columns.map((c) => <th key={c} className="whitespace-nowrap border-b border-line px-3 py-2 text-sindoor">{c}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i} className="odd:bg-paper-2/40">
            {r.map((v, j) => <td key={j} className="max-w-[18rem] truncate whitespace-nowrap px-3 py-1.5" title={String(v ?? "")}>
              {v === null ? <span className="text-ink-3">NULL</span> : Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v)}</td>)}
          </tr>))}</tbody>
      </table>
    </div>
  );
}

// ── query library / plans / why-not ────────────────────────────────────────
function Runner({ kind }: { kind: "queries" | "plans" | "why" }) {
  const list = useQuery({ queryKey: ["lab-list", kind], queryFn: () => api.lab.list(kind) });
  const [sel, setSel] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const run = useMutation({ mutationFn: (name: string) => api.lab.run(kind, name) });
  const explain = useMutation({ mutationFn: (name: string) => api.lab.explainQuery(name) });
  const entries = (list.data ?? []).filter((e) => !filter || (e.name + e.title + e.topic).toLowerCase().includes(filter.toLowerCase()));
  const current: LabEntry | undefined = list.data?.find((e) => e.name === (sel ?? list.data?.[0]?.name));
  const choose = (n: string) => { setSel(n); run.reset(); explain.reset(); };

  const groups = useMemo(() => entries.reduce<Record<string, LabEntry[]>>((acc, e) => {
    const g = kind === "queries" ? e.name.split(".")[0] : kind === "plans" ? "plans" : "scenarios";
    (acc[g] ??= []).push(e); return acc;
  }, {}), [entries, kind]);

  if (list.error) return <ErrorNote error={list.error} />;
  return (
    <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
      <div>
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter — e.g. join, 3NF, division"
          className="w-full rounded-xl border border-line bg-card px-4 py-2.5 text-sm" />
        <div className="mt-3 max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          {Object.entries(groups).map(([g, items]) => (
            <div key={g}>
              <p className="eyebrow px-2">{g}</p>
              {items.map((e) => (
                <button key={e.name} onClick={() => choose(e.name)}
                  className={`mt-1 block w-full rounded-xl px-3 py-2 text-left text-sm ${current?.name === e.name ? "bg-ink text-paper" : "hover:bg-paper-2"}`}>
                  {e.title}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
      {current && (
        <div className="min-w-0">
          <p className="font-mono text-xs text-ink-3">{current.name} · {current.file}</p>
          <h2 className="display mt-1 text-3xl">{current.title}</h2>
          <p className="mt-1 text-sm text-peacock">{current.topic}</p>
          {current.algebra && <p className="mt-4 rounded-xl bg-paper-2/70 px-4 py-3 font-mono text-sm"><span className="text-ink-3">RA / RC · </span>{current.algebra}</p>}
          <p className="mt-4 text-ink-2">{current.explain}</p>
          {current.setup && <p className="mt-3 font-mono text-xs text-ink-3">setup: {current.setup}</p>}
          <pre className="mt-4 overflow-x-auto rounded-2xl bg-[#1E2233] p-4 font-mono text-[0.78rem] leading-relaxed text-[#EFE6D6]">{current.sql};</pre>
          <div className="mt-4 flex gap-2">
            <button onClick={() => run.mutate(current.name)} disabled={run.isPending}
              className="rounded-full bg-sindoor px-5 py-2.5 font-semibold text-sindoor-ink">
              {run.isPending ? "Running…" : kind === "why" ? "Try it" : kind === "plans" ? "EXPLAIN ANALYZE" : "Run query"}
            </button>
            {kind === "queries" && <button onClick={() => explain.mutate(current.name)} className="rounded-full border border-line px-5 py-2.5">Show plan</button>}
          </div>
          {run.error && <div className="mt-4"><ErrorNote error={run.error} /></div>}
          {run.data && kind === "queries" && (
            <div className="mt-6">
              <p className="text-sm text-ink-3 tabular">{run.data.rows.length} row(s){run.data.truncated ? " (first 200)" : ""} · {run.data.ms} ms</p>
              <ResultTable columns={run.data.columns} rows={run.data.rows} />
            </div>
          )}
          {(kind === "plans" ? run.data : explain.data) && <Plan p={kind === "plans" ? run.data : explain.data} />}
          {run.data && kind === "why" && (
            <div className={`mt-6 rounded-2xl border p-5 ${run.data.failed ? "border-peacock/40 bg-peacock/[0.06]" : "border-sindoor/40"}`}>
              <p className="font-semibold">{run.data.failed ? "✓ The database refused it" : "✗ It was allowed (and rolled back)"}</p>
              {run.data.failed && <>
                <p className="mt-2 text-sindoor">{run.data.error}</p>
                {run.data.detail && <p className="mt-1 font-mono text-xs text-ink-3">{run.data.detail}</p>}
                <p className="mt-3 text-ink"><b>Rule:</b> {run.data.rule}</p>
                <p className="mt-1 font-mono text-xs text-ink-3">SQLSTATE {run.data.sqlstate}{run.data.constraint ? ` · ${run.data.constraint}` : ""}{run.data.raised_in ? ` · ${run.data.raised_in}` : ""}</p>
              </>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Plan({ p }: { p: any }) {
  return (
    <div className="mt-6">
      <div className="flex flex-wrap gap-2">
        {p.operators.map((o: string) => <span key={o} className="rounded-full bg-peacock/15 px-3 py-1 text-xs font-semibold text-peacock">{o}</span>)}
      </div>
      <p className="mt-2 text-sm text-ink-3 tabular">planning {p.planning_ms} ms · execution {p.execution_ms} ms</p>
      <pre className="mt-3 max-h-[28rem] overflow-auto rounded-2xl border border-line bg-paper-2/60 p-4 font-mono text-[0.72rem] leading-relaxed">{p.plan_text}</pre>
    </div>
  );
}

// ── concurrency ────────────────────────────────────────────────────────────
const TXN_INFO: Record<string, [string, string]> = {
  double_booking_race: ["Two guests, one last room", "Lock-based protocol · SELECT … FOR UPDATE"],
  deadlock: ["Deadlock", "Wait-for cycle → detection → victim aborted"],
  isolation_levels: ["Isolation levels", "Non-repeatable read: READ COMMITTED vs REPEATABLE READ"],
  mvcc_versions: ["MVCC row versions", "Multiversion / timestamp ordering · xmin, xmax, ctid"],
  atomic_rollback: ["Atomicity", "All or nothing · ROLLBACK undoes step 1 when step 2 fails"],
};

function Transactions() {
  const list = useQuery({ queryKey: ["lab-txn"], queryFn: api.lab.concurrency });
  const run = useMutation({ mutationFn: (n: string) => api.lab.runConcurrency(n) });
  const [cur, setCur] = useState<string | null>(null);
  const timelines: [string, any[]][] = run.data
    ? run.data.timeline ? [["", run.data.timeline]] : Object.entries(run.data.results).map(([k, v]: any) => [k, v.timeline])
    : [];
  return (
    <div>
      <p className="max-w-3xl text-ink-2">Each demo opens <b>two real database sessions</b> (A and B) on separate threads and records what each one saw, millisecond by millisecond.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {list.data?.map((s) => (
          <button key={s.name} onClick={() => { setCur(s.name); run.mutate(s.name); }}
            className={`rounded-2xl border p-4 text-left transition ${cur === s.name ? "border-ink bg-card" : "border-line hover:border-ink/40"}`}>
            <p className="font-semibold">{TXN_INFO[s.name]?.[0] ?? s.name}</p>
            <p className="mt-1 text-xs text-ink-3">{TXN_INFO[s.name]?.[1]}</p>
          </button>
        ))}
      </div>
      {run.isPending && <p className="mt-8 text-ink-3">Running two sessions… (the deadlock demo waits ~1 s for detection)</p>}
      {run.error && <div className="mt-6"><ErrorNote error={run.error} /></div>}
      {run.data && (
        <div className="mt-8 space-y-6">
          {timelines.map(([label, events]) => (
            <div key={label}>
              {label && <p className="eyebrow mb-2">{label}</p>}
              <ol className="relative space-y-3 border-l-2 border-line pl-6">
                {events.map((e: any, i: number) => (
                  <li key={i} className="relative">
                    <span className={`absolute -left-[33px] top-1 grid h-5 w-5 place-items-center rounded-full text-[0.6rem] font-bold text-paper ${e.session === "A" || e.session === "Reader" ? "bg-sindoor" : e.session === "B" || e.session === "Writer" ? "bg-monsoon" : "bg-ink-3"}`}>
                      {e.session[0]}
                    </span>
                    <p className="text-sm"><span className="font-mono text-xs text-ink-3 tabular">{String(e.t_ms).padStart(5, " ")} ms</span> <b>{e.session}</b> — {e.step}</p>
                    {e.result !== null && e.result !== undefined && <pre className="mt-1 overflow-x-auto rounded-lg bg-paper-2/70 px-3 py-1.5 font-mono text-xs">{typeof e.result === "object" ? JSON.stringify(e.result) : String(e.result)}</pre>}
                  </li>
                ))}
              </ol>
            </div>
          ))}
          <div className="rounded-2xl bg-ink p-5 text-paper"><p className="eyebrow !text-paper/60">What this shows</p><p className="mt-2">{run.data.lesson}</p></div>
        </div>
      )}
    </div>
  );
}
