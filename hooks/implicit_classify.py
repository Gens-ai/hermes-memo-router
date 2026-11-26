"""pre_llm_call hook: a lower-confidence, second pass that catches
memo-worthy content that never mentioned the keyword — this is the
"voice memo" case, since voice messages arrive here as plain
already-transcribed text with no special marker: pre_gateway_dispatch
fires before transcription for voice, so the keyword-watch hook alone
would miss voice content; by pre_llm_call time voice and typed text are
indistinguishable, which actually simplifies things — one classifier
applied to every message, voice or not.

Returns injected context (never blocks/suppresses the turn — pre_llm_call
is additive-only per its hook contract) instructing the model to offer
filing on a HIGH-confidence single-category match, and to stay silent
otherwise so this never nags on ordinary conversation.

Every message classified here costs one host LLM call, so the pass is
switchable. The hook stays registered either way and returns early when
it is off: dropping the registration instead would make the manifest's
declared hooks disagree with what register() actually registers, which
catalog rule 6 treats as a security issue rather than a config choice.

The call is also blocking: the reply waits for it. With keyword_only the
pass runs just for messages that say the keyword, which keeps the
voice-memo case and spares every other message the wait.
"""

from __future__ import annotations

import re
from typing import Any, List, Optional

from ..classify import classify


def make_implicit_classify_hook(
    ctx, list_categories, confidence_threshold: float = 0.85, enabled: bool = True,
    keyword_only: bool = False, keyword: str = "memo",
):
    keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)

    def _hook(
        session_id: str, task_id: str, turn_id: str, user_message: Any,
        is_first_turn: bool, **kwargs,
    ) -> Optional[str]:
        if not enabled:
            return None
        text = user_message if isinstance(user_message, str) else getattr(user_message, "content", None)
        if not isinstance(text, str) or len(text.strip()) < 8:
            return None
        if keyword_only:
            # "[memo-router] ..." is the keyword hook's own rewrite: already
            # handled there, and it always contains the plugin's name.
            if text.lstrip().startswith("[memo-router]") or not keyword_re.search(text):
                return None
        try:
            fragments = classify(ctx, text, list_categories(), purpose="memo-router.implicit")
        except Exception:
            return None
        strong = [f for f in fragments if f["confidence"] >= confidence_threshold]
        if not strong:
            return None
        lines = "; ".join(f"{f['category']}: {f['text']!r}" for f in strong)
        return (
            "[memo-router] This message looks like it contains memo-worthy content "
            f"({lines}). If appropriate, mention briefly that you can file it as a memo "
            "if the user wants, but do not call the memo_route tool unless they say yes."
        )

    return _hook
