"""
Anvil seed library -- fundamental Relations that ship with the framework.

Call seed() to populate the local registry with these built-in RSQs.
This runs automatically on first import if the registry is empty.
Namespace loading is deferred (lazy) to avoid circular imports.
"""

from anvil.registry import _get_store


def seed(force=False):
    """Populate the registry database with built-in RSQs.

    Built-in RSQs are always updated so that source-code fixes (e.g. bug
    fixes in seed.py) take effect immediately without needing force=True.
    User-registered RSQs are never overwritten.
    """
    store = _get_store()
    existing_builtins = {r["name"] for r in store.get_all(origin="builtin")}
    # Always reseed if any entries are missing; always update existing ones
    # so fixes to seed.py propagate on next import.
    if not force and existing_builtins and existing_builtins >= {e["name"] for e in _SEED_ENTRIES}:
        # All present -- check if any source OR metadata has changed
        changed = False
        for entry in _SEED_ENTRIES:
            rec = store.get(entry["name"])
            if rec and rec.get("source") != entry["source"]:
                changed = True
                break
            # Re-seed when latex metadata is added/changed so the UI picks it up.
            existing_latex = (rec.get("metadata") or {}).get("latex", "") if rec else ""
            if rec and existing_latex != entry.get("latex", ""):
                changed = True
                break
        if not changed:
            return
    for entry in _SEED_ENTRIES:
        store.put(
            name=entry["name"], rsq_type=entry["type"], source=entry["source"],
            domain=entry.get("domain", ""), version=entry.get("version", "0.1.0"),
            description=entry.get("desc", ""), tags=entry.get("tags", []),
            depends=entry.get("depends", []), origin="builtin",
            metadata={"latex": entry.get("latex", "")},
        )


