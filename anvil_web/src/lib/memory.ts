// Calculator-style MEMORY (B4). Named slots persisted in localStorage. A slot
// holds either a scalar (with optional unit) or an array (time-series).

export interface MemoryScalar {
  kind: "scalar";
  value: number;
  unit: string;
}

export interface MemoryArray {
  kind: "array";
  values: number[];
}

export type MemorySlot = MemoryScalar | MemoryArray;

export interface MemoryMap {
  [name: string]: MemorySlot;
}

const KEY = "anvil-calc-memory";
const HISTORY_KEY = "anvil-calc-history";
const HISTORY_MAX = 40;

/** Window event fired whenever memory or history changes (cross-component). */
export const MEMORY_EVENT = "anvil-memory-changed";

function notify() {
  try {
    window.dispatchEvent(new Event(MEMORY_EVENT));
  } catch {
    /* non-browser env */
  }
}

export function readMemory(): MemoryMap {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as MemoryMap) : {};
  } catch {
    return {};
  }
}

export function writeMemory(map: MemoryMap) {
  localStorage.setItem(KEY, JSON.stringify(map));
  notify();
}

// ---- auto-history: recent solve results + keypad evaluations ---------------

export interface HistorySolveItem {
  name: string;
  value: number;
  unit: string;
}

export interface HistoryEntry {
  kind: "solve" | "calc";
  /** RSQ name for solves; the expression text for keypad evaluations. */
  label: string;
  items: HistorySolveItem[];
  t: number;
}

export function readHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? (arr as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

export function pushHistory(entry: HistoryEntry): HistoryEntry[] {
  const list = [entry, ...readHistory()].slice(0, HISTORY_MAX);
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  } catch {
    /* storage full/unavailable */
  }
  notify();
  return list;
}

export function clearHistory(): HistoryEntry[] {
  try {
    localStorage.removeItem(HISTORY_KEY);
  } catch {
    /* ignore */
  }
  notify();
  return [];
}

/** First free auto slot name: M1, M2, ... */
export function nextSlotName(map: MemoryMap): string {
  for (let i = 1; i < 100; i++) {
    if (!(`M${i}` in map)) return `M${i}`;
  }
  return `M${Date.now() % 1000}`;
}

export function setMemory(name: string, slot: MemorySlot): MemoryMap {
  const map = readMemory();
  map[name] = slot;
  writeMemory(map);
  return map;
}

export function clearMemory(name: string): MemoryMap {
  const map = readMemory();
  delete map[name];
  writeMemory(map);
  return map;
}

export function clearAllMemory(): MemoryMap {
  writeMemory({});
  return {};
}

/** Short human label for a slot (for menus). */
export function memoryLabel(slot: MemorySlot): string {
  if (slot.kind === "array") return `[${slot.values.length} vals]`;
  return `${slot.value}${slot.unit ? " " + slot.unit : ""}`;
}
