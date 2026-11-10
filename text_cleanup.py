"""Strip the filing instruction out of a memo before it is written.

The trigger keyword and the "add this to X" phrasing are addressed to the
plugin, not to the note. Filed verbatim they accumulate as a transcript of
the user talking to a robot:

    - memo - bookmark https://pine64.org/... for open source smartwatch

What belongs in the file is the memo itself. This module removes only the
*instruction* wrapper and never touches the content:

- Only a PREFIX at the very start, or a filing CLAUSE at the very end, is
  removed. Nothing mid-sentence is rewritten, so the memo's own wording is
  preserved exactly.
- A trailing filing word is removed only after real punctuation ("…, add to
  bookmarks") or when a destination follows it ("…stick this in fishing
  spots"). Without that guard, a memo ending in an ordinary word from the
  filing vocabulary ("buy a new log") loses its last word.
- A strip that would leave nothing, or leave only the keyword, is discarded
  and the original text is returned. Filing a slightly chatty memo is a
  cosmetic problem; filing an empty line loses the user's note.
"""

from __future__ import annotations

import re
from typing import Optional

# Words that only ever appear as filing instructions in these positions.
_FILING = r"(?:bookmark|note|save|file|add|put|stick|log|record|remember|jot)"
# Separator between the keyword and the memo: "memo - x", "memo: x", "memo, x".
_SEP = r"(?:\s*[-\u2013\u2014:;,]+\s*|\s+)"
_PREP = r"(?:to|in|under|on|into)"
_ARTICLE = r"(?:my|the)"
_WORD = r"[\w'\-]+"
# "...to my bookmarks", "...in fishing spots" — a short destination phrase.
_DEST = rf"(?:{_ARTICLE}\s+)?{_WORD}(?:\s+{_WORD}){{0,3}}"

_MIN_KEPT_CHARS = 3


def _prefix_re(keyword: str) -> re.Pattern:
    """`memo`, `memo -`, `memo: bookmark`, `memo add this to my bookmarks:` ..."""
    return re.compile(
        rf"^\s*{re.escape(keyword)}\b"
        rf"(?:{_SEP}(?:please\s+)?{_FILING}\b"
        rf"(?:\s+(?:this|that|it))?"
        rf"(?:\s+{_PREP}\b(?:\s+{_ARTICLE})?"
        # A destination may follow, but only when punctuation then separates it
        # from the memo itself — otherwise the memo's first words get eaten.
        rf"(?:\s+{_WORD}(?:\s+{_WORD}){{0,2}}(?=\s*[:\u2013\u2014-]\s*))?"
        rf")?"
        rf")?"
        rf"{_SEP}?",
        re.IGNORECASE,
    )


_TAIL = rf"(?:and\s+|then\s+)?(?:please\s+)?{_FILING}\b(?:\s+(?:this|that|it))?"

# A: after real punctuation, a destination is optional.
_SUFFIX_PUNCT_RE = re.compile(
    rf"\s*[,;.\u2013\u2014-]+\s*{_TAIL}(?:\s+{_PREP}\b\s+{_DEST})?\s*[.!]?\s*$",
    re.IGNORECASE,
)
# B: after mere whitespace, a destination is REQUIRED.
_SUFFIX_PLAIN_RE = re.compile(
    rf"\s+{_TAIL}\s+{_PREP}\b\s+{_DEST}\s*[.!]?\s*$",
    re.IGNORECASE,
)


def _keep(candidate: str, keyword: str) -> Optional[str]:
    """Accept a strip only if it leaves a usable memo behind."""
    candidate = candidate.strip().strip("-\u2013\u2014:;, ")
    if len(candidate) < _MIN_KEPT_CHARS:
        return None
    if candidate.lower() == keyword.lower():
        return None
    return candidate


def strip_filing_boilerplate(text: str, keyword: str = "memo") -> str:
    """Return `text` without its filing instruction, or `text` unchanged.

    Never raises and never returns an empty string for non-empty input.
    """
    try:
        original = text or ""
        if not isinstance(original, str) or not original.strip():
            return text
        working = original

        for pattern in (_prefix_re(keyword), _SUFFIX_PUNCT_RE, _SUFFIX_PLAIN_RE):
            stripped = pattern.sub("", working, count=1)
            if stripped != working:
                kept = _keep(stripped, keyword)
                if kept is not None:
                    working = kept

        result = working.strip()
        return result if result else original.strip()
    except Exception:
        # A cosmetic cleanup must never cost the user their memo.
        return text
