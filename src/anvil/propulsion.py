"""
Gas-turbine cycle analysis -- station-by-station, GasTurb style.

This module builds air-breathing engine cycles out of small, native Anvil
Relations (one per component) wired into a solvable System. Each component
takes the stagnation state at its inlet station and returns the stagnation
state at its exit station, so the System chains them automatically by
variable name. Station numbers follow the usual aero convention:

    0    freestream / ambient
    2    compressor (or fan) face, after the intake
    13   fan / bypass duct exit          (turbofan)
    3    compressor exit  = combustor inlet
    4    combustor exit   = turbine inlet   (turbine inlet temperature, TIT)
    45   HP-turbine exit  = LP-turbine inlet (two-spool)
    5    turbine exit     = nozzle (or afterburner) inlet
    7    afterburner exit
    9    core nozzle exit
    19   bypass nozzle exit               (turbofan)

Gas model
---------
The default is a constant-cp, cold/hot split: a "cold" cp and gamma for the
intake, fan and compressor, and a "hot" cp and gamma for the combustor,
turbine, afterburner and nozzle. This is the textbook / GasTurb-"simple"
model and needs no external tools. A variable-cp path (temperature dependent,
via a thermo adapter) is available through ``gas_properties`` when an adapter
is installed; the builders accept the resulting cp/gamma values directly.

Everything here is plain SI. Component functions accept floats or Anvil
Quantities interchangeably (inputs are coerced with ``float``, so a value
that arrives as a Quantity contributes its SI magnitude) and return
Quantities so units show up in results and station tables.

Typical use
-----------
    import anvil
    from anvil import propulsion as jet

    tj = jet.build_turbojet()
    tj.set(pi_c=12, T04=1500, M0=0.85)
    res = tj.solve()
    res.summary()

    print(jet.station_table(res))          # per-station T0/P0
    fig = jet.cycle_diagram(res)           # T-s diagram (needs matplotlib)

    # sweep and optimize like any other System
    sw = tj.sweep("pi_c", range(4, 40, 2))
    opt = tj.optimize("specific_thrust", {"pi_c": (4, 40)}, minimize=False)
"""
from __future__ import annotations

import math

from anvil import Q, System

# --------------------------------------------------------------------------- #
# Default gas properties (constant-cp, cold/hot split)
# --------------------------------------------------------------------------- #
# "Cold" section: air through intake, fan and compressor.
CP_COLD = 1004.5      # J/(kg*K)
GAMMA_COLD = 1.40
R_COLD = 287.05       # J/(kg*K)
# "Hot" section: combustion products through turbine, afterburner and nozzle.
CP_HOT = 1148.0       # J/(kg*K)
GAMMA_HOT = 1.333
R_HOT = 287.05        # J/(kg*K)
# Fuel and constants.
LHV_JETA = 43.0e6     # J/kg, lower heating value of Jet-A / kerosene
G0 = 9.80665          # m/s^2


def gas_properties(T, fluid="air", fuel_air=0.0, adapter=None):
    """Temperature-dependent cp and gamma for the variable-cp path.

    By default this returns the constant cold-air values; pass a callable
    ``adapter(T, fluid, fuel_air) -> (cp, gamma, R)`` (for example one backed
    by CoolProp or Cantera) to get real temperature-dependent properties.
    Builders take cp/gamma directly, so you can call this to fill them in.
    """
    T = float(T)
    if adapter is not None:
        cp, gamma, R = adapter(T, fluid, fuel_air)
        return {"cp": float(cp), "gamma": float(gamma), "R": float(R)}
    # Fall back to the constant split: hot if clearly combustion gas.
    if fuel_air > 0.0 or T > 1000.0:
        return {"cp": CP_HOT, "gamma": GAMMA_HOT, "R": R_HOT}
    return {"cp": CP_COLD, "gamma": GAMMA_COLD, "R": R_COLD}


