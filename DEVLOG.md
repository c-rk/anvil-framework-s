# Anvil DEVLOG — Claude working notes

Tracking file for Claude sessions. Newest entry first. Format: date, what changed, why, open items.
Not user docs — internal state tracker. Keep terse.

## State snapshot (2026-07-17)

- Repo: nested root `the-anvil-framework-main/the-anvil-framework-main`, branch `main`, HEAD `5baaa82`.
- Remote: `origin` = github.com/c-rk/anvil-framework-s (pushed 2026-07-06). Old repo `the-anvil-framework` — NEVER push there.
- v1.3.0. 46 py files in src. 15 adapters. 101 RSQs, 101 units. FastAPI server (`anvil_server`) + React canvas UI (`anvil_web`, legacy `anvil_web_v1`). Docs wiki 101/101 pages, Cloudflare Pages serves `docs/`.
- Policy: adapters real-only, no mocks. New adapters (coolprop, meshing, rocket_cea, uq) comply. Legacy 9 (xfoil, su2, openfoam, fenics, pynastran, openmdo, cantera, nasa_cea, surrogate) still have mock fallbacks. README line ~70 still advertises "analytical mock fallbacks" — contradicts policy.
- Tests: 11 files, script-style (print "Results: N passed"), pytest-compatible via guarded sys.exit. No CI.
- Cruft: `_probe_tmp.py` at root, `.pytest_cache`, `anvil_framework.egg-info` tracked?, untracked `examples/tank_blowdown.py`.

## Roadmap v2 (rewritten 2026-07-19 per user direction)

User goals: (a) download repo → one command → solver server running, callable from any code or anvil_web;
(b) anvil_web visual/UX upgrade; (c) more tools + features; (d) core stays robust, lean, trivial to start.

Core principles (enforce on every change):
- Core deps stay numpy+scipy only. Everything else = optional extra.
- No mock physics anywhere. Missing tool → clear install-hint error.
- One-command start must keep working — smoke test it in CI.

Phase 0 — hygiene: delete `_probe_tmp.py`, decide tank_blowdown.py, gitignore egg-info/pycache/pytest_cache.
Phase 1 — one-command start:
  - `start_anvil.py` at root: checks Python ≥3.10, creates .venv, pip installs core+server, launches server, opens browser. Idempotent — rerun = just launch.
  - `anvil` CLI entry point: `anvil serve`, `anvil doctor` (which adapters usable on this machine), `anvil version`.
  - Commit prebuilt anvil_web bundle → no npm/node needed by users.
  - HTTP client: `anvil.client.AnvilClient` — call running server from any Python code (later any language via REST).
  - README top rewritten: 3 lines from download to running workbench.
Phase 2 — no-mock migration: strip mocks from 9 legacy adapters (xfoil, su2, openfoam, fenics, pynastran, openmdo, cantera, nasa_cea, surrogate), fix test_m4_adapters + examples, fix README mock claim.
Phase 3 — tests + CI: real pytest asserts, GitHub Actions 3.10–3.12, ruff, coverage, plus smoke test of start_anvil.py + server boot.
Phase 4 — anvil_web facelift: coherent design system (typography/spacing/color, dark+light), canvas UX polish (pan/zoom feel, node styling, edge routing), results panel with proper charts, onboarding (sample canvases + first-run tour), retire anvil_web_v1.
Phase 5 — new tools/features (each as extra, core untouched): report export (HTML/PDF from solved system), optimization/DOE UI in workbench, Jupyter display integration, more RSQ domains as demanded, REST API docs for non-Python callers.
Phase 6 — docs + credibility: 10-min quickstart, autogen API reference, example gallery with outputs, CONTRIBUTING, CITATION.cff, CHANGELOG.md, semver, optional JOSS prep.

## Log

