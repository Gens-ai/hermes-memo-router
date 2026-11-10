"""Tests for text_cleanup.strip_filing_boilerplate.

Run from the plugin root with no Hermes process required:

    python3 -m pytest tests/test_text_cleanup.py -q
    # or, without pytest:
    python3 tests/test_text_cleanup.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from text_cleanup import strip_filing_boilerplate as strip  # noqa: E402

# Instruction wrapper removed, memo preserved verbatim.
STRIPS = [
    ("memo - bookmark https://pine64.org/devices/pinetime/ for open source smartwatch",
     "https://pine64.org/devices/pinetime/ for open source smartwatch"),
    ("memo - survival skills app, add to bookmarks", "survival skills app"),
    ("memo: the gravel bar below the second bridge", "the gravel bar below the second bridge"),
    ("memo bookmark https://example.com", "https://example.com"),
    ("memo add this to my bookmarks: https://example.com", "https://example.com"),
    ("memo - books to read: Dune", "books to read: Dune"),
    ("memo   https://a.b", "https://a.b"),
    ("Dune, add to books to read", "Dune"),
    ("the gravel bar stick this in fishing spots", "the gravel bar"),
    ("memo - buy a new log", "buy a new log"),
    # Keyword present => prefix strip is correct even when the memo itself
    # contains a filing-vocabulary word.
    ("memo - chainsaw log splitter at the hardware store",
     "chainsaw log splitter at the hardware store"),
]

# Must come back untouched: no keyword, keyword mid-sentence, degenerate input,
# or an ordinary last word that happens to be in the filing vocabulary.
KEEPS = [
    "remember the milk",
    "memo",
    "memo - save",
    "the memo router plugin is broken",
    "buy a new log",
    "Hebrews 11 sermon note",
    "",
]


def test_strips_filing_instructions():
    for raw, expected in STRIPS:
        assert strip(raw) == expected, f"{raw!r} -> {strip(raw)!r} (expected {expected!r})"


def test_leaves_content_alone():
    for raw in KEEPS:
        assert strip(raw) == raw, f"{raw!r} -> {strip(raw)!r} (expected unchanged)"


def test_honours_configured_keyword():
    assert strip("jot - a thing, save it to notes", keyword="jot") == "a thing"
    # The default keyword must not fire when a different one is configured.
    assert strip("memo - a thing", keyword="jot") == "memo - a thing"


def test_never_raises_or_empties():
    junk: list = [None, 12345, [], "   "]
    for item in junk:
        strip(item)  # type: ignore[arg-type]  # must not raise on junk input
    assert strip("memo -") == "memo -"


if __name__ == "__main__":
    passed = failed = 0
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
