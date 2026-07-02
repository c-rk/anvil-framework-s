"""Run entry point for the Anvil backend.

Usage:
    python -m anvil_server.run                       # Tier A (in-process), port 8000
    python -m anvil_server.run --project ./my_study  # mount a project registry
    NATIVE_ONLY=1 python -m anvil_server.run         # Tier B (native-only)

Environment variables:
    ANVIL_HOST     (default 127.0.0.1)
    ANVIL_PORT     (default 8000)
    ANVIL_PROJECT  (project dir / .anvil dir / project .db -- same as --project)
    NATIVE_ONLY    (1/true -> Tier B registry filtering)
    ANVIL_CORS_ORIGINS  (comma-separated extra CORS origins)
"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser(description="Run the Anvil web backend.")
    ap.add_argument(
        "--project",
        default=None,
        help="project directory (with .anvil/project_*.db), .anvil dir, or "
             "a project .db file; its RSQs are merged into the web registry",
    )
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args()

    # Settings are read from the environment once at app import, so flags are
    # exported BEFORE the app module loads.
    if args.project:
        os.environ["ANVIL_PROJECT"] = os.path.abspath(args.project)

    host = args.host or os.environ.get("ANVIL_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("ANVIL_PORT", "8000"))
    uvicorn.run("anvil_server.app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
