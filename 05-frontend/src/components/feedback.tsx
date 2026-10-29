/** Loading, empty and error states — each one designed, none left to chance. */
import type { ReactNode } from "react";
import { ApiError } from "../lib/api";
import { Poster } from "../art/Poster";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton rounded-2xl ${className}`} aria-hidden />;
}

export function Empty({ title, sub, action, page = false }: { title: string; sub?: string; action?: ReactNode; page?: boolean }) {
  const Heading = page ? "h1" : "h3";
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-16 text-center">
      <Poster city="Shimla" seed={3} palette="monsoon" className="mb-6 h-36 w-28 rounded-[2rem] opacity-90" />
      <Heading className="display text-2xl">{title}</Heading>
      {sub && <p className="mt-2 text-ink-2">{sub}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/**
 * Shows an API error. When the database refused something, it shows WHICH
 * rule refused it — the answer to "why can't I do this?".
 */
export function ErrorNote({ error, onRetry, compact = false }: { error: unknown; onRetry?: () => void; compact?: boolean }) {
  const e = error instanceof ApiError ? error.body : { error: String((error as Error)?.message ?? error) };
  const isDbRule = Boolean((e as any).sqlstate);
  return (
    <div role="alert" className={`rounded-2xl border border-sindoor/30 bg-sindoor/[0.06] ${compact ? "p-4" : "p-6"}`}>
      <p className="font-semibold text-sindoor">{isDbRule ? "The database said no — here's why" : "Something went wrong"}</p>
      <p className="mt-1 text-ink">{e.error}</p>
      {e.hint && <p className="mt-1 text-sm text-ink-2">Hint: {e.hint}</p>}
      {isDbRule && (
        <div className="mt-3 rounded-xl bg-card px-4 py-3 text-sm">
          <p className="text-ink-2"><span className="font-semibold text-ink">Rule:</span> {(e as any).rule}</p>
          <p className="mt-1 font-mono text-xs text-ink-3">
            SQLSTATE {(e as any).sqlstate}{(e as any).constraint ? ` · constraint ${(e as any).constraint}` : ""}
            {(e as any).table ? ` · table ${(e as any).table}` : ""}
          </p>
        </div>
      )}
      {onRetry && (
        <button onClick={onRetry} className="mt-4 rounded-full border border-ink/20 px-4 py-2 text-sm font-medium hover:bg-ink hover:text-paper">
          Try again
        </button>
      )}
    </div>
  );
}
