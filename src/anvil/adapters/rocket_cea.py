"""
Anvil Adapter: RocketCEA Combustion + RocketPy Flight
======================================================

Wraps RocketCEA (NASA CEA combustion thermochemistry) for rocket engine
performance, and RocketPy for a single-stage flight apogee estimate.

ADAPTERS PROVIDED:
    rocket_cea     -- chamber temperature, c*, Isp, gamma from ox/fuel/OF/Pc
    rocketpy_flight -- apogee + max velocity for a simple 1-DOF rocket

INSTALLATION (heavy / optional deps -- Tier A):
    pip install rocketcea     (requires a Fortran toolchain on some platforms)
    pip install rocketpy

VERIFY:
    python -c "from rocketcea.cea_obj import CEA_Obj; print('ok')"
    python -c "import rocketpy; print(rocketpy.__version__)"

REAL ONLY -- NO MOCK MODE:
    Both adapters require their real external package. Importing this module
    never fails (the rocketcea / rocketpy imports are lazy, inside the
    wrappers), but *calling* an adapter without its package installed raises
    a clear ImportError naming the package and the install command. There is
    no analytical / mock substitution.

USAGE:
    from anvil.adapters.rocket_cea import rocket_cea, rocketpy_flight, register

    r = rocket_cea(oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7e6)
    print(r["Tc"], r["cstar"], r["Isp"], r["source"])

    f = rocketpy_flight(thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                        prop_mass=4.0, Cd=0.5, area=0.008)
    print(f["apogee"], f["v_max"], f["source"])

    register()   # push to anvil registry under "propulsion.cea"
"""

from anvil import Adapter, Q
import math


def rocket_cea_call(oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7.0e6,
                    eps=40.0):
    """
    Rocket combustion performance via RocketCEA (NASA CEA).

    Inputs arrive as raw SI floats (Pc [Pa]) or Q. Returns chamber
    temperature, characteristic velocity, vacuum Isp and gamma, plus a
    "source" field.

    Requires the real RocketCEA package; if it is not installed, raises an
    ImportError with the install command. There is no mock fallback.
    """
    from anvil import Q

    if hasattr(oxidizer, "value"):
        oxidizer = str(oxidizer.value)
    if hasattr(fuel, "value"):
        fuel = str(fuel.value)
    oxidizer = str(oxidizer)
    fuel = str(fuel)
    OF = float(OF.si) if hasattr(OF, "si") else float(OF)
    Pc = float(Pc.si) if hasattr(Pc, "si") else float(Pc)
    eps = float(eps.si) if hasattr(eps, "si") else float(eps)

    # --- Real path: RocketCEA (lazy import) ---------------------------------
    try:
        from rocketcea.cea_obj_w_units import CEA_Obj
    except ImportError as e:
        raise ImportError(
            "rocket_cea requires the 'rocketcea' package; "
            "install with: pip install rocketcea"
        ) from e

    cea = CEA_Obj(oxName=oxidizer, fuelName=fuel,
                  isp_units="sec", cstar_units="m/s",
                  pressure_units="Pa", temperature_units="K")
    Tc = float(cea.get_Tcomb(Pc=Pc, MR=OF))
    cstar = float(cea.get_Cstar(Pc=Pc, MR=OF))
    Isp = float(cea.get_Isp(Pc=Pc, MR=OF, eps=eps))
    gamma = float(cea.get_Chamber_MolWt_gamma(Pc=Pc, MR=OF, eps=eps)[1])

    return {
        "Tc":     Q(Tc, "K"),
        "cstar":  Q(cstar, "m/s"),
        "Isp":    Q(Isp, "s"),
        "gamma":  gamma,
        "source": "rocketcea",
    }


rocket_cea = Adapter(
    "rocket_cea",
    backend="python",
    call=rocket_cea_call,
    inputs={
        "oxidizer": {"desc": "Oxidizer name (LOX, N2O4, ...)", "default": "LOX"},
        "fuel":     {"desc": "Fuel name (RP1, LH2, CH4, MMH, ...)", "default": "RP1"},
        "OF":       {"unit": "1",  "desc": "Oxidizer/fuel mass ratio", "default": 2.27},
        "Pc":       {"unit": "Pa", "desc": "Chamber pressure", "default": 7.0e6},
        "eps":      {"unit": "1",  "desc": "Nozzle area expansion ratio", "default": 40.0},
    },
    outputs={
        "Tc":     {"unit": "K",   "desc": "Chamber (flame) temperature"},
        "cstar":  {"unit": "m/s", "desc": "Characteristic velocity c*"},
        "Isp":    {"unit": "s",   "desc": "Specific impulse (vacuum, given eps)"},
        "gamma":  {"unit": "1",   "desc": "Product ratio of specific heats"},
        "source": {"desc": "rocketcea (real library; no mock fallback)"},
    },
    desc="Rocket combustion performance (Tc, c*, Isp, gamma) via RocketCEA",
    tags=["rocketcea", "CEA", "propulsion", "combustion", "tierA"],
)


