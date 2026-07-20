# Contributing & Extending Anvil

Anything in Anvil, a unit, an RSQ, an adapter, a wiki page, is added by editing one predictable place. This page is the map.

**Priorities** (in order): native functions, sweep, sensitivity, the unit engine, the project database, re-usability, robustness. Adapters to external tools come **after** all of those, they are conveniences, never load-bearing, and they are **real-only** (no mock fallbacks; see [Adapters](10_adapters.md)).

---

## Repo Layout (what to touch for what)

| I want to... | Edit |
|--------------|------|
| Add/fix a unit | `src/anvil/units.py` |
| Add a built-in RSQ | `src/anvil/seed.py` |
| Add an adapter | `src/anvil/adapters/<lib>.py` |
| Change solving/sweep/sensitivity | `src/anvil/system.py`, `src/anvil/solvers/` |
| Change the web API | `anvil_server/app/` |
| Change the web UI | `anvil_web/src/` |
| Update docs | `docs/wiki/*.md`, then rebuild (below) |
| Add an example | `examples/` |
| Add a test | `tests/` |

---

## Adding a Unit

Units live in `src/anvil/units.py` in the `UnitDB` definitions: each unit maps a string to `(scale_to_SI, Dim)`. Find the category block (pressure, energy, ...) and add a line following its neighbours. Offset units (like `degC`, `degF`) additionally carry an offset, see how those two are defined before adding another.

Checklist:

1. Add the definition next to its category.
2. `python -c "import anvil; print(anvil.Q(1,'<new_unit>').to('<si_unit>'))"` round-trips correctly.
3. Add a conversion case to `tests/` (see `test_v03.py` unit-conversion checks).
4. Update the unit count in `docs/wiki/index.md` and `README.md` if you changed the total.

## Adding a Built-in RSQ

Built-ins are seeded from `src/anvil/seed.py`. Each RSQ is a plain function, keyword inputs, dict of outputs (values as `Q` where dimensional), pushed with a domain and tags. Copy the closest existing entry in the same domain.

Rules that keep RSQs reusable:

- Inputs are SI floats or dimensionless; accept `Q` transparently where the neighbours do.
- Return `{"name": Q(value, "unit"), ...}`, declared units let Systems propagate dimensions.
- One equation set per RSQ; compose bigger models in a `System`, not inside one function.
- Docstring: one-line summary + the equation + input/output meaning. The wiki and the workbench catalog both surface it.

Then: add it to `docs/wiki/09_builtin_rsqs.md` under its domain, bump the counts, add a test.

For your **own project's** RSQs you don't edit the repo at all, use the project database:

```python
proj = anvil.project("my_study", path="./work")
proj.push(my_func, domain="aero", tags=["compressible"])
proj.promote("my_func")   # optional: copy into the global registry
```

## Adding an Adapter

Follow the real-only pattern in [Adapters](10_adapters.md) exactly:

1. `src/anvil/adapters/<lib>.py` with `_require_<lib>()` (raises `ImportError`/`RuntimeError` with the install command) and `is_available() -> bool`.
2. Lazy-import the library **inside** the wrapper; the module must import cleanly without the dependency.
3. **No mock fallbacks.** A missing tool is an error, not an approximation. If closed-form physics exists, it belongs in `seed.py` as a native RSQ instead.
4. `register()` pushing to a sensible `domain.subdomain`.
5. An `examples/ex_<lib>_adapter.py` that starts with the availability guard:

```python
from anvil.adapters import mylib_adapter
if not mylib_adapter.is_available():
    print("mylib not installed -- skipping example.")
    print("Install: pip install mylib")
    raise SystemExit(0)
```

6. A row in the Adapter Comparison table in `docs/wiki/10_adapters.md`.

## Adding a Wiki Page

1. Write `docs/wiki/NN_topic.md` (plain Markdown; fenced code blocks and tables supported).
2. Register it in `docs/build_wiki.py`: add to `PAGES` and to a `SECTION_GROUPS` group.
3. Rebuild:

```bash
cd docs
python build_wiki.py        # → ANVIL_WIKI.html + index.html
```

The build produces a single self-contained HTML file (all CSS/JS inline) written to both `ANVIL_WIKI.html` (served at `/wiki` by the workbench server) and `index.html` (so the `docs/` folder deploys directly to any static host, e.g. Cloudflare Pages with `docs` as the build output directory and **no build command**).

## Web UI Development

```bash
cd anvil_web
npm install
npm run dev        # Vite on http://localhost:5173, API proxied to :8000
npm run build      # production bundle → anvil_web/dist (served by the backend)
```

Backend dev: `python -m anvil_server.run` reloads are manual; the API surface is defined in `anvil_server/app/` with Pydantic schemas in `schemas.py`.

---

## Tests

```bash
python -m pytest tests/ -q        # pytest-compatible suite
python tests/test_v03.py          # standalone check scripts also run directly
```

Conventions: test files double as runnable scripts (`if __name__ == "__main__":` guards); helper assertion decorators are named `check`, not `test`, so pytest doesn't collect them as fixtures.

Before submitting changes:

1. Full test suite passes.
2. Any touched example still runs (`python examples/ex_*.py`, adapter examples must exit 0 with an install hint when the tool is absent).
3. Wiki rebuilt if you touched `docs/wiki/`.
4. Counts in `index.md` / `README.md` still true if you added units or RSQs.
