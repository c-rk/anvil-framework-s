# RSQ Integration Pipeline

How to add a new **RSQ** (Relation / System / Quantity) to Anvil, from first draft to shipped
built-in with tests and docs. An RSQ is a unit of reusable engineering knowledge stored as Python
source in a SQLite registry and reconstructed into a live callable on demand.

There are two paths:

- **Prototype** (Section 3): develop in an isolated project registry, never touching the global
  store. Good for experiments and study-specific relations.
- **Ship as built-in** (Section 6): add it to the seed so it registers for every user on first
  import, with tests, wiki, and gallery example. This is the path for anything that belongs in core.

Reference internals: `src/anvil/registry/{store,loader,namespace,__init__}.py`, `src/anvil/project.py`,
`src/anvil/seed.py` (the built-ins), `src/anvil/inspect.py` (`anvil.check`).

As of this writing the registry ships **132 built-ins** (123 R, 4 Q, 5 S) across 18 domains. Do not
hardcode that number anywhere you cannot keep current; read it live from `Store().get_all()`.

---

## 1. What gets stored

Each RSQ is one row in the `rsq` table (`src/anvil/registry/store.py`):

| column | meaning |
|---|---|
| `name` | unique identifier per `origin`; routinely contains `_` |
| `type` | `R` (Relation), `S` (System), or `Q` (Quantity) |
| `domain` | dot-hierarchical, e.g. `aero.compressible`, reachable at `R.aero.compressible.<name>` |
| `version` | semver string |
| `source` | the RSQ's Python code; must define an `export` variable |
| `metadata` | JSON, auto-extracted input signature for Relations |
| `tests` | JSON, persisted test metadata (not auto-asserted today) |
| `hash` | SHA256 of source |
| `origin` | `local` / `builtin` / `public` / `url`; `local` wins on name clash |

Tags and dependencies live in companion tables (`tags`, `dependencies`).

**Lifecycle:** function to `source_from_function()` extracts code (`loader.py`), `store.put()` writes
the row, `_rebuild_namespaces()` reloads it. On access, `load_rsq()` runs `exec(source, ns)` in a
controlled namespace and pulls out `export`, wrapping callables in a `Relation` with outputs
pre-parsed from the source.

> **Security note:** `loader.py` does `exec()` of stored source. Global-registry RSQs are *code* and
> must come from trusted authors. The public deployment must run the loader inside the sandbox
> (restricted builtins, no fs/network, resource caps).

---

## 2. The injected namespace (what your source may use)

When an RSQ's `source` is executed, these names are already bound, so a relation body can use them
without importing:

```
np, numpy, math, _rad,
Q, Quantity, Relation, System, solvers, units
```

`_rad(v)` converts a float in degrees to radians (or a `Q` to its SI value). `import numpy as np`,
`import math`, and `from anvil import Q, solvers` inside the source also work (guarded). Declared
`depends` RSQs are injected by name too, so an `S` builder can reference the `R`s it composes.

Every `source` **must** end by binding `export` to the object you want registered (a function, a
`System`-returning builder, or a `Quantity`).

---

## 3. Prototype path: develop in a project registry

Use an isolated project store so experimental RSQs live in your project directory while the global
registry stays readable (read-through). See `src/anvil/project.py`.

```python
import anvil
from anvil import Q

@anvil.relation(domain="aero", tags=["compressible"], register=False)
def my_mach_ratio(M, gamma=1.4):
    """Stagnation-to-static temperature ratio."""
    return {"T0_T": 1 + 0.5 * (gamma - 1) * M**2}

with anvil.project("my_study", path="./work") as proj:
    anvil.push(my_mach_ratio, domain="aero")   # -> project store, NOT global
    proj.R.my_mach_ratio(M=2.0)                 # call your project RSQ
    anvil.R.isentropic_ratios(M=2.0, gamma=1.4) # global RSQs still reachable
```

Inside the `with` block, `anvil.push()` routes to the project; outside it, `push()` goes global.
Outputs need not be literal in the `return`; dimensions are inferred from arithmetic on the
unit-carrying inputs (verified: `m*a` yields `N`).

Register / inspect / manage:

```python
anvil.check("my_mach_ratio")            # smoke test: load + one run; returns {"ok", "issues", ...}
anvil.registry.list(domain="aero")      # filter by type/domain/origin/tag
anvil.registry.search("mach")           # fuzzy (LIKE wildcards escaped; '_' is literal)
anvil.registry.info("my_mach_ratio")    # full details
anvil.registry.export("my_mach_ratio")  # print stored source
anvil.registry.remove("my_mach_ratio")  # uninstall
```

