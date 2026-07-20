"""
Pressure-tank blowdown through a hole -- "half-life" drain time for a gas.
============================================================================

Problem
-------
A rigid tank of volume V is charged to pressure P0 and temperature T with some
gas species. It has `N` identical circular holes of diameter `d`. How does the
gas drain? In particular:

    * What is the "half-life" of the pressure (time for P to halve)?
    * Mass-flow rate  mdot(t)  from full (choked) tank to atmosphere.
    * Tank pressure   P(t)     through the choked phase and the subsequent
      subsonic, non-linear decay toward ambient.

Physics
-------
Each hole is modelled as a thin orifice / converging nozzle discharging an ideal
gas (de Saint-Venant - Wantzel equation), with a discharge coefficient Cd:

  Critical (choking) pressure ratio (downstream / upstream):
        r_crit = (2 / (gamma + 1)) ** (gamma / (gamma - 1))

  Choked  (P_amb / P  <=  r_crit):     mass flow scales *linearly* with P
        mdot = Cd * A * P * sqrt( gamma/(R*T) ) * (2/(gamma+1))**((gamma+1)/(2(gamma-1)))

  Subsonic (P_amb / P  >  r_crit):     non-linear in P
        mdot = Cd * A * P * sqrt( 2*gamma/((gamma-1)*R*T)
                                  * ( r**(2/gamma) - r**((gamma+1)/gamma) ) ),  r = P_amb/P

The tank is a control volume with mass  m = P*V/(R*T).  Mass balance:
        dm/dt = -mdot

Two thermodynamic closures are provided:
  * adiabatic  (default) -- no wall heat transfer (fast blowdown / sudden
    rupture); the remaining gas cools isentropically, T = T0 (rho/rho0)**(g-1).
    In the CHOKED phase P follows a power law and the *first* half-life is
    analytic:

        tau      = V / (k * R * T)
        t_half   = tau * (2/(g-1)) * ( 2**((g-1)/(2g)) - 1 )

    Half-life is NOT constant here: each successive halving takes longer.
  * isothermal -- tank stays at T (slow blowdown / good wall heat transfer).
    In the CHOKED phase mdot = k*P, so P decays *exponentially* and the
    half-life is CONSTANT and analytic:

        t_half   = tau * ln(2)               (independent of pressure!)

Both hold until the tank unchokes at P_unchoke = P_amb / r_crit, after which
the decay becomes subsonic and non-linear.  Real behaviour lies between the two
closures depending on blowdown speed vs wall heat conduction.

Built entirely on the Anvil framework:
  * gas properties (gamma, R) from anvil.db.fluids   (real tabulated data)
  * the orifice relation registered with @anvil.relation and reused in a System
  * time integration via anvil.solvers.solve_ode  (scipy RK45 + events)
  * plots via anvil.viz sweep + matplotlib

Run
---
    python examples/tank_blowdown.py
    python examples/tank_blowdown.py --species helium --V 0.05 --d 2e-3 --N 3 \
                                     --P0 20e6 --T 300 --model adiabatic
"""

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
