"""Curated example canvases for the web System-builder.

Each example is a CANVAS GRAPH in the system-builder payload shape::

    {
      "id":          str,                 # stable slug
      "name":        str,
      "description": str,
      "domain":      str,
      "quantities":  [{"name", "value", "unit"}, ...],
      "relations":   [name, ...],         # registry relation names (auto-wired)
      "positions":   {name: {"x", "y"}},  # optional node layout hints
      "array_input": bool,                # true for signal/array examples
    }

These mirror the ``SystemSolveRequest`` shape so the frontend can POST a chosen
example straight to ``/api/system/solve`` (or solve a single array relation via
``/api/solve``). They cover a representative spread of domains -- NOT every
example script -- per the milestone brief.

Coverage authored here (9):
  1. isentropic_ratios      compressible-flow ratios (single relation)
  2. normal_shock_chain     normal shock (compressible)
  3. rocket_nozzle_perf     choked mass flow -> specific impulse chain
  4. hohmann_transfer       orbital Hohmann transfer delta-v
  5. heat_conduction_conv   1-D conduction + convection (heat exchanger-ish)
  6. second_order_response  controls: 2nd-order step-response metrics
  7. signal_fft             signal-processing FFT (ARRAY input, /api/solve)
  8. tsiolkovsky_dv         propulsion: ideal rocket-equation delta-v
  9. vis_viva_velocity      orbital: vis-viva orbital velocity
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Helpers to build the array example without hard-coding thousands of points.
# --------------------------------------------------------------------------- #

def _demo_signal(n: int = 1024, fs: float = 1024.0) -> List[float]:
    """50 Hz fundamental + 0.3x 150 Hz harmonic, sampled at ``fs`` for ``n`` pts."""
    dt = 1.0 / fs
    sig = []
    for i in range(n):
        t = i * dt
        sig.append(math.sin(2 * math.pi * 50 * t)
                   + 0.3 * math.sin(2 * math.pi * 150 * t))
    return sig


_FS = 1024.0
_N = 1024


EXAMPLES: List[Dict[str, Any]] = [
    {
        "id": "isentropic_ratios",
        "name": "Isentropic flow ratios",
        "description": "Stagnation-to-static ratios for a Mach-2 isentropic flow.",
        "domain": "aero.compressible",
        "quantities": [
            {"name": "M", "value": 2.0, "unit": ""},
            {"name": "gamma", "value": 1.4, "unit": ""},
        ],
        "relations": ["isentropic_ratios"],
        "positions": {
            "M": {"x": 80, "y": 80},
            "gamma": {"x": 80, "y": 180},
            "isentropic_ratios": {"x": 320, "y": 130},
        },
        "array_input": False,
    },
    {
        "id": "normal_shock_chain",
        "name": "Normal shock + isentropic ratios",
        "description": "Mach-3 normal shock; downstream isentropic ratios from M2.",
        "domain": "aero.compressible",
        "quantities": [
            {"name": "M1", "value": 3.0, "unit": ""},
            {"name": "gamma", "value": 1.4, "unit": ""},
        ],
        # normal_shock produces M2; isentropic_ratios consumes M (rename handled
        # by the canvas: here we chain via the shared 'gamma' and demonstrate the
        # shock relation alone -- the frontend wires M2->M when desired).
        "relations": ["normal_shock"],
        "positions": {
            "M1": {"x": 80, "y": 80},
            "gamma": {"x": 80, "y": 200},
            "normal_shock": {"x": 320, "y": 100},
        },
        "array_input": False,
    },
    {
        "id": "rocket_nozzle_perf",
        "name": "Rocket nozzle performance chain",
        "description": "Choked mass flow feeding specific impulse from thrust.",
        "domain": "propulsion",
        "quantities": [
            {"name": "P0", "value": 6.9e6, "unit": "Pa"},
            {"name": "T0", "value": 3500.0, "unit": "K"},
            {"name": "gamma", "value": 1.25, "unit": ""},
            {"name": "R_gas", "value": 320.0, "unit": "J/kg/K"},
            {"name": "A_throat", "value": 0.01, "unit": "m^2"},
            {"name": "thrust", "value": 22000.0, "unit": "N"},
        ],
        # choked_mass_flow -> mdot; specific_impulse(thrust, mdot) -> Isp.
        "relations": ["choked_mass_flow", "specific_impulse"],
        "positions": {
            "P0": {"x": 60, "y": 40},
            "T0": {"x": 60, "y": 120},
            "gamma": {"x": 60, "y": 200},
            "R_gas": {"x": 60, "y": 280},
            "A_throat": {"x": 60, "y": 360},
            "thrust": {"x": 60, "y": 440},
            "choked_mass_flow": {"x": 320, "y": 160},
            "specific_impulse": {"x": 560, "y": 280},
        },
        "array_input": False,
    },
    {
        "id": "hohmann_transfer",
        "name": "Hohmann transfer (LEO -> GEO)",
        "description": "Two-burn Hohmann transfer delta-v and time of flight.",
        "domain": "orbital",
        "quantities": [
            {"name": "mu", "value": 3.986e14, "unit": ""},
            {"name": "r1", "value": 6.778e6, "unit": ""},
            {"name": "r2", "value": 4.2164e7, "unit": ""},
        ],
        "relations": ["hohmann_transfer"],
        "positions": {
            "mu": {"x": 80, "y": 60},
            "r1": {"x": 80, "y": 160},
            "r2": {"x": 80, "y": 260},
            "hohmann_transfer": {"x": 340, "y": 160},
        },
        "array_input": False,
    },
    {
        "id": "heat_conduction_conv",
        "name": "Wall conduction + convection",
        "description": "1-D conduction through a wall plus surface convection.",
        "domain": "heat_transfer",
        "quantities": [
            {"name": "k", "value": 50.0, "unit": ""},
            {"name": "A_cross", "value": 0.25, "unit": ""},
            {"name": "dT", "value": 80.0, "unit": ""},
            {"name": "L_thickness", "value": 0.02, "unit": ""},
            {"name": "h_conv", "value": 25.0, "unit": ""},
            {"name": "A_surf", "value": 0.25, "unit": ""},
            {"name": "T_surf", "value": 350.0, "unit": ""},
            {"name": "T_inf", "value": 300.0, "unit": ""},
        ],
        "relations": ["conduction_1d", "convection"],
        "positions": {
            "k": {"x": 60, "y": 40},
            "A_cross": {"x": 60, "y": 110},
            "dT": {"x": 60, "y": 180},
            "L_thickness": {"x": 60, "y": 250},
            "conduction_1d": {"x": 320, "y": 140},
            "h_conv": {"x": 60, "y": 340},
            "A_surf": {"x": 60, "y": 410},
            "T_surf": {"x": 60, "y": 480},
            "T_inf": {"x": 60, "y": 550},
            "convection": {"x": 320, "y": 440},
        },
        "array_input": False,
    },
    {
        "id": "second_order_response",
        "name": "Second-order step response",
        "description": "Controls: rise/settle/overshoot for a 2nd-order system.",
        "domain": "controls",
        "quantities": [
            {"name": "omega_n", "value": 10.0, "unit": ""},
            {"name": "zeta", "value": 0.5, "unit": ""},
        ],
        "relations": ["second_order_metrics"],
        "positions": {
            "omega_n": {"x": 80, "y": 80},
            "zeta": {"x": 80, "y": 180},
            "second_order_metrics": {"x": 340, "y": 130},
        },
        "array_input": False,
    },
    {
        "id": "signal_fft",
        "name": "FFT spectrum (signal input)",
        "description": ("Real FFT of a 50 Hz + 150 Hz signal. Array/time-series "
                        "example -- solve via POST /api/solve (single relation)."),
        "domain": "misc",
        "quantities": [
            {"name": "signal", "value": _demo_signal(_N, _FS), "unit": ""},
            {"name": "dt", "value": 1.0 / _FS, "unit": "s"},
            {"name": "window", "value": "hann", "unit": ""},
        ],
        "relations": ["fft_spectrum"],
        "positions": {
            "signal": {"x": 80, "y": 80},
            "dt": {"x": 80, "y": 180},
            "window": {"x": 80, "y": 280},
            "fft_spectrum": {"x": 340, "y": 160},
        },
        "array_input": True,
    },
    {
        "id": "tsiolkovsky_dv",
        "name": "Tsiolkovsky rocket equation",
        "description": "Ideal delta-v from specific impulse and mass ratio.",
        "domain": "propulsion",
        "quantities": [
            {"name": "Isp", "value": 311.0, "unit": ""},
            {"name": "mass_ratio", "value": 3.5, "unit": ""},
        ],
        "relations": ["tsiolkovsky"],
        "positions": {
            "Isp": {"x": 80, "y": 80},
            "mass_ratio": {"x": 80, "y": 180},
            "tsiolkovsky": {"x": 340, "y": 130},
        },
        "array_input": False,
    },
    {
        "id": "vis_viva_velocity",
        "name": "Vis-viva orbital velocity",
        "description": "Orbital speed at radius r on an orbit of semi-major axis a.",
        "domain": "orbital",
        "quantities": [
            {"name": "mu", "value": 3.986e14, "unit": ""},
            {"name": "r", "value": 7.0e6, "unit": ""},
            {"name": "a", "value": 8.0e6, "unit": ""},
        ],
        "relations": ["vis_viva"],
        "positions": {
            "mu": {"x": 80, "y": 60},
            "r": {"x": 80, "y": 160},
            "a": {"x": 80, "y": 260},
            "vis_viva": {"x": 340, "y": 160},
        },
        "array_input": False,
    },
]


_BY_ID: Dict[str, Dict[str, Any]] = {ex["id"]: ex for ex in EXAMPLES}


def list_examples() -> List[Dict[str, Any]]:
    """Return a lightweight summary list (no full quantity payloads)."""
    out = []
    for ex in EXAMPLES:
        out.append({
            "id": ex["id"],
            "name": ex["name"],
            "description": ex["description"],
            "domain": ex.get("domain", ""),
            "relations": ex.get("relations", []),
            "array_input": ex.get("array_input", False),
            "n_quantities": len(ex.get("quantities", [])),
        })
    return out


def get_example(example_id: str) -> Optional[Dict[str, Any]]:
    """Return the full canvas payload for ``example_id`` (or None)."""
    return _BY_ID.get(example_id)
