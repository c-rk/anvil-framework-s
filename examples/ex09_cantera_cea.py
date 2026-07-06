"""
Example 9: Cantera Combustion + Nozzle Design
===============================================

A complete rocket engine analysis using Cantera for combustion
thermochemistry and Anvil's built-in nozzle system for performance.

REAL ONLY -- NO MOCK MODE: requires Cantera installed; the example
exits with install instructions otherwise.

PREREQUISITES:
    conda install -c cantera cantera
    -- OR --
    pip install cantera

WHAT THIS EXAMPLE DOES:
    1. Compute combustion products at equilibrium (like NASA CEA)
    2. Feed Tc, gamma, R_gas into the nozzle system
    3. Sweep O/F ratio to find optimal Isp
    4. Sweep chamber pressure for thrust trades
    5. Compare H2/O2 vs CH4/O2 propellant combinations
    6. Sensitivity analysis on the full engine
    7. Export results for reports
"""

import sys, os
import numpy as np

import anvil
from anvil import Q, System, Adapter

# =====================================================
# Require Cantera (real only -- no mock)
# =====================================================
from anvil.adapters import cantera_thermo

if not cantera_thermo.is_available():
    print("  Cantera not installed -- skipping example.")
    print("  Install: conda install -c cantera cantera")
    print("  Or:      pip install cantera")
    raise SystemExit(0)

import cantera as ct
print(f"  Cantera {ct.__version__} found.")

print("=" * 60)
print("  Example 9: Cantera Combustion + Nozzle Design")
print("=" * 60)

from anvil.adapters.cantera_thermo import cea_rocket


# =====================================================
# 1. Direct combustion call
# =====================================================
print("\n[1] H2/O2 combustion at O/F=5, Pc=20 MPa:")
r = cea_rocket(fuel="H2", oxidizer="O2", OF=5.0, Pc=20e6)
print(f"  Tc     = {r['Tc']}")
print(f"  gamma  = {r['gamma_c']:.4f}")
print(f"  R_gas  = {r['R_gas_c']}")
print(f"  c*     = {r['cstar']}")


# =====================================================
# 2. Build full engine system
# =====================================================
print("\n[2] Full H2/O2 engine system:")

engine = System("h2o2_engine")
engine.add("OF",        5.0,          desc="Oxidizer/fuel ratio")
engine.add("Pc",        20e6,  "Pa",  desc="Chamber pressure")
engine.add("A_throat",  0.01,  "m^2", desc="Throat area")
engine.add("A_exit",    0.15,  "m^2", desc="Exit area")
engine.add("P_amb",     0,     "Pa",  desc="Vacuum")

# Combustion -- fix propellant choice, vary OF and Pc
def h2o2_combustion(OF, Pc):
    return cea_rocket(fuel="H2", oxidizer="O2", OF=OF, Pc=Pc)
engine.use(h2o2_combustion)

# Nozzle (from registry)
engine.use("nozzle_area_ratio")
engine.use("area_mach_supersonic", map={"gamma": "gamma_c"})

# Isentropic + exit conditions using combustion products
def exit_analysis(Tc, Pc, gamma_c, R_gas_c, M_exit):
    T0_T = 1 + ((gamma_c - 1) / 2) * M_exit**2
    P0_P = T0_T ** (gamma_c / (gamma_c - 1))
    T_exit = Tc / T0_T
    P_exit = Pc / P0_P
    a_exit = (gamma_c * R_gas_c * T_exit)**0.5
    V_exit = M_exit * a_exit
    return {"T_exit": Q(T_exit, "K"), "P_exit": Q(P_exit, "Pa"),
            "V_exit": Q(V_exit, "m/s")}

def thrust_isp(Pc, A_throat, gamma_c, R_gas_c, Tc, V_exit, P_exit, P_amb, A_exit):
    t = (2 / (gamma_c + 1))**((gamma_c + 1) / (2 * (gamma_c - 1)))
    mdot = Pc * A_throat * (gamma_c / (R_gas_c * Tc))**0.5 * t
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    Isp = F / (mdot * 9.80665)
    return {"mdot": Q(mdot, "kg/s"), "thrust": Q(F, "N"), "Isp": Q(Isp, "s")}

