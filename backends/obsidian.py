"""Obsidian vault backend: each memo becomes its own atomic note (with
frontmatter + tags), and — when an existing note matches the chosen
category — a wikilink to it gets appended there too, so the memo shows
up in that note's backlinks/graph like any other Obsidian reference.

This is deliberately NOT just "local_markdown pointed at a vault folder":
an Obsidian vault has its own conventions (frontmatter, `[[wikilinks]]`,
one-note-per-idea) that a plain flat-file-append doesn't honor, and
demonstrating that difference is the point of the backend being
pluggable at all — see backends/base.py and backends/registry.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .base import Backend, RouteResult


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "note"


def _title_from_text(text: str, max_words: int = 6) -> str:
    words = text.strip().split()
    title = " ".join(words[:max_words])
    return title if title else "memo"


class ObsidianBackend(Backend):
    name = "obsidian"

    def __init__(self, config: dict):
        self.config = config or {}
        vault_dir = self.config.get("vault_dir")
        self.vault_dir: Optional[Path] = Path(vault_dir).expanduser() if vault_dir else None
        self.memos_subdir: str = self.config.get("memos_subdir", "Memos")
        self.link_from_category: bool = self.config.get("link_from_category", True)
        self.extra_tags: List[str] = self.config.get("extra_tags", [])

    def needs_setup(self) -> bool:
        return self.vault_dir is None

    def list_categories(self) -> List[str]:
        if self.vault_dir is None or not self.vault_dir.exists():
            return []
        memos_path = self.vault_dir / self.memos_subdir
        found = set()
        for path in self.vault_dir.rglob("*.md"):
            try:
                path.relative_to(memos_path)
                continue  # skip memo notes themselves — they aren't categories
            except ValueError:
                pass
            found.add(_slugify(path.stem))
        return sorted(found)

    def _find_category_note(self, category: str) -> Optional[Path]:
        assert self.vault_dir is not None
        slug = _slugify(category)
        memos_path = self.vault_dir / self.memos_subdir
        for path in self.vault_dir.rglob("*.md"):
            try:
                path.relative_to(memos_path)
                continue
            except ValueError:
                pass
            if _slugify(path.stem) == slug:
                return path
        return None

    def preview(self, category: str) -> str:
        if self.vault_dir is None:
            return category
        memos_dir = self.vault_dir / self.memos_subdir
        return str(memos_dir / f"{_slugify(category)}-<memo note>.md")

    def route(self, category: str, text: str) -> RouteResult:
        if self.vault_dir is None:
            return RouteResult(ok=False, category=category, destination="", error="vault_dir not configured")
        try:
            memos_dir = self.vault_dir / self.memos_subdir
            memos_dir.mkdir(parents=True, exist_ok=True)

            title = _title_from_text(text)
            slug = _slugify(title)
            timestamp = datetime.now(timezone.utc)
            note_path = memos_dir / f"{timestamp.strftime('%Y%m%d%H%M%S')}-{slug}.md"

            tags = ["memo", _slugify(category), *self.extra_tags]
            frontmatter = (
                "---\n"
                f"created: {timestamp.isoformat()}\n"
                f"tags: [{', '.join(tags)}]\n"
                "---\n\n"
            )
            note_path.write_text(frontmatter + text.strip() + "\n")

            linked_note: Optional[Path] = None
            if self.link_from_category:
                linked_note = self._find_category_note(category)
                if linked_note is not None:
                    existing = linked_note.read_text()
                    with linked_note.open("a") as f:
                        if existing and not existing.endswith("\n"):
                            f.write("\n")
                        f.write(f"- [[{note_path.stem}]]\n")

            destination = str(note_path)
            if linked_note is not None:
                destination += f" (linked from {linked_note.name})"
            return RouteResult(ok=True, category=category, destination=destination, created_new_destination=True)
        except OSError as exc:
            return RouteResult(ok=False, category=category, destination="", error=str(exc))
