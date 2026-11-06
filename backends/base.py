"""Backend interface for memo-router.

Core routing/classification logic never touches a filesystem, a
database, or a third-party API directly — it only ever calls
``Backend.route()``. This is the extension point: a Notion backend, a
Todoist backend, a Google Keep backend, etc. each just implement this
interface and register under a name; nothing else in the plugin needs
to change.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RouteResult:
    ok: bool
    category: str
    destination: str  # human-readable description of where it landed (file path, Notion page url, etc.)
    created_new_destination: bool = False
    error: Optional[str] = None


class Backend(abc.ABC):
    """Implement this to add a new memo destination."""

    name: str = "base"

    @abc.abstractmethod
    def list_categories(self) -> List[str]:
        """Return known/discovered categories this backend can route into."""
        raise NotImplementedError

    @abc.abstractmethod
    def route(self, category: str, text: str) -> RouteResult:
        """File ``text`` under ``category``. Must not raise — return
        RouteResult(ok=False, error=...) on failure instead, since this
        runs inside a plugin hook callback where an exception is caught
        and logged, not surfaced to the user."""
        raise NotImplementedError

    def needs_setup(self) -> bool:
        """True if this backend has no destination configured yet and
        should prompt the user once instead of silently guessing."""
        return False

    def preview(self, category: str) -> str:
        """Human-readable destination ``route(category, ...)`` would write
        to, WITHOUT writing anything — lets callers (e.g. the keyword-watch
        confirmation prompt) show the user where a memo would land before
        they commit. Default implementation just echoes the category; a
        backend that can resolve a real path/URL without side effects
        should override this."""
        return category