# --------------------------------------------------------------------------- #
# Component relations
#
# Each is a pure function: inlet stagnation state + component parameters ->
# exit stagnation state. Specific work terms (w_*) are per unit mass of the
# flow through that component, in J/kg. Registered as native RSQs in seed.py.
# --------------------------------------------------------------------------- #

def ram_intake(T_amb, P_amb, M0, gamma_c=GAMMA_COLD, R_c=R_COLD, eta_d=0.98):
    """Freestream to compressor face (station 0 -> 2) through the intake.

    Returns the stagnation state after ram compression, using a diffuser
    (ram) efficiency ``eta_d`` on the pressure recovery, plus the flight
    speed V0 and ambient speed of sound a0.
    """
    T_amb = float(T_amb); P_amb = float(P_amb); M0 = float(M0)
    gamma_c = float(gamma_c); R_c = float(R_c); eta_d = float(eta_d)
    a0 = math.sqrt(gamma_c * R_c * T_amb)
    V0 = M0 * a0
    T02 = T_amb * (1.0 + 0.5 * (gamma_c - 1.0) * M0 ** 2)
    # Ram-efficiency form: recovered total pressure from the (efficient) rise.
    P02 = P_amb * (1.0 + eta_d * 0.5 * (gamma_c - 1.0) * M0 ** 2) ** (
        gamma_c / (gamma_c - 1.0))
    return {"T02": Q(T02, "K"), "P02": Q(P02, "Pa"),
            "a0": Q(a0, "m/s"), "V0": Q(V0, "m/s")}


def compressor(T02, P02, pi_c, eta_c=0.87, gamma_c=GAMMA_COLD, cp_c=CP_COLD):
    """Compressor (station 2 -> 3) with isentropic efficiency ``eta_c``.

    ``pi_c`` is the total pressure ratio. Returns exit stagnation state and
    the specific compressor work w_c (J/kg of core air).
    """
    T02 = float(T02); P02 = float(P02); pi_c = float(pi_c)
    eta_c = float(eta_c); gamma_c = float(gamma_c); cp_c = float(cp_c)
    tau_ci = pi_c ** ((gamma_c - 1.0) / gamma_c)      # ideal temperature ratio
    T03 = T02 * (1.0 + (tau_ci - 1.0) / eta_c)
    P03 = P02 * pi_c
    w_c = cp_c * (T03 - T02)
    return {"T03": Q(T03, "K"), "P03": Q(P03, "Pa"), "w_c": Q(w_c, "J/kg")}


def combustor(T03, P03, T04, cp_c=CP_COLD, cp_h=CP_HOT,
              LHV=LHV_JETA, eta_b=0.99, pi_b=0.96):
    """Combustor (station 3 -> 4) at prescribed turbine inlet temperature T04.

    Energy balance gives the fuel-air ratio ``far`` needed to reach T04.
    ``pi_b`` is the combustor total-pressure ratio (pressure loss), ``eta_b``
    the combustion efficiency, ``LHV`` the fuel lower heating value.
    """
    T03 = float(T03); P03 = float(P03); T04 = float(T04)
    cp_c = float(cp_c); cp_h = float(cp_h)
    LHV = float(LHV); eta_b = float(eta_b); pi_b = float(pi_b)
    P04 = P03 * pi_b
    far = (cp_h * T04 - cp_c * T03) / (eta_b * LHV - cp_h * T04)
    q_add = cp_h * T04 - cp_c * T03
    return {"P04": Q(P04, "Pa"), "far": far, "q_add": Q(q_add, "J/kg")}


