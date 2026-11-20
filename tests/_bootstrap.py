"""Import the plugin package by file location, under a fixed name.

A plugin root carries ``__init__.py``, so anything that reaches the package
through its parent directory ends up named after the checkout directory —
and then the suite only runs in a folder called exactly ``memo-router``
(which is not even a legal module name). A reviewer cloning to
``memo-router-review`` would see every test error at collection.

Importing by location under an explicit name removes the dependency on the
directory name entirely. Every entry point goes through here, including a
bare ``python3 tests/test_x.py`` run that never loads a conftest.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE = "memo_router_pkg"
ROOT = Path(__file__).resolve().parent.parent


def load():
    """Return the imported plugin package, importing it once."""
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"could not load plugin package from {ROOT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


def import_submodule(dotted: str):
    """Import ``dotted`` (e.g. 'backends.local_markdown') from the package."""
    load()
    import importlib

    return importlib.import_module(f"{PACKAGE}.{dotted}")
