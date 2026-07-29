"""Shared test helpers.

Lambda handlers are all named `handler.py`, which is idiomatic for Lambda and
awkward for pytest: importing two of them in one session gets whichever landed
in sys.modules first, so tests silently assert against the wrong module. Each
is therefore loaded from its path under a distinct module name.
"""
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_handler(module_name: str, handler_dir: Path, extra_paths=(), env=None):
    """Loads handler.py from `handler_dir` as `module_name`.

    `extra_paths` covers Lambda Layer directories, which are on the path at
    runtime but not when running tests from the repo.
    """
    for path in (handler_dir, *extra_paths):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    for key, value in (env or {}).items():
        os.environ.setdefault(key, value)

    spec = importlib.util.spec_from_file_location(module_name, handler_dir / "handler.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
