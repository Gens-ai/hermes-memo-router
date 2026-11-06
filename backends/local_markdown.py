"""Default v1 backend: plain markdown files in a user-configured directory.

Deliberately NOT opinionated about the user's topic taxonomy or note
format (see PLUGIN-008 design doc / README for the reasoning):

- Categories are DISCOVERED from whatever .md files already exist under
  base_dir, not a fixed enum shipped by the plugin.
- Note append format mirrors whatever that file's existing last lines
  look like (bullet, plain line, dated entry) instead of imposing a
  schema, unless the user set an explicit note_template override.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

from .base import Backend, RouteResult


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "unsorted"


def _guess_line_style(existing_text: str) -> str:
    """Look at the last non-empty lines of a file and guess how new
    entries should be appended. Falls back to a plain "- " bullet for
    an empty/new file, which is the most common markdown list style."""
    lines = [ln for ln in existing_text.splitlines() if ln.strip()]
    if not lines:
        return "- {text}"
    last = lines[-1]
    if last.lstrip().startswith(("- ", "* ")):
        prefix = last[: len(last) - len(last.lstrip())]
        bullet = last.lstrip()[0]
        return f"{prefix}{bullet} " + "{text}"
    if re.match(r"^\d+\.\s", last.lstrip()):
        return "{text}"  # numbered lists are awkward to append to safely; just append the raw line
    return "{text}"


class LocalMarkdownBackend(Backend):
    name = "local_markdown"

    def __init__(self, config: dict):
        self.config = config or {}
        base_dir = self.config.get("base_dir")
        self.base_dir: Optional[Path] = Path(base_dir).expanduser() if base_dir else None
        self.category_overrides: dict = self.config.get("category_overrides", {})
        self.unsorted_file: str = self.config.get("unsorted_file", "unsorted-memos.md")

    def needs_setup(self) -> bool:
        return self.base_dir is None

    def list_categories(self) -> List[str]:
        if self.base_dir is None or not self.base_dir.exists():
            return list(self.category_overrides.keys())
        found = set(self.category_overrides.keys())
        for path in self.base_dir.rglob("*.md"):
            found.add(_slugify(path.stem))
        return sorted(found)

    def _resolve_path(self, category: str) -> Path:
        assert self.base_dir is not None
        if category in self.category_overrides:
            return self.base_dir / self.category_overrides[category]
        slug = _slugify(category)
        for path in self.base_dir.rglob("*.md"):
            if _slugify(path.stem) == slug:
                return path
        return self.base_dir / self.unsorted_file

    def route(self, category: str, text: str) -> RouteResult:
        if self.base_dir is None:
            return RouteResult(ok=False, category=category, destination="", error="base_dir not configured")
        try:
            target = self._resolve_path(category)
            created_new = not target.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text() if target.exists() else ""
            style = self.config.get("note_templates", {}).get(category) or _guess_line_style(existing)
            line = style.format(text=text.strip())
            with target.open("a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write(line.rstrip("\n") + "\n")
            return RouteResult(ok=True, category=category, destination=str(target), created_new_destination=created_new)
        except OSError as exc:
            return RouteResult(ok=False, category=category, destination="", error=str(exc))
