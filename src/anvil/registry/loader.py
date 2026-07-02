"""
Load RSQ source code into live Python objects.

Each RSQ's source is a Python snippet that defines an `export` variable.
The loader executes it in a controlled namespace and extracts the result.
"""

import importlib


def load_rsq(record, store=None, sandboxed=False):
    """
    Load an RSQ record (from Store.get()) into a live object.

    Returns the exported object:
        - For type 'Q': a Quantity
        - For type 'R': a callable function wrapped in a Relation with outputs pre-set
        - For type 'S': a System (or a build function that returns one)

    Parameters
    ----------
    sandboxed : bool
        Default ``False`` preserves the original, trusted execution path
        BYTE-FOR-BYTE: the source is exec'd in the standard namespace with
        full builtins. When ``True`` (Tier B / public deployments) the source
        is exec'd in a *restricted* namespace: ``__builtins__`` is replaced
        with a small whitelist and a guarded ``__import__`` that only permits
        ``math``, ``numpy``/``np`` and ``anvil`` (and its safe submodules).
        Dangerous capabilities (open/eval/exec/compile/input, and imports of
        os/sys/subprocess/socket/shutil/pathlib/importlib/ctypes/builtins …)
        are blocked, so untrusted RSQ source fails to load.
    """
    source = record["source"]
    rsq_type = record["type"]
    name = record["name"]

    # Build execution namespace with anvil imports available.
    # The sandboxed namespace injects the same safe anvil objects but locks
    # down builtins/imports so untrusted source cannot escape.
    exec_ns = _build_sandbox_namespace() if sandboxed else _build_namespace()

    # If this RSQ depends on others, load them first
    if record.get("depends") and store:
        for dep_name in record["depends"]:
            dep_record = store.get(dep_name)
            if dep_record:
                dep_obj = load_rsq(dep_record, store, sandboxed=sandboxed)
                exec_ns[dep_name] = dep_obj

    try:
        exec(source, exec_ns)
    except Exception as e:
        raise RuntimeError(f"Failed to load RSQ '{name}': {e}")

    # Extract the exported object
    if "export" not in exec_ns:
        if name in exec_ns and callable(exec_ns[name]):
            exec_ns["export"] = exec_ns[name]
        else:
            raise RuntimeError(f"RSQ '{name}' source must define an 'export' variable.")

    obj = exec_ns["export"]

    # For Relations: wrap as Relation with outputs pre-discovered from source
    if rsq_type == "R" and callable(obj) and not isinstance(obj, _get_relation_class()):
        from anvil.relation import Relation
        rel = Relation(obj, name=name)
        # Pre-discover outputs by parsing the source (since inspect.getsource fails for exec'd code)
        outputs = _extract_outputs_from_source(source)
        if outputs:
            rel._outputs = outputs
        return rel

    # For Systems: call the build function
    if rsq_type == "S" and callable(obj) and not hasattr(obj, "solve"):
        obj = obj()

    return obj


def _get_relation_class():
    """Lazy import to avoid circular imports."""
    from anvil.relation import Relation
    return Relation


def _extract_outputs_from_source(source):
    """Parse return dict keys from RSQ source code."""
    import ast
    try:
        tree = ast.parse(source)
        keys = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
        return sorted(keys) if keys else []
    except Exception:
        return []


def _build_namespace():
    """Build the execution namespace with standard anvil imports."""
    import numpy as np
    import math

    def _rad(v):
        """Convert angle parameter to radians.
        Accepts Q objects (uses .si which is already in radians) or plain
        floats (treated as degrees and converted with np.radians).
        This lets RSQs with _deg parameters work correctly whether called
        directly with float degrees or from a System with Q('deg') values.
        """
        if hasattr(v, 'si'):
            return float(v.si)           # Q → SI value is already radians
        return np.radians(float(v))      # plain float → assume degrees

    ns = {"np": np, "numpy": np, "math": math, "_rad": _rad}
    try:
        from anvil.quantity import Quantity, Q
        from anvil.relation import Relation
        from anvil.system import System
        from anvil import solvers
        from anvil import units
        ns.update({
            "Q": Q, "Quantity": Quantity,
            "Relation": Relation,
            "System": System,
            "solvers": solvers,
            "units": units,
        })
    except ImportError:
        pass
    return ns


# --------------------------------------------------------------------------- #
# Sandboxed (Tier B) namespace — restricted builtins + guarded import
# --------------------------------------------------------------------------- #

# Modules an untrusted RSQ is permitted to import. Anything else (os, sys,
# subprocess, socket, shutil, pathlib, importlib, ctypes, builtins, ...) is
# rejected by the guarded __import__ below.
_SANDBOX_ALLOWED_MODULES = frozenset({
    "math",
    "numpy",
    "np",          # RSQs occasionally write `import np` style aliases
    "anvil",
    # Safe anvil submodules the seed RSQs import directly.
    "anvil.quantity",
    "anvil.relation",
    "anvil.system",
    "anvil.solvers",
    "anvil.units",
})

# Names from `anvil` that are safe to expose via `from anvil import ...`.
# Mirrors what _build_namespace() pre-injects.
_SANDBOX_ALLOWED_ANVIL_NAMES = frozenset({
    "Q", "Quantity", "Relation", "System", "solvers", "units",
})


