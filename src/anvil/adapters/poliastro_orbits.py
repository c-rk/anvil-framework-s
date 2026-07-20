"""
Anvil Adapter: poliastro Orbital Mechanics
==========================================

Wraps poliastro two-body orbital mechanics for orbit state computation,
Hohmann transfers, and time propagation.

ADAPTERS PROVIDED:
    poliastro_orbit      -- Keplerian elements -> ECI state + orbital properties
    poliastro_hohmann    -- Hohmann transfer delta-v and transfer time
    poliastro_propagate  -- Propagate orbit forward by time of flight

INSTALLATION:
    pip install poliastro astropy

    poliastro >= 0.17.0, Python 3.10+ required.

VERIFY:
    python -c "import poliastro; print(poliastro.__version__)"

REAL ONLY -- NO MOCK MODE:
    Requires poliastro + astropy; missing packages raise ImportError. The
    equivalent closed-form two-body math lives in the native orbital RSQs
    (anvil.R.hohmann_transfer, vis_viva, orbital_period, ...).

USAGE:
    from anvil.adapters.poliastro_orbits import poliastro_orbit, poliastro_hohmann, poliastro_propagate

    r = poliastro_orbit(a=6778e3, ecc=0.0, inc=0.9, raan=0.0, argp=0.0, nu=0.0)
    print(r["period"])    # Q(5556.6, "s")
    print(r["v_mag"])     # Q(7669.2, "m/s")

    register()   # push all three to global Anvil registry under "orbital.poliastro"
"""

from anvil import Adapter, Q
import math

MU_EARTH = 3.986004418e14   # m^3/s^2


def _require_poliastro():
    """Import poliastro or raise with install instructions."""
    try:
        import poliastro  # noqa: F401
        from astropy import units  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "poliastro is not installed. Install with: "
            "pip install poliastro astropy"
        ) from exc


def is_available() -> bool:
    """True when poliastro + astropy can be imported."""
    try:
        import poliastro  # noqa: F401
        from astropy import units  # noqa: F401
        return True
    except ImportError:
        return False


# ── Adapter 1: poliastro_orbit ────────────────────────────────────────────────

def _orbit_call(a, ecc, inc, raan, argp, nu, mu=MU_EARTH):
    _require_poliastro()
    if True:
        from poliastro.twobody import Orbit
        from poliastro.bodies import Earth
        from astropy import units as u

        orbit = Orbit.from_classical(
            Earth,
            (a * 1e-3)         * u.km,
            ecc                * u.one,
            math.degrees(inc)  * u.deg,
            math.degrees(raan) * u.deg,
            math.degrees(argp) * u.deg,
            math.degrees(nu)   * u.deg,
        )
        r_vec, v_vec = orbit.rv()
        rx, ry, rz = [float(x) for x in r_vec.to(u.m).value]
        vx, vy, vz = [float(x) for x in v_vec.to(u.m / u.s).value]
        T  = float(orbit.T.to(u.s).value)
        a_km = float(orbit.a.to(u.m).value)
        ecc_v = float(orbit.ecc.value)
        ra, rp = a_km * (1.0 + ecc_v), a_km * (1.0 - ecc_v)

    return {
        "r_x": Q(rx, "m"),   "r_y": Q(ry, "m"),   "r_z": Q(rz, "m"),
        "v_x": Q(vx, "m/s"), "v_y": Q(vy, "m/s"), "v_z": Q(vz, "m/s"),
        "r_mag":       Q(math.sqrt(rx**2 + ry**2 + rz**2), "m"),
        "v_mag":       Q(math.sqrt(vx**2 + vy**2 + vz**2), "m/s"),
        "period":      Q(T,  "s"),
        "r_apoapsis":  Q(ra, "m"),
        "r_periapsis": Q(rp, "m"),
    }


