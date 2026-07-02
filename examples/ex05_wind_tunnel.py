"""
Example 5: Supersonic Wind Tunnel Sizing
=========================================

Demonstrates:
    - Composing a System from multiple registry RSQs
    - Normal shock + isentropic flow analysis
    - Name mapping for generic Relations
    - Proper unit propagation through all outputs
    - Full design workflow: define -> solve -> sweep -> analyze

Engineering context:
    Size a blowdown supersonic wind tunnel for Mach 2.5 testing.
    Compute required settling chamber conditions, test section
    properties, and diffuser recovery after a normal shock.

Canvas-ready: every relation comes from the registry, so this script
imports directly into the anvil-web canvas (Import .py).
"""

import numpy as np

import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 5: Supersonic Wind Tunnel Design")
print("=" * 60)

# --- Build full tunnel system (registry relations only) ---

tunnel = System("wind_tunnel")
tunnel.add("M_test", 2.5, desc="Test section Mach number")
tunnel.add("T_test", 300, "K", desc="Test section static temperature")
tunnel.add("P_test", 50000, "Pa", desc="Test section static pressure")
tunnel.add("gamma", 1.4)
tunnel.add("R_gas", 287.058, "J/kg/K", desc="Air gas constant")
tunnel.add("A_test", 0.04, "m^2", desc="Test section area (20x20 cm)")
tunnel.add("L_char", 0.2, "m", desc="Model characteristic length")

# Isentropic ratios at test Mach
tunnel.use("isentropic_ratios", map={"M": "M_test"})

# Speed of sound and velocity in test section
tunnel.use("speed_of_sound", map={"T": "T_test"})
tunnel.use("velocity_from_mach", map={"M": "M_test"})

# Density from the ideal-gas law
tunnel.use("ideal_gas_density", map={"P": "P_test", "T": "T_test"})

# Dynamic pressure in the test section
tunnel.use("dynamic_pressure")

# Stagnation (settling chamber) conditions
tunnel.use("stagnation_conditions", map={"T": "T_test", "P": "P_test"})

# Normal shock at test Mach (diffuser entry)
tunnel.use("normal_shock", map={"M1": "M_test"})

# Prandtl-Meyer angle at test Mach
tunnel.use("prandtl_meyer", map={"M": "M_test"})

# Viscosity + Reynolds number on the model
tunnel.use("sutherland_viscosity", map={"T": "T_test"})
tunnel.use("reynolds_number")

result = tunnel.solve_forward()
result.summary(
    keys=[
        "M_test",
        "T_test",
        "P_test",
        "A_test",
        "T0",
        "P0",
        "V",
        "rho",
        "q_inf",
        "M2",
        "P2_P1",
        "P02_P01",
        "Re",
    ]
)

# --- Unit conversions using the unit engine ---
print("\n  Key results (converted via unit engine):")
print(f"  T0 = {result['T0']} {result['T0'].unit}  ({result['T0'].to('R')})")
print(f"  P0 = {result['P0'].to('kPa')}  ({result['P0'].to('atm')})")
print(f"  V_test = {result['V']} {result['V'].unit}")
print(f"  q_inf  = {result['q_inf'].to('kPa')}")
print(f"  Stagnation pressure recovery through shock = {result['P02_P01']:.4f}")
print(f"  nu(M_test) = {result['nu_deg']:.2f} degrees")
print(f"  Re (20 cm model) = {result['Re']:.3e}")

# --- Sweep test Mach ---
print("\n  Sweep: tunnel conditions vs test Mach...")
sweep = tunnel.sweep("M_test", np.linspace(1.5, 4.0, 6))
sweep.summary(outputs=["T0", "P0", "V", "q_inf", "P02_P01"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