def turbine(T04, P04, w_c, far, eta_t=0.89, eta_m=0.99,
            gamma_h=GAMMA_HOT, cp_h=CP_HOT, w_ext=0.0):
    """Turbine (station 4 -> 5) sized to drive the compressor (work balance).

    The turbine specific work equals the compressor work (plus any external
    shaft work ``w_ext``) divided by the mechanical efficiency and the
    (1+far) mass-flow increase from fuel addition. ``eta_t`` is the turbine
    isentropic efficiency.
    """
    T04 = float(T04); P04 = float(P04); w_c = float(w_c); far = float(far)
    eta_t = float(eta_t); eta_m = float(eta_m)
    gamma_h = float(gamma_h); cp_h = float(cp_h); w_ext = float(w_ext)
    w_t = (w_c + w_ext) / (eta_m * (1.0 + far))
    T05 = T04 - w_t / cp_h
    # Invert the isentropic efficiency to get the total pressure ratio.
    T05s = T04 - (T04 - T05) / eta_t
    P05 = P04 * (T05s / T04) ** (gamma_h / (gamma_h - 1.0))
    return {"T05": Q(T05, "K"), "P05": Q(P05, "Pa"), "w_t": Q(w_t, "J/kg")}


def nozzle(T05, P05, P_amb, gamma_h=GAMMA_HOT, R_h=R_HOT, eta_n=0.98):
    """Convergent nozzle (station 5 -> 9). Detects choking automatically.

    If the nozzle pressure ratio exceeds critical, the exit is choked (M9=1)
    and stays at the critical pressure; otherwise the flow is perfectly
    expanded to ambient. Returns exit velocity, state and Mach number.
    """
    T05 = float(T05); P05 = float(P05); P_amb = float(P_amb)
    gamma_h = float(gamma_h); R_h = float(R_h); eta_n = float(eta_n)
    g = gamma_h
    cp_h = g * R_h / (g - 1.0)
    npr = P05 / P_amb
    npr_crit = ((g + 1.0) / 2.0) ** (g / (g - 1.0))
    if npr > npr_crit:                     # choked
        M9 = 1.0
        T9 = T05 * 2.0 / (g + 1.0)
        P9 = P05 / npr_crit
        V9 = math.sqrt(g * R_h * T9)
        choked = True
    else:                                  # perfectly expanded to ambient
        P9 = P_amb
        T9_ideal = T05 * (P_amb / P05) ** ((g - 1.0) / g)
        # nozzle efficiency on the enthalpy drop
        V9 = math.sqrt(2.0 * eta_n * cp_h * (T05 - T9_ideal))
        T9 = T05 - eta_n * (T05 - T9_ideal)
        M9 = V9 / math.sqrt(g * R_h * T9)
        choked = False
    return {"V9": Q(V9, "m/s"), "T9": Q(T9, "K"), "P9": Q(P9, "Pa"),
            "M9": M9, "choked": choked}


def thrust_performance(V0, V9, T9, P9, P_amb, far, mdot=1.0,
                       R_h=R_HOT, LHV=LHV_JETA):
    """Core-stream thrust and efficiencies from the nozzle exit state.

    Specific thrust is per unit core mass flow (N per kg/s); ``mdot`` scales
    it to an absolute thrust. The pressure-thrust term is written through the
    exit density so no exit area is needed. Efficiencies follow the standard
    thermal / propulsive / overall definitions.
    """
    V0 = float(V0); V9 = float(V9); T9 = float(T9); P9 = float(P9)
    P_amb = float(P_amb); far = float(far); mdot = float(mdot)
    R_h = float(R_h); LHV = float(LHV)
    # A9/mdot9 = R*T9/(P9*V9); pressure thrust = mdot9*(A9/mdot9)*(P9-P_amb).
    press_term = (1.0 + far) * (R_h * T9 / V9) * (1.0 - P_amb / P9)
    F_s = (1.0 + far) * V9 - V0 + press_term          # N per (kg/s) core air
    thrust = F_s * mdot
    tsfc = far / F_s if F_s > 0 else float("inf")      # kg/(N*s)
    # Bounded efficiencies (Hill & Peterson form):
    #   thrust power / (thrust power + residual kinetic energy left in the jet).
    thrust_power = F_s * V0                            # W per (kg/s) core air
    residual_ke = 0.5 * (1.0 + far) * (V9 - V0) ** 2   # J/kg wasted in exhaust
    q_in = far * LHV
    eta_prop = (thrust_power / (thrust_power + residual_ke)
                if thrust_power + residual_ke > 0 else 0.0)
    eta_th = ((thrust_power + residual_ke) / q_in) if q_in > 0 else 0.0
    eta_overall = eta_th * eta_prop
    isp = F_s / (far * G0) if far > 0 else float("inf")
    return {"specific_thrust": Q(F_s, "N"), "thrust": Q(thrust, "N"),
            "TSFC": tsfc, "thermal_eff": eta_th, "propulsive_eff": eta_prop,
            "overall_eff": eta_overall, "Isp_air": Q(isp, "s")}


