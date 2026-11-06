"""Shared classification core used by both trigger hooks and the manual tool.

Uses ctx.llm.complete_structured() — the host-owned LLM access surface
for plugins — so it runs against whatever provider/model the user is
already using, no separate API key.
"""

from __future__ import annotations

import re
from typing import List, TypedDict

# A sane category is short and label-like — guards against the classifier
# (or a user's override reply) returning something that isn't really a
# category: a full sentence, a question, or — seen live — a stray
# identifier that leaked in from elsewhere in context.
_CATEGORY_LIKE_RE = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,39}$", re.IGNORECASE)


def looks_like_category(text: str) -> bool:
    stripped = text.strip()
    if "?" in stripped or "!" in stripped:
        return False
    if len(stripped.split()) > 4:
        return False
    return bool(_CATEGORY_LIKE_RE.match(stripped))

_SCHEMA = {
    "type": "object",
    "properties": {
        "fragments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "category": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["text", "category", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["fragments"],
    "additionalProperties": False,
}


class Fragment(TypedDict):
    text: str
    category: str
    confidence: float


def classify(ctx, text: str, known_categories: List[str], purpose: str) -> List[Fragment]:
    """Split `text` into one or more category-tagged fragments.

    known_categories comes from the backend's discovered/configured
    categories — the classifier is told to prefer them but may propose
    a new one if nothing fits (caller decides whether to accept that).
    """
    categories_hint = ", ".join(known_categories) if known_categories else "(none yet — propose one)"
    instructions = (
        "Split the user's message into one or more distinct memo fragments if it "
        "mixes topics (e.g. a grocery item and a place to visit in the same sentence). "
        "For each fragment, assign the closest matching category from this list when "
        f"one fits: {categories_hint}. If nothing fits, propose a short new lowercase "
        "hyphenated category name. Give a confidence 0-1 for how clearly this fragment "
        "belongs in that category (not how clearly it's worth saving at all)."
    )
    result = ctx.llm.complete_structured(
        instructions=instructions,
        input=[{"type": "text", "text": text}],
        json_schema=_SCHEMA,
        schema_name="memo_router.fragments",
        purpose=purpose,
        temperature=0.0,
        max_tokens=512,
    )
    if result.content_type != "json" or not result.parsed:
        return []
    fragments = result.parsed.get("fragments", [])
    known_lower = {c.lower() for c in known_categories}
    cleaned: List[Fragment] = []
    for f in fragments:
        try:
            category = str(f["category"]).strip().lower()
            # Don't trust a category blindly just because the model returned
            # it: if it's not one we told the model about AND it doesn't even
            # look like a plausible short label, something went wrong (seen
            # live: a stray identifier from elsewhere in context came back as
            # a "category") — fall back to "unsorted" rather than surface it.
            if category not in known_lower and not looks_like_category(category):
                category = "unsorted"
            cleaned.append(
                Fragment(
                    text=str(f["text"]).strip(),
                    category=category,
                    confidence=float(f["confidence"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return cleaned
