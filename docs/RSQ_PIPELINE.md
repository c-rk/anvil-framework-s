# RSQ Integration Pipeline

How to add a new **RSQ** (Relation / System / Quantity) to Anvil's registry — from authoring →
project-local testing → promotion to the global registry. An RSQ is a unit of reusable engineering
knowledge stored as Python source in a SQLite database and reconstructed into a live callable on
demand.

Reference internals: `src/anvil/registry/{store,loader,namespace,__init__}.py`, `src/anvil/project.py`,
`src/anvil/seed.py` (the 87 built-ins), and `src/anvil/inspect.py` (`anvil.check`).

---

## 1. What gets stored

Each RSQ is one row in the `rsq` table (`src/anvil/registry/store.py`):

| column | meaning |
|---|---|
| `name` | unique identifier (with `origin`); routinely contains `_` |
| `type` | `R` (Relation), `S` (System), or `Q` (Quantity) |
| `domain` | dot-hierarchical, e.g. `aero.compressible` → reachable at `R.aero.compressible.<name>` |
| `version` | semver string |
| `source` | the RSQ's Python code; must define an `export` variable |
| `metadata` | JSON — auto-extracted input signature for Relations |
| `tests` | JSON — persisted test metadata (not auto-asserted today) |
| `hash` | SHA256 of source |
| `origin` | `local` / `builtin` / `public` / `url`; `local` wins on name clash |

Tags and dependencies live in companion tables (`tags`, `dependencies`).

**Lifecycle:** function → `source_from_function()` extracts code (`loader.py`) → `store.put()` writes
the row → `_rebuild_namespaces()` reloads it → on access, `load_rsq()` runs `exec(source, ns)` in a
controlled namespace (`Q`, `Adapter`, `Relation`, `System`, `numpy`, `math`, `solvers`, `units`) and
pulls out `export`, wrapping callables in a `Relation` with outputs pre-parsed from the source.

> **Security note:** `loader.py` does `exec()` of stored source. Global-registry RSQs are *code* and
> must come from trusted authors. The public **Tier B** deployment must run the loader inside the
> sandbox (restricted builtins, no fs/network, resource caps) — see the project plan.

---

## 2. Author the RSQ

A Relation is just a function taking keyword inputs and returning a dict of outputs. Inputs that carry
units propagate automatically (verified: `m*a → N`):

```python
import anvil
from anvil import Q

@anvil.relation(domain="aero", tags=["compressible"], register=False)
def my_mach_ratio(M, gamma=1.4):
    """Stagnation-to-static temperature ratio."""
    return {"T0_T": 1 + 0.5 * (gamma - 1) * M**2}
```

Outputs need not be literal in the `return` — dims are inferred from the arithmetic on the
unit-carrying inputs.

---

## 3. Develop in a project registry (don't disturb global)

Use an **isolated project store** so experimental RSQs live in your project directory while the global
registry stays accessible (read-through). (`src/anvil/project.py`.)

```python
with anvil.project("my_study", path="./work") as proj:
    anvil.push(my_mach_ratio, domain="aero")   # → project store, NOT global
    proj.R.my_mach_ratio(M=2.0)                 # call your project RSQ
    anvil.R.isentropic_ratios(M=2.0, gamma=1.4) # global RSQs still reachable
```

Inside the `with` block, `anvil.push()` routes to the project (see `anvil/__init__.py:push` →
`get_active_project()`). Outside it, `push()` goes global.

---

## 4. Register + inspect

`anvil.push(obj, name=?, domain=?, version=?, tags=?, tests=?, depends=?, overwrite=?)`:

- Infers `type` from the object (function/Relation → `R`, `System` → `S`, `Quantity` → `Q`).
- Re-registering an existing **non-builtin** name **warns and overwrites**; pass `overwrite=True` to
  signal intent and suppress the warning (now wired through), or use `anvil.update(...)` to change
  only specific fields while keeping the rest.
- `builtin`-origin RSQs are never silently overwritten.

Health-check it:

```python
report = anvil.check("my_mach_ratio")   # loads, runs with defaults/dummy, lists issues
assert report["ok"]
```

`check()` is a smoke test (load + single run), not an expected-value assertion. Put correctness
assertions in `tests/` (script-style, see `tests/test_fixes_v05.py`).

Manage the registry:

```python
anvil.registry.list(domain="aero")     # filter by type/domain/origin/tag
anvil.registry.search("mach")          # fuzzy (LIKE wildcards now escaped — '_' is literal)
anvil.registry.info("my_mach_ratio")   # full details
anvil.registry.export("my_mach_ratio") # print stored source
anvil.registry.remove("my_mach_ratio") # uninstall
```

---

## 5. Promote to global

When the project RSQ is validated, promote it:

```python
proj.promote("my_mach_ratio")   # moves project → global registry
```

It is now `anvil.R.my_mach_ratio` for every session (and `anvil.R.aero.my_mach_ratio` via domain).

---

## 6. Make it a built-in (optional)

To ship an RSQ with the framework, add it to the seed module (`src/anvil/seed.py`) so it registers
on first import with `origin="builtin"`, then document it in `docs/wiki/09_builtin_rsqs.md` and bump
the count in `README.md`.

---

## Checklist

- [ ] Function returns a dict; inputs carry/declare units where physical.
- [ ] Developed and tried in an `anvil.project(...)` store first.
- [ ] `anvil.check()` reports `ok`; correctness test added to `tests/`.
- [ ] Sensible `domain`, `tags`, `version`; `depends` listed if it composes other RSQs.
- [ ] `promote()`d to global (or seeded as builtin + wiki updated) when ready.