# --------------------------------------------------------------------------- #
# Turbofan-specific components (two-spool, separate exhaust)
# --------------------------------------------------------------------------- #

def fan(T02, P02, pi_f, eta_f=0.90, gamma_c=GAMMA_COLD, cp_c=CP_COLD):
    """Fan (station 2 -> 13), pressures the full mass flow (core + bypass).

    ``pi_f`` is the fan total pressure ratio. w_f is per unit mass flow
    through the fan (i.e. per unit of (core + bypass) air).
    """
    T02 = float(T02); P02 = float(P02); pi_f = float(pi_f)
    eta_f = float(eta_f); gamma_c = float(gamma_c); cp_c = float(cp_c)
    tau_fi = pi_f ** ((gamma_c - 1.0) / gamma_c)
    T13 = T02 * (1.0 + (tau_fi - 1.0) / eta_f)
    P13 = P02 * pi_f
    w_f = cp_c * (T13 - T02)
    return {"T13": Q(T13, "K"), "P13": Q(P13, "Pa"), "w_f": Q(w_f, "J/kg")}


def hp_compressor(T13, P13, pi_c, eta_c=0.88, gamma_c=GAMMA_COLD, cp_c=CP_COLD):
    """HP compressor (station 13 -> 3), core flow only. See ``compressor``."""
    T13 = float(T13); P13 = float(P13); pi_c = float(pi_c)
    eta_c = float(eta_c); gamma_c = float(gamma_c); cp_c = float(cp_c)
    tau_ci = pi_c ** ((gamma_c - 1.0) / gamma_c)
    T03 = T13 * (1.0 + (tau_ci - 1.0) / eta_c)
    P03 = P13 * pi_c
    w_c = cp_c * (T03 - T13)
    return {"T03": Q(T03, "K"), "P03": Q(P03, "Pa"), "w_c": Q(w_c, "J/kg")}


def hp_turbine(T04, P04, w_c, far, eta_t=0.89, eta_m=0.99,
               gamma_h=GAMMA_HOT, cp_h=CP_HOT):
    """HP turbine (station 4 -> 45), drives the HP compressor only."""
    T04 = float(T04); P04 = float(P04); w_c = float(w_c); far = float(far)
    eta_t = float(eta_t); eta_m = float(eta_m)
    gamma_h = float(gamma_h); cp_h = float(cp_h)
    w_hpt = w_c / (eta_m * (1.0 + far))
    T45 = T04 - w_hpt / cp_h
    T45s = T04 - (T04 - T45) / eta_t
    P45 = P04 * (T45s / T04) ** (gamma_h / (gamma_h - 1.0))
    return {"T45": Q(T45, "K"), "P45": Q(P45, "Pa"), "w_hpt": Q(w_hpt, "J/kg")}


