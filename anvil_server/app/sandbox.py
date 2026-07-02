"""Subprocess-isolated, time-bounded sandboxed solve (Tier B).

The public RSQ source stored in the registry is untrusted remote input. For
the Tier-B "calculator" deployment we execute it under two layers of defense:

  1. Restricted namespace -- ``anvil.registry.loader.load_rsq(..., sandboxed=True)``
     replaces ``__builtins__`` with a whitelist and a guarded ``__import__`` so
     the source cannot reach os/sys/subprocess/open/eval/exec/etc.
  2. Process isolation + wall-clock timeout -- the actual solve runs in a child
     process (multiprocessing, 'spawn'-safe). If it exceeds the configured
     timeout it is terminated and a clear error is raised. This is the only
     portable resource bound on Windows (no seccomp / resource.setrlimit).

``run_sandboxed_solve`` returns the SAME serialized dict shape that
``executor.solve`` returns, so callers are interchangeable.
"""

from __future__ import annotations

import json
import multiprocessing as mp
from typing import Any, Dict

# Use a spawn context explicitly so behaviour is identical on Windows (spawn is
# the only start method there) and POSIX. The top-level worker below is
# importable, which spawn requires.
_CTX = mp.get_context("spawn")


class SandboxTimeout(RuntimeError):
    """Raised when a sandboxed solve exceeds its wall-clock budget."""


class SandboxError(RuntimeError):
    """Raised when a sandboxed solve fails inside the child process."""


# --------------------------------------------------------------------------- #
# Child-process worker (must be top-level & importable for spawn)
# --------------------------------------------------------------------------- #

def _solve_worker(conn, name: str, inputs: Dict[str, Any], si: bool) -> None:
    """Run a single sandboxed solve and send the serialized result back.

    Executed in the child process. Loads the named RSQ via the sandboxed
    loader (restricted namespace), runs ``anvil.solve`` against the loaded
    object, and serializes the result into the executor's dict shape.
    """
    try:
        import anvil
        from anvil import registry
        from anvil.registry.loader import load_rsq

        store = registry._get_store()
        record = store.get(name)
        if record is None:
            raise KeyError(name)

        # Sandboxed load: untrusted source runs under restricted builtins.
        obj = load_rsq(record, store, sandboxed=True)

        # Coerce {"value":x,"unit":"Pa"} dicts into Quantities, mirroring
        # executor._coerce_input but kept local so the child has no dependency
        # on the executor module (avoids re-import cycles under spawn).
        kwargs = {}
        for k, v in inputs.items():
            if isinstance(v, dict):
                value = v.get("value")
                unit = (v.get("unit") or "").strip()
                if unit:
                    try:
                        kwargs[k] = anvil.Quantity(float(value), unit)
                        continue
                    except Exception:
                        pass
                kwargs[k] = value
            else:
                kwargs[k] = v

        # Pass the loaded object (not the name string) so the sandboxed load
        # is the one actually used -- System.use(name) would re-load it
        # un-sandboxed otherwise.
        result = anvil.solve(obj, **kwargs)

        report = anvil.check(name, verbose=False)
        input_names = set(report.get("inputs", []) or [])

        parsed = json.loads(result.to_json(si=si))
        results: Dict[str, Any] = {}
        for key, vu in parsed.items():
            results[key] = {
                "value": vu.get("value"),
                "unit": vu.get("unit", "") or "",
                "role": "input" if key in input_names else "output",
            }

        payload = {
            "name": name,
            "method": getattr(result, "method", "") or "",
            "results": results,
            "inputs": sorted(k for k in results if results[k]["role"] == "input"),
            "outputs": sorted(k for k in results if results[k]["role"] == "output"),
        }
        conn.send(("ok", payload))
    except Exception as exc:  # noqa: BLE001 - report any failure to parent
        conn.send(("err", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def run_sandboxed_solve(
    name: str,
    inputs: Dict[str, Any],
    timeout_s: float = 10.0,
    si: bool = False,
) -> Dict[str, Any]:
    """Solve ``name`` in an isolated child process with a wall-clock timeout.

    Returns the same dict shape as ``executor.solve``. Raises:
        - ``SandboxTimeout`` if the solve exceeds ``timeout_s``.
        - ``SandboxError`` (or KeyError text wrapped) if the solve fails.
    """
    parent_conn, child_conn = _CTX.Pipe(duplex=False)
    proc = _CTX.Process(
        target=_solve_worker,
        args=(child_conn, name, inputs, si),
        daemon=True,
    )
    proc.start()
    # Close our copy of the child end so we get EOF if the child dies.
    child_conn.close()

    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        raise SandboxTimeout(
            f"sandboxed solve of '{name}' exceeded {timeout_s}s wall-clock timeout"
        )

    # Child finished; collect its message (if any).
    if parent_conn.poll():
        status, payload = parent_conn.recv()
        parent_conn.close()
        if status == "ok":
            return payload
        raise SandboxError(f"sandboxed solve of '{name}' failed: {payload}")

    parent_conn.close()
    raise SandboxError(
        f"sandboxed solve of '{name}' produced no result "
        f"(child exit code {proc.exitcode})"
    )