poliastro_orbit = Adapter("poliastro_orbit",
    backend="python", call=_orbit_call,
    inputs={
        "a":    {"unit": "m",   "desc": "Semi-major axis"},
        "ecc":  {               "desc": "Eccentricity (0 = circular)"},
        "inc":  {"unit": "rad", "desc": "Inclination"},
        "raan": {"unit": "rad", "desc": "Right ascension of ascending node"},
        "argp": {"unit": "rad", "desc": "Argument of perigee"},
        "nu":   {"unit": "rad", "desc": "True anomaly"},
        "mu":   {"desc": "Gravitational parameter (m^3/s^2); default: Earth",
                 "default": MU_EARTH},
    },
    outputs={
        "r_x": {"unit": "m"},   "r_y": {"unit": "m"},   "r_z": {"unit": "m"},
        "v_x": {"unit": "m/s"}, "v_y": {"unit": "m/s"}, "v_z": {"unit": "m/s"},
        "r_mag":       {"unit": "m",   "desc": "Distance from central body"},
        "v_mag":       {"unit": "m/s", "desc": "Orbital speed"},
        "period":      {"unit": "s",   "desc": "Orbital period"},
        "r_apoapsis":  {"unit": "m",   "desc": "Apoapsis radius"},
        "r_periapsis": {"unit": "m",   "desc": "Periapsis radius"},
    },
    desc="Keplerian elements to ECI state vector and orbital properties (poliastro)",
    tags=["orbit", "keplerian", "state", "poliastro", "astrodynamics"],
)


# ── Adapter 2: poliastro_hohmann ──────────────────────────────────────────────

def _hohmann_call(a_i, a_f, mu=MU_EARTH):
    """
    Hohmann transfer between two coplanar circular orbits.
    a_i, a_f: orbit radii (= SMA for circular), m.
    """
    _require_poliastro()
    if True:
        from poliastro.twobody import Orbit
        from poliastro.bodies import Earth
        from poliastro.maneuver import Maneuver
        from astropy import units as u
        import numpy as np

        orbit_i = Orbit.from_classical(
            Earth,
            (a_i * 1e-3) * u.km, 0.0 * u.one,
            0.0 * u.deg, 0.0 * u.deg, 0.0 * u.deg, 0.0 * u.deg,
        )
        man = Maneuver.hohmann(orbit_i, (a_f * 1e-3) * u.km)
        dv1 = float(np.linalg.norm(man.impulses[0][1].to(u.m / u.s).value))
        dv2 = float(np.linalg.norm(man.impulses[1][1].to(u.m / u.s).value))
        dv_total = float(man.get_total_cost().to(u.m / u.s).value)

    a_t = 0.5 * (a_i + a_f)
    t_transfer = math.pi * math.sqrt(a_t**3 / mu)

    return {
        "dv_1":       Q(dv1,        "m/s"),
        "dv_2":       Q(dv2,        "m/s"),
        "dv_total":   Q(dv_total,   "m/s"),
        "t_transfer": Q(t_transfer, "s"),
        "a_transfer": Q(a_t,        "m"),
    }


poliastro_hohmann = Adapter("poliastro_hohmann",
    backend="python", call=_hohmann_call,
    inputs={
        "a_i": {"unit": "m", "desc": "Initial orbit radius / SMA (circular)"},
        "a_f": {"unit": "m", "desc": "Final orbit radius / SMA (circular)"},
        "mu":  {"desc": "Gravitational parameter (m^3/s^2); default: Earth",
                "default": MU_EARTH},
    },
    outputs={
        "dv_1":       {"unit": "m/s", "desc": "Departure burn delta-v"},
        "dv_2":       {"unit": "m/s", "desc": "Arrival burn delta-v"},
        "dv_total":   {"unit": "m/s", "desc": "Total transfer delta-v"},
        "t_transfer": {"unit": "s",   "desc": "Transfer time (half period of transfer ellipse)"},
        "a_transfer": {"unit": "m",   "desc": "Transfer ellipse semi-major axis"},
    },
    desc="Hohmann transfer delta-v for coplanar circular-to-circular transfer (poliastro)",
    tags=["orbit", "hohmann", "transfer", "dv", "poliastro"],
)


# ── Adapter 3: poliastro_propagate ────────────────────────────────────────────

