# Anvil Web (M3 front-end)

A sleek, dark-first React + Vite + TypeScript SPA that serves Anvil's RSQs in
the browser. The MVP is an **RSQ calculator** built as a self-contained,
reusable component (`src/components/Calculator.tsx`) so it can later be embedded
as a node in a system-builder canvas.

## Features

- **Searchable catalog** (left): lists every RSQ from `/api/registry`, with
  client-side filtering across name, domain, description, and tags.
- **Auto-generated calculator** (center): loads the selected RSQ from
  `/api/rsq/{name}`, builds a numeric input form with unit labels, runs
  `POST /api/solve`, and shows a results table with values + units, the solver
  **method** that ran, and **CSV / JSON export**.
- **KaTeX typeset math**: renders an RSQ's `latex` formula when its metadata
  provides one; otherwise it falls back to the Python signature.
- **Dark-first theme** with a light toggle (persisted to `localStorage`).
- Minimal dependencies (React, Vite, KaTeX), plain `fetch`, responsive layout.

## Prerequisites

- Node 18+ and npm.
- The `anvil_server` backend running (default `http://127.0.0.1:8000`).
  See `../anvil_server/README.md`.

## Setup & run

```powershell
cd anvil_web
npm install
npm run dev
# open http://localhost:5173
```

Build for production:

```powershell
npm run build      # type-checks then bundles to dist/
npm run preview    # serve the production build
```

## API base URL

The backend URL is read from `VITE_API_BASE` (default
`http://127.0.0.1:8000`). To override, copy `.env.example` to `.env`:

```
VITE_API_BASE=http://127.0.0.1:8000
```

The backend already enables CORS for the Vite dev server
(`http://localhost:5173`).

## Project layout

```
anvil_web/
├─ index.html
├─ package.json
├─ vite.config.ts
├─ tsconfig.json / tsconfig.node.json
├─ .env.example
└─ src/
   ├─ main.tsx              entry; imports KaTeX CSS + global styles
   ├─ App.tsx               shell: topbar, theme toggle, catalog + center
   ├─ styles.css            dark-first theme via CSS custom properties
   ├─ lib/
   │  ├─ api.ts             typed fetch client for the backend
   │  ├─ types.ts           response types mirroring the backend models
   │  └─ export.ts          CSV / JSON download helpers
   └─ components/
      ├─ Catalog.tsx        searchable registry list
      ├─ Calculator.tsx     reusable RSQ calculator (self-contained)
      └─ MathView.tsx       KaTeX renderer with signature fallback
```

## Reusability note

`Calculator` takes a single `name` prop and owns its own data fetching and
state. Drop `<Calculator name="isentropic_ratios" />` anywhere — no external
wiring needed — which is what the future system-builder canvas will do per node.
