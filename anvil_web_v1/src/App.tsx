import { useEffect, useState } from "react";
import { api } from "./lib/api";
import type { HealthResponse, RegistryEntry } from "./lib/types";
import { Catalog } from "./components/Catalog";
import { Calculator } from "./components/Calculator";
import { Builder } from "./components/Builder";
import { SweepPanel } from "./components/SweepPanel";

type Theme = "dark" | "light";
type View = "calculator" | "builder" | "plots";

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("anvil-theme");
    return saved === "light" ? "light" : "dark";
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
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [view, setView] = useState<View>("calculator");

  useEffect(() => {
    api
      .registry()
      .then((r) => {
        setEntries(r.items);
        if (r.items.length > 0) setSelected(r.items[0].name);
      })
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
    api.health().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">⚒</span>
          <span className="brand-name">Anvil</span>
          <span className="brand-sub">RSQ Workbench</span>
        </div>

        <nav className="view-tabs" role="tablist">
          <button
            className={`view-tab ${view === "calculator" ? "active" : ""}`}
            onClick={() => setView("calculator")}
            role="tab"
            aria-selected={view === "calculator"}
          >
            Calculator
          </button>
          <button
            className={`view-tab ${view === "builder" ? "active" : ""}`}
            onClick={() => setView("builder")}
            role="tab"
            aria-selected={view === "builder"}
          >
            Builder
          </button>
          <button
            className={`view-tab ${view === "plots" ? "active" : ""}`}
            onClick={() => setView("plots")}
            role="tab"
            aria-selected={view === "plots"}
          >
            Plots
          </button>
        </nav>

        <div className="topbar-right">
          {health && (
            <span className="health" title={`Anvil ${health.anvil_version}`}>
              {health.rsq_count} RSQs · Tier {health.tier}
            </span>
          )}
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === "dark" ? "☀ Light" : "☾ Dark"}
          </button>
        </div>
      </header>

      {view === "builder" ? (
        <main className="layout-full">
          {loading ? (
            <div className="panel muted">Loading registry…</div>
          ) : error ? (
            <div className="panel error">{error}</div>
          ) : (
            <Builder entries={entries} />
          )}
        </main>
      ) : (
        <main className="layout">
          <Catalog
            entries={entries}
            selected={selected}
            onSelect={setSelected}
            loading={loading}
            error={error}
          />
          <div className="center">
            {view === "plots" ? (
              selected ? (
                <section className="plots-view">
                  <h2>Plots — {selected}</h2>
                  <p className="calc-desc">
                    Parametric sweep of an input vs the relation’s outputs. For
                    live residual convergence and variable traces, use the
                    Builder’s Solve panel.
                  </p>
                  <SweepPanel key={selected} name={selected} />
                </section>
              ) : (
                <div className="panel muted">
                  {loading ? "Loading…" : "Select an RSQ to plot."}
                </div>
              )
            ) : selected ? (
              <Calculator key={selected} name={selected} />
            ) : (
              <div className="panel muted">
                {loading ? "Loading…" : "Select an RSQ from the catalog."}
              </div>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
