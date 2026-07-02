"""
Anvil Adapter: CoolProp Real-Fluid Thermophysical Properties
============================================================

Wraps CoolProp's ``PropsSI`` high-level interface to compute real-fluid
thermophysical properties (density, enthalpy, specific heat, dynamic
viscosity, speed of sound) for a fluid at a given temperature and pressure.

ADAPTERS PROVIDED:
    coolprop_props  -- rho, h, cp, mu, a  for fluid(T, P)

INSTALLATION (pure pip -- Tier-B eligible):
    pip install CoolProp

VERIFY:
    python -c "import CoolProp; print(CoolProp.__version__)"

REAL ONLY -- NO MOCK MODE:
    This adapter requires the real CoolProp package. Importing this module
    never fails (the CoolProp import is lazy, inside the wrapper), but
    *calling* the adapter without CoolProp installed raises a clear
    ImportError telling you how to install it. There is no analytical /
    mock substitution: when it returns a result, that result came from the
    real CoolProp library.

USAGE:
    from anvil.adapters.coolprop_props import coolprop_props, register

    r = coolprop_props(fluid="Air", T=300.0, P=101325.0)
    print(r["rho"], r["cp"], r["a"], r["source"])

    register()   # push to anvil registry under "thermo.coolprop"
"""

from anvil import Adapter, Q


def coolprop_props_call(fluid="Air", T=300.0, P=101325.0):
    """
    Real-fluid thermophysical properties via CoolProp.PropsSI.

    Parameters arrive as raw SI floats (T [K], P [Pa]) or Q objects.
    Returns a dict of Q-wrapped properties plus a "source" field.

    Requires the real CoolProp package; if it is not installed, raises an
    ImportError with the install command. There is no mock fallback.
    """
    from anvil import Q

    # Coerce Q -> SI float; plain floats are assumed already SI.
    if hasattr(fluid, "value"):
        fluid = str(fluid.value)
    fluid = str(fluid)
    T = float(T.si) if hasattr(T, "si") else float(T)
    P = float(P.si) if hasattr(P, "si") else float(P)

    # --- Real path: CoolProp (lazy import) ----------------------------------
    try:
        import CoolProp.CoolProp as CP
    except ImportError as e:
        raise ImportError(
            "coolprop_props requires the 'CoolProp' package; "
            "install with: pip install CoolProp"
        ) from e

    rho = float(CP.PropsSI("D", "T", T, "P", P, fluid))
    h = float(CP.PropsSI("H", "T", T, "P", P, fluid))
    cp = float(CP.PropsSI("C", "T", T, "P", P, fluid))
    mu = float(CP.PropsSI("V", "T", T, "P", P, fluid))
    a = float(CP.PropsSI("A", "T", T, "P", P, fluid))

    return {
        "rho":    Q(rho, "kg/m^3"),
        "h":      Q(h, "J/kg"),
        "cp":     Q(cp, "J/kg/K"),
        "mu":     Q(mu, "Pa*s"),
        "a":      Q(a, "m/s"),
        "source": "coolprop",
    }


coolprop_props = Adapter(
    "coolprop_props",
    backend="python",
    call=coolprop_props_call,
    inputs={
        "fluid": {"desc": "Fluid name (Air, N2, O2, CO2, H2, CH4, Water, ...)",
                  "default": "Air"},
        "T":     {"unit": "K",  "desc": "Temperature", "default": 300.0},
        "P":     {"unit": "Pa", "desc": "Pressure", "default": 101325.0},
    },
    outputs={
        "rho":    {"unit": "kg/m^3", "desc": "Density"},
        "h":      {"unit": "J/kg",   "desc": "Specific enthalpy"},
        "cp":     {"unit": "J/kg/K", "desc": "Specific heat at constant pressure"},
        "mu":     {"unit": "Pa*s",   "desc": "Dynamic viscosity"},
        "a":      {"unit": "m/s",    "desc": "Speed of sound"},
        "source": {"desc": "coolprop (real library; no mock fallback)"},
    },
    desc="Real-fluid thermophysical properties (rho, h, cp, mu, a) via CoolProp",
    tags=["coolprop", "thermo", "fluid", "properties", "tierB"],
)


def register():
    """Push the CoolProp adapter to the global Anvil registry.

    Registers the self-contained wrapper function (not the closure) so the
    RSQ source round-trips cleanly.
    """
    import anvil
    anvil.push(coolprop_props_call, name="coolprop_props",
               domain="thermo.coolprop",
               description=coolprop_props.desc,
               tags=coolprop_props.tags, overwrite=True)
    print("Registered: coolprop_props  [domain: thermo.coolprop]")


if __name__ == "__main__":
    r = coolprop_props(fluid="Air", T=300.0, P=101325.0)
    for k, v in r.items():
        print(f"  {k}: {v}")
