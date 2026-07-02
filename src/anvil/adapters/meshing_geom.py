"""
Anvil Adapter: Parametric Geometry Meshing (gmsh + meshio)
==========================================================

Generates a simple parametric mesh (box or cylinder) and reports node and
element counts plus the bounding box, using gmsh for real meshing.

ADAPTERS PROVIDED:
    mesh_box       -- tet mesh of a rectangular box
    mesh_cylinder  -- mesh of a cylinder (radius x height)

INSTALLATION (CLI / heavy deps -- Tier A):
    pip install gmsh
    pip install meshio   (optional: reported as the mesh format backend)

VERIFY:
    python -c "import gmsh; print('ok')"
    python -c "import meshio; print(meshio.__version__)"

REAL ONLY -- NO MOCK MODE:
    These adapters require the real gmsh package. Importing this module never
    fails (the gmsh import is lazy, inside the wrappers), but *calling* an
    adapter without gmsh installed raises a clear ImportError naming the
    package and the install command. There is no analytical / mock element
    count: the node/element counts come from a real gmsh mesh.

USAGE:
    from anvil.adapters.meshing_geom import mesh_box, mesh_cylinder, register

    r = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=0.05)
    print(r["n_nodes"], r["n_elements"], r["source"])

    register()   # push to anvil registry under "geometry.mesh"
"""

from anvil import Adapter, Q


def _mesh_format():
    """Return the format-backend name (meshio if present, else gmsh)."""
    try:
        import meshio  # noqa: F401
        return "meshio"
    except ImportError:
        return "gmsh"


def mesh_box_call(Lx=1.0, Ly=1.0, Lz=1.0, elem_size=0.1):
    """
    Mesh a rectangular box of dimensions Lx x Ly x Lz with target element
    size elem_size. Inputs are raw SI floats [m] or Q. Returns node/element
    counts, bounding-box volume, the mesh format name, and a "source" field.

    Requires the real gmsh package; if it is not installed, raises an
    ImportError with the install command. There is no mock fallback.
    """
    from anvil import Q

    Lx = float(Lx.si) if hasattr(Lx, "si") else float(Lx)
    Ly = float(Ly.si) if hasattr(Ly, "si") else float(Ly)
    Lz = float(Lz.si) if hasattr(Lz, "si") else float(Lz)
    elem_size = float(elem_size.si) if hasattr(elem_size, "si") else float(elem_size)
    elem_size = max(elem_size, 1e-9)

    bbox_vol = Lx * Ly * Lz

    # --- Real path: gmsh (lazy import) --------------------------------------
    try:
        import gmsh
    except ImportError as e:
        raise ImportError(
            "mesh_box requires the 'gmsh' package; "
            "install with: pip install gmsh"
        ) from e

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("anvil_box")
        gmsh.model.occ.addBox(0, 0, 0, Lx, Ly, Lz)
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMin", elem_size)
        gmsh.option.setNumber("Mesh.MeshSizeMax", elem_size)
        gmsh.model.mesh.generate(3)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        n_nodes = len(node_tags)
        _, elem_tags, _ = gmsh.model.mesh.getElements(dim=3)
        n_elements = sum(len(t) for t in elem_tags)
    finally:
        gmsh.finalize()

    return {
        "n_nodes":    int(n_nodes),
        "n_elements": int(n_elements),
        "bbox_vol":   Q(bbox_vol, "m^3"),
        "format":     _mesh_format(),
        "source":     "gmsh",
    }


mesh_box = Adapter(
    "mesh_box",
    backend="python",
    call=mesh_box_call,
    inputs={
        "Lx":        {"unit": "m", "desc": "Box length (x)", "default": 1.0},
        "Ly":        {"unit": "m", "desc": "Box length (y)", "default": 1.0},
        "Lz":        {"unit": "m", "desc": "Box length (z)", "default": 1.0},
        "elem_size": {"unit": "m", "desc": "Target element edge size", "default": 0.1},
    },
    outputs={
        "n_nodes":    {"unit": "1",   "desc": "Number of mesh nodes"},
        "n_elements": {"unit": "1",   "desc": "Number of volume elements (tets)"},
        "bbox_vol":   {"unit": "m^3", "desc": "Bounding-box volume"},
        "format":     {"desc": "Mesh/format backend used"},
        "source":     {"desc": "gmsh (real library required; no mock fallback)"},
    },
    desc="Parametric box mesh: node/element counts + bounding box (requires gmsh)",
    tags=["gmsh", "cadquery", "meshio", "mesh", "geometry", "tierA", "cli"],
)


