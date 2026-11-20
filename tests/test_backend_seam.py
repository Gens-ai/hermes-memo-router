"""The backend seam: a new destination is one class and one registry line.

This is the plugin's actual architectural claim, so it is tested rather
than asserted. The backend below writes to SQLite — no filesystem path, no
markdown — and is defined entirely outside `backends/`, which is what a
fork adding Notion, Todoist or Google Keep would be doing.

    python3 -m pytest tests/test_backend_seam.py -q
    # or, without pytest:
    python3 tests/test_backend_seam.py
"""

from __future__ import annotations

import inspect
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _bootstrap import import_submodule  # noqa: E402

base = import_submodule("backends.base")
registry = import_submodule("backends.registry")


class SqliteBackend(base.Backend):
    """A destination that is not a file, to prove the interface is not file-shaped."""

    name = "sqlite"

    def __init__(self, config: dict):
        self.path: str = str(config.get("db_path") or "")
        if self.path:
            with sqlite3.connect(self.path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS memos (category TEXT, text TEXT)")

    def needs_setup(self) -> bool:
        return not self.path

    def list_categories(self):
        with sqlite3.connect(self.path) as conn:
            return [r[0] for r in conn.execute("SELECT DISTINCT category FROM memos")]

    def route(self, category: str, text: str):
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute("INSERT INTO memos VALUES (?, ?)", (category, text))
            return base.RouteResult(
                ok=True, category=category, destination=f"sqlite:{self.path}#{category}"
            )
        except Exception as exc:  # the interface forbids raising
            return base.RouteResult(ok=False, category=category, destination="", error=str(exc))

    def preview(self, category: str) -> str:
        return f"sqlite:{self.path}#{category}"


def _db() -> str:
    return str(Path(tempfile.mkdtemp(prefix="memo-router-seam-")) / "memos.sqlite")


def test_a_third_party_backend_registers_and_routes():
    registry.register_backend("sqlite", SqliteBackend)
    backend = registry.get_backend("sqlite", {"db_path": _db()})

    assert not backend.needs_setup()
    result = backend.route("fishing-spots", "the gravel bar below the second bridge")
    assert result.ok, result.error
    assert result.destination.startswith("sqlite:")
    assert backend.list_categories() == ["fishing-spots"]
    assert backend.preview("bookmarks").endswith("#bookmarks")


def test_an_unconfigured_backend_asks_for_setup_instead_of_guessing():
    registry.register_backend("sqlite", SqliteBackend)
    backend = registry.get_backend("sqlite", {})
    assert backend.needs_setup()


def test_an_unknown_backend_name_is_a_clean_error():
    try:
        registry.get_backend("definitely-not-registered", {})
    except ValueError as exc:
        assert "Available:" in str(exc), "the error must name the backends that do exist"
    else:
        raise AssertionError("an unknown backend name must raise ValueError")


def test_the_shipped_backends_are_the_ones_the_manifest_offers():
    """`choices:` in plugin.yaml is a dropdown, and a stale list is unselectable."""
    root = Path(__file__).resolve().parent.parent
    manifest = (root / "plugin.yaml").read_text()
    line = next(li for li in manifest.splitlines() if li.strip().startswith("choices:"))
    declared = {c.strip() for c in line.split("[", 1)[1].rstrip("]").split(",")}
    shipped = set(registry._REGISTRY) - {"sqlite"}  # minus this file's test backend
    assert declared == shipped, f"plugin.yaml choices {declared} != registry {shipped}"


def test_the_core_never_touches_a_destination_itself():
    """Routing, classification and both hooks go through Backend.route() only.

    This is the modularity claim stated as a check: if a filesystem call
    ever appears in these modules, a new backend stops being one class and
    one registry line.
    """
    for dotted in ("tools.memo_route", "classify", "hooks.keyword_watch", "hooks.implicit_classify"):
        src = inspect.getsource(import_submodule(dotted))
        for forbidden in ("open(", "Path(", ".write_text(", ".read_text(", "os.path"):
            assert forbidden not in src, f"{dotted} touches a destination directly: {forbidden}"


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
