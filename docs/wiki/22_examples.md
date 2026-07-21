# Examples

Every runnable example from the `examples/` folder, with its code and output. Examples that wrap an external tool show what to install; the CFD cases note that they run a full solve locally.


## Example 1: Rocket Nozzle Design Trade Study

`examples/ex01_rocket_nozzle.py`

```python
import sys, os
import numpy as np

import anvil
from anvil import Q

print("=" * 60)
print("  Example 1: Rocket Nozzle Design")
print("=" * 60)

# --- Step 1: Inspect what's available ---
print("\n[1] Inspecting the rocket_nozzle system...")
anvil.check("rocket_nozzle")

# --- Step 2: Load and customize ---
print("\n[2] Loading nozzle with custom propellant properties...")
nozzle = anvil.S.rocket_nozzle.copy()

# LOX/LH2 propellant properties
nozzle.set(
    P0=20e6,          # 20 MPa chamber pressure (high-performance engine)
    T0=3500,           # 3500 K combustion temperature
    gamma=1.20,        # typical for LOX/LH2
    R_gas=520,         # J/kg/K for LOX/LH2 products
    A_throat=0.005,    # 50 cm^2 throat
    A_exit=0.08,       # 800 cm^2 exit
    P_amb=0,           # vacuum (space engine)
)

result = nozzle.solve_forward()
result.summary()

# --- Step 3: Unit conversions ---
print("\n[3] Key results in different units:")
print(f"  Thrust:  {result['thrust'].to('kN')}")
print(f"           {result['thrust'].to('lbf')}")
print(f"  Isp:     {result['Isp']}")
print(f"  Exit V:  {result['V_exit'].to('km/s')}")
print(f"  mdot:    {result['mdot']}")

# --- Step 4: Trade study -- chamber pressure ---
print("\n[4] Sweep: Thrust and Isp vs chamber pressure...")
sweep = nozzle.sweep("P0", np.linspace(5e6, 30e6, 6))
sweep.summary(outputs=["thrust", "Isp", "mdot", "M_exit"])

# --- Step 5: Trade study -- area ratio ---
print("\n[5] Sweep: Performance vs exit area...")
nozzle.set(P0=20e6)  # reset
sweep2 = nozzle.sweep("A_exit", np.linspace(0.02, 0.15, 6))
sweep2.summary(outputs=["thrust", "Isp", "M_exit", "P_exit"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 1: Rocket Nozzle Design
============================================================

[1] Inspecting the rocket_nozzle system...

============================================================
  anvil.check('rocket_nozzle')  [PASS]
============================================================
  Type:        System
  Domain:      propulsion
  Description: Quasi-1D isentropic rocket nozzle with thrust and Isp
  Version:     0.1.0
  Inputs:      P0, T0, gamma, R_gas, A_throat, A_exit, P_amb
  Outputs:     Isp, M_exit, P0_P, P_exit, T0_T, T_exit, V_exit, a_exit, area_ratio, mdot
  Depends on:  nozzle_area_ratio, area_mach_supersonic, isentropic_ratios, exit_conditions, exit_velocity, choked_mass_flow, rocket_thrust, specific_impulse

  --- Dependency Tree ---
  rocket_nozzle (System)
    Inputs (7):
      P0: 6900000.0 Pa  -- Chamber pressure
      T0: 3500.0 K  -- Chamber temperature
      gamma: 1.25   -- Ratio of specific heats
      R_gas: 320.0 J/kg/K  -- Specific gas constant
      A_throat: 0.01 m^2  -- Throat area
      A_exit: 0.08 m^2  -- Exit area
      P_amb: 101325.0 Pa  -- Ambient pressure
    Relations (8):
      [1] nozzle_area_ratio
          in:  A_exit, A_throat
          out: area_ratio
      [2] area_mach_supersonic
          in:  area_ratio, gamma
          out: M_exit
... (125 more lines)
```


## Example 2: Heat Exchanger Design (Coupled System)

`examples/ex02_heat_exchanger.py`

```python
import numpy as np

from anvil import System
from anvil.monitor import diagnose

print("=" * 60)
print("  Example 2: Counter-Flow Heat Exchanger")
print("=" * 60)

# --- Build the system (registry relations only) ---

hx = System("counter_flow_hx")

# Operating conditions
hx.add("T_hot_in",  600,    "K",      desc="Hot inlet (exhaust gas)")
hx.add("T_cold_in", 290,    "K",      desc="Cold inlet (water)")
hx.add("UA",        2000,   "W",      desc="Overall heat transfer coefficient * area")
hx.add("Cp_hot",    1050,   "J/kg/K", desc="Hot fluid specific heat (exhaust)")
hx.add("Cp_cold",   4186,   "J/kg/K", desc="Cold fluid specific heat (water)")
hx.add("mdot_hot",  0.8,    "kg/s",   desc="Hot mass flow rate")
hx.add("mdot_cold", 0.5,    "kg/s",   desc="Cold mass flow rate")

# Initial guesses for the coupled variables
hx.add("T_cold_out", 350,   "K",      desc="Cold outlet (initial guess)")
hx.add("Q_dot",      50000, "W",      desc="Heat transfer rate (initial guess)")

# Q_dot needs T_cold_out; T_cold_out needs Q_dot -> a cycle Anvil
# detects and solves iteratively (gauss_seidel auto-selected).
hx.use("hx_heat_rate")
hx.use("hx_cold_out")
hx.use("hx_hot_out")
hx.use("hx_effectiveness")

# --- Pre-solve diagnostics ---
print("\n[1] Pre-solve diagnostics:")
for msg in diagnose(hx):
    print(f"  {msg}")

# --- Solve ---
print("\n[2] Solving (Gauss-Seidel with monitoring)...")
result = hx.solve_gauss_seidel(
    max_iter=200,
    rtol=1e-10,
    relaxation=0.5,
    monitor=True,
    verbose=True,
)
result.summary()

# --- Verify energy balance ---
print("\n[3] Energy balance check:")
Q_hot  = result["mdot_hot"].si * result["Cp_hot"].si * (result["T_hot_in"].si - result["T_hot_out"].si)
Q_cold = result["mdot_cold"].si * result["Cp_cold"].si * (result["T_cold_out"].si - result["T_cold_in"].si)
print(f"  Q_hot  = {Q_hot:.2f} W")
print(f"  Q_cold = {Q_cold:.2f} W")
print(f"  Error  = {abs(Q_hot - Q_cold):.4f} W")
print(f"  Effectiveness = {result['effectiveness']}")

# --- Convergence info ---
hist = hx.history()
print(f"\n[4] Convergence: {len(hist)} iterations")
print(f"  Initial residual: {hist[0]['residual']:.2e}")
print(f"  Final residual:   {hist[-1]['residual']:.2e}")

# --- Sweep: vary UA ---
print("\n[5] Sweep: effectiveness vs UA...")
sweep = hx.sweep("UA", np.linspace(500, 5000, 6),
                 method="gauss_seidel", relaxation=0.5, max_iter=200)
sweep.summary(outputs=["effectiveness", "T_hot_out", "T_cold_out", "Q_dot"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 2: Counter-Flow Heat Exchanger
============================================================

[1] Pre-solve diagnostics:
  INFO: Coupled variables detected: Q_dot, T_cold_out, T_hot_out. Will use iterative solver.

[2] Solving (Gauss-Seidel with monitoring)...
  WARNING: variable(s) declared via .add() are also produced by a relation, so the declared value will be overwritten after solve: ['T_cold_out', 'Q_dot']
    (This is intentional for iterative initial guesses; for forward systems it may indicate a naming mismatch.)
  iter    0  |  residual = 2.0000e+00  |  t = 0.000s
  iter    1  |  residual = 2.3426e-01  |  t = 0.000s
  iter    2  |  residual = 7.3938e-02  |  t = 0.000s
  iter    3  |  residual = 2.9794e-02  |  t = 0.000s
  iter    4  |  residual = 1.6573e-02  |  t = 0.000s
  iter    5  |  residual = 8.7496e-03  |  t = 0.000s
  iter    6  |  residual = 4.4986e-03  |  t = 0.000s
  iter    7  |  residual = 2.2818e-03  |  t = 0.000s
  iter    8  |  residual = 1.1494e-03  |  t = 0.000s
  iter    9  |  residual = 5.7687e-04  |  t = 0.000s
  iter   10  |  residual = 2.8900e-04  |  t = 0.000s
  iter   11  |  residual = 1.4465e-04  |  t = 0.000s
  iter   12  |  residual = 7.2362e-05  |  t = 0.000s
  iter   13  |  residual = 3.6190e-05  |  t = 0.000s
  iter   14  |  residual = 1.8098e-05  |  t = 0.000s
  iter   15  |  residual = 9.0495e-06  |  t = 0.000s
  iter   16  |  residual = 4.5249e-06  |  t = 0.000s
  iter   17  |  residual = 2.2625e-06  |  t = 0.000s
  iter   18  |  residual = 1.1313e-06  |  t = 0.000s
  iter   19  |  residual = 5.6564e-07  |  t = 0.000s
  iter   20  |  residual = 2.8282e-07  |  t = 0.000s
  iter   21  |  residual = 1.4141e-07  |  t = 0.000s
  iter   22  |  residual = 7.0705e-08  |  t = 0.000s
  iter   23  |  residual = 3.5352e-08  |  t = 0.000s
... (57 more lines)
```


## Example 3: LEO to GEO Orbital Transfer Mission

`examples/ex03_orbital_transfer.py`

```python
import os

import numpy as np

import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 3: LEO to GEO Orbital Transfer")
print("=" * 60)

# --- Constants ---
mu_earth = 3.986004418e14  # m^3/s^2
R_earth = 6371e3  # m

# --- Step 1: Define the orbits ---
h_LEO = 400e3  # 400 km altitude
h_GEO = 35786e3  # geostationary altitude

r_LEO = R_earth + h_LEO
r_GEO = R_earth + h_GEO

print(f"\n[1] Orbit definitions:")
print(f"  LEO: {Q(h_LEO,'m').to('km')} altitude, r = {Q(r_LEO,'m').to('km')}")
print(f"  GEO: {Q(h_GEO,'m').to('km')} altitude, r = {Q(r_GEO,'m').to('km')}")

# --- Step 2: Orbital velocities ---
print(f"\n[2] Orbital velocities:")
leo_v = anvil.R.vis_viva(mu=mu_earth, r=r_LEO, a=r_LEO)
geo_v = anvil.R.vis_viva(mu=mu_earth, r=r_GEO, a=r_GEO)
print(f"  V_LEO = {leo_v['V_orbital'].to('km/s')}")
print(f"  V_GEO = {geo_v['V_orbital'].to('km/s')}")

# --- Step 3: Hohmann transfer ---
print(f"\n[3] Hohmann transfer:")
transfer = anvil.R.hohmann_transfer(mu=mu_earth, r1=r_LEO, r2=r_GEO)
print(f"  dV1 (LEO departure):  {transfer['dv1'].to('km/s')}")
print(f"  dV2 (GEO insertion):  {transfer['dv2'].to('km/s')}")
print(f"  Total delta-V:        {transfer['dv_total'].to('km/s')}")
print(f"  Transfer time:        {transfer['tof'].to('hr')}")

# --- Step 4: Orbital periods ---
print(f"\n[4] Orbital periods:")
T_LEO = anvil.R.orbital_period(mu=mu_earth, a=r_LEO)
T_GEO = anvil.R.orbital_period(mu=mu_earth, a=r_GEO)
print(f"  LEO period: {T_LEO['T_orbital'].to('min')}")
print(f"  GEO period: {T_GEO['T_orbital'].to('hr')} hrs (should be ~24)")

# --- Step 5: Propellant budget using Tsiolkovsky ---
print(f"\n[5] Propellant budget (bipropellant engine, Isp = 320 s):")

# Build a mission system
mission = System("leo_to_geo")
mission.add("mu", mu_earth)
mission.add("r_LEO", r_LEO, "m")
mission.add("r_GEO", r_GEO, "m")
mission.add("Isp_engine", 320, "s", desc="Engine specific impulse")
mission.add("m_dry", 2500, "kg", desc="Dry mass (payload + structure)")

# Delta-V
mission.use("hohmann_transfer", map={"r1": "r_LEO", "r2": "r_GEO"})

# Propellant mass from Tsiolkovsky (inverted) -- registry relation
mission.use("propellant_mass", map={"dv": "dv_total", "Isp": "Isp_engine"})
result = mission.solve_forward()

print(f"  Mass ratio:     {result['mass_ratio']}")
print(f"  Propellant:     {result['m_propellant']}")
print(f"  Wet mass:       {result['m_wet']}")
print(f"  Payload frac:   {2000 / result['m_wet']}")

# --- Step 6: Sweep over engine Isp ---
print(f"\n[6] Sweep: propellant mass vs engine Isp...")
sweep = mission.sweep("Isp_engine", np.linspace(250, 450, 5))
sweep.summary(outputs=["m_propellant", "mass_ratio", "m_wet"])
sweep_dry = mission.sweep("m_dry", np.linspace(1500, 4500, 5))
sweep_dry.summary(outputs=["m_propellant", "mass_ratio", "m_wet"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 3: LEO to GEO Orbital Transfer
============================================================

[1] Orbit definitions:
  LEO: 400.00 km altitude, r = 6771.00 km
  GEO: 35786.00 km altitude, r = 42157.00 km

[2] Orbital velocities:
  V_LEO = 7.6726 km/s
  V_GEO = 3.0749 km/s

[3] Hohmann transfer:
  dV1 (LEO departure):  2.3994 km/s
  dV2 (GEO insertion):  1.4572 km/s
  Total delta-V:        3.8566 km/s
  Transfer time:        5.2890 hr

[4] Orbital periods:
  LEO period: 92.4143 min
  GEO period: 23.9284 hr hrs (should be ~24)

[5] Propellant budget (bipropellant engine, Isp = 320 s):
  Mass ratio:     3.4176 (mass_ratio)
  Propellant:     6044.03 kg (m_propellant)
  Wet mass:       8544.03 kg (m_wet)
  Payload frac:   0.234082 [M-1]

[6] Sweep: propellant mass vs engine Isp...

----------------------------------------------------------------------
  leo_to_geo -- sweep over Isp_engine
----------------------------------------------------------------------
      Isp_engine  m_propellant    mass_ratio         m_wet
... (25 more lines)
```


## Example 4: Structural Beam Analysis

`examples/ex04_beam_analysis.py`

```python
import numpy as np
import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 4: Structural Beam Analysis")
print("=" * 60)

# Material: Aluminum 6061-T6
E        = Q(68.9e9,  "Pa")      # Young's modulus
sigma_y  = Q(276e6,   "Pa")      # yield strength
rho      = Q(2700,    "kg/m^3")  # density

# Cross section: 50 mm x 100 mm rectangular
b = Q(0.050, "m")
h = Q(0.100, "m")
A = b * h                        # m^2
I = b * h**3 / 12                # m^4

print(f"\n[1] Beam properties:")
print(f"  E        = {E.to('GPa')}")
print(f"  sigma_y  = {sigma_y.to('MPa')}")
print(f"  section  = {b.to('mm')} x {h.to('mm')}")
print(f"  Area     = {A}")
print(f"  I        = {I}")


# ── Part A: Cantilever under tip load ────────────────────────────────────────
print(f"\n[A] Cantilever beam, 5 kN tip load:")

F = Q(5000, "N")
L = Q(2.0,  "m")

r = anvil.R.beam_deflection_cantilever(
    F_tip=F.si, L_beam=L.si, E=E.si, I_moment=I.si
)
max_stress = r["max_moment"] * (h / 2) / I

print(f"  deflection  = {r['deflection'].to('mm')}")
print(f"  max moment  = {r['max_moment']}")
print(f"  max stress  = {max_stress.to('MPa')}")
print(f"  safety vs yield = {(sigma_y / max_stress):.2f}x")

# Sweep beam length
print(f"\n  Sweep: deflection vs length (0.5 to 4 m):")
cant = System("cantilever")
cant.add("F_tip",    F.si,  "N")
cant.add("L_beam",   L.si,  "m")
cant.add("E",        E.si,  "Pa")
cant.add("I_moment", I.si,  "m^4")
cant.use("beam_deflection_cantilever")
cant.sweep("L_beam", np.linspace(0.5, 4.0, 8)).summary(
    outputs=["deflection", "max_moment"])


# ── Part B: Simply-supported under uniform load ───────────────────────────────
print(f"\n[B] Simply-supported beam, 2 kN/m uniform load:")

w = Q(2000, "N/m")
L_ss = Q(3.0, "m")

r_ss = anvil.R.beam_deflection_simply_supported(
    w_load=w.si, L_beam=L_ss.si, E=E.si, I_moment=I.si
)
print(f"  max deflection = {r_ss['deflection'].to('mm')}")
print(f"  max moment     = {r_ss['max_moment']}")


# ── Part C: Euler column buckling ─────────────────────────────────────────────
print(f"\n[C] Column buckling (fixed-free, K=2):")

L_col = Q(1.5, "m")
L_eff = Q(2.0 * L_col.si, "m")   # effective length for fixed-free

r_buck = anvil.R.buckling_euler(E=E.si, I_moment=I.si, L_eff=L_eff.si)
print(f"  critical load = {r_buck['P_critical'].to('kN')}")
print(f"  safety at 50 kN = {r_buck['P_critical'] / Q(50e3,'N'):.2f}x")


# ── Part D: Thin-wall pressure vessel ─────────────────────────────────────────
print(f"\n[D] Thin-wall pressure vessel:")

r_pv = anvil.R.thin_wall_hoop_stress(
    P_internal=Q(5e6,"Pa").si, r_inner=Q(0.3,"m").si, t_wall=Q(0.005,"m").si
)
print(f"  hoop stress  = {r_pv['sigma_hoop'].to('MPa')}")
print(f"  axial stress = {r_pv['sigma_axial'].to('MPa')}")
print(f"  safety (yield / hoop) = {sigma_y / r_pv['sigma_hoop']:.2f}x")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 4: Structural Beam Analysis
============================================================

[1] Beam properties:
  E        = 68.9000 GPa
  sigma_y  = 276.00 MPa
  section  = 50.0000 mm x 100.00 mm
  Area     = 5.0000e-03 m^2
  I        = 4.1667e-06 [L4]

[A] Cantilever beam, 5 kN tip load:
  deflection  = 46.4441 mm
  max moment  = 10000.00 N*m
  max stress  = 120.00 MPa
  safety vs yield = 2.30x

  Sweep: deflection vs length (0.5 to 4 m):

----------------------------------------------------------------------
  cantilever -- sweep over L_beam
----------------------------------------------------------------------
          L_beam    deflection    max_moment
             [m]           [m]         [N*m]
  ------------------------------------------
             0.5     0.0007257          2500
               1      0.005806          5000
             1.5       0.01959          7500
               2       0.04644         1e+04
             2.5       0.09071      1.25e+04
               3        0.1567       1.5e+04
             3.5        0.2489      1.75e+04
               4        0.3716         2e+04
----------------------------------------------------------------------
... (17 more lines)
```


## Example 5: Supersonic Wind Tunnel Sizing

`examples/ex05_wind_tunnel.py`

```python
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
```

**Output:**

```
============================================================
  Example 5: Supersonic Wind Tunnel Design
============================================================
  WARNING: variable(s) declared via .add() are not used by any relation: ['A_test']
    (Possible typo or unused parameter.)

--------------------------------------------------------
  wind_tunnel -- results
--------------------------------------------------------
  M_test                    2.5000
  T_test                    300.00 K
  P_test                    50000.00 Pa
  A_test                    0.040000 m^2
                            ---
  T0                        675.00 K
  P0                        854296.88 Pa
  V                         868.06 m/s
  rho                       0.580603 kg/m^3
  q_inf                     218750.00 Pa
  M2                        0.512989
  P2_P1                     7.1250
  P02_P01                   0.499015
  Re                        5.4616e+06
--------------------------------------------------------

  Key results (converted via unit engine):
  T0 = 675.00 K (T0) K  (1215.00 R (T0))
  P0 = 854.30 kPa (P0)  (8.4313 atm (P0))
  V_test = 868.06 m/s (V) m/s
  q_inf  = 218.75 kPa (q_inf)
  Stagnation pressure recovery through shock = 0.4990
  nu(M_test) = 39.12 degrees
  Re (20 cm model) = 5.462e+06

... (19 more lines)
```


## Example 6: Multi-Stage Rocket (Composition + Tsiolkovsky)

`examples/ex06_two_stage_rocket.py`

```python
import sys, os
import numpy as np

import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 6: Two-Stage Launch Vehicle")
print("=" * 60)

# ==========================================
# Stage 1: Kerosene/LOX booster
# ==========================================
print(f"\n--- Stage 1: Kerosene/LOX booster ---")

stage1_nozzle = anvil.S.rocket_nozzle.copy()
stage1_nozzle.set(
    P0=15e6,         # 15 MPa chamber pressure
    T0=3400,          # K
    gamma=1.22,       # RP-1/LOX products
    R_gas=340,        # J/kg/K
    A_throat=0.05,    # m^2 (large booster)
    A_exit=0.40,      # m^2
    P_amb=101325,     # sea-level launch
)

r1 = stage1_nozzle.solve_forward()
Isp_1 = r1["Isp"].si

print(f"  Isp (sea level): {Isp_1:.1f} s")
print(f"  Thrust:          {r1['thrust'].to('kN')}")
print(f"  Exit Mach:       {r1['M_exit']}")

# ==========================================
# Stage 2: LOX/LH2 upper stage
# ==========================================
print(f"\n--- Stage 2: LOX/LH2 upper stage ---")

stage2_nozzle = anvil.S.rocket_nozzle.copy()
stage2_nozzle.set(
    P0=8e6,           # 8 MPa
    T0=3200,           # K
    gamma=1.20,        # LOX/LH2 products
    R_gas=520,         # J/kg/K
    A_throat=0.01,     # m^2 (smaller upper stage)
    A_exit=0.12,       # m^2 (high expansion for vacuum)
    P_amb=0,           # vacuum
)

r2 = stage2_nozzle.solve_forward()
Isp_2 = r2["Isp"].si

print(f"  Isp (vacuum):    {Isp_2:.1f} s")
print(f"  Thrust:          {r2['thrust'].to('kN')}")
print(f"  Exit Mach:       {r2['M_exit']}")

# ==========================================
# Vehicle sizing with Tsiolkovsky
# ==========================================
print(f"\n--- Vehicle sizing ---")

# Mass breakdown
m_payload   = 5000    # kg
m_struct_2  = 2000    # kg (2nd stage dry mass)
m_struct_1  = 15000   # kg (1st stage dry mass)

# Required delta-V budget
dV_gravity_drag = 1500   # m/s (gravity + drag losses)
dV_orbit        = 9400   # m/s (LEO insertion velocity)
dV_total        = dV_orbit + dV_gravity_drag

# Split: 60% stage 1, 40% stage 2 (typical)
dV_1 = 0.60 * dV_total
dV_2 = 0.40 * dV_total

print(f"  Payload:     {m_payload} kg")
print(f"  dV target:   {dV_total} m/s")
print(f"  Stage 1 dV:  {dV_1:.0f} m/s (Isp = {Isp_1:.0f} s)")
print(f"  Stage 2 dV:  {dV_2:.0f} m/s (Isp = {Isp_2:.0f} s)")

# Stage 2 propellant (Tsiolkovsky)
g0 = 9.80665
MR_2 = np.exp(dV_2 / (Isp_2 * g0))
m_dry_2 = m_payload + m_struct_2
m_prop_2 = m_dry_2 * (MR_2 - 1)
m_wet_2 = m_dry_2 + m_prop_2

print(f"\n  Stage 2:")
print(f"    Mass ratio:  {MR_2:.3f}")
print(f"    Propellant:  {m_prop_2:.0f} kg")
print(f"    Wet mass:    {m_wet_2:.0f} kg")

# Stage 1 propellant
MR_1 = np.exp(dV_1 / (Isp_1 * g0))
m_dry_1 = m_wet_2 + m_struct_1  # stage 1 carries all of stage 2
m_prop_1 = m_dry_1 * (MR_1 - 1)
m_wet_1 = m_dry_1 + m_prop_1
m_liftoff = m_wet_1

print(f"\n  Stage 1:")
print(f"    Mass ratio:  {MR_1:.3f}")
print(f"    Propellant:  {m_prop_1:.0f} kg")
print(f"    Wet mass:    {m_wet_1:.0f} kg")

print(f"\n  Vehicle totals:")
print(f"    Liftoff mass:    {m_liftoff:.0f} kg ({m_liftoff/1000:.1f} tonnes)")
print(f"    Payload fraction: {m_payload/m_liftoff:.4f} ({m_payload/m_liftoff*100:.2f}%)")
print(f"    Propellant mass: {(m_prop_1 + m_prop_2):.0f} kg")

# ==========================================
# Using Anvil Systems for the same calculation
# ==========================================
print(f"\n--- Same calculation as an Anvil System ---")

vehicle = System("two_stage_vehicle")
vehicle.add("Isp_1",      Isp_1,     "s",  desc="Stage 1 Isp")
vehicle.add("Isp_2",      Isp_2,     "s",  desc="Stage 2 Isp")
vehicle.add("dV_1",       dV_1,      "m/s")
vehicle.add("dV_2",       dV_2,      "m/s")
vehicle.add("m_payload",  m_payload, "kg")
vehicle.add("m_struct_1", m_struct_1,"kg")
vehicle.add("m_struct_2", m_struct_2,"kg")

def stage_2_sizing(dV_2, Isp_2, m_payload, m_struct_2):
    MR = np.exp(dV_2 / (Isp_2 * 9.80665))
    m_dry = m_payload + m_struct_2
    m_prop = m_dry * (MR - 1)
    return {"m_prop_2": Q(m_prop, "kg"), "m_wet_2": Q(m_dry + m_prop, "kg")}

def stage_1_sizing(dV_1, Isp_1, m_wet_2, m_struct_1):
    MR = np.exp(dV_1 / (Isp_1 * 9.80665))
    m_dry = m_wet_2 + m_struct_1
    m_prop = m_dry * (MR - 1)
    m_liftoff = m_dry + m_prop
    return {"m_prop_1": Q(m_prop, "kg"), "m_liftoff": Q(m_liftoff, "kg")}

def payload_fraction(m_payload, m_liftoff):
    return {"payload_fraction": m_payload / m_liftoff}

vehicle.use(stage_2_sizing)
vehicle.use(stage_1_sizing)
vehicle.use(payload_fraction)

result = vehicle.solve_forward()
result.summary(keys=["Isp_1", "Isp_2", "dV_1", "dV_2",
                       "m_prop_2", "m_wet_2", "m_prop_1",
                       "m_liftoff", "payload_fraction"])

# --- Sweep: payload fraction vs dV split ---
print(f"\n--- Sweep: payload fraction vs Stage 1 dV fraction ---")
dV_splits = np.linspace(0.4, 0.8, 5)
results = []
for frac in dV_splits:
    vehicle.set(dV_1=frac * dV_total, dV_2=(1 - frac) * dV_total)
    r = vehicle.solve_forward()
    pf = r["payload_fraction"].si
    results.append(pf)
    print(f"  Stage 1 = {frac:.0%} of dV  -->  payload fraction = {pf:.4f}")

best_idx = np.argmax(results)
print(f"\n  Optimal split: {dV_splits[best_idx]:.0%} / {1-dV_splits[best_idx]:.0%}")
print(f"  Best payload fraction: {results[best_idx]:.4f}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 6: Two-Stage Launch Vehicle
============================================================

--- Stage 1: Kerosene/LOX booster ---
  Isp (sea level): 277.1 s
  Thrust:          1236.81 kN (thrust)
  Exit Mach:       3.1725 (M_exit)

--- Stage 2: LOX/LH2 upper stage ---
  Isp (vacuum):    357.9 s
  Thrust:          141.16 kN (thrust)
  Exit Mach:       3.4052 (M_exit)

--- Vehicle sizing ---
  Payload:     5000 kg
  dV target:   10900 m/s
  Stage 1 dV:  6540 m/s (Isp = 277 s)
  Stage 2 dV:  4360 m/s (Isp = 358 s)

  Stage 2:
    Mass ratio:  3.463
    Propellant:  17244 kg
    Wet mass:    24244 kg

  Stage 1:
    Mass ratio:  11.094
    Propellant:  396118 kg
    Wet mass:    435363 kg

  Vehicle totals:
    Liftoff mass:    435363 kg (435.4 tonnes)
    Payload fraction: 0.0115 (1.15%)
    Propellant mass: 413363 kg
... (31 more lines)
```


## Example 7: Combustion Chamber Analysis (Custom Empirical Adapter)

`examples/ex07_combustion.py`

```python
import sys, os
import numpy as np

import anvil
from anvil import Q, System, Adapter

print("=" * 60)
print("  Example 7: Combustion + Nozzle Analysis")
print("=" * 60)

# =====================================================
# Empirical curve-fit adapter (LOX/RP-1, from NASA CEA data)
# =====================================================

def lox_rp1_curvefit(Pc, OF, fuel_name="RP1", oxidizer_name="LOX"):
    """
    LOX/RP-1 equilibrium properties from curve fits of NASA CEA data.
    Valid roughly for OF 1.5-4.0 and Pc 1-30 MPa.

    For exact equilibrium chemistry use anvil.adapters.cantera_thermo:
        import cantera as ct
        gas = ct.Solution('gri30.yaml')
        gas.set_equivalence_ratio(1/OF, fuel, oxidizer)
        gas.TP = 300, Pc
        gas.equilibrate('HP')
    """
    # Curve fits based on NASA CEA data for LOX/RP-1
    OF_opt = 2.7  # optimal O/F ratio
    Tc_peak = 3670  # K at optimal O/F

    # Temperature vs O/F (parabolic approximation)
    Tc = Tc_peak * (1 - 0.15 * ((OF - OF_opt) / OF_opt)**2)
    # Slight pressure dependence
    Tc = Tc * (1 + 0.02 * np.log(Pc / 1e6))

    # Molecular weight and gamma vary with O/F
    MW = 22.0 + 2.0 * (OF - 2.0)  # g/mol, approximate
    R_gas = 8314.46 / MW  # J/kg/K
    gamma = 1.15 + 0.03 * (OF - 2.0)  # approximate

    # Characteristic velocity
    cstar = (R_gas * Tc / gamma * ((gamma + 1) / 2)**((gamma + 1) / (gamma - 1)))**0.5

    return {
        "Tc": Q(Tc, "K"),
        "gamma_c": gamma,
        "R_gas_c": Q(R_gas, "J/kg/K"),
        "MW": Q(MW, "g/mol"),
        "cstar": Q(cstar, "m/s"),
    }


combustion = Adapter("lox_rp1_equilibrium",
    backend="python",
    call=lox_rp1_curvefit,
    inputs={
        "Pc":   {"unit": "Pa", "desc": "Chamber pressure"},
        "OF":   {"desc": "Oxidizer-to-fuel mass ratio", "default": 2.7},
        "fuel_name": {"desc": "Fuel identifier", "default": "RP1"},
        "oxidizer_name": {"desc": "Oxidizer identifier", "default": "LOX"},
    },
    outputs={
        "Tc":     {"unit": "K",      "desc": "Chamber temperature"},
        "gamma_c": {"desc": "Ratio of specific heats"},
        "R_gas_c": {"unit": "J/kg/K", "desc": "Specific gas constant"},
        "MW":     {"unit": "g/mol",  "desc": "Mean molecular weight"},
        "cstar":  {"unit": "m/s",    "desc": "Characteristic velocity"},
    },
    desc="LOX/RP-1 equilibrium combustion (empirical NASA CEA curve fits)",
    tags=["combustion", "propulsion", "curve-fit"],
)

# --- Direct call ---
print("\n[1] Direct combustion call (O/F = 2.7, Pc = 10 MPa):")
r = combustion(Pc=10e6, OF=2.7)
for k, v in r.items():
    if isinstance(v, Q):
        print(f"  {k:12s} = {v} {v.unit}")
    else:
        print(f"  {k:12s} = {v:.4f}")

# =====================================================
# Build integrated combustion + nozzle system
# =====================================================
print("\n[2] Integrated combustion + nozzle system:")

engine = System("lox_rp1_engine")

# Design inputs
engine.add("Pc",       10e6,    "Pa",  desc="Chamber pressure")
engine.add("OF",       2.7,            desc="O/F ratio")
engine.add("A_throat", 0.02,    "m^2", desc="Throat area")
engine.add("A_exit",   0.30,    "m^2", desc="Exit area")
engine.add("P_amb",    101325,  "Pa",  desc="Ambient pressure (sea level)")

# Combustion (adapter)
engine.use(combustion)

# Nozzle physics (from registry, with name mapping)
engine.use("nozzle_area_ratio")
engine.use("area_mach_supersonic")
engine.use("isentropic_ratios", map={"M": "M_exit", "gamma": "gamma_c"})

def exit_conditions_mapped(Tc, Pc, T0_T, P0_P, gamma_c, R_gas_c):
    T_exit = Tc / T0_T
    P_exit = Pc / P0_P
    a_exit = (gamma_c * R_gas_c * T_exit)**0.5
    return {"T_exit": Q(T_exit, "K"), "P_exit": Q(P_exit, "Pa"),
            "a_exit": Q(a_exit, "m/s")}
engine.use(exit_conditions_mapped)

def exit_velocity(M_exit, a_exit):
    return {"V_exit": Q(M_exit * a_exit, "m/s")}
engine.use(exit_velocity)

def choked_flow(Pc, A_throat, gamma_c, R_gas_c, Tc):
    t = (2 / (gamma_c + 1))**((gamma_c + 1) / (2 * (gamma_c - 1)))
    mdot = Pc * A_throat * (gamma_c / (R_gas_c * Tc))**0.5 * t
    return {"mdot": Q(mdot, "kg/s")}
engine.use(choked_flow)

engine.use("rocket_thrust", map={"P_exit": "P_exit", "V_exit": "V_exit"})
engine.use("specific_impulse")

result = engine.solve_forward()
result.summary(keys=["Pc", "OF", "A_throat", "A_exit",
                       "Tc", "gamma_c", "R_gas_c", "cstar",
                       "M_exit", "V_exit", "mdot", "thrust", "Isp"])

# --- Unit conversions ---
print(f"\n[3] Engine performance:")
print(f"  Thrust (SL):  {result['thrust'].to('kN')}")
print(f"  Isp (SL):     {result['Isp']}")
print(f"  c*:           {result['cstar']}")
print(f"  Mass flow:    {result['mdot']}")

# --- O/F ratio trade study ---
print(f"\n[4] Sweep: Isp vs O/F ratio...")
sweep = engine.sweep("OF", np.linspace(1.5, 4.0, 8))
sweep.summary(outputs=["Tc", "gamma_c", "cstar", "Isp", "thrust"])

# --- Sensitivity analysis ---
print(f"\n[5] Sensitivity analysis (which inputs drive Isp?):")
sens = engine.sensitivity(outputs=["Isp", "thrust"])
sens.summary()

print("\n  Top 3 drivers of Isp:")
for inp, val in sens.top("Isp", n=3):
    print(f"    {inp}: {val:+.4f}")

# --- Export ---
print(f"\n[6] Exporting results...")
result.to_csv("engine_results.csv")
print(f"  Saved: engine_results.csv")
sweep.to_csv("of_sweep.csv", outputs=["Tc", "Isp", "thrust"])
print(f"  Saved: of_sweep.csv")
json_str = result.to_json()
print(f"  JSON preview: {json_str[:100]}...")

# Cleanup
os.remove("engine_results.csv")
os.remove("of_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 7: Combustion + Nozzle Analysis
============================================================

[1] Direct combustion call (O/F = 2.7, Pc = 10 MPa):
  Tc           = 3839.01 K K
  gamma_c      = 1.1710
  R_gas_c      = 355.32 J/kg/K J/kg/K
  MW           = 23.4000 g/mol g/mol
  cstar        = 1816.84 m/s m/s

[2] Integrated combustion + nozzle system:

--------------------------------------------------------
  lox_rp1_engine -- results
--------------------------------------------------------
  Pc                        1.0000e+07 Pa
  OF                        2.7000
  A_throat                  0.020000 m^2
  A_exit                    0.300000 m^2
                            ---
  Tc                        3839.01 K
  gamma_c                   1.1710
  R_gas_c                   355.32 J/kg/K
  cstar                     1816.84 m/s
  M_exit                    4.3838
  V_exit                    3407.92 m/s
  mdot                      110.08 kg/s
  thrust                    348609.96 N
  Isp                       322.93 s
--------------------------------------------------------

[3] Engine performance:
  Thrust (SL):  348.61 kN (thrust)
... (64 more lines)
```


## Example 8: Research Workflow -- Thermal-Structural Coupled Analysis

`examples/ex08_research_workflow.py`: the full Anvil research workflow

```python
import sys, os
import numpy as np

import anvil
from anvil import Q, System
from anvil.db import fluids, materials

print("=" * 60)
print("  Example 8: Combustion Chamber Wall Design")
print("=" * 60)

# =====================================================
# Step 1: Material selection database lookup
# =====================================================
print("\n[1] Material candidates:")
materials.compare("Copper-C101", "Inconel-718", "Steel-304")

# Select copper for thermal conductivity
mat = materials.get("Copper-C101")
print(f"  Selected: Copper-C101")
print(f"    k = {mat['k']} (high conductivity)")
print(f"    sigma_y = {mat['sigma_y'].to('MPa')}")
print(f"    T_max = {mat['T_max']}")

# =====================================================
# Step 2: Coolant properties
# =====================================================
print(f"\n[2] Coolant: RP-1 (modeled as air-like for demo)")
coolant = fluids.get("air", T=400)  # RP-1 approximation
print(f"  rho = {coolant['rho']}")
print(f"  cp  = {coolant['cp']}")
print(f"  mu  = {coolant['mu']}")

# =====================================================
# Step 3: Build thermal-structural wall system
# =====================================================
print(f"\n[3] Building coupled wall analysis system...")

wall = System("chamber_wall")

# Operating conditions
wall.add("T_gas",      3500,     "K",      desc="Hot gas temperature")
wall.add("h_gas",      5000,     "W",      desc="Gas-side heat transfer coeff")
wall.add("T_coolant",  400,      "K",      desc="Coolant bulk temperature")
wall.add("h_coolant",  15000,    "W",      desc="Coolant-side heat transfer coeff")

# Wall geometry
wall.add("t_wall",     0.003,    "m",      desc="Wall thickness")
wall.add("r_inner",    0.15,     "m",      desc="Chamber inner radius")

# Material (from database)
wall.add("k_wall",     mat["k"].si,           desc="Wall thermal conductivity")
wall.add("E",          mat["E"].si,  "Pa",    desc="Young's modulus")
wall.add("alpha_th",   mat["alpha"].si,        desc="Thermal expansion coeff")
wall.add("nu_poisson", mat["nu_poisson"],      desc="Poisson's ratio")
wall.add("sigma_y",    mat["sigma_y"].si, "Pa", desc="Yield strength")

# Thermal analysis: T_hot -> T_cold through wall
def wall_temperatures(T_gas, h_gas, T_coolant, h_coolant, k_wall, t_wall):
    """Steady-state 1D heat transfer through wall with convection on both sides."""
    # Total thermal resistance per unit area
    R_total = 1/h_gas + t_wall/k_wall + 1/h_coolant
    # Heat flux
    q_flux = (T_gas - T_coolant) / R_total
    # Surface temperatures
    T_hot_wall = T_gas - q_flux / h_gas
    T_cold_wall = T_coolant + q_flux / h_coolant
    T_avg_wall = (T_hot_wall + T_cold_wall) / 2
    return {
        "q_flux": Q(q_flux, "W"),
        "T_hot_wall": Q(T_hot_wall, "K"),
        "T_cold_wall": Q(T_cold_wall, "K"),
        "T_avg_wall": Q(T_avg_wall, "K"),
    }

# Thermal stress
def thermal_stress(T_hot_wall, T_cold_wall, E, alpha_th, nu_poisson):
    """Thermal stress from temperature gradient through wall."""
    dT = T_hot_wall - T_cold_wall
    # Biaxial thermal stress in a constrained plate
    sigma_th = E * alpha_th * dT / (2 * (1 - nu_poisson))
    return {"sigma_thermal": Q(sigma_th, "Pa"), "delta_T_wall": Q(dT, "K")}

# Pressure stress (hoop)
def pressure_stress(P_chamber, r_inner, t_wall):
    sigma_h = P_chamber * r_inner / t_wall
    return {"sigma_hoop": Q(sigma_h, "Pa")}

# Safety factor
def safety_factor(sigma_thermal, sigma_hoop, sigma_y):
    sigma_total = sigma_thermal + sigma_hoop
    SF = sigma_y / sigma_total if sigma_total > 0 else 999
    return {"sigma_total": Q(sigma_total, "Pa"), "safety_factor": SF}

wall.add("P_chamber", 10e6, "Pa", desc="Chamber pressure")
wall.use(wall_temperatures)
wall.use(thermal_stress)
wall.use(pressure_stress)
wall.use(safety_factor)

result = wall.solve_forward()
result.summary(keys=["T_gas", "T_coolant", "t_wall", "P_chamber",
                       "q_flux", "T_hot_wall", "T_cold_wall", "delta_T_wall",
                       "sigma_thermal", "sigma_hoop", "sigma_total", "safety_factor"])

# =====================================================
# Step 4: Sweep over wall thickness
# =====================================================
print(f"\n[4] Sweep: safety factor vs wall thickness...")
sweep = wall.sweep("t_wall", np.linspace(0.001, 0.008, 6))
sweep.summary(outputs=["T_hot_wall", "sigma_thermal", "sigma_hoop",
                          "sigma_total", "safety_factor"])

# =====================================================
# Step 5: Sensitivity analysis
# =====================================================
print(f"\n[5] Sensitivity: what drives safety factor?")
sens = wall.sensitivity(outputs=["safety_factor", "T_hot_wall"])
sens.summary()

print(f"\n  Top 3 drivers of safety factor:")
for inp, val in sens.top("safety_factor", n=3):
    print(f"    {inp}: {val:+.4f}")

# =====================================================
# Step 6: Material comparison
# =====================================================
print(f"\n[6] Material comparison for this wall:")
candidates = ["Copper-C101", "Inconel-718", "Steel-304"]
print(f"  {'Material':20s} {'T_hot(K)':>10s} {'sigma(MPa)':>12s} {'SF':>8s}")
print(f"  {'-'*52}")

for mat_name in candidates:
    m = materials.get(mat_name)
    wall.set(
        k_wall=m["k"].si,
        E=m["E"].si,
        alpha_th=m["alpha"].si,
        nu_poisson=m["nu_poisson"],
        sigma_y=m["sigma_y"].si,
    )
    r = wall.solve_forward()
    sf = r["safety_factor"].si
    thot = r["T_hot_wall"].si
    sig = r["sigma_total"].si / 1e6
    ok = "OK" if sf > 1.5 else "FAIL"
    print(f"  {mat_name:20s} {thot:10.0f} {sig:12.0f} {sf:8.2f}  [{ok}]")

# =====================================================
# Step 7: Export
# =====================================================
print(f"\n[7] Exporting sweep data...")
sweep.to_csv("wall_sweep.csv", outputs=["T_hot_wall", "sigma_total", "safety_factor"])
print(f"  Saved: wall_sweep.csv")
os.remove("wall_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 8: Combustion Chamber Wall Design
============================================================

[1] Material candidates:

                         Copper-C101     Inconel-718       Steel-304
                    ------------------------------------------------
  E (GPa)                      117.0           200.0           193.0
  Yield (MPa)                     69            1035             215
  UTS (MPa)                      221            1240             505
  Density                     8940.0          8190.0          8000.0
  k (W/mK)                     391.0            11.4            16.2
  T_max (K)                    473.0           973.0          1089.0

  Selected: Copper-C101
    k = 391.00 W/m/K (high conductivity)
    sigma_y = 69.0000 MPa
    T_max = 473.00 K

[2] Coolant: RP-1 (modeled as air-like for demo)
  rho = 0.882444 kg/m^3
  cp  = 1005.00 J/kg/K
  mu  = 2.2852e-05 Pa*s

[3] Building coupled wall analysis system...

--------------------------------------------------------
  chamber_wall -- results
--------------------------------------------------------
  T_gas                     3500.00 K
  T_coolant                 400.00 K
  t_wall                    3.0000e-03 m
  P_chamber                 1.0000e+07 Pa
... (75 more lines)
```


## Example 9: Cantera Combustion + Nozzle Design

`examples/ex09_cantera_cea.py`: A complete rocket engine analysis using Cantera for combustion

```python
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
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example 10: Chapman-Jouguet Detonation Analysis

`examples/ex10_detonation.py`

```python
import os

import numpy as np


import anvil
from anvil.adapters import nasa_cea_detonation
from anvil.adapters.nasa_cea_detonation import cea_detonation
from anvil import Q, System

print("=" * 60)
print("  Example 10: Chapman-Jouguet Detonation")
print("=" * 60)

if not nasa_cea_detonation.is_available():
    print("  NASA CEA not installed -- skipping example.")
    print("  Install: pip install cea")
    raise SystemExit(0)

# =====================================================
# 1. Direct detonation calls (inputs in SI)
# =====================================================
print("\n[1] CJ detonation for common mixtures (at 1 atm, 300 K):\n")

P_init = Q(1, "atm")  # define pressure with units
T_init = Q(300, "K")

print(
    f"  Initial: P = {P_init} {P_init.unit} ({P_init.to('Pa')}), T = {T_init} {T_init.unit}"
)
print()
print(f"  {'Mixture':25s} {'D_CJ':>10s} {'T_CJ':>10s} {'P2/P1':>8s} {'P_CJ':>10s}")
print(f"  {'-' * 65}")

cases = [
    ("H2/O2", "H2", "O2", 2.0, 1.0, None),
    ("H2/Air", "H2", "O2", 2.0, 1.0, {"N2": 3.76}),
    ("CH4/O2", "CH4", "O2", 1.0, 2.0, None),
    ("C2H4/O2", "C2H4", "O2", 1.0, 3.0, None),
]

for label, fuel, ox, fm, om, extra in cases:
    r = cea_detonation(
        fuel=fuel,
        oxidizer=ox,
        fuel_moles=fm,
        ox_moles=om,
        T1=T_init.si,
        P1=P_init.si,
        extra_species=extra,
    )
    print(
        f"  {label:25s} {r['D_CJ']} {r['T_CJ']} "
        f"{r['P_ratio']:8.1f} {r['P_CJ'].to('atm')}"
    )


# =====================================================
# 2. Anvil System with proper units
# =====================================================
print(f"\n[2] H2/O2 detonation system (all quantities with units):")

det = System("h2o2_detonation")
det.add("fuel_moles", 2.0, desc="Moles of H2")
det.add("ox_moles", 1.0, desc="Moles of O2")
det.add("T1", 300, "K", desc="Initial temperature")
det.add("P1", 1, "atm", desc="Initial pressure")


def h2o2_det(fuel_moles, ox_moles, T1, P1):
    """Wrapper: Anvil passes SI values (K, Pa) which the adapter handles."""
    return cea_detonation(
        fuel="H2", oxidizer="O2", fuel_moles=fuel_moles, ox_moles=ox_moles, T1=T1, P1=P1
    )


det.use(h2o2_det)

result = det.solve_forward()
result.summary(
    keys=[
        "fuel_moles",
        "ox_moles",
        "T1",
        "P1",
        "D_CJ",
        "T_CJ",
        "P_CJ",
        "P_ratio",
        "gamma_CJ",
        "MW_CJ",
        "a_CJ",
    ]
)

# Unit conversions using the engine
print(f"\n  Key results (unit engine conversions):")
print(
    f"    D_CJ  = {result['D_CJ']} {result['D_CJ'].unit}  ({result['D_CJ'].to('km/s')})"
)
print(f"    T_CJ  = {result['T_CJ']} {result['T_CJ'].unit}")
print(
    f"    P_CJ  = {result['P_CJ'].to('atm')}  ({result['P_CJ'].to('bar')})"
)


# =====================================================
# 3. Sweep: initial pressure
# =====================================================
print(f"\n[3] Sweep: D_CJ vs initial pressure...")
sweep_p = det.sweep("P1", np.array([0.5, 1.0, 2.0, 5.0, 10.0, 20.0]))
sweep_p.summary(outputs=["D_CJ", "T_CJ", "P_ratio", "P_CJ"])


# =====================================================
# 4. Sweep: initial temperature
# =====================================================
print(f"\n[4] Sweep: D_CJ vs initial temperature...")
det.set(P1=1)  # reset to 1 atm
sweep_t = det.sweep("T1", np.linspace(250, 600, 5))
sweep_t.summary(outputs=["D_CJ", "T_CJ", "P_ratio", "a_CJ"])


# =====================================================
# 5. Sensitivity analysis
# =====================================================
print(f"\n[5] Sensitivity: what drives D_CJ?")
det.set(T1=300, P1=1)
sens = det.sensitivity(outputs=["D_CJ", "T_CJ"])
sens.summary()


# =====================================================
# 6. COMPOSITION: Detonation system -> PDE nozzle
# =====================================================
print(f"\n[6] Composition: Detonation -> PDE Nozzle")
print(f"    The det system is used as a sub-system feeding the nozzle.\n")

# Build the PDE system that USES the det system via composition
pde = System("pulse_det_engine")

# PDE inputs (same names as det system, so composition inherits them)
pde.add("fuel_moles", 2.0)
pde.add("ox_moles", 1.0)
pde.add("T1", 300, "K", desc="Initial mixture temperature")
pde.add("P1", 600, "psi", desc="Initial mixture pressure")
pde.add("A_throat", 0.005, "m^2", desc="Nozzle throat area")
pde.add("A_exit", 0.05, "m^2", desc="Nozzle exit area")
pde.add("P_amb", 101325, "Pa", desc="Ambient pressure")

# USE the detonation system as a sub-system (composition!)
pde.use(det)

# Nozzle expansion of detonation products
pde.use("nozzle_area_ratio")
pde.use("area_mach_supersonic", map={"gamma": "gamma_CJ"})


def pde_exit(T_CJ, P_CJ, gamma_CJ, MW_CJ, M_exit):
    """Compute nozzle exit conditions from CJ state."""
    R_gas = 8314.46 / (MW_CJ * 1000)  # MW_CJ is in kg/mol
    T0_T = 1 + ((gamma_CJ - 1) / 2) * M_exit**2
    P0_P = T0_T ** (gamma_CJ / (gamma_CJ - 1))
    T_exit = T_CJ / T0_T
    P_exit = P_CJ / P0_P
    V_exit = M_exit * (gamma_CJ * R_gas * T_exit) ** 0.5
    return {
        "T_exit": Q(T_exit, "K"),
        "P_exit": Q(P_exit, "Pa"),
        "V_exit": Q(V_exit, "m/s"),
    }


def pde_performance(
    P_CJ, A_throat, gamma_CJ, MW_CJ, T_CJ, V_exit, P_exit, P_amb, A_exit
):
    """Compute PDE thrust and Isp."""
    R_gas = 8314.46 / (MW_CJ * 1000)
    t = (2 / (gamma_CJ + 1)) ** ((gamma_CJ + 1) / (2 * (gamma_CJ - 1)))
    mdot = P_CJ * A_throat * (gamma_CJ / (R_gas * T_CJ)) ** 0.5 * t
    F = mdot * V_exit + (P_exit - P_amb) * A_exit
    Isp = F / (mdot * 9.80665)
    return {
        "mdot_pde": Q(mdot, "kg/s"),
        "thrust_pde": Q(F, "N"),
        "Isp_pde": Q(Isp, "s"),
    }


pde.use(pde_exit)
pde.use(pde_performance)

r_pde = pde.solve_forward()
r_pde.summary(
    keys=[
        "T1",
        "P1",
        "fuel_moles",
        "ox_moles",
        "D_CJ",
        "T_CJ",
        "P_CJ",
        "M_exit",
        "V_exit",
        "thrust_pde",
        "Isp_pde",
        "mdot_pde",
    ]
)

print(f"\n  PDE performance (unit conversions):")
print(
    f"    Thrust = {r_pde['thrust_pde'].to('kN')} ({r_pde['thrust_pde'].to('lbf')})"
)
print(f"    Isp    = {r_pde['Isp_pde']} {r_pde['Isp_pde'].unit}")
print(f"    V_exit = {r_pde['V_exit'].to('km/s')}")

# Sweep the PDE over initial pressure
print(f"\n  Sweep: PDE performance vs initial pressure...")
sweep_pde = pde.sweep("P1", np.array([0.5, 1.0, 2.0, 5.0, 10.0]))
sweep_pde.summary(outputs=["D_CJ", "T_CJ", "thrust_pde", "Isp_pde"])


# =====================================================
# 7. Export
# =====================================================
print(f"\n[7] Exporting results...")
r_pde.to_csv("pde_results.csv")
print(f"  Saved: pde_results.csv")
sweep_pde.to_csv("pde_pressure_sweep.csv", outputs=["D_CJ", "thrust_pde", "Isp_pde"])
print(f"  Saved: pde_pressure_sweep.csv")

# Cleanup
os.remove("pde_results.csv")
os.remove("pde_pressure_sweep.csv")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example 11: ODE, BVP, and PDE Solvers

`examples/ex11_ode_solvers.py`

```python
import sys, os
import numpy as np


import anvil
from anvil import Q
from anvil import solvers

print("=" * 60)
print("  Example 11: ODE / BVP / PDE Solvers")
print("=" * 60)


# =====================================================
# Part A: Non-stiff ODE, satellite reentry drag
#
# State: [v, h]   v = speed (m/s), h = altitude (m)
# dv/dt = -D/m - g*sin(gamma)     (deceleration)
# dh/dt = -v * sin(gamma)          (altitude loss)
#
# Simplified: constant flight-path angle gamma = 3 deg,
# exponential atmosphere, drag-only deceleration.
# =====================================================
print("\n" + "=" * 40)
print("  Part A: Satellite Reentry (RK45)")
print("=" * 40)

rho0    = 1.225       # kg/m^3, sea-level density
H_scale = 8500.0      # m     , scale height
Cd      = 1.2         # drag coefficient (blunt capsule)
A       = 10.0        # m^2   , cross-section area
m       = 1500.0      # kg    , capsule mass
g       = 9.80665     # m/s^2
gamma   = np.radians(3.0)  # flight-path angle (shallow entry)

def reentry(t, y):
    v, h = y
    h = max(h, 0.0)
    rho = rho0 * np.exp(-h / H_scale)
    D = 0.5 * rho * Cd * A * v**2
    dvdt = -(D / m) - g * np.sin(gamma)
    dhdt = -v * np.sin(gamma)
    return [dvdt, dhdt]

v0 = 7800.0   # m/s, orbital entry speed
h0 = 120e3    # m  , entry altitude 120 km

t_eval = np.linspace(0, 500, 2000)
sol_a = solvers.solve_ode(
    reentry,
    t_span=(0, 500),
    y0=[v0, h0],
    method="RK45",
    t_eval=t_eval,
    rtol=1e-8,
    atol=1e-10,
    verbose=True,
)

v_final = sol_a["y"][0, -1]
h_final = sol_a["y"][1, -1]
t_ground_idx = np.argmin(np.abs(sol_a["y"][1]))  # closest to h=0

print(f"\n  Entry conditions:")
print(f"    v0 = {v0:.0f} m/s,  h0 = {h0/1e3:.0f} km")
print(f"  After {sol_a['t'][-1]:.0f} s:")
print(f"    v  = {v_final:.0f} m/s,  h = {h_final/1e3:.1f} km")
print(f"  Peak deceleration at t ≈ {sol_a['t'][np.gradient(sol_a['y'][0]).argmin()]:.0f} s")
print(f"  ODE solved in {sol_a['nfev']} function evaluations")


# =====================================================
# Part B: Stiff ODE, chemical kinetics (A → B → C)
#
# Classic stiff problem: two reactions with very
# different time constants (τ1 << τ2).
#
# d[A]/dt = -k1 * [A]
# d[B]/dt =  k1 * [A]  -  k2 * [B]
# d[C]/dt =  k2 * [B]
#
# k1 = 1000 s^-1 (fast),  k2 = 0.01 s^-1 (slow)
# =====================================================
print("\n" + "=" * 40)
print("  Part B: Chemical Kinetics A→B→C (BDF)")
print("=" * 40)

k1 = 1000.0   # fast reaction
k2 = 0.01     # slow reaction

def kinetics(t, y):
    A, B, C = y
    dA = -k1 * A
    dB =  k1 * A - k2 * B
    dC =  k2 * B
    return [dA, dB, dC]

t_end = 300.0   # s, watch the slow reaction complete

sol_b = solvers.solve_ode_stiff(
    kinetics,
    t_span=(0, t_end),
    y0=[1.0, 0.0, 0.0],    # all species A initially
    method="BDF",
    t_eval=np.linspace(0, t_end, 500),
    rtol=1e-6,
    atol=1e-10,
    verbose=True,
)

A_f, B_f, C_f = sol_b["y"][:, -1]
print(f"\n  Rate constants: k1 = {k1} s⁻¹ (fast),  k2 = {k2} s⁻¹ (slow)")
print(f"  At t = {t_end:.0f} s:")
print(f"    [A] = {A_f:.6f}   (consumed by fast reaction)")
print(f"    [B] = {B_f:.6f}   (intermediate)")
print(f"    [C] = {C_f:.6f}   (product of slow reaction)")
print(f"    Sum = {A_f+B_f+C_f:.8f}  (should be 1.0, mass conservation)")
print(f"  Solved in {sol_b['nfev']} rhs evaluations")

# Compare: would RK45 fail on this stiff system?
print(f"\n  Note: RK45 step-size constraint ≈ 1/k1 = {1/k1:.1e} s")
print(f"  BDF adapts automatically, no user tuning needed.")


# =====================================================
# Part C: Boundary Value Problem, fin temperature
#
# Extended surface (fin) with tip insulated:
#   d²T/dx² - m² * (T - T_inf) = 0
#
#   BC: T(0) = T_base  (fin base temperature)
#       dT/dx|_{x=L} = 0  (insulated tip)
#
# Solution: T(x) = T_inf + (T_base - T_inf) * cosh(m*(L-x)) / cosh(m*L)
# =====================================================
print("\n" + "=" * 40)
print("  Part C: Fin Temperature (BVP)")
print("=" * 40)

T_base = 400.0    # K, fin base
T_inf  = 300.0    # K, ambient
h_conv = 50.0     # W/m^2/K, convection coefficient
k_fin  = 200.0    # W/m/K, aluminum
t_fin  = 0.002    # m, fin thickness
L_fin  = 0.1      # m, fin length (10 cm)

P_perim = 2 * (t_fin + 0.05)   # m, perimeter (assume 5 cm width)
A_cs    = t_fin * 0.05          # m^2, cross section
m_fin   = np.sqrt(h_conv * P_perim / (k_fin * A_cs))

print(f"\n  Fin: L={L_fin*100:.0f} cm,  t={t_fin*1000:.0f} mm,  k={k_fin} W/m/K")
print(f"  h_conv = {h_conv} W/m²/K,  m = {m_fin:.2f} m⁻¹")

def fin_ode(x, y):
    # y[0] = T - T_inf,  y[1] = dT/dx
    return np.vstack([y[1], m_fin**2 * y[0]])

def fin_bc(ya, yb):
    # ya[0] = T_base - T_inf (at x=0)
    # yb[1] = 0             (insulated tip)
    return np.array([ya[0] - (T_base - T_inf), yb[1]])

x_init = np.linspace(0, L_fin, 8)
theta0 = (T_base - T_inf) * np.cosh(m_fin * (L_fin - x_init)) / np.cosh(m_fin * L_fin)
y_init = np.zeros((2, x_init.size))
y_init[0] = theta0
y_init[1] = -m_fin * (T_base - T_inf) * np.sinh(m_fin * (L_fin - x_init)) / np.cosh(m_fin * L_fin)

sol_c = solvers.solve_bvp(
    fin_ode,
    fin_bc,
    x=x_init,
    y_init=y_init,
    tol=1e-6,
    verbose=False,
)

x_fine = np.linspace(0, L_fin, 50)
T_numerical = T_inf + sol_c["sol"](x_fine)[0]
T_analytical = T_inf + (T_base - T_inf) * np.cosh(m_fin * (L_fin - x_fine)) / np.cosh(m_fin * L_fin)
max_err = np.max(np.abs(T_numerical - T_analytical))

T_tip_num = T_inf + sol_c["y"][0, -1]
T_tip_ana = T_inf + (T_base - T_inf) / np.cosh(m_fin * L_fin)

print(f"\n  Tip temperature (numerical):  {T_tip_num:.3f} K")
print(f"  Tip temperature (analytical): {T_tip_ana:.3f} K")
print(f"  Max error vs analytical:      {max_err:.2e} K")

# Fin efficiency
Q_actual  = k_fin * A_cs * m_fin * (T_base - T_inf) * np.tanh(m_fin * L_fin)
Q_max     = h_conv * P_perim * L_fin * (T_base - T_inf)
eta_fin   = Q_actual / Q_max
print(f"\n  Heat removed: {Q_actual:.1f} W")
print(f"  Fin efficiency: {eta_fin:.3f}  ({eta_fin*100:.1f}%)")


# =====================================================
# Part D: 1D Heat Equation (PDE), wall thermal soak
#
# Steel wall initially at T_amb. One face suddenly
# exposed to high-temperature gas (step input).
# Track temperature history through the wall.
#
# ∂T/∂t = α ∂²T/∂x²
# BC: T(0,t) = T_gas (hot face)
#     T(L,t) = T_amb (cold face, heat sink)
# IC: T(x,0) = T_amb
# =====================================================
print("\n" + "=" * 40)
print("  Part D: Wall Thermal Soak (1D PDE)")
print("=" * 40)

T_gas   = 1200.0    # K, gas temperature (step input)
T_amb   = 300.0     # K, initial wall / cold-face temperature
L_wall  = 0.025     # m, 25 mm steel wall
alpha   = 1.2e-5    # m^2/s, thermal diffusivity of steel
rho_cp  = 3.9e6     # J/m^3/K, volumetric heat capacity (for Q calc)

print(f"\n  Wall: L={L_wall*1000:.0f} mm,  α={alpha:.2e} m²/s")
print(f"  Step from T_amb={T_amb} K to T_gas={T_gas} K on hot face")
print(f"  Fourier number at t=60s: Fo = α·t/L² = {alpha*60/L_wall**2:.2f}")

sol_d = solvers.solve_pde_heat_1d(
    alpha=alpha,
    x_span=(0, L_wall),
    t_span=(0, 120),
    u_init=lambda x: np.full_like(x, T_amb),
    bc_left=T_gas,
    bc_right=T_amb,
    nx=80,
    verbose=True,
)

x_wall = sol_d["x"]
t_pde  = sol_d["t"]
T_pde  = sol_d["u"]

# Print temperature profile at several time snapshots
print(f"\n  Temperature profile through wall at key times (K):")
print(f"  {'x(mm)':>6s}", end="")
for t_snap in [5, 15, 30, 60, 120]:
    print(f"  {t_snap:>6.0f}s", end="")
print()

for xi in [0.0, 0.005, 0.010, 0.015, 0.020, 0.025]:
    ix = np.argmin(np.abs(x_wall - xi))
    print(f"  {xi*1000:>6.1f}", end="")
    for t_snap in [5, 15, 30, 60, 120]:
        it = np.argmin(np.abs(t_pde - t_snap))
        print(f"  {T_pde[it, ix]:>6.0f}", end="")
    print()

# Time to reach 500 K at mid-wall
ix_mid = len(x_wall) // 2
T_mid  = T_pde[:, ix_mid]
i_500  = np.argmax(T_mid >= 500.0)
if i_500 > 0:
    print(f"\n  Time for mid-wall to reach 500 K: {t_pde[i_500]:.1f} s")

# Heat flux at hot face (Fourier's law, approximate)
dTdx_hot = (T_pde[-1, 1] - T_pde[-1, 0]) / sol_d["dx"]
k_steel   = alpha * rho_cp
q_flux    = -k_steel * dTdx_hot
print(f"  Heat flux at hot face (t=120s): {q_flux/1000:.1f} kW/m²")


# =====================================================
# Part E: Use the dense ODE output (callable solution)
# =====================================================
print("\n" + "=" * 40)
print("  Part E: Dense ODE Output")
print("=" * 40)

# The sol object from solve_ode is callable: sol(t) → y(t)
dense_sol = sol_b["sol"]   # from the kinetics problem
t_query = np.array([0.001, 0.01, 0.1, 1.0, 10.0, 100.0])
y_query = dense_sol.sol(t_query)

print(f"\n  Kinetics concentrations at arbitrary t (dense output):")
print(f"  {'t(s)':>10s}  {'[A]':>12s}  {'[B]':>12s}  {'[C]':>12s}")
for i, t in enumerate(t_query):
    print(f"  {t:>10.3f}  {y_query[0, i]:>12.6f}  {y_query[1, i]:>12.6f}  {y_query[2, i]:>12.6f}")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 11: ODE / BVP / PDE Solvers
============================================================

========================================
  Part A: Satellite Reentry (RK45)
========================================
  ODE t = 5.0669e+01  (y[0] = 7.7271e+03)
  ODE t = 1.0359e+02  (y[0] = 7.1720e+03)
  ODE t = 1.5559e+02  (y[0] = 4.5060e+03)
  ODE t = 2.0573e+02  (y[0] = 1.9231e+03)
  ODE t = 2.5625e+02  (y[0] = 9.2363e+02)
  ODE t = 3.0707e+02  (y[0] = 5.3196e+02)
  ODE t = 3.5733e+02  (y[0] = 3.4562e+02)
  ODE t = 4.0806e+02  (y[0] = 2.3836e+02)
  ODE t = 4.6286e+02  (y[0] = 1.6480e+02)
  ODE converged: 446 function evaluations, t_final = 5.0000e+02

  Entry conditions:
    v0 = 7800 m/s,  h0 = 120 km
  After 500 s:
    v  = 128 m/s,  h = 45.9 km
  Peak deceleration at t ≈ 153 s
  ODE solved in 446 function evaluations

========================================
  Part B: Chemical Kinetics A→B→C (BDF)
========================================
  ODE(stiff) t = 3.1508e+01  (y[0] = -6.6611e-18)
  ODE(stiff) t = 6.8148e+01  (y[0] = -4.2482e-20)
  ODE(stiff) t = 1.0638e+02  (y[0] = -3.4203e-22)
  ODE(stiff) t = 1.4043e+02  (y[0] = 1.2952e-24)
  ODE(stiff) t = 1.7258e+02  (y[0] = 4.8805e-27)
  ODE(stiff) t = 2.0378e+02  (y[0] = -6.0653e-29)
... (77 more lines)
```


## Example 12: Project Registry

`examples/ex12_project_registry.py`

```python
import sys, os, tempfile
import numpy as np


import anvil
from anvil import Q, System

# Use a temp directory so the example is self-contained
_tmp = tempfile.mkdtemp(prefix="anvil_ex12_")

print("=" * 60)
print("  Example 12: Project Registry")
print("=" * 60)


# =====================================================
# 1. Open a project store
# =====================================================
print("\n[1] Opening project store for 'hx_correlations'...")

proj = anvil.project("hx_correlations", path=_tmp)
print(f"  Repr: {proj}")


# =====================================================
# 2. Push draft RSQs to the project
# =====================================================
print("\n[2] Registering draft correlations...")

def ntu_crossflow(UA, C_min, C_max):
    """NTU for cross-flow heat exchanger (both fluids unmixed)."""
    NTU = UA / C_min
    C_r = C_min / C_max
    # Kays & London correlation
    eps = 1 - np.exp((NTU**0.22 / C_r) * (np.exp(-C_r * NTU**0.78) - 1))
    return {"NTU_cf": NTU, "effectiveness_cf": eps, "C_ratio": C_r}

def shell_tube_ntu(UA, mdot_shell, mdot_tube, Cp_shell, Cp_tube):
    """NTU and effectiveness for 1-shell-pass 2-tube-pass (TEMA E)."""
    C_shell = mdot_shell * Cp_shell
    C_tube  = mdot_tube  * Cp_tube
    C_min   = min(C_shell, C_tube)
    C_max   = max(C_shell, C_tube)
    NTU     = UA / C_min
    C_r     = C_min / C_max
    # Shah & Sekulic formula for 1-2 shell-and-tube
    if C_r < 1.0:
        sqrt_term = np.sqrt(1 + C_r**2)
        eps = 2 / (1 + C_r + sqrt_term * (1 + np.exp(-NTU * sqrt_term)) / (1 - np.exp(-NTU * sqrt_term)))
    else:
        eps = NTU / (1 + NTU)   # limit for C_r → 1
    return {
        "NTU_st": NTU,
        "effectiveness_st": eps,
        "C_min_st": Q(C_min, "W/K"),
        "C_max_st": Q(C_max, "W/K"),
    }

def log_mean_temp(T_hot_in, T_hot_out, T_cold_in, T_cold_out):
    """Log Mean Temperature Difference for counter-flow arrangement."""
    dT1 = T_hot_in  - T_cold_out
    dT2 = T_hot_out - T_cold_in
    if abs(dT1 - dT2) < 1e-6:
        LMTD = dT1
    else:
        LMTD = (dT1 - dT2) / np.log(dT1 / max(dT2, 1e-6))
    return {"LMTD": Q(LMTD, "K")}

proj.push(ntu_crossflow,   domain="heat_transfer", description="Cross-flow NTU (Kays & London)")
proj.push(shell_tube_ntu,  domain="heat_transfer", description="1-2 shell-and-tube NTU (Shah & Sekulic)")
proj.push(log_mean_temp,   domain="heat_transfer", description="Log Mean Temperature Difference")

proj.list()


# =====================================================
# 3. Use project RSQs directly
# =====================================================
print("\n[3] Direct calls via proj.R.*")

r_cf = proj.R.ntu_crossflow(UA=3500, C_min=1800, C_max=2400)
print(f"\n  Cross-flow HX (UA=3500, C_min=1800):")
print(f"    NTU         = {r_cf['NTU_cf']:.3f}")
print(f"    C_ratio     = {r_cf['C_ratio']:.3f}")
print(f"    effectiveness = {r_cf['effectiveness_cf']:.4f}")

r_st = proj.R.shell_tube_ntu(UA=5000, mdot_shell=2.0, mdot_tube=1.5,
                               Cp_shell=4186, Cp_tube=1005)
print(f"\n  Shell-and-tube HX (UA=5000):")
print(f"    NTU         = {r_st['NTU_st']:.3f}")
print(f"    effectiveness = {r_st['effectiveness_st']:.4f}")


# =====================================================
# 4. Build a System using project RSQs
# =====================================================
print("\n[4] System using project RSQ for outlet temperature calculation...")

def outlet_temps_from_eff(effectiveness_cf, C_min, C_hot_in, T_hot_in, T_cold_in, C_hot, C_cold):
    Q_actual = effectiveness_cf * C_min * (T_hot_in - T_cold_in)
    T_hot_out  = T_hot_in  - Q_actual / C_hot
    T_cold_out = T_cold_in + Q_actual / C_cold
    return {
        "Q_actual": Q(Q_actual, "W"),
        "T_hot_out":  Q(T_hot_out,  "K"),
        "T_cold_out": Q(T_cold_out, "K"),
    }

hx = System("crossflow_hx")
hx.add("T_hot_in",   450,   "K")
hx.add("T_cold_in",  290,   "K")
hx.add("mdot_hot",   1.2,   "kg/s")
hx.add("mdot_cold",  2.0,   "kg/s")
hx.add("Cp_hot",    1050,   "J/kg/K")
hx.add("Cp_cold",   4186,   "J/kg/K")
hx.add("UA",        3500,   "W/K")

def compute_capacity_rates(mdot_hot, Cp_hot, mdot_cold, Cp_cold):
    C_hot  = mdot_hot  * Cp_hot
    C_cold = mdot_cold * Cp_cold
    C_min  = min(C_hot, C_cold)
    C_max  = max(C_hot, C_cold)
    C_hot_in = C_hot   # pass through for outlet_temps
    return {"C_hot": Q(C_hot, "W/K"), "C_cold": Q(C_cold, "W/K"),
            "C_min": Q(C_min, "W/K"), "C_max": Q(C_max, "W/K"),
            "C_hot_in": Q(C_hot, "W/K")}

hx.use(compute_capacity_rates)
hx.use(proj.R.ntu_crossflow)     # project RSQ used directly in System
hx.use(outlet_temps_from_eff)

result = hx.solve_forward()
result.summary(keys=["T_hot_in", "T_cold_in", "UA",
                      "NTU_cf", "effectiveness_cf",
                      "T_hot_out", "T_cold_out", "Q_actual"])


# =====================================================
# 5. Context manager, route anvil.push() to project
# =====================================================
print("\n[5] Context manager: push drafts inside 'with' block...")

proj2 = anvil.project("fouling_study", path=_tmp)

with proj2:
    @anvil.relation(domain="heat_transfer", register=False)
    def fouling_resistance(mdot, rho_fluid, mu_fluid, D_tube, L_tube, k_fluid):
        """Estimate fouling resistance from Dittus-Boelter Nu and fouling factor."""
        V = mdot / (rho_fluid * np.pi * (D_tube / 2)**2)
        Re = rho_fluid * V * D_tube / mu_fluid
        Pr = mu_fluid * 4186 / k_fluid   # approximate Prandtl
        Nu = 0.023 * Re**0.8 * Pr**0.4  # Dittus-Boelter
        h = Nu * k_fluid / D_tube
        Rf = 0.0002    # typical fouling resistance (m^2·K/W)
        U_fouled = 1.0 / (1.0 / h + Rf)
        A_tube = np.pi * D_tube * L_tube
        return {"Re_tube": Re, "Nu_tube": Nu, "h_tube": Q(h, "W/m^2/K"),
                "U_fouled": Q(U_fouled, "W/m^2/K"), "UA_fouled": Q(U_fouled * A_tube, "W/K")}

    proj2.push(fouling_resistance)

# Outside the with block, context no longer active
proj2.list()

r_foul = proj2.R.fouling_resistance(
    mdot=0.5, rho_fluid=1000, mu_fluid=0.001,
    D_tube=0.02, L_tube=2.0, k_fluid=0.6
)
print(f"\n  Fouling study (D={20}mm, L=2m):")
print(f"    Re      = {r_foul['Re_tube']:.0f}")
print(f"    Nu      = {r_foul['Nu_tube']:.0f}")
print(f"    h       = {r_foul['h_tube']}")
print(f"    UA_foul = {r_foul['UA_fouled']}")


# =====================================================
# 6. Search within project
# =====================================================
print("\n[6] Searching project for 'NTU'...")
proj.search("NTU")

print("\n  Searching for 'effectiveness'...")
proj.search("effectiveness")


# =====================================================
# 7. Promote a tested RSQ to global registry
# =====================================================
print("\n[7] Promoting 'log_mean_temp' to global registry...")

# Verify it isn't already global
existing = anvil.registry.search("log_mean_temp")
if not existing:
    proj.promote("log_mean_temp")
    print("  Verifying it's in global registry:")
    anvil.registry.search("log_mean_temp")

    # Use via global namespace
    r_lmtd = anvil.R.log_mean_temp(
        T_hot_in=result["T_hot_in"].si,
        T_hot_out=result["T_hot_out"].si,
        T_cold_in=result["T_cold_in"].si,
        T_cold_out=result["T_cold_out"].si,
    )
    print(f"\n  LMTD via global registry: {r_lmtd['LMTD']}")

    # Clean up global registry
    anvil.registry.remove("log_mean_temp")
    print("  Cleaned up: removed 'log_mean_temp' from global registry.")
else:
    print("  (already in global registry)")


# =====================================================
# 8. Two projects open simultaneously
# =====================================================
print("\n[8] Two projects open simultaneously (no conflict)...")

proj_a = anvil.project("project_A", path=_tmp)
proj_b = anvil.project("project_B", path=_tmp)

def my_rsq_v1(x, k=1.0):
    return {"y_v1": k * x}

def my_rsq_v2(x, k=1.2):
    return {"y_v2": k * x + 0.5}

proj_a.push(my_rsq_v1, domain="test")
proj_b.push(my_rsq_v2, domain="test")

ra = proj_a.R.my_rsq_v1(x=5.0)
rb = proj_b.R.my_rsq_v2(x=5.0)
print(f"\n  Project A, my_rsq_v1(5): y = {ra['y_v1']}")
print(f"  Project B, my_rsq_v2(5): y = {rb['y_v2']}")
print(f"  Global registry: unaffected (no 'my_rsq_v1' or 'my_rsq_v2' there)")


# =====================================================
# Cleanup temp directory
# =====================================================
import shutil
shutil.rmtree(_tmp, ignore_errors=True)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 12: Project Registry
============================================================

[1] Opening project store for 'hx_correlations'...
  Project 'hx_correlations' opened  (C:\Users\rc\AppData\Local\Temp\anvil_ex12_ft5adu2u\.anvil\project_hx_correlations.db)
  Repr: <Project 'hx_correlations': 0 RSQs at C:\Users\rc\AppData\Local\Temp\anvil_ex12_ft5adu2u>

[2] Registering draft correlations...
  [hx_correlations] Registered 'ntu_crossflow' (R) in domain 'heat_transfer'.
  [hx_correlations] Registered 'shell_tube_ntu' (R) in domain 'heat_transfer'.
  [hx_correlations] Registered 'log_mean_temp' (R) in domain 'heat_transfer'.

  Project: hx_correlations  (C:\Users\rc\AppData\Local\Temp\anvil_ex12_ft5adu2u)

  Relations (3):
    log_mean_temp                   [heat_transfer]
      Log Mean Temperature Difference
    ntu_crossflow                   [heat_transfer]
      Cross-flow NTU (Kays & London)
    shell_tube_ntu                  [heat_transfer]
      1-2 shell-and-tube NTU (Shah & Sekulic)

  Total: 3 RSQs

[3] Direct calls via proj.R.*

  Cross-flow HX (UA=3500, C_min=1800):
    NTU         = 1.944
    C_ratio     = 0.750
    effectiveness = 0.6690

  Shell-and-tube HX (UA=5000):
    NTU         = 3.317
... (71 more lines)
```


## Example 13: Control Systems Analysis

`examples/ex13_controls_analysis.py`

```python
import sys, os

# Windows consoles default to cp1252; this output uses Greek symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np


import anvil
from anvil import Q, System
from anvil import solvers

print("=" * 60)
print("  Example 13: Control Systems Analysis")
print("=" * 60)


# =====================================================
# 1. Plant model: second-order system
#
# G(s) = K_plant / (τ^2 s^2 + 2ζτ s + 1)
#
# Natural frequency ωn = 1/τ = 2 rad/s
# Open-loop damping   ζ_ol = 0.1 (lightly damped)
# DC gain             K_plant = 1.0
# =====================================================
print("\n[1] Plant: Second-order system")

omega_n_plant = 2.0    # rad/s, natural frequency
zeta_plant    = 0.1    #, open-loop damping (lightly damped)
K_plant       = 1.0    #, DC gain

print(f"\n  ωn = {omega_n_plant} rad/s,  ζ_ol = {zeta_plant},  K = {K_plant}")
print(f"  Open-loop step response characteristics:")

r_ol = anvil.R.second_order_metrics(omega_n=omega_n_plant, zeta=zeta_plant)
print(f"    Overshoot:  {r_ol['overshoot_pct']}%")
print(f"    t_settle:   {r_ol['t_settle']}  (2% criterion)")
print(f"    t_rise:     {r_ol['t_rise']}")
print(f"    t_peak:     {r_ol['t_peak']}")
print(f"    ωd:         {r_ol['omega_d']}")


# =====================================================
# 2. Ziegler-Nichols PID tuning
#
# Find the ultimate gain Ku by increasing proportional
# gain until sustained oscillations. Here we use a
# known value for the second-order plant.
# =====================================================
print("\n[2] Ziegler-Nichols PID Tuning")

# For this plant, ultimate gain and period are known analytically:
# Ku = (2*zeta*omega_n)^2 / (omega_n^2 * K_plant) * ... (simplified here)
# Using rule-of-thumb values for demonstration:
Ku = 12.0    # ultimate gain (proportional only, at onset of oscillation)
Tu = 2.2     # s, ultimate period

print(f"\n  Ultimate gain Ku = {Ku},  Ultimate period Tu = {Tu} s")
print(f"\n  Ziegler-Nichols tuning methods:")

for method in ["classic", "no_overshoot", "some_overshoot"]:
    r_zn = anvil.R.ziegler_nichols_pid(Ku=Ku, Tu=Tu, method=method)
    Kp = r_zn["Kp"].si if hasattr(r_zn["Kp"], "si") else r_zn["Kp"]
    Ti = r_zn["Ti"].si if hasattr(r_zn["Ti"], "si") else r_zn["Ti"]
    Td = r_zn["Td"].si if hasattr(r_zn["Td"], "si") else r_zn["Td"]
    print(f"  [{method:>15s}]  Kp={Kp:.3f}  Ti={Ti:.3f}s  Td={Td:.4f}s")

# Use classic Z-N as starting point
r_zn = anvil.R.ziegler_nichols_pid(Ku=Ku, Tu=Tu, method="classic")
def _v(x):
    return float(x.si) if hasattr(x, "si") else float(x)
Kp_zn = _v(r_zn["Kp"])
Ki_zn = _v(r_zn["Ki"])
Kd_zn = _v(r_zn["Kd"])


# =====================================================
# 3. Closed-loop step response via ODE simulation
#
# Plant: d²y/dt² + 2ζωn dy/dt + ωn² y = ωn² K_plant u
# PID:   u = Kp*e + Ki∫e dt + Kd*de/dt
# =====================================================
print("\n[3] Closed-loop step response simulation (PID)")

def closed_loop_ode(t, state, Kp, Ki, Kd, ref=1.0):
    """
    State: [y, dy_dt, integral_e]
    Plant: second-order + PID feedback
    """
    y, dydt, int_e = state
    e     = ref - y
    de_dt = -dydt   # de/dt = d(ref-y)/dt = -dy/dt (constant ref)
    u     = Kp * e + Ki * int_e + Kd * de_dt
    # Plant: d²y/dt² = ωn²(K_plant * u - y) - 2ζωn * dy/dt
    d2ydt2 = omega_n_plant**2 * (K_plant * u - y) - 2 * zeta_plant * omega_n_plant * dydt
    return [dydt, d2ydt2, e]

t_sim = np.linspace(0, 8, 1000)

# Open-loop step (Kp=1, Ki=0, Kd=0)
sol_ol = solvers.solve_ode(
    lambda t, s: closed_loop_ode(t, s, Kp=1.0, Ki=0.0, Kd=0.0),
    t_span=(0, 8), y0=[0.0, 0.0, 0.0], t_eval=t_sim, rtol=1e-8
)

# Z-N tuned PID
sol_zn = solvers.solve_ode(
    lambda t, s: closed_loop_ode(t, s, Kp=Kp_zn, Ki=Ki_zn, Kd=Kd_zn),
    t_span=(0, 8), y0=[0.0, 0.0, 0.0], t_eval=t_sim, rtol=1e-8
)

y_ol = sol_ol["y"][0]
y_zn = sol_zn["y"][0]

# Measure step response metrics
def step_metrics(t, y, ref=1.0, band=0.02):
    OS_pct = (y.max() - ref) / ref * 100 if y.max() > ref else 0.0
    settled = np.where(np.abs(y - ref) <= band * ref)[0]
    t_settle = t[settled[0]] if len(settled) else float("inf")
    above_half = np.where(y >= 0.5 * ref)[0]
    t_rise = t[above_half[0]] if len(above_half) else float("inf")
    return OS_pct, t_settle, t_rise

os_ol, ts_ol, tr_ol = step_metrics(t_sim, y_ol)
os_zn, ts_zn, tr_zn = step_metrics(t_sim, y_zn)

print(f"\n  Step response summary (unit step, 2% band):")
print(f"  {'Controller':>16s}  {'OS%':>6s}  {'t_settle(s)':>12s}  {'t_rise(s)':>10s}")
print(f"  {'P only (K=1)':>16s}  {os_ol:>6.1f}  {ts_ol:>12.3f}  {tr_ol:>10.3f}")
print(f"  {'Z-N PID':>16s}  {os_zn:>6.1f}  {ts_zn:>12.3f}  {tr_zn:>10.3f}")


# =====================================================
# 4. PID output RSQ, compute instantaneous control action
# =====================================================
print("\n[4] PID output RSQ")

pid_sys = System("pid_controller")
pid_sys.add("error",            0.35,     desc="Tracking error (rad)")
pid_sys.add("integral_error",   0.12,     desc="Integral of error (rad·s)")
pid_sys.add("derivative_error", -0.08,    desc="Derivative of error (rad/s)")
pid_sys.add("Kp",               Kp_zn,    desc="Proportional gain")
pid_sys.add("Ki",               Ki_zn,    desc="Integral gain")
pid_sys.add("Kd",               Kd_zn,    desc="Derivative gain")
pid_sys.use("pid_output")

r_pid = pid_sys.solve_forward()
result_u = r_pid["u_pid"].si if hasattr(r_pid["u_pid"], "si") else r_pid["u_pid"]
print(f"\n  Error = 0.35,  Integral = 0.12,  Derivative = -0.08")
print(f"  Z-N PID: Kp={Kp_zn:.3f},  Ki={Ki_zn:.3f},  Kd={Kd_zn:.4f}")
print(f"  Control action u = {result_u:.4f}")


# =====================================================
# 5. Stability check, Routh-Hurwitz (2nd order)
# =====================================================
print("\n[5] Routh-Hurwitz Stability Check")

print(f"\n  Characteristic polynomial: τ²s² + 2ζτs + 1  (2nd order)")
print(f"  Coefficients: a1 = 2ζ/ωn,  a0 = 1/ωn²")

test_cases = [
    ("Open-loop (ζ=0.1)",   2*0.1/omega_n_plant, 1/omega_n_plant**2),
    ("Negative damping",    -0.5,                  1.0),
    ("Unstable (a0<0)",      1.0,                 -1.0),
    ("Critically damped",    2/omega_n_plant,       1/omega_n_plant**2),
]

print(f"\n  {'Case':30s}  {'a1':>6s}  {'a0':>8s}  {'Stable?':>8s}")
print(f"  {'-'*60}")
for name, a1, a0 in test_cases:
    r_rh = anvil.R.routh_hurwitz_2nd(a1=a1, a0=a0)
    stable = r_rh["stable"]
    stable_v = stable if isinstance(stable, bool) else bool(stable)
    print(f"  {name:30s}  {a1:>6.3f}  {a0:>8.5f}  {'YES' if stable_v else 'NO':>8s}")


# =====================================================
# 6. Second-order metrics sweep, ωn and ζ trade study
# =====================================================
print("\n[6] Second-order metrics sweep, ζ trade study")

metrics_sys = System("step_response_design")
metrics_sys.add("omega_n", 5.0)   # rad/s, closed-loop natural frequency
metrics_sys.add("zeta",    0.7)   # damping ratio
metrics_sys.use("second_order_metrics")

print(f"\n  Sweep ζ at ωn = 5 rad/s:")
print(f"  {'ζ':>6s}  {'OS%':>8s}  {'t_settle(s)':>12s}  {'t_rise(s)':>10s}  {'BW(Hz)':>8s}")
print(f"  {'-'*52}")

for zeta in [0.3, 0.5, 0.7, 1.0, 1.5]:
    metrics_sys.set(zeta=zeta)
    r = metrics_sys.solve_forward()
    def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
    print(f"  {zeta:>6.2f}  {_v(r['overshoot_pct']):>8.1f}  "
          f"{_v(r['t_settle']):>12.4f}  {_v(r['t_rise']):>10.4f}  "
          f"{_v(r['bandwidth_Hz']) if 'bandwidth_Hz' in r else 0.0:>8.3f}")

sweep_zeta = metrics_sys.sweep("zeta", np.linspace(0.2, 2.0, 10))
sweep_zeta.summary(outputs=["overshoot_pct", "t_settle", "t_rise", "omega_d"])

print(f"\n  Design choice: ζ = 0.7 balances OS% and t_settle (classic choice).")


# =====================================================
# 7. First-order step response RSQ
# =====================================================
print("\n[7] First-order step response metrics")

fo_sys = System("first_order_control")
fo_sys.add("K",        2.0,   desc="DC gain")
fo_sys.add("tau",      0.5,   desc="Time constant (s)")
fo_sys.use("first_order_step")

r_fo = fo_sys.solve_forward()
def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
print(f"\n  Plant: K={2.0}, τ={0.5}s")
print(f"    Settling time (2%): {_v(r_fo['t_settle']):.3f} s")
print(f"    Rise time:          {_v(r_fo['t_rise']):.3f} s")
print(f"    Bandwidth:          {_v(r_fo['bandwidth_Hz']):.3f} Hz")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 13: Control Systems Analysis
============================================================

[1] Plant: Second-order system

  ωn = 2.0 rad/s,  ζ_ol = 0.1,  K = 1.0
  Open-loop step response characteristics:
    Overshoot:  72.9247614287671%
    t_settle:   20.0  (2% criterion)
    t_rise:     0.49375
    t_peak:     1.5787097084991382
    ωd:         1.98997487421324

[2] Ziegler-Nichols PID Tuning

  Ultimate gain Ku = 12.0,  Ultimate period Tu = 2.2 s

  Ziegler-Nichols tuning methods:
  [        classic]  Kp=7.200  Ti=1.100s  Td=0.2750s
  [   no_overshoot]  Kp=7.200  Ti=1.100s  Td=0.2750s
  [ some_overshoot]  Kp=7.200  Ti=1.100s  Td=0.2750s

[3] Closed-loop step response simulation (PID)

  Step response summary (unit step, 2% band):
        Controller     OS%   t_settle(s)   t_rise(s)
      P only (K=1)     0.0           inf       0.585
           Z-N PID    12.1         0.529       0.264

[4] PID output RSQ

  Error = 0.35,  Integral = 0.12,  Derivative = -0.08
  Z-N PID: Kp=7.200,  Ki=6.545,  Kd=1.9800
... (54 more lines)
```


## Example 14: Materials, Fatigue, Fracture, and Composites

`examples/ex14_materials_fatigue.py`

```python
import sys, os

# Windows consoles default to cp1252; this output uses Greek symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np


import anvil
from anvil import Q, System

print("=" * 60)
print("  Example 14: Materials, Fatigue, Fracture, Composites")
print("=" * 60)


# =====================================================
# Material: 300M High-Strength Steel (typical turbopump shaft)
# =====================================================
E_steel       = 207e9      # Pa, Young's modulus
sigma_y       = 1700e6     # Pa, 0.2% yield strength
sigma_uts     = 1950e6     # Pa, ultimate tensile strength
sigma_f_prime = 2100e6     # Pa, fatigue strength coefficient (Basquin)
b_exp         = -0.07      #,   Basquin exponent (typical for high-strength steel)
KIc           = 70e6       # Pa√m, plane strain fracture toughness

print(f"\n  Material: 300M Steel")
print(f"    E       = {E_steel/1e9:.0f} GPa")
print(f"    σ_y     = {sigma_y/1e6:.0f} MPa")
print(f"    σ_UTS   = {sigma_uts/1e6:.0f} MPa")
print(f"    σ_f'    = {sigma_f_prime/1e6:.0f} MPa  (Basquin coeff)")
print(f"    b       = {b_exp}  (Basquin exponent)")
print(f"    KIc     = {KIc/1e6:.0f} MPa√m")


# =====================================================
# 1. Safety Factor Check, nominal operating stress
# =====================================================
print("\n[1] Safety Factor, Nominal Operating Stress")

design_stress = 750e6    # Pa, stress amplitude at max load

r_sf = anvil.R.safety_factor(allowable_stress=sigma_y, applied_stress=design_stress)
def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
SF   = _v(r_sf["safety_factor"])
MoS  = _v(r_sf["margin_of_safety"])
pass_ = bool(r_sf["pass"])

print(f"\n  σ_applied = {design_stress/1e6:.0f} MPa,  σ_allowable = {sigma_y/1e6:.0f} MPa")
print(f"  Safety factor:   SF = {SF:.3f}  ({'PASS' if pass_ else 'FAIL'})")
print(f"  Margin of safety: MoS = {MoS:.3f}  ({MoS*100:.1f}%)")

# Sweep over applied stress to find failure boundary
sf_sys = System("safety_check")
sf_sys.add("allowable_stress", sigma_y, "Pa")
sf_sys.add("applied_stress",   design_stress, "Pa")
sf_sys.use("safety_factor")

sweep_sf = sf_sys.sweep("applied_stress", np.linspace(500e6, 2000e6, 7))
sweep_sf.summary(outputs=["safety_factor", "margin_of_safety", "pass"])


# =====================================================
# 2. Fatigue Life, Basquin's Law  N = (σ_a / σ_f')^(1/b)
# =====================================================
print("\n[2] Fatigue Life, Basquin's Law")

stress_amplitudes = [300e6, 500e6, 750e6, 1000e6, 1200e6]

print(f"\n  S-N curve for 300M Steel:")
print(f"  {'σ_a (MPa)':>12s}  {'N_cycles':>14s}  {'Life(flights)':>14s}")
print(f"  {'-'*42}")

flights_per_cycle = 100   # cycles per flight for this shaft

for sigma_a in stress_amplitudes:
    r_fat = anvil.R.fatigue_life_basquin(
        sigma_a=sigma_a,
        sigma_f_prime=sigma_f_prime,
        b_exponent=b_exp
    )
    N = _v(r_fat["N_cycles"])
    flights = N / flights_per_cycle
    print(f"  {sigma_a/1e6:>12.0f}  {N:>14.2e}  {flights:>14.1f}")

# Build a fatigue system for sweep
fatigue_sys = System("basquin_fatigue")
fatigue_sys.add("sigma_a",       design_stress, "Pa",  desc="Stress amplitude")
fatigue_sys.add("sigma_f_prime", sigma_f_prime, "Pa",  desc="Basquin coefficient")
fatigue_sys.add("b_exponent",    b_exp,                desc="Basquin exponent")
fatigue_sys.use("fatigue_life_basquin")

print(f"\n  Fatigue life sweep (stress amplitude vs N_cycles):")
sweep_fat = fatigue_sys.sweep("sigma_a", np.linspace(200e6, 1200e6, 8))
sweep_fat.summary(outputs=["N_cycles"])


# =====================================================
# 3. Miner's Rule, Cumulative Fatigue Damage
#
# Flight spectrum: 3 distinct load levels, each with
# a known number of cycles per flight.
# =====================================================
print("\n[3] Miner's Rule, Cumulative Damage")

# Flight spectrum: [stress level (Pa), cycles per flight]
spectrum = [
    ("Taxi/ground",     150e6,  500),   # low stress, many cycles
    ("Cruise",          400e6,   80),   # moderate stress
    ("Maneuver/launch", 750e6,   20),   # high stress, few cycles
]

# Compute fatigue life for each level
cycle_limits = []
cycle_counts = []
print(f"\n  Flight spectrum:")
print(f"  {'Level':20s}  {'σ_a(MPa)':>10s}  {'n/flight':>10s}  {'N_f':>14s}  {'n/N_f':>10s}")
print(f"  {'-'*68}")

for level, sigma_a, n_per_flight in spectrum:
    r_fat = anvil.R.fatigue_life_basquin(
        sigma_a=sigma_a, sigma_f_prime=sigma_f_prime, b_exponent=b_exp
    )
    N_f = _v(r_fat["N_cycles"])
    cycle_limits.append(N_f)
    cycle_counts.append(float(n_per_flight))
    ratio = n_per_flight / N_f
    print(f"  {level:20s}  {sigma_a/1e6:>10.0f}  {n_per_flight:>10d}  {N_f:>14.2e}  {ratio:>10.4e}")

# Compute damage per flight
damage_per_flight = sum(n / N for n, N in zip(cycle_counts, cycle_limits))
flights_to_failure = 1.0 / damage_per_flight

print(f"\n  Damage per flight: D = Σ(n/N) = {damage_per_flight:.6e}")
print(f"  Flights to failure (D = 1):  {flights_to_failure:.0f} flights")

# Full Miner's rule RSQ call
r_miner = anvil.R.miners_rule(
    cycle_counts=cycle_counts,
    cycle_limits=cycle_limits,
)
D_total = _v(r_miner["damage_index"])
failed  = bool(r_miner["failed"])
remain  = _v(r_miner["remaining_life_fraction"])

print(f"\n  After 1 flight:")
print(f"    Damage index D = {D_total:.6f}  ({'FAILED' if failed else 'OK'})")
print(f"    Remaining life fraction: {remain:.6f}")

# After 100 flights
cycle_counts_100 = [n * 100 for n in cycle_counts]
r_miner_100 = anvil.R.miners_rule(
    cycle_counts=cycle_counts_100,
    cycle_limits=cycle_limits,
)
D_100 = _v(r_miner_100["damage_index"])
print(f"\n  After 100 flights: D = {D_100:.4f}  ({'FAILED' if bool(r_miner_100['failed']) else 'OK'})")
print(f"  Flights to inspection limit (D=0.5): {0.5/damage_per_flight:.0f} flights")


# =====================================================
# 4. Fracture Toughness Check
#
# NDI detected a surface semi-circular crack of radius a.
# Check if the stress intensity factor KI exceeds KIc.
# =====================================================
print("\n[4] Fracture Toughness Check (LEFM)")

a_crack_ndi = 0.0008   # m, 0.8 mm crack from NDI (near detection limit)

print(f"\n  Crack size from NDI: a = {a_crack_ndi*1000:.1f} mm")
print(f"  KIc = {KIc/1e6:.0f} MPa√m")
print(f"\n  {'σ (MPa)':>10s}  {'KI (MPa√m)':>12s}  {'SF_frac':>10s}  {'Fail?':>8s}")
print(f"  {'-'*44}")

for sigma in [300e6, 500e6, 750e6, 1000e6, 1400e6]:
    r_frac = anvil.R.fracture_toughness_check(
        sigma=sigma,
        a_crack=a_crack_ndi,
        KIc=KIc,
        F_geometry=1.12,   # free-surface correction for semi-circular crack
    )
    KI    = _v(r_frac["KI"])
    sf_fr = _v(r_frac["safety_factor"])
    fail  = bool(r_frac["failed"])
    print(f"  {sigma/1e6:>10.0f}  {KI/1e6:>12.2f}  {sf_fr:>10.2f}  {'YES' if fail else 'no':>8s}")

# Critical crack size at operating stress
r_frac_op = anvil.R.fracture_toughness_check(
    sigma=design_stress, a_crack=a_crack_ndi, KIc=KIc
)
KI_op = _v(r_frac_op["KI"])
a_critical = (KIc / (1.12 * design_stress * np.sqrt(np.pi)))**2
print(f"\n  At operating stress {design_stress/1e6:.0f} MPa:")
print(f"    KI = {KI_op/1e6:.2f} MPa√m  (KIc = {KIc/1e6:.0f})")
print(f"    Critical crack size: a_crit = {a_critical*1000:.2f} mm")
print(f"    Safety factor: {_v(r_frac_op['safety_factor']):.2f}")


# =====================================================
# 5. Thermal Expansion Stress
# =====================================================
print("\n[5] Thermal Expansion Stress, cryogenic refueling")

# Temperature change during LOX propellant loading
E_al    = 72e9     # Pa, aluminum alloy
alpha_al = 23e-6   # 1/K, thermal expansion coefficient (aluminum)
dT_cry  = -180     # K, cryogenic cooling (ambient → -180°C delta)

r_th = anvil.R.thermal_expansion_stress(E=E_al, alpha_thermal=alpha_al, dT=dT_cry)
sigma_th = abs(_v(r_th["sigma_thermal"]))

print(f"\n  Aluminum structure (E={E_al/1e9:.0f} GPa, α={alpha_al*1e6:.0f} µ/K)")
print(f"  Cooling ΔT = {dT_cry} K (cryogenic LOX loading)")
print(f"  Thermal stress: σ_th = {sigma_th/1e6:.0f} MPa")

sigma_y_al = 503e6  # Pa, Al 7075-T6
r_sf_th = anvil.R.safety_factor(allowable_stress=sigma_y_al, applied_stress=sigma_th)
print(f"  Safety factor (Al 7075-T6, σ_y={sigma_y_al/1e6:.0f} MPa): {_v(r_sf_th['safety_factor']):.2f}")


# =====================================================
# 6. Composite Laminate Stiffness (rule of mixtures)
# =====================================================
print("\n[6] Composite Laminate Stiffness (CFRP)")

# Carbon fiber / epoxy composite (typical UD ply)
Ef     = 230e9   # Pa, fiber modulus (carbon)
Em     = 3.5e9   # Pa, matrix modulus (epoxy)
Gf     = 90e9    # Pa, fiber shear modulus
Gm     = 1.3e9   # Pa, matrix shear modulus
nu_f   = 0.20    #, fiber Poisson's ratio
nu_m   = 0.35    #, matrix Poisson's ratio
Vf     = 0.60    #, fiber volume fraction (60%)

r_comp = anvil.R.composite_laminate_stiffness(
    Ef=Ef, Em=Em, Gf=Gf, Gm=Gm, nu_f=nu_f, nu_m=nu_m, Vf=Vf
)

E1  = _v(r_comp["E1"])
E2  = _v(r_comp["E2"])
G12 = _v(r_comp["G12"])
nu12 = _v(r_comp["nu12"])

print(f"\n  CFRP UD ply (Vf = {Vf*100:.0f}%):")
print(f"    E1   = {E1/1e9:.1f} GPa  (axial, fiber dominated)")
print(f"    E2   = {E2/1e9:.2f} GPa  (transverse, matrix dominated)")
print(f"    G12  = {G12/1e9:.2f} GPa  (shear)")
print(f"    ν12  = {nu12:.4f}")
print(f"    E1/E2 ratio = {E1/E2:.1f}  (strong anisotropy)")

# Sweep Vf
comp_sys = System("composite_design")
comp_sys.add("Ef",   Ef);   comp_sys.add("Em",   Em)
comp_sys.add("Gf",   Gf);   comp_sys.add("Gm",   Gm)
comp_sys.add("nu_f", nu_f); comp_sys.add("nu_m", nu_m)
comp_sys.add("Vf",   Vf)
comp_sys.use("composite_laminate_stiffness")

print(f"\n  Stiffness vs fiber volume fraction:")
sweep_comp = comp_sys.sweep("Vf", np.linspace(0.35, 0.70, 7))
sweep_comp.summary(outputs=["E1", "E2", "G12", "nu12"])


# =====================================================
# 7. Full structural assessment system
# =====================================================
print("\n[7] Integrated structural life system")

struct_sys = System("shaft_life_assessment")
struct_sys.add("sigma_a",       design_stress,  "Pa")
struct_sys.add("sigma_f_prime", sigma_f_prime,  "Pa")
struct_sys.add("b_exponent",    b_exp)
struct_sys.add("allowable_stress", sigma_y,     "Pa")
struct_sys.add("applied_stress",   design_stress, "Pa")
struct_sys.add("sigma",            design_stress, "Pa")
struct_sys.add("a_crack",          a_crack_ndi)
struct_sys.add("KIc",              KIc)
struct_sys.add("F_geometry",       1.12)
struct_sys.use("fatigue_life_basquin")
struct_sys.use("safety_factor")


def fracture_check(sigma, a_crack, KIc, F_geometry):
    """fracture_toughness_check with its safety_factor renamed so it doesn't
    collide with the static safety_factor RSQ's output in the same system."""
    r = dict(anvil.R.fracture_toughness_check(
        sigma=sigma, a_crack=a_crack, KIc=KIc, F_geometry=F_geometry))
    r["SF_fracture"] = r.pop("safety_factor")
    return r


struct_sys.use(fracture_check)

r_final = struct_sys.solve_forward()
print(f"\n  Integrated assessment at σ={design_stress/1e6:.0f} MPa:")
print(f"    Fatigue life:     {_v(r_final['N_cycles']):.2e} cycles")
print(f"    Static SF:        {_v(r_final['safety_factor']):.2f}")
print(f"    Fracture SF:      {_v(r_final['SF_fracture']):.2f}")
print(f"    Fracture KI/KIc:  {_v(r_final['KI'])/_v(r_final['KIc']):.3f}"
      f"  ({'CRITICAL' if bool(r_final['failed']) else 'safe'})")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 14: Materials, Fatigue, Fracture, Composites
============================================================

  Material: 300M Steel
    E       = 207 GPa
    σ_y     = 1700 MPa
    σ_UTS   = 1950 MPa
    σ_f'    = 2100 MPa  (Basquin coeff)
    b       = -0.07  (Basquin exponent)
    KIc     = 70 MPa√m

[1] Safety Factor, Nominal Operating Stress

  σ_applied = 750 MPa,  σ_allowable = 1700 MPa
  Safety factor:   SF = 2.267  (PASS)
  Margin of safety: MoS = 1.267  (126.7%)

----------------------------------------------------------------------
  safety_check -- sweep over applied_stress
----------------------------------------------------------------------
  applied_stress safety_factormargin_of_safety          pass
            [Pa]                                          
  --------------------------------------------------------
           5e+08           3.4           2.4             1
         7.5e+08         2.267         1.267             1
           1e+09           1.7           0.7             1
        1.25e+09          1.36          0.36             1
         1.5e+09         1.133        0.1333             1
        1.75e+09        0.9714      -0.02857             0
           2e+09          0.85         -0.15             0
----------------------------------------------------------------------

[2] Fatigue Life, Basquin's Law
... (110 more lines)
```


## Example 15: Aerodynamic Performance Analysis

`examples/ex15_aero_performance.py`

```python
import sys, os

# Windows consoles default to cp1252; this output uses Greek symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np


import anvil
from anvil import Q, System
from anvil import in_    # `in` is a Python keyword; Anvil provides `in_`

print("=" * 60)
print("  Example 15: Aerodynamic Performance Analysis")
print("=" * 60)


# =====================================================
# Aircraft parameters (narrow-body jet transport)
# =====================================================
W_MTOW     = 750e3    # N , max takeoff weight (≈76 t)
W_OEW      = 420e3    # N , operating empty weight
S_ref      = 122.4    # m^2, wing reference area
AR         = 9.5      #, aspect ratio
sweep_deg  = 25.0     # deg, quarter-chord sweep
taper      = 0.25     #, taper ratio
CD0        = 0.025    #, zero-lift drag coefficient
CLmax      = 2.8      #, max lift coefficient (flaps extended)
TSFC       = 1.8e-5   # kg/N/s, thrust specific fuel consumption (SI)

print(f"\n  Aircraft parameters:")
print(f"    MTOW   = {W_MTOW/1e3:.0f} kN ({W_MTOW/9.80665/1000:.0f} t)")
print(f"    S_ref  = {S_ref} m²,  AR = {AR},  Sweep = {sweep_deg}°")
print(f"    CD0    = {CD0},  CLmax = {CLmax}")
print(f"    TSFC   = {TSFC:.2e} kg/N/s")

# Demonstrate in_ alias (inches as a unit)
wing_chord = 5.5 * in_    # 5.5 inches (model scale test)
print(f"\n  Model scale test chord: {5.5} in = {wing_chord.to('m')}")
print(f"  (in_ alias used since 'in' is a Python keyword)")


# =====================================================
# 1. ISA Standard Atmosphere
# =====================================================
print("\n[1] ISA Standard Atmosphere")

altitudes = [0, 5000, 10000, 11000, 15000, 20000]

print(f"\n  {'h (m)':>8s}  {'T (K)':>8s}  {'P (kPa)':>10s}  {'ρ (kg/m³)':>12s}  {'a (m/s)':>10s}")
print(f"  {'-'*54}")

for h in altitudes:
    r_isa = anvil.R.isa_atmosphere(h=h)
    def _v(x): return float(x.si) if hasattr(x, "si") else float(x)
    T   = _v(r_isa["T_atm"])
    P   = _v(r_isa["P_atm"])
    rho = _v(r_isa["rho_atm"])
    a   = _v(r_isa["a_atm"])
    print(f"  {h:>8.0f}  {T:>8.2f}  {P/1000:>10.3f}  {rho:>12.4f}  {a:>10.2f}")


# =====================================================
# 2. Thin Airfoil Theory + Prandtl-Glauert Correction
# =====================================================
print("\n[2] Thin Airfoil Lift Coefficient (with Prandtl-Glauert)")

angles = [-4, 0, 2, 4, 6, 8, 10]
machs  = [0.0, 0.3, 0.6, 0.75]

print(f"\n  CL vs angle-of-attack (α_L0 = -2°):")
print(f"  {'α (°)':>8s}", end="")
for M in machs:
    print(f"  {'M='+str(M):>10s}", end="")
print()
print(f"  {'-'*48}")

for alpha in angles:
    print(f"  {alpha:>8.1f}", end="")
    for M in machs:
        r_cl = anvil.R.thin_airfoil_cl(alpha_deg=float(alpha), alpha_L0_deg=-2.0, M=M)
        CL = _v(r_cl["CL"])
        print(f"  {CL:>10.4f}", end="")
    print()

print(f"\n  CL_alpha (2π/rad × P-G) at M=0.6:")
r_cla = anvil.R.thin_airfoil_cl(alpha_deg=5.0, alpha_L0_deg=-2.0, M=0.6)
print(f"    CL_alpha = {_v(r_cla['CL_alpha']):.4f} per degree  ({_v(r_cla['CL_alpha'])*180/np.pi:.4f}/rad)")


# =====================================================
# 3. Oswald Efficiency + Drag Polar
# =====================================================
print("\n[3] Drag Polar and L/D at Cruise")

r_oswald = anvil.R.oswald_efficiency(AR=AR, sweep_deg=sweep_deg, taper=taper)
e_oswald = _v(r_oswald["e_oswald"])
print(f"\n  Oswald efficiency: e = {e_oswald:.4f}  (AR={AR}, sweep={sweep_deg}°)")

CL_cruise  = 0.52   # typical cruise CL

r_polar = anvil.R.drag_polar(CL=CL_cruise, CD0=CD0, AR=AR, e=e_oswald)
CD_cr   = _v(r_polar["CD"])
CDi_cr  = _v(r_polar["CDi"])
LoD_cr  = _v(r_polar["LoD"])

print(f"\n  At CL = {CL_cruise} (cruise):")
print(f"    CD0  = {CD0:.4f}  (parasite drag)")
print(f"    CDi  = {CDi_cr:.4f}  (induced drag)")
print(f"    CD   = {CD_cr:.4f}  (total)")
print(f"    L/D  = {LoD_cr:.2f}  (lift-to-drag)")

# Sweep CL to find L/D max
polar_sys = System("wing_polar")
polar_sys.add("CL",  0.5)
polar_sys.add("CD0", CD0)
polar_sys.add("AR",  AR)
polar_sys.add("e",   e_oswald)
polar_sys.use("drag_polar")

print(f"\n  L/D vs CL (drag polar sweep):")
sweep_polar = polar_sys.sweep("CL", np.linspace(0.2, 1.2, 9))
sweep_polar.summary(outputs=["CDi", "CD", "LoD"])

# Find optimum CL
LoD_vals = [_v(sweep_polar["LoD"][i]) if hasattr(sweep_polar["LoD"][i], "si")
            else float(sweep_polar["LoD"][i])
            for i in range(len(sweep_polar["LoD"]))]
CL_vals  = np.linspace(0.2, 1.2, 9)
idx_opt  = np.argmax(LoD_vals)
print(f"\n  Optimal CL = {CL_vals[idx_opt]:.2f}  (L/D_max = {LoD_vals[idx_opt]:.2f})")
print(f"  Analytical: CL_opt = sqrt(π·e·AR·CD0) = {np.sqrt(np.pi*e_oswald*AR*CD0):.3f}")


# =====================================================
# 4. Stall Speed at Different Altitudes
# =====================================================
print("\n[4] Stall Speed vs Altitude")

print(f"\n  {'Alt (m)':>8s}  {'ρ (kg/m³)':>12s}  {'V_stall (m/s)':>14s}  {'V_stall (kt)':>14s}")
print(f"  {'-'*52}")

for h in [0, 2000, 5000, 8000, 10000]:
    r_isa = anvil.R.isa_atmosphere(h=h)
    rho   = _v(r_isa["rho_atm"])
    r_stall = anvil.R.stall_speed(W=W_MTOW, rho=rho, S_ref=S_ref, CLmax=CLmax)
    Vs = _v(r_stall["V_stall"])
    Vs_kt = Vs / 0.5144    # m/s → knots
    print(f"  {h:>8.0f}  {rho:>12.4f}  {Vs:>14.1f}  {Vs_kt:>14.1f}")


# =====================================================
# 5. Induced Drag at Different Lift Coefficients
# =====================================================
print("\n[5] Induced Drag RSQ")

CDi_sys = System("induced_drag")
CDi_sys.add("CL", 0.52)
CDi_sys.add("AR", AR)
CDi_sys.add("e",  e_oswald)
CDi_sys.use("induced_drag")

r_cdi = CDi_sys.solve_forward()
print(f"\n  CL={0.52}, AR={AR}, e={e_oswald:.4f}:")
print(f"    CDi = {_v(r_cdi['CDi']):.5f}")

sweep_cdi = CDi_sys.sweep("CL", np.linspace(0.1, 1.2, 8))
sweep_cdi.summary(outputs=["CDi"])


# =====================================================
# 6. Breguet Range, cruise altitude trade study
# =====================================================
print("\n[6] Breguet Range vs Cruise Altitude")

# Fuel weight = MTOW - OEW (fully loaded)
W_fuel = W_MTOW - W_OEW

print(f"\n  Fuel weight: {W_fuel/1e3:.0f} kN  ({W_fuel/9.80665/1000:.0f} t)")
print(f"  TSFC = {TSFC:.2e} kg/N/s = {TSFC*9.80665*3600:.4f} /hr")

print(f"\n  Breguet range at different cruise altitudes:")
print(f"  {'Alt (m)':>8s}  {'TAS (m/s)':>10s}  {'Mach':>6s}  {'ρ':>10s}  {'L/D':>6s}  {'Range (km)':>12s}")
print(f"  {'-'*60}")

for h_cruise in [7000, 9000, 10668, 12000]:    # FL230, FL295, FL350 (36kft), FL394
    r_isa  = anvil.R.isa_atmosphere(h=h_cruise)
    rho    = _v(r_isa["rho_atm"])
    a_spd  = _v(r_isa["a_atm"])

    # Compute cruise Mach from CL = W/(0.5*rho*V^2*S)
    V_cruise = np.sqrt(W_MTOW / (0.5 * rho * S_ref * CL_cruise))
    M_cruise = V_cruise / a_spd

    # L/D at this condition
    r_pol = anvil.R.drag_polar(CL=CL_cruise, CD0=CD0, AR=AR, e=e_oswald)
    LoD   = _v(r_pol["LoD"])

    # Breguet range
    r_bq = anvil.R.range_breguet(
        V=V_cruise,
        TSFC=TSFC,
        LoD=LoD,
        W_initial=W_MTOW,
        W_final=W_OEW,
    )
    range_km = _v(r_bq["range_km"])

    print(f"  {h_cruise:>8.0f}  {V_cruise:>10.1f}  {M_cruise:>6.3f}  {rho:>10.4f}  {LoD:>6.2f}  {range_km:>12.0f}")


# =====================================================
# 7. Integrated aircraft performance System
# =====================================================
print("\n[7] Integrated aircraft performance System")

acft = System("aircraft_performance")
acft.add("h_cruise",   10668,   "m",      desc="Cruise altitude (FL350)")
acft.add("W_initial",  W_MTOW,  "N",      desc="Initial weight (MTOW)")
acft.add("W_final",    W_OEW,   "N",      desc="Final weight (OEW)")
acft.add("S_ref",      S_ref,   "m^2",    desc="Wing reference area")
acft.add("AR",         AR,                desc="Aspect ratio")
acft.add("CD0",        CD0,               desc="Zero-lift drag coefficient")
acft.add("CLmax",      CLmax,             desc="Max lift coefficient (flaps)")
acft.add("TSFC",       TSFC,             desc="Thrust specific fuel consumption")
acft.add("sweep_deg",  sweep_deg,         desc="Wing quarter-chord sweep")
acft.add("taper",      taper,             desc="Wing taper ratio")
acft.add("CL_cruise",  CL_cruise,         desc="Cruise lift coefficient")
acft.add("e_base",     0.85,              desc="Base Oswald efficiency (fallback)")

def isa_and_cruise(h_cruise):
    r = anvil.R.isa_atmosphere(h=h_cruise)
    def v(x): return float(x.si) if hasattr(x, "si") else float(x)
    return {"rho_cr": Q(v(r["rho_atm"]), "kg/m^3"),
            "a_cr":   Q(v(r["a_atm"]),   "m/s"),
            "T_cr":   Q(v(r["T_atm"]),   "K"),
            "P_cr":   Q(v(r["P_atm"]),   "Pa")}

def cruise_speed_and_mach(W_initial, S_ref, CL_cruise, rho_cr, a_cr):
    V = float((W_initial / (0.5 * float(rho_cr.si if hasattr(rho_cr, 'si') else rho_cr)
                             * float(S_ref.si if hasattr(S_ref, 'si') else S_ref)
                             * (CL_cruise.si if hasattr(CL_cruise, 'si') else CL_cruise)))**0.5)
    a  = float(a_cr.si if hasattr(a_cr, 'si') else a_cr)
    return {"V_cr": Q(V, "m/s"), "M_cr": V / a}

def polar_and_range(CL_cruise, CD0, AR, e_base, V_cr, TSFC, W_initial, W_final):
    CL = float(CL_cruise.si if hasattr(CL_cruise, 'si') else CL_cruise)
    e  = float(e_base.si if hasattr(e_base, 'si') else e_base)
    r  = anvil.R.drag_polar(CL=CL, CD0=float(CD0.si if hasattr(CD0, 'si') else CD0),
                              AR=float(AR.si if hasattr(AR, 'si') else AR), e=e)
    def v(x): return float(x.si) if hasattr(x, "si") else float(x)
    LoD = v(r["LoD"])
    V   = v(V_cr)
    tsfc = v(TSFC)
    Wi   = v(W_initial)
    Wf   = v(W_final)
    rng_r = anvil.R.range_breguet(V=V, TSFC=tsfc, LoD=LoD, W_initial=Wi, W_final=Wf)
    return {"LoD_cr": LoD, "CD_cr": v(r["CD"]), "CDi_cr": v(r["CDi"]),
            "range_km": Q(v(rng_r["range_km"]), "km")}

acft.use(isa_and_cruise)
acft.use(cruise_speed_and_mach)
acft.use(polar_and_range)

r_acft = acft.solve_forward()
def v(x): return float(x.si) if hasattr(x, "si") else float(x)
print(f"\n  Cruise performance summary (FL350 / {10668} m):")
print(f"    V_cruise = {v(r_acft['V_cr']):.1f} m/s  (M = {v(r_acft['M_cr']):.3f})")
print(f"    L/D      = {v(r_acft['LoD_cr']):.2f}")
print(f"    Range    = {v(r_acft['range_km']):.0f} km")

# Sweep altitude
print(f"\n  Range vs cruise altitude:")
sweep_alt = acft.sweep("h_cruise", np.array([7000, 8000, 9000, 10000, 11000, 12000, 13000]))
sweep_alt.summary(outputs=["T_cr", "rho_cr", "M_cr", "LoD_cr", "range_km"])

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 15: Aerodynamic Performance Analysis
============================================================

  Aircraft parameters:
    MTOW   = 750 kN (76 t)
    S_ref  = 122.4 m²,  AR = 9.5,  Sweep = 25.0°
    CD0    = 0.025,  CLmax = 2.8
    TSFC   = 1.80e-05 kg/N/s

  Model scale test chord: 5.5 in = 0.139700 m
  (in_ alias used since 'in' is a Python keyword)

[1] ISA Standard Atmosphere

     h (m)     T (K)     P (kPa)     ρ (kg/m³)     a (m/s)
  ------------------------------------------------------
         0    288.15     101.325        1.2250      340.30
      5000    255.65      54.020        0.7361      320.53
     10000    223.15      26.437        0.4127      299.47
     11000    216.65      22.633        0.3639      295.07
     15000    216.65      12.045        0.1937      295.07
     20000    216.65       5.475        0.0880      295.07

[2] Thin Airfoil Lift Coefficient (with Prandtl-Glauert)

  CL vs angle-of-attack (α_L0 = -2°):
     α (°)       M=0.0       M=0.3       M=0.6      M=0.75
  ------------------------------------------------
      -4.0     -0.2193     -0.2299     -0.2742     -0.3071
       0.0      0.2193      0.2299      0.2742      0.3071
       2.0      0.4386      0.4598      0.5483      0.6142
       4.0      0.6580      0.6897      0.8225      0.9213
       6.0      0.8773      0.9197      1.0966      1.2285
... (109 more lines)
```


## Example 16: Global Optimization and System.optimize()

`examples/ex16_optimization.py`

```python
import sys, os
import numpy as np

import anvil
from anvil import solvers, Q

print("=" * 60)
print("  Example 16: Optimization")
print("=" * 60)


# --------------------------------------------------------------
# Part 1: minimize_global, direct function optimization
# --------------------------------------------------------------
print("\n[1] Direct global optimization: Himmelblau's function")
print("    f(x,y) = (x²+y-11)² + (x+y²-7)²  has 4 global minima at f=0")

def himmelblau(x):
    return (x[0]**2 + x[1] - 11)**2 + (x[0] + x[1]**2 - 7)**2

bounds = [(-5, 5), (-5, 5)]

for method in ["differential_evolution", "dual_annealing", "shgo", "basinhopping"]:
    r = solvers.minimize_global(himmelblau, bounds, method=method, seed=0)
    status = "OK" if r["fun"] < 1e-6 else "MISSED"
    print(f"  {method:28s}  f={r['fun']:.2e}  x=[{r['x'][0]:+.4f}, {r['x'][1]:+.4f}]  [{status}]")

# --------------------------------------------------------------
# Part 2: System.optimize(), nozzle thrust maximization
# --------------------------------------------------------------
print("\n[2] System.optimize(): maximize nozzle thrust")
print("    Design variables: A_throat, A_exit")
print("    Fixed: chamber conditions, ambient pressure")

nozzle = anvil.S.rocket_nozzle.copy()

# Fix chamber conditions and ambient
nozzle.set(
    P0=8e6,       # 8 MPa
    T0=3200,      # K
    gamma=1.25,
    R_gas=400.0,  # J/kg/K
    P_amb=101325,
)

# Maximize thrust by sizing throat and exit
opt = nozzle.optimize(
    objective="thrust",
    design_vars={
        "A_throat": (0.002, 0.030),   # 20 to 300 cm²
        "A_exit":   (0.010, 0.300),   # 100 to 3000 cm²
    },
    minimize=False,
    method="differential_evolution",
    seed=42,
    maxiter=80,
    verbose=False,
)

print(f"\n  Status : {'CONVERGED' if opt.success else 'NOT CONVERGED'}")
print(f"  Evals  : {opt.nfev}")
print(f"  Thrust : {opt.fun/1000:.2f} kN  ({opt.fun:.0f} N)")
print(f"  A_throat: {opt.x['A_throat']*1e4:.1f} cm²")
print(f"  A_exit  : {opt.x['A_exit']*1e4:.1f} cm²")
print(f"  Area ratio: {opt.x['A_exit'] / opt.x['A_throat']:.1f}")

# Access other quantities from the optimal result
print(f"\n  Other results at optimum:")
print(f"    Isp    : {float(opt['Isp'].value):.1f} s")
print(f"    M_exit : {float(opt['M_exit'].value):.2f}")
print(f"    mdot   : {float(opt['mdot'].value):.3f} kg/s")
print(f"    V_exit : {opt['V_exit'].to('km/s')}")

# --------------------------------------------------------------
# Part 3: Maximize Isp (efficiency), different objective
# --------------------------------------------------------------
print("\n[3] Same system, different objective: maximize Isp")

opt_isp = nozzle.optimize(
    objective="Isp",
    design_vars={
        "A_throat": (0.002, 0.030),
        "A_exit":   (0.010, 0.300),
    },
    minimize=False,
    method="differential_evolution",
    seed=42,
    maxiter=80,
    verbose=False,
)

print(f"  Isp    : {opt_isp.fun:.1f} s")
print(f"  Thrust : {float(opt_isp['thrust'].value)/1000:.2f} kN")
print(f"  A_throat: {opt_isp.x['A_throat']*1e4:.1f} cm²")
print(f"  A_exit  : {opt_isp.x['A_exit']*1e4:.1f} cm²  (-> area ratio {opt_isp.x['A_exit']/opt_isp.x['A_throat']:.1f})")
print("  (Higher Isp favours large expansion ratio; thrust trades off mdot vs Ve)")

# --------------------------------------------------------------
# Part 4: Custom system, optimize a heat exchanger NTU
# --------------------------------------------------------------
print("\n[4] Custom system: optimal NTU for heat exchanger effectiveness")

hx = anvil.system("hx_opt")
hx.add("NTU",    2.0)    # number of transfer units
hx.add("Cr",     0.5)    # capacity rate ratio Cmin/Cmax
hx.add("C_min",  500.0, "W/K")
hx.add("T_h_in", 90.0,  "K")   # hot inlet (relative, used for Q calc)
hx.add("T_c_in", 20.0,  "K")   # cold inlet

@anvil.relation
def hx_eff_ntu(NTU, Cr):
    eps = (1 - np.exp(-NTU * (1 - Cr))) / (1 - Cr * np.exp(-NTU * (1 - Cr)))
    return {"effectiveness": eps}

@anvil.relation
def hx_duty(effectiveness, C_min, T_h_in, T_c_in):
    Q_max = C_min * (T_h_in - T_c_in)
    return {"Q_duty": effectiveness * Q_max}

hx.use(hx_eff_ntu)
hx.use(hx_duty)

# Maximize effectiveness by tuning NTU (proxy for heat exchanger size/cost)
opt_hx = hx.optimize(
    objective="effectiveness",
    design_vars={"NTU": (0.1, 10.0), "Cr": (0.1, 1.0)},
    minimize=False,
    method="L-BFGS-B",     # gradient-based: smooth landscape
    maxiter=200,
)

print(f"  Best effectiveness : {opt_hx.fun:.4f}  (max possible = 1.0)")
print(f"  Optimal NTU        : {opt_hx.x['NTU']:.3f}")
print(f"  Optimal Cr         : {opt_hx.x['Cr']:.3f}")
print(f"  Heat duty          : {float(opt_hx['Q_duty'].value):.0f} W")

# --------------------------------------------------------------
# Part 5: OptimizeResult API summary
# --------------------------------------------------------------
print("\n[5] OptimizeResult API")
print(f"  opt.x         = {dict(opt.x)}")
print(f"  opt.fun       = {opt.fun:.4g}")
print(f"  opt.success   = {opt.success}")
print(f"  opt.nfev      = {opt.nfev}  (system solves)")
print(f"  opt.nit       = {opt.nit}  (optimizer iterations)")
print(f"  opt.message   = {opt.message!r}")
print(f"  opt['Isp']    = {opt['Isp']}  (subscript -> Quantity at optimum)")
print(f"  'thrust' in opt = {'thrust' in opt}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 16: Optimization
============================================================

[1] Direct global optimization: Himmelblau's function
    f(x,y) = (x²+y-11)² + (x+y²-7)²  has 4 global minima at f=0
  differential_evolution        f=1.34e-29  x=[+3.5844, -1.8481]  [OK]
  dual_annealing                f=6.36e-14  x=[+3.0000, +2.0000]  [OK]
  shgo                          f=1.01e-08  x=[+3.0000, +2.0000]  [OK]
  basinhopping                  f=6.12e-18  x=[+3.0000, +2.0000]  [OK]

[2] System.optimize(): maximize nozzle thrust
    Design variables: A_throat, A_exit
    Fixed: chamber conditions, ambient pressure

  Status : CONVERGED
  Evals  : 948
  Thrust : 381.22 kN  (381219 N)
  A_throat: 300.0 cm²
  A_exit  : 2695.2 cm²
  Area ratio: 9.0

  Other results at optimum:
    Isp    : 278.5 s
    M_exit : 3.34
    mdot   : 139.597 kg/s
    V_exit : 2.7309 km/s (V_exit)

[3] Same system, different objective: maximize Isp
  Isp    : 278.5 s
  Thrust : 294.53 kN
  A_throat: 231.8 cm²
  A_exit  : 2082.3 cm²  (-> area ratio 9.0)
  (Higher Isp favours large expansion ratio; thrust trades off mdot vs Ve)
... (26 more lines)
```


## Example 17: Rayleigh Flow via Project Registry

`examples/ex17_rayleigh_flow.py`

```python
import sys, os
import numpy as np


import anvil
from anvil import Q, solvers

print("=" * 60)
print("  Example 17: Rayleigh Flow via Project Registry")
print("=" * 60)


# =====================================================
# 1. Define the RSQs as plain Python functions
# =====================================================

def rayleigh_ratios(M, gamma=1.4):
    """Rayleigh flow ratios at Mach M referenced to sonic (★) conditions."""
    g = float(gamma); M = float(M)
    gp1 = g + 1
    denom = 1 + g * M**2
    P_Pstar     = gp1 / denom
    T_Tstar     = (gp1 * M / denom)**2
    rho_rhostar = denom / (gp1 * M**2)
    t0          = 1 + (g - 1) / 2 * M**2
    T0_T0star   = 2 * gp1 * M**2 * t0 / denom**2
    P0_P0star   = P_Pstar * (2 * t0 / gp1) ** (g / (g - 1))
    return {
        "T0_T0star":   T0_T0star,
        "T_Tstar":     T_Tstar,
        "P_Pstar":     P_Pstar,
        "P0_P0star":   P0_P0star,
        "rho_rhostar": rho_rhostar,
        "V_Vstar":     1.0 / rho_rhostar,
    }


def rayleigh_heat(M1, T01, P1, q_heat, cp, gamma=1.4):
    """
    Rayleigh flow with heat addition in a constant-area duct.
    q_heat [J/kg]: >0 heating, <0 cooling.
    Raises ValueError if heat addition would choke the flow.
    """
    g      = float(gamma); M1 = float(M1)
    T01    = float(getattr(T01,    "si", T01))
    P1     = float(getattr(P1,     "si", P1))
    q_heat = float(getattr(q_heat, "si", q_heat))
    cp     = float(getattr(cp,     "si", cp))
    gp1 = g + 1

    def _T0r(M):
        d = 1 + g * M**2
        return 2 * gp1 * M**2 * (1 + (g - 1) / 2 * M**2) / d**2
    def _Pr(M):  return gp1 / (1 + g * M**2)
    def _Tr(M):  return (gp1 * M / (1 + g * M**2))**2

    r1     = _T0r(M1)
    T02    = T01 + q_heat / cp
    T0star = T01 / r1
    r2     = T02 / T0star

    if r2 > 1.0:
        raise ValueError(
            f"Flow chokes: T02/T0* = {r2:.4f} > 1.0. "
            f"Max q_heat = {cp * (T0star - T01):.1f} J/kg"
        )

    bracket = (1.0001, 50.0) if M1 >= 1.0 else (0.001, 0.9999)
    M2  = solvers.find_root(lambda M: _T0r(M) - r2, bracket=bracket,
                            method="brent", tol=1e-12)
    P2  = P1  / _Pr(M1) * _Pr(M2)
    T1  = T01 / (1 + (g - 1) / 2 * M1**2)
    T2  = T1  / _Tr(M1) * _Tr(M2)
    P01 = P1  * (1 + (g - 1) / 2 * M1**2) ** (g / (g - 1))
    P02 = P2  * (1 + (g - 1) / 2 * M2**2) ** (g / (g - 1))
    return {
        "M2":        M2,
        "T02":       Q(T02, "K"),
        "T2":        Q(T2,  "K"),
        "P2":        Q(P2,  "Pa"),
        "P02":       Q(P02, "Pa"),
        "P01":       Q(P01, "Pa"),
        "P02_P01":   P02 / P01,
        "T0_T0star": r2,
    }


# =====================================================
# 2. Push to a project registry
# =====================================================

proj = anvil.project("rayleigh_study", path="./rayleigh_work")

proj.push(rayleigh_ratios,
          domain="aero.compressible",
          description="Rayleigh flow ratios at Mach M referenced to sonic conditions",
          tags=["rayleigh", "compressible", "heat_addition"])

proj.push(rayleigh_heat,
          domain="aero.compressible",
          description="Rayleigh flow exit conditions given inlet state + heat addition",
          tags=["rayleigh", "compressible", "heat_addition", "combustion"])

print("\n--- Project registry contents ---")
proj.list()


# =====================================================
# 3. Verify ratios at M=1 (all should equal 1.0)
# =====================================================

print("\n--- rayleigh_ratios at M=1.0 (all ratios = 1.0) ---")
r = proj.R.rayleigh_ratios(M=1.0)
for k, v in r.items():
    print(f"  {k:15s} = {v:.6f}")


# =====================================================
# 4. Build a System and solve
#    Inlet: M=0.3, T01=400 K, P1=200 kPa, q=300 kJ/kg (air)
# =====================================================

print("\n--- System solve: single heat addition ---")

duct = anvil.system("rayleigh_duct")
duct.add("M1",     0.3)
duct.add("T01",    400.0,   "K")
duct.add("P1",     200e3,   "Pa")
duct.add("q_heat", 300e3,   "J/kg")
duct.add("cp",     1005.0,  "J/kg/K")
duct.add("gamma",  1.4)
duct.use(proj.R.rayleigh_heat)

result = duct.solve_forward()
result.summary()


# =====================================================
# 5. Sweep heat addition from 0 to 80% of choke limit
# =====================================================

print("\n--- Sweep: q_heat from 0 to 80% of choke limit ---")

# Find choke limit for these inlet conditions
r_inlet = proj.R.rayleigh_ratios(M=0.3, gamma=1.4)
T0star  = 400.0 / r_inlet["T0_T0star"]
q_choke = 1005.0 * (T0star - 400.0)
print(f"  Choke limit: q_max = {q_choke/1e3:.1f} kJ/kg")

q_values = np.linspace(0, 0.80 * q_choke, 30)
sweep = duct.sweep("q_heat", q_values, skip_errors=True)
sweep.summary(outputs=["M2", "T02", "P2", "P02_P01"])


# =====================================================
# 6. Promote to global registry when satisfied
# =====================================================

# Uncomment when ready to make these globally available:
# proj.promote("rayleigh_ratios")
# proj.promote("rayleigh_heat")
# print("\nPromoted rayleigh_ratios and rayleigh_heat to global registry.")
# print("Now accessible as anvil.R.rayleigh_ratios / anvil.R.rayleigh_heat")
```

**Output:**

```
============================================================
  Example 17: Rayleigh Flow via Project Registry
============================================================
  Project 'rayleigh_study' opened  (rayleigh_work\.anvil\project_rayleigh_study.db)
  [rayleigh_study] Registered 'rayleigh_ratios' (R) in domain 'aero.compressible'.
  [rayleigh_study] Registered 'rayleigh_heat' (R) in domain 'aero.compressible'.

--- Project registry contents ---

  Project: rayleigh_study  (rayleigh_work)

  Relations (2):
    rayleigh_heat                   [aero.compressible]
      Rayleigh flow exit conditions given inlet state + heat addition
    rayleigh_ratios                 [aero.compressible]
      Rayleigh flow ratios at Mach M referenced to sonic conditions

  Total: 2 RSQs

--- rayleigh_ratios at M=1.0 (all ratios = 1.0) ---
  T0_T0star       = 1.000000
  T_Tstar         = 1.000000
  P_Pstar         = 1.000000
  P0_P0star       = 1.000000
  rho_rhostar     = 1.000000
  V_Vstar         = 1.000000

--- System solve: single heat addition ---

--------------------------------------------------------
  rayleigh_duct -- results
--------------------------------------------------------
  M1                        0.300000
  T01                       400.00 K
... (55 more lines)
```


## Example 18: POD and DMD Signal Decomposition

`examples/ex18_decomp.py`

```python
import sys, os
import numpy as np

import anvil
import anvil.decomp as decomp

print("=" * 60)
print("  Example 18: POD and DMD Decomposition")
print("=" * 60)

rng = np.random.default_rng(42)


# --------------------------------------------------------------
# Part 1: Synthetic 1D signal, known frequencies
# --------------------------------------------------------------
print("\n[1] Synthetic signal: 3 Hz + 11 Hz + noise")

dt   = 0.005          # 200 Hz sample rate
t    = np.arange(0, 8, dt)
N    = len(t)

# True signal: two sinusoids + broadband noise
x = (1.0 * np.sin(2*np.pi*3*t)
   + 0.4 * np.sin(2*np.pi*11*t + 0.7)
   + 0.08 * rng.standard_normal(N))

print(f"  Signal length: {N} samples  ({t[-1]:.1f} s at {1/dt:.0f} Hz)")

# --------------------------------------------------------------
# Part 2: Hankel embedding
# --------------------------------------------------------------
print("\n[2] Hankel embedding")

window = N // 4     # rule of thumb: N/4 to N/3
H = decomp.hankel(x, window=window)
print(f"  window = {window},  Hankel shape = {H.shape}  (rows x columns)")
print(f"  Each column: one {window}-sample snapshot")

# --------------------------------------------------------------
# Part 3: POD
# --------------------------------------------------------------
print("\n[3] POD, energy decomposition")

pod_r = decomp.pod(H)   # all modes first

print(f"  Total modes retained: {pod_r['rank']}")
print(f"  Singular values (top 6): {pod_r['singular_values'][:6].round(1)}")
print(f"  Energy per mode  (top 6): {(pod_r['energy_fractions'][:6]*100).round(2)} %")
print(f"  Cumulative energy (top 6): {(pod_r['cumulative_energy'][:6]*100).round(2)} %")

r_99   = decomp.pod_rank(pod_r, 0.99)
r_999  = decomp.pod_rank(pod_r, 0.999)
print(f"\n  Modes for 99.0% energy : {r_99}")
print(f"  Modes for 99.9% energy : {r_999}")

# --------------------------------------------------------------
# Part 4: POD reconstruction
# --------------------------------------------------------------
print("\n[4] POD reconstruction error vs rank")

for r in [2, 4, 6, 10, 20]:
    X_hat = decomp.pod_reconstruct(pod_r, r=r)
    err = np.linalg.norm(H - X_hat) / np.linalg.norm(H)
    # Recover 1D signal from first row of reconstruction
    x_hat = X_hat[0, :]
    print(f"  r={r:3d}  matrix error = {err:.4f}  "
          f"  cumE = {pod_r['cumulative_energy'][r-1]*100:.2f}%")

# --------------------------------------------------------------
# Part 5: DMD, frequency identification
# --------------------------------------------------------------
print("\n[5] DMD, frequency and growth rate identification")

dmd_r = decomp.dmd(H, dt=dt, r=12)

print(f"  DMD rank used : {len(dmd_r['eigenvalues'])}")
print(f"  {'Mode':>4}  {'|eval|':>8}  {'Freq (Hz)':>12}  {'Growth rate':>12}  {'|Amplitude|':>12}")
print(f"  {'-'*55}")

dom_idx = decomp.dmd_dominant(dmd_r, n=8, by="amplitude")
for i in dom_idx:
    lam  = dmd_r["eigenvalues"][i]
    freq = dmd_r["frequencies"][i]
    grow = dmd_r["growth_rates"][i]
    amp  = np.abs(dmd_r["amplitudes"][i])
    print(f"  {i:4d}  {abs(lam):8.5f}  {freq:+12.4f}  {grow:+12.4f}  {amp:12.4f}")

print("\n  Note: dominant frequencies should match +/-3 Hz and +/-11 Hz")

# --------------------------------------------------------------
# Part 6: DMD reconstruction
# --------------------------------------------------------------
print("\n[6] DMD reconstruction")

X_dmd = decomp.dmd_reconstruct(dmd_r, n_steps=H.shape[1])
dmd_err = np.linalg.norm(H - X_dmd) / np.linalg.norm(H)
print(f"  Reconstruction error (r=12): {dmd_err:.4f}")

# Future prediction: extend 20% beyond training data
n_future = H.shape[1] + int(0.2 * H.shape[1])
X_future = decomp.dmd_reconstruct(dmd_r, n_steps=n_future)
print(f"  Extended to {n_future} steps ({n_future*dt:.2f} s) for future prediction")
print(f"  (DMD extrapolates via eigenvalue powers, valid for stable modes)")

# --------------------------------------------------------------
# Part 7: Multi-dim snapshot matrix (simulated sensor array)
# --------------------------------------------------------------
print("\n[7] Multi-dimensional snapshot matrix: 64-sensor vibration array")

n_sensors   = 64
n_snapshots = 500
dt_vib      = 1e-3     # 1 kHz

# Simulated: mode 1 at 80 Hz decaying, mode 2 at 220 Hz growing slightly
t_vib = np.arange(n_snapshots) * dt_vib
locs  = np.linspace(0, 1, n_sensors)

mode1_space = np.sin(np.pi * locs)           # first bending mode
mode2_space = np.sin(2 * np.pi * locs)       # second bending mode

mode1_time = np.exp(-0.5*t_vib) * np.sin(2*np.pi*80*t_vib)
mode2_time = np.exp(0.3*t_vib)  * np.sin(2*np.pi*220*t_vib) * 0.3

X_vib = (np.outer(mode1_space, mode1_time)
        + np.outer(mode2_space, mode2_time)
        + 0.02 * rng.standard_normal((n_sensors, n_snapshots)))

print(f"  Snapshot matrix shape: {X_vib.shape}  (sensors x time)")

# POD on vibration data
pod_vib = decomp.pod(X_vib, r=6)
print(f"\n  POD energy (top 6 modes):")
for i in range(6):
    bar = "#" * int(pod_vib["energy_fractions"][i] * 50)
    print(f"    Mode {i+1}: {pod_vib['energy_fractions'][i]*100:6.2f}%  {bar}")

# DMD on vibration data
dmd_vib = decomp.dmd(X_vib, dt=dt_vib, r=6)
print(f"\n  DMD dominant frequencies (top 4 by amplitude):")
idx_vib = decomp.dmd_dominant(dmd_vib, n=4, by="amplitude")
for i in idx_vib:
    freq = abs(dmd_vib["frequencies"][i])
    grow = dmd_vib["growth_rates"][i]
    amp  = np.abs(dmd_vib["amplitudes"][i])
    stab = "DECAYING" if grow < -0.1 else ("GROWING" if grow > 0.1 else "neutral")
    print(f"    freq = {freq:7.1f} Hz   growth = {grow:+.2f}   amp = {amp:.2f}  [{stab}]")

print("\n  (Should identify ~80 Hz decaying + ~220 Hz growing modes)")

# POD projection: project last 50 snapshots onto training basis
coeff = decomp.pod_project(pod_vib, X_vib[:, -50:])
print(f"\n  pod_project(): projected last 50 snapshots -> coefficients shape {coeff.shape}")

# --------------------------------------------------------------
# Part 8: Viz (optional, skipped if no matplotlib)
# --------------------------------------------------------------
print("\n[8] Visualization (requires matplotlib)")
try:
    from anvil import viz
    viz.pod_energy(pod_r, show=False)
    viz.dmd_spectrum(dmd_r, show=False)
    print("  Figures created. Call plt.show() or save with fig.savefig().")
    print("  (Running headless, no display. Remove show=False for interactive use.)")
except ImportError:
    print("  matplotlib not installed, skipping plots.")
except Exception as e:
    print(f"  Viz skipped: {e}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 18: POD and DMD Decomposition
============================================================

[1] Synthetic signal: 3 Hz + 11 Hz + noise
  Signal length: 1600 samples  (8.0 s at 200 Hz)

[2] Hankel embedding
  window = 400,  Hankel shape = (400, 1201)  (rows x columns)
  Each column: one 400-sample snapshot

[3] POD, energy decomposition
  Total modes retained: 400
  Singular values (top 6): [345.  344.7 139.5 139.4   4.5   4.5]
  Energy per mode  (top 6): [4.254e+01 4.246e+01 6.950e+00 6.940e+00 1.000e-02 1.000e-02] %
  Cumulative energy (top 6): [42.54 85.   91.95 98.9  98.91 98.91] %

  Modes for 99.0% energy : 20
  Modes for 99.9% energy : 308

[4] POD reconstruction error vs rank
  r=  2  matrix error = 0.3873    cumE = 85.00%
  r=  4  matrix error = 0.1050    cumE = 98.90%
  r=  6  matrix error = 0.1043    cumE = 98.91%
  r= 10  matrix error = 0.1030    cumE = 98.94%
  r= 20  matrix error = 0.0999    cumE = 99.00%

[5] DMD, frequency and growth rate identification
  DMD rank used : 12
  Mode    |eval|     Freq (Hz)   Growth rate   |Amplitude|
  -------------------------------------------------------
     3   1.00001       +3.0003       +0.0013        9.9570
     4   1.00001       -3.0003       +0.0013        9.9570
     9   1.00003      +10.9994       +0.0052        3.8833
... (41 more lines)
```


## Example 19: Abel Transform and Inversion

`examples/ex19_abel.py`

```python
import sys, os
import numpy as np

import anvil
import anvil.decomp as decomp

print("=" * 60)
print("  Example 19: Abel Transform and Inversion")
print("=" * 60)


# ---------------------------------------------------------------
# Part 1: 1D validation -- Gaussian ring (analytic solution known)
# ---------------------------------------------------------------
print("\n[1] Forward Abel: Gaussian radial distribution -> projection")
print("    f(r) = exp(-r^2/sigma^2),  F(y) = sigma*sqrt(pi)*exp(-y^2/sigma^2)")

N = 300
dr = 0.05
r = np.arange(N) * dr
sigma = 3.0   # radial width in physical units

fr_true = np.exp(-(r / sigma) ** 2)
Fy_analytic = sigma * np.sqrt(np.pi) * np.exp(-(r / sigma) ** 2)

Fy_numerical = decomp.abel_forward(fr_true, dr=dr)

err_fwd = np.linalg.norm(Fy_numerical - Fy_analytic) / np.linalg.norm(Fy_analytic)
print(f"  Forward transform error vs analytic: {err_fwd:.2e}")

# ---------------------------------------------------------------
# Part 2: Inversion -- recover f(r) from F(y)
# ---------------------------------------------------------------
print("\n[2] Abel inversion: projection -> radial distribution")

fr_onion = decomp.abel_onion(Fy_numerical, dr=dr)
fr_3pt   = decomp.abel_three_point(Fy_numerical, dr=dr)

# Trim edge (last pixel often inaccurate due to boundary)
check = slice(1, N - 5)
err_onion = np.linalg.norm(fr_onion[check] - fr_true[check]) / np.linalg.norm(fr_true[check])
err_3pt   = np.linalg.norm(fr_3pt[check]   - fr_true[check]) / np.linalg.norm(fr_true[check])

print(f"  Onion peeling  error vs ground truth: {err_onion:.4f}")
print(f"  Three-point    error vs ground truth: {err_3pt:.4f}")
print(f"  Peak (onion)  : f[0] = {fr_onion[0]:.4f}  (true: {fr_true[0]:.4f})")
print(f"  Peak (3-point): f[0] = {fr_3pt[0]:.4f}  (true: {fr_true[0]:.4f})")

# ---------------------------------------------------------------
# Part 3: Hollow sphere / bright ring (harder test)
# ---------------------------------------------------------------
print("\n[3] Harder test: hollow sphere (bright ring)")
print("    f(r) = ring at r=R with Gaussian width")

R = 8.0
width = 1.0
fr_ring = np.exp(-((r - R) / width) ** 2)
fr_ring[r > R + 4 * width] = 0.0

Fy_ring = decomp.abel_forward(fr_ring, dr=dr)

fr_ring_onion = decomp.abel_onion(Fy_ring, dr=dr)
fr_ring_3pt   = decomp.abel_three_point(Fy_ring, dr=dr)

# Peak position recovery
r_peak_true  = r[np.argmax(fr_ring)]
r_peak_onion = r[np.argmax(fr_ring_onion)]
r_peak_3pt   = r[np.argmax(fr_ring_3pt)]
print(f"  True ring center  : r = {r_peak_true:.3f}")
print(f"  Onion peak        : r = {r_peak_onion:.3f}  (err {abs(r_peak_onion-r_peak_true)/r_peak_true*100:.1f}%)")
print(f"  Three-point peak  : r = {r_peak_3pt:.3f}  (err {abs(r_peak_3pt-r_peak_true)/r_peak_true*100:.1f}%)")

# ---------------------------------------------------------------
# Part 4: Noise robustness
# ---------------------------------------------------------------
print("\n[4] Noise robustness (SNR ~ 50 added to projection)")

rng = np.random.default_rng(99)
noise_level = Fy_ring.max() / 50.0
Fy_noisy = Fy_ring + noise_level * rng.standard_normal(N)

fr_noisy_onion = decomp.abel_onion(Fy_noisy, dr=dr)
fr_noisy_3pt   = decomp.abel_three_point(Fy_noisy, dr=dr)

r_peak_on = r[np.argmax(fr_noisy_onion)]
r_peak_tp = r[np.argmax(fr_noisy_3pt)]
print(f"  True peak: {r_peak_true:.3f}")
print(f"  Noisy onion peak : {r_peak_on:.3f}  (err {abs(r_peak_on-r_peak_true)/r_peak_true*100:.1f}%)")
print(f"  Noisy 3-pt  peak : {r_peak_tp:.3f}  (err {abs(r_peak_tp-r_peak_true)/r_peak_true*100:.1f}%)")
print("  (Three-point typically less noisy than onion peeling at center)")

# ---------------------------------------------------------------
# Part 5: 2D image -- simulated plasma emission
# ---------------------------------------------------------------
print("\n[5] 2D image: simulated plasma emission (cylindrical symmetry)")

n_rows, n_cols = 120, 201
cx = n_cols // 2   # center column

x = np.arange(n_cols) - cx
y_ax = np.arange(n_rows) - n_rows // 2

X, Y = np.meshgrid(x, y_ax)
R_img = np.abs(X).astype(float)   # radial distance from axis (2D, using Abel convention)

# Each row: hollow emission ring profile (varying intensity along axis)
axial_profile = np.exp(-(y_ax / 20.0) ** 2)
ring_r = 25.0
ring_w = 4.0

image = np.zeros((n_rows, n_cols))
for i, ax_amp in enumerate(axial_profile):
    fr_row = ax_amp * np.exp(-((np.arange(n_cols // 2 + 1) - ring_r) / ring_w) ** 2)
    Fy_row = decomp.abel_forward(fr_row, dr=1.0)
    m = len(Fy_row)
    image[i, cx:cx + m] = Fy_row
    if cx > 0:
        ml = min(m - 1, cx)
        image[i, cx - ml:cx] = Fy_row[ml:0:-1]

print(f"  Image shape: {image.shape}")

# Find center (should detect cx = {cx})
cr_found, cc_found = decomp.abel_center(image)
print(f"  abel_center() found: col = {cc_found}  (true: {cx})")

# Invert with both methods
result_3pt   = decomp.abel_image(image, method="three_point", center=(cr_found, cc_found))
result_onion = decomp.abel_image(image, method="onion",       center=(cr_found, cc_found))

print(f"  Radial image shape: {result_3pt['radial'].shape}")

# Check ring recovery at central row (highest intensity)
mid_row = n_rows // 2
fr_mid_3pt   = result_3pt["radial"][mid_row, cx:]
fr_mid_onion = result_onion["radial"][mid_row, cx:]

peak_3pt   = np.argmax(fr_mid_3pt)
peak_onion = np.argmax(fr_mid_onion)
print(f"  Ring peak at pixel (true: {int(ring_r)}) -- 3pt: {peak_3pt}  onion: {peak_onion}")

# ---------------------------------------------------------------
# Part 6: Round-trip validation
# ---------------------------------------------------------------
print("\n[6] Round-trip: invert -> re-project -> compare with original")

reprojected = decomp.abel_forward_image(result_3pt["radial"],
                                         center=(cr_found, cc_found))
err_rt = np.linalg.norm(image - reprojected) / np.linalg.norm(image)
print(f"  Round-trip error (project(invert(image)) vs image): {err_rt:.4f}")
print("  (Should be small; remaining error from edge effects and discretisation)")

# ---------------------------------------------------------------
# Part 7: Viz (optional)
# ---------------------------------------------------------------
print("\n[7] Visualization (requires matplotlib)")
try:
    from anvil import viz
    viz.abel_compare(image, result_3pt, show=False)
    print("  abel_compare() figure created. Call plt.show() or fig.savefig().")
    viz.abel_compare(image, result_onion, show=False, cmap="inferno")
    print("  Second figure (onion, inferno colormap) created.")
except ImportError:
    print("  matplotlib not installed -- skipping.")
except Exception as e:
    print(f"  Viz skipped: {e}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Example 19: Abel Transform and Inversion
============================================================

[1] Forward Abel: Gaussian radial distribution -> projection
    f(r) = exp(-r^2/sigma^2),  F(y) = sigma*sqrt(pi)*exp(-y^2/sigma^2)
  Forward transform error vs analytic: 2.05e-04

[2] Abel inversion: projection -> radial distribution
  Onion peeling  error vs ground truth: 0.0000
  Three-point    error vs ground truth: 0.0009
  Peak (onion)  : f[0] = 1.0000  (true: 1.0000)
  Peak (3-point): f[0] = 0.9929  (true: 1.0000)

[3] Harder test: hollow sphere (bright ring)
    f(r) = ring at r=R with Gaussian width
  True ring center  : r = 8.000
  Onion peak        : r = 8.000  (err 0.0%)
  Three-point peak  : r = 8.000  (err 0.0%)

[4] Noise robustness (SNR ~ 50 added to projection)
  True peak: 8.000
  Noisy onion peak : 0.150  (err 98.1%)
  Noisy 3-pt  peak : 7.950  (err 0.6%)
  (Three-point typically less noisy than onion peeling at center)

[5] 2D image: simulated plasma emission (cylindrical symmetry)
  Image shape: (120, 201)
  abel_center() found: col = 100  (true: 100)
  Radial image shape: (120, 201)
  Ring peak at pixel (true: 25) -- 3pt: 25  onion: 25

[6] Round-trip: invert -> re-project -> compare with original
  Round-trip error (project(invert(image)) vs image): 0.0166
... (9 more lines)
```


## Example 20: Space Dynamics, Attitude, and Mission Budgets

`examples/ex20_space_dynamics.py`: the space-focused RSQs added to the Anvil seed library.

```python
import numpy as np

import anvil
from anvil import Q, System

W = 65
print("=" * W)
print("  Example 20: Space Dynamics, Attitude & Mission Budgets")
print("=" * W)

mu_E = 3.986004418e14
R_E = 6.371e6
J2 = 1.08263e-3
a_SSO = R_E + 500e3  # m
i_SSO = 97.4  # deg (SSO for 500 km)


# =============================================================================
# [1] Orbital state
# =============================================================================

print("\n[1] Orbital state: Keplerian <-> Cartesian")

eci = anvil.R.keplerian_to_cartesian(
    a=a_SSO,
    e=0.001,
    i_deg=i_SSO,
    RAAN_deg=45.0,
    omega_deg=90.0,
    nu_deg=0.0,
    mu=mu_E,
)
T_orbit = Q(2 * 3.141592653589793 * (a_SSO**3 / mu_E) ** 0.5, "s")
print(f"  r_mag  = {eci['r_mag']}")
print(f"  v_mag  = {eci['v_mag']}")
print(f"  period = {T_orbit}")

back = anvil.R.cartesian_to_keplerian(
    r_vec=eci["r_eci"],
    v_vec=eci["v_eci"],
    mu=mu_E,
)
print(f"  Round-trip:  a = {back['a']}  e = {back['e']:.5f}")
print(f"               i = {back['i_deg']:.3f} deg  RAAN = {back['RAAN_deg']:.3f} ")


# =============================================================================
# [2] J2 and eclipse
# =============================================================================

print("\n[2] J2 precession and eclipse at SSO")

j2 = anvil.R.j2_precession(a=a_SSO, e=0.001, i_deg=i_SSO)
print(f"  RAAN drift   : {j2['d_RAAN_dt']}  (SSO target ~+1.99e-7 rad/s)")
print(f"  omega drift  : {j2['d_omega_dt']}")

ecl_worst = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=0.0)
ecl_best = anvil.R.eclipse_fraction(a=a_SSO, beta_deg=70.0)
print(f"  Eclipse worst (beta=0):   {ecl_worst['eclipse_frac']:.3f}")
print(f"  Eclipse best  (beta=70):  {ecl_best['eclipse_frac']:.3f}")
print(f"  Max-eclipse beta:         {ecl_worst['beta_max_deg']:.1f} deg")


# =============================================================================
# [3] Delta-V budget
# =============================================================================

print("\n[3] Delta-V budget")

dv = anvil.R.delta_v_budget(
    dv1=50,
    dv2=20,
    dv3=30,
    dv4=80,
    margin_pct=10.0,
)
print(f"  dv total (no margin)  : {dv['dv_total']}")
print(f"  dv with 10% margin    : {dv['dv_with_margin']}")

prop = anvil.R.propellant_mass(
    dv=dv["dv_with_margin"].si,
    Isp=220,
    m_dry=200,
)
print(f"  Propellant (Isp=220 s): {prop['m_propellant']}")
print(f"  Wet mass              : {prop['m_wet']}")
print(f"  Mass ratio            : {prop['mass_ratio']:.4f}")

print(f"\n  Propellant vs Isp (same dv):")
prop_sys = System("propulsion")
prop_sys.add("dv", dv["dv_with_margin"].si, "m/s")
prop_sys.add("Isp", 220, "s")
prop_sys.add("m_dry", 200, "kg")
prop_sys.use("propellant_mass")
prop_sys.sweep("Isp", [80, 150, 220, 300, 450, 3000]).summary(
    outputs=["Isp", "m_propellant", "mass_ratio"]
)


# =============================================================================
# [4] Gravity gradient torque and reaction wheel sizing
# =============================================================================

print("\n[4] Attitude disturbances and actuator sizing")

Ix, Iy, Iz = 8.0, 10.0, 12.0

gg = anvil.R.gravity_gradient_torque(
    mu=mu_E,
    r=a_SSO,
    Ix=Ix,
    Iy=Iy,
    Iz=Iz,
    theta_pitch_deg=1.0,
    phi_roll_deg=0.5,
)
print(f"  T_roll     : {gg['T_roll']}")
print(f"  T_pitch    : {gg['T_pitch']}")
print(f"  T_gg_max   : {gg['T_gg_max']}")

rw = anvil.R.reaction_wheel_sizing(
    I_sc=Iz,
    theta_slew_deg=5.0,
    t_slew=30.0,
    margin=1.5,
)
print(f"\n  5 deg slew in 30 s (1.5x margin):")
print(f"  H_rw       : {rw['H_rw']}")
print(f"  tau_rw     : {rw['tau_rw']}")
print(f"  omega_slew : {rw['omega_slew_max']}")
print(f"  P_peak     : {rw['P_peak']}")


# =============================================================================
# [5] Quaternion kinematics
# =============================================================================

print("\n[5] Quaternion kinematics -- 0.01 rad/s pitch for 10 steps")

dt = 1.0
q = [1.0, 0.0, 0.0, 0.0]
print(f"  {'t':>4}  {'q_w':>8}  {'q_x':>8}  {'q_y':>8}  {'q_z':>8}  {'|q|':>6}")
for step in range(11):
    if step % 2 == 0:
        print(
            f"  {step * dt:>4.0f}  {q[0]:>8.5f}  {q[1]:>8.5f}  {q[2]:>8.5f}  {q[3]:>8.5f}  "
            f"{sum(x**2 for x in q) ** 0.5:>6.4f}"
        )
    if step < 10:
        qd = anvil.R.quaternion_kinematics(
            q_w=q[0],
            q_x=q[1],
            q_y=q[2],
            q_z=q[3],
            omega_x=0.0,
            omega_y=0.01,
            omega_z=0.0,
        )
        q = [
            q[0] + qd["qw_dot"] * dt,
            q[1] + qd["qx_dot"] * dt,
            q[2] + qd["qy_dot"] * dt,
            q[3] + qd["qz_dot"] * dt,
        ]
        n = sum(x**2 for x in q) ** 0.5
        q = [x / n for x in q]


# =============================================================================
# [6] TRIAD attitude determination
# =============================================================================

print("\n[6] TRIAD attitude determination")

theta = np.radians(30)
C_true = np.array(
    [[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]]
)
sun_ref = np.array([0.8, 0.6, 0.0])
mag_ref = np.array([0.3, 0.0, 0.95])
sun_body = C_true @ sun_ref
mag_body = C_true @ mag_ref

tr = anvil.R.triad_attitude(
    b1_x=sun_body[0],
    b1_y=sun_body[1],
    b1_z=sun_body[2],
    b2_x=mag_body[0],
    b2_y=mag_body[1],
    b2_z=mag_body[2],
    r1_x=sun_ref[0],
    r1_y=sun_ref[1],
    r1_z=sun_ref[2],
    r2_x=mag_ref[0],
    r2_y=mag_ref[1],
    r2_z=mag_ref[2],
)
print(
    f"  True rotation: 30 deg about Z  ->  q_z = sin(15 deg) = {np.sin(np.radians(15)):.5f}"
)
print(
    f"  TRIAD q: w={tr['q_w']:.5f}  x={tr['q_x']:.5f}  y={tr['q_y']:.5f}  z={tr['q_z']:.5f}"
)


# =============================================================================
# [7] Euler equations
# =============================================================================

print("\n[7] Euler equations -- spin stability check")

for label, (Ix_, Iy_, Iz_), (ox, oy, oz) in [
    ("Major axis (stable)", (100, 80, 60), (0.01, 0.01, 1.0)),
    ("Minor axis (stable)", (60, 80, 100), (0.01, 0.01, 1.0)),
    ("Intermediate (unstable)", (60, 100, 80), (0.01, 0.01, 1.0)),
]:
    r = anvil.R.euler_equations(
        omega_x=ox, omega_y=oy, omega_z=oz, Ix=Ix_, Iy=Iy_, Iz=Iz_
    )
    alpha_perp = (r["alpha_x"].si ** 2 + r["alpha_y"].si ** 2) ** 0.5
    print(f"  {label:32s}: perp accel = {Q(alpha_perp, 'rad/s^2')}")


# =============================================================================
# [8] Power budget
# =============================================================================

print("\n[8] Power budget -- 200 kg EO smallsat")

pwr = anvil.R.power_budget(
    P_load_W=80,
    T_orbit_min=94.6,
    eclipse_frac=ecl_worst["eclipse_frac"],
    eta_solar=0.30,
    flux_solar=1361.0,
    DOD=0.8,
    eta_battery=0.9,
)
print(f"  Solar array  : {pwr['A_panel_m2']}")
print(f"  Battery      : {pwr['E_bat_Wh']}  /  {pwr['m_bat_kg']}")
print(f"  Panel output : {pwr['P_from_panel_W']}")

print(f"\n  Sensitivity: panel area vs eclipse fraction:")
pwr_sys = System("power_sizing")
pwr_sys.add("P_load_W", 80)
pwr_sys.add("T_orbit_min", 94.6)
pwr_sys.add("eclipse_frac", 0.35)
pwr_sys.add("eta_solar", 0.30)
pwr_sys.add("flux_solar", 1361.0)
pwr_sys.add("DOD", 0.8)
pwr_sys.add("eta_battery", 0.9)
pwr_sys.use("power_budget")
pwr_sys.sweep("eclipse_frac", np.linspace(0.1, 0.5, 5)).summary(
    outputs=["eclipse_frac", "A_panel_m2", "E_bat_Wh", "m_bat_kg"]
)


# =============================================================================
# [9] Link budget
# =============================================================================

print("\n[9] Link budget -- X-band downlink at 500 km")

lnk = anvil.R.link_budget(
    P_tx_W=5,
    G_tx_dBi=3,
    G_rx_dBi=47,
    freq_Hz=8.4e9,
    distance_m=a_SSO,
    losses_dB=4.0,
)
print(f"  FSPL         : {lnk['FSPL_dB']:.1f} dB")
print(f"  EIRP         : {lnk['EIRP_dBW']:.1f} dBW")
print(f"  P_rx         : {lnk['P_rx_dBW']:.1f} dBW  =  {lnk['P_rx_W']}")

print(f"\n  Range sweep:")
print(f"  {'Range (km)':>12}  {'FSPL (dB)':>10}  {'P_rx (dBW)':>12}")
for d_km in [400, 600, 800, 1200, 2000]:
    r = anvil.R.link_budget(
        P_tx_W=5,
        G_tx_dBi=3,
        G_rx_dBi=47,
        freq_Hz=8.4e9,
        distance_m=d_km * 1e3,
        losses_dB=4.0,
    )
    print(f"  {d_km:>12}  {r['FSPL_dB']:>10.1f}  {r['P_rx_dBW']:>12.1f}")


# =============================================================================
# [10] Attitude controller analysis
# =============================================================================

print("\n[10] Attitude controller analysis (pitch PD)")

Kp, Kd = 0.15, 1.2
omega_n = (Kp / Iz) ** 0.5
zeta = Kd / (2 * (Kp * Iz) ** 0.5)

m = anvil.R.second_order_metrics(omega_n=omega_n, zeta=zeta)
print(f"  omega_n = {Q(omega_n, 'rad/s')}  zeta = {zeta:.4f}")
print(
    f"  Overshoot: {m['overshoot_pct']:.1f}%   t_settle: {m['t_settle']:.1f} s   t_rise: {m['t_rise']:.1f} s"
)

poles = anvil.R.state_space_poles(A_flat=[0, 1, -Kp / Iz, -Kd / Iz], n_states=2)
print(
    f"  Poles: {[complex(round(r, 4), round(i, 4)) for r, i in zip(poles['poles_real'], poles['poles_imag'])]}"
)
print(f"  Stable: {poles['stable']}  min damping: {poles['min_damping']:.4f}")

gm = anvil.R.gain_phase_margin(num_coeffs=[Kd, Kp], den_coeffs=[Iz, 0, 0])
print(
    f"  GM = {gm['GM_dB']:.1f} dB   PM = {gm['PM_deg']:.1f} deg   stable = {gm['stable']}"
)

q_lqr = anvil.R.lqr_bryson(
    state_bounds=[np.radians(5)] * 3,
    input_bounds=[0.5] * 3,
)
print(
    f"  LQR Q = {[round(x, 1) for x in q_lqr['Q_diag']]}  R = {[round(x, 2) for x in q_lqr['R_diag']]}"
)


# =============================================================================
# [11] Sphere of influence
# =============================================================================

print("\n[11] Sphere of influence")

soi_moon = anvil.R.sphere_of_influence(
    a_body=384400e3, m_body=7.342e22, m_parent=5.972e24
)
soi_mars = anvil.R.sphere_of_influence(
    a_body=1.524 * 1.496e11, m_body=6.390e23, m_parent=1.989e30
)
print(f"  Moon SOI : {soi_moon['r_SOI'].to('km')}  (expected 66100 km)")
print(f"  Mars SOI : {soi_mars['r_SOI'].to('km')}  (expected ~577000 km)")


# =============================================================================
# [12] Hohmann vs bi-elliptic
# =============================================================================

print("\n[12] Hohmann vs bi-elliptic  LEO -> GEO")

h = anvil.R.hohmann_transfer(mu=mu_E, r1=R_E + 400e3, r2=42164e3)
print(f"  Hohmann:   dv = {h['dv_total'].to('km/s')}   tof = {h['tof']}")

for r_b_km in [100_000, 200_000, 384_400]:
    be = anvil.R.bielliptic_transfer(
        mu=mu_E, r1=R_E + 400e3, r2=42164e3, rb=r_b_km * 1e3
    )
    print(
        f"  Bi-elliptic rb={r_b_km:7d} km:  dv = {be['dv_total'].to('km/s')}   tof = {be['tof']}"
    )


print("\n" + "=" * W)
print("  Done.")
print("=" * W)
```

**Output:**

```
=================================================================
  Example 20: Space Dynamics, Attitude & Mission Budgets
=================================================================

[1] Orbital state: Keplerian <-> Cartesian
  r_mag  = 6.8641e+06 m
  v_mag  = 7624.18 m/s
  period = 5668.14 s
  Round-trip:  a = 6.8710e+06 m  e = 0.00100
               i = 97.400 deg  RAAN = 45.000 

[2] J2 precession and eclipse at SSO
  RAAN drift   : 1.9934e-07 rad/s  (SSO target ~+1.99e-7 rad/s)
  omega drift  : -7.0967e-07 rad/s
  Eclipse worst (beta=0):   0.378
  Eclipse best  (beta=70):  0.000
  Max-eclipse beta:         68.0 deg

[3] Delta-V budget
  dv total (no margin)  : 180.00 m/s
  dv with 10% margin    : 198.00 m/s
  Propellant (Isp=220 s): 19.2235 kg
  Wet mass              : 219.22 kg
  Mass ratio            : 1.0961

  Propellant vs Isp (same dv):

----------------------------------------------------------------------
  propulsion -- sweep over Isp
----------------------------------------------------------------------
             Isp           Isp  m_propellant    mass_ratio
             [s]           [s]          [kg]              
  --------------------------------------------------------
              80            80         57.42         1.287
... (90 more lines)
```


## Example 21: poliastro Adapter -- Orbit Design in Anvil

`examples/ex21_poliastro_adapter.py`: the poliastro adapter for orbit state, Hohmann transfers,

```python
import os
import math
import numpy as np


import anvil
from anvil import Q

from anvil.adapters import poliastro_orbits
from anvil.adapters.poliastro_orbits import (
    poliastro_orbit, poliastro_hohmann, poliastro_propagate, register
)

W = 64
R_E   = 6371e3      # m
MU_E  = 3.986004418e14

print("=" * W)
print("  Example 21: poliastro Adapter")
print("=" * W)

if not poliastro_orbits.is_available():
    print("  poliastro not installed -- skipping example.")
    print("  Install: pip install poliastro astropy")
    raise SystemExit(0)

import poliastro
print(f"  poliastro {poliastro.__version__} found.")
print()


# ── 1. Direct adapter calls ───────────────────────────────────────────────────
print("[1] Orbit state -- direct adapter calls")

orbits = [
    ("ISS / LEO",  R_E + 407e3,  0.0000, math.radians(51.6)),
    ("GTO",        24396e3,      0.7311, math.radians(27.0)),
    ("GEO",        42164e3,      0.0000, math.radians(0.0)),
    ("Polar LEO",  R_E + 500e3,  0.0000, math.radians(98.0)),
]

print(f"  {'Label':14s}  {'a (km)':>10s}  {'ecc':>6s}  {'T (min)':>8s}  {'v (m/s)':>9s}")
print(f"  {'-'*14}  {'-'*10}  {'-'*6}  {'-'*8}  {'-'*9}")
for label, a, ecc, inc in orbits:
    r = poliastro_orbit(a=a, ecc=ecc, inc=inc, raan=0.0, argp=0.0, nu=0.0)
    print(f"  {label:14s}  {a/1e3:10.1f}  {ecc:6.4f}  "
          f"{r['period'].to('min')}  {r['v_mag']}")


# ── 2. Hohmann transfers ──────────────────────────────────────────────────────
print(f"\n[2] Hohmann transfers")

transfers = [
    ("LEO 200km -> GEO",       R_E + 200e3,  42164e3),
    ("LEO 200km -> Moon dist", R_E + 200e3,  384400e3),
    ("LEO 400km -> LEO 600km", R_E + 400e3,  R_E + 600e3),
]

print(f"  {'Transfer':28s}  {'dv1 (m/s)':>10s}  {'dv2 (m/s)':>10s}  "
      f"{'total (m/s)':>11s}  {'TOF (h)':>8s}")
print(f"  {'-'*28}  {'-'*10}  {'-'*10}  {'-'*11}  {'-'*8}")
for label, a_i, a_f in transfers:
    r = poliastro_hohmann(a_i=a_i, a_f=a_f)
    print(f"  {label:28s}  {r['dv_1']}  {r['dv_2']}  "
          f"  {r['dv_total']}  {r['t_transfer'].to('hr')}")


# ── 3. Orbit System -- chain with propellant_mass RSQ ────────────────────────
print(f"\n[3] LEO->GEO mission budget (orbit + propellant_mass in one System)")

register()   # push adapters to global registry so sys.use() can find them

mission = anvil.system("leo_geo_mission")
mission.add("a_i",   R_E + 200e3, "m",   desc="Departure orbit radius")
mission.add("a_f",   42164e3,     "m",   desc="Target orbit radius (GEO)")
mission.add("Isp",   450.0,       "s",   desc="Engine specific impulse")
mission.add("m_wet", 5000.0,      "kg",  desc="Spacecraft wet mass")
mission.add("g0",    9.80665,     "m/s^2")

mission.use(poliastro_hohmann)          # Adapter object directly (not registry lookup)

def rocket_budget(dv_total, Isp, g0, m_wet):
    """Tsiolkovsky: given m_wet, compute propellant and dry mass."""
    mr = math.exp(dv_total / (Isp * g0))
    m_prop = m_wet * (1.0 - 1.0 / mr)
    return {"m_prop": Q(m_prop, "kg"), "m_dry": Q(m_wet - m_prop, "kg"), "mass_ratio": mr}
mission.use(rocket_budget)

result = mission.solve_forward()
result.summary(keys=["a_i", "a_f", "dv_total", "t_transfer", "m_prop", "m_dry"])

print(f"\n  Total dv   = {result['dv_total'].to('km/s')}")
print(f"  Transfer   = {result['t_transfer'].to('hr')}")
print(f"  Propellant = {result['m_prop']}  "
      f"({result['m_prop'].value / 5000.0 * 100:.1f}% of wet mass)")
print(f"  Dry mass   = {result['m_dry']}")


# ── 4. Sweep: transfer dv vs target altitude ──────────────────────────────────
print(f"\n[4] Sweep: transfer dv vs target altitude (100 km to 42 164 km)")

altitudes_km = np.linspace(100, 42164, 8)
print(f"  {'Alt (km)':>10s}  {'dv_total (m/s)':>15s}  {'TOF (h)':>8s}")
print(f"  {'-'*10}  {'-'*15}  {'-'*8}")
for alt in altitudes_km:
    r = poliastro_hohmann(a_i=R_E + 200e3, a_f=R_E + alt * 1e3)
    print(f"  {alt:10.0f}  {r['dv_total']}  "
          f"{r['t_transfer'].to('hr')}")


# ── 5. Sensitivity analysis ───────────────────────────────────────────────────
print(f"\n[5] Sensitivity: what drives orbital speed in LEO?")

leo_sys = anvil.system("leo_orbit")
leo_sys.add("a",    R_E + 400e3, "m")
leo_sys.add("ecc",  0.0)
leo_sys.add("inc",  math.radians(51.6), "rad")
leo_sys.add("raan", 0.0, "rad")
leo_sys.add("argp", 0.0, "rad")
leo_sys.add("nu",   0.0, "rad")
leo_sys.use(poliastro_orbit)            # Adapter object directly

sens = leo_sys.sensitivity(outputs=["v_mag", "period"])
print(f"\n  Top drivers of orbital speed (v_mag):")
for inp, val in sens.top("v_mag", n=4):
    print(f"    {inp:8s}  {val:+.4f}")

print(f"\n  Top drivers of orbital period:")
for inp, val in sens.top("period", n=4):
    print(f"    {inp:8s}  {val:+.4f}")


# ── 6. Propagation checks ─────────────────────────────────────────────────────
print(f"\n[6] Propagation checks (circular LEO, 400 km)")

a0 = R_E + 400e3
T_s = poliastro_orbit(a=a0, ecc=0.0, inc=0.0, raan=0.0, argp=0.0, nu=0.0)
T   = T_s["period"].si

print(f"  Orbital period = {T/60:.2f} min")
print(f"  {'Fraction':12s}  {'nu_f (deg)':>12s}  {'r_mag (km)':>12s}")
print(f"  {'-'*12}  {'-'*12}  {'-'*12}")
for frac, label in [(0.25, "T/4"), (0.5, "T/2"), (1.0, "T")]:
    r = poliastro_propagate(a=a0, ecc=0.0, inc=0.0, raan=0.0,
                             argp=0.0, nu=0.0, dt=T * frac)
    r_km = math.sqrt(r["r_x"].si**2 + r["r_y"].si**2 + r["r_z"].si**2) / 1e3
    print(f"  {label:12s}  {math.degrees(r['nu_f'].si):12.2f}  {r_km:12.1f}")


# ── 7. Eccentric orbit: GTO propagation ──────────────────────────────────────
print(f"\n[7] GTO propagation -- quarter period from perigee")

# GTO: 200 km x 35786 km
a_gto  = (R_E + 200e3 + 42164e3) / 2
ecc_gto = (42164e3 - (R_E + 200e3)) / (42164e3 + R_E + 200e3)
T_gto = poliastro_orbit(a=a_gto, ecc=ecc_gto, inc=0.0,
                         raan=0.0, argp=0.0, nu=0.0)["period"].si

print(f"  a_gto   = {a_gto/1e6:.3f} Mm,  ecc = {ecc_gto:.4f}")
print(f"  r_p     = {(R_E + 200e3)/1e6:.3f} Mm (perigee)")
print(f"  r_a     = {42164e3/1e6:.3f} Mm (apogee)")
print(f"  period  = {T_gto/3600:.2f} h")

rp = poliastro_propagate(a=a_gto, ecc=ecc_gto, inc=0.0,
                          raan=0.0, argp=0.0, nu=0.0,
                          dt=T_gto / 2)
r_apo = math.sqrt(rp["r_x"].si**2 + rp["r_y"].si**2 + rp["r_z"].si**2)
print(f"\n  After T/2 (at apogee):")
print(f"  r_mag   = {r_apo/1e6:.3f} Mm  (expect {42164e3/1e6:.3f} Mm)")

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example 22: pykep Adapter -- Trajectory Design in Anvil

`examples/ex22_pykep_adapter.py`: the pykep adapter for Lambert arc solutions, Keplerian

```python
import os
import math
import numpy as np


import anvil
from anvil import Q

from anvil.adapters import pykep_trajectories
from anvil.adapters.pykep_trajectories import (
    pykep_lambert, pykep_propagate, pykep_planet_state, register
)

W      = 64
AU     = 1.495978707e11
MU_SUN = 1.32712440018e20

print("=" * W)
print("  Example 22: pykep Adapter")
print("=" * W)

if not pykep_trajectories.is_available():
    print("  pykep not installed -- skipping example.")
    print("  Install: pip install pykep")
    raise SystemExit(0)

import pykep
print(f"  pykep {pykep.__version__} found.")
print()


# ── 1. Planet states ──────────────────────────────────────────────────────────
print("[1] Planet states at J2000 (epoch = 0 MJD2000)")

planets = ["mercury", "venus", "earth", "mars", "jupiter"]
print(f"  {'Planet':10s}  {'|r| (AU)':>10s}  {'|v| (km/s)':>12s}")
print(f"  {'-'*10}  {'-'*10}  {'-'*12}")
for planet in planets:
    r = pykep_planet_state(planet=planet, epoch_mjd2000=0.0)
    print(f"  {planet:10s}  {r['r_mag'].value / AU:10.4f}  "
          f"{r['v_mag'].value / 1e3:12.3f}")


# ── 2. Propagate Earth 1 year -- closure check ───────────────────────────────
print(f"\n[2] Propagate Earth state by 1 year (expect |r| ~ 1 AU at end)")

r_e0 = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
r_e1 = pykep_propagate(
    r_x=r_e0["r_x"].si, r_y=r_e0["r_y"].si, r_z=r_e0["r_z"].si,
    v_x=r_e0["v_x"].si, v_y=r_e0["v_y"].si, v_z=r_e0["v_z"].si,
    dt=365.25 * 86400,
    mu=MU_SUN,
)
print(f"  |r| at t=0   : {r_e0['r_mag'].value / AU:.5f} AU")
print(f"  |r| at t=1yr : {r_e1['r_mag_f'].value / AU:.5f} AU  (expect ~1.00000)")

# Cross-check: Earth state 1 year later from ephemeris
r_e1_eph = pykep_planet_state(planet="earth", epoch_mjd2000=365.25)
dr = math.sqrt(
    (r_e1["r_x_f"].si - r_e1_eph["r_x"].si)**2 +
    (r_e1["r_y_f"].si - r_e1_eph["r_y"].si)**2 +
    (r_e1["r_z_f"].si - r_e1_eph["r_z"].si)**2
)
print(f"  Closure error : {dr/AU:.4f} AU  (two-body propagation vs JPL low-precision ephemeris)")


# ── 3. Lambert arc Earth->Mars ────────────────────────────────────────────────
print(f"\n[3] Lambert arc Earth->Mars at J2000 positions, tof=200 days")

r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
r_mars  = pykep_planet_state(planet="mars",  epoch_mjd2000=200.0)  # Mars 200 days later

sol = pykep_lambert(
    r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
    r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,  r1_z=r_mars["r_z"].si,
    tof=200 * 86400,
)
print(f"  Departure v   : ({sol['v_dep_x'].value/1e3:.3f}, "
      f"{sol['v_dep_y'].value/1e3:.3f}, {sol['v_dep_z'].value/1e3:.3f}) km/s")
print(f"  Arrival v     : ({sol['v_arr_x'].value/1e3:.3f}, "
      f"{sol['v_arr_y'].value/1e3:.3f}, {sol['v_arr_z'].value/1e3:.3f}) km/s")
print(f"  |v_dep|       : {sol['dv_dep'].value/1e3:.3f} km/s")
print(f"  |v_arr|       : {sol['dv_arr'].value/1e3:.3f} km/s")

# Verify arc: propagate departure state forward tof
r_check = pykep_propagate(
    r_x=r_earth["r_x"].si, r_y=r_earth["r_y"].si, r_z=r_earth["r_z"].si,
    v_x=sol["v_dep_x"].si, v_y=sol["v_dep_y"].si, v_z=sol["v_dep_z"].si,
    dt=200 * 86400, mu=MU_SUN,
)
err_m = math.sqrt(
    (r_check["r_x_f"].si - r_mars["r_x"].si)**2 +
    (r_check["r_y_f"].si - r_mars["r_y"].si)**2 +
    (r_check["r_z_f"].si - r_mars["r_z"].si)**2
)
print(f"  Arc closure   : {err_m/1e3:.3f} km  (should be ~0)")


# ── 4. Delta-v budget System: planet state + Lambert ─────────────────────────
print(f"\n[4] Delta-v budget System (planet state + Lambert in one solve)")

register()  # push pykep adapters to global registry

traj = anvil.system("earth_mars_transfer")
traj.add("epoch_dep", 0.0,        desc="Departure epoch (MJD2000 days)")
traj.add("tof",       200.0 * 86400, "s", desc="Time of flight")

# Earth departure state
def earth_state(epoch_dep):
    return pykep_planet_state(planet="earth", epoch_mjd2000=epoch_dep)
traj.use(earth_state)

# Mars arrival state (epoch_dep + tof)
def mars_arrival(epoch_dep, tof):
    return pykep_planet_state(
        planet="mars",
        epoch_mjd2000=epoch_dep + tof / 86400
    )
traj.use(mars_arrival, outputs={"r_x": "r_x_m", "r_y": "r_y_m", "r_z": "r_z_m",
                                  "v_x": "v_x_m", "v_y": "v_y_m", "v_z": "v_z_m",
                                  "r_mag": "r_mag_m", "v_mag": "v_mag_m"})

# Lambert
def lambert_transfer(r_x, r_y, r_z, r_x_m, r_y_m, r_z_m, tof):
    return pykep_lambert(
        r0_x=r_x, r0_y=r_y, r0_z=r_z,
        r1_x=r_x_m, r1_y=r_y_m, r1_z=r_z_m,
        tof=tof,
    )
traj.use(lambert_transfer)

res = traj.solve_forward()
print(f"  Departure  : epoch {res['epoch_dep']}")
print(f"  TOF        : {res['tof'].si / 86400:.1f} days")
print(f"  dv_dep     : {res['dv_dep'].value/1e3:.3f} km/s")
print(f"  dv_arr     : {res['dv_arr'].value/1e3:.3f} km/s")
print(f"  dv_total   : {res['dv_total'].value/1e3:.3f} km/s")


# ── 5. Sweep: tof scan (mini porkchop column) ─────────────────────────────────
print(f"\n[5] TOF sweep (Earth->Mars, 100-350 days) -- departure at J2000")

r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
tofs_days = np.linspace(100, 350, 6)

print(f"  {'TOF (days)':>10s}  {'dv_dep (km/s)':>14s}  "
      f"{'dv_arr (km/s)':>14s}  {'dv_total (km/s)':>16s}")
print(f"  {'-'*10}  {'-'*14}  {'-'*14}  {'-'*16}")
for tof_d in tofs_days:
    r_mars = pykep_planet_state(planet="mars", epoch_mjd2000=tof_d)
    try:
        s = pykep_lambert(
            r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si,
            r0_z=r_earth["r_z"].si,
            r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,
            r1_z=r_mars["r_z"].si,
            tof=tof_d * 86400,
        )
        print(f"  {tof_d:10.0f}  {s['dv_dep'].value/1e3:14.3f}  "
              f"{s['dv_arr'].value/1e3:14.3f}  {s['dv_total'].value/1e3:16.3f}")
    except Exception as e:
        print(f"  {tof_d:10.0f}  {'error: '+str(e)[:40]}")


# ── 6. Combined: LEO departure + interplanetary arc ───────────────────────────
print(f"\n[6] Complete mission: LEO parking + escape + interplanetary arc")
print(f"    (patched-conic escape burn + pykep Lambert arc)")

R_E = 6371e3
MU_E = 3.986004418e14
V_EARTH_HELIO = r_earth["v_mag"].si   # Earth's heliocentric speed

# Lambert departure velocity vector magnitude at Earth
r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
r_mars_200 = pykep_planet_state(planet="mars", epoch_mjd2000=200.0)
sol = pykep_lambert(
    r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
    r1_x=r_mars_200["r_x"].si, r1_y=r_mars_200["r_y"].si,
    r1_z=r_mars_200["r_z"].si,
    tof=200 * 86400,
)

# Hyperbolic excess velocity at Earth departure
v_dep = sol["dv_dep"].si      # heliocentric departure speed (m/s)
v_inf = abs(v_dep - V_EARTH_HELIO)   # rough estimate (assumes co-linear)

# Escape dv from 200 km LEO: v_esc^2 = v_circ^2 + v_inf^2
# v_park = sqrt(mu/r), v_hyp = sqrt(v_park^2 + v_inf^2)
r_park = R_E + 200e3
v_park = math.sqrt(MU_E / r_park)
v_hyp  = math.sqrt(v_park**2 + v_inf**2)
dv_escape = v_hyp - v_park

print(f"  Earth heliocentric speed  : {V_EARTH_HELIO/1e3:.3f} km/s")
print(f"  Lambert departure speed   : {v_dep/1e3:.3f} km/s")
print(f"  Hyperbolic excess v_inf   : {v_inf/1e3:.3f} km/s  (co-linear approx)")
print(f"  LEO circular speed (200km): {v_park/1e3:.3f} km/s")
print(f"  Escape burn dv            : {dv_escape/1e3:.3f} km/s")
print(f"  Lambert arc total dv      : {sol['dv_total'].value/1e3:.3f} km/s")
print(f"  Dominant cost: escape burn from LEO to interplanetary")

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: 2D Euler CFD, Subsonic flow over a Gaussian bump

`examples/ex_cfd_subsonic_bump.py`: M = 0.5 air flow through a channel with a Gaussian bump on the lower wall.

```python
import sys, os

import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh, MeshPatch, viz as cfd_viz
from anvil.cfd.bc import SubsonicInlet, SubsonicOutlet, SlipWall
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# ─────────────────────────────────────────────────────────────────
# Parameters
# ─────────────────────────────────────────────────────────────────
M_inlet  = 0.5
gamma    = 1.4
R_gas    = 287.058
p0_inlet = 110_000.0   # Pa  (total pressure)
T0_inlet = 310.0       # K   (total temperature)

# Isentropic static conditions at inlet Mach 0.5
fac       = 1.0 + 0.5*(gamma-1)*M_inlet**2
p_inlet   = p0_inlet / fac**(gamma/(gamma-1))
T_inlet   = T0_inlet / fac
rho_inlet = p_inlet / (R_gas * T_inlet)
p_back    = p_inlet   # outlet back pressure = inlet static (isentropic channel, no net loss)

print("=" * 60)
print("  Subsonic Gaussian-bump channel  (M = 0.5)")
print("=" * 60)
print(f"\n  Inlet:  p0={p0_inlet:.0f} Pa  T0={T0_inlet:.1f} K  M={M_inlet}")
print(f"  Static: p={p_inlet:.1f} Pa  T={T_inlet:.2f} K  rho={rho_inlet:.4f} kg/m³")

# ─────────────────────────────────────────────────────────────────
# PART 1, Build mesh and write .amesh file
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 1: Mesh generation and .amesh file I/O")
print("=" * 60)

out_dir = os.path.dirname(os.path.abspath(__file__))

mesh = Mesh.bump(
    length      = 2.0,
    height      = 0.5,
    nx          = 80,
    ny          = 30,
    bump_height = 0.10,
    bump_x0     = 1.0,
    bump_sigma  = 0.20,
    title       = "subsonic_bump",
    patches     = {
        "inlet":   MeshPatch("left",  0, 30),
        "outlet":  MeshPatch("right",  0, 30),
        "wall":    MeshPatch("bottom", 0, 80),
        "ceiling": MeshPatch("top", 0, 80),
    }
)

# Write then re-read the mesh (demonstrates file I/O)
amesh_path = os.path.join(out_dir, "bump.amesh")
mesh.to_file(amesh_path)
print(f"\n  Mesh written to: {amesh_path}")

mesh = Mesh.from_file(amesh_path)
mesh.info()

# Visualise mesh (saved to PNG, not shown interactively)
mesh_png = os.path.join(out_dir, "bump_mesh.png")
mesh.plot(show=False, save_path=mesh_png, show_patches=True, show_mesh=True)
print(f"  Mesh plot saved: {mesh_png}")

# ─────────────────────────────────────────────────────────────────
# PART 2, Solver setup
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Solver setup and run")
print("=" * 60)

bcs = {
    "inlet":   SubsonicInlet(M=M_inlet, p0=p0_inlet, T0=T0_inlet, gamma=gamma, R_gas=R_gas),
    "outlet":  SubsonicOutlet(p_back=p_back, gamma=gamma),
    "wall":    SlipWall(),
    "ceiling": SlipWall(),
}

solver = CFDSolver(
    mesh        = mesh,
    bcs         = bcs,
    gamma       = gamma,
    R_gas       = R_gas,
    flux_scheme = "roe",
    order       = 2,
    time_scheme = "rk4",
    cfl         = 0.3,
    transient   = False,
)
solver.initialize(M=M_inlet, p=p_inlet, T=T_inlet)

snap_dir = os.path.join(out_dir, "bump_snapshots")
print(f"\n  Running ({mesh.nx}×{mesh.ny} cells, M={M_inlet}, 2nd-order Roe)...")
print(f"  Saving Mach contour snapshots to: {snap_dir}/")

result = solver.run(
    max_iter    = 3000,
    tol         = 1e-3,    # subsonic fixed-ghost inlet converges slowly
    monitor     = True,
    verbose     = True,
    print_every = 300,
    save_every  = 600,      # save PNG every 600 iterations
    save_field  = "M",
    save_dir    = snap_dir,
    save_vmin   = 0.3,      # fixed scale -- all frames comparable
    save_vmax   = 1.0,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3, Post-processing
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Post-processing and comparison")
print("=" * 60)

# Centreline Mach number
j_mid   = mesh.ny // 2
M_up    = result.M[:mesh.nx // 2, j_mid].mean()
M_crest = result.M[mesh.nx // 2 - 5 : mesh.nx // 2 + 5, 0].mean()  # near wall at crest
p_crest = result.p[mesh.nx // 2 - 5 : mesh.nx // 2 + 5, 0].mean()
p_down  = result.p[mesh.nx // 2:, j_mid].mean()

print(f"\n  Upstream M (avg):     {M_up:.4f}  (inlet target: {M_inlet})")
print(f"  M near bump crest:    {M_crest:.4f}  (expected > inlet M)")
print(f"  p near bump crest:    {p_crest:.1f} Pa  (expected < {p_inlet:.1f} Pa)")
print(f"  p downstream (avg):   {p_down:.1f} Pa  (expected ~ {p_back:.1f} Pa)")
print(f"  p/p_back at outlet:   {p_down/p_back:.4f}  (ideal: 1.0000)")

# Multi-field contour panel
panel_png = os.path.join(out_dir, "bump_fields.png")
cfd_viz.multi_field(result, fields=["M", "p", "T", "rho"],
                    show=False, save_path=panel_png)
print(f"\n  Multi-field plot saved: {panel_png}")

# Residual convergence
conv_png = os.path.join(out_dir, "bump_convergence.png")
cfd_viz.convergence_png(result.history, conv_png, title="Bump: residual convergence")
print(f"  Convergence plot saved: {conv_png}")

# VTK for ParaView
vtk_path = os.path.join(out_dir, "bump_flow.vtk")
result.to_vtk(vtk_path)
print(f"  VTK output saved: {vtk_path}")

# ─────────────────────────────────────────────────────────────────
# PART 4, Mach sweep via as_relation() + parallel
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Mach sweep (parallel=2) using solver as Anvil Relation")
print("=" * 60)

sweep_mesh = Mesh.bump(
    length=2.0, height=0.5, nx=40, ny=15,
    bump_height=0.10, bump_x0=1.0, bump_sigma=0.20,
    patches={
        "inlet":   MeshPatch("left",  0, 15),
        "outlet":  MeshPatch("right",  0, 15),
        "wall":    MeshPatch("bottom", 0, 40),
        "ceiling": MeshPatch("top", 0, 40),
    }
)

def bump_bcs(M, p0, T0, alpha=0.0):
    g = gamma; R = R_gas
    fac = 1.0 + 0.5*(g-1)*M**2
    p_s = p0 / fac**(g/(g-1))   # isentropic static at inlet M
    return {
        "inlet":   SubsonicInlet(M=M, p0=p0, T0=T0, gamma=g, R_gas=R),
        "outlet":  SubsonicOutlet(p_back=p_s, gamma=g),  # matched back pressure
        "wall":    SlipWall(),
        "ceiling": SlipWall(),
    }

sweep_solver = CFDSolver(
    mesh=sweep_mesh, bcs=bump_bcs(0.5, p0_inlet, T0_inlet),
    gamma=gamma, R_gas=R_gas, flux_scheme="roe", order=2, cfl=0.3
)

cfd_rel = sweep_solver.as_relation(
    inputs     = ["M_inf", "p_inf", "T_inf"],
    outputs    = ["M_max", "p_wall"],
    name       = "bump_euler",
    bc_factory = bump_bcs,
    run_kwargs = {"max_iter": 1000, "tol": 1e-3, "verbose": False},
)

sweep_sys = anvil.system("bump_mach_sweep")
sweep_sys.add("M_inf", 0.5)
sweep_sys.add("p_inf",  p0_inlet)
sweep_sys.add("T_inf",  T0_inlet)
sweep_sys.use(cfd_rel)

mach_vals = np.array([0.3, 0.4, 0.5, 0.6])
print(f"\n  Sweeping M = {mach_vals}  (parallel=2)...")
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2, skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# ─────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────
for f in ["bump.amesh", "bump_flow.vtk"]:
    fp = os.path.join(out_dir, f)
    if os.path.exists(fp):
        os.remove(fp)

print("\n" + "=" * 60)
print("  Done. Output files:")
print(f"    {mesh_png}      , mesh + patch labels")
print(f"    {panel_png}     , M/p/T/rho contours")
print(f"    {conv_png}      , residual convergence")
print(f"    {snap_dir}/     , Mach snapshots every 500 iters")
print("=" * 60)
```

> Runs a full solve that takes a while; run the script locally to see its output.


## Example: 2D Euler CFD, Supersonic flow over a compression ramp

`examples/ex_cfd_supersonic_ramp.py`: M = 2.5 flow over a compression ramp (lower wall turns up 12deg).

```python
import sys, os

import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh, MeshPatch, viz as cfd_viz
from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall
from anvil.seed import seed; seed(force=True)
from anvil.registry import _rebuild_namespaces; _rebuild_namespaces()

# ─────────────────────────────────────────────────────────────────
# Parameters
# ─────────────────────────────────────────────────────────────────
M_inf       = 2.5
theta_deg   = 12.0      # ramp angle
gamma       = 1.4
R_gas       = 287.058
p_inf       = 101_325.0
T_inf       = 300.0
length      = 2.0
height      = 0.6
ramp_x0     = 0.6       # ramp starts here

print("=" * 60)
print(f"  Supersonic compression ramp  (M={M_inf}, theta={theta_deg}deg)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# Analytical check (oblique shock at ramp foot)
# ─────────────────────────────────────────────────────────────────
r = anvil.R.oblique_shock(M1=M_inf, theta_deg=theta_deg, gamma=gamma)
print(f"\n  Analytical oblique shock (ramp foot):")
print(f"  Shock angle beta   = {r['beta_deg']:.3f} deg")
print(f"  Downstream M2   = {r['M2']:.4f}")
print(f"  p2/p1           = {r['p2_p1']:.4f}")
print(f"  Attached:         {r['attached']}")

if r['attached']:
    # Second shock: reflected off upper wall (same theta, M2 incoming)
    r2 = anvil.R.oblique_shock(M1=r['M2'], theta_deg=theta_deg, gamma=gamma)
    print(f"\n  Reflected shock (upper wall):")
    print(f"  M3 = {r2['M2']:.4f}   p3/p1 = {r['p2_p1']*r2['p2_p1']:.4f}")

# ─────────────────────────────────────────────────────────────────
# PART 1, Mesh
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 1: Mesh with named patches (flat_wall + ramp)")
print("=" * 60)

# nx cells; ramp starts at cell i_ramp
nx, ny = 80, 30
i_ramp = int(nx * ramp_x0 / length)   # first ramp cell

patches = {
    "inlet":     MeshPatch("left",  0, ny),
    "outlet":    MeshPatch("right",  0, ny),
    "flat_wall": MeshPatch("bottom", 0, i_ramp),
    "ramp":      MeshPatch("bottom", i_ramp, nx),
    "ceiling":   MeshPatch("top", 0, nx),
}

mesh = Mesh.compression_ramp(
    length          = length,
    height          = height,
    ramp_x0         = ramp_x0,
    ramp_angle_deg  = theta_deg,
    nx              = nx,
    ny              = ny,
    title           = "supersonic_ramp",
    patches         = patches,
)

out_dir = os.path.dirname(os.path.abspath(__file__))
amesh_path = os.path.join(out_dir, "ramp.amesh")
mesh.to_file(amesh_path)
mesh = Mesh.from_file(amesh_path)   # round-trip test
mesh.info()

mesh_png = os.path.join(out_dir, "ramp_mesh.png")
mesh.plot(show=False, save_path=mesh_png)
print(f"  Mesh plot saved: {mesh_png}")

# ─────────────────────────────────────────────────────────────────
# PART 2, Solve
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Solver run")
print("=" * 60)

bcs = {
    "inlet":     SupersonicInlet(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
    "outlet":    SupersonicOutlet(),
    "flat_wall": SlipWall(),
    "ramp":      SlipWall(),
    "ceiling":   SlipWall(),
}

solver = CFDSolver(
    mesh        = mesh,
    bcs         = bcs,
    gamma       = gamma,
    R_gas       = R_gas,
    flux_scheme = "roe",
    order       = 2,
    time_scheme = "rk4",
    cfl         = 0.3,
    transient   = False,
)
solver.initialize(M=M_inf, p=p_inf, T=T_inf)

snap_dir = os.path.join(out_dir, "ramp_snapshots")
print(f"\n  Running ({mesh.nx}×{mesh.ny} cells, Roe, 2nd order)...")
result = solver.run(
    max_iter    = 2000,
    tol         = 1e-4,
    monitor     = True,
    verbose     = True,
    print_every = 250,
    save_every  = 500,
    save_field  = "p",
    save_dir    = snap_dir,
    save_vmin   = 100_000,   # fixed scale for all frames
    save_vmax   = 430_000,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3, Comparison
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Analytical vs Numerical comparison")
print("=" * 60)

# Sample downstream region (right half, lower half, behind first shock)
ds_i = slice(nx // 2, nx)
ds_j = slice(0, ny // 4)

M_ds  = result.M[ds_i, ds_j].mean()
p_ds  = result.p[ds_i, ds_j].mean()

if r['attached']:
    print(f"\n  {'':25s}  {'Analytical':>12s}  {'Numerical':>12s}  {'Error':>8s}")
    M_an = r['M2']; p_an = p_inf * r['p2_p1']
    print(f"  {'p2 [Pa]':25s}  {p_an:>12.1f}  {p_ds:>12.1f}  "
          f"{abs(p_ds-p_an)/p_an*100:>7.2f}%")
    print(f"  {'M2':25s}  {M_an:>12.4f}  {M_ds:>12.4f}  "
          f"{abs(M_ds-M_an)/M_an*100:>7.2f}%")
    print("  (Numerical value is area-averaged; boundary-layer and mesh effects)")

# ─────────────────────────────────────────────────────────────────
# PART 4, Save output files
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Output files")
print("=" * 60)

panel_png = os.path.join(out_dir, "ramp_fields.png")
cfd_viz.multi_field(result, fields=["M", "p", "T", "rho"],
                    show=False, save_path=panel_png)
print(f"  Multi-field plot: {panel_png}")

conv_png = os.path.join(out_dir, "ramp_convergence.png")
cfd_viz.convergence_png(result.history, conv_png, "Ramp: residual convergence")
print(f"  Convergence plot: {conv_png}")

vtk_path = os.path.join(out_dir, "ramp_flow.vtk")
result.to_vtk(vtk_path)
print(f"  VTK for ParaView: {vtk_path}")

# ─────────────────────────────────────────────────────────────────
# PART 5, Parallel ramp-angle sweep
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 5: Ramp-angle sweep (parallel=2)")
print("=" * 60)

def make_ramp_mesh(theta):
    i_r = int(40 * ramp_x0 / length)
    return Mesh.compression_ramp(
        length=length, height=height, ramp_x0=ramp_x0,
        ramp_angle_deg=theta, nx=40, ny=15,
        patches={
            "inlet":     MeshPatch("left",  0, 15),
            "outlet":    MeshPatch("right",  0, 15),
            "flat_wall": MeshPatch("bottom", 0, i_r),
            "ramp":      MeshPatch("bottom", i_r, 40),
            "ceiling":   MeshPatch("top", 0, 40),
        }
    )

# For the sweep we vary M_inf; theta is fixed at theta_deg
# (angle sweep would need a different relation wrapper)
_sweep_mesh = make_ramp_mesh(theta_deg)
_sweep_bcs  = {k: v for k, v in bcs.items()}   # reuse same BC types

def ramp_bcs(M, p, T, alpha=0.0):
    return {
        "inlet":     SupersonicInlet(M=M, p=p, T=T, gamma=gamma, R_gas=R_gas),
        "outlet":    SupersonicOutlet(),
        "flat_wall": SlipWall(),
        "ramp":      SlipWall(),
        "ceiling":   SlipWall(),
    }

sweep_solver = CFDSolver(
    mesh=_sweep_mesh, bcs=ramp_bcs(M_inf, p_inf, T_inf),
    gamma=gamma, R_gas=R_gas, flux_scheme="roe", order=2, cfl=0.3,
)
cfd_rel = sweep_solver.as_relation(
    inputs     = ["M_inf", "p_inf", "T_inf"],
    outputs    = ["M_max", "p_wall"],
    name       = "ramp_euler",
    bc_factory = ramp_bcs,
    run_kwargs = {"max_iter": 1000, "tol": 1e-3, "verbose": False},
)

sweep_sys = anvil.system("ramp_mach_sweep")
sweep_sys.add("M_inf", M_inf)
sweep_sys.add("p_inf", p_inf)
sweep_sys.add("T_inf", T_inf)
sweep_sys.use(cfd_rel)

mach_vals = np.array([2.0, 2.5, 3.0, 3.5])
print(f"\n  Sweeping M = {mach_vals}  (parallel=2) for theta = {theta_deg}deg...")
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2, skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# Analytical comparison
print("\n  Analytical comparison:")
print(f"  {'M_inf':>8s}  {'beta [deg]':>10s}  {'M2':>8s}  {'p2/p1':>8s}")
for M in mach_vals:
    ra = anvil.R.oblique_shock(M1=float(M), theta_deg=theta_deg, gamma=gamma)
    if ra["attached"]:
        print(f"  {M:>8.1f}  {ra['beta_deg']:>10.3f}  {ra['M2']:>8.4f}  {ra['p2_p1']:>8.4f}")
    else:
        print(f"  {M:>8.1f}  {'(detached)':>10s}  {'---':>8s}  {'---':>8s}")

# Cleanup
for f in ["ramp.amesh", "ramp_flow.vtk"]:
    fp = os.path.join(out_dir, f)
    if os.path.exists(fp): os.remove(fp)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

> Runs a full solve that takes a while; run the script locally to see its output.


## Example: 2D Euler CFD -- Supersonic flow over a wedge

`examples/ex_cfd_wedge.py`: Inviscid supersonic flow (M=2) over a 10-degree wedge.

```python
import os


import numpy as np
import anvil
from anvil.cfd import CFDSolver, Mesh, MeshPatch
from anvil.cfd.bc import SupersonicInlet, SupersonicOutlet, SlipWall, Farfield
from anvil.seed import seed

seed(force=True)
from anvil.registry import _rebuild_namespaces

_rebuild_namespaces()

# Quick-reference: uncomment to see all CFDSolver parameters and outputs
# anvil.lookup("CFDSolver")
# anvil.lookup("bc")
# anvil.lookup("mesh")

# ─────────────────────────────────────────────────────────────────
# PART 1, Analytical oblique shock (exact solution)
# ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("  PART 1: Analytical oblique shock solution")
print("=" * 60)

M_inf = 2.0
theta_deg = 10.0  # wedge half-angle
gamma = 1.4
p_inf = 101325.0  # Pa
T_inf = 300.0  # K
R_gas = 287.058  # J/kg/K

r = anvil.R.oblique_shock(M1=M_inf, theta_deg=theta_deg, gamma=gamma)
print(f"\n  Freestream M = {M_inf},  wedge half-angle = {theta_deg} deg")
print(f"  Shock attached: {r['attached']}")
print(
    f"  Shock angle beta = {r['beta_deg']:.3f} deg  (Mach angle = {np.degrees(np.arcsin(1 / M_inf)):.3f} deg)"
)
print(f"  Downstream M2   = {r['M2']:.4f}")
print(f"  p2/p1           = {r['p2_p1']:.4f}")
print(f"  T2/T1           = {r['T2_T1']:.4f}")
print(f"  rho2/rho1       = {r['rho2_rho1']:.4f}")

# Downstream conditions
p2 = p_inf * r["p2_p1"]
T2 = T_inf * r["T2_T1"]
rho2 = (p_inf / (R_gas * T_inf)) * r["rho2_rho1"]
print(f"\n  Downstream: p = {p2:.1f} Pa,  T = {T2:.1f} K,  M = {r['M2']:.4f}")

# ─────────────────────────────────────────────────────────────────
# PART 2, Numerical solution: anvil.cfd 2D Euler solver
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 2: Numerical 2D Euler solution")
print("=" * 60)

# Build body-fitted wedge mesh
# Domain: x in [0, 1] m,  y from wedge surface up to 0.6 m above
nx_main, ny_main = 80, 40
mesh = Mesh.wedge(
    half_angle_deg=theta_deg,
    chord=1.0,  # m
    height=0.6,  # m above wedge surface
    nx=nx_main,
    ny=ny_main,
    title="wedge_10deg",
    patches={
        "inlet":    MeshPatch("left",   0, ny_main),
        "outlet":   MeshPatch("right",  0, ny_main),
        "wall":     MeshPatch("bottom", 0, nx_main),
        "farfield": MeshPatch("top",    0, nx_main),
    },
)
mesh.info()

# Boundary conditions, use descriptive edge names (left/right/top/bottom)
bcs = {
    "inlet":   SupersonicInlet(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
    "outlet":  SupersonicOutlet(),
    "wall":    SlipWall(),
    "farfield": Farfield(M=M_inf, p=p_inf, T=T_inf, gamma=gamma, R_gas=R_gas),
}

# Solver: 2nd-order Roe with MUSCL, local time stepping, RK4
solver = CFDSolver(
    mesh=mesh,
    bcs=bcs,
    gamma=gamma,
    R_gas=R_gas,
    flux_scheme="roe",  # Roe approximate Riemann solver
    order=2,  # MUSCL + van Leer limiter
    time_scheme="rk4",  # 4-stage Runge-Kutta
    cfl=0.3,  # CFL number (0.3 recommended for 2nd order)
    transient=False,  # local time stepping for steady-state
)
solver.initialize(M=M_inf, p=p_inf, T=T_inf, alpha_deg=0.0)

# Run solver, watch residuals converge
print(f"\n  Running Euler solver ({mesh.nx}x{mesh.ny} cells, Roe flux, 2nd order)...")
out_dir = os.path.dirname(os.path.abspath(__file__))
result = solver.run(
    max_iter=3000,
    tol=1e-4,       # shock residual stagnates at ~1e-4 (truncation error)
    monitor=True,
    verbose=True,
    print_every=200,
    save_every=500,              # save PNG every 500 iters
    save_field="M",
    save_dir=os.path.join(out_dir, "wedge_snapshots"),
    save_vmin=1.4,               # fixed scale, all frames comparable
    save_vmax=2.1,
)

result.summary()

# ─────────────────────────────────────────────────────────────────
# PART 3, Comparison: analytical vs numerical
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 3: Analytical vs Numerical comparison")
print("=" * 60)

# Sample downstream region (right half of domain, above wall)
nx, ny = mesh.nx, mesh.ny
ds_i = slice(nx // 2, nx)  # downstream half
ds_j = slice(ny // 4, ny // 2)  # mid-domain height

M_ds = result.M[ds_i, ds_j].mean()
p_ds = result.p[ds_i, ds_j].mean()
T_ds = result.T[ds_i, ds_j].mean()

print(f"\n  Downstream region (x=[0.5,1.0], mid-height):")
print(f"  {'':20s}  {'Analytical':>12s}  {'Numerical':>12s}  {'Error %':>9s}")
print(
    f"  {'p2 [Pa]':20s}  {p2:>12.2f}  {p_ds:>12.2f}  {abs(p_ds - p2) / p2 * 100:>8.2f}%"
)
print(
    f"  {'T2 [K]':20s}  {T2:>12.3f}  {T_ds:>12.3f}  {abs(T_ds - T2) / T2 * 100:>8.2f}%"
)
print(
    f"  {'M2':20s}  {r['M2']:>12.4f}  {M_ds:>12.4f}  {abs(M_ds - r['M2']) / r['M2'] * 100:>8.2f}%"
)
print(f"\n  (numerical error expected ~1-5% at this resolution)")

# ─────────────────────────────────────────────────────────────────
# PART 4, Write output files for ParaView and Tecplot
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 4: Writing output files")
print("=" * 60)

out_dir = os.path.dirname(__file__)
result.to_vtk(os.path.join(out_dir, "wedge_flow.vtk"))
result.to_tecplot(os.path.join(out_dir, "wedge_flow.dat"))
result.to_restart(os.path.join(out_dir, "wedge_restart.npz"))
print("  -> Open wedge_flow.vtk in ParaView (File -> Open, then Apply)")
print("  -> Open wedge_flow.dat in Tecplot (Data -> Load Data File)")

# ─────────────────────────────────────────────────────────────────
# PART 5, Mach sweep using solver as Anvil Relation
#           Runs each Mach number in parallel threads
# ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PART 5: Mach number sweep (solver as Anvil Relation)")
print("=" * 60)

# BC factory, rebuilds BCs for each M_inf so sweep is physically correct
nx_sw, ny_sw = 40, 20
sweep_mesh = Mesh.wedge(
    half_angle_deg=theta_deg,
    chord=1.0,
    height=0.6,
    nx=nx_sw,
    ny=ny_sw,
    title="wedge_sweep",
    patches={
        "inlet":    MeshPatch("left",   0, ny_sw),
        "outlet":   MeshPatch("right",  0, ny_sw),
        "wall":     MeshPatch("bottom", 0, nx_sw),
        "farfield": MeshPatch("top",    0, nx_sw),
    },
)


def wedge_bcs(M, p, T, alpha=0.0):
    return {
        "inlet":    SupersonicInlet(M=M, p=p, T=T, gamma=gamma, R_gas=R_gas),
        "outlet":   SupersonicOutlet(),
        "wall":     SlipWall(),
        "farfield": Farfield(M=M, p=p, T=T, gamma=gamma, R_gas=R_gas),
    }


sweep_solver = CFDSolver(
    mesh=sweep_mesh,
    bcs=wedge_bcs(M_inf, p_inf, T_inf),  # placeholder; factory overrides
    gamma=gamma,
    R_gas=R_gas,
    flux_scheme="roe",
    order=2,
    cfl=0.3,
    transient=False,
)

# Wrap solver as a Relation: M_inf -> M_max, p_wall
cfd_rel = sweep_solver.as_relation(
    inputs=["M_inf", "p_inf", "T_inf"],
    outputs=["M_max", "p_wall"],
    name="wedge_euler",
    bc_factory=wedge_bcs,
    run_kwargs={"max_iter": 1500, "tol": 1e-4, "verbose": False},
)

# Build a simple System around it
sweep_sys = anvil.system("wedge_mach_sweep")
sweep_sys.add("M_inf", 2.0)
sweep_sys.add("p_inf", p_inf)
sweep_sys.add("T_inf", T_inf)
sweep_sys.use(cfd_rel)

print("\n  Sweeping M = 1.5, 2.0, 2.5, 3.0  (parallel=2)...")
mach_vals = np.array([1.5, 2.0, 2.5, 3.0])
sweep = sweep_sys.sweep("M_inf", mach_vals, parallel=2, skip_errors=True)
sweep.summary(outputs=["M_max", "p_wall"])

# Compare with analytical
print("\n  Analytical comparison:")
print(f"  {'M_inf':>8s}  {'beta [deg]':>12s}  {'p_wall/p_inf':>14s}")
for M in mach_vals:
    r_a = anvil.R.oblique_shock(M1=float(M), theta_deg=theta_deg, gamma=gamma)
    if r_a["attached"]:
        print(f"  {M:>8.1f}  {r_a['beta_deg']:>12.3f}  {r_a['p2_p1']:>14.4f}")
    else:
        print(f"  {M:>8.1f}  {'(detached)':>12s}  {'---':>14s}")

# Cleanup output files
# for f in ["wedge_flow.vtk", "wedge_flow.dat", "wedge_restart.npz"]:
#    fpath = os.path.join(out_dir, f)
#    if os.path.exists(fpath):
#        os.remove(fpath)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
print("""
  CFD solver architecture summary:
    Scheme:    2D cell-centred finite volume (ghost cells)
    Flux:      Roe approximate Riemann solver (with Harten entropy fix)
    Order:     2nd order MUSCL + van Leer limiter
    Time:      4-stage Runge-Kutta, local time stepping
    BCs:       SupersonicInlet, SupersonicOutlet, SlipWall, Farfield
    Output:    VTK legacy (.vtk, ParaView), Tecplot ASCII (.dat)

  Extensible to:
    - Viscous flows: add viscous_flux_2d() in flux.py
    - 3D:           add k-index in mesh and w-velocity in state
    - CLI adapter:  wrap solver in Adapter("su2_cfd", backend="cli", ...)
""")
```

> Runs a full solve that takes a while; run the script locally to see its output.


## Chemistry RSQs

`examples/ex_chemistry.py`: A tour of the chemistry relation pack: stoichiometry, gas laws, solutions,

```python
import anvil

print("=" * 60)
print("  Stoichiometry")
print("=" * 60)
print(f"  Moles in 18 g of water (M=18 g/mol): {anvil.R.moles_from_mass(m=0.018, M=0.018)['n']}")
print(f"  Percent yield (8.2 of 10)          : {anvil.R.percent_yield(actual=8.2, theoretical=10)['percent_yield']:.1f} %")
mol = anvil.R.molarity(n=0.5, V=0.002)
print(f"  Molarity (0.5 mol in 2 L)          : {mol['c']} ({mol['c_molar']:.3f} mol/L)")

print("\n" + "=" * 60)
print("  Gas laws")
print("=" * 60)
print(f"  Moles of gas (1 atm, 22.4 L, 273 K): {anvil.R.moles_ideal_gas(P=101325, V=0.0224140, T=273.15)['n']}")
print(f"  Combined gas law (double pressure) : "
      f"{anvil.R.combined_gas_law(P1=1e5, V1=1e-3, T1=300, P2=2e5, T2=300)['V2']}")

print("\n" + "=" * 60)
print("  Solutions and colligative properties")
print("=" * 60)
print(f"  Dilution (2 M, 10 mL to 0.5 M)     : {anvil.R.dilution(M1=2, V1=0.010, M2=0.5)['V2']}")
print(f"  Beer-Lambert absorbance            : {anvil.R.beer_lambert_absorbance(eps=100, l=0.01, c=1.0)['A']:.3f}")
print(f"  Freezing-point drop (0.5 m NaCl)   : {anvil.R.freezing_point_depression(i=2, Kf=1.86, m=0.5)['dTf']}")
print(f"  Osmotic pressure (1000 mol/m^3)    : {anvil.R.osmotic_pressure(i=1, M=1000, T=298.15)['Pi']}")

print("\n" + "=" * 60)
print("  Thermodynamics, kinetics, equilibrium")
print("=" * 60)
print(f"  Gibbs free energy (dH-TdS)         : {anvil.R.gibbs_free_energy(dH=-1e5, T=298.15, dS=-100)['dG']}")
print(f"  Gibbs from K=100                   : {anvil.R.gibbs_from_equilibrium_constant(K=100, T=298.15)['dG']}")
print(f"  Arrhenius k (Ea=100 kJ/mol, 300 K) : {anvil.R.arrhenius_rate_constant(A=1e13, Ea=1e5, T=300)['k']}")
print(f"  First-order half-life (k=6.93e-3)  : {anvil.R.first_order_half_life(k=0.00693)['t_half']}")

print("\n" + "=" * 60)
print("  Electrochemistry and acid-base")
print("=" * 60)
print(f"  Nernst potential (Q=1e-3, n=2)     : {anvil.R.nernst_cell_potential(E0=1.10, n=2, T=298.15, Q_rxn=1e-3)['E']}")
print(f"  pH of neutral water (1e-7 M)       : {anvil.R.ph_from_concentration(H_conc=1e-7)['pH']:.2f}")
print(f"  Buffer pH (pKa 4.76, 10:1 base)    : {anvil.R.henderson_hasselbalch(pKa=4.76, conc_base=1.0, conc_acid=0.1)['pH']:.2f}")
```

**Output:**

```
============================================================
  Stoichiometry
============================================================
  Moles in 18 g of water (M=18 g/mol): 1.0000 mol
  Percent yield (8.2 of 10)          : 82.0 %
  Molarity (0.5 mol in 2 L)          : 250.00 mol/m^3 (0.250 mol/L)

============================================================
  Gas laws
============================================================
  Moles of gas (1 atm, 22.4 L, 273 K): 1.0000 mol
  Combined gas law (double pressure) : 5.0000e-04 m^3

============================================================
  Solutions and colligative properties
============================================================
  Dilution (2 M, 10 mL to 0.5 M)     : 0.040000 m^3
  Beer-Lambert absorbance            : 1.000
  Freezing-point drop (0.5 m NaCl)   : 1.8600 K
  Osmotic pressure (1000 mol/m^3)    : 2.4790e+06 Pa

============================================================
  Thermodynamics, kinetics, equilibrium
============================================================
  Gibbs free energy (dH-TdS)         : -70185.00 J/mol
  Gibbs from K=100                   : -11416.02 J/mol
  Arrhenius k (Ea=100 kJ/mol, 300 K) : 3.8797e-05 s^-1
  First-order half-life (k=6.93e-3)  : 100.02 s

============================================================
  Electrochemistry and acid-base
============================================================
  Nernst potential (Q=1e-3, n=2)     : 1.1887 V
  pH of neutral water (1e-7 M)       : 7.00
... (1 more lines)
```


## Example: CoolProp Adapter -- Real-Fluid Properties in Anvil (real-only)

`examples/ex_coolprop_adapter.py`: the CoolProp adapter (rho, h, cp, mu, a) for several fluids and

```python
import anvil
from anvil import Q
from anvil.adapters.coolprop_props import coolprop_props, register

W = 64
print("=" * W)
print("  CoolProp Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs CoolProp; importing the module is always safe.
register()

try:
    # ── 1. Direct adapter calls over several fluids ──────────────────────────
    print("\n[1] Properties at T=300 K, P=101325 Pa")
    print(f"  {'fluid':8s}  {'rho':>10s}  {'cp':>10s}  {'a (m/s)':>9s}  {'source':>9s}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*9}  {'-'*9}")
    for fluid in ("Air", "N2", "O2", "CO2", "CH4"):
        r = coolprop_props(fluid=fluid, T=300.0, P=101325.0)
        print(f"  {fluid:8s}  {r['rho'].value:10.4f}  {r['cp'].value:10.1f}  "
              f"{r['a'].value:9.1f}  {str(r['source']):>9s}")

    # ── 2. Pipeline: adapter properties feed a Reynolds-number System ────────
    print("\n[2] Pipe-flow Reynolds number using adapter rho & mu")
    props = coolprop_props(fluid="Air", T=300.0, P=5e5)
    print(f"  rho    = {props['rho']}")
    print(f"  mu     = {props['mu']}  (source: {props['source']})")

    pipe = anvil.system("pipe_flow")
    pipe.add("rho", props["rho"].value, "kg/m^3")
    pipe.add("mu", props["mu"].value, "Pa*s")
    pipe.add("D_pipe", 0.05, "m")
    pipe.add("V_flow", 10.0, "m/s")

    def reynolds(rho, mu, D_pipe, V_flow):
        Re = rho * V_flow * D_pipe / mu
        return {"Re": Q(Re, "1")}
    pipe.use(reynolds)

    res = pipe.solve_forward()
    print(f"  Re     = {res['Re'].value:.0f}")

except ImportError as e:
    print("\n  CoolProp is not installed -- cannot run this example.")
    print(f"  {e}")
    print("\n  Install CoolProp to run this example: pip install CoolProp")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Curve Fitting and Data Tables

`examples/ex_curve_fitting.py`: the data-fitting RSQs that take ``x_data`` / ``y_data`` arrays and

```python
import numpy as np

import anvil

rng = np.random.default_rng(0)

print("=" * 60)
print("  Linear regression: y = 2 x + 1 (+ noise)")
print("=" * 60)

x = np.linspace(0, 10, 25)
y = 2.0 * x + 1.0 + rng.normal(0, 0.15, x.size)
lin = anvil.R.linear_regression(x_data=x, y_data=y)
print(f"  slope     = {lin['slope']:.4f}  (true 2.0)")
print(f"  intercept = {lin['intercept']:.4f}  (true 1.0)")
print(f"  R-squared = {lin['r_squared']:.5f},  RMSE = {lin['rmse']:.4f}")

print("\n" + "=" * 60)
print("  Polynomial fit: y = x^2 + 1 (exact)")
print("=" * 60)

xp = np.linspace(-3, 3, 21)
yp = xp**2 + 1.0
poly = anvil.R.poly_fit(x_data=xp, y_data=yp, degree=2)
coeffs = poly["coeffs"]
print(f"  coeffs (high->low) = "
      f"[{coeffs[0]:.4f}, {coeffs[1]:.4f}, {coeffs[2]:.4f}]  (true [1, 0, 1])")
print(f"  R-squared = {poly['r_squared']:.5f}")

print("\n" + "=" * 60)
print("  Power fit: y = 2 x^1.5")
print("=" * 60)

xw = np.linspace(1, 20, 20)
yw = 2.0 * xw**1.5
powr = anvil.R.power_fit(x_data=xw, y_data=yw)
print(f"  a = {powr['a']:.4f}  (true 2.0)")
print(f"  b = {powr['b']:.4f}  (true 1.5)")
print(f"  R-squared = {powr['r_squared']:.5f}")

print("\n" + "=" * 60)
print("  Exponential fit: y = 5 e^(0.3 x)")
print("=" * 60)

xe = np.linspace(0, 8, 20)
ye = 5.0 * np.exp(0.3 * xe)
expf = anvil.R.exp_fit(x_data=xe, y_data=ye)
print(f"  a = {expf['a']:.4f}  (true 5.0)")
print(f"  b = {expf['b']:.4f}  (true 0.3)")
print(f"  R-squared = {expf['r_squared']:.5f}")

print("\n  Each fit recovers the generating coefficients, confirming the")
print("  data-fitting RSQs are ready to drop into the workbench data tables.")
```

**Output:**

```
============================================================
  Linear regression: y = 2 x + 1 (+ noise)
============================================================
  slope     = 2.0028  (true 2.0)
  intercept = 0.9751  (true 1.0)
  R-squared = 0.99955,  RMSE = 0.1280

============================================================
  Polynomial fit: y = x^2 + 1 (exact)
============================================================
  coeffs (high->low) = [1.0000, 0.0000, 1.0000]  (true [1, 0, 1])
  R-squared = 1.00000

============================================================
  Power fit: y = 2 x^1.5
============================================================
  a = 2.0000  (true 2.0)
  b = 1.5000  (true 1.5)
  R-squared = 1.00000

============================================================
  Exponential fit: y = 5 e^(0.3 x)
============================================================
  a = 5.0000  (true 5.0)
  b = 0.3000  (true 0.3)
  R-squared = 1.00000

  Each fit recovers the generating coefficients, confirming the
  data-fitting RSQs are ready to drop into the workbench data tables.
```


## Example: Design of Experiments (DOE) + parallel sweeps on a built-in System.

`examples/ex_doe.py`

```python
import warnings

import numpy as np
import anvil
from anvil import doe


def main():
    warnings.simplefilter("ignore")  # quiet DOF/backend-fallback warnings for the demo

    # --- A built-in System ----------------------------------------------------
    nozzle = anvil.S.rocket_nozzle.copy()
    print("Inputs:", list(nozzle._quantities.keys()))

    # --- 1. Latin Hypercube DOE over two inputs -------------------------------
    bounds = {
        "P0": (3.0e6, 10.0e6),    # chamber pressure [Pa]
        "A_exit": (0.05, 0.30),   # exit area [m^2]
    }
    samples = doe.latin_hypercube(bounds, n=20, seed=7)
    print(f"\nGenerated {len(samples)} Latin Hypercube samples.")
    print("First sample:", {k: round(v, 4) for k, v in samples[0].items()})

    # Evaluate the design (parallel=4 -> process pool, auto-falls back to threads
    # for this registry-loaded System).
    design = doe.run_doe(
        nozzle, samples, outputs=["thrust", "Isp", "M_exit"], parallel=4
    )
    design.summary()

    thrust = design["thrust"]
    best = int(np.nanargmax(thrust))
    print(f"\nBest design (max thrust): sample #{best}")
    print(f"  P0     = {samples[best]['P0']/1e6:.3f} MPa")
    print(f"  A_exit = {samples[best]['A_exit']:.4f} m^2")
    print(f"  thrust = {thrust[best]:.1f} N")

    # --- 2. Sobol sampling (low-discrepancy) ----------------------------------
    sob = doe.sobol(bounds, n=8, seed=1)
    print(f"\nSobol design: {len(sob)} samples (power-of-two recommended).")

    # --- 3. Full-factorial grid -----------------------------------------------
    grid = doe.full_factorial({
        "P0": [4e6, 7e6, 10e6],
        "A_exit": [0.08, 0.16, 0.24],
    })
    print(f"Full-factorial design: {len(grid)} grid points (3 x 3).")

    # --- 4. Parallel parameter sweep ------------------------------------------
    print("\nParallel sweep of chamber pressure P0:")
    sweep = nozzle.sweep("P0", np.linspace(3e6, 10e6, 8), parallel=4)
    sweep.summary(outputs=["thrust", "Isp"])


if __name__ == "__main__":
    main()
```

**Output:**

```
Inputs: ['P0', 'T0', 'gamma', 'R_gas', 'A_throat', 'A_exit', 'P_amb']

Generated 20 Latin Hypercube samples.
First sample: {'P0': 4181216.5867, 'A_exit': 0.1138}

-------------------------------------------------------------------
  rocket_nozzle -- DOE  (20/20 succeeded)
-------------------------------------------------------------------
             P0       A_exit       thrust          Isp       M_exit
  -----------------------------------------------------------------
      4.181e+06       0.1138    6.072e+04        238.1        3.528
      4.829e+06       0.1472    6.976e+04        236.9        3.731
      7.795e+06      0.08908    1.236e+05          260        3.335
      8.248e+06       0.1647    1.288e+05        256.1         3.82
      3.071e+06      0.05665    4.477e+04        239.1        2.977
      3.944e+06        0.259    4.485e+04        186.5        4.182
      9.911e+06       0.2444    1.534e+05        253.9        4.136
      7.373e+06       0.1056    1.161e+05        258.3        3.469
      8.252e+06       0.2151    1.257e+05        249.8        4.033
      5.582e+06       0.1501    8.278e+04        243.2        3.747
      6.425e+06       0.1355    9.842e+04        251.2        3.666
      9.086e+06       0.2995    1.345e+05        242.7          4.3
  ... (8 more rows)
-------------------------------------------------------------------

Best design (max thrust): sample #6
  P0     = 9.911 MPa
  A_exit = 0.2444 m^2
  thrust = 153431.5 N

Sobol design: 8 samples (power-of-two recommended).
Full-factorial design: 9 grid points (3 x 3).

Parallel sweep of chamber pressure P0:
... (16 more lines)
```


## Extended Engineering RSQs

`examples/ex_extended_rsqs.py`: the extended relation pack that fills common gaps across

```python
import anvil

print("=" * 60)
print("  Compressible duct flow")
print("=" * 60)

fanno = anvil.R.fanno_flow(M=2.0, gamma=1.4)
print(f"  Fanno   M=2.0 : fL*/D_max = {fanno['fLD_max']:.4f}, "
      f"T/T* = {fanno['T_Tstar']:.4f}")

rayleigh = anvil.R.rayleigh_flow(M=0.5, gamma=1.4)
print(f"  Rayleigh M=0.5: T0/T0* = {rayleigh['T0_T0star']:.4f}, "
      f"P/P* = {rayleigh['P_Pstar']:.4f}")

mu = anvil.R.mach_angle(M=2.0)
print(f"  Mach angle M=2.0 : mu = {mu['mu_deg']:.3f} deg")

print("\n" + "=" * 60)
print("  Internal and external flow")
print("=" * 60)

cole = anvil.R.colebrook_friction(Re=1e5, rel_roughness=0.001)
haal = anvil.R.haaland_friction(Re=1e5, rel_roughness=0.001)
print(f"  Darcy friction (Re=1e5, e/D=0.001):")
print(f"    Colebrook (implicit) = {cole['f_darcy']:.5f}  [{cole['regime']}]")
print(f"    Haaland   (explicit) = {haal['f_darcy']:.5f}")

dp = anvil.R.pipe_pressure_drop(f_darcy=cole["f_darcy"], L=50, D=0.1,
                                rho=998, V=2.0)
print(f"  Pipe drop (50 m, D=0.1 m, water @ 2 m/s): "
      f"dP = {dp['dP']}, head = {dp['head_loss']}")

cf = anvil.R.skin_friction_flat_plate(Re_L=1e6, regime="auto")
print(f"  Flat-plate skin friction (Re_L=1e6): Cf = {cf['Cf']:.5f} "
      f"[{cf['regime']}]")

print("\n" + "=" * 60)
print("  Heat transfer")
print("=" * 60)

db = anvil.R.dittus_boelter(Re=1e5, Pr=0.7, k_fluid=0.026, D=0.05,
                            heating=True)
print(f"  Dittus-Boelter (air in tube): Nu = {db['Nu']:.1f}, "
      f"h = {db['h_conv']}")

hx = anvil.R.lmtd(T_hot_in=150, T_hot_out=90, T_cold_in=30, T_cold_out=70,
                  flow="counter")
print(f"  LMTD (counterflow): {hx['LMTD']}")

bi = anvil.R.biot_number(h_conv=50, L_char=0.01, k_solid=200)
print(f"  Biot number: Bi = {bi['Bi']:.4f} "
      f"(lumped valid = {bi['lumped_valid']})")

lc = anvil.R.lumped_capacitance(T0=200, T_inf=25, t=60, h_conv=50,
                                A_surf=0.02, rho=2700, V_vol=1e-4, cp=900)
print(f"  Lumped cooling after 60 s: T = {lc['T_t']} (tau = {lc['tau']})")

print("\n" + "=" * 60)
print("  Structures")
print("=" * 60)

tor = anvil.R.torsion_circular_shaft(torque=500, d_outer=0.04, L=1.0,
                                     G=79e9, d_inner=0.0)
print(f"  Solid shaft torsion (T=500 N.m, d=40 mm): "
      f"tau_max = {tor['tau_max']}, twist = {tor['twist_deg']:.3f} deg")

ps = anvil.R.principal_stresses_2d(sigma_x=80e6, sigma_y=20e6, tau_xy=30e6)
print(f"  Principal stresses: s1 = {ps['sigma_1']}, s2 = {ps['sigma_2']}, "
      f"tau_max = {ps['tau_max']}")

vm = anvil.R.von_mises_stress(sigma_x=80e6, sigma_y=20e6, sigma_z=0,
                              tau_xy=30e6, tau_yz=0, tau_zx=0)
print(f"  Von Mises equivalent stress: {vm['sigma_vm']}")

print("\n" + "=" * 60)
print("  Ideal cycles")
print("=" * 60)

carnot = anvil.R.carnot_efficiency(T_hot=800, T_cold=300)
print(f"  Carnot (800 K / 300 K): eta = {carnot['eta_carnot']:.4f}, "
      f"COP_hp = {carnot['COP_heat_pump']:.3f}")

brayton = anvil.R.brayton_ideal(pressure_ratio=15, gamma=1.4,
                                T_min=300, T_max=1600)
print(f"  Ideal Brayton (rp=15): eta = {brayton['eta_thermal']:.4f}, "
      f"back-work ratio = {brayton['back_work_ratio']:.4f}")
```

**Output:**

```
============================================================
  Compressible duct flow
============================================================
  Fanno   M=2.0 : fL*/D_max = 0.3050, T/T* = 0.6667
  Rayleigh M=0.5: T0/T0* = 0.6914, P/P* = 1.7778
  Mach angle M=2.0 : mu = 30.000 deg

============================================================
  Internal and external flow
============================================================
  Darcy friction (Re=1e5, e/D=0.001):
    Colebrook (implicit) = 0.02217  [turbulent]
    Haaland   (explicit) = 0.02197
  Pipe drop (50 m, D=0.1 m, water @ 2 m/s): dP = 22130.19 Pa, head = 2.2612 m
  Flat-plate skin friction (Re_L=1e6): Cf = 0.00467 [turbulent]

============================================================
  Heat transfer
============================================================
  Dittus-Boelter (air in tube): Nu = 199.4, h = 103.70 W/m^2/K
  LMTD (counterflow): 69.5212 K
  Biot number: Bi = 0.0025 (lumped valid = True)
  Lumped cooling after 60 s: T = 161.71 K (tau = 243.00 s)

============================================================
  Structures
============================================================
  Solid shaft torsion (T=500 N.m, d=40 mm): tau_max = 3.9789e+07 Pa, twist = 1.443 deg
  Principal stresses: s1 = 9.2426e+07 Pa, s2 = 7.5736e+06 Pa, tau_max = 4.2426e+07 Pa
  Von Mises equivalent stress: 8.8882e+07 Pa

============================================================
  Ideal cycles
============================================================
... (2 more lines)
```


## Example: FEniCSx FEM Adapter (real only -- requires dolfinx)

`examples/ex_fenics_adapter.py`: fenics_linear_elasticity and fenics_heat_conduction.

```python
import sys, os

import numpy as np
import anvil
from anvil.adapters import fenics_fem
from anvil.adapters.fenics_fem import (
    fenics_linear_elasticity, fenics_heat_conduction, register
)

if not fenics_fem.is_available():
    print("FEniCSx (dolfinx) not installed -- skipping example.")
    print("Install: conda install -c conda-forge fenics-dolfinx mpich")
    raise SystemExit(0)

# ── Linear elasticity: cantilever box ────────────────────────────────────────
print("=== FEniCSx linear elasticity: cantilever box ===")
r = fenics_linear_elasticity(
    E=200e9, nu=0.3,
    Lx=1.0, Ly=0.05, Lz=0.05,
    F_distributed=1e4,    # N/m^2 on top face
    nx=20, ny=4, nz=4,
)
print(f"  Max displacement = {r['max_displacement']}")
print(f"  Max von Mises    = {r['max_von_mises']}")
print(f"  source: {r['source']}")
# Analytical check: δ = wL⁴/(8EI)
import math
w = 1e4 * 0.05
I = 0.05 * 0.05**3 / 12
delta_analytical = w * 1.0**4 / (8 * 200e9 * I)
print(f"  Analytical δ     = {delta_analytical*1000:.4f} mm  (Euler-Bernoulli check)")

# ── Geometry sensitivity: deflection vs length ───────────────────────────────
print("\n=== Deflection vs beam length (E=200GPa, Ly=Lz=5cm, F=10kPa) ===")
sys_ = anvil.system("fenics_length_sweep")
sys_.add("E",            200e9)
sys_.add("nu",           0.3)
sys_.add("Lx",           1.0)
sys_.add("Ly",           0.05)
sys_.add("Lz",           0.05)
sys_.add("F_distributed", 1e4)
sys_.add("nx",           20)
sys_.add("ny",           4)
sys_.add("nz",           4)
sys_.use(fenics_linear_elasticity)

Lx_vals = np.linspace(0.5, 2.0, 6)
sweep   = sys_.sweep("Lx", Lx_vals)
print(f"  {'Lx [m]':>7}  {'δ_max [mm]':>12}  {'σ_vm [MPa]':>12}")
for i in range(len(Lx_vals)):
    row  = sweep.table.iloc[i]
    d = row["max_displacement"]
    s = row["max_von_mises"]
    d_mm  = float(d.si) * 1000 if hasattr(d, "si") else float(d) * 1000
    s_mpa = float(s.si) / 1e6  if hasattr(s, "si") else float(s) / 1e6
    print(f"  {Lx_vals[i]:7.2f}  {d_mm:12.3f}  {s_mpa:12.2f}")
print("  (δ ∝ L⁴, σ ∝ L²: doubling length → 16× more deflection, 4× more stress)")

# ── Heat conduction ────────────────────────────────────────────────────────────
print("\n=== FEniCSx heat conduction: aluminium rod ===")
r2 = fenics_heat_conduction(
    k=205.0,       # W/m/K  (aluminium)
    Lx=0.5,        # m
    Ly=0.02, Lz=0.02,
    T_left=600.0,  # K
    T_right=300.0, # K
    Q_vol=0.0,
    nx=20, ny=5, nz=5,
)
print(f"  T_max     = {r2['T_max']}")
print(f"  Heat flux = {r2['heat_flux']}")
print(f"  source: {r2['source']}")
# 1D Fourier check: Q = k·A·ΔT/L
A = 0.02 * 0.02
Q_analytical = 205.0 * A * (600.0 - 300.0) / 0.5
print(f"  Analytical Q = {Q_analytical:.2f} W")

# ── Thermal sensitivity: conductivity sweep ────────────────────────────────────
print("\n=== Heat flux vs thermal conductivity (ΔT=300K, L=0.5m) ===")
sys2 = anvil.system("fenics_k_sweep")
sys2.add("k",       205.0)
sys2.add("Lx",      0.5)
sys2.add("Ly",      0.02)
sys2.add("Lz",      0.02)
sys2.add("T_left",  600.0)
sys2.add("T_right", 300.0)
sys2.add("Q_vol",   0.0)
sys2.add("nx",      20)
sys2.add("ny",      5)
sys2.add("nz",      5)
sys2.use(fenics_heat_conduction)

k_vals = [15.0, 45.0, 100.0, 205.0, 385.0]   # steel, Ti, Al alloy, Al, Cu
labels = ["Steel", "Ti alloy", "Al alloy", "Aluminium", "Copper"]
sweep2 = sys2.sweep("k", k_vals)
print(f"  {'Material':>12}  {'k [W/mK]':>10}  {'Q [W]':>8}")
for i, (mat, k) in enumerate(zip(labels, k_vals)):
    row = sweep2.table.iloc[i]
    q   = row["heat_flux"]
    q_w = float(q.si) if hasattr(q, "si") else float(q)
    print(f"  {mat:>12}  {k:10.1f}  {q_w:8.3f}")
print("  (Q ∝ k: linear as expected from Fourier's law)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: fenics_linear_elasticity, fenics_heat_conduction → domain fem.fenics")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Jet Engine Cycle Analysis (GasTurb style)

`examples/ex_jet_engine_cycle.py`

```python
from anvil import propulsion as jet

print("=" * 60)
print("  Turbojet -- cruise design point")
print("=" * 60)

tj = jet.build_turbojet()
tj.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
res = tj.solve()
res.summary(keys=["specific_thrust", "thrust", "TSFC", "far",
                  "thermal_eff", "propulsive_eff", "overall_eff", "M9"])

print("\n  Station stagnation conditions:")
print(jet.station_table(res))

print("\n" + "=" * 60)
print("  Two-spool turbofan (bypass ratio 5)")
print("=" * 60)

tf = jet.build_turbofan()
tf.set(M0=0.80, pi_f=1.6, pi_c=22, bypass=5, T04=1550, mdot=30)
rtf = tf.solve()
rtf.summary(keys=["specific_thrust", "thrust", "TSFC",
                  "thermal_eff", "propulsive_eff", "overall_eff"])
print("\n  The high-bypass fan trades specific thrust for a much lower TSFC")
print("  and higher propulsive efficiency than the bare turbojet above.")

print("\n" + "=" * 60)
print("  Sweep: compressor pressure ratio (turbojet)")
print("=" * 60)

tj2 = jet.build_turbojet()
tj2.set(M0=0.80, T04=1500)
sweep = tj2.sweep("pi_c", [6, 10, 15, 20, 25, 30, 40])
sweep.summary(outputs=["specific_thrust", "TSFC", "thermal_eff"])
print("\n  Higher pressure ratio lowers TSFC (better fuel economy), while")
print("  specific thrust peaks at a moderate pressure ratio.")

print("\n" + "=" * 60)
print("  Optimize: pressure ratio for maximum specific thrust")
print("=" * 60)

opt = jet.build_turbojet()
opt.set(M0=0.80, T04=1500)
best = opt.optimize("specific_thrust", {"pi_c": (4, 45)},
                    minimize=False, seed=1)
print(f"  Best compressor pressure ratio : {best.x['pi_c']:.2f}")
print(f"  Maximum specific thrust        : {best.fun:.1f} N per kg/s")

print("\n" + "=" * 60)
print("  Afterburning turbojet (reheat to 2000 K)")
print("=" * 60)

ab = jet.build_turbojet_ab()
ab.set(M0=0.90, pi_c=10, T04=1500, T07=2000, mdot=25)
rab = ab.solve()
rab.summary(keys=["specific_thrust", "thrust", "TSFC", "far_total",
                 "thermal_eff", "M9"])
print("\n  The afterburner adds fuel downstream of the turbine, raising")
print("  specific thrust sharply at the cost of a much higher TSFC.")

print("\n" + "=" * 60)
print("  Turboprop / turboshaft (shaft-power output)")
print("=" * 60)

tp = jet.build_turboprop()
tp.set(M0=0.50, pi_c=10, T04=1400, mdot=15)
rtp = tp.solve()
rtp.summary(keys=["shaft_power", "specific_power", "PSFC", "thermal_eff"])
print("\n  A turboprop extracts nearly all the exhaust energy as shaft power")
print("  instead of jet thrust, reported here as power-specific fuel burn.")

print("\n" + "=" * 60)
print("  Cycle diagrams (T-s and h-s / Mollier)")
print("=" * 60)

diag = jet.build_turbojet()
diag.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
rdiag = diag.solve()
for kind, fname in [("Ts", "jet_cycle_Ts.png"), ("hs", "jet_cycle_hs.png")]:
    try:
        fig = jet.cycle_diagram(rdiag, kind=kind)
        fig.savefig(f"examples/{fname}", dpi=90, bbox_inches="tight")
        print(f"  Saved {kind} diagram to examples/{fname}")
    except Exception as exc:  # headless / no display: skip gracefully
        print(f"  Skipped {kind} diagram ({exc})")
```

**Output:**

```
============================================================
  Turbojet -- cruise design point
============================================================

--------------------------------------------------------
  turbojet -- results
--------------------------------------------------------
  specific_thrust           663.09 N
  thrust                    16577.23 N
  TSFC                      3.6810e-05
  far                       0.024408
  thermal_eff               0.235274
  propulsive_eff            0.776715
  overall_eff               0.182741
  M9                        1.0000
--------------------------------------------------------

  Station stagnation conditions:
   st  location              T0 [K]    P0 [kPa]
  ---------------------------------------------
    0  ambient                288.1       101.3
    2  comp face              329.8       161.1
    3  comp exit              721.7      1932.9
    4  turbine inlet         1500.0      1855.6
    5  turbine exit          1161.9       576.4
    9  core nozzle            996.0       311.1

============================================================
  Two-spool turbofan (bypass ratio 5)
============================================================

--------------------------------------------------------
  turbofan -- results
--------------------------------------------------------
... (78 more lines)
```


## Example: Meshing Adapter -- Parametric Geometry in Anvil (real-only)

`examples/ex_meshing_adapter.py`: the mesh_box and mesh_cylinder adapters: node/element counts

```python
import anvil
from anvil import Q
from anvil.adapters.meshing_geom import mesh_box, mesh_cylinder, register

W = 64
print("=" * W)
print("  Meshing Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs gmsh; importing the module is always safe.
register()

try:
    # ── 1. Box mesh refinement study ─────────────────────────────────────────
    print("\n[1] Box (1.0 x 0.5 x 0.2 m) mesh vs element size")
    print(f"  {'elem_size':>10s}  {'n_nodes':>9s}  {'n_elem':>9s}  {'src':>6s}")
    print(f"  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*6}")
    for h in (0.1, 0.05, 0.025):
        r = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=h)
        print(f"  {h:10.3f}  {int(r['n_nodes']):9d}  "
              f"{int(r['n_elements']):9d}  {str(r['source']):>6s}")

    # ── 2. Cylinder mesh ─────────────────────────────────────────────────────
    print("\n[2] Cylinder (r=0.5 m, h=1.0 m) mesh")
    c = mesh_cylinder(radius=0.5, height=1.0, elem_size=0.1)
    print(f"  n_nodes   = {int(c['n_nodes'])}")
    print(f"  n_elements= {int(c['n_elements'])}")
    print(f"  bbox_vol  = {c['bbox_vol']}  (source: {c['source']})")

    # ── 3. Pipeline: estimate solver memory from element count ───────────────
    print("\n[3] System: solver memory estimate from box mesh")
    mesh = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=0.05)
    job = anvil.system("mesh_job")
    job.add("n_elements", int(mesh["n_elements"]), "1")
    job.add("bytes_per_elem", 2000.0, "1")

    def memory(n_elements, bytes_per_elem):
        mem_mb = n_elements * bytes_per_elem / 1e6
        return {"mem_MB": Q(mem_mb, "1")}
    job.use(memory)
    res = job.solve_forward()
    print(f"  mem_MB     = {res['mem_MB'].value:.1f} MB")

except ImportError as e:
    print("\n  gmsh is not installed -- cannot run this example.")
    print(f"  {e}")
    print("\n  Install gmsh to run this example: pip install gmsh")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: Differential Equations in Anvil

`examples/ex_ode_patterns.py`: Shows three patterns for using differential equations within the framework

```python
import sys, os

import numpy as np
import anvil
from anvil import Q, solvers

print("=" * 60)
print("  Pattern A -- Direct ODE (no System)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN A: call solve_ode directly.
#
# Problem: two-species radioactive decay chain
#   dN1/dt = -λ1 * N1
#   dN2/dt =  λ1 * N1  -  λ2 * N2
#
# Write the RHS as a plain function f(t, y) -> dy/dt.
# Call solvers.solve_ode() with the method named explicitly.
# ─────────────────────────────────────────────────────────────────

lambda1 = 0.05    # 1/s  (parent decay constant)
lambda2 = 0.10    # 1/s  (daughter decay constant)
N0      = [1000.0, 0.0]  # initial populations

def decay_rhs(t, y):
    N1, N2 = y
    return [
        -lambda1 * N1,
         lambda1 * N1 - lambda2 * N2,
    ]

result = solvers.solve_ode(
    decay_rhs,
    t_span=(0, 60),
    y0=N0,
    method="RK45",         # explicit -- good for non-stiff problems
    t_eval=np.linspace(0, 60, 300),
    rtol=1e-8,
    atol=1e-10,
    verbose=True,
)

t   = result["t"]
N1  = result["y"][0]
N2  = result["y"][1]

print(f"\n  At t=60 s:")
print(f"    N1 = {N1[-1]:.2f}  (expect {N0[0]*np.exp(-lambda1*60):.2f})")
print(f"    N2 = {N2[-1]:.2f}")
print(f"    Peak N2 at t = {t[np.argmax(N2)]:.2f} s")

# result["sol"] is the scipy OdeResult; .sol is the dense callable
print(f"    N1 at t=10 s (dense): {result['sol'].sol(10)[0]:.2f}")


print("\n" + "=" * 60)
print("  Pattern B -- ODE inside a Relation (System integration)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN B: wrap the ODE call inside a Relation.
#
# Problem: vertical rocket burn.
#   dv/dt = F_thrust/m - g - (0.5*Cd*A*rho*v^2)/m
#   dm/dt = -mdot
#   dh/dt = v
#
# The Relation takes design parameters, integrates the ODE,
# returns summary scalars (burnout velocity, peak altitude).
# These scalars can then feed other Relations in the same System.
# ─────────────────────────────────────────────────────────────────

def rocket_burn(F_thrust, mdot, Cd, A_ref, m_dry, m_prop, rho_air=1.225, g=9.81):
    """
    Integrate vertical rocket burn ODE from liftoff to burnout.
    Returns peak velocity, burnout altitude, burnout time.
    """
    m0       = m_dry + m_prop
    t_burn   = m_prop / mdot           # burnout time

    def rhs(t, state):
        v, h, m = state
        if m <= m_dry:
            # coast phase -- no thrust
            F = 0.0
            dm = 0.0
        else:
            F  = F_thrust
            dm = -mdot

        drag  = 0.5 * Cd * A_ref * rho_air * v * abs(v)
        dvdt  = (F - drag) / m - g
        dhdt  = v
        dmdt  = dm
        return [dvdt, dhdt, dmdt]

    # Event: burnout (mass reaches m_dry)
    def burnout(t, state):
        return state[2] - m_dry
    burnout.terminal  = True
    burnout.direction = -1

    sol = solvers.solve_ode(
        rhs,
        t_span=(0, t_burn * 1.5),    # generous span; event stops it
        y0=[0.0, 0.0, m0],
        method="RK45",
        events=burnout,
        rtol=1e-7,
        atol=1e-9,
    )

    v_burnout = float(sol["y"][0, -1])
    h_burnout = float(sol["y"][1, -1])
    t_burnout = float(sol["t"][-1])

    return {
        "v_burnout":  Q(v_burnout, "m/s"),
        "h_burnout":  Q(h_burnout, "m"),
        "t_burnout":  Q(t_burnout, "s"),
        "delta_v":    Q(v_burnout, "m/s"),   # no gravity / drag: Tsiolkovsky would give more
    }


def coast_to_apogee(v_burnout, h_burnout, g=9.81):
    """After burnout, coast phase: v^2 = v0^2 - 2*g*dh."""
    dh_coast = v_burnout**2 / (2 * g)
    h_apogee = h_burnout + dh_coast
    return {
        "dh_coast":  Q(dh_coast, "m"),
        "h_apogee":  Q(h_apogee, "m"),
    }


# Build the System -- ODE Relation sits alongside algebraic Relation
rocket = anvil.system("sounding_rocket")
rocket.add("F_thrust",  10000, "N",    desc="Thrust")
rocket.add("mdot",        5.0, "kg/s", desc="Mass flow rate")
rocket.add("Cd",          0.3,         desc="Drag coefficient")
rocket.add("A_ref",      0.02, "m^2",  desc="Reference area")
rocket.add("m_dry",      20.0, "kg",   desc="Dry mass")
rocket.add("m_prop",     30.0, "kg",   desc="Propellant mass")

rocket.use(rocket_burn)       # ODE inside -- solves internally, returns scalars
rocket.use(coast_to_apogee)   # algebraic -- uses burnout scalars from ODE above

result = rocket.solve_forward()
result.summary(keys=["F_thrust", "m_dry", "m_prop",
                      "v_burnout", "h_burnout", "t_burnout", "h_apogee"])

print(f"\n  Apogee: {result['h_apogee'].to('km')}")
print(f"  Burnout velocity: {result['v_burnout']}")


print("\n" + "=" * 60)
print("  Pattern B -- Sweep over propellant mass")
print("=" * 60)

# Sweep works normally -- the ODE re-integrates for each point
sweep = rocket.sweep("m_prop", np.linspace(10, 60, 8), parallel=4)
sweep.summary(outputs=["v_burnout", "h_burnout", "h_apogee"])


print("\n" + "=" * 60)
print("  Pattern C -- Stiff ODE (combustion kinetics stub)")
print("=" * 60)

# ─────────────────────────────────────────────────────────────────
# PATTERN C: use solve_ode_stiff for stiff problems.
#
# Problem: simplified A -> B -> C kinetics (two-step first-order)
#   The second step is 1000× faster -> stiff system.
#   RK45 would need tiny steps; BDF handles it efficiently.
# ─────────────────────────────────────────────────────────────────

k1 = 1.0      # slow step A -> B
k2 = 1000.0   # fast step B -> C  (stiffness ratio = 1000)

def kinetics_rhs(t, y):
    A, B, C = y
    return [
        -k1 * A,
         k1 * A - k2 * B,
         k2 * B,
    ]

sol_stiff = solvers.solve_ode_stiff(
    kinetics_rhs,
    t_span=(0, 5),
    y0=[1.0, 0.0, 0.0],
    method="BDF",          # implicit -- handles stiff systems efficiently
    t_eval=np.linspace(0, 5, 200),
    rtol=1e-6,
    atol=1e-10,
    verbose=True,
)

A_final = sol_stiff["y"][0, -1]
C_final = sol_stiff["y"][2, -1]
print(f"\n  At t=5 s:")
print(f"    A = {A_final:.6f}  (expect {np.exp(-k1*5):.6f})")
print(f"    C = {C_final:.6f}  (expect ~{1 - np.exp(-k1*5):.6f})")
print(f"    Steps taken: {sol_stiff['nfev']} RHS evaluations")
print(f"    (RK45 would need ~{int(k2*5/1e-4):,} steps to stay stable)")


print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
print("""
  Summary of patterns:

  Pattern A -- Direct solve_ode / solve_ode_stiff / solve_bvp call.
    When: self-contained ODE, fixed parameters, time-history output.
    How:  write f(t, y), call solvers.solve_ode(..., method="RK45").

  Pattern B -- ODE wrapped inside a Relation.
    When: ODE parameters come from inputs or other equations in a System.
    How:  Relation takes scalar inputs -> calls solve_ode inside -> returns
          scalar summary outputs -> feeds rest of System normally.
          Sweep, sensitivity analysis, and composition all work.

  Pattern C -- Stiff ODE.
    Same as A or B, but use solve_ode_stiff(..., method="BDF").
    BDF/Radau handle k_fast/k_slow >> 1 without tiny step sizes.

  Why not put RHS in the registry?
    The RHS function (f(t,y)) is problem-specific physics -- it CAN be
    registered as an RSQ if you want to reuse it:
      anvil.push(decay_rhs, domain="nuclear", tags=["decay", "ODE"])
    But solve_ode itself is math machinery, not physics -- it stays in
    anvil.solvers, callable anywhere.
""")
```

**Output:**

```
============================================================
  Pattern A -- Direct ODE (no System)
============================================================
  ODE t = 6.0701e+00  (y[0] = 7.3820e+02)
  ODE t = 1.2185e+01  (y[0] = 5.4373e+02)
  ODE t = 1.8226e+01  (y[0] = 4.0199e+02)
  ODE t = 2.4521e+01  (y[0] = 2.9345e+02)
  ODE t = 3.0702e+01  (y[0] = 2.1543e+02)
  ODE t = 3.6762e+01  (y[0] = 1.5912e+02)
  ODE t = 4.3352e+01  (y[0] = 1.1445e+02)
  ODE t = 4.9727e+01  (y[0] = 8.3210e+01)
  ODE t = 5.5762e+01  (y[0] = 6.1537e+01)
  ODE converged: 338 function evaluations, t_final = 6.0000e+01

  At t=60 s:
    N1 = 49.79  (expect 49.79)
    N2 = 47.31
    Peak N2 at t = 13.85 s
    N1 at t=10 s (dense): 606.53

============================================================
  Pattern B -- ODE inside a Relation (System integration)
============================================================

--------------------------------------------------------
  sounding_rocket -- results
--------------------------------------------------------
  F_thrust                  10000.00 N
  m_dry                     20.0000 kg
  m_prop                    30.0000 kg
                            ---
  v_burnout                 1297.48 m/s
  h_burnout                 3889.54 m
  t_burnout                 6.0000 s
... (577 more lines)
```


## Example: OpenFOAM CFD Adapter (real only -- requires OpenFOAM on PATH)

`examples/ex_openfoam_adapter.py`: openfoam_incompressible on a real, prepared OpenFOAM case.

```python
import sys, os

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
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: OpenMDAO MDO Adapter (real only -- requires openmdao)

`examples/ex_openmdo_adapter.py`: openmdo_sellar, openmdo_beam, and the make_openmdo_adapter

```python
import sys, os

import numpy as np
import anvil
from anvil.adapters import openmdo_wrap
from anvil.adapters.openmdo_wrap import (
    openmdo_sellar, openmdo_beam, make_openmdo_adapter, register
)

if not openmdo_wrap.is_available():
    print("OpenMDAO not installed -- skipping example.")
    print("Install: pip install openmdao")
    raise SystemExit(0)

# ── Sellar benchmark ──────────────────────────────────────────────────────────
print("=== Sellar coupled MDO benchmark ===")
r = openmdo_sellar(x1=1.0, z1=5.0, z2=2.0)
print(f"  f  = {r['f']:.4f}  (objective, minimize)")
print(f"  g1 = {r['g1']:.4f}  (constraint, feasible if <= 0)")
print(f"  g2 = {r['g2']:.4f}  (constraint, feasible if <= 0)")
print(f"  y1 = {r['y1']:.4f}  (coupling variable, discipline 1)")
print(f"  y2 = {r['y2']:.4f}  (coupling variable, discipline 2)")

# ── Sweep: Sellar objective vs z1 ─────────────────────────────────────────────
print("\n=== Sellar objective vs z1 (x1=1, z2=2) ===")
sys_ = anvil.system("sellar_z1_sweep")
sys_.add("x1", 1.0)
sys_.add("z1", 5.0)
sys_.add("z2", 2.0)
sys_.use(openmdo_sellar)

z1_vals = np.linspace(1.0, 8.0, 8)
sweep   = sys_.sweep("z1", z1_vals)

print(f"  {'z1':>5}  {'f':>8}  {'g1':>7}  {'g2':>7}  feasible?")
for i in range(len(z1_vals)):
    row  = sweep.table.iloc[i]
    feas = "YES" if row["g1"] <= 0 and row["g2"] <= 0 else " no"
    print(f"  {row['z1']:5.2f}  {row['f']:8.4f}  {row['g1']:7.4f}  {row['g2']:7.4f}  {feas}")
print("  (g2 = y2 - 24; tends infeasible at high z1 due to y2 growth)")

# ── Cantilever beam ───────────────────────────────────────────────────────────
print("\n=== OpenMDAO cantilever beam ===")
r2 = openmdo_beam(
    F_tip=5000.0,    # N
    L_beam=2.0,      # m
    E=70e9,          # Pa (aluminium)
    b=0.05,          # m
    h=0.10,          # m
)
print(f"  Deflection = {r2['deflection']}")
print(f"  Max stress = {r2['max_stress']}")
print(f"  I_moment   = {r2['I_moment']}")

# ── Beam sensitivity: deflection vs cross-section height ─────────────────────
print("\n=== Beam deflection vs height h (F=5kN, L=2m, E=70GPa, b=0.05) ===")
sys2 = anvil.system("beam_height_sweep")
sys2.add("F_tip",  5000.0)
sys2.add("L_beam", 2.0)
sys2.add("E",      70e9)
sys2.add("b",      0.05)
sys2.add("h",      0.1)
sys2.use(openmdo_beam)

h_vals = np.linspace(0.04, 0.20, 8)
sweep2 = sys2.sweep("h", h_vals)
print(f"  {'h [m]':>7}  {'d [mm]':>8}  {'s_max [MPa]':>12}")
for i in range(len(h_vals)):
    row  = sweep2.table.iloc[i]
    defl = row["deflection"]
    sig  = row["max_stress"]
    defl_mm    = (float(defl.si) if hasattr(defl, "si") else float(defl)) * 1000
    stress_mpa = (float(sig.si)  if hasattr(sig,  "si") else float(sig))  / 1e6
    print(f"  {h_vals[i]:7.3f}  {defl_mm:8.2f}  {stress_mpa:12.1f}")
print("  (deflection ~ 1/h^3: doubling height cuts deflection 8x)")

# ── Custom OpenMDAO problem via factory ───────────────────────────────────────
print("\n=== Custom OpenMDAO problem via make_openmdo_adapter ===")
import openmdao.api as om

def build_paraboloid():
    class Paraboloid(om.ExplicitComponent):
        def setup(self):
            self.add_input("x", val=0.0)
            self.add_input("y", val=0.0)
            self.add_output("f_xy", val=0.0)
            self.declare_partials("*", "*", method="fd")
        def compute(self, inputs, outputs):
            x = inputs["x"]; y = inputs["y"]
            outputs["f_xy"] = (x - 3.0)**2 + x*y + (y + 4.0)**2 - 3.0
    p = om.Problem()
    p.model.add_subsystem("comp", Paraboloid(), promotes=["*"])
    p.setup()
    return p

paraboloid = make_openmdo_adapter(
    prob_factory=build_paraboloid,
    input_vars={"x": {"unit": "1", "desc": "x variable", "default": 0.0},
                "y": {"unit": "1", "desc": "y variable", "default": 0.0}},
    output_vars={"f_xy": {"unit": "1", "desc": "Paraboloid value"}},
    name="paraboloid_mdo",
    desc="Paraboloid function via OpenMDAO",
)
r3 = paraboloid(x=6.6, y=-7.3)
print(f"  f_xy at (6.6, -7.3) = {r3['f_xy']:.4f}  (expected ~ -15.94)")

# ── Register ──────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
print("  Global: openmdo_sellar, openmdo_beam -> domain mdo.openmdao")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: Orifice Pressure Solver

`examples/ex_orifice_pressure_solver.py`: Given phi, gas names, orifice size range, and per-line P0 bounds,

```python
import os
import math
import re
import numpy as np


import anvil
from anvil import Q
from anvil.db import fluids


# =============================================================================
# Stoichiometry helper  (not an RSQ -- takes string inputs)
# =============================================================================

def _stoich_FO(fuel_formula, oxidizer="O2"):
    """Stoichiometric (F/O) mass ratio for CxHy fuel."""
    _AW = {"H": 1.008, "C": 12.011, "O": 15.999, "N": 14.007}
    _OX = {"o2": (31.999, 1.00), "air": (28.970, 0.21)}
    a = {e: int(n or 1)
         for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", fuel_formula) if e}
    n_O2 = a.get("C", 0) + a.get("H", 0) / 4 - a.get("O", 0) / 2
    mw_f = sum(_AW.get(e, 0) * n for e, n in a.items())
    MW_ox, x_O2 = _OX.get(oxidizer.lower(), (mw_f, 1.0))
    return mw_f / ((n_O2 / x_O2) * MW_ox)


# =============================================================================
# RSQ definitions  -- each function is self-contained so it serialises safely
# into the project registry (registry stores source only, not module context)
# =============================================================================

def ox_choked_flow(P0_O2, T0_O2, d_O2, gamma_O2, R_O2, Cd_O2=0.61):
    """Choked flow through the oxidizer orifice (d_O2 in mm)."""
    import math
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    g  = si(gamma_O2)
    Gm = math.sqrt(g) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    K  = si(Cd_O2) * math.pi * (si(d_O2) * 5e-4) ** 2 * Gm / math.sqrt(si(R_O2) * si(T0_O2))
    return {"mdot_O2": Q(K * si(P0_O2), "kg/s"), "K_O2": K}


def phi_to_fuel_mdot(mdot_O2, phi, stoich_FO_val):
    """Fuel mdot for target equivalence ratio."""
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    return {"mdot_fuel": Q(si(phi) * si(stoich_FO_val) * si(mdot_O2), "kg/s")}


def fuel_P0_required(mdot_fuel, T0_fuel, d_fuel, gamma_fuel, R_fuel, Cd_fuel=0.61):
    """P0 required to deliver mdot_fuel through fuel orifice (d_fuel in mm)."""
    import math
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    g  = si(gamma_fuel)
    Gm = math.sqrt(g) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    K  = si(Cd_fuel) * math.pi * (si(d_fuel) * 5e-4) ** 2 * Gm / math.sqrt(si(R_fuel) * si(T0_fuel))
    return {"P0_fuel": Q(si(mdot_fuel) / K, "Pa"), "K_fuel": K}


def pressure_margin(P0_O2, P0_fuel, P0_O2_min, P0_O2_max, P0_fuel_min, P0_fuel_max):
    """
    Minimum pressure margin across both lines with per-line bounds (Pa).
    Positive = both lines inside bounds.  Maximised by the optimizer.
    """
    from anvil import Q
    si = lambda v: float(getattr(v, "si", v))
    return {"min_slack": Q(min(
        si(P0_O2)   - si(P0_O2_min),  si(P0_O2_max)   - si(P0_O2),
        si(P0_fuel) - si(P0_fuel_min), si(P0_fuel_max) - si(P0_fuel),
    ), "Pa")}


# =============================================================================
# Project registry
# =============================================================================

proj = anvil.project("orifice_phi_study", path="./orifice_phi_work")

for fn, desc in [
    (ox_choked_flow,   "Choked flow through the oxidizer orifice"),
    (phi_to_fuel_mdot, "Required fuel mdot for target equivalence ratio"),
    (fuel_P0_required, "Required P0 for fuel line at target mass flow"),
    (pressure_margin,  "Min pressure margin across both lines (optimizer objective)"),
]:
    proj.push(fn, domain="flow.orifice.phi", description=desc,
              tags=["orifice", "choked", "phi"])


# =============================================================================
# System builder  (gas properties fetched from the Anvil fluids DB)
# =============================================================================

def _build_system(fuel_gas, ox_gas, T0=300.0, Cd=0.61):
    gf = fluids.get(fuel_gas, T=T0)
    go = fluids.get(ox_gas,   T=T0)
    s  = anvil.system("phi_solver")
    s.add("P0_O2",       1e6,                    "Pa")
    s.add("T0_O2",       T0,                     "K")
    s.add("d_O2",        1.0)
    s.add("gamma_O2",    float(go["gamma"]))
    s.add("R_O2",        float(go["R_gas"].si),  "J/kg/K")
    s.add("Cd_O2",       Cd)
    s.add("phi",         1.0)
    s.add("stoich_FO_val", 0.1)
    s.add("T0_fuel",     T0,                     "K")
    s.add("d_fuel",      1.0)
    s.add("gamma_fuel",  float(gf["gamma"]))
    s.add("R_fuel",      float(gf["R_gas"].si),  "J/kg/K")
    s.add("Cd_fuel",     Cd)
    s.add("P0_O2_min",   3e5,   "Pa")
    s.add("P0_O2_max",   20e5,  "Pa")
    s.add("P0_fuel_min", 3e5,   "Pa")
    s.add("P0_fuel_max", 20e5,  "Pa")
    s.use(proj.R.ox_choked_flow)
    s.use(proj.R.phi_to_fuel_mdot)
    s.use(proj.R.fuel_P0_required)
    s.use(proj.R.pressure_margin)
    return s


# =============================================================================
# Solver  (single sys.optimize() over P0_O2, d_fuel, d_O2 jointly)
# =============================================================================

def find_pressure_settings(phi, fuel_gas, ox_gas, fuel_formula,
                            orifice_range, P0_bounds,
                            oxidizer_formula="O2", T0=300.0, Cd=0.61):
    """
    Find optimal orifice sizes and P0 setpoints for a target phi.

    Parameters
    ----------
    phi : float
        Target equivalence ratio.
    fuel_gas, ox_gas : str
        Anvil fluids DB keys, e.g. "hydrogen", "oxygen".
    fuel_formula : str
        Chemical formula for stoichiometry, e.g. "H2", "CH4".
    orifice_range : (float, float)
        (d_min_mm, d_max_mm) -- continuous search window for both orifices.
    P0_bounds : dict
        {"fuel": (lo_Pa, hi_Pa), "ox": (lo_Pa, hi_Pa)} -- per-line limits.
    oxidizer_formula : str
        "O2" (default) or "air".

    Returns
    -------
    dict with keys d_fuel, d_ox, P0_fuel, P0_ox, mdot_fuel, mdot_ox, margin
    (pressures in bar, flows in g/s, diameters in mm).
    None if no feasible solution exists within the given bounds.
    """
    s = _build_system(fuel_gas, ox_gas, T0, Cd)
    s.set(
        phi=phi,
        stoich_FO_val=_stoich_FO(fuel_formula, oxidizer_formula),
        P0_O2_min=P0_bounds["ox"][0],    P0_O2_max=P0_bounds["ox"][1],
        P0_fuel_min=P0_bounds["fuel"][0], P0_fuel_max=P0_bounds["fuel"][1],
    )

    opt = s.optimize(
        objective="min_slack",
        design_vars={
            "P0_O2":  P0_bounds["ox"],
            "d_O2":   orifice_range,
            "d_fuel": orifice_range,
        },
        minimize=False,
        method="differential_evolution",
        seed=0, maxiter=500, tol=1e-4,
    )

    # opt.success may be False if convergence tolerance not met, but the
    # optimizer still records the best feasible point found. Check opt.fun
    # (the actual min_slack at best point) rather than convergence status.
    if not math.isfinite(opt.fun) or opt.fun <= 0:
        return None

    return {
        "d_fuel":    Q(opt.x["d_fuel"] * 1e-3, "m"),
        "d_ox":      Q(opt.x["d_O2"]   * 1e-3, "m"),
        "P0_fuel":   opt["P0_fuel"],
        "P0_ox":     Q(opt.x["P0_O2"],          "Pa"),
        "mdot_fuel": opt["mdot_fuel"],
        "mdot_ox":   opt["mdot_O2"],
        "margin":    Q(opt.fun,                  "Pa"),
    }


# =============================================================================
# Usage
# =============================================================================

W = 64
print("=" * W)
print("  Orifice Pressure Solver")
print("=" * W)

def _show(r):
    if r:
        print(f"  d_fuel  = {r['d_fuel'].to('mm')}   d_ox    = {r['d_ox'].to('mm')}")
        print(f"  P0_fuel = {r['P0_fuel'].to('bar')}   P0_ox   = {r['P0_ox'].to('bar')}")
        print(f"  mdot_fuel = {r['mdot_fuel']}   mdot_ox = {r['mdot_ox']}")
        print(f"  margin  = {r['margin'].to('bar')}")


# ── Single solve ──────────────────────────────────────────────────────────────
print("\n[1] H2/O2  phi=1.0  |  orifice 0.5-2.0 mm  |  both lines 3-20 bar")
_show(find_pressure_settings(
    phi=1.0, fuel_gas="hydrogen", ox_gas="oxygen", fuel_formula="H2",
    orifice_range=(0.5, 2.0), P0_bounds={"fuel": (3e5, 20e5), "ox": (3e5, 20e5)},
))

# ── phi sweep ─────────────────────────────────────────────────────────────────
print(f"\n[2] phi sweep  (0.5 to 2.5)")
print(f"  {'phi':>6}  {'d_fuel':>12}  {'d_ox':>12}  {'P0_fuel':>16}  {'P0_ox':>16}")
print(f"  {'-'*6}  {'-'*12}  {'-'*12}  {'-'*16}  {'-'*16}")
for phi_val in np.linspace(0.5, 2.5, 9):
    r = find_pressure_settings(
        phi=phi_val, fuel_gas="hydrogen", ox_gas="oxygen", fuel_formula="H2",
        orifice_range=(0.5, 2.0), P0_bounds={"fuel": (3e5, 20e5), "ox": (3e5, 20e5)},
    )
    if r:
        print(f"  {phi_val:>6.2f}  {r['d_fuel'].to('mm')!s:>12}  {r['d_ox'].to('mm')!s:>12}  "
              f"{r['P0_fuel'].to('bar')!s:>16}  {r['P0_ox'].to('bar')!s:>16}")
    else:
        print(f"  {phi_val:>6.2f}  -- no feasible solution --")

# ── asymmetric bounds ─────────────────────────────────────────────────────────
print(f"\n[3] Asymmetric bounds: H2 3-10 bar,  O2 3-20 bar")
_show(find_pressure_settings(
    phi=1.0, fuel_gas="hydrogen", ox_gas="oxygen", fuel_formula="H2",
    orifice_range=(0.5, 2.0), P0_bounds={"fuel": (3e5, 10e5), "ox": (3e5, 20e5)},
))

# ── CH4 / O2 ─────────────────────────────────────────────────────────────────
print(f"\n[4] CH4/O2  phi=0.8  |  orifice 0.5-3.0 mm  |  5-25 bar")
_show(find_pressure_settings(
    phi=0.8, fuel_gas="methane", ox_gas="oxygen", fuel_formula="CH4",
    orifice_range=(0.5, 3.0), P0_bounds={"fuel": (5e5, 25e5), "ox": (5e5, 25e5)},
))

print(f"\n{'='*W}")
print("  Done.")
print(f"{'='*W}")
```

**Output:**

```
  Project 'orifice_phi_study' opened  (orifice_phi_work\.anvil\project_orifice_phi_study.db)
  [orifice_phi_study] Registered 'ox_choked_flow' (R) in domain 'flow.orifice.phi'.
  [orifice_phi_study] Registered 'phi_to_fuel_mdot' (R) in domain 'flow.orifice.phi'.
  [orifice_phi_study] Registered 'fuel_P0_required' (R) in domain 'flow.orifice.phi'.
  [orifice_phi_study] Registered 'pressure_margin' (R) in domain 'flow.orifice.phi'.
================================================================
  Orifice Pressure Solver
================================================================

[1] H2/O2  phi=1.0  |  orifice 0.5-2.0 mm  |  both lines 3-20 bar
  d_fuel  = 1.0660 mm   d_ox    = 1.5063 mm
  P0_fuel = 11.4999 bar (P0_fuel)   P0_ox   = 11.5001 bar
  mdot_fuel = 3.8635e-04 kg/s (mdot_fuel)   mdot_ox = 3.0661e-03 kg/s (mdot_O2)
  margin  = 8.4999 bar

[2] phi sweep  (0.5 to 2.5)
     phi        d_fuel          d_ox           P0_fuel             P0_ox
  ------  ------------  ------------  ----------------  ----------------
    0.50   0.891958 mm     1.7825 mm  11.5000 bar (P0_fuel)       11.5000 bar
    0.75   0.707712 mm     1.1548 mm  11.4999 bar (P0_fuel)       11.5001 bar
    1.00     1.0660 mm     1.5063 mm  11.4999 bar (P0_fuel)       11.5001 bar
    1.25     1.3725 mm     1.7347 mm  11.5000 bar (P0_fuel)       11.5001 bar
    1.50     1.6084 mm     1.8557 mm  11.5000 bar (P0_fuel)       11.5001 bar
    1.75     1.7808 mm     1.9022 mm  11.5000 bar (P0_fuel)       11.5001 bar
    2.00     1.9805 mm     1.9790 mm  11.5002 bar (P0_fuel)       11.4998 bar
    2.25   0.880314 mm   0.829315 mm  11.5000 bar (P0_fuel)       11.4999 bar
    2.50     1.7051 mm     1.5239 mm  11.5000 bar (P0_fuel)       11.5000 bar

[3] Asymmetric bounds: H2 3-10 bar,  O2 3-20 bar
  d_fuel  = 1.9495 mm   d_ox    = 1.8361 mm
  P0_fuel = 6.5000 bar (P0_fuel)   P0_ox   = 14.6333 bar
  mdot_fuel = 7.3041e-04 kg/s (mdot_fuel)   mdot_ox = 5.7967e-03 kg/s (mdot_O2)
  margin  = 3.5000 bar

... (9 more lines)
```


## Fundamental Physics RSQs

`examples/ex_physics.py`: A tour of the physics relation pack: mechanics, electromagnetism, optics,

```python
import anvil

print("=" * 60)
print("  Mechanics")
print("=" * 60)
print(f"  Kinetic energy (2 kg at 3 m/s) : {anvil.R.kinetic_energy(m=2, v=3)['KE']}")
print(f"  Gravity (Earth on 1 kg at surface): "
      f"{anvil.R.newton_gravitation(m1=5.972e24, m2=1, r=6.371e6)['F_grav']}")
print(f"  Projectile range (10 m/s, 45 deg): "
      f"{anvil.R.projectile_range(v0=10, angle_deg=45)['range']}")
print(f"  Pendulum period (1 m)          : {anvil.R.pendulum_period(L=1)['period']}")

print("\n" + "=" * 60)
print("  Electromagnetism")
print("=" * 60)
print(f"  Coulomb force (2x 1 uC at 0.1 m): "
      f"{anvil.R.coulomb_force(q1=1e-6, q2=1e-6, r=0.1)['F_coulomb']}")
print(f"  Capacitor energy (1 m^2, 1 mm, 100 V): "
      f"{anvil.R.parallel_plate_capacitor_energy(A=1, d=1e-3, V=100)['U_stored']}")
print(f"  Lorentz force (proton, 1e6 m/s, 0.5 T): "
      f"{anvil.R.lorentz_force_magnitude(q=1.602176634e-19, v=1e6, B=0.5)['F_lorentz']}")

print("\n" + "=" * 60)
print("  Optics")
print("=" * 60)
snell = anvil.R.snell_refraction_angle(n1=1, n2=1.5, theta1_deg=30)
print(f"  Snell refraction (30 deg into glass): {snell['theta2_deg']:.3f} deg")
print(f"  Thin lens image (f=0.1, d_o=0.3): "
      f"{anvil.R.thin_lens_image_distance(f=0.1, d_o=0.3)['d_i']}")
print(f"  Photon energy (green, 5.5e14 Hz): "
      f"{anvil.R.photon_energy_frequency(f=5.5e14)['E_photon']}")

print("\n" + "=" * 60)
print("  Waves and relativity")
print("=" * 60)
print(f"  Wave speed (100 Hz, 3.4 m)     : {anvil.R.wave_speed(frequency=100, wavelength=3.4)['speed']}")
dop = anvil.R.relativistic_doppler_shift(f_src=1e9, v_radial=2.99792458e7)
print(f"  Relativistic Doppler (approach 0.1c): {dop['f_obs']} (x{dop['shift_factor']:.4f})")
print(f"  Lorentz factor (0.6c)          : {anvil.R.lorentz_factor(v=0.6 * 2.99792458e8)['gamma']:.4f}")
print(f"  Rest energy of 1 kg            : {anvil.R.mass_energy_equivalence(m=1)['E_rest']}")

print("\n" + "=" * 60)
print("  Quantum")
print("=" * 60)
print(f"  de Broglie wavelength (p=1e-24): "
      f"{anvil.R.de_broglie_wavelength(p=1e-24)['wavelength']}")
print(f"  Wien peak (Sun, 5778 K)        : "
      f"{anvil.R.wien_peak_wavelength(T=5778)['lambda_peak']}")
```

**Output:**

```
============================================================
  Mechanics
============================================================
  Kinetic energy (2 kg at 3 m/s) : 9.0000 J
  Gravity (Earth on 1 kg at surface): 9.8195 N
  Projectile range (10 m/s, 45 deg): 10.1937 m
  Pendulum period (1 m)          : 2.0061 s

============================================================
  Electromagnetism
============================================================
  Coulomb force (2x 1 uC at 0.1 m): 0.898755 N
  Capacitor energy (1 m^2, 1 mm, 100 V): 4.4271e-05 J
  Lorentz force (proton, 1e6 m/s, 0.5 T): 8.0109e-14 N

============================================================
  Optics
============================================================
  Snell refraction (30 deg into glass): 19.471 deg
  Thin lens image (f=0.1, d_o=0.3): 0.150000 m
  Photon energy (green, 5.5e14 Hz): 3.6443e-19 J

============================================================
  Waves and relativity
============================================================
  Wave speed (100 Hz, 3.4 m)     : 340.00 m/s
  Relativistic Doppler (approach 0.1c): 1.1055e+09 Hz (x1.1055)
  Lorentz factor (0.6c)          : 1.2500
  Rest energy of 1 kg            : 8.9876e+16 J

============================================================
  Quantum
============================================================
  de Broglie wavelength (p=1e-24): 6.6261e-10 m
... (1 more lines)
```


## Example: Custom Relations + Project Registry

`examples/ex_project_workflow.py`: Scenario: pipe flow design, friction factor, pressure drop, pump power.

```python
import sys, os

import numpy as np
import anvil
from anvil import Q, system

# ─────────────────────────────────────────────────────────────────
# PART 1, Define your own Relations (plain Python functions)
#
# Rules:
#   - Accept inputs as keyword arguments
#   - Return a dict
#   - Wrap dimensional outputs in Q(value, "unit") so units propagate
# ─────────────────────────────────────────────────────────────────

def friction_factor(Re, roughness_ratio=0.0):
    """
    Darcy-Weisbach friction factor.
    Laminar Re < 2300: f = 64/Re
    Turbulent Re >= 2300: Swamee-Jain explicit approximation
    roughness_ratio = epsilon/D (dimensionless)
    """
    if Re < 2300:
        f = 64.0 / Re
    else:
        # Swamee-Jain (explicit approx to Colebrook)
        numerator   = roughness_ratio / 3.7
        denominator = 5.74 / Re**0.9
        f = 0.25 / (np.log10(numerator + denominator))**2
    return {"f_darcy": f}


def pressure_drop(f_darcy, rho, V, D_pipe, L_pipe):
    """
    Darcy-Weisbach pressure drop: dP = f * (L/D) * 0.5 * rho * V^2
    """
    dP = f_darcy * (L_pipe / D_pipe) * 0.5 * rho * V**2
    return {"dP": Q(dP, "Pa")}


def pump_power(dP, V, D_pipe, eta_pump=0.75):
    """
    Hydraulic pump power: W = Q_vol * dP / eta
    Q_vol = V * pi/4 * D^2
    """
    A     = np.pi / 4 * D_pipe**2
    Q_vol = V * A
    W_hyd = Q_vol * dP          # watts if dP in Pa, Q_vol in m^3/s
    W_shaft = W_hyd / eta_pump
    return {
        "W_hydraulic": Q(W_hyd,   "W"),
        "W_shaft":     Q(W_shaft, "W"),
        "Q_vol":       Q(Q_vol,   "m^3/s"),
    }


# ─────────────────────────────────────────────────────────────────
# PART 2, Open a project registry
#
# Creates (or opens) a local .db file in the given directory.
# Nothing goes to the global registry until you explicitly promote it.
# ─────────────────────────────────────────────────────────────────

print("=" * 60)
print("  PART 2: Project Registry")
print("=" * 60)

project_dir = os.path.join(os.path.dirname(__file__), "pipe_project")
os.makedirs(project_dir, exist_ok=True)

proj = anvil.project("pipe_flow", path=project_dir)
# → Creates: pipe_project/.anvil/project_pipe_flow.db

# Register your three relations to the project
proj.push(friction_factor,
    domain="fluid.pipe",
    description="Darcy-Weisbach friction factor (laminar + Swamee-Jain turbulent)",
    tags=["pipe", "friction", "darcy"])

proj.push(pressure_drop,
    domain="fluid.pipe",
    description="Darcy-Weisbach pressure drop along a pipe segment",
    tags=["pipe", "pressure_drop"])

proj.push(pump_power,
    domain="fluid.pipe",
    description="Hydraulic and shaft pump power from flow and pressure drop",
    tags=["pipe", "pump", "power"])

# List what's in the project
proj.list()


# ─────────────────────────────────────────────────────────────────
# PART 3, Use project RSQs directly (no System needed)
#
# Quick sanity check on each relation before wiring them together.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 3: Direct calls to project RSQs")
print("=" * 60)

# proj.R.<name> gives you the callable Relation
r_lam = proj.R.friction_factor(Re=1000)
r_tur = proj.R.friction_factor(Re=50000, roughness_ratio=0.001)

print(f"\n  Laminar  Re=1000  : f = {r_lam['f_darcy']:.5f}  (expect 0.064)")
print(f"  Turbulent Re=50000 : f = {r_tur['f_darcy']:.5f}")

r_dp = proj.R.pressure_drop(
    f_darcy=r_tur["f_darcy"],
    rho=998.2, V=2.0, D_pipe=0.05, L_pipe=10.0
)
print(f"  Pressure drop: {r_dp['dP']}")


# ─────────────────────────────────────────────────────────────────
# PART 4, Build a System using project RSQs
#
# Use proj.R.<name> to pull a relation from the project into a System.
# Alternatively use the string name: sys.use("friction_factor")
# works the same once the RSQ is in the project registry.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 4: System built from own Relations")
print("=" * 60)

# --- Define inputs with units ---
pipe_sys = system("water_pipe")

pipe_sys.add("rho",            998.2,  "kg/m^3",  desc="Water density")
pipe_sys.add("V",                2.0,  "m/s",     desc="Mean flow velocity")
pipe_sys.add("D_pipe",          0.05,  "m",       desc="Pipe inner diameter")
pipe_sys.add("L_pipe",          10.0,  "m",       desc="Pipe length")
pipe_sys.add("roughness_ratio", 1e-4,             desc="Relative roughness eps/D")
pipe_sys.add("eta_pump",        0.75,             desc="Pump efficiency")

# Add Reynolds number from the built-in registry RSQ
pipe_sys.add("mu",            1.002e-3, "Pa*s",   desc="Dynamic viscosity (water)")
pipe_sys.use("reynolds_number",
    map={"L_char": "D_pipe"})    # map the 'L_char' input to our 'D_pipe'

# Add our own relations from the project.
#
# IMPORTANT: sys.use("name") only searches the GLOBAL registry.
# Project RSQs must be passed as objects via proj.R.<name>.
pipe_sys.use(proj.R.friction_factor)
pipe_sys.use(proj.R.pressure_drop)
pipe_sys.use(proj.R.pump_power)

# Solve, acyclic (feed-forward), so forward pass
result = pipe_sys.solve_forward()
result.summary()

# --- Unit conversions on results ---
print("\n  Key results:")
print(f"    Re         = {result['Re']}  (turbulent: {'yes' if result['Re'].si > 2300 else 'no'})")
print(f"    f_darcy    = {result['f_darcy']}")
print(f"    dP         = {result['dP'].to('kPa')}")
print(f"    W_shaft    = {result['W_shaft'].to('kW')}")
print(f"    Q_vol      = {result['Q_vol']}"
      f"  ({result['Q_vol'].si * 1000:.2f} L/s)")


# ─────────────────────────────────────────────────────────────────
# PART 5, Parametric sweep using the system
#
# Vary flow velocity; observe friction factor, pressure drop, pump power.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 5: Velocity sweep")
print("=" * 60)

sweep = pipe_sys.sweep("V", np.linspace(0.5, 4.0, 8), parallel=2)
sweep.summary(outputs=["Re", "f_darcy", "dP", "W_shaft"])


# ─────────────────────────────────────────────────────────────────
# PART 6, Promote to global registry
#
# Once your relations are validated and producing correct results,
# promote them from the project store to the global registry.
# They then become available to any script via anvil.R.<name>.
# ─────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  PART 6: Promote to global registry")
print("=" * 60)

proj.promote("friction_factor", overwrite=True)
proj.promote("pressure_drop",   overwrite=True)
proj.promote("pump_power",      overwrite=True)

# Verify they're now in global registry
print("\n  Searching global registry for 'pipe'...")
anvil.registry.search("pipe")

# Access via global namespace, exactly like any built-in RSQ
r_check = anvil.R.friction_factor(Re=1000)
print(f"\n  anvil.R.friction_factor(Re=1000) -> f = {r_check['f_darcy']:.4f}")


# ─────────────────────────────────────────────────────────────────
# CLEANUP (optional, remove promoted RSQs from global for clean demo)
# ─────────────────────────────────────────────────────────────────

for name in ("friction_factor", "pressure_drop", "pump_power"):
    anvil.registry.remove(name)

import shutil
shutil.rmtree(project_dir, ignore_errors=True)

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  PART 2: Project Registry
============================================================
  Project 'pipe_flow' opened  (C:\Users\rc\OneDrive - University of Maryland\Documents\Personal\the-anvil-framework-main\the-anvil-framework-main\examples\pipe_project\.anvil\project_pipe_flow.db)
  [pipe_flow] Registered 'friction_factor' (R) in domain 'fluid.pipe'.
  [pipe_flow] Registered 'pressure_drop' (R) in domain 'fluid.pipe'.
  [pipe_flow] Registered 'pump_power' (R) in domain 'fluid.pipe'.

  Project: pipe_flow  (C:\Users\rc\OneDrive - University of Maryland\Documents\Personal\the-anvil-framework-main\the-anvil-framework-main\examples\pipe_project)

  Relations (3):
    friction_factor                 [fluid.pipe]
      Darcy-Weisbach friction factor (laminar + Swamee-Jain turbulent)
    pressure_drop                   [fluid.pipe]
      Darcy-Weisbach pressure drop along a pipe segment
    pump_power                      [fluid.pipe]
      Hydraulic and shaft pump power from flow and pressure drop

  Total: 3 RSQs

============================================================
  PART 3: Direct calls to project RSQs
============================================================

  Laminar  Re=1000  : f = 0.06400  (expect 0.064)
  Turbulent Re=50000 : f = 0.02418
  Pressure drop: 9654.95 Pa

============================================================
  PART 4: System built from own Relations
============================================================

--------------------------------------------------------
  water_pipe -- results
... (77 more lines)
```


## Example: pyNastran / NASTRAN FEM Adapter (real only)

`examples/ex_pynastran_adapter.py`: nastran_linear_static and nastran_normal_modes against a real

```python
import sys, os

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
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: RocketCEA + RocketPy Adapter -- Engine & Flight (real-only)

`examples/ex_rocketcea_adapter.py`: the rocket_cea combustion adapter (Tc, c*, Isp, gamma) and the

```python
import anvil
from anvil import Q
from anvil.adapters.rocket_cea import rocket_cea, rocketpy_flight, register

W = 64
print("=" * W)
print("  RocketCEA / RocketPy Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs the external packages; importing is always safe.
register()

# ── 1. Combustion performance over propellant combos ─────────────────────────
print("\n[1] Combustion performance at Pc = 7 MPa, eps = 40 (rocket_cea)")
try:
    print(f"  {'ox/fuel':12s}  {'OF':>5s}  {'Tc (K)':>8s}  {'c* (m/s)':>9s}  {'Isp (s)':>8s}")
    print(f"  {'-'*12}  {'-'*5}  {'-'*8}  {'-'*9}  {'-'*8}")
    for ox, fuel, of in (("LOX", "RP1", 2.27), ("LOX", "LH2", 6.0), ("LOX", "CH4", 3.5)):
        r = rocket_cea(oxidizer=ox, fuel=fuel, OF=of, Pc=7e6, eps=40.0)
        print(f"  {ox+'/'+fuel:12s}  {of:5.2f}  {r['Tc'].value:8.0f}  "
              f"{r['cstar'].value:9.1f}  {r['Isp'].value:8.1f}")

    # ── 3. Pipeline: chamber c* drives required throat-area mass flow ────────
    print("\n  System: mass flow from c* and throat area")
    cea = rocket_cea(oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7e6, eps=40.0)
    eng = anvil.system("engine_point")
    eng.add("Pc", 7e6, "Pa")
    eng.add("cstar", cea["cstar"].value, "m/s")
    eng.add("A_throat", 0.01, "m^2")

    def mass_flow(Pc, A_throat, cstar):
        mdot = Pc * A_throat / cstar
        return {"mdot": Q(mdot, "kg/s")}
    eng.use(mass_flow)
    res = eng.solve_forward()
    print(f"  mdot   = {res['mdot']}")
except ImportError as e:
    print("\n  RocketCEA is not installed -- cannot run the combustion part.")
    print(f"  {e}")
    print("  Install RocketCEA to run this part: pip install rocketcea")

# ── 2. Flight: apogee of a simple sounding rocket ────────────────────────────
print("\n[2] Flight estimate (rocketpy_flight)")
try:
    f = rocketpy_flight(thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                        prop_mass=4.0, Cd=0.5, area=0.008)
    print(f"  apogee    = {f['apogee']}")
    print(f"  v_max     = {f['v_max']}")
    print(f"  v_burnout = {f['v_burnout']}  (source: {f['source']})")
except ImportError as e:
    print("  RocketPy is not installed -- cannot run the flight part.")
    print(f"  {e}")
    print("  Install RocketPy to run this part: pip install rocketpy")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Anvil Framework -- Complete Showcase

`examples/ex_showcase_v2.py`: every major feature in one runnable file.

```python
#!/usr/bin/env python3

import os

import numpy as np

# --- path setup ----------------------------------------------------------

import anvil
from anvil import (
    BTU,
    MJ,
    Adapter,
    GPa,
    J,
    K,
    MPa,
    N,
    Pa,
    Q,
    Quantity,
    Relation,
    System,
    W,
    atm,
    bar,
    cm,
    ft,
    g_mol,
    kg,
    kg_mol,
    kJ,
    km,
    kN,
    kPa,
    kW,
    lb,
    lbf,
    m,
    mm,
    mol,
    monitor,
    ms,
    s,
    solvers,
    viz,
)

OUT_DIR = os.path.dirname(__file__)  # save PNGs next to this file


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


# =========================================================================
# 1. UNIT ENGINE
# =========================================================================
section("1. UNIT ENGINE")

# --- 1a. Classic Q() syntax ---
T_chamber = Q(3500, "K", name="T_chamber")
P_chamber = Q(6.9e6, "Pa", name="P_chamber")
mdot = Q(12.5, "kg/s", name="mdot")
area = Q(0.1, "m^2", name="area")

print(f"\nClassic Q():")
print(f"  T_chamber = {T_chamber}")
print(f"  P_chamber = {P_chamber}")
print(f"  mdot      = {mdot}")

# --- 1b. UnitStub syntax: value * unit ---
T_amb = 298.15 * K  # -> Q(298.15, "K")
P_atm = 101325 * Pa  # -> Q(101325, "Pa")
v_sound = 340.0 * (m / s)  # -> Q(340.0, "m/s")
g_earth = 9.80665 * m / s**2  # -> Q(9.80665, "m/s^2")  -- no parens needed
rho_air = 1.225 * kg / m**3  # -> Q(1.225, "kg/m^3")   -- no parens needed
cp_air = 1005.0 * J / kg / K  # -> Q(1005.0, "J/kg/K")
mu_air = 1.789e-5 * Pa * s  # -> Q(1.789e-5, "Pa*s")

print(f"\nUnitStub syntax:")
print(f"  T_amb    = {T_amb}")
print(f"  v_sound  = {v_sound}")
print(f"  g_earth  = {g_earth}")
print(f"  rho_air  = {rho_air}")
print(f"  cp_air   = {cp_air}")
print(f"  mu_air   = {mu_air}")

# Imperial units
V_jet = 550.0 * (ft / s)  # -> Q(550, "ft/s")  -- SI internally
F_drag = 150.0 * lbf  # -> Q(150 lbf in N)
L_wing = 12.5 * ft
print(f"\n  V_jet  = {V_jet}  ->  {V_jet.to('m/s')}")
print(f"  F_drag = {F_drag} ->  {F_drag.to('N')}")

# --- 1c. Quantity arithmetic ---
KE = 0.5 * rho_air * v_sound**2  # dynamic pressure
Re = rho_air * v_sound * (1.0 * m) / mu_air
print(f"\nArithmetic:")
print(f"  q_dyn = 12rhoV2 = {KE}")
print(f"  Re    = rhoVL/mu = {Re}")

# --- 1d. Unit conversion ---
T_K = Q(1000, "K")
T_R = T_K.to("R")  # Kelvin -> Rankine (same dimension, different scale)
P_Pa = Q(10e6, "Pa")
P_bar = P_Pa.to("bar")
P_psi = P_Pa.to("psi")
P_MPa = P_Pa.to("MPa")

print(f"\nUnit conversions:")
print(f"  {T_K}  ->  {T_R}")
print(f"  {P_Pa} ->  {P_bar}  =  {P_psi}  =  {P_MPa}")

# --- 1e. SI access ---
print(f"\n  cp_air.si    = {cp_air}  (always in SI: J/kg/K)")
print(f"  cp_air.value = {cp_air} {cp_air.unit}")


# =========================================================================
# 2. DEFINING RELATIONS
# =========================================================================
section("2. DEFINING RELATIONS")


# --- 2a. Decorator syntax -- auto-registers in the registry ---
@anvil.relation(domain="thermo", tags=["ideal_gas"])
def ideal_gas_rho(P, R_gas, T):
    """Ideal gas: rho = P / (R * T)"""
    return {"rho": Q(P / (R_gas * T), "kg/m^3")}


@anvil.relation(domain="thermo", tags=["acoustics"])
def speed_of_sound_gas(gamma, R_gas, T):
    """Speed of sound in ideal gas: a = sqrt(gamma * R * T)"""
    return {"a_sound": Q((gamma * R_gas * T) ** 0.5, "m/s")}


@anvil.relation(domain="aero", tags=["reynolds"])
def reynolds_num(rho, V, L_char, mu):
    """Reynolds number: Re = rho V L / mu"""
    return {"Re": rho * V * L_char / mu}


print(f"\n@relation auto-registered: {ideal_gas_rho}")
print(f"  inputs:  {ideal_gas_rho.inputs}")
print(f"  outputs: {ideal_gas_rho.outputs}")


# --- 2b. Relation() explicit wrap ---
def nusselt_dittus_boelter(Re, Pr, heating=True):
    """Dittus-Boelter: Nu = 0.023 * Re^0.8 * Pr^n"""
    n = 0.4 if heating else 0.3
    Nu = 0.023 * Re**0.8 * Pr**n
    return {"Nu": Nu}


nu_rel = Relation(nusselt_dittus_boelter, tags=["convection", "heat_transfer"])
print(f"\nRelation() wrap: {nu_rel}")


# --- 2c. Relation.block() -- chain multiple functions ---
def sutherland(T, T_ref=288.15, mu_ref=1.789e-5, S=110.4):
    mu = mu_ref * (T / T_ref) ** 1.5 * (T_ref + S) / (T + S)
    return {"mu": mu}


def prandtl_air(mu, cp, k_cond=0.0257):
    Pr = mu * cp / k_cond
    return {"Pr": Pr}


air_props = Relation.block(
    "air_transport_props",
    steps=[sutherland, prandtl_air],
    desc="Sutherland viscosity + Prandtl number for air",
)
print(f"\nRelation.block(): {air_props}")
print(f"  inputs:  {air_props.inputs}")
print(f"  outputs: {air_props.outputs}")


# =========================================================================
# 3. ONE-SHOT SOLVE
# =========================================================================
section("3. ONE-SHOT SOLVE -- anvil.solve()")

# No System object needed; inputs passed as keyword arguments
r = anvil.solve(ideal_gas_rho, P=101325.0, R_gas=287.0, T=298.15)
print(f"\nOne-shot solve -- ideal gas density:")
r.summary()

r2 = anvil.solve(speed_of_sound_gas, gamma=1.4, R_gas=287.0, T=298.15)
print(f"Speed of sound: {r2['a_sound']}")

# Works with registry names too
r3 = anvil.solve("isentropic_ratios", M=2.0, gamma=1.4)
print(f"\nisentropic_ratios at M=2: T0/T={r3['T0_T']:.4f}  P0/P={r3['P0_P']:.4f}")


# =========================================================================
# 4. SYSTEM API
# =========================================================================
section("4. SYSTEM API -- system(), add(kwargs), use(), solve()")

# --- 4a. Build and solve a compressible nozzle flow system ---
nozzle = anvil.system("de_laval_nozzle")

# New kwargs-style add -- name inferred from keyword
nozzle.add(
    P0=8.0e6 * Pa,  # chamber total pressure
    T0=3300.0 * K,  # chamber total temperature
    gamma=Q(1.22),  # ratio of specific heats (dimensionless)
    R_gas=380.0 * J / kg / K,
    A_throat=0.001 * m**2,
    A_exit=Q(0.07, "m^2"),
    P_amb=P_atm,
)

# Can also mix old style
nozzle._add_single("P_amb", P_atm)  # (overwrite with same value, fine)

nozzle.use("nozzle_area_ratio")
nozzle.use("area_mach_supersonic")
nozzle.use("isentropic_ratios", map={"M": "M_exit"})
nozzle.use("exit_conditions")
nozzle.use("exit_velocity")
nozzle.use("choked_mass_flow")
nozzle.use("rocket_thrust")
nozzle.use("specific_impulse")

result = nozzle.solve(verbose=True)
result.summary()

# --- 4b. Result access ---
thrust = result["thrust"]
Isp = result["Isp"]
mdot_r = result["mdot"]
V_exit = result["V_exit"]

print(f"\nKey outputs:")
print(f"  Thrust = {thrust.to('kN')}")
print(f"  Isp    = {Isp}")
print(f"  mdot   = {mdot_r}")
print(f"  V_exit = {V_exit.to('km/s')}")

# --- 4c. Export results ---
result.to_csv(os.path.join(OUT_DIR, "nozzle_result.csv"))
print(f"\n  Saved: nozzle_result.csv")

json_str = result.to_json()
print(f"  JSON (first 150 chars): {json_str[:150]}...")


# =========================================================================
# 5. BUILT-IN RSQs
# =========================================================================
section("5. BUILT-IN RSQs (R and S namespaces)")

# --- 5a. Direct relation calls (no System needed) ---
print("\nIsentropic ratios at M=3, gamma=1.4:")
r_isen = anvil.R.isentropic_ratios(M=3.0, gamma=1.4)
print(f"  T0/T   = {r_isen['T0_T']:.4f}")
print(f"  P0/P   = {r_isen['P0_P']:.4f}")
print(f"  rho0/rho   = {r_isen['rho0_rho']:.4f}")

print("\nNormal shock at M1=2.5:")
r_shock = anvil.R.normal_shock(M1=2.5, gamma=1.4)
print(f"  M2     = {r_shock['M2']:.4f}")
print(f"  P2/P1  = {r_shock['P2_P1']:.4f}")
print(f"  T2/T1  = {r_shock['T2_T1']:.4f}")
print(f"  P02/P01= {r_shock['P02_P01']:.5f}  (stagnation pressure loss)")

print("\nHohmann transfer: LEO (400 km) -> GEO (35 786 km):")
R_earth = 6.371e6  # m
mu_earth = 3.986e14  # m^3/s^2
r1 = R_earth + 400e3
r2 = R_earth + 35786e3
r_hohmann = anvil.R.hohmann_transfer(mu=mu_earth, r1=r1, r2=r2)
print(f"  DV1    = {r_hohmann['dv1'].to('km/s')}")
print(f"  DV2    = {r_hohmann['dv2'].to('km/s')}")
print(f"  DV_tot = {r_hohmann['dv_total'].to('km/s')}")
print(f"  TOF    = {Q(float(r_hohmann['tof']._si_value) / 3600, 'hr')}")

# --- 5b. Pre-built rocket nozzle System ---
print("\nPre-built rocket_nozzle System:")
rn = anvil.S.rocket_nozzle.copy()
rn.set(P0=10e6, T0=3600, gamma=1.2, R_gas=400.0, A_throat=0.015, A_exit=0.12)
rn.solve().summary()


# =========================================================================
# 6. COUPLED SOLVE -- GAUSS-SEIDEL + MONITOR
# =========================================================================
section("6. COUPLED SOLVE -- Gauss-Seidel + Convergence History")

# Coupled fixed-point system (Gauss-Seidel converges by design):
#   y1 = sqrt(y2 + 4.0)     (y1 depends on y2)
#   y2 = sqrt(y1)            (y2 depends on y1)
#
# Solution satisfies y1 = sqrt(sqrt(y1) + 4)
# Numerically: y1 ~ 2.4353, y2 ~ 1.5606


@anvil.relation(domain="math", register=False)
def fp_eq1(y2):
    return {"y1": (y2 + 4.0) ** 0.5}


@anvil.relation(domain="math", register=False)
def fp_eq2(y1):
    return {"y2": y1**0.5}


coupled_sys = anvil.system("fixed_point_demo")
coupled_sys.add("y2", 1.0)  # initial guess for y2
coupled_sys.use(fp_eq1)
coupled_sys.use(fp_eq2)

result_coupled = coupled_sys.solve(
    method="gauss_seidel",
    max_iter=200,
    rtol=1e-8,
    monitor=True,
    verbose=True,
)
result_coupled.summary()

# Verify fixed-point consistency
y1_val = float(result_coupled["y1"]._si_value)
y2_val = float(result_coupled["y2"]._si_value)
print(f"\n  Check: y1 == sqrt(y2+4): {y1_val:.6f} vs {(y2_val + 4) ** 0.5:.6f}")
print(f"  Check: y2 == sqrt(y1):   {y2_val:.6f} vs {y1_val**0.5:.6f}")

# Convergence history plot
monitor.plot_convergence(
    coupled_sys, save=os.path.join(OUT_DIR, "convergence.png"), show=False
)
print(f"\n  Saved: convergence.png")

monitor.plot_variables(
    coupled_sys,
    variables=["y1", "y2"],
    save=os.path.join(OUT_DIR, "variable_trace.png"),
    show=False,
)
print(f"  Saved: variable_trace.png")


# =========================================================================
# 7. PARAMETRIC SWEEP
# =========================================================================
section("7. PARAMETRIC SWEEP")

sweep_nozzle = anvil.S.rocket_nozzle.copy()

# Sweep chamber pressure from 2 MPa to 12 MPa
P0_values = np.linspace(2e6, 12e6, 12)  # Pa
sweep = sweep_nozzle.sweep("P0", P0_values, skip_errors=True)
sweep.summary(outputs=["thrust", "Isp", "mdot", "V_exit"])

# Export sweep data
sweep.to_csv(os.path.join(OUT_DIR, "sweep_pressure.csv"))
print(f"\n  Saved: sweep_pressure.csv")

# Plot sweep
monitor.plot_sweep(
    sweep,
    y=["thrust", "Isp", "mdot", "V_exit"],
    save=os.path.join(OUT_DIR, "sweep_plot.png"),
    show=False,
)
print(f"  Saved: sweep_plot.png")

# Sweep over area ratio (exit/throat)
sweep_nozzle2 = anvil.S.rocket_nozzle.copy()
A_exit_values = np.linspace(0.02, 0.16, 10)  # m^2
sweep2 = sweep_nozzle2.sweep("A_exit", A_exit_values, skip_errors=True)
sweep2.summary(outputs=["M_exit", "thrust", "Isp"])


# =========================================================================
# 8. SENSITIVITY ANALYSIS
# =========================================================================
section("8. SENSITIVITY ANALYSIS")

sens_sys = anvil.S.rocket_nozzle.copy()
sens = sens_sys.sensitivity(
    outputs=["thrust", "Isp", "mdot"],
    step=0.01,
)
sens.summary()

print(f"\nTop 3 drivers of Isp:")
for inp, val in sens.top("Isp", n=3):
    print(f"  {inp:20s}  {val:+.4f}")


# =========================================================================
# 9. DEPENDENCY GRAPH
# =========================================================================
section("9. DEPENDENCY GRAPH")

dep_sys = anvil.S.rocket_nozzle.copy()
try:
    dep_sys.validate()
except Exception:
    pass

monitor.plot_system(
    dep_sys, save=os.path.join(OUT_DIR, "dependency_graph.png"), show=False
)
print(f"  Saved: dependency_graph.png")


# =========================================================================
# 10. ODE SOLVERS
# =========================================================================
section("10. ODE SOLVERS")

# --- 10a. Explicit RK45: radioactive decay chain ---
print("\n--- Explicit RK45: two-species decay  A -> B -> products ---")
# dA/dt = -k1 * A
# dB/dt = +k1 * A - k2 * B
k1, k2 = 0.1, 0.3  # 1/s


def decay_chain(t, y):
    A, B = y
    return [-k1 * A, k1 * A - k2 * B]


t_span = (0.0, 30.0)
y0 = [1.0, 0.0]
t_eval = np.linspace(0, 30, 300)

sol = solvers.solve_ode(decay_chain, t_span, y0, t_eval=t_eval, rtol=1e-8, verbose=True)
A_final = sol["y"][0, -1]
B_max = sol["y"][1].max()
t_Bmax = t_eval[np.argmax(sol["y"][1])]
print(f"  A(30 s)  = {A_final:.6f}  (exact: {np.exp(-k1 * 30):.6f})")
print(f"  B_max    = {B_max:.4f}  at t ~ {t_Bmax:.2f} s")
print(f"  nfev     = {sol['nfev']}")

# Plot ODE result
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(sol["t"], sol["y"][0], label="A(t)", color="steelblue")
    ax.plot(sol["t"], sol["y"][1], label="B(t)", color="tomato")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Concentration")
    ax.set_title("Decay chain A -> B -> products  (RK45)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "ode_decay_chain.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: ode_decay_chain.png")
except Exception as e:
    print(f"  Plot skipped: {e}")

# --- 10b. Stiff ODE: Robertson chemical kinetics ---
print("\n--- Stiff BDF: Robertson kinetics (classic benchmark) ---")


def robertson(t, y):
    k1, k2, k3 = 0.04, 3e7, 1e4
    return [
        -k1 * y[0] + k2 * y[1] * y[2],
        k1 * y[0] - k2 * y[1] * y[2] - k3 * y[1] ** 2,
        k3 * y[1] ** 2,
    ]


sol_stiff = solvers.solve_ode_stiff(
    robertson, (0, 1e11), [1.0, 0.0, 0.0], method="BDF", rtol=1e-8, verbose=True
)
y_end = sol_stiff["y"][:, -1]
print(f"  y(t=1e11): A={y_end[0]:.6f}  B={y_end[1]:.2e}  C={y_end[2]:.6f}")
print(f"  A + B + C = {y_end.sum():.8f}  (should = 1.0, conservation check)")

# --- 10c. ODE with event: find when B peaks ---
print("\n--- ODE with event: stop when dB/dt = 0 ---")


def dB_dt_zero(t, y):
    """Event: B reaches its maximum (dB/dt = 0)"""
    k1, k2 = 0.1, 0.3
    A, B = y
    return k1 * A - k2 * B  # zero when B peaks


dB_dt_zero.terminal = True
dB_dt_zero.direction = -1  # peak: going from + to -

sol_event = solvers.solve_ode(
    decay_chain, (0, 30), [1.0, 0.0], events=dB_dt_zero, rtol=1e-10
)
if sol_event["sol"].t_events[0].size > 0:
    t_peak = sol_event["sol"].t_events[0][0]
    y_peak = sol_event["sol"].y_events[0][0]
    print(
        f"  B peaks at t = {t_peak:.4f} s  (analytic: {np.log(k2 / k1) / (k2 - k1):.4f} s)"
    )
    print(f"  B_max = {y_peak[1]:.6f}")


# =========================================================================
# 11. BVP SOLVER
# =========================================================================
section("11. BOUNDARY VALUE PROBLEM (BVP)")

# Solve the heat conduction BVP:
#   -k T'' = q_dot  (volumetric heat source)
#   T(0) = T_left   (Dirichlet)
#   T(L) = T_right  (Dirichlet)
#
# Transform to first-order: y = [T, T']
#   y[0]' = y[1]
#   y[1]' = -q_dot / k

T_left_val = 300.0  # K
T_right_val = 500.0  # K
k_cond = 50.0  # W/m/K  (steel-ish)
q_dot = 1e6  # W/m^3  (volumetric heat source)
L_slab = 0.1  # m


def heat_bvp_rhs(x, y):
    """dy/dx = [T', T''] -> [y[1], -q_dot/k]"""
    return np.vstack([y[1], np.full_like(x, -q_dot / k_cond)])


def heat_bvp_bc(ya, yb):
    """Boundary: T(0) = T_left, T(L) = T_right"""
    return np.array([ya[0] - T_left_val, yb[0] - T_right_val])


# Initial mesh and guess (linear profile as starting guess)
x_mesh = np.linspace(0, L_slab, 10)
T_guess = np.linspace(T_left_val, T_right_val, 10)
y_guess = np.zeros((2, 10))
y_guess[0] = T_guess
y_guess[1] = (T_right_val - T_left_val) / L_slab  # constant slope guess

bvp_result = solvers.solve_bvp(heat_bvp_rhs, heat_bvp_bc, x_mesh, y_guess, verbose=True)

# Evaluate on fine grid
x_fine = np.linspace(0, L_slab, 200)
T_fine = bvp_result["sol"](x_fine)[0]

# Analytic solution: T(x) = T_left + (T_right-T_left)*x/L - q_dot/(2k) * x*(L-x)
T_analytic = (
    T_left_val
    + (T_right_val - T_left_val) * x_fine / L_slab
    - q_dot / (2 * k_cond) * x_fine * (L_slab - x_fine)
)

max_err = np.max(np.abs(T_fine - T_analytic))
T_max_numerical = T_fine.max()
T_max_analytic = T_analytic.max()

print(f"\n  T_max numerical = {T_max_numerical:.4f} K")
print(f"  T_max analytic  = {T_max_analytic:.4f} K")
print(f"  Max error       = {max_err:.4e} K  (BVP success={bvp_result['success']})")

try:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_fine * 100, T_fine, "-", label="BVP numerical", linewidth=2)
    ax.plot(x_fine * 100, T_analytic, "--", label="Analytic", linewidth=1.5)
    ax.set_xlabel("x [cm]")
    ax.set_ylabel("Temperature [K]")
    ax.set_title("Heat conduction with volumetric source -- BVP solution")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "bvp_heat.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: bvp_heat.png")
except Exception as e:
    print(f"  Plot skipped: {e}")


# =========================================================================
# 12. 1D HEAT PDE -- CRANK-NICOLSON
# =========================================================================
section("12. 1D HEAT EQUATION -- Crank-Nicolson FD")

# Fin cooling: Gaussian initial temperature distribution decays to walls
# alpha = k / (rho cp)  for aluminium
rho_al = 2700.0  # kg/m^3
cp_al = 900.0  # J/kg/K
k_al = 205.0  # W/m/K
alpha = k_al / (rho_al * cp_al)  # ~ 8.46e-5 m^2/s

print(f"\n  Aluminium alpha = {alpha:.4e} m2/s")

pde_result = solvers.solve_pde_heat_1d(
    alpha=alpha,
    x_span=(0.0, 0.1),  # 10 cm slab
    t_span=(0.0, 60.0),  # 60 second transient
    u_init=lambda x: 300.0 + 200.0 * np.exp(-500 * (x - 0.05) ** 2),
    bc_left=300.0,  # constant 300 K wall
    bc_right=300.0,  # constant 300 K wall
    nx=60,
    nt=600,  # 600 steps (Crank-Nicolson is unconditionally stable)
    verbose=True,
)

x = pde_result["x"]
t = pde_result["t"]
u = pde_result["u"]

T_center_init = u[0, 40]  # near x = 0.05 m
T_center_final = u[-1, 40]  # after 60 s
print(f"\n  T(center, t=0)  = {T_center_init:.2f} K")
print(f"  T(center, t=60) = {T_center_final:.2f} K  (cooled toward 300 K)")
print(
    f"  Grid: {pde_result['dx'] * 100:.2f} cm spacing, {pde_result['dt']:.3f} s time step"
)

try:
    import matplotlib.pyplot as plt
    from matplotlib import cm as mpl_cm

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Spatial profiles at several time snapshots
    ax1 = axes[0]
    t_indices = [0, len(t) // 6, len(t) // 3, len(t) // 2, len(t) - 1]
    colors = plt.cm.viridis(np.linspace(0, 1, len(t_indices)))
    for idx, col in zip(t_indices, colors):
        ax1.plot(x * 100, u[idx], color=col, label=f"t={t[idx]:.1f} s", linewidth=1.5)
    ax1.set_xlabel("x [cm]")
    ax1.set_ylabel("Temperature [K]")
    ax1.set_title("Temperature profiles at snapshots")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Center temperature vs time
    ax2 = axes[1]
    ax2.plot(t, u[:, 40], color="steelblue", linewidth=2)
    ax2.axhline(300, color="gray", linestyle="--", label="Wall T = 300 K")
    ax2.set_xlabel("Time [s]")
    ax2.set_ylabel("Temperature [K]")
    ax2.set_title("Center temperature vs time")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.suptitle(
        "1D Heat Equation -- Crank-Nicolson (aluminium slab)",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "pde_heat_1d.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved: pde_heat_1d.png")
except Exception as e:
    print(f"  Plot skipped: {e}")


# =========================================================================
# 13. NASA CEA DETONATION ADAPTER
# =========================================================================
section("13. NASA CEA -- Chapman-Jouguet Detonation")

from anvil.adapters import nasa_cea_detonation
from anvil.adapters.nasa_cea_detonation import cea_detonation

if not nasa_cea_detonation.is_available():
    print("\n  NASA CEA not installed (pip install cea) -- section skipped.")
    print("\n" + "=" * 70)
    print("  Done (CEA sections skipped).")
    raise SystemExit(0)

# Single call -- full output
print("\n--- H2/O2 stoichiometric at 1 atm, 300 K ---")
cea_r = cea_detonation.func(
    fuel="H2",
    oxidizer="O2",
    fuel_moles=2.0,
    ox_moles=1.0,
    T1=300.0,
    P1=101325.0,
)

print("\n  Core CJ state:")
core_keys = ["D_CJ", "T_CJ", "P_CJ", "P_ratio", "rho_CJ", "gamma_CJ", "a_CJ", "u_CJ"]
for k in core_keys:
    v = cea_r[k]
    if isinstance(v, Q):
        print(f"    {k:10s} = {v} {v.unit}")
    else:
        print(f"    {k:10s} = {v:.4f}")

print("\n  Thermochemical:")
for k in ["cp_CJ", "cv_CJ", "e_CJ", "h_CJ"]:
    v = cea_r[k]
    print(f"    {k:10s} = {v} {v.unit}")

print("\n  Transport:")
for k in ["mu_CJ", "k_CJ", "Pr_CJ"]:
    v = cea_r[k]
    if isinstance(v, Q):
        print(f"    {k:10s} = {v} {v.unit}")
    else:
        print(f"    {k:10s} = {v:.4f}")

print("\n  Product species (mole fractions):")
sp = cea_r.get("species_CJ", {})
if sp:
    for name, frac in sorted(sp.items(), key=lambda x: -x[1]):
        bar_str = "#" * int(frac * 30)
        print(f"    {name:8s}  {frac:.4f}  {bar_str}")
else:
    print("    (species not available in this CEA version)")

# Verify adapter info
print(f"\n{cea_detonation.info()}")

# Sweep over initial pressure: 0.5 -> 5 atm
print("\n--- Pressure sweep: 0.5 -> 5 atm ---")
P1_vals_Pa = np.linspace(0.5 * 101325, 5 * 101325, 8)
D_vals, T_vals, P_ratio_vals = [], [], []

for P1 in P1_vals_Pa:
    r_p = cea_detonation.func(
        fuel="H2", oxidizer="O2", fuel_moles=2.0, ox_moles=1.0, T1=300.0, P1=float(P1)
    )
    D_vals.append(float(r_p["D_CJ"]._si_value))
    T_vals.append(float(r_p["T_CJ"]._si_value))
    P_ratio_vals.append(r_p["P_ratio"])

print(f"\n  {'P1 [atm]':>10}  {'D_CJ [m/s]':>12}  {'T_CJ [K]':>10}  {'P_ratio':>8}")
print(f"  {'-' * 46}")
for P1, D, T, PR in zip(P1_vals_Pa, D_vals, T_vals, P_ratio_vals):
    print(f"  {P1 / 101325:>10.2f}  {D:>12.1f}  {T:>10.1f}  {PR:>8.2f}")

# Plot CEA pressure sweep
try:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    P_atm_arr = P1_vals_Pa / 101325
    labels_data = [
        ("D_CJ [m/s]", D_vals),
        ("T_CJ [K]", T_vals),
        ("P2/P1", P_ratio_vals),
    ]
    for ax, (ylabel, ydata) in zip(axes, labels_data):
        ax.plot(P_atm_arr, ydata, "o-", color="firebrick", linewidth=1.5, markersize=5)
        ax.set_xlabel("P1 [atm]")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    fig.suptitle(
        "H2/O2 CJ Detonation -- Pressure Sweep", fontsize=12, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "cea_pressure_sweep.png"), dpi=150)
    plt.close(fig)
    print(f"\n  Saved: cea_pressure_sweep.png")
except Exception as e:
    print(f"  Plot skipped: {e}")

# Fuel comparison at 1 atm
print("\n--- Fuel comparison at 1 atm, T1=300 K ---")
fuels = [
    ("H2", "O2", 2.0, 1.0),
    ("CH4", "O2", 1.0, 2.0),
    ("C2H4", "O2", 1.0, 3.0),
    ("C3H8", "O2", 1.0, 5.0),
]
print(
    f"  {'Fuel':>6}  {'D_CJ [m/s]':>12}  {'T_CJ [K]':>10}  {'P_ratio':>8}  "
    f"{'gamma_CJ':>6}  {'a_CJ [m/s]':>12}"
)
print(f"  {'-' * 62}")
for fuel_name, ox_name, fm, om in fuels:
    rc = cea_detonation.func(
        fuel=fuel_name,
        oxidizer=ox_name,
        fuel_moles=fm,
        ox_moles=om,
        T1=300.0,
        P1=101325.0,
    )
    print(
        f"  {fuel_name:>6}  "
        f"{float(rc['D_CJ']._si_value):>12.1f}  "
        f"{float(rc['T_CJ']._si_value):>10.1f}  "
        f"{rc['P_ratio']:>8.2f}  "
        f"{rc['gamma_CJ']:>6.3f}  "
        f"{float(rc['a_CJ']._si_value):>12.1f}"
    )


# =========================================================================
# 14. REGISTRY OPERATIONS
# =========================================================================
section("14. REGISTRY OPERATIONS")


# --- 14a. Register a custom relation ---
@anvil.relation(domain="heat_transfer.fins", tags=["fin", "efficiency"])
def fin_effectiveness(h, P_fin, k_fin, A_c, A_total):
    """
    Fin effectiveness: ratio of heat transfer with fin to without fin.
    eps = Q_fin / Q_without_fin
    """
    import numpy as np

    m = (h * P_fin / (k_fin * A_c)) ** 0.5
    L = A_c / P_fin  # characteristic length
    Q_fin = (h * P_fin * k_fin * A_c) ** 0.5  # per unit DT
    Q_no_fin = h * A_c
    effectiveness = Q_fin / Q_no_fin
    return {"fin_eff": effectiveness}


print(f"\nRegistered: fin_effectiveness")
print(fin_effectiveness.info())  # use the object directly (namespace rebuild is async)

# --- 14b. Search registry ---
print("\nSearch 'compressible':")
hits = anvil.registry.search("compressible")
for h in hits[:4]:
    print(f"  [{h['type']}] {h['name']:30s}  {h['description'][:50]}")

print("\nSearch 'orbital':")
hits2 = anvil.registry.search("orbital")
for h in hits2:
    print(f"  [{h['type']}] {h['name']:30s}  {h['description'][:50]}")

# --- 14c. List by domain ---
print("\nList domain='aero':")
anvil.registry.list(domain="aero")

# --- 14d. Detailed info on a specific RSQ ---
print("\nInfo on 'normal_shock':")
anvil.registry.info("normal_shock")


# --- 14e. Update an existing RSQ ---
@anvil.relation(
    domain="heat_transfer.fins",
    tags=["fin", "efficiency", "v2"],
    name="fin_effectiveness",
    register=False,
)
def fin_effectiveness_v2(h, P_fin, k_fin, A_c, A_total):
    """Fin effectiveness -- improved (includes fin tip correction)."""
    m_val = (h * P_fin / (k_fin * A_c)) ** 0.5
    L_c = A_c / P_fin + A_c / P_fin * 0.05  # tip correction ~ 5%
    mL = m_val * L_c
    import numpy as np

    Q_fin = (h * P_fin * k_fin * A_c) ** 0.5 * np.tanh(mL) / mL
    Q_no_fin = h * A_c
    return {"fin_eff": Q_fin / Q_no_fin}


anvil.update(
    fin_effectiveness_v2,
    name="fin_effectiveness",
    domain="heat_transfer.fins",
    tags=["fin", "efficiency", "v2"],
)

# --- 14f. Export source ---
print("\nExport source of 'ideal_gas_rho':")
anvil.registry.export("ideal_gas_rho")


# =========================================================================
# FINAL SUMMARY
# =========================================================================
section("FILES SAVED")
saved = [
    "nozzle_result.csv",
    "sweep_pressure.csv",
    "convergence.png",
    "variable_trace.png",
    "sweep_plot.png",
    "dependency_graph.png",
    "ode_decay_chain.png",
    "bvp_heat.png",
    "pde_heat_1d.png",
    "cea_pressure_sweep.png",
]
for f in saved:
    path = os.path.join(OUT_DIR, f)
    exists = os.path.exists(path)
    print(f"  {'OK' if exists else 'MISSING':6s}  {f}")

print(f"\n{'=' * 65}")
print(f"  Anvil Framework showcase complete.")
print(f"{'=' * 65}\n")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: Signal Processing RSQs

`examples/ex_signal_processing.py`: all 7 signal processing RSQs in the misc domain

```python
import sys, os

import numpy as np
import anvil

rng = np.random.default_rng(42)

# ── Shared signals ────────────────────────────────────────────────────────────
fs   = 2048.0                              # sample rate [Hz]
dt   = 1.0 / fs
n    = 4096
t    = np.arange(n) * dt                   # 2 seconds

# Clean signal: 50 Hz fundamental + 3rd harmonic
sig_clean = np.sin(2*np.pi*50*t) + 0.3*np.sin(2*np.pi*150*t)

# Noisy version
noise     = 0.4 * rng.standard_normal(n)
sig_noisy = sig_clean + noise

# Chirp: frequency sweeps 20 -> 400 Hz over 2 s
chirp = np.sin(2*np.pi * (20 + 190*t) * t)

# AM signal: 500 Hz carrier, 8 Hz modulation
am = (1 + 0.7*np.sin(2*np.pi*8*t)) * np.sin(2*np.pi*500*t)

# Bearing fault: 2 kHz carrier, 120 Hz outer-race fault, noise
# Needs fs > 2*2500 = 5 kHz; use separate higher sample rate
fs_fault  = 8192.0
dt_fault  = 1.0 / fs_fault
n_fault   = 16384
t_fault   = np.arange(n_fault) * dt_fault
fault     = (1 + 0.6*np.sin(2*np.pi*120*t_fault)) * np.sin(2*np.pi*2000*t_fault) \
            + 0.3*rng.standard_normal(n_fault)


# ══════════════════════════════════════════════════════════════════════════════
# 1. fft_spectrum
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("1. fft_spectrum, power spectrum")
print("=" * 60)

r = anvil.R.fft_spectrum(signal=sig_clean, dt=dt, window="hann")
print(f"  Signal: 50 Hz + 0.3x150 Hz")
print(f"  dominant_freq  = {r['dominant_freq']:.1f} Hz")
print(f"  RMS            = {r['rms']:.4f}")
print(f"  THD            = {r['thd']:.4f}  (~= 0.30 = amplitude of 3rd harmonic)")
print(f"  f_resolution   = {r['f_resolution']:.3f} Hz  (= 1 / 2 s = 0.5 Hz)")
print(f"  spectrum shape : {r['power'].shape}  ({r['n_samples']} samples -> {len(r['freqs'])} bins)")

# Window comparison
print(f"\n  Window comparison (same signal):")
for win in ["none", "hann", "hamming", "blackman"]:
    rw = anvil.R.fft_spectrum(signal=sig_clean, dt=dt, window=win)
    print(f"    {win:10s}: dominant={rw['dominant_freq']:.1f} Hz  THD={rw['thd']:.4f}")
print("  (rectangular 'none' accurate for exact-integer-cycle signals)")


# ══════════════════════════════════════════════════════════════════════════════
# 2. welch_psd
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("2. welch_psd, averaged power spectral density")
print("=" * 60)

r_fft   = anvil.R.fft_spectrum(signal=sig_noisy, dt=dt)
r_welch = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=512)

print(f"  Noisy signal (SNR ~= {20*np.log10(0.7/0.4):.1f} dB)")
print(f"  FFT  dominant_freq = {r_fft['dominant_freq']:.1f} Hz")
print(f"  Welch dominant_freq = {r_welch['dominant_freq']:.1f} Hz")
print(f"  Welch total_power   = {r_welch['total_power']:.4f}")
print(f"  Welch f_resolution  = {r_welch['f_resolution']:.3f} Hz  (nperseg=512)")
print(f"  PSD shape: {r_welch['psd'].shape}")

# nperseg tradeoff
print(f"\n  nperseg tradeoff (noise floor vs resolution):")
for nperseg in [128, 256, 512, 1024]:
    rw = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=nperseg)
    print(f"    nperseg={nperseg:4d}: f_res={rw['f_resolution']:.2f} Hz  "
          f"dominant={rw['dominant_freq']:.1f} Hz")


# ══════════════════════════════════════════════════════════════════════════════
# 3. stft_spectrogram
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("3. stft_spectrogram, time-frequency power map")
print("=" * 60)

r = anvil.R.stft_spectrogram(signal=chirp, dt=dt, nperseg=256, window="hann")
print(f"  Chirp: 20 -> 400 Hz sweep over 2 s")
print(f"  S shape (n_freq x n_time): {r['S'].shape}")
print(f"  n_frames : {r['n_frames']}")
print(f"  t_peak   = {r['t_peak']:.3f} s   (energy peak near end, highest freq)")
print(f"  f_peak   = {r['f_peak']:.1f} Hz")

# Time-frequency slices: check instantaneous frequency tracks the chirp
t_centers = r['t']
f_inst_expected = 20 + 190 * t_centers   # f(t) = 20 + 2x95xt (chirp formula: d/dt[(20+190t)t])
f_inst_expected = np.clip(f_inst_expected, 0, fs/2)

# Find peak frequency per time frame
f_per_frame = r['freqs'][np.argmax(r['S'], axis=0)]
print(f"\n  Instantaneous frequency tracking (sample frames):")
step = max(1, len(t_centers)//8)
print(f"  {'t [s]':>7}  {'f_inst [Hz]':>12}  {'f_expected [Hz]':>16}")
for i in range(0, len(t_centers), step):
    print(f"  {t_centers[i]:7.3f}  {f_per_frame[i]:12.1f}  {f_inst_expected[i]:16.1f}")
print("  (STFT tracks swept frequency through time)")


# ══════════════════════════════════════════════════════════════════════════════
# 4. bandpass_filter
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("4. bandpass_filter, zero-phase Butterworth")
print("=" * 60)

# Lowpass: keep 50 Hz, suppress 150 Hz harmonic and noise
r_lp = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_high=80.0, order=5)
print(f"  Lowpass  (f_high=80 Hz, order=5):")
print(f"    RMS in  = {r_lp['rms_in']:.4f}")
print(f"    RMS out = {r_lp['rms_out']:.4f}  (noise + 150 Hz removed)")
print(f"    att.    = {r_lp['attenuation_dB']:.1f} dB")

# Bandpass: isolate 50 Hz ± 20 Hz band
r_bp = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_low=30.0, f_high=70.0, order=4)
print(f"\n  Bandpass (30-70 Hz, order=4):")
print(f"    RMS in  = {r_bp['rms_in']:.4f}")
print(f"    RMS out = {r_bp['rms_out']:.4f}  (only 50 Hz component passes)")
print(f"    att.    = {r_bp['attenuation_dB']:.1f} dB")

# Highpass: remove DC drift
drift = sig_clean + 2.5 + 0.3*t   # add DC + slow drift
r_hp = anvil.R.bandpass_filter(signal=drift, dt=dt, f_low=5.0, order=3)
print(f"\n  Highpass (f_low=5 Hz, order=3): removes DC/drift")
print(f"    mean before filter = {drift.mean():.3f}")
print(f"    mean after filter  = {r_hp['signal_filtered'].mean():.6f}  (~= 0)")

# Order comparison
print(f"\n  Filter order vs stopband attenuation (bandpass 30-70 Hz):")
for order in [2, 4, 6, 8]:
    rr = anvil.R.bandpass_filter(signal=sig_noisy, dt=dt, f_low=30, f_high=70, order=order)
    print(f"    order={order}: RMS_out={rr['rms_out']:.4f}  att={rr['attenuation_dB']:.1f} dB")


# ══════════════════════════════════════════════════════════════════════════════
# 5. envelope_detection
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("5. envelope_detection, Hilbert transform")
print("=" * 60)

r = anvil.R.envelope_detection(signal=am, dt=dt)
print(f"  AM signal: 500 Hz carrier, 8 Hz modulation depth=0.7")
print(f"  peak_envelope = {r['peak_envelope']:.4f}  (expected ~= 1.70)")
print(f"  mean_envelope = {r['mean_envelope']:.4f}  (expected ~= 1.00)")
print(f"  carrier freq  ~= {float(np.median(r['inst_freq'])):.1f} Hz  (median of inst_freq)")

# Envelope spectrum: FFT of envelope reveals modulation frequency
env_spec = anvil.R.fft_spectrum(signal=r['envelope'], dt=dt, window="hann")
# Find second peak (skip DC region)
mask = env_spec['freqs'] > 2
f_mod = env_spec['freqs'][mask][np.argmax(env_spec['power'][mask])]
print(f"  modulation freq from envelope spectrum = {f_mod:.1f} Hz  (expected 8 Hz)")

# Fault signal: bearing fault detection (uses higher sample rate signal)
print(f"\n  Bearing fault detection (2 kHz carrier, 120 Hz fault, fs={int(fs_fault)} Hz):")
# Step 1: bandpass around 2 kHz carrier
r_bp = anvil.R.bandpass_filter(signal=fault, dt=dt_fault, f_low=1500, f_high=2500, order=5)
# Step 2: envelope
r_env = anvil.R.envelope_detection(signal=r_bp['signal_filtered'], dt=dt_fault)
# Step 3: FFT of envelope -> fault frequency appears at 120 Hz
r_env_spec = anvil.R.fft_spectrum(signal=r_env['envelope'], dt=dt_fault, window="hann")
mask2 = r_env_spec['freqs'] > 10
f_fault_det = r_env_spec['freqs'][mask2][np.argmax(r_env_spec['power'][mask2])]
print(f"  Detected fault frequency = {f_fault_det:.1f} Hz  (expected 120 Hz)")


# ══════════════════════════════════════════════════════════════════════════════
# 6. cross_correlation
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("6. cross_correlation, time delay estimation")
print("=" * 60)

# Use broadband (noise) signal, xcorr on periodic sine has many equal peaks
# making argmax unreliable without restricting the lag search window.
delay_samples = 35
# Use broadband signal, xcorr on a pure periodic sine has many equal-height
# peaks separated by the signal period, making argmax unreliable.
# broadband noise has a unique peak at the true delay.
broadband = rng.standard_normal(n)
sig_ref    = broadband                          # reference (earlier sensor)
sig_del    = np.roll(broadband, delay_samples)  # delayed copy (later sensor)

# Correlate (delayed, reference) -> peak at +delay_samples
r = anvil.R.cross_correlation(signal_a=sig_del, signal_b=sig_ref, dt=dt)
print(f"  Broadband signal, delay = {delay_samples} samples = {delay_samples*dt*1000:.3f} ms")
print(f"  Detected lag    = {r['lag_peak']*1000:.3f} ms  ({round(r['lag_peak']/dt):.0f} samples)")
print(f"  corr_peak       = {r['corr_peak']:.6f}  (1.0 = perfect match)")

# Noisy: does xcorr still recover the delay?
print(f"\n  Noise robustness (broadband, 35-sample delay):")
for snr_db in [20, 10, 3, 0]:
    noise_amp = 10**(-snr_db/20)
    sig_del_noisy = sig_del + noise_amp * rng.standard_normal(n)
    rr = anvil.R.cross_correlation(signal_a=sig_del_noisy, signal_b=sig_ref, dt=dt)
    detected = round(rr['lag_peak']/dt)
    print(f"    SNR={snr_db:3d} dB: lag={detected:4.0f} samples  corr_peak={rr['corr_peak']:.4f}")

# Flow velocity measurement from two sensors
print(f"\n  Flow velocity (two probes, d=0.5 m apart):")
d_probe      = 0.5   # m
broadband2   = rng.standard_normal(n)
v_true       = 12.5  # m/s -> delay = d/v
delay_samp   = int(d_probe / v_true / dt)
sig_down     = np.roll(broadband2, delay_samp)
r_flow       = anvil.R.cross_correlation(signal_a=broadband2, signal_b=sig_down, dt=dt)
v_measured   = d_probe / abs(r_flow['lag_peak'])
print(f"    True velocity     = {v_true:.2f} m/s  (delay = {delay_samp} samples)")
print(f"    Measured velocity = {v_measured:.2f} m/s  (lag={r_flow['lag_peak']*1000:.2f} ms)")


# ══════════════════════════════════════════════════════════════════════════════
# 7. signal_statistics
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("7. signal_statistics, descriptive statistics")
print("=" * 60)

signals = {
    "sine 50 Hz":      (sig_clean,  dt),
    "sine + noise":    (sig_noisy,  dt),
    "Gaussian noise":  (rng.standard_normal(n), dt),
    "bearing fault":   (fault[:n],  dt_fault),   # use same-length slice
    "impulse train":   (np.where((np.arange(n) % 256) == 0, 5.0, 0.0) + 0.1*rng.standard_normal(n), dt),
}

print(f"  {'Signal':>16}  {'RMS':>6}  {'Crest':>6}  {'Kurtosis':>10}  {'Skew':>6}")
for name, (s, s_dt) in signals.items():
    r = anvil.R.signal_statistics(signal=s, dt=s_dt)
    print(f"  {name:>16}  {r['rms']:6.3f}  {r['crest_factor']:6.3f}  {r['kurtosis']:10.4f}  {r['skewness']:6.3f}")

print(f"\n  Notes:")
print(f"    Gaussian noise: kurtosis ~= 3.0 (mesokurtic)")
print(f"    Bearing fault:  kurtosis > 3, impulsive content from carrier modulation")
print(f"    Impulse train:  very high crest factor and kurtosis, sparse, large peaks")
print(f"    Sine: kurtosis ~= 1.5, crest factor = sqrt2 ~= 1.414")


# ══════════════════════════════════════════════════════════════════════════════
# 8. Sweep example: SNR effect on dominant frequency detection
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("8. Direct loop, nperseg vs Welch frequency resolution")
print("=" * 60)

# Note: sys.sweep() sweeps scalar parameters. Array inputs (signal) must be
# fixed; sweep over numeric parameters like nperseg directly.
print(f"  {'nperseg':>8}  {'f_res [Hz]':>12}  {'dominant [Hz]':>15}  {'dom_psd':>10}")
for nperseg in [64, 128, 256, 512, 1024, 2048]:
    rw = anvil.R.welch_psd(signal=sig_noisy, dt=dt, nperseg=nperseg)
    print(f"  {nperseg:>8}  {rw['f_resolution']:12.3f}  {rw['dominant_freq']:15.1f}  {rw['dominant_psd']:.4f}")
print("  (larger nperseg -> finer freq resolution; fewer averages -> higher variance)")


# ══════════════════════════════════════════════════════════════════════════════
# 9. Full pipeline: vibration health monitoring
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("9. Full pipeline: vibration health monitoring")
print("=" * 60)

for fault_level in [0.0, 0.3, 0.6, 1.0]:
    # Use higher fs to accommodate 2 kHz carrier + 1500-2500 Hz bandpass
    vibration = (1 + fault_level*np.sin(2*np.pi*120*t_fault)) * np.sin(2*np.pi*2000*t_fault) \
                + 0.2*rng.standard_normal(n_fault)

    # Step 1: raw statistics
    stats = anvil.R.signal_statistics(signal=vibration, dt=dt_fault)

    # Step 2: bandpass around 2 kHz, extract envelope
    bp     = anvil.R.bandpass_filter(signal=vibration, dt=dt_fault, f_low=1500, f_high=2500, order=5)
    env    = anvil.R.envelope_detection(signal=bp['signal_filtered'], dt=dt_fault)
    espec  = anvil.R.fft_spectrum(signal=env['envelope'], dt=dt_fault, window="hann")

    mask3  = espec['freqs'] > 10
    f_detected = espec['freqs'][mask3][np.argmax(espec['power'][mask3])]
    p_fault    = float(espec['power'][mask3][np.argmax(espec['power'][mask3])])

    print(f"  fault_level={fault_level:.1f}:  kurtosis={stats['kurtosis']:.2f}  "
          f"crest={stats['crest_factor']:.2f}  "
          f"f_fault={f_detected:.0f} Hz  fault_power={p_fault:.4f}")

print("  (fault_level 0 -> kurtosis near Gaussian, fault_power ~noise floor)")
print("  (fault_level 1.0 -> elevated kurtosis, fault frequency at 120 Hz clearly detected)")
```

**Output:**

```
============================================================
1. fft_spectrum, power spectrum
============================================================
  Signal: 50 Hz + 0.3x150 Hz
  dominant_freq  = 50.0 Hz
  RMS            = 0.7382
  THD            = 0.3000  (~= 0.30 = amplitude of 3rd harmonic)
  f_resolution   = 0.500 Hz  (= 1 / 2 s = 0.5 Hz)
  spectrum shape : (2049,)  (4096 samples -> 2049 bins)

  Window comparison (same signal):
    none      : dominant=50.0 Hz  THD=0.3000
    hann      : dominant=50.0 Hz  THD=0.3000
    hamming   : dominant=50.0 Hz  THD=0.3000
    blackman  : dominant=50.0 Hz  THD=0.3000
  (rectangular 'none' accurate for exact-integer-cycle signals)

============================================================
2. welch_psd, averaged power spectral density
============================================================
  Noisy signal (SNR ~= 4.9 dB)
  FFT  dominant_freq = 50.0 Hz
  Welch dominant_freq = 48.0 Hz
  Welch total_power   = 0.6956
  Welch f_resolution  = 4.000 Hz  (nperseg=512)
  PSD shape: (257,)

  nperseg tradeoff (noise floor vs resolution):
    nperseg= 128: f_res=16.00 Hz  dominant=48.0 Hz
    nperseg= 256: f_res=8.00 Hz  dominant=48.0 Hz
    nperseg= 512: f_res=4.00 Hz  dominant=48.0 Hz
    nperseg=1024: f_res=2.00 Hz  dominant=50.0 Hz

============================================================
... (112 more lines)
```


## Example: SU2 CFD Adapter (real only -- requires SU2_CFD on PATH)

`examples/ex_su2_adapter.py`: su2_euler and su2_rans against a real SU2 install.

```python
import sys, os

import anvil
from anvil.adapters import su2_aero
from anvil.adapters.su2_aero import su2_euler, su2_rans, register

if not su2_aero.is_available():
    print("SU2_CFD binary not found on PATH -- skipping example.")
    print("Install: https://su2code.github.io/download.html")
    raise SystemExit(0)

if len(sys.argv) < 3:
    print("Usage: python ex_su2_adapter.py <case.cfg> <mesh.su2>")
    print("Grab a tutorial case (cfg + su2 mesh) from:")
    print("  https://su2code.github.io/tutorials/Inviscid_2D_Unconstrained_NACA0012/")
    raise SystemExit(0)

cfg_path, mesh_path = sys.argv[1], sys.argv[2]
for p in (cfg_path, mesh_path):
    if not os.path.exists(p):
        raise SystemExit(f"File not found: {p}")

# ── Euler (inviscid) ─────────────────────────────────────────────────────────
print("=== SU2 Euler: inviscid (M=0.5, AoA=2 deg) ===")
r = su2_euler(cfg_template=cfg_path, mesh=mesh_path, Mach=0.5, AoA_deg=2.0)
print(f"  CL = {r['CL']:.4f}   CD = {r['CD']:.5f}   CM = {r['CM']:.4f}")

# ── Mach sweep: wave drag onset ──────────────────────────────────────────────
print("\n=== Wave drag onset: CD vs Mach (AoA=2 deg, inviscid) ===")
sys_ = anvil.system("su2_mach_sweep")
sys_.add("cfg_template", cfg_path)
sys_.add("mesh",         mesh_path)
sys_.add("AoA_deg",      2.0)
sys_.add("Mach",         0.5)   # placeholder; swept below
sys_.use(su2_euler)

sweep = sys_.sweep("Mach", [0.5, 0.7, 0.8, 0.85, 0.9])
print(f"  {'Mach':>6}  {'CL':>7}  {'CD':>8}")
for i in range(len(sweep.table)):
    row = sweep.table.iloc[i]
    print(f"  {row['Mach']:6.2f}  {row['CL']:7.4f}  {row['CD']:8.5f}")
print("  (CD rises sharply past the drag-divergence Mach number)")

# ── RANS (viscous) -- needs a cfg with a turbulence model + wall BC mesh ─────
# Uncomment if your cfg/mesh pair is a RANS case:
# r2 = su2_rans(cfg_template=cfg_path, mesh=mesh_path,
#               Mach=0.3, AoA_deg=4.0, Reynolds=3e6)
# print(f"  CL = {r2['CL']:.4f}   CD = {r2['CD']:.5f} (pressure + friction)")

# ── Register ─────────────────────────────────────────────────────────────────
print("\n=== Register adapters ===")
register()
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: Surrogate Model Adapters

`examples/ex_surrogate_adapter.py`: make_poly_adapter, make_rbf_adapter (real methods on Anvil's

```python
import sys, os

import numpy as np
import anvil
from anvil.adapters import surrogate_models
from anvil.adapters.surrogate_models import (
    make_gp_adapter, make_poly_adapter, make_rbf_adapter, gp_demo, register
)

rng = np.random.default_rng(42)
HAS_SKLEARN = surrogate_models.is_available()
if not HAS_SKLEARN:
    print("scikit-learn not installed -- GP sections skipped.")
    print("Install: pip install scikit-learn\n")

# ── Demo adapter: noisy sine (GP; needs sklearn) ─────────────────────────────
gp_cd = None
if HAS_SKLEARN:
    print("=== Demo GP surrogate: noisy sin(x) ===")
    for x in [0.5, 1.57, 3.14, 4.71]:
        r = gp_demo(x=x)
        print(f"  x={x:.2f}:  y_pred={r['y_pred']:.4f}  y_std={r['y_std']:.4f}"
              f"  exact={r['y_exact']:.4f}")

    # ── GP surrogate from custom data ────────────────────────────────────────
    print("\n=== Custom GP surrogate: drag coefficient vs AoA ===")
    # Synthetic drag polar training data
    aoa_train  = np.linspace(-4, 16, 15)
    cd_train   = 0.01 + 0.003 * aoa_train + 0.0015 * aoa_train**2 + 0.005 * rng.standard_normal(15)
    cd_train   = np.maximum(cd_train, 0.005)

    gp_cd = make_gp_adapter(
        X_train=aoa_train.reshape(-1, 1),
        y_train=cd_train,
        x_name="AoA_deg",
        y_name="CD_pred",
        x_unit="1",
        y_unit="1",
        name="drag_gp",
        desc="GP drag coefficient surrogate from wind tunnel data",
    )
    print("  AoA sweep prediction:")
    for aoa in [-2, 0, 4, 8, 12, 15]:
        r = gp_cd(AoA_deg=float(aoa))
        cd = r["CD_pred"] if not hasattr(r["CD_pred"], "si") else float(r["CD_pred"].si)
        unc = r["CD_pred_std"] if not hasattr(r["CD_pred_std"], "si") else float(r["CD_pred_std"].si)
        print(f"  AoA={aoa:3d} deg:  CD={cd:.5f} +/- {unc:.5f}")

# ── Polynomial surrogate ──────────────────────────────────────────────────────
print("\n=== Polynomial chaos surrogate (degree 4): C_d = f(Re) ===")
Re_train = np.logspace(4, 7, 20)
cd_sphere_train = (
    24.0 / Re_train
    + 6.0 / (1.0 + Re_train**0.5)
    + 0.4
    + 0.01 * rng.standard_normal(20)
)
# Work in log10(Re) space for numerical stability
log_Re_train = np.log10(Re_train)

poly_cd = make_poly_adapter(
    X_train=log_Re_train,
    y_train=cd_sphere_train,
    x_name="log_Re",
    y_name="CD_sphere",
    degree=4,
    name="sphere_drag_poly",
    desc="Sphere drag coefficient polynomial surrogate",
)
print(f"  {'Re':>10}  {'CD_pred':>9}  {'CD_exact':>10}")
for Re in [1e4, 1e5, 5e5, 1e6, 5e6]:
    r = poly_cd(log_Re=np.log10(Re))
    cd_pred  = r["CD_sphere"] if not hasattr(r["CD_sphere"], "si") else float(r["CD_sphere"].si)
    cd_exact = 24/Re + 6/(1+Re**0.5) + 0.4
    print(f"  {Re:10.2e}  {cd_pred:9.5f}  {cd_exact:10.5f}")

# ── RBF surrogate (2-input) ────────────────────────────────────────────────────
print("\n=== RBF surrogate (2 inputs): lift = f(AoA, Mach) ===")
n_pts  = 40
aoa_s  = rng.uniform(-4, 14, n_pts)
mach_s = rng.uniform(0.1, 0.8, n_pts)
cl_s   = (2 * np.pi * np.radians(aoa_s)
           / np.sqrt(1 - mach_s**2)
           + 0.02 * rng.standard_normal(n_pts))

X_2d = np.column_stack([aoa_s, mach_s])

rbf_cl = make_rbf_adapter(
    X_train=X_2d, y_train=cl_s,
    input_names=["AoA_deg", "Mach"],
    y_name="CL_pred",
    function="multiquadric",
    name="lift_rbf",
    desc="Lift coefficient RBF surrogate (AoA, Mach)",
)
print(f"  {'AoA':>5}  {'Mach':>5}  {'CL_RBF':>8}  {'CL_theory':>10}")
for aoa, mach in [(2, 0.3), (5, 0.3), (5, 0.6), (8, 0.5)]:
    r = rbf_cl(AoA_deg=float(aoa), Mach=float(mach))
    cl_rbf = r["CL_pred"] if not hasattr(r["CL_pred"], "si") else float(r["CL_pred"].si)
    import math
    cl_th  = 2*math.pi*math.radians(aoa) / math.sqrt(1 - mach**2)
    print(f"  {aoa:5.1f}  {mach:5.2f}  {cl_rbf:8.4f}  {cl_th:10.4f}")

# ── GP surrogate in Anvil System ──────────────────────────────────────────────
if gp_cd is not None:
    print("\n=== GP surrogate in System: drag polar study ===")
    sys_ = anvil.system("surrogate_polar")
    sys_.add("AoA_deg", 0.0)
    sys_.use(gp_cd)

    alphas = np.linspace(-2, 14, 9)
    sweep  = sys_.sweep("AoA_deg", alphas)
    print(f"  {'AoA':>5}  {'CD_pred':>9}  {'uncertainty':>12}")
    for i in range(len(alphas)):
        row = sweep.table.iloc[i]
        cd  = row.get("CD_pred", None)
        if cd is None:
            continue
        cd  = float(cd.si) if hasattr(cd, "si") else float(cd)
        unc = row.get("CD_pred_std", 0.0)
        unc = float(unc.si) if hasattr(unc, "si") else float(unc)
        print(f"  {alphas[i]:5.1f}  {cd:9.5f}  +/-{unc:.5f}")

# ── Register ──────────────────────────────────────────────────────────────────
if HAS_SKLEARN:
    print("\n=== Register demo adapter ===")
    register()
    print("  Global: gp_demo_sine -> domain surrogate.demo")
    print("  Factories: make_gp_adapter, make_poly_adapter, make_rbf_adapter")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: UQ Adapter -- Monte Carlo Uncertainty Propagation in Anvil

`examples/ex_uq_adapter.py`: the uq_montecarlo adapter: propagate input uncertainty through

```python
import anvil
from anvil import Q
from anvil.adapters.uq_surrogate import uq_montecarlo, register


def _num(v):
    """Plain float of a Q or number (uq outputs are plain floats)."""
    return float(v.value) if hasattr(v, "value") else float(v)


W = 64
print("=" * W)
print("  UQ Monte Carlo Adapter Example (native numpy MC)")
print("=" * W)

register()

# ── 1. UQ over several response models (native numpy MC, always runs) ────────
print("\n[1] a ~ N(10,1), b ~ N(5,0.5), 20000 samples (native numpy)")
print(f"  {'model':10s}  {'mean':>10s}  {'std':>9s}  {'p05':>10s}  {'p95':>10s}  {'R2':>6s}")
print(f"  {'-'*10}  {'-'*10}  {'-'*9}  {'-'*10}  {'-'*10}  {'-'*6}")
for model in ("sum", "product", "ratio", "quadratic"):
    r = uq_montecarlo(model=model, a_mean=10.0, a_std=1.0,
                      b_mean=5.0, b_std=0.5, n_samples=20000, seed=0)
    print(f"  {model:10s}  {_num(r['mean']):10.4f}  {_num(r['std']):9.4f}  "
          f"{_num(r['p05']):10.4f}  {_num(r['p95']):10.4f}  {_num(r['surrogate_r2']):6.3f}")
print(f"  (source: {r['source']})")

# ── 1b. Optional scikit-learn surrogate ──────────────────────────────────────
print("\n[1b] Optional scikit-learn surrogate (surrogate='sklearn')")
try:
    rs = uq_montecarlo(model="product", a_mean=10.0, a_std=1.0,
                       b_mean=5.0, b_std=0.5, n_samples=20000, seed=0,
                       surrogate="sklearn")
    print(f"  sklearn surrogate R^2 = {_num(rs['surrogate_r2']):.4f}  "
          f"(source: {rs['source']})")
except ImportError as e:
    print("  scikit-learn is not installed -- the optional sklearn surrogate")
    print(f"  is unavailable: {e}")
    print("  Install scikit-learn to use it: pip install scikit-learn")
    print("  (The native numpy MC above ran fine without it.)")

# ── 2. Pipeline: UQ feeding a margin calculation ─────────────────────────────
print("\n[2] System: design margin from UQ mean & std (native numpy MC)")
uq = uq_montecarlo(model="product", a_mean=100.0, a_std=5.0,
                   b_mean=2.0, b_std=0.1, n_samples=20000, seed=0)
print(f"  mean    = {_num(uq['mean']):.2f}  (source: {uq['source']})")
print(f"  std     = {_num(uq['std']):.2f}")

study = anvil.system("uq_study")
study.add("mean", _num(uq["mean"]), "1")
study.add("std", _num(uq["std"]), "1")
study.add("limit", 250.0, "1")

def margin(mean, std, limit):
    # Number of std-devs of headroom before exceeding the limit.
    n_sigma = (limit - mean) / std if std > 0 else float("inf")
    return {"n_sigma": Q(n_sigma, "1")}
study.use(margin)

res = study.solve_forward()
print(f"  n_sigma = {res['n_sigma'].value:.2f}")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Example: XFOIL 2D Airfoil Adapter (real only -- requires XFOIL on PATH)

`examples/ex_xfoil_adapter.py`: xfoil_polar and xfoil_alpha_sweep against a real XFOIL binary.

```python
import sys, os

import anvil
from anvil.adapters import xfoil_airfoil
from anvil.adapters.xfoil_airfoil import xfoil_polar, xfoil_alpha_sweep, register

if not xfoil_airfoil.is_available():
    print("XFOIL binary not found on PATH -- skipping example.")
    print("Install: https://web.mit.edu/drela/Public/web/xfoil/")
    print("(put xfoil.exe / xfoil on your PATH, then re-run)")
    raise SystemExit(0)

# ── Single operating point ────────────────────────────────────────────────────
print("=== NACA2412: single point (alpha = 4 deg, Re = 1e6) ===")
r = xfoil_polar(airfoil="NACA2412", Re=1e6, alpha_deg=4.0, Mach=0.1)
print(f"  CL   = {r['CL']:.4f}")
print(f"  CD   = {r['CD']:.5f}")
print(f"  CM   = {r['CM']:.4f}")
print(f"  L/D  = {r['CL']/r['CD']:.1f}")
print(f"  transition (top/bot): {r['xtr_top']:.3f} / {r['xtr_bot']:.3f}")

# ── Polar sweep ───────────────────────────────────────────────────────────────
print("\n=== Alpha sweep (-4 to 12 deg, Re = 1.5e6) ===")
r = xfoil_alpha_sweep(airfoil="NACA2412", Re=1.5e6,
                      alpha_min=-4.0, alpha_max=12.0, alpha_step=2.0,
                      Mach=0.15)
print(f"  Converged points: {r['n_converged']}")
print(f"  CL range: [{r['CL_array'].min():.3f}, {r['CL_array'].max():.3f}]")
best = (r['CL_array'] / r['CD_array']).argmax()
print(f"  Best L/D = {r['LD_max']:.1f} at alpha = {r['alpha_array'][best]:.1f} deg")
print(f"  CL_max   = {r['CL_max']:.3f}")

# ── Reynolds sweep with an Anvil System ──────────────────────────────────────
print("\n=== Reynolds effect on drag (alpha = 4 deg) ===")
sys_ = anvil.system("xfoil_re_study")
sys_.add("airfoil",   "NACA2412")
sys_.add("alpha_deg", 4.0)
sys_.add("Mach",      0.1)
sys_.add("Re",        1e6)   # placeholder; swept below
sys_.use(xfoil_polar)

sweep = sys_.sweep("Re", [2e5, 5e5, 1e6, 2e6, 5e6])
print(f"  {'Re':>10}  {'CL':>7}  {'CD':>8}")
for i in range(len(sweep.table)):
    row = sweep.table.iloc[i]
    print(f"  {row['Re']:10.1e}  {row['CL']:7.4f}  {row['CD']:8.5f}")
print("  (CD drops with Re: thinner boundary layer, later transition)")

# ── Register in project ───────────────────────────────────────────────────────
print("\n=== Register in global registry ===")
register()
print("  xfoil_polar, xfoil_alpha_sweep -> domain aero.xfoil")
```

> Requires an external tool that is not installed here. Run `anvil doctor` for the exact install command, then run the script to see its output.


## Anvil v0.3 Showcase

`examples/showcase.py`: the full RSQ workflow

```python
import os

# Windows consoles default to cp1252; this output uses Greek symbols.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np


import anvil
from anvil import Q, System

print("=" * 60)
print("  Anvil v0.3 Showcase")
print("=" * 60)

# ─────────────────────────────────────────────────
# 1. Browse what's available
# ─────────────────────────────────────────────────

print("\n--- What's in the registry? ---")
anvil.registry.list()

# ─────────────────────────────────────────────────
# 2. Search for something specific
# ─────────────────────────────────────────────────

print("\n--- Search: 'shock' ---")
anvil.registry.search("shock")

print("\n--- Search: 'thrust' ---")
anvil.registry.search("thrust")

# ─────────────────────────────────────────────────
# 3. Use a Relation directly from the registry
# ─────────────────────────────────────────────────

print("\n--- Call isentropic_ratios directly ---")
result = anvil.R.isentropic_ratios(M=2.0, gamma=1.4)
print(f"  M = 2.0, gamma = 1.4")
print(f"  T0/T   = {result['T0_T']:.4f}")
print(f"  P0/P   = {result['P0_P']:.4f}")
print(f"  rho0/rho = {result['rho0_rho']:.4f}")

print("\n--- Normal shock at M=3 ---")
shock = anvil.R.normal_shock(M1=3.0, gamma=1.4)
print(f"  M1 = 3.0")
print(f"  M2     = {shock['M2']:.4f}")
print(f"  P2/P1  = {shock['P2_P1']:.4f}")
print(f"  T2/T1  = {shock['T2_T1']:.4f}")
print(f"  P02/P01 = {shock['P02_P01']:.4f}")

# ─────────────────────────────────────────────────
# 4. Load a pre-built System, no .add() needed
# ─────────────────────────────────────────────────

print("\n--- Load the rocket nozzle system ---")
nozzle = anvil.S.rocket_nozzle
print(nozzle.info())

# Solve with defaults
print("\n--- Solve with defaults ---")
nozzle.solve().summary()

# ─────────────────────────────────────────────────
# 5. Override with .set(), clean, no re-declaration
# ─────────────────────────────────────────────────

print("\n--- Override chamber pressure and solve again ---")
nozzle.set(P0=10e6, T0=3200)
nozzle.solve().summary()

# Override with different unit system
print("\n--- Override with imperial units ---")
nozzle.set(P0=Q(1500, "psi"))
nozzle.solve().summary()

# ─────────────────────────────────────────────────
# 6. Parametric sweep
# ─────────────────────────────────────────────────

print("\n--- Sweep: thrust vs chamber pressure ---")
nozzle.set(P0=6.9e6)  # reset to baseline
sweep = nozzle.sweep("P0", np.linspace(1e6, 20e6, 10))
sweep.summary(outputs=["M_exit", "V_exit", "mdot", "thrust", "Isp"])

# ─────────────────────────────────────────────────
# 7. Compose: nozzle inside a bigger system
# ─────────────────────────────────────────────────

print("\n--- Composition: nozzle + custom delta-V calc ---")


# Define a custom Relation
def delta_v(Isp, mass_ratio):
    """Tsiolkovsky rocket equation: dV = Isp * g0 * ln(mass_ratio)"""
    import numpy as np

    dv = Isp * 9.80665 * np.log(mass_ratio)
    return {"delta_v": Q(dv, "m/s")}


# Build a stage system, use() with a System inherits its defaults
# Get a fresh nozzle from the registry
from anvil.registry.loader import load_rsq

fresh_nozzle = load_rsq(
    anvil.registry._get_store().get("rocket_nozzle"), anvil.registry._get_store()
)

stage = System("rocket_stage")
stage.use(fresh_nozzle)  # inherits all 7 nozzle defaults
stage.add("mass_ratio", 4.0, desc="Initial/final mass ratio")
stage.use(delta_v)

# Solve
stage.solve().summary()

# ─────────────────────────────────────────────────
# 8. Register your own RSQ
# ─────────────────────────────────────────────────

print("\n--- Register a custom Relation ---")


def oblique_shock_angle(M, theta_deg, gamma=1.4):
    """Find weak shock angle beta for given deflection theta."""
    import numpy as np

    from anvil import solvers

    theta = np.radians(theta_deg)
    mu = np.arcsin(1.0 / M)  # Mach angle

    def residual(beta_deg):
        b = np.radians(beta_deg)
        num = M**2 * np.sin(b) ** 2 - 1
        den = M**2 * (gamma + np.cos(2 * b)) + 2
        return np.tan(theta) - 2 * (1 / np.tan(b)) * num / den

    # Initial guess: midpoint between Mach angle and 60 degrees
    x0 = np.degrees(mu) + (60 - np.degrees(mu)) * 0.4
    beta = solvers.find_root(residual, x0=x0, method="newton")
    return {"beta_deg": beta, "beta_rad": np.radians(beta)}


anvil.push(
    oblique_shock_angle,
    domain="aero.compressible",
    tags=["shock", "oblique", "compressible"],
    description="Oblique shock wave angle from deflection angle and Mach",
)

# Now use it from the registry
print("\n--- Use the newly registered Relation ---")
result = anvil.R.oblique_shock_angle(M=3.0, theta_deg=20.0)
print(f"  M=3.0, theta=20 deg")
print(f"  beta = {result['beta_deg']:.2f} deg")

# ─────────────────────────────────────────────────
# 9. Unit conversions on results
# ─────────────────────────────────────────────────

print("\n--- Unit conversions ---")
nozzle.set(P0=6.9e6)
r = nozzle.solve()

F = r["thrust"]
print(f"  Thrust:  {F}  →  {F.to('kN')}  →  {F.to('lbf')}")

T = r["T_exit"]
print(f"  T_exit:  {T}  →  {T.to('R')}")

V = r["V_exit"]
print(f"  V_exit:  {V}  →  {V.to('ft/s')}")

print("\n" + "=" * 60)
print("  Done.")
print("=" * 60)
```

**Output:**

```
============================================================
  Anvil v0.3 Showcase
============================================================

--- What's in the registry? ---

  Relations (171):
    hx_duty                       
    hx_eff_ntu                    
    drag_force                      [aero]  (builtin)
      Drag force: D = 0.5 * rho * V^2 * S * CD
    drag_polar                      [aero]  (builtin)
      Parabolic drag polar: CD = CD0 + CL^2/(pi*e*AR)
    dynamic_pressure                [aero]  (builtin)
      Dynamic pressure: q = 0.5 * rho * V^2
    induced_drag                    [aero]  (builtin)
      Induced drag: CDi = CL^2 / (pi * e * AR)
    lift_force                      [aero]  (builtin)
      Lift force: L = 0.5 * rho * V^2 * S * CL
    oswald_efficiency               [aero]  (builtin)
      Oswald span efficiency estimate from aspect ratio (empirical)
    reynolds_num                    [aero]
      Reynolds number: Re = rho V L / mu
    skin_friction_flat_plate        [aero]  (builtin)
      Average skin-friction coefficient on a flat plate (laminar or turbulen
    stall_speed                     [aero]  (builtin)
      Aircraft stall speed: Vs = sqrt(2*W/(rho*S*CLmax))
    thin_airfoil_cl                 [aero]  (builtin)
      Thin airfoil theory: CL = 2*pi*(alpha + alpha_L0); M correction via Pr
    isa_atmosphere                  [aero.atmosphere]  (builtin)
      International Standard Atmosphere (ISA) up to 86 km
    area_mach_subsonic              [aero.compressible]  (builtin)
      Subsonic Mach from area ratio (A/A*)
    area_mach_supersonic            [aero.compressible]  (builtin)
... (541 more lines)
```


## Pressure-tank blowdown through a hole -- "half-life" drain time for a gas.

`examples/tank_blowdown.py`: Problem

```python
from __future__ import annotations

import argparse
import math

import numpy as np

import anvil
from anvil import Q
from anvil.db import fluids


# --------------------------------------------------------------------------- #
#  Gas properties  (real tabulated data from anvil.db.fluids -- no mocks)
# --------------------------------------------------------------------------- #
# Map friendly CLI names / chemical symbols onto anvil.db.fluids keys.
_SPECIES_ALIASES = {
    "air": "air",
    "n2": "nitrogen", "nitrogen": "nitrogen",
    "o2": "oxygen", "oxygen": "oxygen",
    "co2": "co2", "carbon_dioxide": "co2",
    "h2": "hydrogen", "hydrogen": "hydrogen",
    "he": "helium", "helium": "helium",
    "ch4": "methane", "methane": "methane",
    "ar": "argon", "argon": "argon",
    "c3h8": "propane", "propane": "propane",
}


def gas_properties(species: str, T: float, P: float):
    """Return (gamma, R_gas [J/kg/K]) for `species` from the real fluid DB."""
    key = _SPECIES_ALIASES.get(species.lower().strip(), species.lower().strip())
    props = fluids.get(key, T=T, P=P)          # raises KeyError w/ suggestions
    if "gamma" not in props or "R_gas" not in props:
        raise ValueError(
            f"Fluid '{species}' has no ideal-gas (gamma, R_gas) data in the DB. "
            f"Choose a gas species, e.g. air, N2, O2, CO2, H2, He, CH4, Ar."
        )
    return float(props["gamma"]), float(props["R_gas"].si)


# --------------------------------------------------------------------------- #
#  Core compressible-orifice relation (registered into the Anvil registry)
# --------------------------------------------------------------------------- #
def _mass_flux(P_up, T_up, gamma, R_gas, P_down):
    """Mass flux [kg/s per m^2 of geometric hole area, Cd = 1] and choked flag.

    Pure-float core so it is fast inside the ODE right-hand side. Handles both
    the choked (sonic) and subsonic branches of the de Saint-Venant - Wantzel
    orifice equation.
    """
    r_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
    r = P_down / P_up                                  # downstream / upstream
    if r <= r_crit:                                    # --- choked (sonic) ---
        flux = P_up * math.sqrt(gamma / (R_gas * T_up)) \
            * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        choked = True
    else:                                              # --- subsonic ---
        term = r ** (2.0 / gamma) - r ** ((gamma + 1.0) / gamma)
        flux = P_up * math.sqrt(
            max(0.0, 2.0 * gamma / ((gamma - 1.0) * R_gas * T_up) * term)
        )
        choked = False
    return flux, choked, r_crit


@anvil.relation(domain="fluids.compressible", tags=["orifice", "blowdown"],
                register=False)
def orifice_mass_flow(P_up, T_up, gamma, R_gas, A_eff, P_down=101325.0, Cd=0.62):
    """Ideal-gas mass flow through N holes of total geometric area `A_eff`.

    Returns the instantaneous mdot plus the choked flag and the critical
    pressure ratio -- usable directly (anvil.R.orifice_mass_flow(...)), inside a
    System, or in a parametric sweep.
    """
    flux, choked, r_crit = _mass_flux(P_up, T_up, gamma, R_gas, P_down)
    return {
        "mdot":   Q(Cd * A_eff * flux, "kg/s"),
        "choked": 1.0 if choked else 0.0,
        "r_crit": r_crit,
    }


# --------------------------------------------------------------------------- #
#  Blowdown solver
# --------------------------------------------------------------------------- #
class BlowdownResult:
    """Container for a solved blowdown (time histories + key scalars)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def summary(self):
        P_bar = lambda p: p / 1e5
        print("=" * 66)
        print(f"  Tank blowdown -- {self.species}  ({self.model})")
        print("=" * 66)
        print(f"  Tank volume            V      = {self.V:.4g} m^3")
        print(f"  Hole diameter          d      = {self.d*1e3:.4g} mm")
        print(f"  Number of holes        N      = {self.N}")
        print(f"  Total hole area        A_eff  = {self.A_eff*1e6:.4g} mm^2")
        print(f"  Discharge coefficient  Cd     = {self.Cd}")
        print(f"  Initial pressure       P0     = {P_bar(self.P0):.4g} bar "
              f"({self.P0:.4g} Pa)")
        print(f"  Temperature            T      = {self.T0:.4g} K")
        print(f"  Ambient pressure       P_amb  = {P_bar(self.P_amb):.4g} bar")
        print(f"  gamma / R_gas                 = {self.gamma:.4g} / "
              f"{self.R_gas:.4g} J/kg/K")
        print(f"  Initial gas mass       m0     = {self.m0*1e3:.4g} g")
        print("-" * 66)
        print(f"  Critical pressure ratio r_crit = {self.r_crit:.4f}")
        print(f"  Choking threshold      P*      = {P_bar(self.P_unchoke):.4g} bar")
        started = "choked" if self.P0 > self.P_unchoke else "SUBSONIC (never choked)"
        print(f"  Flow starts             : {started}")
        print(f"  Characteristic time    tau     = {self.tau:.4g} s")
        if self.model == "isothermal" and self.P0 > self.P_unchoke:
            print(f"  >>> HALF-LIFE  t_half (choked) = {self.t_half:.4g} s "
                  f"(CONSTANT while choked)")
            print(f"      Clean half-lives before unchoke = {self.n_half_choked:.2f}")
            print(f"      Time to unchoke  (P -> P*)      = {self.t_unchoke:.4g} s")
        elif self.model == "adiabatic" and self.P0 > self.P_unchoke:
            print(f"  >>> FIRST HALF-LIFE (P0->P0/2) = {self.t_half:.4g} s "
                  f"(analytic, choked)")
            print(f"      NOTE: adiabatic decay is power-law, so each successive")
            print(f"            halving takes LONGER (half-life is not constant).")
            print(f"      Time to unchoke  (P -> P*)      = {self.t_unchoke:.4g} s")
        else:
            print(f"  >>> First pressure HALF-LIFE   = {self.t_half:.4g} s "
                  f"(numeric, {self.model})")
            if self.t_unchoke is not None:
                print(f"      Time to unchoke  (P -> P*)      = "
                      f"{self.t_unchoke:.4g} s")
        print(f"  Time to 90% drained (P->P_amb) = {self.t_90:.4g} s")
        print(f"  Time to 99% drained            = {self.t_99:.4g} s")
        print("=" * 66)


def solve_blowdown(V, d, N, P0, T, species="air", Cd=0.62, P_amb=101325.0,
                   model="adiabatic", n_points=600, verbose=False):
    """Integrate the tank blowdown and return a BlowdownResult.

    Parameters
    ----------
    V : float     tank volume [m^3]
    d : float     hole diameter [m]
    N : int       number of holes
    P0 : float    initial (full) tank pressure [Pa, absolute]
    T : float     tank temperature [K]
    species : str gas name (air, N2, O2, CO2, H2, He, CH4, Ar, ...)
    Cd : float    orifice discharge coefficient (0.62 sharp hole, ~0.9 rounded)
    P_amb : float ambient/back pressure [Pa]
    model : str   "isothermal" (constant T, analytic half-life) or "adiabatic"
    """
    gamma, R_gas = gas_properties(species, T, P0)
    A_eff = N * math.pi * 0.25 * d ** 2                 # total geometric hole area
    rho0 = P0 / (R_gas * T)
    m0 = rho0 * V
    r_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
    P_unchoke = P_amb / r_crit                          # tank P at which flow unchokes

    # ---- instantaneous tank state as a function of remaining mass m --------
    def state(m):
        rho = m / V
        if model == "adiabatic":
            P = P0 * (rho / rho0) ** gamma
            T_now = T * (rho / rho0) ** (gamma - 1.0)
        else:                                           # isothermal
            T_now = T
            P = rho * R_gas * T_now
        return P, T_now

    # ---- ODE right-hand side:  dm/dt = -mdot -------------------------------
    def rhs(t, y):
        m = max(y[0], 0.0)
        P, T_now = state(m)
        if P <= P_amb:
            return [0.0]
        flux, _, _ = _mass_flux(P, T_now, gamma, R_gas, P_amb)
        return [-Cd * A_eff * flux]

    # ---- analytic choked time scale / half-life ----------------------------
    #   Choked mdot = k*P,  k = Cd*A*sqrt(gamma/(R*T))*(2/(g+1))**((g+1)/(2(g-1)))
    #   The characteristic time  tau = V/(k*R*T)  governs BOTH closures:
    #     isothermal:  P/P0 = exp(-t/tau)                         (const half-life)
    #     adiabatic :  P/P0 = [1 + ((g-1)/2)(t/tau)]**(-2g/(g-1)) (power-law decay)
    k = Cd * A_eff * math.sqrt(gamma / (R_gas * T)) \
        * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
    tau = V / (k * R_gas * T)

    def _t_choked(P_target):
        """Analytic time (from full tank) to reach P_target *while choked*."""
        if model == "adiabatic":
            return tau * (2.0 / (gamma - 1.0)) \
                * ((P_target / P0) ** (-(gamma - 1.0) / (2.0 * gamma)) - 1.0)
        return tau * math.log(P0 / P_target)            # isothermal (exponential)

    if P0 > P_unchoke:
        t_unchoke_an = _t_choked(P_unchoke)
        n_half_choked = math.log2(P0 / P_unchoke)       # only "constant" if isothermal
    else:
        t_unchoke_an = None
        n_half_choked = 0.0
    # First pressure half-life: analytic if 0.5*P0 is still choked, else numeric later
    half_still_choked = (0.5 * P0) >= P_unchoke
    t_half_an = _t_choked(0.5 * P0) if half_still_choked else None

    # ---- integration horizon & terminal event -----------------------------
    # Drain is asymptotic to P_amb; stop at 99.9% drained (or a time cap).
    P_stop = P_amb + 0.001 * (P0 - P_amb)
    m_stop, _ = _mass_for_pressure(P_stop, model, V, rho0, P0, R_gas, T, gamma)
    t_cap = 40.0 * tau + 1.0

    def ev_drained(t, y):
        return y[0] - m_stop
    ev_drained.terminal = True
    ev_drained.direction = -1

    sol = anvil.solvers.solve_ode(
        rhs, (0.0, t_cap), [m0],
        method="RK45", rtol=1e-9, atol=1e-12,
        max_step=t_cap / 200.0, events=ev_drained, verbose=verbose,
    )
    t_end = float(sol["t"][-1])
    dense = sol["sol"].sol                               # scipy dense output y(t)

    # ---- sample fine time histories ----------------------------------------
    t = np.linspace(0.0, t_end, n_points)
    m_t = np.clip(dense(t)[0], 0.0, None)
    P_t = np.empty_like(t)
    T_t = np.empty_like(t)
    mdot_t = np.empty_like(t)
    choked_t = np.zeros_like(t)
    for i, m in enumerate(m_t):
        P, Tn = state(m)
        P_t[i], T_t[i] = P, Tn
        flux, ch, _ = _mass_flux(max(P, P_amb), Tn, gamma, R_gas, P_amb)
        mdot_t[i] = Cd * A_eff * flux if P > P_amb else 0.0
        choked_t[i] = 1.0 if (ch and P > P_amb) else 0.0

    # ---- numeric scalars: half-life, unchoke, 90/99% drained ---------------
    def _time_at_pressure(P_target):
        if P_target >= P0:
            return 0.0
        if P_target <= P_t[-1]:
            return t_end
        return float(np.interp(-P_target, -P_t, t))     # P_t is monotone decreasing

    t_half = t_half_an if t_half_an is not None else _time_at_pressure(0.5 * P0)
    t_unchoke = t_unchoke_an if t_unchoke_an is not None else (
        _time_at_pressure(P_unchoke) if P0 > P_unchoke else None)
    t_90 = _time_at_pressure(P_amb + 0.10 * (P0 - P_amb))
    t_99 = _time_at_pressure(P_amb + 0.01 * (P0 - P_amb))

    return BlowdownResult(
        species=species, model=model,
        V=V, d=d, N=N, A_eff=A_eff, Cd=Cd, P0=P0, T0=T, P_amb=P_amb,
        gamma=gamma, R_gas=R_gas, rho0=rho0, m0=m0,
        r_crit=r_crit, P_unchoke=P_unchoke,
        tau=tau, t_half=t_half,
        n_half_choked=n_half_choked,
        t_unchoke=t_unchoke,
        t_90=t_90, t_99=t_99,
        t=t, P=P_t, T=T_t, mdot=mdot_t, m=m_t, choked=choked_t,
        _sol=sol,
    )


def _mass_for_pressure(P_target, model, V, rho0, P0, R_gas, T, gamma):
    """Invert the state relation P(m) -> m (remaining gas mass at pressure P)."""
    if model == "adiabatic":
        rho = rho0 * (P_target / P0) ** (1.0 / gamma)
    else:
        rho = P_target / (R_gas * T)
    return rho * V, rho


# --------------------------------------------------------------------------- #
#  Plotting
# --------------------------------------------------------------------------- #
def plot_blowdown(res, save=None, show=True):
    import matplotlib.pyplot as plt

    adiabatic = res.model == "adiabatic"
    nrows = 3 if adiabatic else 2
    fig, axes = plt.subplots(nrows, 1, figsize=(9, 4 * nrows), sharex=True)
    axP, axM = axes[0], axes[1]

    # shade the choked window
    choked = res.choked > 0.5
    if choked.any():
        t_unchoke = res.t[choked][-1]
        for ax in axes:
            ax.axvspan(res.t[0], t_unchoke, color="tab:orange", alpha=0.10,
                       label="choked (sonic)")

    # --- pressure ---
    axP.plot(res.t, res.P / 1e5, color="tab:blue", lw=2)
    axP.axhline(res.P_unchoke / 1e5, ls="--", color="tab:orange", lw=1.2,
                label=f"unchoke P* = {res.P_unchoke/1e5:.2f} bar")
    axP.axhline(res.P_amb / 1e5, ls=":", color="grey", lw=1.2, label="P_amb")
    # half-life markers
    if res.t_half is not None and res.t_half < res.t[-1]:
        axP.axvline(res.t_half, ls="-.", color="tab:red", lw=1.2,
                    label=f"t_half = {res.t_half:.3g} s")
        axP.plot([res.t_half], [0.5 * res.P0 / 1e5], "o", color="tab:red")
    axP.set_ylabel("Tank pressure  [bar]")
    axP.set_title(f"Pressure-tank blowdown -- {res.species} ({res.model})")
    axP.grid(alpha=0.3)
    axP.legend(fontsize=8, loc="upper right")

    # --- mass flow ---
    axM.plot(res.t, res.mdot * 1e3, color="tab:green", lw=2)
    axM.set_ylabel("Mass-flow rate  [g/s]")
    axM.grid(alpha=0.3)
    if choked.any():
        axM.axvline(t_unchoke, ls="--", color="tab:orange", lw=1.0)
        axM.annotate("choked -> subsonic", xy=(t_unchoke, res.mdot.max() * 1e3 * 0.6),
                     xytext=(8, 0), textcoords="offset points", fontsize=8,
                     color="tab:orange", rotation=90, va="center")

    # --- temperature (adiabatic only: gas cools as it expands) ---
    if adiabatic:
        axT = axes[2]
        axT.plot(res.t, res.T, color="tab:purple", lw=2)
        axT.axhline(res.T0, ls=":", color="grey", lw=1.0,
                    label=f"T0 = {res.T0:.0f} K")
        axT.set_ylabel("Tank gas temperature  [K]")
        axT.grid(alpha=0.3)
        axT.legend(fontsize=8, loc="lower right")
        axT.set_xlabel("time  [s]")
    else:
        axM.set_xlabel("time  [s]")

    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  saved plot -> {save}")
    if show:
        plt.show()
    return fig


# --------------------------------------------------------------------------- #
#  Bonus: half-life as a function of design, via an Anvil System + sweep
# --------------------------------------------------------------------------- #
def halflife_vs_diameter(V, N, P0, T, species="air", Cd=0.62, P_amb=101325.0,
                         d_range=(0.5e-3, 5e-3), n=25, save=None, show=True):
    """Sweep hole diameter and plot the (choked, isothermal) half-life.

    Demonstrates wrapping the closed-form result in an Anvil System so it can be
    swept / optimized like any other Anvil model.
    """
    gamma, R_gas = gas_properties(species, T, P0)

    def choked_halflife(V, d, N, gamma, R_gas, T, Cd):
        A = N * math.pi * 0.25 * d ** 2
        k = Cd * A * math.sqrt(gamma / (R_gas * T)) \
            * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        tau = V / (k * R_gas * T)
        return {"tau": Q(tau, "s"), "t_half": Q(tau * math.log(2.0), "s")}

    sys = anvil.system("tank_halflife")
    sys.add("V", V, "m^3")
    sys.add("d", d_range[0], "m")
    sys.add("N", N)
    sys.add("gamma", gamma)
    sys.add("R_gas", R_gas, "J/kg/K")
    sys.add("T", T, "K")
    sys.add("Cd", Cd)
    sys.use(choked_halflife)

    sweep = sys.sweep("d", np.linspace(d_range[0], d_range[1], n))
    fig = anvil.viz.sweep_plot(sweep, y=["t_half"], x_label="hole diameter d [m]",
                               show=False)
    if save:
        fig.savefig(save, dpi=150, bbox_inches="tight")
        print(f"  saved plot -> {save}")
    if show:
        import matplotlib.pyplot as plt
        plt.show()
    return sweep


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def _build_parser():
    p = argparse.ArgumentParser(
        description="Pressure-tank gas blowdown / half-life (Anvil).")
    p.add_argument("--V", type=float, default=0.05, help="tank volume [m^3]")
    p.add_argument("--d", type=float, default=2e-3, help="hole diameter [m]")
    p.add_argument("--N", type=int, default=1, help="number of holes")
    p.add_argument("--P0", type=float, default=10e6,
                   help="initial tank pressure [Pa, absolute]")
    p.add_argument("--T", type=float, default=300.0, help="temperature [K]")
    p.add_argument("--species", type=str, default="air",
                   help="gas: air, N2, O2, CO2, H2, He, CH4, Ar, propane")
    p.add_argument("--Cd", type=float, default=0.62,
                   help="discharge coeff (0.62 sharp hole, ~0.9 rounded)")
    p.add_argument("--P_amb", type=float, default=101325.0,
                   help="ambient pressure [Pa]")
    p.add_argument("--model", choices=["isothermal", "adiabatic"],
                   default="adiabatic")
    p.add_argument("--save", type=str, default=None,
                   help="path to save the time-history PNG")
    p.add_argument("--sweep", action="store_true",
                   help="also plot half-life vs hole diameter")
    p.add_argument("--no-show", action="store_true", help="do not display plots")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    res = solve_blowdown(
        V=args.V, d=args.d, N=args.N, P0=args.P0, T=args.T,
        species=args.species, Cd=args.Cd, P_amb=args.P_amb, model=args.model,
    )
    res.summary()
    try:
        plot_blowdown(res, save=args.save, show=not args.no_show)
        if args.sweep:
            halflife_vs_diameter(args.V, args.N, args.P0, args.T,
                                 species=args.species, Cd=args.Cd,
                                 P_amb=args.P_amb, show=not args.no_show)
    except ImportError:
        print("  (matplotlib not installed -- skipping plots; "
              "pip install matplotlib)")
    return res


if __name__ == "__main__":
    main()
```

> Runs a full solve that takes a while; run the script locally to see its output.
