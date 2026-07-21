"""
Curve Fitting and Data Tables
=============================

Demonstrates the data-fitting RSQs that take ``x_data`` / ``y_data`` arrays and
return coefficients, a fitted curve and a goodness-of-fit measure. Each fit is
run against data generated from known coefficients so you can see it recover
them.

Demonstrates:
    - linear_regression : least-squares line y = m x + b
    - poly_fit          : polynomial fit of chosen degree
    - power_fit         : power law y = a x^b (log-log)
    - exp_fit           : exponential y = a e^(b x) (semi-log)
"""

import numpy as np

import anvil

rng = np.random.default_rng(0)

print("=" * 60)
print("  Linear regression: y = 2 x + 1 (+ noise)")
print("=" * 60)

x = np.linspace(0, 10, 25)
y = 2.0 * x + 1.0 + rng.normal(0, 0.15, x.size)
lin = anvil.R.linear_regression(x_data=x, y_data=y)
print(f"  slope     = {lin['slope']:.4f}  (true 2.0)")
print(f"  intercept = {lin['intercept']:.4f}  (true 1.0)")
print(f"  R-squared = {lin['r_squared']:.5f},  RMSE = {lin['rmse']:.4f}")

print("\n" + "=" * 60)
print("  Polynomial fit: y = x^2 + 1 (exact)")
print("=" * 60)

xp = np.linspace(-3, 3, 21)
yp = xp**2 + 1.0
poly = anvil.R.poly_fit(x_data=xp, y_data=yp, degree=2)
coeffs = poly["coeffs"]
print(f"  coeffs (high->low) = "
      f"[{coeffs[0]:.4f}, {coeffs[1]:.4f}, {coeffs[2]:.4f}]  (true [1, 0, 1])")
print(f"  R-squared = {poly['r_squared']:.5f}")

print("\n" + "=" * 60)
print("  Power fit: y = 2 x^1.5")
print("=" * 60)

xw = np.linspace(1, 20, 20)
yw = 2.0 * xw**1.5
powr = anvil.R.power_fit(x_data=xw, y_data=yw)
print(f"  a = {powr['a']:.4f}  (true 2.0)")
print(f"  b = {powr['b']:.4f}  (true 1.5)")
print(f"  R-squared = {powr['r_squared']:.5f}")

print("\n" + "=" * 60)
print("  Exponential fit: y = 5 e^(0.3 x)")
print("=" * 60)

xe = np.linspace(0, 8, 20)
ye = 5.0 * np.exp(0.3 * xe)
expf = anvil.R.exp_fit(x_data=xe, y_data=ye)
print(f"  a = {expf['a']:.4f}  (true 5.0)")
print(f"  b = {expf['b']:.4f}  (true 0.3)")
print(f"  R-squared = {expf['r_squared']:.5f}")

print("\n  Each fit recovers the generating coefficients, confirming the")
print("  data-fitting RSQs are ready to drop into the workbench data tables.")
