"""Tiny per-session pending-confirmation store for the keyword-watch flow.

Keyed by session_id, holds the quoted memo text + a timestamp with a
short TTL, so a bare "yes"/"no" reply on the next turn can be resolved
without re-running classification. Backed by a JSON file under the
plugin's own data directory (NOT the user's notes directory — this is
internal plugin state, not a memo).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class PendingStore:
    def __init__(self, data_dir: Path, ttl_seconds: int = 300):
        self.path = Path(data_dir) / "pending_confirmations.json"
        self.ttl_seconds = ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data))

    def set(self, session_id: str, text: str) -> None:
        data = self._load()
        data[session_id] = {"text": text, "ts": time.time()}
        self._save(data)

    def pop(self, session_id: str) -> Optional[str]:
        data = self._load()
        entry = data.pop(session_id, None)
        self._save(data)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self.ttl_seconds:
            return None
        return entry["text"]

    def peek(self, session_id: str) -> Optional[str]:
        data = self._load()
        entry = data.get(session_id)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self.ttl_seconds:
            return None
        return entry["text"]