def mesh_cylinder_call(radius=0.5, height=1.0, elem_size=0.1):
    """
    Mesh a cylinder of given radius and height with target element size.
    Inputs are raw SI floats [m] or Q. Returns node/element counts, the
    bounding-box volume, the format name, and a "source" field.

    Requires the real gmsh package; if it is not installed, raises an
    ImportError with the install command. There is no mock fallback.
    """
    from anvil import Q

    radius = float(radius.si) if hasattr(radius, "si") else float(radius)
    height = float(height.si) if hasattr(height, "si") else float(height)
    elem_size = float(elem_size.si) if hasattr(elem_size, "si") else float(elem_size)
    elem_size = max(elem_size, 1e-9)

    bbox_vol = (2.0 * radius) * (2.0 * radius) * height  # AABB of the cylinder

    # --- Real path: gmsh (lazy import) --------------------------------------
    try:
        import gmsh
    except ImportError as e:
        raise ImportError(
            "mesh_cylinder requires the 'gmsh' package; "
            "install with: pip install gmsh"
        ) from e

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("anvil_cyl")
        gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, height, radius)
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMin", elem_size)
        gmsh.option.setNumber("Mesh.MeshSizeMax", elem_size)
        gmsh.model.mesh.generate(3)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        n_nodes = len(node_tags)
        _, elem_tags, _ = gmsh.model.mesh.getElements(dim=3)
        n_elements = sum(len(t) for t in elem_tags)
    finally:
        gmsh.finalize()

    return {
        "n_nodes":    int(n_nodes),
        "n_elements": int(n_elements),
        "bbox_vol":   Q(bbox_vol, "m^3"),
        "format":     _mesh_format(),
        "source":     "gmsh",
    }


mesh_cylinder = Adapter(
    "mesh_cylinder",
    backend="python",
    call=mesh_cylinder_call,
    inputs={
        "radius":    {"unit": "m", "desc": "Cylinder radius", "default": 0.5},
        "height":    {"unit": "m", "desc": "Cylinder height", "default": 1.0},
        "elem_size": {"unit": "m", "desc": "Target element edge size", "default": 0.1},
    },
    outputs={
        "n_nodes":    {"unit": "1",   "desc": "Number of mesh nodes"},
        "n_elements": {"unit": "1",   "desc": "Number of volume elements (tets)"},
        "bbox_vol":   {"unit": "m^3", "desc": "Bounding-box (AABB) volume"},
        "format":     {"desc": "Mesh/format backend used"},
        "source":     {"desc": "gmsh (real library required; no mock fallback)"},
    },
    desc="Parametric cylinder mesh: node/element counts + bounding box (requires gmsh)",
    tags=["gmsh", "cadquery", "meshio", "mesh", "geometry", "tierA", "cli"],
)


def register():
    """Push the meshing adapters to the global Anvil registry."""
    import anvil
    anvil.push(mesh_box_call, name="mesh_box",
               domain="geometry.mesh",
               description=mesh_box.desc,
               tags=mesh_box.tags, overwrite=True)
    anvil.push(mesh_cylinder_call, name="mesh_cylinder",
               domain="geometry.mesh",
               description=mesh_cylinder.desc,
               tags=mesh_cylinder.tags, overwrite=True)
    print("Registered: mesh_box, mesh_cylinder  [domain: geometry.mesh]")


if __name__ == "__main__":
    r = mesh_box(Lx=1.0, Ly=0.5, Lz=0.2, elem_size=0.05)
    for k, v in r.items():
        print(f"  {k}: {v}")
    c = mesh_cylinder(radius=0.5, height=1.0, elem_size=0.1)
    for k, v in c.items():
        print(f"  {k}: {v}")
