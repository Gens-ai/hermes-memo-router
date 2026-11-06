"""Backend registry — the actual extension point.

Adding a new destination (Notion, Todoist, Google Keep, Apple Notes,
...) means writing a class that implements backends.base.Backend and
registering it here under a name. Nothing in hooks/ or tools/ needs to
change.
"""

from __future__ import annotations

from typing import Callable, Dict

from .base import Backend
from .local_markdown import LocalMarkdownBackend

_REGISTRY: Dict[str, Callable[[dict], Backend]] = {
    "local_markdown": LocalMarkdownBackend,
}


def register_backend(name: str, factory: Callable[[dict], Backend]) -> None:
    _REGISTRY[name] = factory


def get_backend(name: str, config: dict) -> Backend:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown memo-router backend '{name}'. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name](config)
