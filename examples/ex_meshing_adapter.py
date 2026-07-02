"""
Example: Meshing Adapter -- Parametric Geometry in Anvil (real-only)
===================================================================

Demonstrates the mesh_box and mesh_cylinder adapters: node/element counts
and bounding box from a requested element size, and how the element count
feeds an Anvil System that estimates a solver memory footprint.

These adapters are REAL-ONLY: there is no mock fallback. They require the
gmsh package (pip install gmsh). When gmsh is missing, *calling* the adapter
raises a clear ImportError; this example catches it, prints the install
message, and exits 0 -- so it always runs to completion.
"""

import anvil
from anvil import Q
from anvil.adapters.meshing_geom import mesh_box, mesh_cylinder, register

W = 64
print("=" * W)
print("  Meshing Adapter Example (real-only, no mock)")
print("=" * W)

# register() never needs gmsh; importing the module is always safe.
register()

try:
    # ── 1. Box mesh refinement study ─────────────────────────────────────────
    print("\n[1] Box (1.0 x 0.5 x 0.2 m) mesh vs element size")
    print(f"  {'elem_size':>10s}  {'n_nodes':>9s}  {'n_elem':>9s}  {'src':>6s}")
    print(f"  {'-'*10}  {'-'*9}  {'-'*9}  {'-'*6}")
    for h in (0.1, 0.05, 0.025):
        r = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=h)
        print(f"  {h:10.3f}  {int(r['n_nodes']):9d}  "
              f"{int(r['n_elements']):9d}  {str(r['source']):>6s}")

    # ── 2. Cylinder mesh ─────────────────────────────────────────────────────
    print("\n[2] Cylinder (r=0.5 m, h=1.0 m) mesh")
    c = mesh_cylinder(radius=0.5, height=1.0, elem_size=0.1)
    print(f"  n_nodes   = {int(c['n_nodes'])}")
    print(f"  n_elements= {int(c['n_elements'])}")
    print(f"  bbox_vol  = {c['bbox_vol']}  (source: {c['source']})")

    # ── 3. Pipeline: estimate solver memory from element count ───────────────
    print("\n[3] System: solver memory estimate from box mesh")
    mesh = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=0.05)
    job = anvil.system("mesh_job")
    job.add("n_elements", int(mesh["n_elements"]), "1")
    job.add("bytes_per_elem", 2000.0, "1")

    def memory(n_elements, bytes_per_elem):
        mem_mb = n_elements * bytes_per_elem / 1e6
        return {"mem_MB": Q(mem_mb, "1")}
    job.use(memory)
    res = job.solve_forward()
    print(f"  mem_MB     = {res['mem_MB'].value:.1f} MB")

except ImportError as e:
    print("\n  gmsh is not installed -- cannot run this example.")
    print(f"  {e}")
    print("\n  Install gmsh to run this example: pip install gmsh")

print("\n" + "=" * W)
print("  Done.")
print("=" * W)
