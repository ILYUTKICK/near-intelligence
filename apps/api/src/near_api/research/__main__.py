"""``python -m near_api.research`` — thin dispatch to offline research code.

Commands:

- ``fit`` — the NI-052 fixed deterministic econometric estimator
  (``research/models/fit.py``); arguments are forwarded verbatim.

Exit codes follow the research CLI convention: 0 success, 4
contract/policy failure, 2 usage. The wrapper maps only its own
failures (missing research module, unknown command) onto exit code 4;
everything else — including argument parsing of the forwarded command —
is owned by the target module.

Example::

    uv run --project apps/api python -m near_api.research fit \\
        --archive-root /path/to/research \\
        --out-dir research/models/reports \\
        --code-commit <git sha>
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import near_api

COMMANDS = ("fit",)
EXIT_CONTRACT = 4

# The editable install (the documented `uv sync` layout) places the package
# at <repo>/apps/api/src/near_api/, so the repository root is three parents up.
_REPO_ROOT_DEPTH_FROM_PACKAGE = 3


def _load_research_module(command: str, override: Path | None):
    """Locate and import-only load the research module behind a command."""
    module_names = {"fit": "ni052_fit_module"}
    candidates = []
    if override is not None:
        candidates.append(override)
    package_file = Path(near_api.__file__).resolve()
    repo_root = package_file.parents[_REPO_ROOT_DEPTH_FROM_PACKAGE]
    candidates.append(repo_root / "research" / "models" / "fit.py")
    candidates.append(Path.cwd() / "research" / "models" / "fit.py")
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(module_names[command],
                                                           candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    tried = ", ".join(str(candidate) for candidate in candidates)
    print(f"near_api.research: cannot locate the research module for command "
          f"{command!r}; tried: {tried}. Run from a repository checkout (the "
          f"documented `uv sync --project apps/api` layout) or pass the module "
          f"path before the command: python -m near_api.research --fit-module "
          f"research/models/fit.py fit ...", file=sys.stderr)
    raise SystemExit(EXIT_CONTRACT)


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="python -m near_api.research",
        description="Dispatch to the offline model research code; the wrapper "
                    "owns no estimation logic.")
    parser.add_argument("--fit-module", type=Path, default=None,
                        help="path to research/models/fit.py (default: the "
                             "repository checkout of the editable install); "
                             "must be given BEFORE the command")
    parser.add_argument("command", choices=list(COMMANDS),
                        help="research command to run")
    parser.add_argument("arguments", nargs=argparse.REMAINDER,
                        metavar="...",
                        help="arguments forwarded verbatim to the command")
    arguments = parser.parse_args(argv)
    module = _load_research_module(arguments.command, arguments.fit_module)
    return module.main(arguments.arguments)


if __name__ == "__main__":
    sys.exit(main())
