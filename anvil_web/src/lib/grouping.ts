import type { RegistryEntry } from "./types";

export interface DomainGroup {
  domain: string;
  entries: RegistryEntry[];
}

const UNGROUPED = "(uncategorized)";

/**
 * Group registry entries by `domain`, sorted by domain name, with each group's
 * entries sorted by name. Entries with no domain land in a trailing
 * "(uncategorized)" group. Used by both the Calculator picker and the Canvas
 * palette so the two stay consistent.
 */
export function groupByDomain(entries: RegistryEntry[]): DomainGroup[] {
  const map = new Map<string, RegistryEntry[]>();
  for (const e of entries) {
    const key = e.domain?.trim() || UNGROUPED;
    const arr = map.get(key);
    if (arr) arr.push(e);
    else map.set(key, [e]);
  }
  const groups: DomainGroup[] = [...map.entries()].map(([domain, es]) => ({
    domain,
    entries: [...es].sort((a, b) => a.name.localeCompare(b.name)),
  }));
  groups.sort((a, b) => {
    // Keep the uncategorized bucket last.
    if (a.domain === UNGROUPED) return 1;
    if (b.domain === UNGROUPED) return -1;
    return a.domain.localeCompare(b.domain);
  });
  return groups;
}

/** Case-insensitive substring match across name/domain/description/tags. */
export function matchesQuery(e: RegistryEntry, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  return (
    e.name.toLowerCase().includes(needle) ||
    (e.domain ?? "").toLowerCase().includes(needle) ||
    (e.description ?? "").toLowerCase().includes(needle) ||
    (e.tags ?? []).some((t) => t.toLowerCase().includes(needle))
  );
}
