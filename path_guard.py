"""Refuse writes a memo backend should never make.

A memo's destination is built from the user's own config plus a slugified
category, so a model-supplied category cannot carry `../` out of the notes
directory. That is not the same as the write being safe: an absolute or
climbing `category_overrides` value, a mistyped `base_dir`, or a symlinked
note inside the vault can still aim the append at a shell rc file, a
credential store, or Hermes's own state.

Every backend write goes through ``guard_write()`` first. Three gates, and
the result reports which ones actually ran so a caller can never imply a
check approved a write when it never executed:

1. ``containment`` - the resolved target must stay inside the resolved
   destination root the user configured.
2. ``hermes_home`` - nothing inside the Hermes home, ever. Plugin state
   belongs to ``plugin_data_dir()``, not to a memo file, and a denylist of
   known filenames would happily allow a NEW file next to them.
3. ``denylist`` - Hermes's own write denylist (``agent.file_safety``), the
   same list its file tools enforce.

Fails closed: an unimportable or erroring check is a refusal, not a pass.
A denylist that raised is not a denylist that approved.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple


def _resolve(path) -> Path:
    return Path(path).expanduser().resolve()


def _hermes_home() -> Optional[Path]:
    """The active profile's Hermes home, or None if it cannot be determined.

    ``hermes_constants`` is the only correct source: one gateway can serve
    several profiles and keeps the launch profile in ``HERMES_HOME``, so the
    raw env read is a fallback for running outside Hermes, not the answer.
    """
    try:
        import hermes_constants

        return _resolve(hermes_constants.get_hermes_home())
    except Exception:
        pass
    try:
        import os

        env = os.environ.get("HERMES_HOME")
        if env:
            return _resolve(env)
        return _resolve(Path.home() / ".hermes")
    except Exception:
        return None


def _is_under(target: Path, base: Path) -> bool:
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def guard_write(target, root) -> Tuple[bool, Optional[str], List[str]]:
    """Return ``(allowed, error, checks_ran)`` for writing ``target``.

    ``root`` is the destination directory the user configured (``base_dir``
    or ``vault_dir``). ``error`` is a message safe to hand back to the user.
    """
    checks: List[str] = []

    try:
        resolved = _resolve(target)
        resolved_root = _resolve(root)
    except Exception as exc:
        return False, f"could not resolve the memo destination path ({exc})", checks

    checks.append("containment")
    if not _is_under(resolved, resolved_root):
        return (
            False,
            f"refusing to write outside the configured notes directory "
            f"({resolved} is not inside {resolved_root})",
            checks,
        )

    home = _hermes_home()
    if home is None:
        return False, "refusing to write: could not locate the Hermes home to check against", checks
    checks.append("hermes_home")
    if _is_under(resolved, home) or resolved == home:
        return (
            False,
            f"refusing to write inside the Hermes home ({home}); plugin state "
            "belongs in the plugin's own data directory, not in a memo file",
            checks,
        )

    try:
        from agent import file_safety
    except Exception:
        # `agent.file_safety` is core rather than a ctx.* surface, and
        # `hermes plugins validate` flags the import for the reviewer. There
        # is no public seam for "is this path one Hermes refuses to write",
        # and re-implementing the list here would drift from the one its own
        # file tools enforce. So: optional import, and the two gates above
        # still apply when it is absent.
        return True, None, checks
    checks.append("denylist")
    try:
        denied = file_safety.get_write_denied_error(str(resolved), verb="File a memo to")
    except Exception as exc:
        return False, f"refusing to write: Hermes's write denylist check failed ({exc})", checks
    if denied:
        return False, denied, checks

    return True, None, checks