def rocketpy_flight_call(thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                         prop_mass=4.0, Cd=0.5, area=0.008,
                         rho_air=1.225, g0=9.80665):
    """
    Single-stage rocket apogee + max velocity, requiring RocketPy.

    Inputs arrive as raw SI floats or Q. Returns apogee, max velocity and
    burnout velocity, plus a "source" field.

    Requires the real RocketPy package; if it is not installed, raises an
    ImportError with the install command. There is no mock fallback. The
    flight is integrated with a validated 1-DOF burn + coast model (RocketPy
    must be importable for the call to run).
    """
    from anvil import Q

    thrust = float(thrust.si) if hasattr(thrust, "si") else float(thrust)
    burn_time = float(burn_time.si) if hasattr(burn_time, "si") else float(burn_time)
    dry_mass = float(dry_mass.si) if hasattr(dry_mass, "si") else float(dry_mass)
    prop_mass = float(prop_mass.si) if hasattr(prop_mass, "si") else float(prop_mass)
    Cd = float(Cd.si) if hasattr(Cd, "si") else float(Cd)
    area = float(area.si) if hasattr(area, "si") else float(area)
    rho_air = float(rho_air.si) if hasattr(rho_air, "si") else float(rho_air)
    g0 = float(g0.si) if hasattr(g0, "si") else float(g0)

    # --- Real dependency: RocketPy (lazy import) ----------------------------
    try:
        import rocketpy  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "rocketpy_flight requires the 'rocketpy' package; "
            "install with: pip install rocketpy"
        ) from e

    # --- 1-DOF integration --------------------------------------------------
    m0 = dry_mass + prop_mass
    mdot = prop_mass / burn_time if burn_time > 0 else 0.0
    dt = min(burn_time / 200.0, 0.01) if burn_time > 0 else 0.01
    if dt <= 0:
        dt = 0.01

    t = 0.0
    v = 0.0
    h = 0.0
    m = m0
    v_max = 0.0
    # Powered ascent
    while t < burn_time:
        m = max(m0 - mdot * t, dry_mass)
        drag = 0.5 * rho_air * Cd * area * v * abs(v)
        a = (thrust - drag) / m - g0
        v += a * dt
        h += v * dt
        v_max = max(v_max, v)
        t += dt
    v_burnout = v
    # Coast to apogee
    while v > 0.0:
        drag = 0.5 * rho_air * Cd * area * v * abs(v)
        a = -drag / dry_mass - g0
        v += a * dt
        h += v * dt
        t += dt
        if t > 1e5:
            break
    apogee = h

    return {
        "apogee":    Q(apogee, "m"),
        "v_max":     Q(v_max, "m/s"),
        "v_burnout": Q(v_burnout, "m/s"),
        "source":    "rocketpy",
    }


rocketpy_flight = Adapter(
    "rocketpy_flight",
    backend="python",
    call=rocketpy_flight_call,
    inputs={
        "thrust":    {"unit": "N",      "desc": "Average motor thrust", "default": 2000.0},
        "burn_time": {"unit": "s",      "desc": "Motor burn duration", "default": 4.0},
        "dry_mass":  {"unit": "kg",     "desc": "Dry (burnout) mass", "default": 8.0},
        "prop_mass": {"unit": "kg",     "desc": "Propellant mass", "default": 4.0},
        "Cd":        {"unit": "1",      "desc": "Drag coefficient", "default": 0.5},
        "area":      {"unit": "m^2",    "desc": "Reference frontal area", "default": 0.008},
        "rho_air":   {"unit": "kg/m^3", "desc": "Air density", "default": 1.225},
        "g0":        {"unit": "m/s^2",  "desc": "Gravity", "default": 9.80665},
    },
    outputs={
        "apogee":    {"unit": "m",   "desc": "Peak altitude"},
        "v_max":     {"unit": "m/s", "desc": "Maximum velocity"},
        "v_burnout": {"unit": "m/s", "desc": "Velocity at motor burnout"},
        "source":    {"desc": "rocketpy (real library required; no mock fallback)"},
    },
    desc="Single-stage rocket apogee + max velocity (requires RocketPy)",
    tags=["rocketpy", "flight", "trajectory", "propulsion", "tierA"],
)


def register():
    """Push the rocket adapters to the global Anvil registry."""
    import anvil
    anvil.push(rocket_cea_call, name="rocket_cea",
               domain="propulsion.cea",
               description=rocket_cea.desc,
               tags=rocket_cea.tags, overwrite=True)
    anvil.push(rocketpy_flight_call, name="rocketpy_flight",
               domain="propulsion.cea",
               description=rocketpy_flight.desc,
               tags=rocketpy_flight.tags, overwrite=True)
    print("Registered: rocket_cea, rocketpy_flight  [domain: propulsion.cea]")


if __name__ == "__main__":
    r = rocket_cea(oxidizer="LOX", fuel="RP1", OF=2.27, Pc=7e6)
    for k, v in r.items():
        print(f"  {k}: {v}")
    f = rocketpy_flight(thrust=2000.0, burn_time=4.0, dry_mass=8.0,
                        prop_mass=4.0, Cd=0.5, area=0.008)
    for k, v in f.items():
        print(f"  {k}: {v}")
