import { useEffect, useMemo, useRef, useState } from "react";
import type { RegistryEntry } from "../lib/types";

interface Props {
  open: boolean;
  entries: RegistryEntry[];
  /** Where the user currently is — affects the action verb shown. */
  page: "calculator" | "canvas";
  onClose: () => void;
  /** Fired with the chosen RSQ name. The host decides open-in-calculator vs drop-on-canvas. */
  onSelect: (name: string) => void;
}

interface Scored {
  entry: RegistryEntry;
  score: number;
}

/**
 * Subsequence fuzzy score: characters of `q` must appear in order in `text`.
 * Returns a positive score (higher = better, contiguous/early matches win) or
 * -1 for no match. Cheap and dependency-free.
 */
function fuzzyScore(text: string, q: string): number {
  if (!q) return 0;
  const t = text.toLowerCase();
  const needle = q.toLowerCase();
  let ti = 0;
  let score = 0;
  let streak = 0;
  let firstIdx = -1;
  for (let qi = 0; qi < needle.length; qi++) {
    const ch = needle[qi];
    const found = t.indexOf(ch, ti);
    if (found === -1) return -1;
    if (firstIdx === -1) firstIdx = found;
    streak = found === ti ? streak + 1 : 0;
    score += 1 + streak; // reward contiguous runs
    ti = found + 1;
  }
  // Reward early matches.
  score += Math.max(0, 10 - firstIdx);
  return score;
}

/**
 * Global Ctrl/Cmd-K command palette. Fuzzy-searches RSQs by name, domain and
 * description. Arrow keys move the selection, Enter activates, Esc closes.
 * Names render mono; domain + description render serif.
 */
export function Spotlight({ open, entries, page, onClose, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Reset state each time the palette opens, and focus the input.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // Focus after the overlay mounts.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const results = useMemo<Scored[]>(() => {
    const q = query.trim();
    if (!q) {
      return entries
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(0, 50)
        .map((entry) => ({ entry, score: 0 }));
    }
    const scored: Scored[] = [];
    for (const entry of entries) {
      const haystacks = [entry.name, entry.domain ?? "", entry.description ?? ""];
      let best = -1;
      for (let i = 0; i < haystacks.length; i++) {
        const s = fuzzyScore(haystacks[i], q);
        // Weight name matches highest, then domain, then description.
        const weighted = s < 0 ? -1 : s + (2 - i) * 5;
        if (weighted > best) best = weighted;
      }
      if (best >= 0) scored.push({ entry, score: best });
    }
    scored.sort(
      (a, b) => b.score - a.score || a.entry.name.localeCompare(b.entry.name),
    );
    return scored.slice(0, 50);
  }, [entries, query]);

  // Keep the active index in range as results change.
  useEffect(() => {
    setActive((a) => (results.length === 0 ? 0 : Math.min(a, results.length - 1)));
  }, [results.length]);

  // Scroll the active row into view.
  useEffect(() => {
    const el = listRef.current?.children[active] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const verb = page === "canvas" ? "Drop on canvas" : "Open in Calculator";

  function choose(name: string) {
    onSelect(name);
    onClose();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = results[active];
      if (hit) choose(hit.entry.name);
    }
  }

  return (
    <div
      className="spotlight-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="spotlight" role="dialog" aria-modal="true" aria-label="Search RSQs">
        <div className="spotlight-input-row">
          <span className="spotlight-icon" aria-hidden>
            ⌕
          </span>
          <input
            ref={inputRef}
            className="spotlight-input"
            placeholder="Search relations, systems, quantities…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Search RSQs"
          />
          <span className="spotlight-hint">{verb} · Esc to close</span>
        </div>
        <ul className="spotlight-results" ref={listRef}>
          {results.map(({ entry }, i) => (
            <li
              key={entry.name}
              className={`spotlight-item ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(entry.name);
              }}
            >
              <span className="spotlight-name">{entry.name}</span>
              <span className="spotlight-meta">
                {entry.domain && (
                  <span className="spotlight-domain">{entry.domain}</span>
                )}
                <span className={`badge badge-${entry.type}`}>{entry.type}</span>
              </span>
              {entry.description && (
                <span className="spotlight-desc">{entry.description}</span>
              )}
            </li>
          ))}
          {results.length === 0 && (
            <li className="spotlight-empty">No matching RSQs.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
