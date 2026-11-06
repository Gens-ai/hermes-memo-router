"""pre_gateway_dispatch hook: watches every incoming gateway message, on
every platform, for the configured keyword (default "memo") BEFORE the
message reaches auth/dispatch or the LLM.

Classifies first, so the confirmation prompt shows the user WHERE the
memo would land (and lets them override the category) before anything
is written — rather than a blind yes/no that only reveals the
destination after the fact.

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

from ..classify import classify

_YES_RE = re.compile(r"^\s*(y|yes|yeah|yep|sure|do it)\s*[.!]?\s*$", re.IGNORECASE)
_NO_RE = re.compile(r"^\s*(n|no|nope|nah|cancel|skip)\s*[.!]?\s*$", re.IGNORECASE)
# A real category name is short and label-like, not a sentence/question the
# user is actually directing at the assistant — guards against e.g. a
# genuine follow-up question getting swallowed as a literal category name.
_CATEGORY_LIKE_RE = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,39}$", re.IGNORECASE)


def _looks_like_category(text: str) -> bool:
    stripped = text.strip()
    if "?" in stripped or "!" in stripped:
        return False
    if len(stripped.split()) > 4:
        return False
    return bool(_CATEGORY_LIKE_RE.match(stripped))


def make_keyword_watch_hook(keyword: str, pending_store, ctx, get_backend):
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

        pending = pending_store.peek(session_id)
        if pending is not None:
            memo_text = pending["text"]
            category = pending["category"]

            if _YES_RE.match(text):
                pending_store.pop(session_id)
                injected = (
                    "[memo-router] The user confirmed. Call the memo_route tool with "
                    f"text={memo_text!r}, category={category!r} now, then reply with a "
                    "short one-line confirmation of where it was filed. Do not ask "
                    "anything else this turn."
                )
                return {"action": "rewrite", "text": injected}
            if _NO_RE.match(text):
                pending_store.pop(session_id)
                return {
                    "action": "rewrite",
                    "text": "[memo-router] The user declined. Reply with a brief acknowledgement only.",
                }
            if _looks_like_category(text):
                # Short, label-like reply: treat as a category override and
                # file immediately (no second round-trip) so e.g.
                # "fishing-spots" or "ideas" both just work.
                pending_store.pop(session_id)
                override_category = text.strip()
                injected = (
                    "[memo-router] The user wants a different category. Call the "
                    f"memo_route tool with text={memo_text!r}, category={override_category!r} "
                    "now, then reply with a short one-line confirmation of where it was "
                    "filed. Do not ask anything else this turn."
                )
                return {"action": "rewrite", "text": injected}
            # Doesn't look like yes/no/a category — probably an unrelated message
            # (a question, a new topic) rather than an answer to the prompt. Drop
            # the pending confirmation and let this be handled as a normal turn,
            # instead of misfiling a sentence as a literal category name.
            pending_store.pop(session_id)
            return None

        if keyword_re.search(text):
            backend = get_backend()
            if backend.needs_setup():
                return {
                    "action": "rewrite",
                    "text": (
                        "[memo-router] The user wants to file a memo but no notes "
                        "destination is configured yet. Ask them where they keep "
                        "notes (a folder path) and tell them to set it via "
                        "memo-router's backend_config.base_dir setting. Do not "
                        "call any tool this turn."
                    ),
                }
            known_categories = backend.list_categories()
            try:
                fragments = classify(ctx, text, known_categories, purpose="memo-router.keyword_watch")
            except Exception:
                fragments = []
            category = fragments[0]["category"] if fragments else "unsorted"
            # The classifier is told to prefer known_categories but may propose a
            # new one. If what comes back is neither a known category nor a sane
            # short label, don't trust it blindly — fall back to "unsorted" rather
            # than surface garbage (seen live: a stray identifier from elsewhere
            # in context got returned as a "category").
            if category not in known_categories and not _looks_like_category(category):
                category = "unsorted"
            destination = backend.preview(category)

            pending_store.set(session_id, {"text": text, "category": category})
            injected = (
                "[memo-router] The user's message contains the trigger word. Ask them: "
                f'"File this as a memo under \'{category}\' ({destination})? Reply yes, '
                f'no, or name a different category." Quote their original text: {text!r}. '
                "Do not call any tool yet, do not do anything else this turn."
            )
            return {"action": "rewrite", "text": injected}

        return None

    return _hook
