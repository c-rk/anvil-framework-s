"""
Anvil Adapter: pykep Trajectory Design
=======================================

Wraps pykep for Lambert arc solutions, Keplerian propagation, and
planet ephemerides.  Designed to complement poliastro_orbits.py:
poliastro for orbit design (Keplerian elements, maneuvers),
pykep for trajectory design (Lambert, planet-to-planet transfers).

ADAPTERS PROVIDED:
    pykep_lambert       -- Lambert arc: two position vectors + TOF -> v_dep, v_arr
    pykep_propagate     -- Propagate Cartesian state by time of flight
    pykep_planet_state  -- Heliocentric planet position/velocity from JPL ephemeris

INSTALLATION:
    pip install pykep

    pykep >= 2.6, Python 3.8+.

VERIFY:
    python -c "import pykep; print(pykep.__version__)"

REAL ONLY -- NO MOCK MODE:
    Requires pykep; missing package raises ImportError for every adapter.

ALL UNITS:
    pykep uses SI throughout (m, m/s, s, m^3/s^2). Anvil adapters pass and
    return SI values with Q wrappers. No unit conversion occurs at the adapter
    boundary.

USAGE:
    from anvil.adapters.pykep_trajectories import pykep_lambert, pykep_propagate, pykep_planet_state

    # Earth position now
    r = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
    print(r["r_x"])   # Q(~1.5e11, "m")

    # Lambert arc Earth -> Mars in 200 days
    sol = pykep_lambert(
        r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
        r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,  r1_z=r_mars["r_z"].si,
        tof=200 * 86400,
    )
    print(sol["dv_dep"])   # departure delta-v magnitude (m/s)

    register()   # push all three to global registry under "trajectory.pykep"
"""

from anvil import Adapter, Q
import math

MU_SUN = 1.32712440018e20   # m^3/s^2
AU     = 1.495978707e11     # m
GM_EARTH = 3.986004418e14   # m^3/s^2


def _require_pykep():
    """Import pykep or raise with install instructions."""
    try:
        import pykep  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "pykep is not installed. Install with: pip install pykep\n"
            "Docs: https://esa.github.io/pykep/"
        ) from exc


def is_available() -> bool:
    """True when pykep can be imported."""
    try:
        import pykep  # noqa: F401
        return True
    except ImportError:
        return False


# ── Adapter 1: pykep_lambert ──────────────────────────────────────────────────

def _lambert_call(r0_x, r0_y, r0_z, r1_x, r1_y, r1_z, tof,
                  mu=MU_SUN, cw=0.0, multi_revs=0.0):
    """
    Lambert arc from r0 to r1 in tof seconds.
    Returns departure/arrival velocity vectors and delta-v magnitudes.
    cw: 0 = prograde (default), 1 = retrograde.
    multi_revs: max multi-revolution solutions (0 = single rev only).
    pykep REQUIRED -- no analytical fallback for Lambert.
    """
    _require_pykep()
    import pykep as pk

    r0 = [r0_x, r0_y, r0_z]
    r1 = [r1_x, r1_y, r1_z]

    l = pk.lambert_problem(
        r1=r0, r2=r1, tof=tof, mu=mu,
        cw=bool(cw), multi_revs=int(multi_revs),
    )
    v_dep = l.get_v1()[0]
    v_arr = l.get_v2()[0]

    dv_dep = math.sqrt(sum(v**2 for v in v_dep))
    dv_arr = math.sqrt(sum(v**2 for v in v_arr))

    return {
        "v_dep_x": Q(v_dep[0], "m/s"), "v_dep_y": Q(v_dep[1], "m/s"),
        "v_dep_z": Q(v_dep[2], "m/s"),
        "v_arr_x": Q(v_arr[0], "m/s"), "v_arr_y": Q(v_arr[1], "m/s"),
        "v_arr_z": Q(v_arr[2], "m/s"),
        "dv_dep":  Q(dv_dep,   "m/s"),
        "dv_arr":  Q(dv_arr,   "m/s"),
        "dv_total":Q(dv_dep + dv_arr, "m/s"),
    }


