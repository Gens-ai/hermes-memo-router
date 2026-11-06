"""pre_gateway_dispatch hook: watches every incoming gateway message, on
every platform, for the configured keyword (default "memo") BEFORE the
message reaches auth/dispatch or the LLM.

Deliberately uses only the documented hook contract — skip / rewrite /
allow — never a private gateway API. On a keyword hit (or a pending
confirmation reply), it REWRITES the event text to inject an instruction
that makes the model ask the confirmation question (or call the
memo_route tool) through Hermes's own normal reply path, rather than
bypassing it with an unreviewed direct-send call.
"""

from __future__ import annotations

import re
from typing import Any, Optional

_YES_RE = re.compile(r"^\s*(y|yes|yeah|yep|sure|do it)\s*[.!]?\s*$", re.IGNORECASE)
_NO_RE = re.compile(r"^\s*(n|no|nope|nah|cancel|skip)\s*[.!]?\s*$", re.IGNORECASE)


def make_keyword_watch_hook(keyword: str, pending_store):
    keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)

    async def _hook(event: Any, gateway: Any, session_store: Any, **kwargs) -> Optional[dict]:
        text = getattr(event, "text", None)
        if not isinstance(text, str) or not text.strip():
            return None
        source = getattr(event, "source", None)
        chat_id = getattr(source, "chat_id", None) if source is not None else None
        if chat_id is None:
            return None
        platform = getattr(source, "platform", None)
        thread_id = getattr(source, "thread_id", None)
        # chat_id alone collides across platforms/forum-threads; compose a key.
        session_id = f"{platform}:{chat_id}:{thread_id}"

        pending = pending_store.peek(str(session_id))
        if pending is not None:
            if _YES_RE.match(text):
                pending_store.pop(str(session_id))
                injected = (
                    "[memo-router] The user confirmed. Call the memo_route tool with "
                    f"text={pending!r} now, then reply with a short one-line confirmation "
                    "of where it was filed. Do not ask anything else this turn."
                )
                return {"action": "rewrite", "text": injected}
            if _NO_RE.match(text):
                pending_store.pop(str(session_id))
                return {
                    "action": "rewrite",
                    "text": "[memo-router] The user declined. Reply with a brief acknowledgement only.",
                }
            # Anything else: drop the stale pending state and fall through to normal handling.
            pending_store.pop(str(session_id))
            return None

        if keyword_re.search(text):
            pending_store.set(str(session_id), text)
            injected = (
                "[memo-router] The user's message contains the trigger word. Ask them: "
                f'"Want me to file that as a memo? -> {text!r}" and wait for yes/no. '
                "Do not call any tool yet, do not do anything else this turn."
            )
            return {"action": "rewrite", "text": injected}

        return None

    return _hook