def lp_turbine(T45, P45, w_f, far, bypass, eta_t=0.90, eta_m=0.99,
               gamma_h=GAMMA_HOT, cp_h=CP_HOT):
    """LP turbine (station 45 -> 5), drives the fan.

    The fan pumps (1+bypass) units of air per unit core, so per unit core
    mass the LP turbine must supply (1+bypass)*w_f of shaft work.
    """
    T45 = float(T45); P45 = float(P45); w_f = float(w_f); far = float(far)
    bypass = float(bypass); eta_t = float(eta_t); eta_m = float(eta_m)
    gamma_h = float(gamma_h); cp_h = float(cp_h)
    w_lpt = (1.0 + bypass) * w_f / (eta_m * (1.0 + far))
    T05 = T45 - w_lpt / cp_h
    T05s = T45 - (T45 - T05) / eta_t
    P05 = P45 * (T05s / T45) ** (gamma_h / (gamma_h - 1.0))
    return {"T05": Q(T05, "K"), "P05": Q(P05, "Pa"), "w_lpt": Q(w_lpt, "J/kg")}


def bypass_nozzle(T13, P13, P_amb, gamma_c=GAMMA_COLD, R_c=R_COLD, eta_n=0.98):
    """Cold bypass nozzle (station 13 -> 19). Same logic as ``nozzle``."""
    out = nozzle(T13, P13, P_amb, gamma_h=gamma_c, R_h=R_c, eta_n=eta_n)
    return {"V19": out["V9"], "T19": out["T9"], "P19": out["P9"],
            "M19": out["M9"], "choked_bypass": out["choked"]}


def turbofan_thrust(V0, V9, T9, P9, V19, T19, P19, P_amb, far, bypass,
                    mdot_core=1.0, R_h=R_HOT, R_c=R_COLD, LHV=LHV_JETA):
    """Combined core + bypass thrust and efficiencies for a turbofan.

    Specific thrust is per unit *core* mass flow; the bypass contributes
    ``bypass`` units of cold air per unit core. ``mdot_core`` scales to an
    absolute thrust.
    """
    V0 = float(V0); V9 = float(V9); T9 = float(T9); P9 = float(P9)
    V19 = float(V19); T19 = float(T19); P19 = float(P19)
    P_amb = float(P_amb); far = float(far); bypass = float(bypass)
    mdot_core = float(mdot_core); R_h = float(R_h); R_c = float(R_c)
    LHV = float(LHV)
    core_press = (1.0 + far) * (R_h * T9 / V9) * (1.0 - P_amb / P9)
    Fs_core = (1.0 + far) * V9 - V0 + core_press
    byp_press = bypass * (R_c * T19 / V19) * (1.0 - P_amb / P19)
    Fs_byp = bypass * (V19 - V0) + byp_press
    F_s = Fs_core + Fs_byp                  # N per (kg/s) core air
    thrust = F_s * mdot_core
    tsfc = far / F_s if F_s > 0 else float("inf")
    # Bounded efficiencies: thrust power over thrust power + residual jet KE,
    # summed over the core and bypass streams.
    thrust_power = F_s * V0
    residual_ke = (0.5 * (1.0 + far) * (V9 - V0) ** 2
                   + 0.5 * bypass * (V19 - V0) ** 2)
    q_in = far * LHV
    eta_prop = (thrust_power / (thrust_power + residual_ke)
                if thrust_power + residual_ke > 0 else 0.0)
    eta_th = ((thrust_power + residual_ke) / q_in) if q_in > 0 else 0.0
    eta_overall = eta_th * eta_prop
    return {"specific_thrust": Q(F_s, "N"), "thrust": Q(thrust, "N"),
            "TSFC": tsfc, "thermal_eff": eta_th, "propulsive_eff": eta_prop,
            "overall_eff": eta_overall, "specific_thrust_core": Q(Fs_core, "N"),
            "specific_thrust_bypass": Q(Fs_byp, "N")}


# --------------------------------------------------------------------------- #
# Afterburner
# --------------------------------------------------------------------------- #

