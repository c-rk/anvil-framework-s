"""
Extended Engineering RSQs
=========================

Demonstrates the extended relation pack that fills common gaps across
compressible flow, internal flow, heat transfer, structures and cycles.
Every relation is a native RSQ, called directly through ``anvil.R.*`` with
unit-aware inputs.

Demonstrates:
    - Compressible duct flow: Fanno, Rayleigh, Mach angle
    - Internal flow: Colebrook and Haaland friction, pipe pressure drop
    - External flow: flat-plate skin friction
    - Heat transfer: Dittus-Boelter, LMTD, Biot number, lumped capacitance
    - Structures: shaft torsion, plane-stress principal stresses, von Mises
    - Cycles: Carnot efficiency, ideal Brayton
"""

import anvil

print("=" * 60)
print("  Compressible duct flow")
print("=" * 60)

fanno = anvil.R.fanno_flow(M=2.0, gamma=1.4)
print(f"  Fanno   M=2.0 : fL*/D_max = {fanno['fLD_max']:.4f}, "
      f"T/T* = {fanno['T_Tstar']:.4f}")

rayleigh = anvil.R.rayleigh_flow(M=0.5, gamma=1.4)
print(f"  Rayleigh M=0.5: T0/T0* = {rayleigh['T0_T0star']:.4f}, "
      f"P/P* = {rayleigh['P_Pstar']:.4f}")

mu = anvil.R.mach_angle(M=2.0)
print(f"  Mach angle M=2.0 : mu = {mu['mu_deg']:.3f} deg")

print("\n" + "=" * 60)
print("  Internal and external flow")
print("=" * 60)

cole = anvil.R.colebrook_friction(Re=1e5, rel_roughness=0.001)
haal = anvil.R.haaland_friction(Re=1e5, rel_roughness=0.001)
print(f"  Darcy friction (Re=1e5, e/D=0.001):")
print(f"    Colebrook (implicit) = {cole['f_darcy']:.5f}  [{cole['regime']}]")
print(f"    Haaland   (explicit) = {haal['f_darcy']:.5f}")

dp = anvil.R.pipe_pressure_drop(f_darcy=cole["f_darcy"], L=50, D=0.1,
                                rho=998, V=2.0)
print(f"  Pipe drop (50 m, D=0.1 m, water @ 2 m/s): "
      f"dP = {dp['dP']}, head = {dp['head_loss']}")

cf = anvil.R.skin_friction_flat_plate(Re_L=1e6, regime="auto")
print(f"  Flat-plate skin friction (Re_L=1e6): Cf = {cf['Cf']:.5f} "
      f"[{cf['regime']}]")

print("\n" + "=" * 60)
print("  Heat transfer")
print("=" * 60)

db = anvil.R.dittus_boelter(Re=1e5, Pr=0.7, k_fluid=0.026, D=0.05,
                            heating=True)
print(f"  Dittus-Boelter (air in tube): Nu = {db['Nu']:.1f}, "
      f"h = {db['h_conv']}")

hx = anvil.R.lmtd(T_hot_in=150, T_hot_out=90, T_cold_in=30, T_cold_out=70,
                  flow="counter")
print(f"  LMTD (counterflow): {hx['LMTD']}")

bi = anvil.R.biot_number(h_conv=50, L_char=0.01, k_solid=200)
print(f"  Biot number: Bi = {bi['Bi']:.4f} "
      f"(lumped valid = {bi['lumped_valid']})")

lc = anvil.R.lumped_capacitance(T0=200, T_inf=25, t=60, h_conv=50,
                                A_surf=0.02, rho=2700, V_vol=1e-4, cp=900)
print(f"  Lumped cooling after 60 s: T = {lc['T_t']} (tau = {lc['tau']})")

print("\n" + "=" * 60)
print("  Structures")
print("=" * 60)

tor = anvil.R.torsion_circular_shaft(torque=500, d_outer=0.04, L=1.0,
                                     G=79e9, d_inner=0.0)
print(f"  Solid shaft torsion (T=500 N.m, d=40 mm): "
      f"tau_max = {tor['tau_max']}, twist = {tor['twist_deg']:.3f} deg")

ps = anvil.R.principal_stresses_2d(sigma_x=80e6, sigma_y=20e6, tau_xy=30e6)
print(f"  Principal stresses: s1 = {ps['sigma_1']}, s2 = {ps['sigma_2']}, "
      f"tau_max = {ps['tau_max']}")

vm = anvil.R.von_mises_stress(sigma_x=80e6, sigma_y=20e6, sigma_z=0,
                              tau_xy=30e6, tau_yz=0, tau_zx=0)
print(f"  Von Mises equivalent stress: {vm['sigma_vm']}")

print("\n" + "=" * 60)
print("  Ideal cycles")
print("=" * 60)

carnot = anvil.R.carnot_efficiency(T_hot=800, T_cold=300)
print(f"  Carnot (800 K / 300 K): eta = {carnot['eta_carnot']:.4f}, "
      f"COP_hp = {carnot['COP_heat_pump']:.3f}")

brayton = anvil.R.brayton_ideal(pressure_ratio=15, gamma=1.4,
                                T_min=300, T_max=1600)
print(f"  Ideal Brayton (rp=15): eta = {brayton['eta_thermal']:.4f}, "
      f"back-work ratio = {brayton['back_work_ratio']:.4f}")
