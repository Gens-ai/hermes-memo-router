"""Shared classification core used by both trigger hooks and the manual tool.

Uses ctx.llm.complete_structured() — the host-owned LLM access surface
for plugins — so it runs against whatever provider/model the user is
already using, no separate API key.
"""

from __future__ import annotations

from typing import List, TypedDict

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
    cleaned: List[Fragment] = []
    for f in fragments:
        try:
            cleaned.append(
                Fragment(
                    text=str(f["text"]).strip(),
                    category=str(f["category"]).strip().lower(),
                    confidence=float(f["confidence"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return cleaned
