# Chemistry

A pack of general-chemistry relations spanning stoichiometry, gas laws, solutions and colligative
properties, thermodynamics, kinetics, equilibrium, electrochemistry and acid-base. Each is a native
RSQ reachable at `anvil.R.<name>` or by domain at `anvil.R.chemistry.<subdomain>.<name>`.

Authored with an LLM using the workflow in `docs/RSQ_AUTHORING_PROMPT.md` and validated against
textbook values before seeding.

```python
import anvil

anvil.R.ph_from_concentration(H_conc=1e-7)              # {"pH": 7.0}
anvil.R.moles_ideal_gas(P=101325, V=0.0224, T=273.15)  # ~1 mol at STP
anvil.R.gibbs_free_energy(dH=-1e5, T=298.15, dS=-100)   # {"dG": -70185 J/mol}
```

## Unit convention

Outputs use SI. In particular **dimensioned concentration is `mol/m^3`**, so a `0.25 M` solution is
`250 mol/m^3`. `molarity` additionally returns a `c_molar` convenience value in mol/L. Where a
concentration only enters a ratio or a logarithm (pH, Henderson-Hasselbalch, dilution) it is a
unit-agnostic plain-float input, and the assumed unit is noted in the relation description.

## Stoichiometry (`chemistry.stoichiometry`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `moles_from_mass` | m, M | n | `n = m / M` |
| `percent_yield` | actual, theoretical | percent_yield | `100 actual / theoretical` |
| `molarity` | n, V | c, c_molar | `c = n / V` |

## Gas laws (`chemistry.gas`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `moles_ideal_gas` | P, V, T | n | `n = P V / (R T)` |
| `combined_gas_law` | P1, V1, T1, P2, T2 | V2 | `P1 V1 / T1 = P2 V2 / T2` |

## Solutions (`chemistry.solution`, `chemistry.solution.colligative`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `dilution` | M1, V1, M2 | V2 | `M1 V1 = M2 V2` |
| `beer_lambert_absorbance` | eps, l, c | A | `A = eps l c` |
| `freezing_point_depression` | i, Kf, m | dTf | `dTf = i Kf m` |
| `osmotic_pressure` | i, M, T | Pi | `Pi = i M R T` |
| `raoult_vapor_pressure` | x_solvent, P_pure | P | `P = x P_pure` |

## Thermodynamics and equilibrium (`chemistry.thermo`, `chemistry.equilibrium`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `gibbs_free_energy` | dH, T, dS | dG | `dG = dH - T dS` |
| `gibbs_from_equilibrium_constant` | K, T | dG | `dG = -R T ln K` |
| `equilibrium_constant_from_gibbs` | dG, T | K | `K = exp(-dG / R T)` |

## Kinetics (`chemistry.kinetics`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `arrhenius_rate_constant` | A, Ea, T | k | `k = A exp(-Ea / R T)` |
| `first_order_half_life` | k | t_half | `t = ln 2 / k` |

## Electrochemistry and acid-base (`chemistry.electro`, `chemistry.acidbase`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `nernst_cell_potential` | E0, n, T, Q_rxn | E | `E = E0 - (R T / n F) ln Q` |
| `ph_from_concentration` | H_conc | pH | `pH = -log10[H+]` |
| `henderson_hasselbalch` | pKa, conc_base, conc_acid | pH | `pH = pKa + log10([A-]/[HA])` |

## Notes

- Constants (`R`, Faraday `F`) are baked in as SI literals, so no constant inputs are needed.
- Log and reciprocal relations guard their domain: `gibbs_from_equilibrium_constant` returns NaN for
  `K <= 0`, `nernst_cell_potential` for `Q <= 0`, and the rate/half-life relations return infinity at
  the zero-rate limit instead of raising.
- Run `examples/ex_chemistry.py` for a full tour with computed values.