### 2026-07-20 — Docs: pure monochrome (user feedback)
Dropped the bronze accent entirely — `--accent` is now brightest-ink (dark #f5f0e7 / light #0a0906), so hover/current-page/labels still read via contrast alone. De-hued code syntax too (was blue/tan/orange) → bone/grey brightness tiers. Fixed a latent light-theme bug found in passing: `.code`/`.step .body` code panels (always-dark bg) were using theme-flipping `var(--ink-2)` text → dark-on-dark in light mode; now fixed bone-grey. IMPORTANT distinction: the hero `.deck pre` install block has NO dark bg (sits on page) so it KEEPS theme-flipping `var(--ink-2)` — do not hardcode it. Verified dark + light full-page captures; both legible. Preview artifact updated.

### 2026-07-20 — Docs website EDITORIAL REDESIGN (user feedback)
User called v1 "okay but generic." New direction applied to both index.html + quickstart.html: more serif + monospace, larger type, no icons/emoji at all, minimalist, multi-column, elegant glass. Key fixes:
- LOGO: the ⚒ emoji was WRONG. Real logo is a b/w anvil silhouette at `anvil_web/public/favicon.svg` (two SVG paths, black anvil on white). Inlined those paths with `fill="currentColor"` so it's monochrome + theme-aware. Removed ALL emoji/icons (⚒ ✓ ⚖ terminal traffic-light dots) — text and the anvil mark only.
- TYPE: serif display (Iowan Old Style / Palatino / Georgia stack) for headlines + body; monospace (ui-monospace stack) for eyebrows, nav, labels, meta, code. Larger sizes (hero up to ~88px, body 19px).
- PALETTE: dropped the teal SaaS gradient. Monochrome warm neutrals — near-black #0b0c0e ground, bone ink #ece7dd, warm greys; single forged-bronze accent #c69a6d used ONLY for interaction (link hover, mono labels). Light theme = warm paper #f2efe9.
- LAYOUT: broadsheet/editorial. Landing = huge serif headline + 3-col deck (lede | one-command | spec table), newspaper columns for the 3 primitives split by vertical rules, multi-column CSS `columns` feature list, full-width "standing rule" creed. Quickstart = two-column steps (mono 01–07 index rail + serif content), 2×2 grid for next-steps. Thin hairline rules throughout, sharp 2px radii.
- Verified via full-page headless-Chrome capture (landing 3299px, quickstart 4432px). Republished preview artifact. (Note: full-page screenshots show a faint ghost of the sticky header — CDP capture artifact, renders clean in a real browser.)

### 2026-07-20 — Docs website (new, per user request)
User asked for a website + quickstart + docs site for Cloudflare Pages, building on existing `docs/`. Found: Cloudflare serves `docs/`, and `index.html` was LITERALLY the wiki (identical to ANVIL_WIKI.html) — no real landing page existed. User chose (via AskUserQuestion): new landing+quickstart keeping wiki/guide, and match the app's dark-glass aesthetic.
- Preserved wiki at `docs/wiki.html` (copy of ANVIL_WIKI.html), then replaced `docs/index.html` with a NEW dark-glass **landing page**: hero ("From equations to engineering tools"), terminal-style `python start_anvil.py` card, three-primitives grid, real code example, feature grid, "real physics only / no mock" callout, footer. Dark+light themes (prefers-color-scheme + toggle w/ localStorage), teal accent, self-contained (no external requests), responsive.
- New `docs/quickstart.html` — 10-min numbered tutorial (install → first relation → units → build+solve system → sweep/sensitivity → workbench+AnvilClient → next steps). Same design system. All code snippets use verified real APIs.
- All cross-linked (index/quickstart/guide/wiki/GitHub c-rk/anvil-framework-s). Non-destructive: old wiki still at ANVIL_WIKI.html + now wiki.html; guide untouched.
- Verified via headless-Chrome full-page screenshots (landing 3302px, quickstart 3917px) — both render cleanly in dark. Published preview artifact for the user.
- Cloudflare setup unchanged (build output dir = docs, no build command). index.html is the new root; anyone who bookmarked the old wiki-at-root now lands on the welcome page which links prominently to the wiki.

### 2026-07-20 — Phase 3 (CI + tests) + UI screenshots
- **Glass UI verified visually.** Booted server, drove headless Chrome via CDP, captured calculator (dark), canvas (dark), calculator (light). All coherent — teal accent, translucent surfaces, tabular readouts. Published a private artifact gallery for the user. Glass build confirmed (backdrop-filter in dist CSS).
- **Found + fixed a real shipped bug via the test suite:** `examples/ex02_heat_exchanger.py` failed to solve standalone (`hx_effectiveness needs NTU and Cr`). ROOT CAUSE: this machine's local SQLite store had stale `origin='local'` RSQs shadowing the correct builtins — `hx_effectiveness` (local wanted NTU/Cr; builtin uses temps), `ideal_gas_density` (local had no latex), `orifice_mass_flow` (bad-indent source). `store.get()` returns local origin over builtin, so examples/tests picked the broken copies. Removed the 3 stale local dupes via `registry.remove(name, origin='local')`. ex02 now converges (33 iters, energy balance 0.0000 W, effectiveness 0.8056). A fresh clone was always fine — this was local drift, NOT shipped code. But it exposed two REAL robustness gaps (see below).
- **Test suite now fully green:** 11 script suites total 316 passed / 0 failed / 4 skipped. Fixed `test_latex` (32/0) and `test_canvas_scripts` (30/0) via the store cleanup; made `test_v04` plot tests SKIP gracefully when matplotlib absent (added `skip=` to its check decorator) → 36 passed/4 skipped instead of hard-failing.
- **Phase 3 delivered:**
  - `tests/test_scripts_run.py` — pytest bridge: parametrizes over the 11 script-style suites, runs each as a subprocess, asserts exit 0 + "0 failed". Now plain `pytest` exercises the WHOLE suite (before: it only saw test_sandbox's 4 native tests).
  - `tests/test_smoke_onboarding.py` — real pytest guarding one-command start: clean+fast `import anvil`, CLI import, server boot fixture, `/healthz`, and AnvilClient round-trip == direct call. Uses `importorskip` for the server extra. NOTE: server health path is `/healthz` (not `/health`).
  - `.github/workflows/ci.yml` — matrix ubuntu+windows × py3.10/3.11/3.12: install `.[dev,server]`, ruff correctness gate, `pytest tests -q`; plus a separate ubuntu `smoke-one-command` job that runs `start_anvil.py --no-browser` and curls `/healthz` (tests the true fresh-clone path). CANNOT be verified without a push (forbidden) — validated all components locally instead.
  - pyproject: added `ruff>=0.6` + server deps to `dev` extra; `[tool.ruff]` config with a CORRECTNESS-ONLY lint gate (E9,F63,F7,F82,F821 — real bugs, not style). Default ruff finds 401 style nits (unused imports etc.) — deferred as a separate cleanup pass, NOT blocking CI.
  - Full local `pytest tests -q`: **19 passed in ~50s** (11 bridge + 4 sandbox native + 4 smoke).

- **ROBUSTNESS GAPS surfaced (follow-ups, not yet fixed):**
  1. Builtin RSQ updates (new latex, source fixes) do NOT reach existing user stores — `seed()` skips when all names present unless the source/latex differs, but a local-origin shadow masks the builtin entirely. Consider: `seed()` should detect+heal builtin shadows, or `anvil doctor` should warn on local RSQs shadowing builtins.
  2. Examples/tests can pollute the GLOBAL store with local RSQs (orifice/ideal_gas/hx_effectiveness got there somehow). Examples should register to a scratch/project registry, never global. Worth auditing which example does this.

### 2026-07-20 — Wave 1 recovery (main thread)
All 3 subagents died mid-task on a shared session limit (not code errors). Assessed disk state and finished inline:
- **Phase 0/1 (Agent A) — DONE + VERIFIED.** `_probe_tmp.py` deleted; `.gitignore` covers venv/egg-info/pycache/pytest_cache. `start_anvil.py`/`.bat`/`.sh`, `src/anvil/cli.py` (serve/doctor/version), `src/anvil/client.py`, `server` extra in pyproject, README quick-start — all present. Verified: `anvil version`/`anvil doctor` clean output; server boots on a chosen port; **AnvilClient round-trip == direct call** for isentropic_ratios (exact match); health() reports 108 RSQs. `import anvil` fast+clean.
- **Phase 2 (Agent B) — effectively DONE.** KEY FINDING: the 15-day-old memory was STALE — the 9 "legacy" adapters were already real-only. Every "mock" string in adapters/ is now a docstring saying "no mock fallback"; all ImportError/RuntimeError handlers raise with install hints, none return fabricated data. `tests/test_m4_adapters.py` → 42 passed/0 failed. Cleaned remaining misleading mock text in `docs/ANVIL_GUIDE.html` (aero/FEM/MDO examples said "source: mock" + a note claiming "analytical mock fallbacks" — corrected to real-only; also fixed stale `_fallback` params in the NASTRAN example that no longer exist in the real API). README + other docs already mock-free.
- **Phase 4 (Agent C) — styles+build DONE; un-ignore fixed by me.** `tokens.css` + restyled App/main/styles; `dist/` rebuilt 2026-07-19 with glass CSS (backdrop-filter present). dist WAS still git-ignored (rule lived in `anvil_web/.gitignore` + root `anvil_web/dist/`) — FIXED: un-ignored anvil_web/dist in both, added `!` negations to beat the global `*.png` rule; 63 dist files now stage. anvil_web_v1/dist stays ignored (v1 retiring).
- **Bug fixed:** stale broken RSQ `orifice_mass_flow` (bad indent, "line 4") was stuck in the local SQLite store, warning on every import — purged via `registry.remove`. Import now warning-free. Root cause: earlier run registered it before `tank_blowdown.py` switched to `register=False`; DB is local/gitignored so ships clean.

Remaining: Phase 3 (pytest conversion + GitHub Actions CI — files can be written but CI unverifiable without a push, which is forbidden). Phase 4 visual screenshot of glass UI still pending. Full ANVIL_GUIDE signature-accuracy pass (many adapter examples show outdated signatures beyond the mock claims) — separate docs task. Nothing committed.

### 2026-07-19
- Roadmap v2 approved by user. New requirement for Phase 4: glassmorphism sleek minimal look, must stay fast.
- Wave 1 launched — 3 parallel subagents, disjoint file ownership:
  - A (Phase 0+1): root cruft, start_anvil.py/.bat/.sh, anvil CLI (serve/doctor/version), `server` extra, AnvilClient stdlib HTTP client, README rewrite. Owns README + pyproject + root.
  - B (Phase 2): strip mocks from 9 legacy adapters (+check poliastro/pykep), real-only errors at call time, fix test_m4_adapters (skip pattern + error-path tests), examples fail gracefully, docs mock-claim sweep. Owns adapters/tests/examples/docs.
  - C (Phase 4): glass design tokens (tokens.css), dark+light, restrained backdrop-filter (perf), restyle shell/panels/canvas/nodes/inputs, npm build, un-ignore anvil_web/dist. Owns anvil_web.
- After wave 1: sequential Phase 3 agent (pytest conversion + GitHub Actions CI + start_anvil smoke test), then integration verify (fresh-clone sim → start_anvil → UI + client round-trip). Commits held until user asks.

### 2026-07-17
- Created this DEVLOG. Surveyed repo state, wrote 6-phase roadmap (above). No code changes yet.
