/**
 * A tiny external store holding the most recent SQL traces from the API,
 * read with useSyncExternalStore by the "Under the hood" drawer.
 */
import { useSyncExternalStore } from "react";
import type { TraceStep } from "./api";

export type TraceEntry = { id: number; label: string; at: Date; steps: TraceStep[] };

let entries: TraceEntry[] = [];
let seq = 0;
const listeners = new Set<() => void>();

export function pushTrace(label: string, steps: TraceStep[]) {
  entries = [{ id: ++seq, label, at: new Date(), steps }, ...entries].slice(0, 25);
  listeners.forEach((l) => l());
}

export function useTraces() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => entries,
  );
}
