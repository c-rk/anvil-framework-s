"""Anvil chemistry RSQ tests -- stoichiometry, gas, solution, thermo, kinetics,
equilibrium, electro, acid-base.

Values checked against textbook / first-principles results. These RSQs were authored via
docs/RSQ_AUTHORING_PROMPT.md and validated before seeding. Note the SI convention: dimensioned
concentrations are mol/m^3 (so 0.25 M is 250 mol/m^3).
"""
import sys, os, math, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anvil
from anvil.seed import seed
seed(force=True)
anvil.registry._rebuild_namespaces()
R = anvil.R

passed = failed = skipped = 0
errors = []

RGAS = 8.314462618
FARADAY = 96485.332


def check(name, skip=False):
    def dec(fn):
        global passed, failed, skipped
        if skip:
            print(f"  SKIP  {name}"); skipped += 1; return
        try:
            fn(); print(f"  PASS  {name}"); passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}"); traceback.print_exc()
            failed += 1; errors.append((name, e))
    return dec


def close(a, b, tol=1e-3):
    if abs(float(a) - float(b)) > tol:
        raise AssertionError(f"{a} != {b} (tol={tol})")


def rel(a, b, rtol=1e-3):
    if abs(float(a) - float(b)) > abs(float(b)) * rtol:
        raise AssertionError(f"{a} != {b} (rtol={rtol})")


print("\n=== Stoichiometry ===")


@check("moles_from_mass: 18 g water is 1 mol")
def _():
    close(R.moles_from_mass(m=0.018, M=0.018)["n"], 1.0)


@check("percent_yield: 8.2 of 10 is 82 percent")
def _():
    close(R.percent_yield(actual=8.2, theoretical=10)["percent_yield"], 82.0)


@check("molarity: 0.5 mol in 2 L is 250 mol/m^3 (0.25 M)")
def _():
    o = R.molarity(n=0.5, V=0.002)
    close(o["c"], 250.0)          # SI mol/m^3
    close(o["c_molar"], 0.25)     # convenience mol/L


print("\n=== Gas ===")


@check("moles_ideal_gas: 22.414 L at STP is 1 mol")
def _():
    rel(R.moles_ideal_gas(P=101325, V=0.0224140, T=273.15)["n"], 1.0, rtol=2e-3)


@check("combined_gas_law: double the pressure halves the volume")
def _():
    close(R.combined_gas_law(P1=1e5, V1=1e-3, T1=300, P2=2e5, T2=300)["V2"], 5e-4)


print("\n=== Solution ===")


@check("dilution: 2 M into 0.5 M needs 4x the volume")
def _():
    close(R.dilution(M1=2, V1=0.010, M2=0.5)["V2"], 0.04)


@check("beer_lambert_absorbance: A = eps l c")
def _():
    close(R.beer_lambert_absorbance(eps=100, l=0.01, c=1.0)["A"], 1.0)


@check("freezing_point_depression: 0.5 m NaCl (i=2) in water")
def _():
    close(R.freezing_point_depression(i=2, Kf=1.86, m=0.5)["dTf"], 1.86)


@check("osmotic_pressure: 1000 mol/m^3 at 298 K")
def _():
    rel(R.osmotic_pressure(i=1, M=1000, T=298.15)["Pi"], 1000 * RGAS * 298.15)


@check("raoult_vapor_pressure: 0.9 mole fraction of solvent")
def _():
    close(R.raoult_vapor_pressure(x_solvent=0.9, P_pure=3170)["P"], 2853.0)


print("\n=== Thermo and equilibrium ===")


@check("gibbs_free_energy: dG = dH - T dS")
def _():
    close(R.gibbs_free_energy(dH=-1e5, T=298.15, dS=-100)["dG"], -1e5 + 298.15 * 100)


@check("gibbs_from_equilibrium_constant: K=100 is spontaneous")
def _():
    rel(R.gibbs_from_equilibrium_constant(K=100, T=298.15)["dG"], -RGAS * 298.15 * math.log(100))


@check("equilibrium_constant_from_gibbs: inverse of the above")
def _():
    dG = -RGAS * 298.15 * math.log(100)
    close(R.equilibrium_constant_from_gibbs(dG=dG, T=298.15)["K"], 100.0, tol=1e-2)


print("\n=== Kinetics ===")


@check("arrhenius_rate_constant: k = A exp(-Ea/RT)")
def _():
    rel(R.arrhenius_rate_constant(A=1e13, Ea=1e5, T=300)["k"], 1e13 * math.exp(-1e5 / (RGAS * 300)))


@check("first_order_half_life: t = ln2 / k")
def _():
    rel(R.first_order_half_life(k=0.00693)["t_half"], math.log(2) / 0.00693)


print("\n=== Electrochemistry and acid-base ===")


@check("nernst_cell_potential: Daniell-like cell, Q=1e-3")
def _():
    expect = 1.10 - (RGAS * 298.15 / (2 * FARADAY)) * math.log(1e-3)
    rel(R.nernst_cell_potential(E0=1.10, n=2, T=298.15, Q_rxn=1e-3)["E"], expect)


@check("ph_from_concentration: neutral water 1e-7 gives pH 7")
def _():
    close(R.ph_from_concentration(H_conc=1e-7)["pH"], 7.0)


@check("henderson_hasselbalch: equal buffer gives pH = pKa")
def _():
    close(R.henderson_hasselbalch(pKa=4.76, conc_base=0.1, conc_acid=0.1)["pH"], 4.76)


@check("henderson_hasselbalch: 10:1 base:acid raises pH by 1")
def _():
    close(R.henderson_hasselbalch(pKa=4.76, conc_base=1.0, conc_acid=0.1)["pH"], 5.76)


# ============================================================
print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
if errors:
    print("\nFailed:")
    for n, e in errors:
        print(f"  {n}: {e}")
print(f"{'=' * 50}")
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