`anvil.push(obj, name=?, domain=?, version=?, tags=?, tests=?, depends=?, overwrite=?)` infers `type`
from the object. Re-registering a non-builtin name warns and overwrites; pass `overwrite=True` to
signal intent, or `anvil.update(...)` to change only some fields. `builtin`-origin RSQs are never
silently overwritten.

When validated, promote to global:

```python
proj.promote("my_mach_ratio")   # project -> global; now anvil.R.my_mach_ratio for every session
```

---

## 4. Choosing R, S, or Q

- **R (Relation):** a function `f(**inputs) -> {name: value}`. Return `Q(value, "unit")` for
  dimensioned outputs. If an input may arrive as a dimensioned `Q`, `float()`-coerce it first so a
  `Q`-vs-raw-float comparison cannot raise, then wrap the result in `Q`.
- **S (System):** a builder function that returns a solvable `System` composing several R's. Use it
  for multi-step chains (the jet cycles are S's). List the R's it uses in `depends`.
- **Q (Quantity):** a constant, e.g. `export = Q(9.80665, "m/s^2", name="g0")`.

**Inline vs module:** short relations live as an inline `source` string in `seed.py`. Anything past a
few lines or with real physics goes in a module (`src/anvil/<pack>.py`) with a thin seed that imports
it (`from anvil.<pack> import X\nexport = X`). Everything in `propulsion.py` follows this.

**System chaining rule:** relations wire together by **variable name** in the system workspace. Each
output name must be unique across the system, or you get a "produced by both" validation error.
Cross-wire mismatched names with `s.use(rel, map={"T05": "T07"})`. Station-numbered names (T02, T03,
...) are how the cycle systems avoid collisions. (`_apply_map` discovers a mapped relation's outputs
before wrapping, so mapping does not drop outputs.)

---

## 5. Seed entry format

Add a dict to `_SEED_ENTRIES` in `src/anvil/seed.py`. Full field set:

```python
{"name": "my_rsq", "type": "R", "domain": "aero.compressible",
 "desc": "one-line description shown in the catalog and wiki",
 "tags": ["compressible", "isentropic"],
 "latex": r"T_0 = T\left(1 + \frac{\gamma-1}{2} M^2\right)",   # KaTeX, renders in workbench + docs
 "source": "from anvil.propulsion import my_rsq\nexport = my_rsq",   # OR an inline function body
 "depends": ["isentropic_ratios"]},   # optional; required for S builders that compose other RSQs
```

- Pick a sensible dot-`domain`; it decides catalog grouping, `R.<domain>.<name>` access, and which
  workbench pack the RSQ joins (packs match by domain and tags, so a good domain slots it in for
  free, no UI change needed).
- `latex` is optional but expected for physical relations; it typesets in the web calculator and the
  wiki.
- Inline `source` is a single string with `\n` separators, ending in `export = <fn>`.

`seed()` runs on first import. It **skips** if every seed name is already present, so a *new* name
seeds automatically, but *editing* an existing built-in's source or latex will not reach an existing
local DB unless you reseed. Run `from anvil.seed import seed; seed(force=True)` (or delete
`~/.anvil/registry.db`) when you change a shipped RSQ.

---

## 6. Ship-as-built-in pipeline (end to end)

1. **Author** the logic: inline in the seed `source`, or a function in `src/anvil/<pack>.py` plus a
   thin seed entry.
2. **Seed** it: add the dict to `_SEED_ENTRIES` (Section 5).
3. **Array inputs:** if an input is an array (e.g. `x_data` / `y_data`), add the RSQ name to
   `ARRAY_INPUT_RSQS` in `anvil_server/app/config.py`, or name the input using one of
   `ARRAY_INPUT_NAMES`. Otherwise the web calculator renders it as a scalar box.
4. **Test:** add a script-style `tests/test_<pack>.py` that prints `Results: N passed, M failed` and
   `sys.exit`s nonzero on failure. It is auto-discovered by `tests/test_scripts_run.py`, so
   `pytest tests -q` runs it. Assert against textbook values, not just "it ran".
5. **Compatibility gate:**
   - `anvil.check("my_rsq")["ok"]` is `True` (loads + one run).
   - Units propagate; dimensioned outputs are `Q(...)`; no raw-float-vs-`Q` comparisons.
   - `pytest tests -q` is fully green.
6. **Wiki:** add the RSQ to `docs/wiki/09_builtin_rsqs.md` (narrative section + a quick-reference
   table row), and **correct the header counts** on that page (total, R/Q/S split, domain count),
   which are hand-maintained and drift. A whole new domain worth its own page gets
   `docs/wiki/NN_<topic>.md` registered in `docs/build_wiki.py` `PAGES` plus a `SECTION_GROUPS`
   entry (that is how page 23, Propulsion, was added).
7. **Example + guide:** add `examples/ex_<topic>.py` calling `anvil.R.<name>(...)`. It is
   auto-discovered by the gallery, no registration needed. Keep it free of em and en dashes.
8. **Rebuild docs:**
   ```
   python docs/build_examples.py    # regenerates wiki page 22 + docs/_examples_section.html
   python docs/build_wiki.py        # rebuilds ANVIL_WIKI.html / wiki.html
   ```
   For the guide, re-inject the fresh examples fragment into `docs/ANVIL_GUIDE.html` (replace the
   `<section id="examples">...</section>` block with `docs/_examples_section.html`) then run
   `python docs/embed_plots.py`.
9. **Web workbench:** RSQs alone need **no** frontend rebuild; the calculator reads them live from
   `/api/registry`. Rebuild `anvil_web` (`npm run build`) only if you changed UI code.
10. **Commit:** plain message, no co-author or session trailers, author
    `Ramakrishnan C <wittyrk@gmail.com>` (already the local git identity). Push only to
    `anvil-framework-s`.

---

## 7. Compatibility gotchas (these bite every time)

- **Registry shadow poison.** Never give a demo, example, or test RSQ the same name as a built-in. An
  example that registers a builtin name writes a `local`-origin row that shadows the builtin in
  `store.get()` and corrupts the persistent DB for later runs. Name example relations distinctly
  (e.g. `hx_eff_ntu`, not `hx_effectiveness`).
- **Reseed on edit.** Changing a shipped RSQ needs `from anvil.seed import seed; seed(force=True)`; a
  plain reseed skips when all names already exist.
- **Header-count drift.** The wiki count headers are manual. Recompute from `Store().get_all()` and
  update them whenever the built-in set changes.
- **Units.** A dimensioned `Q` compared against a raw float raises. Component functions
  `float()`-coerce inputs and return `Q(...)`.
- **`float(Quantity)`** returns the SI value, handy for internal math before re-wrapping.
- **AI-tell dashes.** Keep em and en dashes out of new source, examples, and docs; keep CSS `--`
  variables and compound-word hyphens.

---

## 8. Authoring RSQs with an LLM

An LLM is good at turning a page of domain equations into RSQ candidates, as long as you give it the
exact output contract and a few exemplars rather than this whole human-oriented document. Ship two
things for that:

- **`docs/RSQ_AUTHORING_PROMPT.md`** is a self-contained, feed-me file. Hand the whole file to any
  capable LLM, append your equations at the marked block, and it returns a Python list of seed dicts
  plus a sample call and expected value for each.
- The prompt encodes the same rules as Sections 2, 4, and 5: the injected namespace (so it does not
  re-import `Q`, `np`, ...), `Q(value, "unit")` for dimensioned outputs, `float()`-coercion of
  inputs, `export = <fn>` at the end, dot-`domain`, no dash characters, and unique non-colliding
  names.

**The human stays in the loop.** The LLM writes candidates; it does not self-certify. For each dict
it returns:

1. Seed it into a scratch project registry (`anvil.project(...)`) or paste it into a temporary list
   and load it, then run `anvil.check("<name>")["ok"]`.
2. Run its sample call and assert the returned value against the textbook number the LLM supplied.
3. Confirm units come back as expected `Q` dimensions, and that the name does not shadow a built-in
   (Section 7).

Only after a candidate passes does it earn a place in `_SEED_ENTRIES`, a `tests/` assertion, and the
wiki. Treat LLM output as a fast first draft through the same gate as hand-written RSQs, never as a
shortcut around it.

---

## Checklist

- [ ] Correct `type` (R/S/Q); function returns a dict; dimensioned outputs are `Q(...)`.
- [ ] Short relation inline in seed, or complex logic in a module with a thin seed entry.
- [ ] Sensible `domain`, `tags`, `version`, `latex`; `depends` listed for composing systems.
- [ ] Array inputs registered in `anvil_server/app/config.py`.
- [ ] Tried via `anvil.project(...)` or `anvil.check()`; correctness test added under `tests/`.
- [ ] Full `pytest tests -q` green; no builtin-name shadow introduced.
- [ ] Wiki page 09 updated (row + counts); new domain page registered in `build_wiki.py` if needed.
- [ ] Gallery example added; `build_examples.py` + `build_wiki.py` (+ guide re-inject) rerun.
- [ ] Committed with the correct author and no trailers; pushed to `anvil-framework-s`.
