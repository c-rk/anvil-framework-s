# Anvil Server (M3 backend)

A FastAPI wrapper over the Anvil RSQ registry and solver. It exposes the
in-process Anvil API (registry, `anvil.check`, `anvil.solve`, sweeps) over HTTP
so the `anvil_web` calculator front-end (and other clients) can use it.

## Install

```powershell
# from the repo root, with `anvil` already installed (pip install -e .)
python -m pip install -r anvil_server/requirements.txt
```

## Run

### Tier A — in-process (default)

```powershell
python -m anvil_server.run
# serves http://127.0.0.1:8000
```

One command serves the whole app from a single origin:

- `/` — the built web UI (`anvil_web/dist`, if present; run `npm run build`
  in `anvil_web/` once to produce it)
- `/wiki` — the reference documentation (`docs/ANVIL_WIKI.html` and the rest
  of `docs/`); all "Docs" links in the UI point here
- `/api/*`, `/ws/*`, `/healthz` — the JSON/WebSocket API

The Vite dev server (`npm run dev` in `anvil_web/`, port 5173) still works for
frontend development; it proxies to `http://127.0.0.1:8000` by default.

Or directly via uvicorn:

```powershell
uvicorn anvil_server.app.main:app --host 127.0.0.1 --port 8000
```

### Tier B — native-only

Set `NATIVE_ONLY=1`. This filters the registry exposed by `/api/registry` and
`/api/rsq/{name}` to RSQs that:

- do **not** carry the `tierA` / `cli` tags, and
- declare **no** external-binary requirement in their metadata
  (`external_binary` / `requires_binary` / `binary`).

```powershell
$env:NATIVE_ONLY = "1"; python -m anvil_server.run
```

> The current Anvil seed registry uses none of those tags and no external-binary
> RSQs, so Tier B currently exposes the same catalog as Tier A. The filter is
> intentionally conservative — it is wired up and documented so newly added
> tier-A/CLI/binary RSQs are excluded automatically without further code
> changes. See `anvil_server/app/config.py`.

### Environment variables

| Variable             | Default       | Meaning                                   |
| -------------------- | ------------- | ----------------------------------------- |
| `ANVIL_HOST`         | `127.0.0.1`   | Bind host                                 |
| `ANVIL_PORT`         | `8000`        | Bind port                                 |
| `NATIVE_ONLY`        | `0`           | `1`/`true` -> Tier B registry filtering   |
| `ANVIL_CORS_ORIGINS` | _(empty)_     | Comma-separated extra CORS origins        |

CORS is preconfigured for the Vite dev server (`http://localhost:5173` and
`http://127.0.0.1:5173`).

## Endpoints

| Method | Path                | Description                                              |
| ------ | ------------------- | ------------------------------------------------------- |
| GET    | `/healthz`          | Liveness + Anvil version + active tier + RSQ count      |
| GET    | `/api/registry`     | List RSQs: name, type, domain, description, tags        |
| GET    | `/api/rsq/{name}`   | Signature, inputs, outputs, defaults, description, latex|
| POST   | `/api/solve`        | Run `anvil.solve`; returns values + units + solver method |
| POST   | `/api/sweep`        | Parametric sweep; returns `SweepResult` data            |

Interactive docs: `http://127.0.0.1:8000/docs`.

### `POST /api/solve` body

```json
{
  "name": "isentropic_ratios",
  "inputs": { "M": 2.0, "gamma": 1.4 },
  "si": false
}
```

Inputs may be bare numbers or `{"value": x, "unit": "Pa"}` objects (the unit is
applied as an Anvil `Quantity`).

### `POST /api/sweep` body

```json
{
  "name": "isentropic_ratios",
  "param": "M",
  "values": [1.5, 2.0, 2.5],
  "outputs": ["P0_P"],
  "inputs": { "gamma": 1.4 },
  "si": true
}
```

## Notes / architecture

- All Anvil access is isolated in `anvil_server/app/executor.py` (Tier A,
  in-process). The HTTP layer (`app/main.py`) never imports `anvil` directly,
  so a future sandbox/subprocess tier can be swapped in there.
- Route handlers are `async def` on purpose: the Anvil registry uses a
  thread-bound SQLite connection, so keeping all access on the single event-loop
  thread avoids `SQLite objects created in a thread...` errors.
- Response shapes mirror the real Anvil objects:
  `Result.to_json()` -> `{name: {value, unit}}`, `Result.method`, and
  `anvil.check()` for inputs/outputs/defaults.