def _make_guarded_import():
    """Build a restricted __import__ that only permits whitelisted modules.

    Blocks os/sys/subprocess/socket/shutil/pathlib/importlib/ctypes/builtins
    and anything else not explicitly allowed, while still letting native RSQs
    do `import numpy as np`, `import math`, and `from anvil import Q, solvers`.
    """
    real_import = importlib.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError("relative imports are not allowed in sandboxed RSQs")
        root = name.split(".")[0]
        if name not in _SANDBOX_ALLOWED_MODULES and root not in _SANDBOX_ALLOWED_MODULES:
            raise ImportError(
                f"import of '{name}' is blocked in the sandbox "
                f"(allowed: math, numpy, anvil)"
            )
        module = real_import(name, globals, locals, fromlist, level)
        # When importing `from anvil import X, Y`, restrict the exposed names.
        if root == "anvil" and fromlist:
            for attr in fromlist:
                if attr == "*":
                    raise ImportError("`from anvil import *` is blocked in the sandbox")
                if attr not in _SANDBOX_ALLOWED_ANVIL_NAMES:
                    raise ImportError(
                        f"`from anvil import {attr}` is blocked in the sandbox"
                    )
        return module

    return guarded_import


def _build_sandbox_namespace():
    """Build a RESTRICTED execution namespace for untrusted RSQ source.

    Same safe anvil objects as _build_namespace() are pre-injected, but
    ``__builtins__`` is replaced with a small whitelist plus a guarded
    ``__import__``. There is no open/eval/exec/compile/input/__import__ to
    the dangerous stdlib here.
    """
    import numpy as np
    import math as _math

    # Start from the standard (already-safe) anvil namespace so native RSQs
    # have Q, Quantity, Relation, System, solvers, units, np, math, _rad.
    ns = _build_namespace()

    # Whitelisted builtins. NOTE: deliberately excludes open, eval, exec,
    # compile, input, __import__ (replaced below), getattr/setattr/delattr,
    # globals/locals/vars, type, object, etc.
    safe_builtins = {
        "abs": abs, "min": min, "max": max, "round": round, "range": range,
        "len": len, "enumerate": enumerate, "zip": zip, "sum": sum,
        "pow": pow, "float": float, "int": int, "bool": bool, "str": str,
        "list": list, "dict": dict, "tuple": tuple, "set": set,
        "sorted": sorted, "map": map, "filter": filter,
        "True": True, "False": False, "None": None,
        "isinstance": isinstance, "callable": callable,
        "all": all, "any": any, "divmod": divmod, "repr": repr,
        "ValueError": ValueError, "TypeError": TypeError,
        "ZeroDivisionError": ZeroDivisionError, "KeyError": KeyError,
        "Exception": Exception, "ArithmeticError": ArithmeticError,
        # Guarded import so `import numpy as np` / `from anvil import Q` work.
        "__import__": _make_guarded_import(),
    }

    ns["__builtins__"] = safe_builtins
    return ns


def source_from_function(func, rsq_type="R"):
    """
    Generate RSQ source code from a live Python function.

    Used when the user does anvil.push(my_function, ...).
    """
    import inspect
    import textwrap

    source = inspect.getsource(func)
    source = textwrap.dedent(source)

    # Strip decorator lines (@...) before the `def` keyword.
    # Python 3.12+ includes decorator source in co_firstlineno, so
    # inspect.getsource may return lines like "@anvil.relation(...)" which
    # would fail when exec'd without the original module in scope.
    lines = source.splitlines()
    stripped = []
    past_decorators = False
    for line in lines:
        stripped_line = line.strip()
        if not past_decorators:
            if stripped_line.startswith("def ") or stripped_line.startswith("async def "):
                past_decorators = True
                stripped.append(line)
            elif stripped_line.startswith("@"):
                continue  # skip decorator lines
            else:
                stripped.append(line)
        else:
            stripped.append(line)
    source = "\n".join(stripped)

    # Wrap in standard RSQ format
    lines = [
        "from anvil import Q, System, Relation",
        "from anvil import solvers",
        "",
        source,
        "",
        f"export = {func.__name__}",
    ]
    return "\n".join(lines)


def source_from_quantity(q, name):
    """Generate RSQ source code from a Quantity."""
    unit = q._unit_hint or ""
    val = q.si if not unit else q.value
    desc = q.desc or q.name or name
    return (
        f'from anvil import Q\n'
        f'export = Q({val}, "{unit}", name="{name}", desc="{desc}")\n'
    )


def source_from_system(system):
    """
    Generate a description of a System for storage.
    Note: full serialization of arbitrary Systems is complex.
    For now, stores a rebuild function.
    """
    # This is a simplified version -- full serialization would
    # need to capture all quantities and relation references
    lines = [
        "from anvil import Q, System",
        "from anvil import solvers",
        "",
        "def build():",
        f'    s = System("{system.name}")',
    ]
    for qname, q in system._quantities.items():
        unit = q._unit_hint or ""
        val = q.value
        desc = q.desc or ""
        if unit:
            lines.append(f'    s.add("{qname}", {val}, "{unit}", desc="{desc}")')
        else:
            lines.append(f'    s.add("{qname}", {val}, desc="{desc}")')

    for rel in system._relations:
        lines.append(f'    s.use("{rel.name}")')

    lines.append("    return s")
    lines.append("")
    lines.append("export = build")

    return "\n".join(lines)