def afterburner(T05, P05, far, T07, cp_h=CP_HOT, LHV=LHV_JETA,
                eta_ab=0.95, pi_ab=0.95):
    """Afterburner (station 5 -> 7): reheat to T07, extra fuel far_ab.

    Adds fuel between turbine and nozzle to raise the temperature to T07.
    Returns the new total fuel-air ratio and the post-afterburner pressure.
    """
    T05 = float(T05); P05 = float(P05); far = float(far); T07 = float(T07)
    cp_h = float(cp_h); LHV = float(LHV)
    eta_ab = float(eta_ab); pi_ab = float(pi_ab)
    P07 = P05 * pi_ab
    far_ab = (1.0 + far) * cp_h * (T07 - T05) / (eta_ab * LHV - cp_h * T07)
    far_total = far + far_ab
    # T07 is a declared design input (the reheat target), so it is already in
    # the result; only the derived quantities are returned here.
    return {"P07": Q(P07, "Pa"), "far_ab": far_ab, "far_total": far_total}


# --------------------------------------------------------------------------- #
# Turboprop / turboshaft (free power turbine)
# --------------------------------------------------------------------------- #

def power_turbine(T45, P45, P_amb, far, eta_t=0.90, gamma_h=GAMMA_HOT,
                  cp_h=CP_HOT, eta_gearbox=0.98, frac_expand=0.95):
    """Free power turbine (station 45 -> 5) extracting shaft power.

    Expands the gas toward ambient and turns the enthalpy drop into shaft
    work. ``frac_expand`` is the fraction of the available pressure ratio
    used by the power turbine (the rest leaves as residual jet). Returns the
    specific shaft work delivered through the gearbox.
    """
    T45 = float(T45); P45 = float(P45); P_amb = float(P_amb); far = float(far)
    eta_t = float(eta_t); gamma_h = float(gamma_h); cp_h = float(cp_h)
    eta_gearbox = float(eta_gearbox); frac_expand = float(frac_expand)
    g = gamma_h
    # Target exit pressure: expand most of the way to ambient.
    P5 = P45 - frac_expand * (P45 - P_amb)
    T5s = T45 * (P5 / P45) ** ((g - 1.0) / g)
    T05 = T45 - eta_t * (T45 - T5s)
    w_shaft = (1.0 + far) * cp_h * (T45 - T05) * eta_gearbox
    return {"T05": Q(T05, "K"), "P05": Q(P5, "Pa"),
            "w_shaft": Q(w_shaft, "J/kg")}


def turboshaft_performance(w_shaft, far, mdot_core=1.0, LHV=LHV_JETA):
    """Shaft power, specific power and SFC for a turboprop / turboshaft."""
    w_shaft = float(w_shaft); far = float(far)
    mdot_core = float(mdot_core); LHV = float(LHV)
    power = w_shaft * mdot_core                       # W
    psfc = far / w_shaft if w_shaft > 0 else float("inf")   # kg/(W*s) = kg/J
    eta_th = w_shaft / (far * LHV) if far > 0 else 0.0
    return {"shaft_power": Q(power, "W"), "specific_power": Q(w_shaft, "J/kg"),
            "PSFC": psfc, "thermal_eff": eta_th}


# --------------------------------------------------------------------------- #
# Engine builders -- wire components into solvable Systems
# --------------------------------------------------------------------------- #

def build_turbojet(name="turbojet"):
    """Single-spool turbojet. Design inputs: M0, pi_c, T04, mdot, altitude gas.

    Returns a ready-to-solve System. Override design point with .set(...).
    """
    s = System(name, "Single-spool turbojet cycle")
    s.add("T_amb", 288.15, "K", desc="Ambient (static) temperature")
    s.add("P_amb", 101325.0, "Pa", desc="Ambient (static) pressure")
    s.add("M0", 0.0, desc="Flight Mach number")
    s.add("pi_c", 10.0, desc="Compressor pressure ratio")
    s.add("T04", 1400.0, "K", desc="Turbine inlet temperature (TIT)")
    s.add("mdot", 1.0, "kg/s", desc="Core mass flow")
    s.use(ram_intake)
    s.use(compressor)
    s.use(combustor)
    s.use(turbine)
    s.use(nozzle)
    s.use(thrust_performance)
    return s


