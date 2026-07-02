import { useMemo, useState } from "react";
import type { RegistryEntry } from "../lib/types";

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

export function Catalog({ entries, selected, onSelect, loading, error }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => {
      return (
        e.name.toLowerCase().includes(q) ||
        e.domain.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [entries, query]);

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

      <ul className="catalog-list">
        {filtered.map((e) => (
          <li key={e.name}>
            <button
              className={`catalog-item ${selected === e.name ? "active" : ""}`}
              onClick={() => onSelect(e.name)}
            >
              <span className="catalog-item-head">
                <span className="catalog-name">{e.name}</span>
                <span className={`badge badge-${e.type}`}>
                  {TYPE_LABEL[e.type] ?? e.type}
                </span>
              </span>
              {e.domain && <span className="catalog-domain">{e.domain}</span>}
              {e.description && (
                <span className="catalog-desc">{e.description}</span>
              )}
            </button>
          </li>
        ))}
        {!loading && filtered.length === 0 && (
          <li className="catalog-msg">No matches.</li>
        )}
      </ul>
    </aside>
  );
}