pykep_lambert = Adapter("pykep_lambert",
    backend="python", call=_lambert_call,
    inputs={
        "r0_x": {"unit": "m", "desc": "Departure position x"},
        "r0_y": {"unit": "m", "desc": "Departure position y"},
        "r0_z": {"unit": "m", "desc": "Departure position z"},
        "r1_x": {"unit": "m", "desc": "Arrival position x"},
        "r1_y": {"unit": "m", "desc": "Arrival position y"},
        "r1_z": {"unit": "m", "desc": "Arrival position z"},
        "tof":  {"unit": "s", "desc": "Time of flight"},
        "mu":   {"desc": "Gravitational parameter (m^3/s^2); default: Sun",
                 "default": MU_SUN},
        "cw":         {"desc": "1 = retrograde / clockwise arc, 0 = prograde", "default": 0.0},
        "multi_revs": {"desc": "Max multi-rev solutions (0 = single rev)", "default": 0.0},
    },
    outputs={
        "v_dep_x": {"unit": "m/s"}, "v_dep_y": {"unit": "m/s"}, "v_dep_z": {"unit": "m/s"},
        "v_arr_x": {"unit": "m/s"}, "v_arr_y": {"unit": "m/s"}, "v_arr_z": {"unit": "m/s"},
        "dv_dep":   {"unit": "m/s", "desc": "Departure velocity magnitude"},
        "dv_arr":   {"unit": "m/s", "desc": "Arrival velocity magnitude"},
        "dv_total": {"unit": "m/s", "desc": "Total Lambert arc delta-v"},
    },
    desc="Lambert arc between two position vectors (pykep) -- pykep required",
    tags=["lambert", "transfer", "trajectory", "pykep"],
)


# ── Adapter 2: pykep_propagate ────────────────────────────────────────────────

def _prop_call(r_x, r_y, r_z, v_x, v_y, v_z, dt, mu=GM_EARTH):
    r0 = [r_x, r_y, r_z]
    v0 = [v_x, v_y, v_z]

    _require_pykep()
    import pykep as pk
    r1, v1 = pk.propagate_lagrangian(r0, v0, dt, mu)

    return {
        "r_x_f": Q(r1[0], "m"),   "r_y_f": Q(r1[1], "m"),   "r_z_f": Q(r1[2], "m"),
        "v_x_f": Q(v1[0], "m/s"), "v_y_f": Q(v1[1], "m/s"), "v_z_f": Q(v1[2], "m/s"),
        "r_mag_f": Q(math.sqrt(sum(x**2 for x in r1)), "m"),
        "v_mag_f": Q(math.sqrt(sum(x**2 for x in v1)), "m/s"),
    }


pykep_propagate = Adapter("pykep_propagate",
    backend="python", call=_prop_call,
    inputs={
        "r_x": {"unit": "m",   "desc": "Initial position x"},
        "r_y": {"unit": "m",   "desc": "Initial position y"},
        "r_z": {"unit": "m",   "desc": "Initial position z"},
        "v_x": {"unit": "m/s", "desc": "Initial velocity x"},
        "v_y": {"unit": "m/s", "desc": "Initial velocity y"},
        "v_z": {"unit": "m/s", "desc": "Initial velocity z"},
        "dt":  {"unit": "s",   "desc": "Propagation time"},
        "mu":  {"desc": "Gravitational parameter (m^3/s^2); default: Earth",
                "default": GM_EARTH},
    },
    outputs={
        "r_x_f": {"unit": "m"},   "r_y_f": {"unit": "m"},   "r_z_f": {"unit": "m"},
        "v_x_f": {"unit": "m/s"}, "v_y_f": {"unit": "m/s"}, "v_z_f": {"unit": "m/s"},
        "r_mag_f": {"unit": "m",   "desc": "Final distance from central body"},
        "v_mag_f": {"unit": "m/s", "desc": "Final speed"},
    },
    desc="Propagate Cartesian state by time of flight, Keplerian (pykep)",
    tags=["propagation", "keplerian", "cartesian", "pykep"],
)


# ── Adapter 3: pykep_planet_state ─────────────────────────────────────────────