def build_turbojet_ab(name="turbojet_ab"):
    """Turbojet with an afterburner (reheat) between turbine and nozzle."""
    s = System(name, "Turbojet with afterburner")
    s.add("T_amb", 288.15, "K", desc="Ambient (static) temperature")
    s.add("P_amb", 101325.0, "Pa", desc="Ambient (static) pressure")
    s.add("M0", 0.0, desc="Flight Mach number")
    s.add("pi_c", 10.0, desc="Compressor pressure ratio")
    s.add("T04", 1400.0, "K", desc="Turbine inlet temperature (TIT)")
    s.add("T07", 2000.0, "K", desc="Afterburner exit temperature")
    s.add("mdot", 1.0, "kg/s", desc="Core mass flow")
    s.use(ram_intake)
    s.use(compressor)
    s.use(combustor)
    s.use(turbine)
    s.use(afterburner)
    # Nozzle now expands from the afterburner exit (station 7).
    s.use(nozzle, map={"T05": "T07", "P05": "P07"})
    # Thrust uses the total (core + afterburner) fuel-air ratio.
    s.use(thrust_performance, map={"far": "far_total"})
    return s


def build_turbofan(name="turbofan"):
    """Two-spool, separate-exhaust turbofan. Adds fan, bypass and LP/HP spools."""
    s = System(name, "Two-spool separate-flow turbofan cycle")
    s.add("T_amb", 288.15, "K", desc="Ambient (static) temperature")
    s.add("P_amb", 101325.0, "Pa", desc="Ambient (static) pressure")
    s.add("M0", 0.0, desc="Flight Mach number")
    s.add("pi_f", 1.6, desc="Fan pressure ratio")
    s.add("pi_c", 20.0, desc="HP compressor pressure ratio")
    s.add("bypass", 5.0, desc="Bypass ratio")
    s.add("T04", 1500.0, "K", desc="Turbine inlet temperature (TIT)")
    s.add("mdot", 1.0, "kg/s", desc="Core mass flow")
    s.use(ram_intake)
    s.use(fan)
    s.use(hp_compressor)
    s.use(combustor)
    s.use(hp_turbine)
    s.use(lp_turbine)
    s.use(nozzle)                    # core nozzle 5 -> 9
    s.use(bypass_nozzle)             # bypass nozzle 13 -> 19
    s.use(turbofan_thrust, map={"mdot_core": "mdot"})
    return s


def build_turboprop(name="turboprop"):
    """Turboprop / turboshaft with a free power turbine driving a propeller."""
    s = System(name, "Turboprop with free power turbine")
    s.add("T_amb", 288.15, "K", desc="Ambient (static) temperature")
    s.add("P_amb", 101325.0, "Pa", desc="Ambient (static) pressure")
    s.add("M0", 0.0, desc="Flight Mach number")
    s.add("pi_c", 12.0, desc="Compressor pressure ratio")
    s.add("T04", 1350.0, "K", desc="Turbine inlet temperature (TIT)")
    s.add("mdot", 1.0, "kg/s", desc="Core mass flow")
    s.use(ram_intake)
    s.use(compressor)
    s.use(combustor)
    # Gas generator turbine drives the compressor (HP-style balance).
    s.use(hp_turbine)
    # Free power turbine extracts shaft power from station 45.
    s.use(power_turbine)
    s.use(turboshaft_performance, map={"mdot_core": "mdot"})
    return s


# --------------------------------------------------------------------------- #
# Post-processing: station table + cycle diagrams
# --------------------------------------------------------------------------- #

# Station variable names present for each engine type, in flow order.
_STATION_MAP = [
    ("0", "T_amb", "P_amb"),
    ("2", "T02", "P02"),
    ("13", "T13", "P13"),
    ("3", "T03", "P03"),
    ("4", "T04", "P04"),
    ("45", "T45", "P45"),
    ("5", "T05", "P05"),
    ("7", "T07", "P07"),
    ("9", "T9", "P9"),
    ("19", "T19", "P19"),
]

