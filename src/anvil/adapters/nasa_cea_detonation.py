"""
Anvil Adapter: NASA CEA Detonation (Chapman-Jouguet)
=====================================================

Wraps NASA CEA's DetonationSolver for CJ detonation calculations.

UNIT CONVENTION:
    Anvil always passes SI values (Pa, K) to adapter functions.
    This adapter converts Pa → bar internally before calling CEA.

REQUIRES: pip install cea  (NASA CEA >= 3.0)
REAL ONLY -- NO MOCK MODE: if the cea package is not installed, calls raise
ImportError with the install command.

FULL OUTPUT:
    Thermodynamic:    D_CJ, T_CJ, P_CJ, P_ratio, rho_CJ, gamma_CJ, MW_CJ, a_CJ
    Calorific:        cp_CJ, cv_CJ, e_CJ, h_CJ        [J/kg, J/kg/K]
    Transport:        mu_CJ [Pa*s], k_CJ [W/m/K], Pr_CJ [-]
    Velocities:       u_CJ [m/s]  (particle velocity behind detonation front)
    Species:          species_CJ   (dict of mole fractions, e.g. {"H2O": 0.56, ...})
"""

from anvil import Adapter, Q
import numpy as np


# ============================================================
# Internal computation
# ============================================================

def _cea_detonation(fuel="H2", oxidizer="O2", fuel_moles=2.0, ox_moles=1.0,
                     T1=300.0, P1=101325.0, extra_species=None):
    """
    Compute Chapman-Jouguet detonation parameters.

    All inputs arrive as SI units from Anvil workspace:
        T1 [K], P1 [Pa]  — converted to bar internally for CEA
    """
    try:
        import cea as _cea
    except ImportError as exc:
        raise ImportError(
            "NASA CEA is not installed. Install with: pip install cea"
        ) from exc
    return _run_real_cea(_cea, fuel, oxidizer, fuel_moles,
                         ox_moles, T1, P1, extra_species)


def is_available() -> bool:
    """True when the NASA CEA python package can be imported."""
    try:
        import cea  # noqa: F401
        return True
    except ImportError:
        return False


def _run_real_cea(cea, fuel, oxidizer, fuel_moles, ox_moles,
                   T1, P1, extra_species):
    """Real NASA CEA detonation calculation — full output extraction."""

    P1_bar = float(P1) / 1e5
    T1_K   = float(T1)

    species = [fuel, oxidizer]
    fuel_weights = [1.0, 0.0]
    oxidant_weights = [0.0, 1.0]

    if extra_species:
        for sp, mol in extra_species.items():
            species.append(sp)
            fuel_weights.append(0.0)
            oxidant_weights.append(0.0)

    fuel_weights    = np.array(fuel_weights,    dtype=np.float64)
    oxidant_weights = np.array(oxidant_weights, dtype=np.float64)

    reac = cea.Mixture(species)
    prod = cea.Mixture(species, products_from_reactants=True)

    solver   = cea.DetonationSolver(prod, reactants=reac)
    solution = cea.DetonationSolution(solver)

    of_ratio = reac.chem_eq_ratio_to_of_ratio(
        oxidant_weights, fuel_weights,
        float(fuel_moles) / float(ox_moles)
    )
    weights = reac.of_ratio_to_weights(oxidant_weights, fuel_weights, of_ratio)

    if extra_species:
        for i, (sp, mol) in enumerate(extra_species.items()):
            idx = 2 + i
            sp_mix = cea.Mixture([sp])
            sp_mw = sp_mix.moles_to_weights(np.array([1.0]))[0]
            weights[idx] = mol * sp_mw

    solver.solve(solution, weights, T1_K, P1_bar)

    T_CJ   = float(solution.T)
    P_CJ   = float(solution.P) * 1e5   # bar → Pa
    MW_CJ  = float(solution.M) / 1000  # g/mol → kg/mol
    gamma  = float(solution.gamma_s)
    D_CJ   = float(solution.velocity)  # m/s
    a_CJ   = float(solution.sonic_velocity)
    rho_CJ = float(solution.density) * 1e-3  # g/L → kg/m^3

    R_spec = 8314.46 / (MW_CJ * 1000)  # J/(kg·K)
    cp_CJ  = gamma * R_spec / (gamma - 1)
    cv_CJ  = R_spec / (gamma - 1)
    # u_CJ: particle velocity = D - a (CJ condition: flow behind front is sonic)
    u_CJ   = D_CJ - a_CJ

    base = {
        "D_CJ":     Q(D_CJ,   "m/s"),
        "T_CJ":     Q(T_CJ,   "K"),
        "P_CJ":     Q(P_CJ,   "Pa"),
        "P_ratio":  float(solution.P_P1),
        "rho_CJ":   Q(rho_CJ, "kg/m^3"),
        "gamma_CJ": gamma,
        "MW_CJ":    Q(MW_CJ,  "kg/mol"),
        "a_CJ":     Q(a_CJ,   "m/s"),
        "u_CJ":     Q(u_CJ,   "m/s"),
        "cp_CJ":    Q(cp_CJ,  "J/kg/K"),
        "cv_CJ":    Q(cv_CJ,  "J/kg/K"),
        "e_CJ":     Q(cv_CJ * T_CJ, "J/kg"),
        "h_CJ":     Q(cp_CJ * T_CJ, "J/kg"),
    }

    # Transport properties — available in newer CEA versions
    try:
        base["mu_CJ"] = Q(float(solution.viscosity),    "Pa*s")
        base["k_CJ"]  = Q(float(solution.conductivity), "W/m/K")
        base["Pr_CJ"] = float(solution.prandtl)
    except AttributeError:
        # Estimate via Eucken's relation if not in solution object
        mu_est = 2.67e-6 * (MW_CJ * 1000)**0.5 * T_CJ**0.6 / 1e5
        k_est  = mu_est * cp_CJ * (9 * gamma - 5) / (4 * gamma)
        Pr_est = mu_est * cp_CJ / k_est
        base["mu_CJ"] = Q(mu_est, "Pa*s")
        base["k_CJ"]  = Q(k_est,  "W/m/K")
        base["Pr_CJ"] = Pr_est

    # Species mole fractions
    try:
        sp_dict = {}
        for i, sp_name in enumerate(solution.species_names):
            mf = float(solution.mole_fractions[i])
            if mf > 1e-6:
                sp_dict[sp_name] = round(mf, 6)
        base["species_CJ"] = sp_dict
    except AttributeError:
        base["species_CJ"] = {}

    return base


