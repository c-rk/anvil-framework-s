"""
Fundamental Physics RSQs
========================

A tour of the physics relation pack: mechanics, electromagnetism, optics,
waves, relativity and quantum. Each is a native Anvil RSQ called directly
through ``anvil.R.*`` with unit-aware inputs and outputs.

These RSQs were authored with an LLM using docs/RSQ_AUTHORING_PROMPT.md and
validated against textbook values before seeding.
"""

import anvil

print("=" * 60)
print("  Mechanics")
print("=" * 60)
print(f"  Kinetic energy (2 kg at 3 m/s) : {anvil.R.kinetic_energy(m=2, v=3)['KE']}")
print(f"  Gravity (Earth on 1 kg at surface): "
      f"{anvil.R.newton_gravitation(m1=5.972e24, m2=1, r=6.371e6)['F_grav']}")
print(f"  Projectile range (10 m/s, 45 deg): "
      f"{anvil.R.projectile_range(v0=10, angle_deg=45)['range']}")
print(f"  Pendulum period (1 m)          : {anvil.R.pendulum_period(L=1)['period']}")

print("\n" + "=" * 60)
print("  Electromagnetism")
print("=" * 60)
print(f"  Coulomb force (2x 1 uC at 0.1 m): "
      f"{anvil.R.coulomb_force(q1=1e-6, q2=1e-6, r=0.1)['F_coulomb']}")
print(f"  Capacitor energy (1 m^2, 1 mm, 100 V): "
      f"{anvil.R.parallel_plate_capacitor_energy(A=1, d=1e-3, V=100)['U_stored']}")
print(f"  Lorentz force (proton, 1e6 m/s, 0.5 T): "
      f"{anvil.R.lorentz_force_magnitude(q=1.602176634e-19, v=1e6, B=0.5)['F_lorentz']}")

print("\n" + "=" * 60)
print("  Optics")
print("=" * 60)
snell = anvil.R.snell_refraction_angle(n1=1, n2=1.5, theta1_deg=30)
print(f"  Snell refraction (30 deg into glass): {snell['theta2_deg']:.3f} deg")
print(f"  Thin lens image (f=0.1, d_o=0.3): "
      f"{anvil.R.thin_lens_image_distance(f=0.1, d_o=0.3)['d_i']}")
print(f"  Photon energy (green, 5.5e14 Hz): "
      f"{anvil.R.photon_energy_frequency(f=5.5e14)['E_photon']}")

print("\n" + "=" * 60)
print("  Waves and relativity")
print("=" * 60)
print(f"  Wave speed (100 Hz, 3.4 m)     : {anvil.R.wave_speed(frequency=100, wavelength=3.4)['speed']}")
dop = anvil.R.relativistic_doppler_shift(f_src=1e9, v_radial=2.99792458e7)
print(f"  Relativistic Doppler (approach 0.1c): {dop['f_obs']} (x{dop['shift_factor']:.4f})")
print(f"  Lorentz factor (0.6c)          : {anvil.R.lorentz_factor(v=0.6 * 2.99792458e8)['gamma']:.4f}")
print(f"  Rest energy of 1 kg            : {anvil.R.mass_energy_equivalence(m=1)['E_rest']}")

print("\n" + "=" * 60)
print("  Quantum")
print("=" * 60)
print(f"  de Broglie wavelength (p=1e-24): "
      f"{anvil.R.de_broglie_wavelength(p=1e-24)['wavelength']}")
print(f"  Wien peak (Sun, 5778 K)        : "
      f"{anvil.R.wien_peak_wavelength(T=5778)['lambda_peak']}")