_STATION_LABEL = {
    "0": "ambient", "2": "comp face", "13": "fan/bypass exit",
    "3": "comp exit", "4": "turbine inlet", "45": "HPT exit",
    "5": "turbine exit", "7": "afterburner", "9": "core nozzle",
    "19": "bypass nozzle",
}


def _val(result, key):
    """SI float of a result quantity, or None if absent/undefined."""
    if key not in result:
        return None
    q = result[key]
    try:
        return float(q._si_value) if hasattr(q, "_si_value") else float(q)
    except (TypeError, ValueError):
        return None


def station_table(result, as_text=True):
    """Per-station stagnation table (T0, P0) from a solved cycle Result.

    Returns a formatted string (``as_text=True``) or a list of row dicts.
    Only stations present in the result are shown.
    """
    rows = []
    for station, tkey, pkey in _STATION_MAP:
        T = _val(result, tkey)
        P = _val(result, pkey)
        if T is None and P is None:
            continue
        rows.append({"station": station, "label": _STATION_LABEL.get(station, ""),
                     "T0_K": T, "P0_Pa": P})
    if not as_text:
        return rows
    lines = [f"  {'st':>3}  {'location':<16}  {'T0 [K]':>10}  {'P0 [kPa]':>10}",
             "  " + "-" * 45]
    for r in rows:
        t = f"{r['T0_K']:.1f}" if r["T0_K"] is not None else "-"
        p = f"{r['P0_Pa'] / 1000:.1f}" if r["P0_Pa"] is not None else "-"
        lines.append(f"  {r['station']:>3}  {r['label']:<16}  {t:>10}  {p:>10}")
    return "\n".join(lines)


def cycle_diagram(result, kind="Ts", cp=CP_HOT, R=R_HOT, ax=None):
    """Cycle diagram from a solved Result. ``kind`` is "Ts" or "hs" (Mollier).

    Plots stagnation temperature (or enthalpy) against a computed entropy
    change through the stations present in the result. Requires matplotlib;
    returns the Matplotlib Figure.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "cycle_diagram needs matplotlib. Install with: pip install matplotlib"
        ) from e

    cp = float(cp); R = float(R)
    pts = []
    for station, tkey, pkey in _STATION_MAP:
        T = _val(result, tkey)
        P = _val(result, pkey)
        if T is None or P is None:
            continue
        pts.append((station, T, P))
    if len(pts) < 2:
        raise ValueError("Not enough stations with T0 and P0 to draw a cycle.")

    # Entropy relative to the first station: ds = cp ln(T/Tref) - R ln(P/Pref).
    _, T0, P0 = pts[0]
    s_vals, y_vals, labels = [], [], []
    for station, T, P in pts:
        s = cp * math.log(T / T0) - R * math.log(P / P0)
        s_vals.append(s)
        y_vals.append(cp * (T - T0) if kind == "hs" else T)
        labels.append(station)

    created = ax is None
    if created:
        fig, ax = plt.subplots(figsize=(7, 5))
    else:
        fig = ax.figure
    ax.plot(s_vals, y_vals, "-o", color="#222", lw=1.6, zorder=3)
    for s, y, lab in zip(s_vals, y_vals, labels):
        ax.annotate(lab, (s, y), textcoords="offset points", xytext=(6, 6),
                    fontsize=10, fontfamily="monospace")
    ax.set_xlabel("entropy change  s - s0  [J/(kg K)]")
    if kind == "hs":
        ax.set_ylabel("stagnation enthalpy  h0 - h0,ref  [J/kg]")
        ax.set_title(f"{result._system_name or 'cycle'}  --  h-s (Mollier) diagram")
    else:
        ax.set_ylabel("stagnation temperature  T0  [K]")
        ax.set_title(f"{result._system_name or 'cycle'}  --  T-s diagram")
    ax.grid(True, alpha=0.25)
    if created:
        fig.tight_layout()
    return fig
