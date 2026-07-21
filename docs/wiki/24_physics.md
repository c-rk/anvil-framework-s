# Physics

A pack of fundamental-physics relations spanning mechanics, electromagnetism, optics, waves,
relativity and quantum. Each is a native RSQ with unit-aware inputs and outputs, reachable at
`anvil.R.<name>` or by domain at `anvil.R.physics.<subdomain>.<name>`.

These relations were authored with an LLM using the workflow in `docs/RSQ_AUTHORING_PROMPT.md` and
validated against textbook values before being seeded, a worked demonstration of that pipeline.

```python
import anvil

anvil.R.kinetic_energy(m=2, v=3)                       # {"KE": 9.0 J}
anvil.R.mass_energy_equivalence(m=1)                   # {"E_rest": 8.99e16 J}
anvil.R.snell_refraction_angle(n1=1, n2=1.5, theta1_deg=30)  # 19.47 deg
```

## Mechanics (`physics.mechanics`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `kinetic_energy` | m, v | KE | `KE = 1/2 m v^2` |
| `newton_gravitation` | m1, m2, r | F_grav | `F = G m1 m2 / r^2` |
| `projectile_range` | v0, angle_deg, g=9.81 | range | `R = v0^2 sin(2 theta) / g` |
| `pendulum_period` | L, g=9.81 | period | `T = 2 pi sqrt(L/g)` |

## Electromagnetism (`physics.em`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `coulomb_force` | q1, q2, r | F_coulomb | `F = q1 q2 / (4 pi eps0 r^2)` |
| `parallel_plate_capacitor_energy` | A, d, V | U_stored | `U = 1/2 (eps0 A / d) V^2` |
| `lorentz_force_magnitude` | q, v, B, angle_deg=90 | F_lorentz | `F = q v B sin(theta)` |

## Optics (`physics.optics`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `snell_refraction_angle` | n1, n2, theta1_deg | theta2_deg, theta2_rad, total_internal_reflection | `n1 sin(theta1) = n2 sin(theta2)` |
| `thin_lens_image_distance` | f, d_o | d_i | `1/f = 1/d_o + 1/d_i` |
| `photon_energy_frequency` | f | E_photon | `E = h f` |

`snell_refraction_angle` flags total internal reflection (returns `total_internal_reflection = 1.0`
and NaN angles) past the critical angle. `thin_lens_image_distance` returns an infinite image
distance when the object sits at the focal point (`d_o = f`) instead of raising.

## Waves (`physics.waves`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `wave_speed` | frequency, wavelength | speed | `v = f lambda` |
| `relativistic_doppler_shift` | f_src, v_radial | f_obs, shift_factor | `f_obs = f_src sqrt((1+beta)/(1-beta))` |

## Relativity (`physics.relativity`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `lorentz_factor` | v | gamma | `gamma = 1 / sqrt(1 - (v/c)^2)` |
| `mass_energy_equivalence` | m | E_rest | `E = m c^2` |

## Quantum (`physics.quantum`)

| Name | Inputs | Outputs | Relation |
|------|--------|---------|----------|
| `de_broglie_wavelength` | p | wavelength | `lambda = h / p` |
| `wien_peak_wavelength` | T | lambda_peak | `lambda_peak = b / T` |

## Notes

- Physical constants (`c`, `G`, `h`, `eps0`, Wien `b`, ...) are baked into each relation as SI
  literals, so no constant inputs are required.
- Angle inputs are named `*_deg` and taken in degrees; outputs carry SI units (`J`, `N`, `m`, `s`,
  `m/s`, `Hz`) except for dimensionless results (`gamma`, refraction angles, `shift_factor`).
- Run `examples/ex_physics.py` for a full tour with computed values.
