"""
Chemistry RSQs
==============

A tour of the chemistry relation pack: stoichiometry, gas laws, solutions,
colligative properties, thermodynamics, kinetics, equilibrium, electrochemistry
and acid-base. Each is a native Anvil RSQ called through ``anvil.R.*``.

SI convention: dimensioned concentrations are mol/m^3, so 0.25 M reads as
250 mol/m^3. These RSQs were authored with an LLM using
docs/RSQ_AUTHORING_PROMPT.md and validated against textbook values.
"""

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