_SEED_ENTRIES = [
    # ==================== CONSTANTS ====================
    {"name": "g0", "type": "Q", "domain": "const",
     "desc": "Standard gravitational acceleration", "tags": ["constant", "gravity"],
     "latex": r"g_0 = 9.80665\ \mathrm{m/s^2}",
     "source": 'from anvil import Q\nexport = Q(9.80665, "m/s^2", name="g0")'},
    {"name": "R_universal", "type": "Q", "domain": "const",
     "desc": "Universal gas constant", "tags": ["constant", "gas"],
     "latex": r"R = 8.314462618\ \mathrm{J\,mol^{-1}\,K^{-1}}",
     "source": 'from anvil import Q\nexport = Q(8.314462618, "J/mol/K", name="R_universal")'},
    {"name": "atm_pressure", "type": "Q", "domain": "const",
     "desc": "Standard atmospheric pressure", "tags": ["constant", "atmosphere"],
     "latex": r"P_{atm} = 101325\ \mathrm{Pa}",
     "source": 'from anvil import Q\nexport = Q(101325.0, "Pa", name="atm_pressure")'},
    {"name": "sigma_sb", "type": "Q", "domain": "const",
     "desc": "Stefan-Boltzmann constant", "tags": ["constant", "radiation", "thermal"],
     "latex": r"\sigma = 5.670374419\times10^{-8}\ \mathrm{W\,m^{-2}\,K^{-4}}",
     "source": 'from anvil import Q\nexport = Q(5.670374419e-8, "W", name="sigma_sb")'},

    # ==================== AERO: COMPRESSIBLE ====================
    {"name": "isentropic_ratios", "type": "R", "domain": "aero.compressible",
     "desc": "Isentropic stagnation-to-static ratios from Mach number",
     "tags": ["compressible", "isentropic", "mach"],
     "latex": r"\frac{T_0}{T} = 1 + \tfrac{\gamma-1}{2}M^2,\quad \frac{P_0}{P} = \left(\frac{T_0}{T}\right)^{\frac{\gamma}{\gamma-1}},\quad \frac{\rho_0}{\rho} = \left(\frac{T_0}{T}\right)^{\frac{1}{\gamma-1}}",
     "source": 'def isentropic_ratios(M, gamma=1.4):\n    T_ratio = 1 + ((gamma - 1) / 2) * M**2\n    P_ratio = T_ratio ** (gamma / (gamma - 1))\n    rho_ratio = T_ratio ** (1 / (gamma - 1))\n    return {"T0_T": T_ratio, "P0_P": P_ratio, "rho0_rho": rho_ratio}\nexport = isentropic_ratios'},
    {"name": "area_mach_supersonic", "type": "R", "domain": "aero.compressible",
     "desc": "Supersonic Mach from area ratio (A/A*)", "tags": ["compressible", "nozzle", "mach"],
     "latex": r"\frac{A}{A^*} = \frac{1}{M}\left[\frac{2}{\gamma+1}\left(1+\tfrac{\gamma-1}{2}M^2\right)\right]^{\frac{\gamma+1}{2(\gamma-1)}}",
     "source": 'from anvil import solvers\ndef area_mach_supersonic(area_ratio, gamma=1.4):\n    def residual(M):\n        t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)\n        return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio\n    M = solvers.find_root(residual, bracket=(1.001, 30.0))\n    return {"M_exit": M}\nexport = area_mach_supersonic'},
    {"name": "area_mach_subsonic", "type": "R", "domain": "aero.compressible",
     "desc": "Subsonic Mach from area ratio (A/A*)", "tags": ["compressible", "mach"],
     "latex": r"\frac{A}{A^*} = \frac{1}{M}\left[\frac{2}{\gamma+1}\left(1+\tfrac{\gamma-1}{2}M^2\right)\right]^{\frac{\gamma+1}{2(\gamma-1)}}",
     "source": 'from anvil import solvers\ndef area_mach_subsonic(area_ratio, gamma=1.4):\n    def residual(M):\n        t = (2/(gamma+1))*(1+(gamma-1)/2*M**2)\n        return (1/M)*t**((gamma+1)/(2*(gamma-1))) - area_ratio\n    M = solvers.find_root(residual, bracket=(0.001, 0.999))\n    return {"M_sub": M}\nexport = area_mach_subsonic'},
    {"name": "normal_shock", "type": "R", "domain": "aero.compressible",
     "desc": "Normal shock relations", "tags": ["compressible", "shock"],
     "latex": r"M_2^2 = \frac{1+\tfrac{\gamma-1}{2}M_1^2}{\gamma M_1^2 - \tfrac{\gamma-1}{2}},\quad \frac{P_2}{P_1} = 1 + \frac{2\gamma}{\gamma+1}(M_1^2-1),\quad \frac{\rho_2}{\rho_1} = \frac{(\gamma+1)M_1^2}{2+(\gamma-1)M_1^2}",
     "source": 'def normal_shock(M1, gamma=1.4):\n    M1sq = M1**2\n    M2sq = (1+(gamma-1)/2*M1sq)/(gamma*M1sq-(gamma-1)/2)\n    M2 = M2sq**0.5\n    P2_P1 = 1+2*gamma/(gamma+1)*(M1sq-1)\n    T2_T1 = P2_P1*(2+(gamma-1)*M1sq)/((gamma+1)*M1sq)\n    rho2_rho1 = (gamma+1)*M1sq/(2+(gamma-1)*M1sq)\n    P02_P01 = ((((gamma+1)*M1sq)/(2+(gamma-1)*M1sq))**(gamma/(gamma-1)))*((2*gamma*M1sq-(gamma-1))/(gamma+1))**(-1/(gamma-1))\n    return {"M2":M2,"P2_P1":P2_P1,"T2_T1":T2_T1,"rho2_rho1":rho2_rho1,"P02_P01":P02_P01}\nexport = normal_shock'},
    {"name": "prandtl_meyer", "type": "R", "domain": "aero.compressible",
     "desc": "Prandtl-Meyer expansion angle", "tags": ["compressible", "expansion"],
     "latex": r"\nu(M) = \sqrt{\frac{\gamma+1}{\gamma-1}}\,\arctan\sqrt{\frac{\gamma-1}{\gamma+1}(M^2-1)} - \arctan\sqrt{M^2-1}",
     "source": 'import numpy as np\ndef prandtl_meyer(M, gamma=1.4):\n    g = gamma\n    term = ((g+1)/(g-1))**0.5\n    nu = term*np.arctan(((M**2-1)/((g+1)/(g-1)))**0.5) - np.arctan((M**2-1)**0.5)\n    return {"nu": nu, "nu_deg": np.degrees(nu)}\nexport = prandtl_meyer'},
    {"name": "velocity_from_mach", "type": "R", "domain": "aero.compressible",
     "desc": "Flow velocity from Mach number and speed of sound: V = M * a",
     "tags": ["compressible", "mach", "velocity"],
     "latex": r"V = M\, a",
     "source": 'from anvil import Q\ndef velocity_from_mach(M, a):\n    return {"V": Q(M*a, "m/s")}\nexport = velocity_from_mach'},
    {"name": "stagnation_conditions", "type": "R", "domain": "aero.compressible",
     "desc": "Stagnation temperature and pressure from static conditions and isentropic ratios",
     "tags": ["compressible", "isentropic", "stagnation"],
     "latex": r"T_0 = T\,\frac{T_0}{T},\quad P_0 = P\,\frac{P_0}{P}",
     "source": 'from anvil import Q\ndef stagnation_conditions(T, P, T0_T, P0_P):\n    return {"T0": Q(T*T0_T, "K"), "P0": Q(P*P0_P, "Pa")}\nexport = stagnation_conditions'},
    {"name": "dynamic_pressure", "type": "R", "domain": "aero",
     "desc": "Dynamic pressure: q = 0.5 * rho * V^2", "tags": ["aerodynamics", "pressure"],
     "latex": r"q_\infty = \tfrac{1}{2}\rho V^2",
     "source": 'from anvil import Q\ndef dynamic_pressure(rho, V):\n    return {"q_inf": Q(0.5*rho*V**2, "Pa")}\nexport = dynamic_pressure'},
    {"name": "lift_force", "type": "R", "domain": "aero",
     "desc": "Lift force: L = 0.5 * rho * V^2 * S * CL", "tags": ["aerodynamics", "lift"],
     "latex": r"L = \tfrac{1}{2}\rho V^2 S\, C_L",
     "source": 'from anvil import Q\ndef lift_force(rho, V, S_ref, CL):\n    return {"lift": Q(0.5*rho*V**2*S_ref*CL, "N")}\nexport = lift_force'},
    {"name": "drag_force", "type": "R", "domain": "aero",
     "desc": "Drag force: D = 0.5 * rho * V^2 * S * CD", "tags": ["aerodynamics", "drag"],
     "latex": r"D = \tfrac{1}{2}\rho V^2 S\, C_D",
     "source": 'from anvil import Q\ndef drag_force(rho, V, S_ref, CD):\n    return {"drag": Q(0.5*rho*V**2*S_ref*CD, "N")}\nexport = drag_force'},

    # ==================== PROPULSION ====================
    {"name": "nozzle_area_ratio", "type": "R", "domain": "propulsion",
     "desc": "Exit-to-throat area ratio", "tags": ["nozzle", "geometry"],
     "latex": r"\varepsilon = \frac{A_e}{A_t}",
     "source": 'def nozzle_area_ratio(A_exit, A_throat):\n    return {"area_ratio": A_exit / A_throat}\nexport = nozzle_area_ratio'},
    {"name": "exit_conditions", "type": "R", "domain": "propulsion",
     "desc": "Nozzle exit static conditions", "tags": ["nozzle", "propulsion"],
     "latex": r"T_e = \frac{T_0}{T_0/T},\quad P_e = \frac{P_0}{P_0/P},\quad a_e = \sqrt{\gamma R T_e}",
     "source": 'from anvil import Q\ndef exit_conditions(T0, P0, T0_T, P0_P, gamma, R_gas):\n    T_exit = T0/T0_T\n    P_exit = P0/P0_P\n    a_exit = (gamma*R_gas*T_exit)**0.5\n    return {"T_exit": Q(T_exit,"K"), "P_exit": Q(P_exit,"Pa"), "a_exit": Q(a_exit,"m/s")}\nexport = exit_conditions'},
    {"name": "exit_velocity", "type": "R", "domain": "propulsion",
     "desc": "Exit velocity", "tags": ["nozzle", "velocity"],
     "latex": r"V_e = M_e\, a_e",
     "source": 'from anvil import Q\ndef exit_velocity(M_exit, a_exit):\n    return {"V_exit": Q(M_exit*a_exit, "m/s")}\nexport = exit_velocity'},
    {"name": "choked_mass_flow", "type": "R", "domain": "propulsion",
     "desc": "Mass flow through choked throat", "tags": ["nozzle", "mass_flow"],
     "latex": r"\dot{m} = P_0 A_t \sqrt{\frac{\gamma}{R T_0}}\left(\frac{2}{\gamma+1}\right)^{\frac{\gamma+1}{2(\gamma-1)}}",
     "source": 'from anvil import Q\ndef choked_mass_flow(P0, A_throat, gamma, R_gas, T0):\n    t = (2/(gamma+1))**((gamma+1)/(2*(gamma-1)))\n    mdot = P0*A_throat*(gamma/(R_gas*T0))**0.5*t\n    return {"mdot": Q(mdot, "kg/s")}\nexport = choked_mass_flow'},
    {"name": "rocket_thrust", "type": "R", "domain": "propulsion",
     "desc": "Rocket thrust", "tags": ["propulsion", "thrust"],
     "latex": r"F = \dot{m} V_e + (P_e - P_a) A_e",
     "source": 'from anvil import Q\ndef rocket_thrust(mdot, V_exit, P_exit, P_amb, A_exit):\n    F = mdot*V_exit + (P_exit-P_amb)*A_exit\n    return {"thrust": Q(F, "N")}\nexport = rocket_thrust'},
    {"name": "specific_impulse", "type": "R", "domain": "propulsion",
     "desc": "Specific impulse", "tags": ["propulsion", "isp"],
     "latex": r"I_{sp} = \frac{F}{\dot{m}\, g_0}",
     "source": 'from anvil import Q\ndef specific_impulse(thrust, mdot):\n    return {"Isp": Q(thrust/(mdot*9.80665), "s")}\nexport = specific_impulse'},
    {"name": "tsiolkovsky", "type": "R", "domain": "propulsion",
     "desc": "Tsiolkovsky rocket equation: dV = Isp * g0 * ln(m0/mf)",
     "tags": ["propulsion", "rocket", "delta_v"],
     "latex": r"\Delta V = I_{sp}\, g_0 \ln\!\left(\frac{m_0}{m_f}\right)",
     "source": 'import numpy as np\nfrom anvil import Q\ndef tsiolkovsky(Isp, mass_ratio):\n    dv = Isp * 9.80665 * np.log(mass_ratio)\n    return {"delta_v": Q(dv, "m/s")}\nexport = tsiolkovsky'},

    # ==================== PROPULSION: NOZZLE SYSTEM ====================
    {"name": "rocket_nozzle", "type": "S", "domain": "propulsion",
     "desc": "Quasi-1D isentropic rocket nozzle with thrust and Isp",
     "tags": ["nozzle", "propulsion", "rocket", "system"],
     "depends": ["nozzle_area_ratio", "area_mach_supersonic", "isentropic_ratios",
                  "exit_conditions", "exit_velocity", "choked_mass_flow",
                  "rocket_thrust", "specific_impulse"],
     "source": 'from anvil import Q, System\ndef build():\n    s = System("rocket_nozzle")\n    s.add("P0", 6.9e6, "Pa", desc="Chamber pressure")\n    s.add("T0", 3500, "K", desc="Chamber temperature")\n    s.add("gamma", 1.25, desc="Ratio of specific heats")\n    s.add("R_gas", 320, "J/kg/K", desc="Specific gas constant")\n    s.add("A_throat", 0.01, "m^2", desc="Throat area")\n    s.add("A_exit", 0.08, "m^2", desc="Exit area")\n    s.add("P_amb", 101325, "Pa", desc="Ambient pressure")\n    s.use("nozzle_area_ratio")\n    s.use("area_mach_supersonic")\n    s.use("isentropic_ratios", map={"M": "M_exit"})\n    s.use("exit_conditions")\n    s.use("exit_velocity")\n    s.use("choked_mass_flow")\n    s.use("rocket_thrust")\n    s.use("specific_impulse")\n    return s\nexport = build'},

    # ==================== THERMODYNAMICS ====================
    {"name": "ideal_gas_density", "type": "R", "domain": "thermo",
     "desc": "Ideal gas density: rho = P / (R * T)", "tags": ["thermodynamics", "density"],
     "latex": r"\rho = \frac{P}{R T}",
     "source": 'from anvil import Q\ndef ideal_gas_density(P, R_gas, T):\n    return {"rho": Q(P/(R_gas*T), "kg/m^3")}\nexport = ideal_gas_density'},
    {"name": "speed_of_sound", "type": "R", "domain": "thermo",
     "desc": "Speed of sound in ideal gas", "tags": ["thermodynamics", "acoustics"],
     "latex": r"a = \sqrt{\gamma R T}",
     "source": 'from anvil import Q\ndef speed_of_sound(gamma, R_gas, T):\n    return {"a": Q((gamma*R_gas*T)**0.5, "m/s")}\nexport = speed_of_sound'},
    {"name": "sutherland_viscosity", "type": "R", "domain": "thermo",
     "desc": "Sutherland's law for dynamic viscosity of a gas",
     "tags": ["thermodynamics", "viscosity", "transport"],
     "latex": r"\mu = \mu_{ref}\left(\frac{T}{T_{ref}}\right)^{3/2}\frac{T_{ref}+S}{T+S}",
     "source": 'from anvil import Q\ndef sutherland_viscosity(T, T_ref=288.15, mu_ref=1.789e-5, S=110.4):\n    mu = mu_ref * (T/T_ref)**1.5 * (T_ref + S) / (T + S)\n    return {"mu": Q(mu, "Pa*s")}\nexport = sutherland_viscosity'},
    {"name": "reynolds_number", "type": "R", "domain": "thermo",
     "desc": "Reynolds number: Re = rho * V * L / mu",
     "tags": ["fluid", "dimensionless", "reynolds"],
     "latex": r"Re = \frac{\rho V L}{\mu}",
     "source": 'def reynolds_number(rho, V, L_char, mu):\n    return {"Re": rho * V * L_char / mu}\nexport = reynolds_number'},

    # ==================== HEAT TRANSFER ====================
    {"name": "conduction_1d", "type": "R", "domain": "heat_transfer",
     "desc": "1D steady conduction: Q = k * A * dT / L",
     "tags": ["heat_transfer", "conduction", "fourier"],
     "latex": r"\dot{Q} = \frac{k A\, \Delta T}{L}",
     "source": 'from anvil import Q\ndef conduction_1d(k, A_cross, dT, L_thickness):\n    Q_dot = k * A_cross * dT / L_thickness\n    return {"Q_cond": Q(Q_dot, "W")}\nexport = conduction_1d'},
    {"name": "convection", "type": "R", "domain": "heat_transfer",
     "desc": "Newton's law of cooling: Q = h * A * (T_s - T_inf)",
     "tags": ["heat_transfer", "convection", "newton"],
     "latex": r"\dot{Q} = h A\,(T_s - T_\infty)",
     "source": 'from anvil import Q\ndef convection(h_conv, A_surf, T_surf, T_inf):\n    Q_dot = h_conv * A_surf * (T_surf - T_inf)\n    return {"Q_conv": Q(Q_dot, "W")}\nexport = convection'},
    {"name": "radiation", "type": "R", "domain": "heat_transfer",
     "desc": "Radiation heat transfer: Q = eps * sigma * A * (T1^4 - T2^4)",
     "tags": ["heat_transfer", "radiation", "stefan_boltzmann"],
     "latex": r"\dot{Q} = \varepsilon \sigma A\,(T_h^4 - T_c^4)",
     "source": 'from anvil import Q\ndef radiation(emissivity, A_surf, T_hot, T_cold):\n    sigma = 5.670374419e-8\n    Q_dot = emissivity * sigma * A_surf * (T_hot**4 - T_cold**4)\n    return {"Q_rad": Q(Q_dot, "W")}\nexport = radiation'},
    {"name": "thermal_resistance_wall", "type": "R", "domain": "heat_transfer",
     "desc": "Thermal resistance of a plane wall: R = L / (k * A)",
     "tags": ["heat_transfer", "resistance", "conduction"],
     "latex": r"R_{th} = \frac{L}{k A}",
     "source": 'def thermal_resistance_wall(L_thickness, k, A_cross):\n    return {"R_thermal": L_thickness / (k * A_cross)}\nexport = thermal_resistance_wall'},
    {"name": "hx_heat_rate", "type": "R", "domain": "heat_transfer",
     "desc": "Heat-exchanger transfer rate from UA and mean temperature difference (couples with hx_cold_out)",
     "tags": ["heat_transfer", "heat_exchanger", "coupled"],
     "latex": r"\dot{Q} = UA\,\frac{T_{h,in} - T_{c,out}}{2}",
     "source": 'from anvil import Q\ndef hx_heat_rate(UA, T_hot_in, T_cold_out):\n    Q_dot = UA * (T_hot_in - T_cold_out) * 0.5\n    return {"Q_dot": Q(Q_dot, "W")}\nexport = hx_heat_rate'},
    {"name": "hx_hot_out", "type": "R", "domain": "heat_transfer",
     "desc": "Hot-side outlet temperature from an energy balance",
     "tags": ["heat_transfer", "heat_exchanger", "energy_balance"],
     "latex": r"T_{h,out} = T_{h,in} - \frac{\dot{Q}}{\dot{m}_h c_{p,h}}",
     "source": 'from anvil import Q\ndef hx_hot_out(T_hot_in, Q_dot, mdot_hot, Cp_hot):\n    return {"T_hot_out": Q(T_hot_in - Q_dot/(mdot_hot*Cp_hot), "K")}\nexport = hx_hot_out'},
    {"name": "hx_cold_out", "type": "R", "domain": "heat_transfer",
     "desc": "Cold-side outlet temperature from an energy balance (couples with hx_heat_rate)",
     "tags": ["heat_transfer", "heat_exchanger", "energy_balance", "coupled"],
     "latex": r"T_{c,out} = T_{c,in} + \frac{\dot{Q}}{\dot{m}_c c_{p,c}}",
     "source": 'from anvil import Q\ndef hx_cold_out(T_cold_in, Q_dot, mdot_cold, Cp_cold):\n    return {"T_cold_out": Q(T_cold_in + Q_dot/(mdot_cold*Cp_cold), "K")}\nexport = hx_cold_out'},
    {"name": "hx_effectiveness", "type": "R", "domain": "heat_transfer",
     "desc": "Heat-exchanger effectiveness: actual over maximum possible temperature drop",
     "tags": ["heat_transfer", "heat_exchanger", "effectiveness"],
     "latex": r"\varepsilon = \frac{T_{h,in} - T_{h,out}}{T_{h,in} - T_{c,in}}",
     "source": 'def hx_effectiveness(T_hot_in, T_hot_out, T_cold_in):\n    eps = (T_hot_in - T_hot_out) / (T_hot_in - T_cold_in + 1e-10)\n    return {"effectiveness": eps}\nexport = hx_effectiveness'},
    {"name": "fin_efficiency_rect", "type": "R", "domain": "heat_transfer",
     "desc": "Rectangular fin efficiency: eta = tanh(mL) / (mL)",
     "tags": ["heat_transfer", "fin", "extended_surface"],
     "latex": r"\eta_{fin} = \frac{\tanh(mL)}{mL},\quad m = \sqrt{\frac{hP}{k A_c}}",
     "source": 'import numpy as np\ndef fin_efficiency_rect(h_conv, k_fin, t_fin, L_fin):\n    P = 2 * (1 + t_fin)  # perimeter per unit depth (approx for wide fin)\n    Ac = t_fin * 1  # cross section per unit depth\n    m = (h_conv * P / (k_fin * Ac))**0.5\n    mL = m * L_fin\n    eta = np.tanh(mL) / mL if mL > 0.01 else 1.0\n    return {"eta_fin": eta, "mL": mL}\nexport = fin_efficiency_rect'},

    # ==================== STRUCTURES ====================
    {"name": "hooke_stress", "type": "R", "domain": "structures",
     "desc": "Hooke's law: stress = E * strain", "tags": ["structures", "stress", "elastic"],
     "latex": r"\sigma = E\, \epsilon",
     "source": 'from anvil import Q\ndef hooke_stress(E, strain):\n    return {"stress": Q(E * strain, "Pa")}\nexport = hooke_stress'},
    {"name": "axial_stress", "type": "R", "domain": "structures",
     "desc": "Axial stress: sigma = F / A", "tags": ["structures", "stress", "axial"],
     "latex": r"\sigma = \frac{F}{A}",
     "source": 'from anvil import Q\ndef axial_stress(F_axial, A_cross):\n    return {"sigma_axial": Q(F_axial / A_cross, "Pa")}\nexport = axial_stress'},
    {"name": "beam_deflection_cantilever", "type": "R", "domain": "structures",
     "desc": "Cantilever beam tip deflection under point load: delta = F*L^3 / (3*E*I)",
     "tags": ["structures", "beam", "deflection", "cantilever"],
     "latex": r"\delta = \frac{F L^3}{3 E I}",
     "source": 'from anvil import Q\ndef beam_deflection_cantilever(F_tip, L_beam, E, I_moment):\n    delta = F_tip * L_beam**3 / (3 * E * I_moment)\n    return {"deflection": Q(delta, "m"), "max_moment": Q(F_tip * L_beam, "N*m")}\nexport = beam_deflection_cantilever'},
    {"name": "beam_deflection_simply_supported", "type": "R", "domain": "structures",
     "desc": "Simply supported beam center deflection under uniform load: delta = 5*w*L^4 / (384*E*I)",
     "tags": ["structures", "beam", "deflection"],
     "latex": r"\delta = \frac{5 w L^4}{384 E I}",
     "source": 'from anvil import Q\ndef beam_deflection_simply_supported(w_load, L_beam, E, I_moment):\n    delta = 5 * w_load * L_beam**4 / (384 * E * I_moment)\n    max_M = w_load * L_beam**2 / 8\n    return {"deflection": Q(delta, "m"), "max_moment": Q(max_M, "N*m")}\nexport = beam_deflection_simply_supported'},
    {"name": "buckling_euler", "type": "R", "domain": "structures",
     "desc": "Euler buckling critical load: Pcr = pi^2 * E * I / L_eff^2",
     "tags": ["structures", "buckling", "stability"],
     "latex": r"P_{cr} = \frac{\pi^2 E I}{L_{eff}^2}",
     "source": 'import numpy as np\nfrom anvil import Q\ndef buckling_euler(E, I_moment, L_eff):\n    Pcr = np.pi**2 * E * I_moment / L_eff**2\n    return {"P_critical": Q(Pcr, "N")}\nexport = buckling_euler'},
    {"name": "thin_wall_hoop_stress", "type": "R", "domain": "structures",
     "desc": "Hoop stress in thin-walled pressure vessel: sigma = P*r/t",
     "tags": ["structures", "pressure_vessel", "hoop"],
     "latex": r"\sigma_\theta = \frac{P r}{t},\quad \sigma_a = \frac{P r}{2 t}",
     "source": 'from anvil import Q\ndef thin_wall_hoop_stress(P_internal, r_inner, t_wall):\n    sigma_h = P_internal * r_inner / t_wall\n    sigma_a = P_internal * r_inner / (2 * t_wall)\n    return {"sigma_hoop": Q(sigma_h, "Pa"), "sigma_axial": Q(sigma_a, "Pa")}\nexport = thin_wall_hoop_stress'},

    # ==================== AERO: OBLIQUE SHOCK ====================
    {"name": "oblique_shock", "type": "R", "domain": "aero.compressible",
     "desc": "2D oblique shock: shock angle, downstream M, pressure/temperature ratios",
     "tags": ["compressible", "shock", "oblique", "wedge"],
     "source": (
         'import numpy as np\nfrom anvil import solvers\n'
         'def oblique_shock(M1, theta_deg, gamma=1.4):\n'
         '    """Oblique shock: weak (attached) solution for wedge half-angle theta_deg.\n'
         '    The theta-beta-M function starts at 0 (at Mach angle mu), rises to a\n'
         '    maximum deflection, then falls back to 0 at beta=90. Both endpoints are\n'
         '    below theta for attached shocks, so we sample to find the sign-change\n'
         '    bracket near the weak-shock crossing.\n'
         '    """\n'
         '    theta = _rad(theta_deg)\n'
         '    mu = np.arcsin(1.0 / M1)\n'
         '    def tbm(beta):\n'
         '        sb2 = np.sin(beta)**2\n'
         '        num = M1**2 * sb2 - 1.0\n'
         '        den = M1**2 * (gamma + np.cos(2.0*beta)) + 2.0\n'
         '        tb  = abs(np.tan(beta))\n'
         '        if tb < 1e-14: return 0.0\n'
         '        return np.arctan(2.0 / tb * num / den)\n'
         '    betas = np.linspace(mu + 0.001, np.pi/2 - 0.001, 500)\n'
         '    vals  = np.array([tbm(b) for b in betas])\n'
         '    if vals.max() <= theta:\n'
         '        return {"beta_deg": float("nan"), "M2": float("nan"),\n'
         '                "p2_p1": float("nan"), "T2_T1": float("nan"),\n'
         '                "rho2_rho1": float("nan"), "attached": False}\n'
         '    resid = vals - theta\n'
         '    # Weak shock: first upward crossing (vals rising through theta)\n'
         '    cross = np.where((resid[:-1] < 0) & (resid[1:] >= 0))[0]\n'
         '    if len(cross) == 0:\n'
         '        cross = np.where((resid[:-1] >= 0) & (resid[1:] < 0))[0]\n'
         '    if len(cross) == 0:\n'
         '        return {"beta_deg": float("nan"), "M2": float("nan"),\n'
         '                "p2_p1": float("nan"), "T2_T1": float("nan"),\n'
         '                "rho2_rho1": float("nan"), "attached": False}\n'
         '    idx = int(cross[0])\n'
         '    beta = solvers.find_root(lambda b: tbm(b) - theta,\n'
         '                            bracket=(float(betas[idx]), float(betas[idx+1])),\n'
         '                            method="brent", tol=1e-12)\n'
         '    M1n       = M1 * np.sin(beta)\n'
         '    M2n2      = (1+(gamma-1)/2*M1n**2) / (gamma*M1n**2-(gamma-1)/2)\n'
         '    M2        = np.sqrt(max(M2n2, 0.0)) / np.sin(beta - theta)\n'
         '    p2_p1     = 1 + 2*gamma/(gamma+1)*(M1n**2 - 1)\n'
         '    T2_T1     = p2_p1*(2+(gamma-1)*M1n**2) / ((gamma+1)*M1n**2)\n'
         '    rho2_rho1 = (gamma+1)*M1n**2 / (2+(gamma-1)*M1n**2)\n'
         '    return {"beta_deg": float(np.degrees(beta)), "M2": float(M2),\n'
         '            "p2_p1": float(p2_p1), "T2_T1": float(T2_T1),\n'
         '            "rho2_rho1": float(rho2_rho1), "attached": True}\n'
         'export = oblique_shock'
     )},

    # ==================== ORBITAL MECHANICS ====================
    {"name": "vis_viva", "type": "R", "domain": "orbital",
     "desc": "Vis-viva equation: V = sqrt(mu * (2/r - 1/a))",
     "tags": ["orbital", "velocity", "kepler"],
     "latex": r"V = \sqrt{\mu\left(\frac{2}{r} - \frac{1}{a}\right)}",
     "source": 'from anvil import Q\ndef vis_viva(mu, r, a):\n    V = (mu*(2/r - 1/a))**0.5\n    return {"V_orbital": Q(V, "m/s")}\nexport = vis_viva'},
    {"name": "hohmann_transfer", "type": "R", "domain": "orbital",
     "desc": "Hohmann transfer delta-V between two circular orbits",
     "tags": ["orbital", "transfer", "hohmann", "delta_v"],
     "latex": r"\Delta V = \left|\sqrt{\mu\!\left(\tfrac{2}{r_1}-\tfrac{1}{a_t}\right)} - \sqrt{\tfrac{\mu}{r_1}}\right| + \left|\sqrt{\tfrac{\mu}{r_2}} - \sqrt{\mu\!\left(\tfrac{2}{r_2}-\tfrac{1}{a_t}\right)}\right|,\ a_t=\tfrac{r_1+r_2}{2}",
     "source": 'import numpy as np\nfrom anvil import Q\ndef hohmann_transfer(mu, r1, r2):\n    a_t = (r1 + r2) / 2\n    v1 = (mu / r1)**0.5\n    v2 = (mu / r2)**0.5\n    v_t1 = (mu * (2/r1 - 1/a_t))**0.5\n    v_t2 = (mu * (2/r2 - 1/a_t))**0.5\n    dv1 = abs(v_t1 - v1)\n    dv2 = abs(v2 - v_t2)\n    return {"dv1": Q(dv1, "m/s"), "dv2": Q(dv2, "m/s"), "dv_total": Q(dv1+dv2, "m/s"), "tof": Q(np.pi*(a_t**3/mu)**0.5, "s")}\nexport = hohmann_transfer'},
    {"name": "orbital_period", "type": "R", "domain": "orbital",
     "desc": "Orbital period: T = 2*pi*sqrt(a^3/mu)",
     "tags": ["orbital", "period", "kepler"],
     "latex": r"T = 2\pi\sqrt{\frac{a^3}{\mu}}",
     "source": 'import numpy as np\nfrom anvil import Q\ndef orbital_period(mu, a):\n    T = 2*np.pi*(a**3/mu)**0.5\n    return {"T_orbital": Q(T, "s")}\nexport = orbital_period'},

    # ==================== AERODYNAMICS: ATMOSPHERE ====================
    {"name": "isa_atmosphere", "type": "R", "domain": "aero.atmosphere",
     "desc": "International Standard Atmosphere (ISA) up to 86 km",
     "tags": ["atmosphere", "ISA", "altitude", "aerodynamics"],
     "source": (
         'import numpy as np\nfrom anvil import Q\n'
         'def isa_atmosphere(h):\n'
         '    """ISA atmosphere. h in meters. Troposphere 0-11km, Stratosphere 11-20km."""\n'
         '    T0, P0, rho0 = 288.15, 101325.0, 1.225\n'
         '    g0, R_air = 9.80665, 287.058\n'
         '    if h <= 11000:\n'
         '        T = T0 - 0.0065 * h\n'
         '        P = P0 * (T / T0) ** (g0 / (0.0065 * R_air))\n'
         '    elif h <= 20000:\n'
         '        T11 = 216.65\n'
         '        P11 = 101325.0 * (216.65 / 288.15) ** (g0 / (0.0065 * R_air))\n'
         '        T = T11\n'
         '        P = P11 * np.exp(-g0 * (h - 11000) / (R_air * T11))\n'
         '    elif h <= 32000:\n'
         '        T20 = 216.65\n'
         '        P20 = 5474.89\n'
         '        T = T20 + 0.001 * (h - 20000)\n'
         '        P = P20 * (T / T20) ** (-g0 / (0.001 * R_air))\n'
         '    else:\n'
         '        T = 228.65 + 0.0028 * (h - 32000) if h <= 47000 else 270.65\n'
         '        P = 868.019 * np.exp(-g0 * (h - 32000) / (R_air * 228.65)) if h <= 47000 else 110.906\n'
         '    rho = P / (R_air * T)\n'
         '    a = (1.4 * R_air * T) ** 0.5\n'
         '    mu = 1.458e-6 * T**1.5 / (T + 110.4)\n'
         '    return {"T_atm": Q(T, "K"), "P_atm": Q(P, "Pa"), "rho_atm": Q(rho, "kg/m^3"),\n'
         '            "a_atm": Q(a, "m/s"), "mu_atm": Q(mu, "Pa*s"),\n'
         '            "sigma": rho / 1.225}\n'
         'export = isa_atmosphere'
     )},

    # ==================== AERODYNAMICS: LIFT & DRAG ====================
    {"name": "thin_airfoil_cl", "type": "R", "domain": "aero",
     "desc": "Thin airfoil theory: CL = 2*pi*(alpha + alpha_L0); M correction via Prandtl-Glauert",
     "tags": ["aerodynamics", "lift", "thin_airfoil", "subsonic"],
     "latex": r"C_L = \frac{2\pi(\alpha - \alpha_{L0})}{\sqrt{1-M^2}}",
     "source": (
         'import numpy as np\n'
         'def thin_airfoil_cl(alpha_deg, alpha_L0_deg=0.0, M=0.0):\n'
         '    """Thin airfoil CL with optional Prandtl-Glauert compressibility correction."""\n'
         '    alpha = _rad(alpha_deg)\n'
         '    alpha_L0 = _rad(alpha_L0_deg)\n'
         '    CL_inc = 2 * np.pi * (alpha - alpha_L0)\n'
         '    beta = max((1 - min(M, 0.7)**2)**0.5, 0.1)\n'
         '    CL = CL_inc / beta\n'
         '    return {"CL": CL, "CL_alpha": 2 * np.pi / beta}\n'
         'export = thin_airfoil_cl'
     )},
    {"name": "induced_drag", "type": "R", "domain": "aero",
     "desc": "Induced drag: CDi = CL^2 / (pi * e * AR)",
     "tags": ["aerodynamics", "drag", "induced", "lifting_line"],
     "latex": r"C_{D_i} = \frac{C_L^2}{\pi e\, AR}",
     "source": (
         'import numpy as np\n'
         'def induced_drag(CL, AR, e=0.85):\n'
         '    """Lifting-line induced drag. e = Oswald efficiency (0.7-0.9 typical)."""\n'
         '    CDi = CL**2 / (np.pi * e * AR)\n'
         '    return {"CDi": CDi}\n'
         'export = induced_drag'
     )},
    {"name": "drag_polar", "type": "R", "domain": "aero",
     "desc": "Parabolic drag polar: CD = CD0 + CL^2/(pi*e*AR)",
     "tags": ["aerodynamics", "drag", "polar"],
     "latex": r"C_D = C_{D_0} + \frac{C_L^2}{\pi e\, AR}",
     "source": (
         'import numpy as np\n'
         'def drag_polar(CL, CD0, AR, e=0.85):\n'
         '    CDi = CL**2 / (np.pi * e * AR)\n'
         '    CD = CD0 + CDi\n'
         '    LoD = CL / CD if CD > 0 else 0\n'
         '    return {"CD": CD, "CDi": CDi, "LoD": LoD}\n'
         'export = drag_polar'
     )},
    {"name": "oswald_efficiency", "type": "R", "domain": "aero",
     "desc": "Oswald span efficiency estimate from aspect ratio (empirical)",
     "tags": ["aerodynamics", "oswald", "efficiency", "wing"],
     "latex": r"e = 1.78\left(1 - 0.045\, AR^{0.68}\right) - 0.64",
     "source": (
         'import numpy as np\n'
         'def oswald_efficiency(AR, sweep_deg=0.0, taper=1.0):\n'
         '    """Raymer/Hoak empirical fit for Oswald efficiency factor."""\n'
         '    sweep_rad = _rad(sweep_deg)\n'
         '    e = 1.78 * (1 - 0.045 * AR**0.68) - 0.64\n'
         '    e = max(0.5, min(e, 1.0))\n'
         '    return {"e_oswald": e}\n'
         'export = oswald_efficiency'
     )},
    {"name": "stall_speed", "type": "R", "domain": "aero",
     "desc": "Aircraft stall speed: Vs = sqrt(2*W/(rho*S*CLmax))",
     "tags": ["aerodynamics", "stall", "speed", "performance"],
     "latex": r"V_s = \sqrt{\frac{2W}{\rho S\, C_{L,max}}}",
     "source": (
         'from anvil import Q\n'
         'def stall_speed(W, rho, S_ref, CLmax):\n'
         '    """W: weight [N], rho: air density [kg/m^3], S_ref: wing area [m^2]."""\n'
         '    Vs = (2 * W / (rho * S_ref * CLmax)) ** 0.5\n'
         '    return {"V_stall": Q(Vs, "m/s")}\n'
         'export = stall_speed'
     )},
    {"name": "range_breguet", "type": "R", "domain": "aero.performance",
     "desc": "Breguet range equation for jet aircraft",
     "tags": ["aerodynamics", "range", "breguet", "performance"],
     "latex": r"R = \frac{V}{c_T}\,\frac{L}{D}\ln\!\left(\frac{W_i}{W_f}\right)",
     "source": (
         'import numpy as np\nfrom anvil import Q\n'
         'def range_breguet(V, TSFC, LoD, W_initial, W_final):\n'
         '    """V [m/s], TSFC [1/s = kg/N/s], LoD = L/D, weights in N."""\n'
         '    R = (V / TSFC) * LoD * np.log(W_initial / W_final)\n'
         '    return {"range": Q(R, "m"), "range_km": Q(R / 1000, "km")}\n'
         'export = range_breguet'
     )},

    # ==================== CONTROLS ====================
    {"name": "pid_output", "type": "R", "domain": "controls",
     "desc": "PID controller output: u = Kp*e + Ki*integral(e) + Kd*de/dt",
     "tags": ["controls", "PID", "controller"],
     "latex": r"u = K_p e + K_i \int e\,dt + K_d \frac{de}{dt}",
     "source": (
         'def pid_output(error, integral_error, derivative_error, Kp, Ki, Kd):\n'
         '    """PID control law. Provide pre-computed integral and derivative of error."""\n'
         '    u = Kp * error + Ki * integral_error + Kd * derivative_error\n'
         '    return {"u_pid": u}\n'
         'export = pid_output'
     )},
    {"name": "ziegler_nichols_pid", "type": "R", "domain": "controls",
     "desc": "Ziegler-Nichols PID tuning from ultimate gain and period",
     "tags": ["controls", "PID", "tuning", "ziegler_nichols"],
     "source": (
         'def ziegler_nichols_pid(Ku, Tu, method="classic"):\n'
         '    """Compute Kp, Ki, Kd from ultimate gain Ku and period Tu."""\n'
         '    if method == "classic":\n'
         '        Kp = 0.6 * Ku\n'
         '        Ti = 0.5 * Tu\n'
         '        Td = 0.125 * Tu\n'
         '    elif method == "PI":\n'
         '        Kp = 0.45 * Ku; Ti = 0.833 * Tu; Td = 0.0\n'
         '    elif method == "PD":\n'
         '        Kp = 0.8 * Ku; Ti = 1e12; Td = 0.1 * Tu\n'
         '    else:\n'
         '        Kp = 0.6 * Ku; Ti = 0.5 * Tu; Td = 0.125 * Tu\n'
         '    Ki = Kp / Ti if Ti > 0 else 0\n'
         '    Kd = Kp * Td\n'
         '    return {"Kp": Kp, "Ki": Ki, "Kd": Kd, "Ti": Ti, "Td": Td}\n'
         'export = ziegler_nichols_pid'
     )},
    {"name": "first_order_step", "type": "R", "domain": "controls",
     "desc": "First-order system step response: y(t) = K*(1-exp(-t/tau))",
     "tags": ["controls", "first_order", "step_response", "dynamics"],
     "latex": r"y(t) = K\left(1 - e^{-t/\tau}\right)",
     "source": (
         'import numpy as np\n'
         'def first_order_step(K, tau, t_settle_criterion=0.02):\n'
         '    """K: DC gain, tau: time constant. Returns settling time for 2% criterion."""\n'
         '    t_settle = -tau * np.log(t_settle_criterion)\n'
         '    rise_time = 2.2 * tau\n'
         '    return {"t_settle": t_settle, "t_rise": rise_time,\n'
         '            "bandwidth_Hz": 1 / (2 * np.pi * tau)}\n'
         'export = first_order_step'
     )},
    {"name": "second_order_metrics", "type": "R", "domain": "controls",
     "desc": "Second-order system metrics from natural frequency and damping ratio",
     "tags": ["controls", "second_order", "damping", "natural_frequency"],
     "latex": r"M_p = e^{-\pi\zeta/\sqrt{1-\zeta^2}},\quad \omega_d = \omega_n\sqrt{1-\zeta^2},\quad t_s \approx \frac{4}{\zeta\omega_n}",
     "source": (
         'import numpy as np\n'
         'def second_order_metrics(omega_n, zeta):\n'
         '    """omega_n [rad/s], zeta = damping ratio. Returns step response metrics."""\n'
         '    if zeta >= 1.0:\n'
         '        t_settle = 4.0 / (zeta * omega_n)\n'
         '        overshoot = 0.0\n'
         '        t_peak = float("inf")\n'
         '    else:\n'
         '        omega_d = omega_n * (1 - zeta**2)**0.5\n'
         '        overshoot = np.exp(-np.pi * zeta / (1 - zeta**2)**0.5) * 100\n'
         '        t_peak = np.pi / omega_d\n'
         '        t_settle = 4.0 / (zeta * omega_n)\n'
         '    t_rise = (1 - 0.4167 * zeta + 2.917 * zeta**2) / omega_n\n'
         '    omega_d_out = omega_n * (1 - zeta**2)**0.5 if zeta < 1.0 else 0.0\n'
         '    return {"overshoot_pct": overshoot, "t_peak": t_peak,\n'
         '            "t_settle": t_settle, "t_rise": t_rise,\n'
         '            "omega_d": omega_d_out}\n'
         'export = second_order_metrics'
     )},
    {"name": "routh_hurwitz_2nd", "type": "R", "domain": "controls",
     "desc": "Stability check for 2nd-order characteristic polynomial: s^2 + a1*s + a0",
     "tags": ["controls", "stability", "routh_hurwitz"],
     "latex": r"s^2 + a_1 s + a_0 \ \text{stable} \iff a_1 > 0 \ \wedge\ a_0 > 0",
     "source": (
         'def routh_hurwitz_2nd(a1, a0):\n'
         '    """All coefficients must be positive for stability."""\n'
         '    stable = (a1 > 0) and (a0 > 0)\n'
         '    return {"stable": stable, "a1": a1, "a0": a0}\n'
         'export = routh_hurwitz_2nd'
     )},

    # ==================== MATERIALS ====================
    {"name": "safety_factor", "type": "R", "domain": "materials",
     "desc": "Safety factor and margin of safety",
     "tags": ["materials", "safety", "stress", "design"],
     "latex": r"\mathrm{SF} = \frac{\sigma_{allow}}{\sigma_{applied}},\quad \mathrm{MS} = \mathrm{SF} - 1",
     "source": (
         'def safety_factor(allowable_stress, applied_stress):\n'
         '    SF = allowable_stress / applied_stress if applied_stress != 0 else float("inf")\n'
         '    MS = SF - 1\n'
         '    return {"safety_factor": SF, "margin_of_safety": MS, "pass": SF >= 1.0}\n'
         'export = safety_factor'
     )},
    {"name": "thermal_expansion_stress", "type": "R", "domain": "materials",
     "desc": "Thermal stress in fully constrained member: sigma = E * alpha * dT",
     "tags": ["materials", "thermal", "stress", "expansion"],
     "latex": r"\sigma = E\, \alpha\, \Delta T",
     "source": (
         'from anvil import Q\n'
         'def thermal_expansion_stress(E, alpha_thermal, dT):\n'
         '    """E [Pa], alpha_thermal [1/K], dT [K]. Fully constrained."""\n'
         '    sigma = E * alpha_thermal * dT\n'
         '    return {"sigma_thermal": Q(sigma, "Pa")}\n'
         'export = thermal_expansion_stress'
     )},
    {"name": "fatigue_life_basquin", "type": "R", "domain": "materials",
     "desc": "Basquin S-N fatigue life: N = (sigma_f / sigma_a)^(1/b)",
     "tags": ["materials", "fatigue", "SN_curve", "basquin"],
     "latex": r"N = \tfrac{1}{2}\left(\frac{\sigma_a}{\sigma_f'}\right)^{1/b}",
     "source": (
         'def fatigue_life_basquin(sigma_a, sigma_f_prime, b_exponent):\n'
         '    """sigma_a: stress amplitude, sigma_f\': fatigue strength coefficient,\n'
         '    b: fatigue strength exponent (typically -0.05 to -0.12).\n'
         '    Returns number of cycles to failure."""\n'
         '    N = 0.5 * (sigma_a / sigma_f_prime) ** (1 / b_exponent)\n'
         '    return {"N_cycles": N}\n'
         'export = fatigue_life_basquin'
     )},
    {"name": "miners_rule", "type": "R", "domain": "materials",
     "desc": "Miner's rule cumulative damage: D = sum(ni/Ni). Failure when D >= 1.",
     "tags": ["materials", "fatigue", "damage", "miners_rule"],
     "latex": r"D = \sum_i \frac{n_i}{N_i}",
     "source": (
         'def miners_rule(cycle_counts, cycle_limits):\n'
         '    """cycle_counts: list of ni, cycle_limits: list of Ni."""\n'
         '    D = sum(n / N for n, N in zip(cycle_counts, cycle_limits) if N > 0)\n'
         '    return {"damage_index": D, "failed": D >= 1.0,\n'
         '            "remaining_life_fraction": max(0, 1 - D)}\n'
         'export = miners_rule'
     )},
    {"name": "fracture_toughness_check", "type": "R", "domain": "materials",
     "desc": "Linear elastic fracture mechanics: K = sigma * sqrt(pi * a) * F",
     "tags": ["materials", "fracture", "LEFM", "toughness"],
     "latex": r"K_I = \sigma\, F\sqrt{\pi a}",
     "source": (
         'import numpy as np\n'
         'def fracture_toughness_check(sigma, a_crack, KIc, F_geometry=1.12):\n'
         '    """sigma: stress [Pa], a_crack: crack half-length [m],\n'
         '    KIc: plane strain fracture toughness [Pa*sqrt(m)], F: geometry factor."""\n'
         '    KI = sigma * np.sqrt(np.pi * a_crack) * F_geometry\n'
         '    SF = KIc / KI if KI > 0 else float("inf")\n'
         '    return {"KI": KI, "KIc": KIc, "safety_factor": SF, "failed": KI >= KIc}\n'
         'export = fracture_toughness_check'
     )},
    {"name": "composite_laminate_stiffness", "type": "R", "domain": "materials",
     "desc": "Rule-of-mixtures for unidirectional composite: E1, E2, G12, nu12",
     "tags": ["materials", "composite", "laminate", "rule_of_mixtures"],
     "latex": r"E_1 = E_f V_f + E_m V_m,\quad E_2 = \frac{E_f E_m}{E_f V_m + E_m V_f},\quad \nu_{12} = \nu_f V_f + \nu_m V_m",
     "source": (
         'def composite_laminate_stiffness(Ef, Em, Gf, Gm, nu_f, nu_m, Vf):\n'
         '    """Vf: fiber volume fraction (0-1). Returns UD ply properties."""\n'
         '    Vm = 1 - Vf\n'
         '    E1 = Ef * Vf + Em * Vm\n'
         '    E2 = Ef * Em / (Ef * Vm + Em * Vf)\n'
         '    G12 = Gf * Gm / (Gf * Vm + Gm * Vf)\n'
         '    nu12 = nu_f * Vf + nu_m * Vm\n'
         '    return {"E1": E1, "E2": E2, "G12": G12, "nu12": nu12}\n'
         'export = composite_laminate_stiffness'
     )},

    # ==================== ORBITAL MECHANICS (EXTENDED) ====================
    {"name": "keplerian_to_cartesian", "type": "R", "domain": "orbital",
     "desc": "Convert Keplerian elements to ECI Cartesian state (r, v vectors)",
     "tags": ["orbital", "keplerian", "cartesian", "state_vector"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def keplerian_to_cartesian(a, e, i_deg, RAAN_deg, omega_deg, nu_deg, mu):\n'
         '    """Convert classical orbital elements to ECI position and velocity.\n'
         '    a: semi-major axis [m], e: eccentricity, angles in degrees, mu [m³/s²].\n'
         '    Returns r_eci [m] and v_eci [m/s] as 3-element lists.\n'
         '    """\n'
         '    a=float(a); e=float(e); mu=float(mu)\n'
         '    i=_rad(i_deg); W=_rad(RAAN_deg)\n'
         '    w=_rad(omega_deg); nu=_rad(nu_deg)\n'
         '    p = a*(1-e**2)\n'
         '    r = p/(1+e*np.cos(nu))\n'
         '    r_pf = r*np.array([np.cos(nu), np.sin(nu), 0.0])\n'
         '    v_pf = np.sqrt(mu/p)*np.array([-np.sin(nu), e+np.cos(nu), 0.0])\n'
         '    cW,sW=np.cos(W),np.sin(W); ci,si=np.cos(i),np.sin(i)\n'
         '    cw,sw=np.cos(w),np.sin(w)\n'
         '    Q_mat = np.array([\n'
         '        [cW*cw-sW*sw*ci, -cW*sw-sW*cw*ci,  sW*si],\n'
         '        [sW*cw+cW*sw*ci, -sW*sw+cW*cw*ci, -cW*si],\n'
         '        [sw*si,           cw*si,             ci  ]])\n'
         '    r_eci = Q_mat @ r_pf\n'
         '    v_eci = Q_mat @ v_pf\n'
         '    return {"r_eci": r_eci.tolist(), "v_eci": v_eci.tolist(),\n'
         '            "r_mag": Q(float(r), "m"), "v_mag": Q(float(np.linalg.norm(v_eci)), "m/s")}\n'
         'export = keplerian_to_cartesian'
     )},
    {"name": "cartesian_to_keplerian", "type": "R", "domain": "orbital",
     "desc": "Convert ECI Cartesian state vector to Keplerian orbital elements",
     "tags": ["orbital", "keplerian", "cartesian", "orbit_determination"],
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def cartesian_to_keplerian(r_vec, v_vec, mu):\n'
         '    """Convert ECI position+velocity to classical orbital elements.\n'
         '    r_vec, v_vec: 3-element lists [m] and [m/s]. mu in m³/s².\n'
         '    """\n'
         '    r=np.array(r_vec,dtype=float); v=np.array(v_vec,dtype=float)\n'
         '    mu=float(mu)\n'
         '    r_m=np.linalg.norm(r); v_m=np.linalg.norm(v)\n'
         '    eps = v_m**2/2 - mu/r_m\n'
         '    a = -mu/(2*eps)\n'
         '    h = np.cross(r,v); h_m=np.linalg.norm(h)\n'
         '    e_vec = np.cross(v,h)/mu - r/r_m\n'
         '    e = np.linalg.norm(e_vec)\n'
         '    i_deg = float(np.degrees(np.arccos(np.clip(h[2]/h_m,-1,1))))\n'
         '    N = np.cross(np.array([0,0,1.0]),h); N_m=np.linalg.norm(N)\n'
         '    RAAN_deg = 0.0\n'
         '    if N_m > 1e-10:\n'
         '        RAAN_deg = float(np.degrees(np.arccos(np.clip(N[0]/N_m,-1,1))))\n'
         '        if N[1] < 0: RAAN_deg = 360-RAAN_deg\n'
         '    omega_deg = 0.0\n'
         '    if N_m > 1e-10 and e > 1e-10:\n'
         '        omega_deg = float(np.degrees(np.arccos(np.clip(np.dot(N,e_vec)/(N_m*e),-1,1))))\n'
         '        if e_vec[2] < 0: omega_deg = 360-omega_deg\n'
         '    nu_deg = 0.0\n'
         '    if e > 1e-10:\n'
         '        nu_deg = float(np.degrees(np.arccos(np.clip(np.dot(e_vec,r)/(e*r_m),-1,1))))\n'
         '        if np.dot(r,v) < 0: nu_deg = 360-nu_deg\n'
         '    return {"a": Q(float(a),"m"), "e": float(e), "i_deg": i_deg,\n'
         '            "RAAN_deg": RAAN_deg, "omega_deg": omega_deg, "nu_deg": nu_deg,\n'
         '            "h_mag": Q(float(h_m),"m^2/s")}\n'
         'export = cartesian_to_keplerian'
     )},
    {"name": "plane_change_dv", "type": "R", "domain": "orbital",
     "desc": "Delta-V for a pure orbital plane change (inclination change)",
     "tags": ["orbital", "plane_change", "inclination", "delta_v"],
     "latex": r"\Delta V = 2 V \sin\!\left(\frac{\Delta i}{2}\right)",
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def plane_change_dv(v, delta_i_deg):\n'
         '    """Delta-V for a pure inclination change.\n'
         '    v: orbital speed [m/s], delta_i_deg: inclination change [deg].\n'
         '    Most efficient at apoapsis (lowest v).\n'
         '    """\n'
         '    dv = 2*float(v)*math.sin(_rad(delta_i_deg)/2)\n'
         '    return {"dv_plane_change": Q(dv,"m/s")}\n'
         'export = plane_change_dv'
     )},
    {"name": "bielliptic_transfer", "type": "R", "domain": "orbital",
     "desc": "Bi-elliptic transfer delta-V between two circular orbits via intermediate radius",
     "tags": ["orbital", "bielliptic", "transfer", "delta_v"],
     "latex": r"\Delta V = \Delta V_1 + \Delta V_2 + \Delta V_3,\quad a_1 = \tfrac{r_1+r_b}{2},\ a_2 = \tfrac{r_b+r_2}{2}",
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def bielliptic_transfer(mu, r1, r2, rb):\n'
         '    """Bi-elliptic transfer r1 -> rb -> r2. More efficient than Hohmann when r2/r1 > 11.94.\n'
         '    rb: intermediate apoapsis radius [m]. Must be >= max(r1,r2).\n'
         '    """\n'
         '    mu=float(mu); r1=float(r1); r2=float(r2); rb=float(rb)\n'
         '    a1=(r1+rb)/2; a2=(rb+r2)/2\n'
         '    v1=np.sqrt(mu/r1)\n'
         '    vt1a=np.sqrt(mu*(2/r1-1/a1)); dv1=abs(vt1a-v1)\n'
         '    vt1b=np.sqrt(mu*(2/rb-1/a1)); vt2b=np.sqrt(mu*(2/rb-1/a2)); dv2=abs(vt2b-vt1b)\n'
         '    vt2a=np.sqrt(mu*(2/r2-1/a2)); v2=np.sqrt(mu/r2); dv3=abs(v2-vt2a)\n'
         '    tof=np.pi*((a1**3/mu)**0.5+(a2**3/mu)**0.5)\n'
         '    return {"dv1":Q(dv1,"m/s"),"dv2":Q(dv2,"m/s"),"dv3":Q(dv3,"m/s"),\n'
         '            "dv_total":Q(dv1+dv2+dv3,"m/s"),"tof":Q(tof,"s")}\n'
         'export = bielliptic_transfer'
     )},
    {"name": "j2_precession", "type": "R", "domain": "orbital",
     "desc": "J2 oblateness nodal (RAAN) and apsidal (perigee) precession rates",
     "tags": ["orbital", "J2", "precession", "perturbation"],
     "latex": r"\dot{\Omega} = -\tfrac{3}{2} n J_2 \left(\frac{R}{p}\right)^2 \cos i,\quad \dot{\omega} = \tfrac{3}{4} n J_2 \left(\frac{R}{p}\right)^2 (5\cos^2 i - 1)",
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def j2_precession(a, e, i_deg, mu=3.986004418e14, R_body=6.371e6, J2=1.08263e-3):\n'
         '    """J2 secular precession rates for Earth orbit.\n'
         '    Returns RAAN and argument-of-perigee drift in rad/s and deg/day.\n'
         '    """\n'
         '    a=float(a); e=float(e); i=_rad(i_deg)\n'
         '    n=np.sqrt(float(mu)/a**3); p=a*(1-e**2)\n'
         '    fac=-1.5*n*float(J2)*(float(R_body)/p)**2\n'
         '    d_RAAN = fac*np.cos(i)\n'
         '    d_omega = -0.5*fac*(5*np.cos(i)**2-1)\n'
         '    return {"d_RAAN_dt":Q(float(d_RAAN),"rad/s"),\n'
         '            "d_omega_dt":Q(float(d_omega),"rad/s")}\n'
         'export = j2_precession'
     )},
    {"name": "eclipse_fraction", "type": "R", "domain": "orbital",
     "desc": "Fraction of circular orbit spent in planet shadow (cylindrical model)",
     "tags": ["orbital", "eclipse", "shadow", "power"],
     "latex": r"f_{ecl} = \frac{1}{\pi}\arccos\!\left(\frac{\cos\rho}{\cos\beta}\right),\quad \rho = \arcsin\!\left(\frac{R}{a}\right)",
     "source": (
         'import numpy as np\n'
         'def eclipse_fraction(a, R_body=6.371e6, beta_deg=0.0):\n'
         '    """Cylindrical shadow model. beta_deg: sun-orbit plane angle.\n'
         '    Returns eclipse_frac=0 when |beta|>beta_max (no eclipse season).\n'
         '    """\n'
         '    a=float(a); R_body=float(R_body); beta=_rad(beta_deg)\n'
         '    rho=np.arcsin(min(R_body/a,1.0))\n'
         '    beta_max_deg=float(np.degrees(rho))\n'
         '    if abs(beta)>=rho:\n'
         '        return {"eclipse_frac":0.0,"beta_max_deg":beta_max_deg,"in_eclipse_season":False}\n'
         '    eclipse_frac=float(np.arccos(np.cos(rho)/np.cos(beta))/np.pi)\n'
         '    return {"eclipse_frac":eclipse_frac,"beta_max_deg":beta_max_deg,"in_eclipse_season":True}\n'
         'export = eclipse_fraction'
     )},
    {"name": "sphere_of_influence", "type": "R", "domain": "orbital",
     "desc": "Laplace sphere of influence radius: r_SOI = a*(m_body/m_parent)^(2/5)",
     "tags": ["orbital", "SOI", "patched_conic", "gravity_assist"],
     "latex": r"r_{SOI} = a\left(\frac{m_{body}}{m_{parent}}\right)^{2/5}",
     "source": (
         'from anvil import Q\n'
         'def sphere_of_influence(a_body, m_body, m_parent):\n'
         '    """Sphere of influence for patched-conic trajectory design.\n'
         '    a_body: semi-major axis of body around parent [m],\n'
         '    m_body, m_parent: masses [kg].\n'
         '    """\n'
         '    r_SOI=float(a_body)*(float(m_body)/float(m_parent))**0.4\n'
         '    return {"r_SOI":Q(r_SOI,"m")}\n'
         'export = sphere_of_influence'
     )},
    {"name": "propellant_mass", "type": "R", "domain": "orbital",
     "desc": "Propellant mass from delta-V requirement via Tsiolkovsky equation (inverse)",
     "tags": ["orbital", "propulsion", "propellant", "tsiolkovsky", "delta_v"],
     "latex": r"m_p = m_{dry}\left(e^{\Delta V/(I_{sp} g_0)} - 1\right)",
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def propellant_mass(dv, Isp, m_dry):\n'
         '    """Compute propellant mass from delta-V, Isp, and dry mass.\n'
         '    dv [m/s], Isp [s], m_dry [kg].\n'
         '    """\n'
         '    mass_ratio=math.exp(float(dv)/(float(Isp)*9.80665))\n'
         '    m_wet=float(m_dry)*mass_ratio\n'
         '    return {"m_propellant":Q(m_wet-float(m_dry),"kg"),"m_wet":Q(m_wet,"kg"),"mass_ratio":mass_ratio}\n'
         'export = propellant_mass'
     )},
    {"name": "delta_v_budget", "type": "R", "domain": "orbital",
     "desc": "Aggregate mission delta-V budget across up to 6 phases with margin",
     "tags": ["orbital", "delta_v", "budget", "mission"],
     "latex": r"\Delta V_{total} = \left(\sum_i \Delta V_i\right)\left(1 + \frac{m_{\%}}{100}\right)",
     "source": (
         'from anvil import Q\n'
         'def delta_v_budget(dv1, dv2=0, dv3=0, dv4=0, dv5=0, dv6=0, margin_pct=5.0):\n'
         '    """Sum delta-V phases and apply a percentage margin.\n'
         '    dv1..dv6 [m/s]: mission phase delta-Vs. margin_pct: design margin [%].\n'
         '    """\n'
         '    tot=float(dv1)+float(dv2)+float(dv3)+float(dv4)+float(dv5)+float(dv6)\n'
         '    margin=tot*float(margin_pct)/100\n'
         '    return {"dv_total":Q(tot,"m/s"),"dv_with_margin":Q(tot+margin,"m/s"),\n'
         '            "dv_margin":Q(margin,"m/s")}\n'
         'export = delta_v_budget'
     )},

    # ==================== ATTITUDE & ADCS ====================
    {"name": "euler_equations", "type": "R", "domain": "attitude",
     "desc": "Euler's equations of motion for rigid body rotation in principal axes",
     "tags": ["attitude", "rigid_body", "euler", "rotation", "dynamics"],
     "latex": r"\dot{\omega}_x = \frac{\tau_x - (I_z - I_y)\omega_y\omega_z}{I_x}\quad(\text{and cyclic in } x,y,z)",
     "source": (
         'from anvil import Q\n'
         'def euler_equations(omega_x, omega_y, omega_z, Ix, Iy, Iz,\n'
         '                    tau_x=0.0, tau_y=0.0, tau_z=0.0):\n'
         '    """Instantaneous angular acceleration from Euler equations.\n'
         '    omega_* [rad/s]: body rates. I* [kg*m²]: principal moments.\n'
         '    tau_* [N*m]: external torques.\n'
         '    """\n'
         '    ox,oy,oz=float(omega_x),float(omega_y),float(omega_z)\n'
         '    Ix,Iy,Iz=float(Ix),float(Iy),float(Iz)\n'
         '    ax=(float(tau_x)-(Iz-Iy)*oy*oz)/Ix\n'
         '    ay=(float(tau_y)-(Ix-Iz)*oz*ox)/Iy\n'
         '    az=(float(tau_z)-(Iy-Ix)*ox*oy)/Iz\n'
         '    return {"alpha_x":Q(ax,"rad/s^2"),"alpha_y":Q(ay,"rad/s^2"),"alpha_z":Q(az,"rad/s^2")}\n'
         'export = euler_equations'
     )},
    {"name": "quaternion_kinematics", "type": "R", "domain": "attitude",
     "desc": "Quaternion kinematic equation: q_dot = 0.5 * Ξ(q) * omega",
     "tags": ["attitude", "quaternion", "kinematics", "ADCS"],
     "latex": r"\dot{q} = \tfrac{1}{2}\,q \otimes \begin{bmatrix}0 \\ \boldsymbol{\omega}\end{bmatrix}",
     "source": (
         'import math\n'
         'def quaternion_kinematics(q_w, q_x, q_y, q_z, omega_x, omega_y, omega_z):\n'
         '    """Quaternion time derivative given attitude q=[w,x,y,z] and body rate omega.\n'
         '    Hamilton convention. omega [rad/s] in body frame.\n'
         '    """\n'
         '    qw,qx,qy,qz=float(q_w),float(q_x),float(q_y),float(q_z)\n'
         '    ox,oy,oz=float(omega_x),float(omega_y),float(omega_z)\n'
         '    qw_dot=0.5*(-qx*ox-qy*oy-qz*oz)\n'
         '    qx_dot=0.5*( qw*ox-qz*oy+qy*oz)\n'
         '    qy_dot=0.5*( qz*ox+qw*oy-qx*oz)\n'
         '    qz_dot=0.5*(-qy*ox+qx*oy+qw*oz)\n'
         '    q_norm=math.sqrt(qw**2+qx**2+qy**2+qz**2)\n'
         '    return {"qw_dot":qw_dot,"qx_dot":qx_dot,"qy_dot":qy_dot,"qz_dot":qz_dot,\n'
         '            "q_norm":q_norm}\n'
         'export = quaternion_kinematics'
     )},
    {"name": "triad_attitude", "type": "R", "domain": "attitude",
     "desc": "TRIAD two-vector attitude determination: body-to-reference DCM and quaternion",
     "tags": ["attitude", "TRIAD", "attitude_determination", "ADCS"],
     "source": (
         'import numpy as np\n'
         'def triad_attitude(b1_x,b1_y,b1_z, b2_x,b2_y,b2_z,\n'
         '                   r1_x,r1_y,r1_z, r2_x,r2_y,r2_z):\n'
         '    """TRIAD attitude determination.\n'
         '    b1,b2: reference vectors measured in body frame.\n'
         '    r1,r2: same vectors in reference (inertial) frame.\n'
         '    Returns body-to-reference DCM C (3x3) and quaternion [w,x,y,z].\n'
         '    """\n'
         '    def u(v): return v/np.linalg.norm(v)\n'
         '    b1=u(np.array([float(b1_x),float(b1_y),float(b1_z)]))\n'
         '    b2=u(np.array([float(b2_x),float(b2_y),float(b2_z)]))\n'
         '    r1=u(np.array([float(r1_x),float(r1_y),float(r1_z)]))\n'
         '    r2=u(np.array([float(r2_x),float(r2_y),float(r2_z)]))\n'
         '    t1b=b1; t2b=u(np.cross(b1,b2)); t3b=np.cross(t1b,t2b)\n'
         '    t1r=r1; t2r=u(np.cross(r1,r2)); t3r=np.cross(t1r,t2r)\n'
         '    C=(np.column_stack([t1b,t2b,t3b])@np.column_stack([t1r,t2r,t3r]).T)\n'
         '    tr=np.trace(C)\n'
         '    qw=0.5*np.sqrt(max(0,1+tr))\n'
         '    if qw>1e-10:\n'
         '        qx=(C[2,1]-C[1,2])/(4*qw); qy=(C[0,2]-C[2,0])/(4*qw); qz=(C[1,0]-C[0,1])/(4*qw)\n'
         '    else:\n'
         '        qx=np.sqrt(max(0,(1+C[0,0]-C[1,1]-C[2,2])/4))\n'
         '        qy=np.sqrt(max(0,(1-C[0,0]+C[1,1]-C[2,2])/4))\n'
         '        qz=np.sqrt(max(0,(1-C[0,0]-C[1,1]+C[2,2])/4))\n'
         '    return {"C":C.tolist(),"q_w":float(qw),"q_x":float(qx),"q_y":float(qy),"q_z":float(qz)}\n'
         'export = triad_attitude'
     )},
    {"name": "gravity_gradient_torque", "type": "R", "domain": "attitude",
     "desc": "Gravity gradient torque on a nadir-pointing satellite",
     "tags": ["attitude", "gravity_gradient", "torque", "disturbance"],
     "latex": r"T_{gg} = \tfrac{3}{2}\,\frac{\mu}{r^3}\,|I_z - I_y|",
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def gravity_gradient_torque(mu, r, Ix, Iy, Iz,\n'
         '                            theta_pitch_deg=0.0, phi_roll_deg=0.0):\n'
         '    """Gravity gradient torque in orbital (roll-pitch-yaw) frame.\n'
         '    mu [m³/s²], r [m]: orbit radius, I* [kg*m²]: principal moments.\n'
         '    Small-angle linearisation. T_gg_max is worst-case (45 deg) peak.\n'
         '    """\n'
         '    omega2=float(mu)/float(r)**3\n'
         '    theta=_rad(theta_pitch_deg); phi=_rad(phi_roll_deg)\n'
         '    Ix,Iy,Iz=float(Ix),float(Iy),float(Iz)\n'
         '    T_roll =3*omega2*(Iz-Iy)*phi\n'
         '    T_pitch=3*omega2*(Iy-Ix)*theta\n'
         '    T_gg_max=1.5*omega2*max(abs(Ix-Iy),abs(Iy-Iz),abs(Ix-Iz))\n'
         '    return {"T_roll":Q(float(T_roll),"N*m"),"T_pitch":Q(float(T_pitch),"N*m"),\n'
         '            "T_gg_max":Q(float(T_gg_max),"N*m"),\n'
         '            "omega_orbital":Q(float(np.sqrt(omega2)),"rad/s")}\n'
         'export = gravity_gradient_torque'
     )},
    {"name": "reaction_wheel_sizing", "type": "R", "domain": "attitude",
     "desc": "Reaction wheel angular momentum and torque sizing for a slew maneuver",
     "tags": ["attitude", "reaction_wheel", "sizing", "ADCS"],
     "latex": r"\omega_{max} = \frac{2\theta}{t_s},\quad \tau = I\,\frac{\omega_{max}}{t_s/2},\quad H = I\,\omega_{max}\,k",
     "source": (
         'import numpy as np\n'
         'from anvil import Q\n'
         'def reaction_wheel_sizing(I_sc, theta_slew_deg, t_slew, margin=1.5):\n'
         '    """Size a reaction wheel for a bang-bang slew maneuver.\n'
         '    I_sc [kg*m²]: spacecraft MOI about slew axis.\n'
         '    theta_slew_deg [deg]: slew angle. t_slew [s]: slew time.\n'
         '    margin: design margin factor (1.5 = 50% margin).\n'
         '    """\n'
         '    theta=_rad(theta_slew_deg)\n'
         '    omega_max=2*theta/float(t_slew)\n'
         '    alpha_max=omega_max/(float(t_slew)/2)\n'
         '    tau_max=float(I_sc)*alpha_max\n'
         '    H=float(I_sc)*omega_max*float(margin)\n'
         '    P_peak=tau_max*omega_max*float(margin)\n'
         '    return {"H_rw":Q(H,"N*m*s"),"tau_rw":Q(tau_max,"N*m"),\n'
         '            "omega_slew_max":Q(omega_max,"rad/s"),"P_peak":Q(P_peak,"W")}\n'
         'export = reaction_wheel_sizing'
     )},

    # ==================== MISSION BUDGETS ====================
    {"name": "link_budget", "type": "R", "domain": "mission",
     "desc": "RF link budget: received power and FSPL via Friis equation",
     "tags": ["mission", "link_budget", "RF", "communications", "FSPL"],
     "latex": r"P_{rx} = P_{tx} + G_{tx} + G_{rx} - L_{FS} - L,\quad L_{FS} = 20\log_{10}\!\left(\frac{4\pi d f}{c}\right)",
     "source": (
         'import math\n'
         'from anvil import Q\n'
         'def link_budget(P_tx_W, G_tx_dBi, G_rx_dBi, freq_Hz, distance_m, losses_dB=3.0):\n'
         '    """Friis free-space link budget.\n'
         '    P_tx_W: transmit power [W]. G_*_dBi: antenna gains [dBi].\n'
         '    freq_Hz: carrier frequency. distance_m: range. losses_dB: misc losses.\n'
         '    """\n'
         '    c=2.998e8\n'
         '    FSPL_dB=20*math.log10(4*math.pi*float(distance_m)*float(freq_Hz)/c)\n'
         '    P_tx_dBW=10*math.log10(float(P_tx_W))\n'
         '    P_rx_dBW=P_tx_dBW+float(G_tx_dBi)+float(G_rx_dBi)-FSPL_dB-float(losses_dB)\n'
         '    EIRP_dBW=P_tx_dBW+float(G_tx_dBi)\n'
         '    return {"P_rx_W":Q(10**(P_rx_dBW/10),"W"),"P_rx_dBW":P_rx_dBW,\n'
         '            "FSPL_dB":FSPL_dB,"EIRP_dBW":EIRP_dBW}\n'
         'export = link_budget'
     )},
    {"name": "power_budget", "type": "R", "domain": "mission",
     "desc": "Spacecraft solar array area and battery sizing from load and eclipse fraction",
     "tags": ["mission", "power_budget", "solar", "battery", "eclipse"],
     "source": (
         'from anvil import Q\n'
         'def power_budget(P_load_W, T_orbit_min, eclipse_frac,\n'
         '                 eta_solar=0.28, flux_solar=1361.0, DOD=0.8, eta_battery=0.9):\n'
         '    """Solar panel area and battery capacity sizing.\n'
         '    P_load_W: average load. T_orbit_min: orbital period [min].\n'
         '    eclipse_frac: fraction in shadow. eta_solar: panel efficiency.\n'
         '    flux_solar [W/m²]: solar irradiance. DOD: depth of discharge.\n'
         '    """\n'
         '    t_sun=float(T_orbit_min)*60*(1-float(eclipse_frac))\n'
         '    t_ecl=float(T_orbit_min)*60*float(eclipse_frac)\n'
         '    P_load=float(P_load_W)\n'
         '    E_bat_J=P_load*t_ecl\n'
         '    P_charge=E_bat_J/(t_sun*float(eta_battery)) if t_sun>0 else 0\n'
         '    P_from_panel=P_load+P_charge\n'
         '    A_panel=P_from_panel/(float(eta_solar)*float(flux_solar))\n'
         '    E_bat_Wh=P_load*t_ecl/3600/float(DOD)\n'
         '    m_bat=E_bat_Wh/120  # 120 Wh/kg Li-ion\n'
         '    return {"A_panel_m2":Q(A_panel,"m^2"),"E_bat_Wh":Q(E_bat_Wh,"Wh"),\n'
         '            "m_bat_kg":Q(m_bat,"kg"),"P_from_panel_W":Q(P_from_panel,"W")}\n'
         'export = power_budget'
     )},

    # ==================== CONTROLS (EXTENDED) ====================
    {"name": "state_space_poles", "type": "R", "domain": "controls",
     "desc": "Eigenvalues (poles) of a state matrix A; stability check",
     "tags": ["controls", "state_space", "poles", "stability", "eigenvalues"],
     "latex": r"\det(A - \lambda I) = 0,\quad \text{stable} \iff \mathrm{Re}(\lambda_i) < 0\ \forall i",
     "source": (
         'import numpy as np\n'
         'def state_space_poles(A_flat, n_states):\n'
         '    """Compute poles (eigenvalues) of state matrix A.\n'
         '    A_flat: row-major list of n_states² floats.\n'
         '    n_states: system order.\n'
         '    """\n'
         '    A=np.array([float(x) for x in A_flat],dtype=float).reshape(int(n_states),int(n_states))\n'
         '    poles=np.linalg.eigvals(A)\n'
         '    stable=bool(np.all(poles.real<0))\n'
         '    min_damp=float(min((-p.real/abs(p) if abs(p)>1e-20 else (1.0 if p.real<0 else -1.0))\n'
         '                       for p in poles))\n'
         '    return {"poles_real":poles.real.tolist(),"poles_imag":poles.imag.tolist(),\n'
         '            "stable":stable,"min_damping":min_damp}\n'
         'export = state_space_poles'
     )},
    {"name": "lqr_bryson", "type": "R", "domain": "controls",
     "desc": "Bryson's rule for LQR Q and R weighting matrices from max allowable values",
     "tags": ["controls", "LQR", "bryson", "optimal_control", "tuning"],
     "latex": r"Q_{ii} = \frac{1}{x_{i,max}^2},\quad R_{jj} = \frac{1}{u_{j,max}^2}",
     "source": (
         'def lqr_bryson(state_bounds, input_bounds):\n'
         '    """Bryson rule: Q_ii=1/x_max_i², R_jj=1/u_max_j².\n'
         '    state_bounds: list of max allowable state deviations.\n'
         '    input_bounds: list of max allowable control inputs.\n'
         '    Returns diagonal entries of Q and R.\n'
         '    """\n'
         '    Q_diag=[1.0/float(x)**2 for x in state_bounds]\n'
         '    R_diag=[1.0/float(u)**2 for u in input_bounds]\n'
         '    return {"Q_diag":Q_diag,"R_diag":R_diag,"n_states":len(Q_diag),"n_inputs":len(R_diag)}\n'
         'export = lqr_bryson'
     )},
    {"name": "gain_phase_margin", "type": "R", "domain": "controls",
     "desc": "Gain margin and phase margin for an open-loop transfer function",
     "tags": ["controls", "stability", "gain_margin", "phase_margin", "bode"],
     "source": (
         'import numpy as np\n'
         'def gain_phase_margin(num_coeffs, den_coeffs, omega_lo=1e-3, omega_hi=1e4, n=2000):\n'
         '    """Gain and phase margins from frequency sweep of G(s)=num/den.\n'
         '    Polynomial coefficients in descending order [s^n, ..., s^0].\n'
         '    """\n'
         '    omega=np.logspace(np.log10(float(omega_lo)),np.log10(float(omega_hi)),int(n))\n'
         '    num=[float(c) for c in num_coeffs]; den=[float(c) for c in den_coeffs]\n'
         '    def polyval(coeffs,s):\n'
         '        n=len(coeffs)-1; return sum(c*s**(n-k) for k,c in enumerate(coeffs))\n'
         '    G=np.array([polyval(num,1j*w)/polyval(den,1j*w) for w in omega])\n'
         '    mag=np.abs(G); phase_deg=np.angle(G,deg=True)\n'
         '    # Phase crossover (phase = -180 deg)\n'
         '    GM_dB=float("inf")\n'
         '    cross_p=np.where(np.diff(np.sign(phase_deg+180)))[0]\n'
         '    if len(cross_p)>0:\n'
         '        i=int(cross_p[-1])\n'
         '        GM_dB=float(-20*np.log10(mag[i])) if mag[i]>0 else float("inf")\n'
         '    # Gain crossover (mag = 1)\n'
         '    PM_deg=float("inf")\n'
         '    cross_g=np.where(np.diff(np.sign(mag-1)))[0]\n'
         '    if len(cross_g)>0:\n'
         '        i=int(cross_g[-1])\n'
         '        PM_deg=float(phase_deg[i]+180)\n'
         '    return {"GM_dB":GM_dB,"PM_deg":PM_deg,"stable":GM_dB>0 and PM_deg>0}\n'
         'export = gain_phase_margin'
     )},

    # ==================== DECOMPOSITION ====================
    {"name": "pod_analysis", "type": "R", "domain": "misc",
     "desc": "Proper Orthogonal Decomposition of snapshot matrix X (n_space × n_time)",
     "tags": ["pod", "svd", "decomposition", "rom", "modes"],
     "source": (
         'def pod_analysis(X, r=None, subtract_mean=True):\n'
         '    """POD of snapshot matrix X (n_space × n_time). Returns modes, energy, rank."""\n'
         '    from anvil.decomp import pod, pod_rank\n'
         '    import numpy as np\n'
         '    result = pod(X, r=r, subtract_mean=bool(subtract_mean))\n'
         '    rank_99  = int(pod_rank(result, target_energy=0.99))\n'
         '    rank_999 = int(pod_rank(result, target_energy=0.999))\n'
         '    return {\n'
         '        "modes":                result["modes"],\n'
         '        "singular_values":      result["singular_values"],\n'
         '        "temporal_coefficients":result["temporal_coefficients"],\n'
         '        "energy_fractions":     result["energy_fractions"],\n'
         '        "cumulative_energy":    result["cumulative_energy"],\n'
         '        "mean":                 result["mean"],\n'
         '        "rank":                 result["rank"],\n'
         '        "rank_99":              rank_99,\n'
         '        "rank_999":             rank_999,\n'
         '    }\n'
         'export = pod_analysis'
     )},

    {"name": "dmd_analysis", "type": "R", "domain": "misc",
     "desc": "Dynamic Mode Decomposition of snapshot matrix X (n_space × n_time)",
     "tags": ["dmd", "decomposition", "eigenvalues", "stability", "modes"],
     "source": (
         'def dmd_analysis(X, dt=1.0, r=None):\n'
         '    """DMD of snapshot matrix X (n_space × n_time). dt = time step between columns."""\n'
         '    from anvil.decomp import dmd\n'
         '    import numpy as np\n'
         '    result = dmd(X, dt=float(dt), r=r)\n'
         '    gr = result["growth_rates"]\n'
         '    return {\n'
         '        "eigenvalues":    result["eigenvalues"],\n'
         '        "omega":          result["omega"],\n'
         '        "modes":          result["modes"],\n'
         '        "amplitudes":     result["amplitudes"],\n'
         '        "frequencies":    result["frequencies"],\n'
         '        "growth_rates":   gr,\n'
         '        "singular_values":result["singular_values"],\n'
         '        "n_stable":       int(np.sum(gr < 0)),\n'
         '        "n_unstable":     int(np.sum(gr > 0)),\n'
         '        "n_neutral":      int(np.sum(np.abs(gr) < 1e-8)),\n'
         '    }\n'
         'export = dmd_analysis'
     )},

    {"name": "abel_inverse", "type": "R", "domain": "misc",
     "desc": "Inverse Abel transform: projected profile F(y) → radial profile f(r)",
     "tags": ["abel", "inverse", "spectroscopy", "axisymmetric", "combustion"],
     "source": (
         'def abel_inverse(F_projected, dr=1.0, method="three_point"):\n'
         '    """Inverse Abel transform. F_projected: 1D projected profile array.\n'
         '    dr: radial step size. method: "three_point" (smooth) or "onion" (sharp features).\n'
         '    """\n'
         '    import numpy as np\n'
         '    from anvil.decomp import abel_three_point, abel_onion\n'
         '    F = np.asarray(F_projected, dtype=float)\n'
         '    if method == "three_point":\n'
         '        f = abel_three_point(F, dr=float(dr))\n'
         '    elif method == "onion":\n'
         '        f = abel_onion(F, dr=float(dr))\n'
         '    else:\n'
         '        raise ValueError(f"method must be \'three_point\' or \'onion\', got \'{method}\'")\n'
         '    return {"f_radial": f}\n'
         'export = abel_inverse'
     )},

    {"name": "abel_forward", "type": "R", "domain": "misc",
     "desc": "Forward Abel transform: radial profile f(r) → projected profile F(y)",
     "tags": ["abel", "forward", "spectroscopy", "axisymmetric", "projection"],
     "source": (
         'def abel_forward(f_radial, dr=1.0):\n'
         '    """Forward Abel transform. f_radial: 1D radial profile. dr: radial step."""\n'
         '    import numpy as np\n'
         '    from anvil.decomp import abel_forward as _af\n'
         '    return {"F_projected": _af(np.asarray(f_radial, dtype=float), dr=float(dr))}\n'
         'export = abel_forward'
     )},

    # ==================== SIGNAL PROCESSING ====================
    {"name": "fft_spectrum", "type": "R", "domain": "misc",
     "desc": "Real FFT: signal → one-sided power spectrum, dominant frequency, THD",
     "tags": ["fft", "spectrum", "frequency", "signal", "vibration", "power"],
     "latex": r"X_k = \sum_{n=0}^{N-1} x_n\, e^{-i 2\pi k n / N}",
     "source": (
         'def fft_spectrum(signal, dt=1.0, window="hann"):\n'
         '    """Real FFT of a 1-D signal array.\n'
         '    dt: sampling interval (s). window: "hann", "hamming", "blackman", "none".\n'
         '    Returns: freqs (Hz), power, dominant_freq (Hz), dominant_power,\n'
         '             rms, thd (total harmonic distortion ratio 2nd-5th harmonics).\n'
         '    """\n'
         '    import numpy as np\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    n = len(x)\n'
         '    wins = {"hann": np.hanning, "hamming": np.hamming,\n'
         '            "blackman": np.blackman, "none": np.ones}\n'
         '    w = wins.get(str(window).lower(), np.hanning)(n)\n'
         '    xw = x * w\n'
         '    X = np.fft.rfft(xw)\n'
         '    freqs = np.fft.rfftfreq(n, d=float(dt))\n'
         '    # Normalise amplitude: scale by 2/n for one-sided (×2 for negative freq energy)\n'
         '    amp = np.abs(X) * 2.0 / n\n'
         '    amp[0] /= 2.0  # DC is one-sided already\n'
         '    power = amp**2\n'
         '    idx_dom = int(np.argmax(power[1:]) + 1)  # skip DC\n'
         '    f_dom = float(freqs[idx_dom])\n'
         '    p_dom = float(power[idx_dom])\n'
         '    rms_val = float(np.sqrt(np.mean(x**2)))\n'
         '    # THD: ratio of harmonic power (2nd-5th) to fundamental\n'
         '    if f_dom > 0:\n'
         '        harm_power = 0.0\n'
         '        for h in range(2, 6):\n'
         '            f_h = h * f_dom\n'
         '            if f_h > freqs[-1]: break\n'
         '            i_h = int(np.argmin(np.abs(freqs - f_h)))\n'
         '            harm_power += float(power[i_h])\n'
         '        thd = float(np.sqrt(harm_power) / (float(amp[idx_dom]) + 1e-30))\n'
         '    else:\n'
         '        thd = 0.0\n'
         '    return {\n'
         '        "freqs":          freqs,\n'
         '        "power":          power,\n'
         '        "amplitude":      amp,\n'
         '        "dominant_freq":  f_dom,\n'
         '        "dominant_power": p_dom,\n'
         '        "rms":            rms_val,\n'
         '        "thd":            thd,\n'
         '        "n_samples":      n,\n'
         '        "f_resolution":   float(freqs[1]) if len(freqs) > 1 else 0.0,\n'
         '    }\n'
         'export = fft_spectrum'
     )},

    {"name": "stft_spectrogram", "type": "R", "domain": "misc",
     "desc": "Short-Time Fourier Transform: signal → time-frequency spectrogram (t, f, S)",
     "tags": ["stft", "spectrogram", "time-frequency", "signal", "fft", "vibration"],
     "source": (
         'def stft_spectrogram(signal, dt=1.0, nperseg=256, noverlap=None, window="hann"):\n'
         '    """STFT spectrogram of a 1-D signal.\n'
         '    dt: sampling interval (s). nperseg: FFT segment length.\n'
         '    noverlap: overlap samples (default: nperseg//2). window: hann/hamming/blackman.\n'
         '    Returns: t (s), freqs (Hz), S (power, shape n_freq × n_time),\n'
         '             t_peak, f_peak (time and frequency of maximum energy).\n'
         '    """\n'
         '    import numpy as np\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    n = len(x)\n'
         '    seg = int(nperseg)\n'
         '    ovlp = seg // 2 if noverlap is None else int(noverlap)\n'
         '    step = seg - ovlp\n'
         '    wins = {"hann": np.hanning, "hamming": np.hamming,\n'
         '            "blackman": np.blackman, "none": np.ones}\n'
         '    w = wins.get(str(window).lower(), np.hanning)(seg)\n'
         '    freqs = np.fft.rfftfreq(seg, d=float(dt))\n'
         '    starts = list(range(0, n - seg + 1, step))\n'
         '    S = np.zeros((len(freqs), len(starts)))\n'
         '    t_arr = np.zeros(len(starts))\n'
         '    for k, s in enumerate(starts):\n'
         '        frame = x[s:s+seg] * w\n'
         '        X = np.fft.rfft(frame)\n'
         '        S[:, k] = (np.abs(X) * 2.0 / seg)**2\n'
         '        S[0, k] /= 4.0\n'
         '        t_arr[k] = (s + seg / 2) * float(dt)\n'
         '    idx = np.unravel_index(np.argmax(S), S.shape)\n'
         '    return {\n'
         '        "t":       t_arr,\n'
         '        "freqs":   freqs,\n'
         '        "S":       S,\n'
         '        "t_peak":  float(t_arr[idx[1]]),\n'
         '        "f_peak":  float(freqs[idx[0]]),\n'
         '        "n_frames": len(starts),\n'
         '    }\n'
         'export = stft_spectrogram'
     )},

    {"name": "bandpass_filter", "type": "R", "domain": "misc",
     "desc": "Butterworth bandpass (or lowpass/highpass) filter applied to a signal",
     "tags": ["filter", "bandpass", "butterworth", "signal", "lowpass", "highpass"],
     "source": (
         'def bandpass_filter(signal, dt=1.0, f_low=None, f_high=None, order=4):\n'
         '    """Zero-phase Butterworth filter.\n'
         '    f_low:  lower cutoff (Hz); None → lowpass only.\n'
         '    f_high: upper cutoff (Hz); None → highpass only.\n'
         '    Both set → bandpass. order: filter order (applied twice for zero-phase).\n'
         '    Returns: filtered signal array, same length as input.\n'
         '    """\n'
         '    import numpy as np\n'
         '    from scipy.signal import butter, sosfiltfilt\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    fs = 1.0 / float(dt)\n'
         '    nyq = fs / 2.0\n'
         '    if f_low is not None and f_high is not None:\n'
         '        btype = "bandpass"\n'
         '        Wn = [float(f_low)/nyq, float(f_high)/nyq]\n'
         '    elif f_low is not None:\n'
         '        btype = "highpass"\n'
         '        Wn = float(f_low)/nyq\n'
         '    elif f_high is not None:\n'
         '        btype = "lowpass"\n'
         '        Wn = float(f_high)/nyq\n'
         '    else:\n'
         '        return {"signal_filtered": x, "rms_in": float(np.sqrt(np.mean(x**2))),\n'
         '                "rms_out": float(np.sqrt(np.mean(x**2)))}\n'
         '    Wn = np.clip(Wn, 1e-6, 1.0 - 1e-6).tolist() if hasattr(Wn, "__len__") else float(np.clip(Wn, 1e-6, 1.0-1e-6))\n'
         '    sos = butter(int(order), Wn, btype=btype, output="sos")\n'
         '    y = sosfiltfilt(sos, x)\n'
         '    return {\n'
         '        "signal_filtered": y,\n'
         '        "rms_in":  float(np.sqrt(np.mean(x**2))),\n'
         '        "rms_out": float(np.sqrt(np.mean(y**2))),\n'
         '        "attenuation_dB": float(20*np.log10(np.sqrt(np.mean(y**2)) / (np.sqrt(np.mean(x**2))+1e-30))),\n'
         '    }\n'
         'export = bandpass_filter'
     )},

    {"name": "signal_statistics", "type": "R", "domain": "misc",
     "desc": "Descriptive statistics of a signal: mean, std, RMS, peak, crest factor, kurtosis",
     "tags": ["statistics", "signal", "rms", "kurtosis", "crest_factor", "vibration"],
     "source": (
         'def signal_statistics(signal, dt=1.0):\n'
         '    """Descriptive statistics for a 1-D time-domain signal.\n'
         '    dt: sampling interval (s), used to compute duration and sample rate.\n'
         '    """\n'
         '    import numpy as np\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    n = len(x)\n'
         '    mean   = float(np.mean(x))\n'
         '    std    = float(np.std(x))\n'
         '    rms    = float(np.sqrt(np.mean(x**2)))\n'
         '    peak   = float(np.max(np.abs(x)))\n'
         '    crest  = peak / (rms + 1e-30)\n'
         '    m2 = float(np.mean((x - mean)**2))\n'
         '    m4 = float(np.mean((x - mean)**4))\n'
         '    kurt   = m4 / (m2**2 + 1e-30)    # kurtosis (4 for Gaussian)\n'
         '    skew   = float(np.mean((x - mean)**3) / (m2**1.5 + 1e-30))\n'
         '    p2p    = float(np.max(x) - np.min(x))  # peak-to-peak\n'
         '    return {\n'
         '        "mean":         mean,\n'
         '        "std":          std,\n'
         '        "rms":          rms,\n'
         '        "peak":         peak,\n'
         '        "peak_to_peak": p2p,\n'
         '        "crest_factor": crest,\n'
         '        "kurtosis":     kurt,\n'
         '        "skewness":     skew,\n'
         '        "n_samples":    n,\n'
         '        "duration":     float(n * float(dt)),\n'
         '        "sample_rate":  float(1.0 / float(dt)),\n'
         '    }\n'
         'export = signal_statistics'
     )},

    {"name": "cross_correlation", "type": "R", "domain": "misc",
     "desc": "Normalized cross-correlation of two signals: lag at peak, max correlation",
     "tags": ["cross_correlation", "correlation", "lag", "signal", "delay", "alignment"],
     "source": (
         'def cross_correlation(signal_a, signal_b, dt=1.0, mode="full"):\n'
         '    """Normalized cross-correlation between two equal-length 1-D signals.\n'
         '    dt: sampling interval (s). mode: "full", "same", "valid".\n'
         '    Returns: lags (s), xcorr (normalized), lag_peak (s), corr_peak.\n'
         '    """\n'
         '    import numpy as np\n'
         '    a = np.asarray(signal_a, dtype=float)\n'
         '    b = np.asarray(signal_b, dtype=float)\n'
         '    a = (a - np.mean(a)) / (np.std(a) + 1e-30)\n'
         '    b = (b - np.mean(b)) / (np.std(b) + 1e-30)\n'
         '    corr = np.correlate(a, b, mode=str(mode))\n'
         '    corr = corr / (len(a))  # normalize\n'
         '    n_lag = len(corr)\n'
         '    lag_idx = np.arange(-(n_lag//2), n_lag - n_lag//2) if mode=="full" else np.arange(n_lag)\n'
         '    if mode == "full":\n'
         '        lag_idx = np.arange(-(len(a)-1), len(b))\n'
         '    lags = lag_idx * float(dt)\n'
         '    idx_peak = int(np.argmax(np.abs(corr)))\n'
         '    return {\n'
         '        "lags":      lags,\n'
         '        "xcorr":     corr,\n'
         '        "lag_peak":  float(lags[idx_peak]),\n'
         '        "corr_peak": float(corr[idx_peak]),\n'
         '        "n_samples": len(corr),\n'
         '    }\n'
         'export = cross_correlation'
     )},

    {"name": "welch_psd", "type": "R", "domain": "misc",
     "desc": "Welch method power spectral density (averaged periodogram, reduced variance)",
     "tags": ["welch", "psd", "power_spectral_density", "signal", "noise", "fft"],
     "source": (
         'def welch_psd(signal, dt=1.0, nperseg=256, noverlap=None, window="hann"):\n'
         '    """Welch averaged PSD of a 1-D signal.\n'
         '    dt: sampling interval (s). nperseg: segment length. noverlap: default nperseg//2.\n'
         '    Returns: freqs (Hz), psd (power/Hz), total_power, dominant_freq (Hz).\n'
         '    """\n'
         '    import numpy as np\n'
         '    from scipy.signal import welch\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    fs = 1.0 / float(dt)\n'
         '    seg = int(nperseg)\n'
         '    ovlp = seg // 2 if noverlap is None else int(noverlap)\n'
         '    wins = {"hann": "hann", "hamming": "hamming",\n'
         '            "blackman": "blackman", "none": "boxcar"}\n'
         '    win_str = wins.get(str(window).lower(), "hann")\n'
         '    f, Pxx = welch(x, fs=fs, window=win_str, nperseg=seg,\n'
         '                   noverlap=ovlp, scaling="density")\n'
         '    total_power = float(np.trapz(Pxx, f) if hasattr(np, "trapz") else np.trapezoid(Pxx, f))\n'
         '    idx_dom = int(np.argmax(Pxx[1:]) + 1)\n'
         '    return {\n'
         '        "freqs":         f,\n'
         '        "psd":           Pxx,\n'
         '        "total_power":   total_power,\n'
         '        "dominant_freq": float(f[idx_dom]),\n'
         '        "dominant_psd":  float(Pxx[idx_dom]),\n'
         '        "f_resolution":  float(f[1]) if len(f) > 1 else 0.0,\n'
         '    }\n'
         'export = welch_psd'
     )},

    {"name": "envelope_detection", "type": "R", "domain": "misc",
     "desc": "Hilbert-transform envelope, instantaneous frequency and phase of a signal",
     "tags": ["envelope", "hilbert", "instantaneous_frequency", "signal", "AM", "vibration"],
     "source": (
         'def envelope_detection(signal, dt=1.0):\n'
         '    """Analytic signal via Hilbert transform.\n'
         '    Returns: envelope (amplitude modulation), inst_freq (Hz),\n'
         '             inst_phase (rad), peak_envelope, mean_envelope.\n'
         '    """\n'
         '    import numpy as np\n'
         '    from scipy.signal import hilbert\n'
         '    x = np.asarray(signal, dtype=float)\n'
         '    analytic = hilbert(x)\n'
         '    envelope = np.abs(analytic)\n'
         '    phase    = np.unwrap(np.angle(analytic))\n'
         '    inst_freq = np.diff(phase) / (2.0 * np.pi * float(dt))\n'
         '    inst_freq = np.append(inst_freq, inst_freq[-1])  # same length\n'
         '    return {\n'
         '        "envelope":       envelope,\n'
         '        "inst_freq":      inst_freq,\n'
         '        "inst_phase":     phase,\n'
         '        "peak_envelope":  float(envelope.max()),\n'
         '        "mean_envelope":  float(envelope.mean()),\n'
         '        "n_samples":      len(x),\n'
         '    }\n'
         'export = envelope_detection'
     )},

    # ==================== COMPRESSIBLE DUCT FLOW ====================
    {"name": "fanno_flow", "type": "R", "domain": "aero.compressible",
     "desc": "Fanno flow (adiabatic, constant-area, with friction): sonic-reference ratios and 4fL*/D",
     "tags": ["compressible", "fanno", "friction", "duct"],
     "latex": r"\frac{4 f L^*}{D}=\frac{1-M^2}{\gamma M^2}+\frac{\gamma+1}{2\gamma}\ln\frac{(\gamma+1)M^2}{2+(\gamma-1)M^2}",
     "source":
'''import numpy as np
def fanno_flow(M, gamma=1.4):
    g = gamma; M2 = M * M
    T_Tstar = (g + 1) / (2 + (g - 1) * M2)
    P_Pstar = (1.0 / M) * T_Tstar ** 0.5
    rho_rhostar = (1.0 / M) * ((2 + (g - 1) * M2) / (g + 1)) ** 0.5
    P0_P0star = (1.0 / M) * ((2 + (g - 1) * M2) / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    fLD = (1 - M2) / (g * M2) + (g + 1) / (2 * g) * np.log((g + 1) * M2 / (2 + (g - 1) * M2))
    return {"T_Tstar": T_Tstar, "P_Pstar": P_Pstar, "rho_rhostar": rho_rhostar,
            "P0_P0star": P0_P0star, "fLD_max": fLD}
export = fanno_flow'''},
    {"name": "rayleigh_flow", "type": "R", "domain": "aero.compressible",
     "desc": "Rayleigh flow (frictionless, constant-area, with heat addition): sonic-reference ratios",
     "tags": ["compressible", "rayleigh", "heat_addition", "duct"],
     "latex": r"\frac{T_0}{T_0^*}=\frac{(\gamma+1)M^2\,[2+(\gamma-1)M^2]}{(1+\gamma M^2)^2},\quad \frac{P}{P^*}=\frac{1+\gamma}{1+\gamma M^2}",
     "source":
'''def rayleigh_flow(M, gamma=1.4):
    g = gamma; M2 = M * M; d = 1 + g * M2
    T0_T0star = ((g + 1) * M2 * (2 + (g - 1) * M2)) / d ** 2
    P_Pstar = (1 + g) / d
    T_Tstar = M2 * (1 + g) ** 2 / d ** 2
    P0_P0star = ((1 + g) / d) * ((2 + (g - 1) * M2) / (g + 1)) ** (g / (g - 1))
    V_Vstar = M2 * (1 + g) / d
    return {"T0_T0star": T0_T0star, "P_Pstar": P_Pstar, "T_Tstar": T_Tstar,
            "P0_P0star": P0_P0star, "V_Vstar": V_Vstar}
export = rayleigh_flow'''},
    {"name": "mach_angle", "type": "R", "domain": "aero.compressible",
     "desc": "Mach angle of a supersonic flow: mu = arcsin(1/M)",
     "tags": ["compressible", "mach", "wave_angle"],
     "latex": r"\mu = \arcsin\!\left(\frac{1}{M}\right)",
     "source":
'''import numpy as np
def mach_angle(M):
    mu = np.arcsin(1.0 / M) if M >= 1 else float("nan")
    return {"mu_rad": mu, "mu_deg": np.degrees(mu)}
export = mach_angle'''},

    # ==================== INTERNAL / PIPE FLOW ====================
    {"name": "colebrook_friction", "type": "R", "domain": "fluids",
     "desc": "Darcy friction factor from the implicit Colebrook equation (laminar branch below Re=2300)",
     "tags": ["fluids", "pipe", "friction", "colebrook", "moody"],
     "latex": r"\frac{1}{\sqrt{f}}=-2\log_{10}\!\left(\frac{\epsilon/D}{3.7}+\frac{2.51}{Re\sqrt{f}}\right)",
     "source":
'''import numpy as np
from anvil import solvers
def colebrook_friction(Re, rel_roughness=0.0):
    if Re < 2300:
        return {"f_darcy": 64.0 / Re, "regime": "laminar"}
    def resid(f):
        return 1.0 / f ** 0.5 + 2.0 * np.log10(rel_roughness / 3.7 + 2.51 / (Re * f ** 0.5))
    f = solvers.find_root(resid, bracket=(0.005, 0.15), method="brent")
    return {"f_darcy": f, "regime": "turbulent"}
export = colebrook_friction'''},
    {"name": "haaland_friction", "type": "R", "domain": "fluids",
     "desc": "Darcy friction factor from the explicit Haaland approximation to Colebrook",
     "tags": ["fluids", "pipe", "friction", "haaland"],
     "latex": r"\frac{1}{\sqrt{f}}=-1.8\log_{10}\!\left[\left(\frac{\epsilon/D}{3.7}\right)^{1.11}+\frac{6.9}{Re}\right]",
     "source":
'''import numpy as np
def haaland_friction(Re, rel_roughness=0.0):
    if Re < 2300:
        return {"f_darcy": 64.0 / Re}
    inv = -1.8 * np.log10((rel_roughness / 3.7) ** 1.11 + 6.9 / Re)
    return {"f_darcy": 1.0 / inv ** 2}
export = haaland_friction'''},
    {"name": "pipe_pressure_drop", "type": "R", "domain": "fluids",
     "desc": "Darcy-Weisbach pressure drop and head loss in a pipe",
     "tags": ["fluids", "pipe", "darcy_weisbach", "head_loss"],
     "latex": r"\Delta P=f\frac{L}{D}\frac{\rho V^2}{2},\quad h_L=\frac{\Delta P}{\rho g}",
     "source":
'''from anvil import Q
def pipe_pressure_drop(f_darcy, L, D, rho, V):
    dP = f_darcy * (L / D) * 0.5 * rho * V ** 2
    hL = dP / (rho * 9.80665)
    return {"dP": Q(dP, "Pa"), "head_loss": Q(hL, "m")}
export = pipe_pressure_drop'''},

    # ==================== HEAT TRANSFER (EXTENDED) ====================
    {"name": "dittus_boelter", "type": "R", "domain": "heat_transfer",
     "desc": "Dittus-Boelter correlation for turbulent internal convection Nusselt number and h",
     "tags": ["heat_transfer", "convection", "nusselt", "dittus_boelter"],
     "latex": r"Nu = 0.023\,Re^{0.8}Pr^{n},\quad n=0.4\ (\text{heating}),\ 0.3\ (\text{cooling})",
     "source":
'''from anvil import Q
def dittus_boelter(Re, Pr, k_fluid, D, heating=True):
    n = 0.4 if heating else 0.3
    Nu = 0.023 * Re ** 0.8 * Pr ** n
    h = Nu * k_fluid / D
    return {"Nu": Nu, "h_conv": Q(h, "W/m^2/K")}
export = dittus_boelter'''},
    {"name": "lmtd", "type": "R", "domain": "heat_transfer",
     "desc": "Log-mean temperature difference for counter- or parallel-flow heat exchangers",
     "tags": ["heat_transfer", "heat_exchanger", "lmtd"],
     "latex": r"\Delta T_{lm}=\frac{\Delta T_1-\Delta T_2}{\ln(\Delta T_1/\Delta T_2)}",
     "source":
'''import numpy as np
from anvil import Q
def lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out, flow="counter"):
    if flow == "counter":
        dT1 = T_hot_in - T_cold_out; dT2 = T_hot_out - T_cold_in
    else:
        dT1 = T_hot_in - T_cold_in; dT2 = T_hot_out - T_cold_out
    lm = dT1 if abs(dT1 - dT2) < 1e-9 else (dT1 - dT2) / np.log(dT1 / dT2)
    return {"LMTD": Q(lm, "K"), "dT1": Q(dT1, "K"), "dT2": Q(dT2, "K")}
export = lmtd'''},
    {"name": "biot_number", "type": "R", "domain": "heat_transfer",
     "desc": "Biot number and whether the lumped-capacitance assumption is valid (Bi < 0.1)",
     "tags": ["heat_transfer", "biot", "lumped", "transient"],
     "latex": r"Bi=\frac{h L_c}{k}",
     "source":
'''def biot_number(h_conv, L_char, k_solid):
    Bi = h_conv * L_char / k_solid
    return {"Bi": Bi, "lumped_valid": Bi < 0.1}
export = biot_number'''},
    {"name": "lumped_capacitance", "type": "R", "domain": "heat_transfer",
     "desc": "Transient lumped-capacitance cooling/heating: temperature at time t and time constant",
     "tags": ["heat_transfer", "transient", "lumped", "cooling"],
     "latex": r"T(t)=T_\infty+(T_0-T_\infty)e^{-t/\tau},\quad \tau=\frac{\rho V c_p}{h A_s}",
     "source":
'''import numpy as np
from anvil import Q
def lumped_capacitance(T0, T_inf, t, h_conv, A_surf, rho, V_vol, cp):
    tau = rho * V_vol * cp / (h_conv * A_surf)
    theta = np.exp(-t / tau)
    T = T_inf + (T0 - T_inf) * theta
    return {"T_t": Q(T, "K"), "tau": Q(tau, "s"), "theta": theta}
export = lumped_capacitance'''},

    # ==================== STRUCTURES (EXTENDED) ====================
    {"name": "torsion_circular_shaft", "type": "R", "domain": "structures",
     "desc": "Torsion of a solid/hollow circular shaft: max shear stress, polar moment, angle of twist",
     "tags": ["structures", "torsion", "shaft", "shear"],
     "latex": r"\tau_{max}=\frac{T r}{J},\quad J=\frac{\pi(d_o^4-d_i^4)}{32},\quad \phi=\frac{T L}{G J}",
     "source":
'''import numpy as np
from anvil import Q
def torsion_circular_shaft(torque, d_outer, L, G, d_inner=0.0):
    J = np.pi * (d_outer ** 4 - d_inner ** 4) / 32.0
    tau_max = torque * (d_outer / 2.0) / J
    phi = torque * L / (G * J)
    return {"tau_max": Q(tau_max, "Pa"), "J": J, "twist_rad": phi,
            "twist_deg": np.degrees(phi)}
export = torsion_circular_shaft'''},
    {"name": "principal_stresses_2d", "type": "R", "domain": "structures",
     "desc": "Plane-stress principal stresses, maximum shear and orientation (Mohr's circle)",
     "tags": ["structures", "stress", "principal", "mohr"],
     "latex": r"\sigma_{1,2}=\frac{\sigma_x+\sigma_y}{2}\pm\sqrt{\left(\frac{\sigma_x-\sigma_y}{2}\right)^2+\tau_{xy}^2}",
     "source":
'''import numpy as np
from anvil import Q
def principal_stresses_2d(sigma_x, sigma_y, tau_xy):
    avg = (sigma_x + sigma_y) / 2.0
    R = (((sigma_x - sigma_y) / 2.0) ** 2 + tau_xy ** 2) ** 0.5
    theta_p = 0.5 * np.degrees(np.arctan2(2 * tau_xy, sigma_x - sigma_y))
    return {"sigma_1": Q(avg + R, "Pa"), "sigma_2": Q(avg - R, "Pa"),
            "tau_max": Q(R, "Pa"), "theta_p_deg": theta_p}
export = principal_stresses_2d'''},
    {"name": "von_mises_stress", "type": "R", "domain": "structures",
     "desc": "Von Mises equivalent stress from a general 3D stress state",
     "tags": ["structures", "stress", "von_mises", "yield"],
     "latex": r"\sigma_{vm}=\sqrt{\tfrac{1}{2}\left[(\sigma_x-\sigma_y)^2+(\sigma_y-\sigma_z)^2+(\sigma_z-\sigma_x)^2+6(\tau_{xy}^2+\tau_{yz}^2+\tau_{zx}^2)\right]}",
     "source":
'''from anvil import Q
def von_mises_stress(sigma_x=0.0, sigma_y=0.0, sigma_z=0.0,
                     tau_xy=0.0, tau_yz=0.0, tau_zx=0.0):
    vm = (0.5 * ((sigma_x - sigma_y) ** 2 + (sigma_y - sigma_z) ** 2
                 + (sigma_z - sigma_x) ** 2
                 + 6 * (tau_xy ** 2 + tau_yz ** 2 + tau_zx ** 2))) ** 0.5
    return {"sigma_vm": Q(vm, "Pa")}
export = von_mises_stress'''},

    # ==================== THERMODYNAMIC CYCLES ====================
    {"name": "carnot_efficiency", "type": "R", "domain": "thermo",
     "desc": "Carnot efficiency and heat-pump/refrigerator coefficients of performance",
     "tags": ["thermo", "carnot", "efficiency", "cop"],
     "latex": r"\eta_{Carnot}=1-\frac{T_c}{T_h}",
     "source":
'''def carnot_efficiency(T_hot, T_cold):
    eta = 1.0 - T_cold / T_hot
    return {"eta_carnot": eta,
            "COP_heat_pump": T_hot / (T_hot - T_cold),
            "COP_refrigerator": T_cold / (T_hot - T_cold)}
export = carnot_efficiency'''},
    {"name": "brayton_ideal", "type": "R", "domain": "thermo",
     "desc": "Ideal (air-standard) Brayton cycle thermal efficiency, stage temperatures and back-work ratio",
     "tags": ["thermo", "brayton", "cycle", "gas_turbine"],
     "latex": r"\eta_{th}=1-\frac{1}{r_p^{(\gamma-1)/\gamma}}",
     "source":
'''from anvil import Q
def brayton_ideal(pressure_ratio, gamma=1.4, T_min=288.0, T_max=1600.0):
    x = pressure_ratio ** ((gamma - 1) / gamma)
    eta = 1.0 - 1.0 / x
    T2 = T_min * x; T4 = T_max / x
    return {"eta_thermal": eta, "T_compressor_out": Q(T2, "K"),
            "T_turbine_out": Q(T4, "K"),
            "back_work_ratio": (T2 - T_min) / (T_max - T4)}
export = brayton_ideal'''},
    {"name": "skin_friction_flat_plate", "type": "R", "domain": "aero",
     "desc": "Average skin-friction coefficient on a flat plate (laminar or turbulent, auto by Re)",
     "tags": ["aero", "skin_friction", "boundary_layer", "drag"],
     "latex": r"C_f=\frac{1.328}{\sqrt{Re_L}}\ (\text{laminar}),\quad C_f=\frac{0.074}{Re_L^{1/5}}\ (\text{turbulent})",
     "source":
'''def skin_friction_flat_plate(Re_L, regime="auto"):
    if regime == "auto":
        regime = "laminar" if Re_L < 5e5 else "turbulent"
    Cf = 1.328 / Re_L ** 0.5 if regime == "laminar" else 0.074 / Re_L ** 0.2
    return {"Cf": Cf, "regime": regime}
export = skin_friction_flat_plate'''},

    # ==================== DATA FITTING / REGRESSION ====================
    # Fit a model to (x, y) data. Inputs are named *_data so the web calculator
    # renders array widgets (and its CSV-column picker) for them.
    {"name": "linear_regression", "type": "R", "domain": "data.fitting",
     "desc": "Ordinary least-squares straight-line fit: slope, intercept, R-squared, residuals",
     "tags": ["data", "regression", "curve_fit", "least_squares"],
     "latex": r"y = m x + b,\quad R^2 = 1-\frac{\sum(y-\hat y)^2}{\sum(y-\bar y)^2}",
     "source":
'''import numpy as np
def linear_regression(x_data, y_data):
    x = np.asarray(x_data, float); y = np.asarray(y_data, float)
    A = np.vstack([x, np.ones(len(x))]).T
    (m, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = m * x + b
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"slope": float(m), "intercept": float(b), "r_squared": r2,
            "rmse": float((ss_res / len(x)) ** 0.5),
            "y_fit": yhat.tolist(), "residuals": (y - yhat).tolist()}
export = linear_regression'''},
    {"name": "poly_fit", "type": "R", "domain": "data.fitting",
     "desc": "Least-squares polynomial fit of a given degree: coefficients, R-squared, RMSE",
     "tags": ["data", "regression", "curve_fit", "polynomial"],
     "latex": r"y=\sum_{k=0}^{n} c_k x^{n-k}",
     "source":
'''import numpy as np
def poly_fit(x_data, y_data, degree=2):
    x = np.asarray(x_data, float); y = np.asarray(y_data, float)
    coeffs = np.polyfit(x, y, int(degree))
    yhat = np.polyval(coeffs, x)
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"coeffs": coeffs.tolist(), "r_squared": r2,
            "rmse": float((ss_res / len(x)) ** 0.5), "y_fit": yhat.tolist()}
export = poly_fit'''},
    {"name": "power_fit", "type": "R", "domain": "data.fitting",
     "desc": "Power-law fit y = a x^b via log-log least squares (x, y > 0)",
     "tags": ["data", "regression", "curve_fit", "power_law"],
     "latex": r"y = a\,x^{b}",
     "source":
'''import numpy as np
def power_fit(x_data, y_data):
    x = np.asarray(x_data, float); y = np.asarray(y_data, float)
    mask = (x > 0) & (y > 0)
    b, lna = np.polyfit(np.log(x[mask]), np.log(y[mask]), 1)
    a = float(np.exp(lna))
    yhat = a * x ** b
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"a": a, "b": float(b), "r_squared": r2, "y_fit": yhat.tolist()}
export = power_fit'''},
    {"name": "exp_fit", "type": "R", "domain": "data.fitting",
     "desc": "Exponential fit y = a exp(b x) via semi-log least squares (y > 0)",
     "tags": ["data", "regression", "curve_fit", "exponential"],
     "latex": r"y = a\,e^{b x}",
     "source":
'''import numpy as np
def exp_fit(x_data, y_data):
    x = np.asarray(x_data, float); y = np.asarray(y_data, float)
    mask = y > 0
    b, lna = np.polyfit(x[mask], np.log(y[mask]), 1)
    a = float(np.exp(lna))
    yhat = a * np.exp(b * x)
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return {"a": a, "b": float(b), "r_squared": r2, "y_fit": yhat.tolist()}
export = exp_fit'''},

    # ==================== PROPULSION: GAS-TURBINE CYCLE ====================
    # Station-by-station engine components (GasTurb style). Each maps an inlet
    # stagnation state to an exit stagnation state; the real, documented
    # implementations live in anvil/propulsion.py so they stay easy to read
    # and test. Wired into full engines by the *_cycle systems below.
    {"name": "ram_intake", "type": "R", "domain": "propulsion.cycle",
     "desc": "Intake ram compression, freestream to compressor face (station 0 to 2)",
     "tags": ["propulsion", "cycle", "intake", "ram", "gas_turbine"],
     "latex": r"T_{02}=T_a\left(1+\tfrac{\gamma-1}{2}M_0^2\right),\quad P_{02}=P_a\left(1+\eta_d\tfrac{\gamma-1}{2}M_0^2\right)^{\frac{\gamma}{\gamma-1}}",
     "source": "from anvil.propulsion import ram_intake\nexport = ram_intake"},
    {"name": "compressor", "type": "R", "domain": "propulsion.cycle",
     "desc": "Compressor with isentropic efficiency, station 2 to 3; returns exit state and specific work",
     "tags": ["propulsion", "cycle", "compressor", "gas_turbine"],
     "latex": r"T_{03}=T_{02}\left(1+\frac{\pi_c^{(\gamma-1)/\gamma}-1}{\eta_c}\right),\quad w_c=c_p(T_{03}-T_{02})",
     "source": "from anvil.propulsion import compressor\nexport = compressor"},
    {"name": "combustor", "type": "R", "domain": "propulsion.cycle",
     "desc": "Combustor at prescribed turbine inlet temperature; energy balance gives fuel-air ratio (station 3 to 4)",
     "tags": ["propulsion", "cycle", "combustor", "gas_turbine"],
     "latex": r"f=\frac{c_{p,h}T_{04}-c_{p,c}T_{03}}{\eta_b\,\mathrm{LHV}-c_{p,h}T_{04}}",
     "source": "from anvil.propulsion import combustor\nexport = combustor"},
    {"name": "turbine", "type": "R", "domain": "propulsion.cycle",
     "desc": "Turbine sized by work balance to drive the compressor (station 4 to 5)",
     "tags": ["propulsion", "cycle", "turbine", "gas_turbine"],
     "latex": r"w_t=\frac{w_c+w_{ext}}{\eta_m(1+f)},\quad T_{05}=T_{04}-\frac{w_t}{c_{p,h}}",
     "source": "from anvil.propulsion import turbine\nexport = turbine"},
    {"name": "nozzle", "type": "R", "domain": "propulsion.cycle",
     "desc": "Convergent nozzle with automatic choking detection (station 5 to 9)",
     "tags": ["propulsion", "cycle", "nozzle", "gas_turbine"],
     "latex": r"\mathrm{NPR}_{crit}=\left(\tfrac{\gamma+1}{2}\right)^{\frac{\gamma}{\gamma-1}};\ \text{choked if } P_{05}/P_a>\mathrm{NPR}_{crit}",
     "source": "from anvil.propulsion import nozzle\nexport = nozzle"},
    {"name": "thrust_performance", "type": "R", "domain": "propulsion.cycle",
     "desc": "Specific thrust, TSFC and thermal/propulsive/overall efficiencies for a core stream",
     "tags": ["propulsion", "cycle", "thrust", "tsfc", "efficiency"],
     "latex": r"F_s=(1+f)V_9-V_0+(1+f)\frac{R T_9}{V_9}\!\left(1-\frac{P_a}{P_9}\right),\quad \mathrm{TSFC}=\frac{f}{F_s}",
     "source": "from anvil.propulsion import thrust_performance\nexport = thrust_performance"},
    {"name": "fan", "type": "R", "domain": "propulsion.cycle",
     "desc": "Turbofan fan pressuring the full core+bypass flow (station 2 to 13)",
     "tags": ["propulsion", "cycle", "fan", "turbofan"],
     "source": "from anvil.propulsion import fan\nexport = fan"},
    {"name": "hp_compressor", "type": "R", "domain": "propulsion.cycle",
     "desc": "HP compressor, core flow only, station 13 to 3 (two-spool turbofan)",
     "tags": ["propulsion", "cycle", "compressor", "turbofan", "spool"],
     "source": "from anvil.propulsion import hp_compressor\nexport = hp_compressor"},
    {"name": "hp_turbine", "type": "R", "domain": "propulsion.cycle",
     "desc": "HP turbine driving the HP compressor / gas generator (station 4 to 45)",
     "tags": ["propulsion", "cycle", "turbine", "turbofan", "spool"],
     "source": "from anvil.propulsion import hp_turbine\nexport = hp_turbine"},
    {"name": "lp_turbine", "type": "R", "domain": "propulsion.cycle",
     "desc": "LP turbine driving the fan, accounts for bypass mass flow (station 45 to 5)",
     "tags": ["propulsion", "cycle", "turbine", "turbofan", "spool"],
     "source": "from anvil.propulsion import lp_turbine\nexport = lp_turbine"},
    {"name": "bypass_nozzle", "type": "R", "domain": "propulsion.cycle",
     "desc": "Cold bypass-duct nozzle for a turbofan (station 13 to 19)",
     "tags": ["propulsion", "cycle", "nozzle", "turbofan", "bypass"],
     "source": "from anvil.propulsion import bypass_nozzle\nexport = bypass_nozzle"},
    {"name": "turbofan_thrust", "type": "R", "domain": "propulsion.cycle",
     "desc": "Combined core+bypass specific thrust, TSFC and efficiencies for a turbofan",
     "tags": ["propulsion", "cycle", "thrust", "turbofan", "efficiency"],
     "source": "from anvil.propulsion import turbofan_thrust\nexport = turbofan_thrust"},
    {"name": "afterburner", "type": "R", "domain": "propulsion.cycle",
     "desc": "Afterburner / reheat to a target temperature; adds fuel (station 5 to 7)",
     "tags": ["propulsion", "cycle", "afterburner", "reheat"],
     "latex": r"f_{ab}=(1+f)\frac{c_{p,h}(T_{07}-T_{05})}{\eta_{ab}\,\mathrm{LHV}-c_{p,h}T_{07}}",
     "source": "from anvil.propulsion import afterburner\nexport = afterburner"},
    {"name": "power_turbine", "type": "R", "domain": "propulsion.cycle",
     "desc": "Free power turbine extracting shaft work for a turboprop/turboshaft (station 45 to 5)",
     "tags": ["propulsion", "cycle", "turbine", "turboprop", "turboshaft"],
     "source": "from anvil.propulsion import power_turbine\nexport = power_turbine"},
    {"name": "turboshaft_performance", "type": "R", "domain": "propulsion.cycle",
     "desc": "Shaft power, specific power and power-specific fuel consumption for a turboprop/turboshaft",
     "tags": ["propulsion", "cycle", "shaft_power", "turboprop", "psfc"],
     "source": "from anvil.propulsion import turboshaft_performance\nexport = turboshaft_performance"},

    # --- Full engine cycles (solvable Systems) ---
    {"name": "turbojet_cycle", "type": "S", "domain": "propulsion.cycle",
     "desc": "Single-spool turbojet: intake, compressor, combustor, turbine, nozzle, performance",
     "tags": ["propulsion", "cycle", "turbojet", "system", "gas_turbine"],
     "depends": ["ram_intake", "compressor", "combustor", "turbine", "nozzle",
                 "thrust_performance"],
     "source": "from anvil.propulsion import build_turbojet as build\nexport = build"},
    {"name": "turbojet_ab_cycle", "type": "S", "domain": "propulsion.cycle",
     "desc": "Turbojet with afterburner (reheat) between turbine and nozzle",
     "tags": ["propulsion", "cycle", "turbojet", "afterburner", "system"],
     "depends": ["ram_intake", "compressor", "combustor", "turbine",
                 "afterburner", "nozzle", "thrust_performance"],
     "source": "from anvil.propulsion import build_turbojet_ab as build\nexport = build"},
    {"name": "turbofan_cycle", "type": "S", "domain": "propulsion.cycle",
     "desc": "Two-spool separate-flow turbofan with fan, bypass duct and LP/HP spools",
     "tags": ["propulsion", "cycle", "turbofan", "bypass", "system"],
     "depends": ["ram_intake", "fan", "hp_compressor", "combustor", "hp_turbine",
                 "lp_turbine", "nozzle", "bypass_nozzle", "turbofan_thrust"],
     "source": "from anvil.propulsion import build_turbofan as build\nexport = build"},
    {"name": "turboprop_cycle", "type": "S", "domain": "propulsion.cycle",
     "desc": "Turboprop / turboshaft with a free power turbine driving a propeller or shaft",
     "tags": ["propulsion", "cycle", "turboprop", "turboshaft", "system"],
     "depends": ["ram_intake", "compressor", "combustor", "hp_turbine",
                 "power_turbine", "turboshaft_performance"],
     "source": "from anvil.propulsion import build_turboprop as build\nexport = build"},

    # --- Fundamental physics (authored via docs/RSQ_AUTHORING_PROMPT.md, all textbook-verified) ---
    {"name": "kinetic_energy", "type": "R", "domain": "physics.mechanics",
     "desc": "Translational kinetic energy of a moving mass",
     "tags": ["mechanics", "energy"],
     "latex": r"KE = \tfrac{1}{2} m v^2",
     "source": "def kinetic_energy(m, v):\n    m = float(m); v = float(v)\n    return {\"KE\": Q(0.5*m*v**2, \"J\")}\nexport = kinetic_energy"},
    {"name": "newton_gravitation", "type": "R", "domain": "physics.mechanics",
     "desc": "Newton gravitational force between two point masses",
     "tags": ["mechanics", "gravitation"],
     "latex": r"F = G \frac{m_1 m_2}{r^2}",
     "source": "def newton_gravitation(m1, m2, r):\n    G = 6.674e-11\n    m1 = float(m1); m2 = float(m2); r = float(r)\n    return {\"F_grav\": Q(G*m1*m2/r**2, \"N\")}\nexport = newton_gravitation"},
    {"name": "projectile_range", "type": "R", "domain": "physics.mechanics",
     "desc": "Range of a projectile launched over flat ground",
     "tags": ["mechanics", "kinematics"],
     "latex": r"R = \frac{v_0^2 \sin(2\theta)}{g}",
     "source": "def projectile_range(v0, angle_deg, g=9.81):\n    v0 = float(v0); g = float(g)\n    theta = _rad(angle_deg)\n    return {\"range\": Q(v0**2*math.sin(2.0*theta)/g, \"m\")}\nexport = projectile_range"},
    {"name": "pendulum_period", "type": "R", "domain": "physics.mechanics",
     "desc": "Small-angle period of a simple pendulum",
     "tags": ["mechanics", "oscillation"],
     "latex": r"T = 2\pi \sqrt{L/g}",
     "source": "def pendulum_period(L, g=9.81):\n    L = float(L); g = float(g)\n    return {\"period\": Q(2.0*math.pi*math.sqrt(L/g), \"s\")}\nexport = pendulum_period"},
    {"name": "coulomb_force", "type": "R", "domain": "physics.em",
     "desc": "Electrostatic force between two point charges in vacuum",
     "tags": ["em", "electrostatics"],
     "latex": r"F = \frac{1}{4\pi\varepsilon_0}\frac{q_1 q_2}{r^2}",
     "source": "def coulomb_force(q1, q2, r):\n    eps0 = 8.8541878128e-12\n    k = 1.0/(4.0*math.pi*eps0)\n    q1 = float(q1); q2 = float(q2); r = float(r)\n    return {\"F_coulomb\": Q(k*q1*q2/r**2, \"N\")}\nexport = coulomb_force"},
    {"name": "parallel_plate_capacitor_energy", "type": "R", "domain": "physics.em",
     "desc": "Stored energy of a vacuum parallel-plate capacitor from geometry and voltage",
     "tags": ["em", "capacitor", "energy"],
     "latex": r"U = \tfrac{1}{2} \frac{\varepsilon_0 A}{d} V^2",
     "source": "def parallel_plate_capacitor_energy(A, d, V):\n    eps0 = 8.8541878128e-12\n    A = float(A); d = float(d); V = float(V)\n    C = eps0*A/d\n    return {\"U_stored\": Q(0.5*C*V**2, \"J\")}\nexport = parallel_plate_capacitor_energy"},
    {"name": "lorentz_force_magnitude", "type": "R", "domain": "physics.em",
     "desc": "Magnitude of the magnetic Lorentz force on a moving charge",
     "tags": ["em", "magnetism"],
     "latex": r"F = q v B \sin\theta",
     "source": "def lorentz_force_magnitude(q, v, B, angle_deg=90.0):\n    q = float(q); v = float(v); B = float(B)\n    theta = _rad(angle_deg)\n    return {\"F_lorentz\": Q(abs(q)*v*B*math.sin(theta), \"N\")}\nexport = lorentz_force_magnitude"},
    {"name": "snell_refraction_angle", "type": "R", "domain": "physics.optics",
     "desc": "Refraction angle from Snell law at an interface",
     "tags": ["optics", "refraction"],
     "latex": r"n_1 \sin\theta_1 = n_2 \sin\theta_2",
     "source": "def snell_refraction_angle(n1, n2, theta1_deg):\n    n1 = float(n1); n2 = float(n2)\n    t1 = _rad(theta1_deg)\n    s = n1*math.sin(t1)/n2\n    if abs(s) > 1.0:\n        return {\"theta2_deg\": float('nan'), \"theta2_rad\": float('nan'), \"total_internal_reflection\": 1.0}\n    t2 = math.asin(s)\n    return {\"theta2_deg\": math.degrees(t2), \"theta2_rad\": t2, \"total_internal_reflection\": 0.0}\nexport = snell_refraction_angle"},
    {"name": "thin_lens_image_distance", "type": "R", "domain": "physics.optics",
     "desc": "Image distance from the thin lens equation",
     "tags": ["optics", "lens"],
     "latex": r"\frac{1}{f} = \frac{1}{d_o} + \frac{1}{d_i}",
     "source": "def thin_lens_image_distance(f, d_o):\n    f = float(f); d_o = float(d_o)\n    inv = 1.0/f - 1.0/d_o\n    d_i = float('inf') if inv == 0 else 1.0/inv\n    return {\"d_i\": Q(d_i, \"m\")}\nexport = thin_lens_image_distance"},
    {"name": "photon_energy_frequency", "type": "R", "domain": "physics.optics",
     "desc": "Photon energy from its frequency",
     "tags": ["optics", "quantum", "photon"],
     "latex": r"E = h f",
     "source": "def photon_energy_frequency(f):\n    h = 6.62607015e-34\n    f = float(f)\n    return {\"E_photon\": Q(h*f, \"J\")}\nexport = photon_energy_frequency"},
    {"name": "wave_speed", "type": "R", "domain": "physics.waves",
     "desc": "Wave propagation speed from frequency and wavelength",
     "tags": ["waves"],
     "latex": r"v = f \lambda",
     "source": "def wave_speed(frequency, wavelength):\n    frequency = float(frequency); wavelength = float(wavelength)\n    return {\"speed\": Q(frequency*wavelength, \"m/s\")}\nexport = wave_speed"},
    {"name": "relativistic_doppler_shift", "type": "R", "domain": "physics.waves",
     "desc": "Relativistic Doppler observed frequency for radial source motion",
     "tags": ["waves", "relativity", "doppler"],
     "latex": r"f_{obs} = f_{src} \sqrt{\frac{1+\beta}{1-\beta}}",
     "source": "def relativistic_doppler_shift(f_src, v_radial):\n    c = 2.99792458e8\n    f_src = float(f_src); v = float(v_radial)\n    beta = v/c\n    factor = math.sqrt((1.0+beta)/(1.0-beta))\n    return {\"f_obs\": Q(f_src*factor, \"Hz\"), \"shift_factor\": factor}\nexport = relativistic_doppler_shift"},
    {"name": "lorentz_factor", "type": "R", "domain": "physics.relativity",
     "desc": "Lorentz factor gamma for a given speed",
     "tags": ["relativity"],
     "latex": r"\gamma = \frac{1}{\sqrt{1-(v/c)^2}}",
     "source": "def lorentz_factor(v):\n    c = 2.99792458e8\n    v = float(v)\n    beta = v/c\n    return {\"gamma\": 1.0/math.sqrt(1.0-beta**2)}\nexport = lorentz_factor"},
    {"name": "mass_energy_equivalence", "type": "R", "domain": "physics.relativity",
     "desc": "Rest energy from mass-energy equivalence",
     "tags": ["relativity", "energy"],
     "latex": r"E = m c^2",
     "source": "def mass_energy_equivalence(m):\n    c = 2.99792458e8\n    m = float(m)\n    return {\"E_rest\": Q(m*c**2, \"J\")}\nexport = mass_energy_equivalence"},
    {"name": "de_broglie_wavelength", "type": "R", "domain": "physics.quantum",
     "desc": "de Broglie wavelength from momentum",
     "tags": ["quantum", "wave"],
     "latex": r"\lambda = h/p",
     "source": "def de_broglie_wavelength(p):\n    h = 6.62607015e-34\n    p = float(p)\n    return {\"wavelength\": Q(h/p, \"m\")}\nexport = de_broglie_wavelength"},
    {"name": "wien_peak_wavelength", "type": "R", "domain": "physics.quantum",
     "desc": "Peak emission wavelength of a blackbody from Wien displacement law",
     "tags": ["quantum", "thermal", "blackbody"],
     "latex": r"\lambda_{peak} = b/T",
     "source": "def wien_peak_wavelength(T):\n    b = 2.897771955e-3\n    T = float(T)\n    return {\"lambda_peak\": Q(b/T, \"m\")}\nexport = wien_peak_wavelength"},

    # --- Chemistry (authored via docs/RSQ_AUTHORING_PROMPT.md, all textbook-verified) ---
    {"name": "moles_from_mass", "type": "R", "domain": "chemistry.stoichiometry",
     "desc": "Amount of substance from sample mass and molar mass, n = m / M",
     "tags": ["stoichiometry", "moles", "mass"],
     "latex": r"n = \frac{m}{M}",
     "source": 'from anvil import Q\ndef moles_from_mass(m, M):\n    m = float(m); M = float(M)\n    n = m / M if M != 0.0 else float(\'inf\')\n    return {"n": Q(n, "mol")}\nexport = moles_from_mass'},
    {"name": "percent_yield", "type": "R", "domain": "chemistry.stoichiometry",
     "desc": "Percent yield from actual and theoretical amount of product",
     "tags": ["stoichiometry", "yield"],
     "latex": r"\%\,\text{yield} = \frac{n_\text{actual}}{n_\text{theoretical}}\times 100",
     "source": 'def percent_yield(actual, theoretical):\n    a = float(actual); t = float(theoretical)\n    pct = 100.0 * a / t if t != 0.0 else float(\'inf\')\n    return {"percent_yield": pct}\nexport = percent_yield'},
    {"name": "molarity", "type": "R", "domain": "chemistry.stoichiometry",
     "desc": "Molar concentration from moles of solute and solution volume, c = n / V (SI mol per m^3)",
     "tags": ["stoichiometry", "concentration", "molarity"],
     "latex": r"c = \frac{n}{V}",
     "source": 'from anvil import Q\ndef molarity(n, V):\n    n = float(n); V = float(V)\n    c = n / V if V != 0.0 else float(\'inf\')\n    return {"c": Q(c, "mol/m^3"), "c_molar": c / 1000.0}\nexport = molarity'},
    {"name": "moles_ideal_gas", "type": "R", "domain": "chemistry.gas",
     "desc": "Moles of an ideal gas from PV = nRT, solved for n",
     "tags": ["gas", "ideal-gas", "moles"],
     "latex": r"n = \frac{PV}{RT}",
     "source": 'from anvil import Q\ndef moles_ideal_gas(P, V, T):\n    P = float(P); V = float(V); T = float(T)\n    R = 8.314462618\n    n = P * V / (R * T) if T != 0.0 else float(\'inf\')\n    return {"n": Q(n, "mol")}\nexport = moles_ideal_gas'},
    {"name": "combined_gas_law", "type": "R", "domain": "chemistry.gas",
     "desc": "Final volume of a fixed gas sample from P1 V1 / T1 = P2 V2 / T2, solved for V2",
     "tags": ["gas", "combined-gas-law", "state-change"],
     "latex": r"V_2 = \frac{P_1 V_1 T_2}{T_1 P_2}",
     "source": 'from anvil import Q\ndef combined_gas_law(P1, V1, T1, P2, T2):\n    P1 = float(P1); V1 = float(V1); T1 = float(T1); P2 = float(P2); T2 = float(T2)\n    denom = T1 * P2\n    V2 = P1 * V1 * T2 / denom if denom != 0.0 else float(\'inf\')\n    return {"V2": Q(V2, "m^3")}\nexport = combined_gas_law'},
    {"name": "dilution", "type": "R", "domain": "chemistry.solution",
     "desc": "Final volume from the dilution relation M1 V1 = M2 V2, solved for V2",
     "tags": ["solution", "dilution"],
     "latex": r"V_2 = \frac{M_1 V_1}{M_2}",
     "source": 'from anvil import Q\ndef dilution(M1, V1, M2):\n    M1 = float(M1); V1 = float(V1); M2 = float(M2)\n    V2 = M1 * V1 / M2 if M2 != 0.0 else float(\'inf\')\n    return {"V2": Q(V2, "m^3")}\nexport = dilution'},
    {"name": "beer_lambert_absorbance", "type": "R", "domain": "chemistry.solution",
     "desc": "Absorbance from Beer-Lambert law A = eps l c (eps in m^2/mol, l in m, c in mol/m^3), dimensionless",
     "tags": ["solution", "spectroscopy", "beer-lambert"],
     "latex": r"A = \varepsilon\, l\, c",
     "source": 'def beer_lambert_absorbance(eps, l, c):\n    eps = float(eps); l = float(l); c = float(c)\n    return {"A": eps * l * c}\nexport = beer_lambert_absorbance'},
    {"name": "freezing_point_depression", "type": "R", "domain": "chemistry.solution.colligative",
     "desc": "Freezing point depression dTf = i Kf m (Kf in K kg/mol, m in mol/kg)",
     "tags": ["solution", "colligative", "freezing-point"],
     "latex": r"\Delta T_f = i\, K_f\, m",
     "source": 'from anvil import Q\ndef freezing_point_depression(i, Kf, m):\n    i = float(i); Kf = float(Kf); m = float(m)\n    return {"dTf": Q(i * Kf * m, "K")}\nexport = freezing_point_depression'},
    {"name": "osmotic_pressure", "type": "R", "domain": "chemistry.solution.colligative",
     "desc": "Osmotic pressure Pi = i M R T (M in mol/m^3, T in K), result in Pa",
     "tags": ["solution", "colligative", "osmosis"],
     "latex": r"\Pi = i\, M\, R\, T",
     "source": 'from anvil import Q\ndef osmotic_pressure(i, M, T):\n    i = float(i); M = float(M); T = float(T)\n    R = 8.314462618\n    return {"Pi": Q(i * M * R * T, "Pa")}\nexport = osmotic_pressure'},
    {"name": "raoult_vapor_pressure", "type": "R", "domain": "chemistry.solution.colligative",
     "desc": "Solution vapor pressure from Raoult law P = x_solvent P_pure",
     "tags": ["solution", "colligative", "raoult", "vapor-pressure"],
     "latex": r"P = x_\text{solvent}\, P^{*}",
     "source": 'from anvil import Q\ndef raoult_vapor_pressure(x_solvent, P_pure):\n    x = float(x_solvent); Pp = float(P_pure)\n    return {"P": Q(x * Pp, "Pa")}\nexport = raoult_vapor_pressure'},
    {"name": "gibbs_free_energy", "type": "R", "domain": "chemistry.thermo",
     "desc": "Gibbs free energy change dG = dH - T dS (dH in J/mol, dS in J/mol/K), result in J/mol",
     "tags": ["thermo", "gibbs", "spontaneity"],
     "latex": r"\Delta G = \Delta H - T\,\Delta S",
     "source": 'from anvil import Q\ndef gibbs_free_energy(dH, T, dS):\n    dH = float(dH); T = float(T); dS = float(dS)\n    return {"dG": Q(dH - T * dS, "J/mol")}\nexport = gibbs_free_energy'},
    {"name": "gibbs_from_equilibrium_constant", "type": "R", "domain": "chemistry.thermo",
     "desc": "Standard Gibbs free energy from equilibrium constant, dG = -R T ln K",
     "tags": ["thermo", "gibbs", "equilibrium"],
     "latex": r"\Delta G^{\circ} = -R T \ln K",
     "source": 'from anvil import Q\ndef gibbs_from_equilibrium_constant(K, T):\n    K = float(K); T = float(T)\n    R = 8.314462618\n    dG = -R * T * math.log(K) if K > 0.0 else float(\'nan\')\n    return {"dG": Q(dG, "J/mol")}\nexport = gibbs_from_equilibrium_constant'},
    {"name": "arrhenius_rate_constant", "type": "R", "domain": "chemistry.kinetics",
     "desc": "Rate constant from the Arrhenius equation k = A exp(-Ea/(R T)) (Ea in J/mol), first-order units s^-1",
     "tags": ["kinetics", "arrhenius", "rate-constant"],
     "latex": r"k = A\, e^{-E_a/(R T)}",
     "source": 'from anvil import Q\ndef arrhenius_rate_constant(A, Ea, T):\n    A = float(A); Ea = float(Ea); T = float(T)\n    R = 8.314462618\n    k = A * math.exp(-Ea / (R * T)) if T != 0.0 else float(\'inf\')\n    return {"k": Q(k, "s^-1")}\nexport = arrhenius_rate_constant'},
    {"name": "first_order_half_life", "type": "R", "domain": "chemistry.kinetics",
     "desc": "Half-life of a first-order reaction t_half = ln 2 / k (k in s^-1), result in s",
     "tags": ["kinetics", "half-life", "first-order"],
     "latex": r"t_{1/2} = \frac{\ln 2}{k}",
     "source": 'from anvil import Q\ndef first_order_half_life(k):\n    k = float(k)\n    t = math.log(2.0) / k if k != 0.0 else float(\'inf\')\n    return {"t_half": Q(t, "s")}\nexport = first_order_half_life'},
    {"name": "equilibrium_constant_from_gibbs", "type": "R", "domain": "chemistry.equilibrium",
     "desc": "Equilibrium constant from standard Gibbs energy, K = exp(-dG/(R T)), dimensionless",
     "tags": ["equilibrium", "gibbs", "equilibrium-constant"],
     "latex": r"K = e^{-\Delta G^{\circ}/(R T)}",
     "source": 'def equilibrium_constant_from_gibbs(dG, T):\n    dG = float(dG); T = float(T)\n    R = 8.314462618\n    K = math.exp(-dG / (R * T)) if T != 0.0 else float(\'inf\')\n    return {"K": K}\nexport = equilibrium_constant_from_gibbs'},
    {"name": "nernst_cell_potential", "type": "R", "domain": "chemistry.electro",
     "desc": "Cell potential from the Nernst equation E = E0 - (R T/(n F)) ln Q (E0 in V), result in V",
     "tags": ["electro", "nernst", "cell-potential"],
     "latex": r"E = E^{0} - \frac{R T}{n F}\ln Q",
     "source": 'from anvil import Q\ndef nernst_cell_potential(E0, n, T, Q_rxn):\n    E0 = float(E0); n = float(n); T = float(T); Qr = float(Q_rxn)\n    R = 8.314462618; F = 96485.332\n    if n == 0.0 or Qr <= 0.0:\n        return {"E": Q(float(\'nan\'), "V")}\n    E = E0 - (R * T / (n * F)) * math.log(Qr)\n    return {"E": Q(E, "V")}\nexport = nernst_cell_potential'},
    {"name": "ph_from_concentration", "type": "R", "domain": "chemistry.acidbase",
     "desc": "pH from hydronium ion concentration, pH = -log10[H+] (concentration in mol/L), dimensionless",
     "tags": ["acidbase", "ph"],
     "latex": r"\mathrm{pH} = -\log_{10}[\mathrm{H}^+]",
     "source": 'def ph_from_concentration(H_conc):\n    h = float(H_conc)\n    pH = -math.log10(h) if h > 0.0 else float(\'inf\')\n    return {"pH": pH}\nexport = ph_from_concentration'},
    {"name": "henderson_hasselbalch", "type": "R", "domain": "chemistry.acidbase",
     "desc": "Buffer pH from the Henderson-Hasselbalch equation pH = pKa + log10([A-]/[HA])",
     "tags": ["acidbase", "buffer", "henderson-hasselbalch"],
     "latex": r"\mathrm{pH} = \mathrm{p}K_a + \log_{10}\!\frac{[\mathrm{A}^-]}{[\mathrm{HA}]}",
     "source": 'def henderson_hasselbalch(pKa, conc_base, conc_acid):\n    pKa = float(pKa); cb = float(conc_base); ca = float(conc_acid)\n    if ca <= 0.0 or cb <= 0.0:\n        return {"pH": float(\'nan\')}\n    pH = pKa + math.log10(cb / ca)\n    return {"pH": pH}\nexport = henderson_hasselbalch'},
]