engine.use(exit_analysis)
engine.use(thrust_isp)

result = engine.solve_forward()
result.summary(keys=["OF", "Pc",
                       "Tc", "gamma_c", "R_gas_c", "cstar",
                       "M_exit", "V_exit", "thrust", "Isp"])

print(f"\n  Performance:")
print(f"    Thrust (vac): {result['thrust'].to('kN')}")
print(f"    Isp (vac):    {result['Isp']}")
print(f"    c*:           {result['cstar']}")


# =====================================================
# 3. O/F ratio sweep
# =====================================================
print("\n[3] Sweep: Isp vs O/F ratio (H2/O2)...")
sweep_of = engine.sweep("OF", np.linspace(3.0, 8.0, 6))
sweep_of.summary(outputs=["Tc", "gamma_c", "cstar", "Isp", "thrust"])


# =====================================================
# 4. Chamber pressure sweep
# =====================================================
print("\n[4] Sweep: Performance vs chamber pressure...")
engine.set(OF=5.0)  # reset to near-optimal
sweep_pc = engine.sweep("Pc", np.linspace(5e6, 30e6, 6))
sweep_pc.summary(outputs=["Tc", "cstar", "thrust", "Isp", "mdot"])


# =====================================================
# 5. Propellant comparison: H2/O2 vs CH4/O2
# =====================================================
print("\n[5] Propellant comparison:")
print(f"  {'Propellant':20s} {'Tc(K)':>8s} {'gamma':>8s} {'Isp(s)':>8s} {'c*(m/s)':>8s}")
print(f"  {'-'*56}")

for fuel_name, ox_name, of_ratio in [
    ("H2",  "O2", 5.0),
    ("CH4", "O2", 3.5),
]:
    # Rebuild engine with different propellant
    eng2 = System(f"{fuel_name}_{ox_name}_engine")
    eng2.add("OF", of_ratio); eng2.add("Pc", 20e6, "Pa")
    eng2.add("A_throat", 0.01, "m^2"); eng2.add("A_exit", 0.15, "m^2")
    eng2.add("P_amb", 0, "Pa")
    def make_comb(f, o):
        def comb(OF, Pc): return cea_rocket(fuel=f, oxidizer=o, OF=OF, Pc=Pc)
        return comb
    eng2.use(make_comb(fuel_name, ox_name))
    eng2.use("nozzle_area_ratio")
    eng2.use("area_mach_supersonic", map={"gamma": "gamma_c"})
    eng2.use(exit_analysis); eng2.use(thrust_isp)
    r = eng2.solve_forward()
    print(f"  {fuel_name + '/' + ox_name:20s} "
          f"{r['Tc']} {r['gamma_c']} "
          f"{r['Isp']} {r['cstar']}")


# =====================================================
# 6. Sensitivity analysis
# =====================================================
print("\n[6] Sensitivity: what drives Isp?")
engine.set(OF=5.0, Pc=20e6)
sens = engine.sensitivity(outputs=["Isp", "thrust"])
sens.summary(outputs=["Isp"])

print(f"\n  Top drivers of Isp:")
for inp, val in sens.top("Isp", n=5):
    print(f"    {inp}: {val:+.4f}")


# =====================================================
# 7. Export for report
# =====================================================
print("\n[7] Exporting data...")
result = engine.solve_forward()
result.to_csv("engine_h2o2.csv")
print("  Saved: engine_h2o2.csv")

sweep_of.to_csv("of_sweep_h2o2.csv", outputs=["Tc", "Isp", "thrust", "cstar"])
print("  Saved: of_sweep_h2o2.csv")

json_str = result.to_json("engine_h2o2.json")
print("  Saved: engine_h2o2.json")

# Show CSV content
print("\n  CSV preview:")
with open("engine_h2o2.csv") as f:
    for line in f.readlines()[:8]:
        print(f"    {line.rstrip()}")

# Cleanup
os.remove("engine_h2o2.csv")
os.remove("of_sweep_h2o2.csv")
os.remove("engine_h2o2.json")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