def _propagate_call(a, ecc, inc, raan, argp, nu, dt, mu=MU_EARTH):
    """Propagate Keplerian orbit by dt seconds; return new ECI state."""
    _require_poliastro()
    if True:
        from poliastro.twobody import Orbit
        from poliastro.bodies import Earth
        from astropy import units as u

        orbit = Orbit.from_classical(
            Earth,
            (a * 1e-3)         * u.km,
            ecc                * u.one,
            math.degrees(inc)  * u.deg,
            math.degrees(raan) * u.deg,
            math.degrees(argp) * u.deg,
            math.degrees(nu)   * u.deg,
        )
        orbit_f = orbit.propagate(dt * u.s)
        r_vec, v_vec = orbit_f.rv()
        rx, ry, rz = [float(x) for x in r_vec.to(u.m).value]
        vx, vy, vz = [float(x) for x in v_vec.to(u.m / u.s).value]
        nu_f = float(orbit_f.nu.to(u.rad).value)

    return {
        "r_x": Q(rx, "m"),   "r_y": Q(ry, "m"),   "r_z": Q(rz, "m"),
        "v_x": Q(vx, "m/s"), "v_y": Q(vy, "m/s"), "v_z": Q(vz, "m/s"),
        "nu_f": Q(nu_f, "rad"),
    }


poliastro_propagate = Adapter("poliastro_propagate",
    backend="python", call=_propagate_call,
    inputs={
        "a":    {"unit": "m",   "desc": "Semi-major axis"},
        "ecc":  {               "desc": "Eccentricity"},
        "inc":  {"unit": "rad", "desc": "Inclination"},
        "raan": {"unit": "rad", "desc": "Right ascension of ascending node"},
        "argp": {"unit": "rad", "desc": "Argument of perigee"},
        "nu":   {"unit": "rad", "desc": "True anomaly at epoch"},
        "dt":   {"unit": "s",   "desc": "Propagation time"},
        "mu":   {"desc": "Gravitational parameter (m^3/s^2); default: Earth",
                 "default": MU_EARTH},
    },
    outputs={
        "r_x": {"unit": "m"},   "r_y": {"unit": "m"},   "r_z": {"unit": "m"},
        "v_x": {"unit": "m/s"}, "v_y": {"unit": "m/s"}, "v_z": {"unit": "m/s"},
        "nu_f": {"unit": "rad", "desc": "True anomaly after propagation"},
    },
    desc="Propagate Keplerian orbit by time of flight, return new ECI state (poliastro)",
    tags=["orbit", "propagation", "keplerian", "poliastro"],
)


# ── Register ──────────────────────────────────────────────────────────────────

def register():
    """Push all poliastro adapters to the global Anvil registry."""
    import anvil
    for ad in (poliastro_orbit, poliastro_hohmann, poliastro_propagate):
        anvil.push(ad, domain="orbital.poliastro", tags=["poliastro"])


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    R_E = 6371e3

    print("poliastro adapters -- smoke test (requires poliastro installed)")
    print()

    # ISS-like LEO orbit
    r = poliastro_orbit(a=R_E + 407e3, ecc=0.0,
                         inc=math.radians(51.6), raan=0.0, argp=0.0, nu=0.0)
    print(f"ISS-like orbit (407 km, 51.6 deg incl):")
    print(f"  period  = {r['period'].to('min').value:.2f} min")
    print(f"  v_mag   = {r['v_mag'].value:.1f} m/s")
    print(f"  r_mag   = {r['r_mag'].value / 1e6:.4f} Mm")

    # LEO to GEO Hohmann
    r_h = poliastro_hohmann(a_i=R_E + 200e3, a_f=42164e3)
    print(f"\nLEO (200 km) -> GEO Hohmann:")
    print(f"  dv_1      = {r_h['dv_1'].value:.1f} m/s")
    print(f"  dv_2      = {r_h['dv_2'].value:.1f} m/s")
    print(f"  dv_total  = {r_h['dv_total'].value:.1f} m/s")
    print(f"  transfer  = {r_h['t_transfer'].to('hr').value:.2f} h")

    # Propagate quarter orbit
    T = poliastro_orbit(a=R_E + 200e3, ecc=0.0, inc=0.0,
                         raan=0.0, argp=0.0, nu=0.0)["period"].si
    r_p = poliastro_propagate(a=R_E + 200e3, ecc=0.0, inc=0.0,
                               raan=0.0, argp=0.0, nu=0.0, dt=T / 4)
    print(f"\nPropagate quarter orbit (expect nu_f ~ 90 deg):")
    print(f"  nu_f = {math.degrees(r_p['nu_f'].si):.2f} deg")
