"""Adversarial tests for the backend write guard.

Every case here is a write that must be REFUSED, plus the ordinary write
that must still succeed. Run from the plugin root (any directory name):

    python3 -m pytest tests/test_path_guard.py -q
    # or, without pytest:
    python3 tests/test_path_guard.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _bootstrap import import_submodule  # noqa: E402

guard_write = import_submodule("path_guard").guard_write
LocalMarkdownBackend = import_submodule("backends.local_markdown").LocalMarkdownBackend
ObsidianBackend = import_submodule("backends.obsidian").ObsidianBackend


def _outside_hermes_home() -> Path:
    """A scratch root that is not inside the Hermes home.

    TMPDIR itself can live under the Hermes home (Hermes points it at its
    own cache), and the guard refuses writes there by design — so a fixture
    built on the default temp dir would fail the allow-path tests for the
    right reason and hide the wrong one.
    """
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")).expanduser().resolve()
    for candidate in (Path(tempfile.gettempdir()), Path("/tmp"), Path.home()):
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if not resolved.is_dir():
            continue
        try:
            resolved.relative_to(home)
            continue  # inside the Hermes home, which the guard refuses
        except ValueError:
            return resolved
    raise RuntimeError("no scratch directory outside the Hermes home")


def _tmp_notes() -> Path:
    base = Path(tempfile.mkdtemp(prefix="memo-router-test-", dir=_outside_hermes_home()))
    (base / "fishing-spots.md").write_text("- an existing spot\n")
    return base


def test_allows_a_write_inside_the_configured_dir():
    base = _tmp_notes()
    allowed, error, checks = guard_write(base / "fishing-spots.md", base)
    assert allowed, error
    assert "containment" in checks and "hermes_home" in checks


def test_refuses_traversal_out_of_the_configured_dir():
    base = _tmp_notes()
    for escape in ("../outside.md", "../../etc/profile.d/x.sh", "sub/../../outside.md"):
        allowed, error, _ = guard_write(base / escape, base)
        assert not allowed, f"{escape} was allowed"
        assert "outside the configured notes directory" in (error or "")


def test_refuses_an_absolute_destination():
    base = _tmp_notes()
    allowed, error, _ = guard_write(Path.home() / ".bashrc", base)
    assert not allowed
    assert error


def test_refuses_a_symlink_that_escapes_the_configured_dir():
    base = _tmp_notes()
    outside = Path(tempfile.mkdtemp(prefix="memo-router-outside-")) / "secret.md"
    outside.write_text("x\n")
    link = base / "innocent.md"
    link.symlink_to(outside)
    allowed, error, _ = guard_write(link, base)
    assert not allowed, "a symlink out of the notes dir must be refused"
    assert "outside the configured notes directory" in (error or "")


def test_refuses_the_hermes_home_even_when_it_is_the_configured_dir():
    """A base_dir pointed at the Hermes home must not become writable.

    Containment passes here by construction, so this asserts the second
    gate really is independent of the first.
    """
    home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    allowed, error, checks = guard_write(home / "notes.md", home)
    assert not allowed
    assert "hermes_home" in checks
    assert "Hermes home" in (error or "")


def test_local_markdown_route_reports_a_refusal_instead_of_writing():
    base = _tmp_notes()
    backend = LocalMarkdownBackend({
        "base_dir": str(base),
        # A hostile/mistyped override is the realistic way an escape arrives.
        "category_overrides": {"evil": "../escaped.md"},
    })
    result = backend.route("evil", "should never land")
    assert not result.ok
    assert "outside the configured notes directory" in (result.error or "")
    assert not (base.parent / "escaped.md").exists()


def test_local_markdown_route_still_files_a_normal_memo():
    base = _tmp_notes()
    backend = LocalMarkdownBackend({"base_dir": str(base)})
    result = backend.route("fishing-spots", "the gravel bar below the second bridge")
    assert result.ok, result.error
    assert "the gravel bar below the second bridge" in (base / "fishing-spots.md").read_text()


def test_local_markdown_route_survives_a_broken_note_template():
    base = _tmp_notes()
    backend = LocalMarkdownBackend({
        "base_dir": str(base),
        "note_templates": {"fishing-spots": "- {nope} {text}"},
    })
    result = backend.route("fishing-spots", "a memo that must not be lost")
    assert result.ok, result.error
    assert "a memo that must not be lost" in (base / "fishing-spots.md").read_text()


def test_obsidian_route_writes_inside_the_vault_only():
    vault = _tmp_notes()
    backend = ObsidianBackend({"vault_dir": str(vault), "memos_subdir": "Memos"})
    result = backend.route("fishing-spots", "a vault memo")
    assert result.ok, result.error
    written = Path(result.destination.split(" (linked from")[0])
    assert vault in written.parents
    assert "[[" in (vault / "fishing-spots.md").read_text()


def test_route_never_raises_on_a_missing_destination():
    for backend in (LocalMarkdownBackend({}), ObsidianBackend({})):
        assert backend.needs_setup()
        result = backend.route("anything", "text")
        assert not result.ok and result.error


def test_implicit_pass_stays_silent_and_costs_nothing_when_disabled():
    """implicit_enabled: false must short-circuit before any LLM call."""
    make_hook = import_submodule("hooks.implicit_classify").make_implicit_classify_hook

    calls = []

    class Ctx:
        class llm:
            @staticmethod
            def complete_structured(*a, **kw):
                calls.append(kw)
                raise AssertionError("the disabled pass must not call the model")

    def categories():
        raise AssertionError("the disabled pass must not touch the backend")

    hook = make_hook(Ctx(), categories, enabled=False)
    out = hook(
        session_id="s", task_id="t", turn_id="1",
        user_message="the gravel bar below the second bridge was good today",
        is_first_turn=False,
    )
    assert out is None
    assert calls == []


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
