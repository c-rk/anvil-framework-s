# Gas-Turbine Cycle Analysis

Anvil ships a GasTurb-style engine cycle pack: air-breathing engines built
station by station from small native Relations, wired into a solvable System
you can sweep and optimize like any other Anvil problem.

```python
from anvil import propulsion as jet

tj = jet.build_turbojet()
tj.set(M0=0.85, pi_c=12, T04=1500, mdot=25)
res = tj.solve()
res.summary()

print(jet.station_table(res))     # per-station stagnation T0, P0
fig = jet.cycle_diagram(res)      # T-s diagram (needs matplotlib)
```

## Station numbering

Each component maps the stagnation state at its inlet station to the state at
its exit station, so the System chains them automatically by variable name.
Station numbers follow the usual aero convention:

| Station | Location |
|:-------:|:---------|
| 0  | freestream / ambient |
| 2  | compressor (or fan) face, after the intake |
| 13 | fan / bypass duct exit (turbofan) |
| 3  | compressor exit = combustor inlet |
| 4  | combustor exit = turbine inlet (turbine inlet temperature, TIT) |
| 45 | HP-turbine exit = LP-turbine inlet (two-spool) |
| 5  | turbine exit = nozzle (or afterburner) inlet |
| 7  | afterburner exit |
| 9  | core nozzle exit |
| 19 | bypass nozzle exit (turbofan) |

## Engines

Four ready-to-solve builders, each returning a `System`:

```python
jet.build_turbojet()      # single spool: intake, compressor, combustor, turbine, nozzle
jet.build_turbofan()      # two-spool, separate exhaust, fan + bypass duct
jet.build_turbojet_ab()   # turbojet with an afterburner (reheat)
jet.build_turboprop()     # free power turbine driving a propeller / shaft
```

Override the design point with `.set(...)`. Common design inputs: `M0` (flight
Mach), `pi_c` (compressor pressure ratio), `pi_f` (fan pressure ratio),
`bypass` (bypass ratio), `T04` (turbine inlet temperature), `T07` (afterburner
temperature), `mdot` (core mass flow).

## Outputs

A solved cycle reports specific thrust, absolute thrust, TSFC, fuel-air ratio,
exit Mach, and the thermal, propulsive and overall efficiencies. A turboprop
reports shaft power, specific power and PSFC instead.

```python
res.summary(keys=["specific_thrust", "TSFC", "thermal_eff",
                  "propulsive_eff", "overall_eff"])
```

`station_table(res)` prints the stagnation temperature and pressure at every
station present in the result. `cycle_diagram(res, kind="Ts")` draws the
temperature-entropy cycle; `kind="hs"` draws the enthalpy-entropy (Mollier)
form. Both mark each station and return a Matplotlib figure.

## Sweeps and optimization

Because an engine is a normal `System`, the usual analysis tools apply:

```python
# how compressor pressure ratio trades specific thrust against TSFC
sweep = tj.sweep("pi_c", [6, 10, 15, 20, 25, 30, 40])
sweep.summary(outputs=["specific_thrust", "TSFC", "thermal_eff"])

# pressure ratio that maximizes specific thrust
best = tj.optimize("specific_thrust", {"pi_c": (4, 45)}, minimize=False)
print(best.x["pi_c"], best.fun)
```

Higher pressure ratio lowers TSFC (better fuel economy) while specific thrust
peaks at a moderate pressure ratio, the classic turbojet trade.

## Gas model

The default is a constant-cp, cold/hot split: cold cp and gamma for the
intake, fan and compressor, hot cp and gamma for the combustor, turbine,
afterburner and nozzle. This is the textbook / GasTurb-"simple" model and needs
no external tools. A variable-cp path is available through
`propulsion.gas_properties`, which accepts a thermo adapter (for example one
backed by CoolProp or Cantera) and returns temperature-dependent cp, gamma
and R that you can pass to the components.

## Component RSQs

Every stage is a registered RSQ you can search, inspect and reuse on its own or
inside your own System: `ram_intake`, `compressor`, `combustor`, `turbine`,
`nozzle`, `thrust_performance` (turbojet); `fan`, `hp_compressor`,
`hp_turbine`, `lp_turbine`, `bypass_nozzle`, `turbofan_thrust` (turbofan);
`afterburner`; and `power_turbine`, `turboshaft_performance` (turboprop). The
full engines are the `turbojet_cycle`, `turbofan_cycle`, `turbojet_ab_cycle`
and `turboprop_cycle` systems.

See the [Examples](22_examples.md) page for a complete, runnable walkthrough.
