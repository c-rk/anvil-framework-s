// Result comparison tray. Snapshots of solved RSQ results, kept in
// localStorage so they survive switching between RSQs, and broadcast via a
// window event (same pattern as memory.ts) so the panel updates live.

import type { ResultValue, SolveResponse } from "./types";

export interface CompareSnapshot {
  id: string;
  /** RSQ name plus a short disambiguator when the same RSQ is added twice. */
  label: string;
  rsq: string;
  method: string;
  results: Record<string, ResultValue>;
  t: number;
}

const KEY = "anvil-compare-snapshots";
const MAX = 8;

export const COMPARE_EVENT = "anvil-compare-changed";

function notify() {
  try {
    window.dispatchEvent(new Event(COMPARE_EVENT));
  } catch {
    /* non-browser env */
  }
}

export function readCompare(): CompareSnapshot[] {
  try {
    const raw = localStorage.getItem(KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? (arr as CompareSnapshot[]) : [];
  } catch {
    return [];
  }
}

function write(list: CompareSnapshot[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* storage full/unavailable */
  }
  notify();
}

export function addCompare(result: SolveResponse): CompareSnapshot[] {
  const list = readCompare();
  const sameRsq = list.filter((s) => s.rsq === result.name).length;
  const snap: CompareSnapshot = {
    id: `${result.name}-${Date.now()}`,
    label: sameRsq > 0 ? `${result.name} (${sameRsq + 1})` : result.name,
    rsq: result.name,
    method: result.method,
    results: result.results,
    t: Date.now(),
  };
  const next = [...list, snap].slice(-MAX);
  write(next);
  return next;
}

export function removeCompare(id: string): CompareSnapshot[] {
  const next = readCompare().filter((s) => s.id !== id);
  write(next);
  return next;
}

export function clearCompare(): CompareSnapshot[] {
  write([]);
  return [];
}