def _planet_call(planet="earth", epoch_mjd2000=0.0):
    """
    Heliocentric position/velocity of a planet.
    planet: "mercury","venus","earth","mars","jupiter","saturn","uranus","neptune"
    epoch_mjd2000: days since 2000-01-01.5 (MJD2000).
    """
    _require_pykep()
    import pykep as pk
    body  = pk.planet.jpl_lp(planet.lower())
    epoch = pk.epoch(epoch_mjd2000, "mjd2000")
    r_m, v_ms = body.eph(epoch)

    r_mag = math.sqrt(sum(x**2 for x in r_m))
    v_mag = math.sqrt(sum(x**2 for x in v_ms))

    return {
        "r_x": Q(float(r_m[0]),  "m"),   "r_y": Q(float(r_m[1]),  "m"),
        "r_z": Q(float(r_m[2]),  "m"),
        "v_x": Q(float(v_ms[0]), "m/s"), "v_y": Q(float(v_ms[1]), "m/s"),
        "v_z": Q(float(v_ms[2]), "m/s"),
        "r_mag": Q(r_mag, "m"),
        "v_mag": Q(v_mag, "m/s"),
    }


pykep_planet_state = Adapter("pykep_planet_state",
    backend="python", call=_planet_call,
    inputs={
        "planet":        {"desc": "Planet name string: earth, mars, venus, ...",
                          "default": "earth"},
        "epoch_mjd2000": {"desc": "Epoch in days since 2000-01-01.5 (MJD2000)",
                          "default": 0.0},
    },
    outputs={
        "r_x": {"unit": "m"}, "r_y": {"unit": "m"}, "r_z": {"unit": "m"},
        "v_x": {"unit": "m/s"}, "v_y": {"unit": "m/s"}, "v_z": {"unit": "m/s"},
        "r_mag": {"unit": "m",   "desc": "Heliocentric distance"},
        "v_mag": {"unit": "m/s", "desc": "Heliocentric speed"},
    },
    desc="Heliocentric planet position/velocity from JPL low-precision ephemeris (pykep)",
    tags=["planet", "ephemeris", "heliocentric", "pykep"],
)


# ── Register ──────────────────────────────────────────────────────────────────

def register():
    """Push all pykep adapters to the global Anvil registry."""
    import anvil
    for ad in (pykep_lambert, pykep_propagate, pykep_planet_state):
        anvil.push(ad, domain="trajectory.pykep", tags=["pykep"])


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("pykep adapters -- smoke test (requires pykep installed)")
    print()

    # Earth state at J2000
    r_earth = pykep_planet_state(planet="earth", epoch_mjd2000=0.0)
    print(f"Earth at J2000:")
    print(f"  |r| = {r_earth['r_mag'].value / AU:.4f} AU")
    print(f"  |v| = {r_earth['v_mag'].value / 1e3:.3f} km/s  (expect ~29.8)")

    # Mars state at J2000
    r_mars = pykep_planet_state(planet="mars", epoch_mjd2000=0.0)
    print(f"\nMars at J2000:")
    print(f"  |r| = {r_mars['r_mag'].value / AU:.4f} AU  (expect ~1.38 AU)")

    # Propagate Earth state by 1 year
    r_e1y = pykep_propagate(
        r_x=r_earth["r_x"].si, r_y=r_earth["r_y"].si, r_z=r_earth["r_z"].si,
        v_x=r_earth["v_x"].si, v_y=r_earth["v_y"].si, v_z=r_earth["v_z"].si,
        dt=365.25 * 86400, mu=MU_SUN,
    )
    print(f"\nEarth propagated 1 year:")
    print(f"  |r| = {r_e1y['r_mag_f'].value / AU:.4f} AU  (expect ~1.00)")

    # Lambert arc (requires pykep; shows usage pattern)
    print(f"\nLambert arc (Earth->Mars, 200 days) -- skipped if pykep not installed")
    try:
        sol = pykep_lambert(
            r0_x=r_earth["r_x"].si, r0_y=r_earth["r_y"].si, r0_z=r_earth["r_z"].si,
            r1_x=r_mars["r_x"].si,  r1_y=r_mars["r_y"].si,  r1_z=r_mars["r_z"].si,
            tof=200 * 86400,
        )
        print(f"  v_dep   = {sol['dv_dep'].value / 1e3:.3f} km/s")
        print(f"  v_arr   = {sol['dv_arr'].value / 1e3:.3f} km/s")
    except ImportError as e:
        print(f"  {e.args[0].splitlines()[0]}")