# ============================================================
# Anvil Adapter declaration
# ============================================================

cea_detonation = Adapter(
    "nasa_cea_detonation",
    backend="python",
    call=_cea_detonation,
    inputs={
        "fuel":          {"desc": "Fuel species (H2, CH4, C2H4, C3H8)",    "default": "H2"},
        "oxidizer":      {"desc": "Oxidizer species",                        "default": "O2"},
        "fuel_moles":    {"desc": "Moles of fuel",                           "default": 2.0},
        "ox_moles":      {"desc": "Moles of oxidizer",                       "default": 1.0},
        "T1":            {"unit": "K",  "desc": "Initial temperature [K]"},
        "P1":            {"unit": "Pa", "desc": "Initial pressure [Pa]"},
        "extra_species": {"desc": "Additional species {name: moles}",        "default": None},
    },
    outputs={
        # Core CJ state
        "D_CJ":      {"unit": "m/s",    "desc": "CJ detonation velocity"},
        "T_CJ":      {"unit": "K",      "desc": "CJ temperature"},
        "P_CJ":      {"unit": "Pa",     "desc": "CJ pressure"},
        "P_ratio":   {"desc": "Pressure ratio P_CJ / P1"},
        "rho_CJ":    {"unit": "kg/m^3", "desc": "CJ density"},
        "gamma_CJ":  {"desc": "Isentropic gamma at CJ state"},
        "MW_CJ":     {"unit": "kg/mol", "desc": "Products molecular weight"},
        "a_CJ":      {"unit": "m/s",    "desc": "Speed of sound at CJ state"},
        # Velocities
        "u_CJ":      {"unit": "m/s",    "desc": "Particle velocity behind detonation front"},
        # Thermochemical
        "cp_CJ":     {"unit": "J/kg/K", "desc": "Specific heat at constant pressure"},
        "cv_CJ":     {"unit": "J/kg/K", "desc": "Specific heat at constant volume"},
        "e_CJ":      {"unit": "J/kg",   "desc": "Specific internal energy"},
        "h_CJ":      {"unit": "J/kg",   "desc": "Specific enthalpy"},
        # Transport
        "mu_CJ":     {"unit": "Pa*s",   "desc": "Dynamic viscosity"},
        "k_CJ":      {"unit": "W/m/K",  "desc": "Thermal conductivity"},
        "Pr_CJ":     {"desc": "Prandtl number"},
        # Species
        "species_CJ": {"desc": "Product mole fractions (dict: {species: fraction})"},
    },
    desc="Chapman-Jouguet detonation via NASA CEA (real only; no mock fallback)",
    tags=["detonation", "CJ", "CEA", "combustion", "Chapman-Jouguet"],
)


def register():
    """Register in Anvil registry."""
    import anvil
    anvil.push(cea_detonation, domain="combustion.detonation",
               tags=["CEA", "detonation", "CJ"])


# ============================================================
# Standalone test
# ============================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  NASA CEA Detonation Adapter  —  Full Output Test")
    print("=" * 65)

    try:
        import cea
        print(f"  NASA CEA {cea.__version__} found.\n")
    except ImportError:
        raise SystemExit("  NASA CEA not installed (pip install cea); cannot run test.")

    print("--- H2/O2 stoichiometric (1 atm, 300 K) ---")
    r = cea_detonation.func(fuel="H2", oxidizer="O2",
                             fuel_moles=2.0, ox_moles=1.0,
                             T1=300.0, P1=101325.0)

    core = ["D_CJ", "T_CJ", "P_CJ", "P_ratio", "rho_CJ",
            "gamma_CJ", "a_CJ", "u_CJ"]
    thermo = ["cp_CJ", "cv_CJ", "e_CJ", "h_CJ"]
    transport = ["mu_CJ", "k_CJ", "Pr_CJ"]

    print("\n  Core CJ state:")
    for k in core:
        v = r[k]
        if hasattr(v, "value"):
            print(f"    {k:12s} = {v.value:.4g} {v.unit}")
        else:
            print(f"    {k:12s} = {v:.4g}")

    print("\n  Thermochemical:")
    for k in thermo:
        v = r[k]
        print(f"    {k:12s} = {v.value:.4g} {v.unit}")

    print("\n  Transport:")
    for k in transport:
        v = r[k]
        if hasattr(v, "value"):
            print(f"    {k:12s} = {v.value:.4e} {v.unit}")
        else:
            print(f"    {k:12s} = {v:.4f}")

    print("\n  Product species (mole fractions):")
    for sp, frac in sorted(r["species_CJ"].items(), key=lambda x: -x[1]):
        print(f"    {sp:8s}  {frac:.4f}")

    print("=" * 65)
