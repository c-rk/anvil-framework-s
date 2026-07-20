import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, API_BASE } from "./lib/api";
import type { RegistryEntry } from "./lib/types";
import { DOCS_URL, NEW_TAB } from "./lib/docs";
import { useConnection } from "./hooks/useConnection";
import { Catalog } from "./components/Catalog";
import { Calculator } from "./components/Calculator";
import { CalcPad } from "./components/CalcPad";
import { Builder } from "./components/Builder";
import { Spotlight } from "./components/Spotlight";
import { ShortcutsHelp } from "./components/ShortcutsHelp";

type Theme = "dark" | "light";
type Page = "calculator" | "canvas";

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("anvil-theme");
    if (saved === "light" || saved === "dark") return saved;
    // No saved preference: respect the OS color scheme (dark-first fallback).
    return window.matchMedia?.("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("anvil-theme", theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [entries, setEntries] = useState<RegistryEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("calculator");

  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // When the spotlight targets the Canvas, we hand the RSQ to the Builder to
  // drop onto the canvas; a counter forces a fresh drop even for repeats.
  const [canvasDrop, setCanvasDrop] = useState<{ name: string; seq: number } | null>(
    null,
  );
  const dropSeq = useRef(0);

  const { status, health, recheck } = useConnection();

  // B1 inclusion rule for the Calculator picker: show NON-ADAPTER relations
  // (includes array/signal-processing RSQs; excludes adapters). Quantity-only
  // entries (type "Q") aren't directly solvable, so they're dropped too.
  const calcEntries = useMemo(
    () =>
      entries.filter(
        (e) => e.adapter !== true && (e.type === "R" || e.type === "S"),
      ),
    [entries],
  );

  // Load the registry once. Re-load automatically when the API recovers.
  const loadRegistry = useCallback(() => {
    setLoading(true);
    api
      .registry()
      .then((r) => {
        setEntries(r.items);
        setError(null);
        const firstCalc = r.items.find(
          (e) => e.adapter !== true && (e.type === "R" || e.type === "S"),
        );
        setSelected(
          (cur) => cur ?? firstCalc?.name ?? (r.items.length > 0 ? r.items[0].name : null),
        );
      })
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRegistry();
  }, [loadRegistry]);

  // If we were empty/errored and the backend comes back, retry the registry.
  useEffect(() => {
    if (status === "connected" && (entries.length === 0 || error)) {
      loadRegistry();
    }
  }, [status, entries.length, error, loadRegistry]);

  // Navigate to an RSQ from the spotlight: open in Calculator, or drop on Canvas.
  const openRsq = useCallback(
    (name: string) => {
      setSelected(name);
      if (page === "canvas") {
        dropSeq.current += 1;
        setCanvasDrop({ name, seq: dropSeq.current });
      }
    },
    [page],
  );

  // ----------------------------- global keys -----------------------------
  useEffect(() => {
    let pendingG = false;
    let gTimer: number | null = null;

    const isTyping = () => {
      const el = document.activeElement as HTMLElement | null;
      if (!el) return false;
      const tag = el.tagName;
      return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        el.isContentEditable
      );
    };

    const onKey = (e: KeyboardEvent) => {
      // Ctrl/Cmd-K — spotlight (works even while typing).
      if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setHelpOpen(false);
        setSpotlightOpen((o) => !o);
        return;
      }

      if (isTyping()) return;

      // "?" — shortcuts help.
      if (e.key === "?") {
        e.preventDefault();
        setSpotlightOpen(false);
        setHelpOpen((o) => !o);
        return;
      }

      // "t" — theme toggle.
      if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        toggleTheme();
        return;
      }

      // "g" then "c"/"v" — page navigation.
      if (e.key === "g" || e.key === "G") {
        pendingG = true;
        if (gTimer) window.clearTimeout(gTimer);
        gTimer = window.setTimeout(() => (pendingG = false), 800);
        return;
      }
      if (pendingG && (e.key === "c" || e.key === "C")) {
        pendingG = false;
        setPage("calculator");
        return;
      }
      if (pendingG && (e.key === "v" || e.key === "V")) {
        pendingG = false;
        setPage("canvas");
        return;
      }
      pendingG = false;
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (gTimer) window.clearTimeout(gTimer);
    };
  }, [toggleTheme]);

  const disconnected = status === "disconnected";

  return (
    <div className="app">
      {disconnected && (
        <div className="conn-banner" role="alert">
          Backend disconnected — no response from <code>{API_BASE}</code>. Start
          the server with <code>python -m anvil_server.run</code>; this page
          reconnects automatically.{" "}
          <button className="conn-retry" onClick={recheck}>
            Retry now
          </button>
        </div>
      )}

      <header className="topbar">
        <div className="brand">
          <AnvilGlyph />
          <span className="brand-name">Anvil</span>
          <span className="brand-sub">RSQ Workbench</span>
        </div>

        <nav className="view-tabs" role="tablist" aria-label="Pages">
          <button
            className={`view-tab ${page === "calculator" ? "active" : ""}`}
            onClick={() => setPage("calculator")}
            role="tab"
            aria-selected={page === "calculator"}
          >
            Calculator
          </button>
          <button
            className={`view-tab ${page === "canvas" ? "active" : ""}`}
            onClick={() => setPage("canvas")}
            role="tab"
            aria-selected={page === "canvas"}
          >
            Canvas
          </button>
        </nav>

        <div className="topbar-right">
          <button
            className="ghost-btn spotlight-trigger"
            onClick={() => setSpotlightOpen(true)}
            title="Search RSQs (Ctrl/Cmd-K)"
          >
            <span className="ghost-label">Search</span>
            <kbd className="kbd">⌘K</kbd>
          </button>

          <span
            className={`conn-badge conn-${status}`}
            title={
              status === "connected"
                ? health
                  ? `Anvil ${health.anvil_version} · ${health.rsq_count} RSQs · Tier ${health.tier}`
                  : "Backend connected"
                : status === "connecting"
                  ? "Checking backend…"
                  : "Backend unreachable"
            }
          >
            <span className="conn-dot" aria-hidden />
            API: {status === "connected" ? "connected" : status === "connecting" ? "…" : "disconnected"}
          </span>

          {status === "connected" && health && (
            <span className="health">
              {health.rsq_count} RSQs · Tier {health.tier}
            </span>
          )}

          <a className="ghost-btn" href={DOCS_URL} {...NEW_TAB} title="Open documentation in a new tab">
            Docs ↗
          </a>

          <button
            className="ghost-btn icon-btn"
            onClick={() => setHelpOpen(true)}
            title="Keyboard shortcuts (?)"
            aria-label="Keyboard shortcuts"
          >
            ?
          </button>

          <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme (t)">
            {theme === "dark" ? "☀ Light" : "☾ Dark"}
          </button>
        </div>
      </header>

      {page === "canvas" ? (
        <main className="layout-full">
          {loading ? (
            <div className="panel muted">Loading registry…</div>
          ) : error ? (
            <div className="panel error">{error}</div>
          ) : (
            <Builder entries={entries} dropRequest={canvasDrop} />
          )}
        </main>
      ) : (
        <main className="layout">
          <Catalog
            entries={calcEntries}
            selected={selected}
            onSelect={setSelected}
            loading={loading}
            error={error}
          />
          <div className="center">
            {selected ? (
              <Calculator key={selected} name={selected} />
            ) : (
              <div className="panel muted">
                {loading ? "Loading…" : "Select an RSQ from the catalog."}
              </div>
            )}
          </div>
          <CalcPad />
        </main>
      )}

      <Spotlight
        open={spotlightOpen}
        entries={entries}
        page={page}
        onClose={() => setSpotlightOpen(false)}
        onSelect={openRsq}
      />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

/** Inline monochrome anvil glyph for the brand mark (matches the favicon). */
function AnvilGlyph() {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" width="22" height="22" aria-hidden>
      <path
        fill="currentColor"
        d="M6 21C13 18 22 18 28 21L54 21L54 27L44 27C42 31 38 33 32 33L38 33L38 37L26 37L26 33L20 33L20 27L10 27C8 26 7 23 6 21Z"
      />
      <path fill="currentColor" d="M23 39L41 39L41 42L50 50L50 53L14 53L14 50L23 42Z" />
    </svg>
  );
}
