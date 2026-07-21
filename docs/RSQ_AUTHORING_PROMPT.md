# Anvil RSQ Authoring Prompt

Hand this entire file to an LLM, then append your domain equations at the bottom where marked. The
LLM will return Anvil RSQ seed dicts you can validate and seed. Nothing here needs editing except the
final section.

---

You are authoring **Anvil RSQs**: reusable engineering relations stored as Python source and run
inside a controlled namespace. Output ONLY a Python list of dicts, each matching this exact schema:

```python
{"name": "<snake_case>", "type": "R", "domain": "<dot.hierarchy>",
 "desc": "<one line, no em dashes or en dashes>",
 "tags": ["<tag>", "..."],
 "latex": r"<KaTeX, raw string>",
 "source": "<python; \n-separated; MUST end with: export = <fn>>"}
```

## Types

- `"R"` (Relation): a function `f(**inputs) -> {output_name: value}`. This is the common case.
- `"Q"` (Quantity): a physical constant. `source` is `from anvil import Q\nexport = Q(<value>, "<unit>", name="<name>")`.
- `"S"` (System): a builder returning a composed `System`. Only for chaining several R's; list the
  R's it uses in a `"depends"` key. Prefer R's unless the task is genuinely multi-relation.

## Hard rules

1. The `source` is `exec`'d in a namespace that ALREADY binds these names. Do NOT redefine or import
   them (though `from anvil import Q` is still fine):
   `np`, `numpy`, `math`, `_rad`, `Q`, `Quantity`, `Relation`, `System`, `solvers`, `units`.
2. Return dimensioned outputs as `Q(value, "unit")`, e.g. `{"F": Q(m*a, "N")}`. Dimensionless
   outputs are plain floats.
3. Unit strings use `*`, `/`, and `^`: `"m/s"`, `"kg*m/s"`, `"W/m^2/K"`, `"Pa"`, `"J"`, `"N"`.
   Dimensionless is `"1"` or omit the wrapper. CAUTION: only base and standard derived SI units
   resolve to real dimensions. Confirmed-good: `m, s, kg, A, K, mol, N, J, W, Pa, Hz, V, m/s`, and
   any product/quotient of base units. Some named units (for example `F` farad, `C` coulomb) do NOT
   resolve and silently produce an opaque custom dimension with no error, so a wrong-dimension result
   slips through. If a needed unit is not clearly base or standard-derived, express the output in a
   unit you are sure of (for capacitance return energy in `J`; for charge keep it a plain-float
   input) or verify with `Q(1.0, "<unit>").dim` before trusting it.
3a. Physical constants are NOT injected. If you need `c`, `h`, `hbar`, `G`, `e` (elementary charge),
    `epsilon_0`, `k_B`, `N_A`, etc., define them as SI numeric literals inside the function body.
    Do not import `scipy.constants` (blocked in the sandbox) and do not assume any constant is in
    scope.
4. `float()`-coerce every input you compare, branch on, or feed to `math.*`, so a dimensioned `Q` vs
   raw float never raises: write `M = float(M)` first.
5. `_rad(x)` converts degrees to radians (accepts a float or a `Q`). Use it for angle inputs named in
   degrees.
6. Provide a default value only when a textbook default is standard (e.g. `gamma=1.4`). Never invent
   defaults for quantities that must be supplied.
7. `source` MUST end with `export = <function_name>`.
7a. Guard denominators and domains that can blow up. The validator `anvil.check` probes the relation
    with default values (often all 1.0), which can hit a physical singularity (for example the thin
    lens with `d_o == f`, giving an infinite image distance). Return `float('inf')` or `float('nan')`
    gracefully in that case rather than letting a `ZeroDivisionError` or math-domain error raise.
8. Choose a dot-hierarchical `domain` (e.g. `physics.mechanics`). It sets catalog grouping and access
   as `anvil.R.<domain>.<name>`.
9. Names must be unique and must NOT collide with existing built-ins. If unsure a name is taken,
   pick a more specific one.
10. No em dashes or en dashes anywhere in any field.
11. For an `S` builder: each output name must be unique across the system; there is no shared mutable
    state beyond the workspace variables, which are matched by name.

## Worked examples

```python
{"name": "dynamic_pressure", "type": "R", "domain": "aero",
 "desc": "Dynamic pressure from density and speed",
 "tags": ["aero"],
 "latex": r"q = \tfrac{1}{2}\rho V^2",
 "source": "from anvil import Q\ndef dynamic_pressure(rho, V):\n    return {\"q_inf\": Q(0.5*float(rho)*float(V)**2, \"Pa\")}\nexport = dynamic_pressure"}

{"name": "mach_angle", "type": "R", "domain": "aero.compressible",
 "desc": "Mach angle of a supersonic flow",
 "tags": ["compressible", "supersonic"],
 "latex": r"\mu = \arcsin(1/M)",
 "source": "def mach_angle(M):\n    M = float(M)\n    mu = math.asin(1.0/M)\n    return {\"mu_rad\": mu, \"mu_deg\": math.degrees(mu)}\nexport = mach_angle"}

{"name": "carnot_efficiency", "type": "R", "domain": "thermo",
 "desc": "Carnot efficiency and heat-pump and refrigerator COPs",
 "tags": ["thermo", "cycle"],
 "latex": r"\eta = 1 - T_c/T_h",
 "source": "def carnot_efficiency(T_hot, T_cold):\n    Th, Tc = float(T_hot), float(T_cold)\n    eta = 1 - Tc/Th\n    return {\"eta_carnot\": eta, \"COP_heat_pump\": 1/eta, \"COP_refrigerator\": Tc/(Th-Tc)}\nexport = carnot_efficiency"}
```

## Output format

Return a single Python list `[ {...}, {...}, ... ]` of dicts and nothing else. For each RSQ, also
give (as a Python comment above the dict) one sample call with numeric inputs and the expected
numeric output from a textbook or first principles, so the author can write a correctness test.

You do not get to certify your own output. The author will run `anvil.check("<name>")` and a
textbook-value test before seeding.

---

## WRITE RSQs FOR THESE EQUATIONS

<!-- Replace this block with your domain equations. For each: the relation name you want, the
     equation, every input symbol with its unit, and one worked numeric example (inputs -> output)
     so the generated RSQ can be tested. -->
