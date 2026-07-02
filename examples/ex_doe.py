"""
Example: Design of Experiments (DOE) + parallel sweeps on a built-in System.

Demonstrates:
  * Latin Hypercube sampling over a built-in rocket-nozzle System.
  * Evaluating the design with anvil.doe.run_doe().
  * A parallel parameter sweep using the pluggable executor.

Run:
    python examples/ex_doe.py

Notes
-----
The parallel executor defaults to a process pool (true multi-core scaling).
Built-in / registry-loaded Systems are typically NOT picklable (their relation
functions are reconstructed in a loader namespace), so Anvil transparently
falls back to a thread pool with a warning -- the results are identical either
way. The `if __name__ == "__main__"` guard below is required so process-based
workers can import this module cleanly on Windows ('spawn' start method).
"""
import warnings

import numpy as np
import anvil
from anvil import doe


def main():
    warnings.simplefilter("ignore")  # quiet DOF/backend-fallback warnings for the demo

    # --- A built-in System ----------------------------------------------------
    nozzle = anvil.S.rocket_nozzle.copy()
    print("Inputs:", list(nozzle._quantities.keys()))

    # --- 1. Latin Hypercube DOE over two inputs -------------------------------
    bounds = {
        "P0": (3.0e6, 10.0e6),    # chamber pressure [Pa]
        "A_exit": (0.05, 0.30),   # exit area [m^2]
    }
    samples = doe.latin_hypercube(bounds, n=20, seed=7)
    print(f"\nGenerated {len(samples)} Latin Hypercube samples.")
    print("First sample:", {k: round(v, 4) for k, v in samples[0].items()})

    # Evaluate the design (parallel=4 -> process pool, auto-falls back to threads
    # for this registry-loaded System).
    design = doe.run_doe(
        nozzle, samples, outputs=["thrust", "Isp", "M_exit"], parallel=4
    )
    design.summary()

    thrust = design["thrust"]
    best = int(np.nanargmax(thrust))
    print(f"\nBest design (max thrust): sample #{best}")
    print(f"  P0     = {samples[best]['P0']/1e6:.3f} MPa")
    print(f"  A_exit = {samples[best]['A_exit']:.4f} m^2")
    print(f"  thrust = {thrust[best]:.1f} N")

    # --- 2. Sobol sampling (low-discrepancy) ----------------------------------
    sob = doe.sobol(bounds, n=8, seed=1)
    print(f"\nSobol design: {len(sob)} samples (power-of-two recommended).")

    # --- 3. Full-factorial grid -----------------------------------------------
    grid = doe.full_factorial({
        "P0": [4e6, 7e6, 10e6],
        "A_exit": [0.08, 0.16, 0.24],
    })
    print(f"Full-factorial design: {len(grid)} grid points (3 x 3).")

    # --- 4. Parallel parameter sweep ------------------------------------------
    print("\nParallel sweep of chamber pressure P0:")
    sweep = nozzle.sweep("P0", np.linspace(3e6, 10e6, 8), parallel=4)
    sweep.summary(outputs=["thrust", "Isp"])


if __name__ == "__main__":
    main()
