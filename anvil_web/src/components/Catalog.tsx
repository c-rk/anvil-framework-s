import { useEffect, useMemo, useState } from "react";
import type { RegistryEntry } from "../lib/types";
import { groupByDomain, matchesQuery } from "../lib/grouping";
import { rsqDocsUrl, NEW_TAB } from "../lib/docs";

interface Props {
  entries: RegistryEntry[];
  selected: string | null;
  onSelect: (name: string) => void;
  loading: boolean;
  error: string | null;
}

const TYPE_LABEL: Record<string, string> = {
  R: "Relation",
  S: "System",
  Q: "Quantity",
};

const PINS_KEY = "anvil.pinnedRsqs";

function loadPins(): string[] {
  try {
    const raw = localStorage.getItem(PINS_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/**
 * RSQ catalog grouped by domain (collapsible groups, sorted, with counts).
 * Names render in monospace; domains/descriptions in serif. Each item exposes a
 * per-RSQ docs link that opens in a new tab, plus a pin toggle; pinned RSQs are
 * kept in a quick-access group at the top (persisted in localStorage).
 */
export function Catalog({ entries, selected, onSelect, loading, error }: Props) {
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [pins, setPins] = useState<string[]>(loadPins);

  const togglePin = (name: string) => {
    setPins((p) => {
      const next = p.includes(name) ? p.filter((x) => x !== name) : [...p, name];
      try {
        localStorage.setItem(PINS_KEY, JSON.stringify(next));
      } catch {
        /* storage unavailable: pin lives for the session only */
      }
      return next;
    });
  };

  const filtered = useMemo(
    () => entries.filter((e) => matchesQuery(e, query.trim())),
    [entries, query],
  );
  const groups = useMemo(() => groupByDomain(filtered), [filtered]);
  const pinned = useMemo(
    () => filtered.filter((e) => pins.includes(e.name)),
    [filtered, pins],
  );

  // While searching, auto-expand every group so matches are always visible.
  const searching = query.trim() !== "";

  // Ensure the group containing the selected item is expanded when it changes.
  useEffect(() => {
    if (!selected) return;
    const ent = entries.find((e) => e.name === selected);
    const dom = ent?.domain?.trim() || "(uncategorized)";
    setCollapsed((c) => (c[dom] ? { ...c, [dom]: false } : c));
  }, [selected, entries]);

  const toggle = (domain: string) =>
    setCollapsed((c) => ({ ...c, [domain]: !c[domain] }));

  const renderItem = (e: RegistryEntry) => (
    <li key={e.name}>
      <button
        className={`catalog-item ${selected === e.name ? "active" : ""}`}
        onClick={() => onSelect(e.name)}
      >
        <span className="catalog-item-head">
          <span className="catalog-name">{e.name}</span>
          <span className="catalog-item-badges">
            {e.project && <span className="chip chip-project">project</span>}
            <span className={`badge badge-${e.type}`}>
              {TYPE_LABEL[e.type] ?? e.type}
            </span>
          </span>
        </span>
        {e.description && <span className="catalog-desc">{e.description}</span>}
      </button>
      <span className="catalog-item-actions">
        <button
          className={`catalog-pin ${pins.includes(e.name) ? "pinned" : ""}`}
          onClick={(ev) => {
            ev.stopPropagation();
            togglePin(e.name);
          }}
          title={pins.includes(e.name) ? `Unpin ${e.name}` : `Pin ${e.name} for quick access`}
          aria-label={pins.includes(e.name) ? `Unpin ${e.name}` : `Pin ${e.name}`}
        >
          {pins.includes(e.name) ? "★" : "☆"}
        </button>
        <a
          className="catalog-doc"
          href={rsqDocsUrl(e.name)}
          {...NEW_TAB}
          title={`Open docs for ${e.name} in a new tab`}
          onClick={(ev) => ev.stopPropagation()}
        >
          docs ↗
        </a>
      </span>
    </li>
  );

  return (
    <aside className="catalog">
      <div className="catalog-search">
        <input
          type="search"
          placeholder="Search RSQs…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search RSQ catalog"
        />
        <span className="catalog-count">
          {filtered.length}/{entries.length}
        </span>
      </div>

      {loading && <div className="catalog-msg">Loading catalog…</div>}
      {error && <div className="catalog-msg error">{error}</div>}

      <div className="catalog-groups">
        {pinned.length > 0 && (
          <section className="domain-group domain-group-pinned">
            <div className="domain-head domain-head-static">
              <span className="domain-caret">★</span>
              <span className="domain-name">pinned</span>
              <span className="domain-count">{pinned.length}</span>
            </div>
            <ul className="catalog-list">{pinned.map(renderItem)}</ul>
          </section>
        )}
        {groups.map((g) => {
          const isOpen = searching || !collapsed[g.domain];
          return (
            <section key={g.domain} className="domain-group">
              <button
                className="domain-head"
                onClick={() => toggle(g.domain)}
                aria-expanded={isOpen}
              >
                <span className="domain-caret">{isOpen ? "▾" : "▸"}</span>
                <span className="domain-name">{g.domain}</span>
                <span className="domain-count">{g.entries.length}</span>
              </button>
              {isOpen && (
                <ul className="catalog-list">{g.entries.map(renderItem)}</ul>
              )}
            </section>
          );
        })}
        {!loading && filtered.length === 0 && (
          <div className="catalog-msg">No matches.</div>
        )}
      </div>
    </aside>
  );
}
