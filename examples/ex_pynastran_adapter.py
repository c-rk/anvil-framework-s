"""
Example: pyNastran / NASTRAN FEM Adapter (real only)
=====================================================
Demonstrates nastran_linear_static and nastran_normal_modes against a real
NASTRAN-compatible solver. There is no mock mode: missing pyNastran or a
missing solver binary exits with install instructions.

Requirements:
    pip install pyNastran
    A NASTRAN-compatible solver on PATH -- MYSTRAN is free/open-source:
    https://github.com/dr-bill-c/MYSTRAN

Usage:
    python ex_pynastran_adapter.py <static_model.bdf> [modes_model.bdf]

    static_model.bdf : SOL 101 linear static deck
    modes_model.bdf  : SOL 103 normal modes deck (optional)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.adapters import pynastran_fem
from anvil.adapters.pynastran_fem import (
    nastran_linear_static, nastran_normal_modes, register
)

if not pynastran_fem.is_available():
    print("pyNastran and/or a NASTRAN solver binary not found -- skipping example.")
    print("  pip install pyNastran")
    print("  MYSTRAN (free solver): https://github.com/dr-bill-c/MYSTRAN")
    raise SystemExit(0)

if len(sys.argv) < 2:
    print("Usage: python ex_pynastran_adapter.py <static.bdf> [modes.bdf]")
    print("Provide a SOL 101 deck (and optionally a SOL 103 deck).")
    print("MYSTRAN ships test decks; pyNastran also bundles models under")
    print("  pyNastran/../models/ in its source tree.")
    raise SystemExit(0)

static_bdf = sys.argv[1]
modes_bdf  = sys.argv[2] if len(sys.argv) > 2 else None
if not os.path.exists(static_bdf):
    raise SystemExit(f"BDF file not found: {static_bdf}")

# ── Linear static (SOL 101) ──────────────────────────────────────────────────
print(f"=== NASTRAN SOL 101: linear static ({os.path.basename(static_bdf)}) ===")
r = nastran_linear_static(bdf_path=static_bdf, load_case_id=1)
print(f"  Max displacement = {r['max_displacement']}")
print(f"  Max stress       = {r['max_stress']}")

# ── Normal modes (SOL 103) ───────────────────────────────────────────────────
if modes_bdf and os.path.exists(modes_bdf):
    print(f"\n=== NASTRAN SOL 103: normal modes ({os.path.basename(modes_bdf)}) ===")
    r2 = nastran_normal_modes(bdf_path=modes_bdf, n_modes=6)
    print(f"  n_modes = {r2['n_modes']}")
    for i, f in enumerate(r2["frequencies"], 1):
        fq = float(f.si) if hasattr(f, "si") else float(f)
        print(f"    Mode {i}: {fq:.2f} Hz")
else:
    print("\n(no SOL 103 deck given -- skipping normal-modes demo)")

# ── Anvil System integration ─────────────────────────────────────────────────
# The adapter plugs into a System like any native relation, so you can sweep
# any input the deck exposes (e.g. load case id across subcases):
print("\n=== System integration ===")
sys_ = anvil.system("nastran_static")
sys_.add("bdf_path", static_bdf)
sys_.add("load_case_id", 1)
sys_.use(nastran_linear_static)
res = sys_.solve()
print(f"  Solved via System: max_displacement = {res['max_displacement']}")

# ── Register ─────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
