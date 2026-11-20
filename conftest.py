"""Make the suite importable from any checkout directory name.

A plugin root carries ``__init__.py``, so pytest treats the checkout itself
as a Package and imports that file to set the package up. It derives the
module name from the *directory name*, which for a clone called
``memo-router-review`` (or any name with a hyphen) is not a legal
identifier, so it falls back to plain ``__init__`` — imported with no
parent package, which makes the plugin's own ``from .backends...`` lines
fail at collection. Every test then errors at setup and the suite looks
broken when it is not.

Loading the package by file location under a fixed name and registering it
under the name pytest will derive removes the dependency on the directory
name. The same bootstrap is imported directly by each test file, so a bare
``python3 tests/test_x.py`` run (which never loads a conftest) works too.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from _bootstrap import PACKAGE, load  # noqa: E402  # type: ignore[import-not-found]

_pkg = load()

# The names pytest may derive for the plugin root's own __init__.py.
for _alias in ("__init__", Path(__file__).resolve().parent.name.replace("-", "_")):
    sys.modules.setdefault(_alias, _pkg)

__all__ = ["PACKAGE"]
