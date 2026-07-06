"""
Example: OpenFOAM CFD Adapter (real only -- requires OpenFOAM on PATH)
=======================================================================
Demonstrates openfoam_incompressible on a real, prepared OpenFOAM case.
There is no mock mode: if simpleFoam or the case directory is missing
the example exits with instructions.

Usage:
    python ex_openfoam_adapter.py <case_dir>

The case directory must be a complete OpenFOAM case (0/, constant/,
system/) with a forceCoeffs function object in system/controlDict.
Tutorials ship with OpenFOAM under $FOAM_TUTORIALS (e.g.
incompressible/simpleFoam/airFoil2D).

Get OpenFOAM: https://openfoam.org/download/ or https://www.openfoam.com/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.adapters import openfoam_cfd
from anvil.adapters.openfoam_cfd import (
    openfoam_incompressible, openfoam_compressible, register
)

if not openfoam_cfd.is_available():
    print("OpenFOAM (simpleFoam) not found on PATH -- skipping example.")
    print("Install: https://openfoam.org/download/")
    print("(on Windows, run inside WSL with OpenFOAM sourced)")
    raise SystemExit(0)

if len(sys.argv) < 2:
    print("Usage: python ex_openfoam_adapter.py <case_dir>")
    print("Point it at a prepared case, e.g. a copy of")
    print("  $FOAM_TUTORIALS/incompressible/simpleFoam/airFoil2D")
    print("with a forceCoeffs function object in system/controlDict.")
    raise SystemExit(0)

case_dir = sys.argv[1]
if not os.path.isdir(case_dir):
    raise SystemExit(f"Case directory not found: {case_dir}")

# ── Incompressible: low-speed airfoil ────────────────────────────────────────
print("=== simpleFoam: incompressible airfoil (AoA=5 deg, U=50 m/s) ===")
r = openfoam_incompressible(
    case_path=case_dir,
    U_inf=50.0,
    alpha_deg=5.0,
    rho=1.225, nu=1.5e-5,
    L_ref=1.0, A_ref=1.0,
)
print(f"  CL     = {r['CL']:.4f}")
print(f"  CD     = {r['CD']:.5f}")
print(f"  F_lift = {r['F_lift']}")
print(f"  F_drag = {r['F_drag']}")
print(f"  Re     = {float(r['Re']):.2e}")

# ── Polar sweep: CL/CD vs angle of attack ────────────────────────────────────
print("\n=== Polar: CL/CD vs AoA (U=30 m/s) ===")
sys_ = anvil.system("foam_polar")
sys_.add("case_path", case_dir)
sys_.add("U_inf",     30.0)
sys_.add("alpha_deg", 0.0)   # placeholder; swept below
sys_.use(openfoam_incompressible)

sweep = sys_.sweep("alpha_deg", [-4.0, 0.0, 4.0, 8.0, 12.0])
print(f"  {'AoA':>6}  {'CL':>7}  {'CD':>8}  {'L/D':>7}")
for i in range(len(sweep.table)):
    row = sweep.table.iloc[i]
    ld  = row["CL"] / row["CD"] if row["CD"] != 0 else float("inf")
    print(f"  {row['alpha_deg']:6.1f}  {row['CL']:7.4f}  {row['CD']:8.5f}  {ld:7.1f}")

# ── Compressible (rhoSimpleFoam) -- needs a compressible case ────────────────
# r2 = openfoam_compressible(case_path="<compressible_case>", U_inf=272.0,
#                            alpha_deg=3.0, p_inf=101325.0, T_inf=288.15)
# print(f"  CL = {r2['CL']:.4f}   Mach = {float(r2['Mach']):.3f}")

# ── Register ─────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
