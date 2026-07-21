# Web Workbench

The Web Workbench is Anvil's browser UI: a **Calculator** for calling any registered RSQ with units, and a **Canvas** for building solvable systems visually. One local server serves the UI, the JSON/WebSocket API, and this wiki from a single origin.

The workbench is the third (optional) run tier, the core package and the project database work without it. See [Overview](index.md).

---

## Quick Start

```bash
# 1. Server dependencies (FastAPI + uvicorn)
pip install -r anvil_server/requirements.txt

# 2. Build the frontend once (Node 18+)
cd anvil_web && npm install && npm run build && cd ..

# 3. Run
python -m anvil_server.run
# → UI    http://127.0.0.1:8000/
# → wiki  http://127.0.0.1:8000/wiki
# → API   http://127.0.0.1:8000/api/...
```

**Mount a project database** so its RSQs appear alongside the 101 built-ins:

```bash
python -m anvil_server.run --project ./my_study
```

| Env var | Default | Purpose |
|---------|---------|---------|
| `ANVIL_HOST` | `127.0.0.1` | Bind address |
| `ANVIL_PORT` | `8000` | Port |
| `ANVIL_PROJECT` |, | Same as `--project` |
| `NATIVE_ONLY` | off | Tier B: hide adapter RSQs, sandbox execution |
| `ANVIL_CORS_ORIGINS` |, | Extra CORS origins (comma-separated) |

For frontend development, run `npm run dev` in `anvil_web/` (Vite dev server on port 5173, proxying to the API at 8000).

---

## Calculator Page

- **Catalog**, browse every RSQ from the global registry (and the mounted project registry), grouped by domain. Categories are collapsible. Each entry links to its wiki section.
- **Calc pad**, pick an RSQ, fill inputs (units accepted, e.g. `500 kPa`), get outputs with units and LaTeX-rendered relations (KaTeX).
- **Sweep panel**, sweep any input over a range and plot the response inline.

## Canvas Page

A node-graph editor (React Flow) where quantity blocks wire into relation blocks to form a System:

- **Palette**, add quantity nodes and relation/adapter nodes; grouped by domain, collapsible.
- **Solve**, runs the graph server-side; iterative solves stream residuals live over WebSocket.
- **Auto-align**, one click re-lays the graph left-to-right by dependency depth (quantities → relations → outputs) so nothing overlaps.
- **Script bridge**, every canvas serializes to a plain Python script and back. `GET /api/example-scripts` lists the repo's `examples/*.py` that parse into non-empty canvases; loading one populates the graph.
- **Save/load**, canvases persist server-side as scripts (`PUT /api/canvases/{name}`).

---

## API Reference (summary)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Liveness + version |
| `/api/registry` | GET | All RSQs (global + project) with metadata |
| `/api/registry/refresh` | POST | Re-read registry databases |
| `/api/rsq/{name}` | GET | One RSQ: signature, units, source, docs link |
| `/api/solve` | POST | Call one RSQ with inputs |
| `/api/sweep` | POST | Sweep an input, return table |
| `/api/system/solve` | POST | Solve a canvas graph as a System |
| `/ws/system/solve` | WS | System solve with live residual streaming |
| `/api/canvases` | GET/PUT/DELETE | Saved canvases (as Python scripts) |
| `/api/canvases/parse` | POST | Script text → canvas graph |
| `/api/example-scripts` | GET | Example scripts that produce valid canvases |
| `/api/viz/sweep`, `/api/viz/convergence` | POST | Server-rendered plots |
| `/wiki` | GET | This wiki (static) |
| `/` | GET | The built SPA (`anvil_web/dist`) |

Interactive OpenAPI docs at `http://127.0.0.1:8000/docs` while the server runs.

---

## Execution Tiers

| Tier | Flag | Behaviour |
|------|------|-----------|
| A | default | RSQs run in-process; fastest; trusted local use |
| B | `NATIVE_ONLY=1` | Adapter RSQs hidden; solves run in a sandboxed subprocess with a timeout |

---

## Architecture

```
anvil_server/            FastAPI backend
├── run.py               entry point (python -m anvil_server.run)
└── app/
    ├── main.py          app factory, registry/solve/sweep/viz routes, static mounts
    ├── builder_routes.py    /api/system/solve + /ws/system/solve
    ├── canvas_routes.py     canvas CRUD + script parse/serialize (AST-based)
    ├── ws_routes.py         /ws/solve residual streaming
    ├── executor.py          Tier A/B execution
    ├── sandbox.py           subprocess sandbox for Tier B
    └── schemas.py           Pydantic request/response models

anvil_web/               React 18 + TypeScript + Vite frontend
└── src/
    ├── components/      Calculator, Catalog, Builder (canvas), SweepPanel, ...
    ├── components/nodes/    canvas node types (quantity, relation, result)
    └── lib/             API client, docs links, graph layout
```

The canvas ↔ script bridge is the design centre: the canvas is never a separate format, it **is** a Python script, so anything built visually runs headless with plain `python`, and any example script opens as a canvas.

---

## Calculator features

Beyond running a single RSQ with unit-aware inputs, the Calculator page has:

- **Formula rendering.** Every RSQ shows its formula typeset with KaTeX (from
  the RSQ `latex` metadata), falling back to the Python signature when none is
  set.
- **Relation packs.** Chips above the catalog filter the RSQ list to a curated
  pack (Jet Engine Cycle, Compressible Flow, Heat Transfer, Structures, Curve
  Fitting, and more). Packs match by domain and tags, so newly seeded RSQs join
  the right pack automatically.
- **Curve fitting and data tables.** The fitting RSQs (`linear_regression`,
  `poly_fit`, `power_fit`, `exp_fit`) take `x_data` and `y_data` arrays. Paste a
  data table into the CSV box and map columns straight onto the array inputs,
  then read back the coefficients, R-squared and fitted curve.
- **Result comparison.** Click **+ Compare** on any result to pin it into the
  comparison tray, which lines up every pinned run as a column with one row per
  variable. Export the whole comparison as CSV.
- **Report export.** Export a solved RSQ as a self-contained **HTML** report
  (formula as MathML, inputs and results tables, ready to print) or as
  **Markdown**, alongside the raw CSV and JSON exports.

## Keypad, memory and navigation

The right-hand pane of the Calculator page and a few global keys round out the
workbench:

- **Scientific keypad.** A calculator pad evaluates freeform expressions
  (trig, logs, powers, constants) with a rad/deg angle-mode toggle, independent
  of any RSQ.
- **Memory plane.** Named slots plus an auto-log of recent results sit below the
  keypad. Press **M+** on any RSQ result to drop it into memory instantly; slots
  and history persist in `localStorage` and sync live with the calculator.
- **Spotlight.** Press **Ctrl/Cmd-K** for a fuzzy command palette that searches
  every RSQ by name and description. Enter opens the match in the Calculator, or
  drops it onto the Canvas when that page is active.
- **Keyboard shortcuts.** `?` opens the shortcuts help, `t` toggles the theme,
  and `g` then `c` / `v` jumps between the Calculator and Canvas pages.
- **Pinning.** The star toggle on any catalog entry pins it to a quick-access
  group at the top of the catalog (persisted in `localStorage`).
