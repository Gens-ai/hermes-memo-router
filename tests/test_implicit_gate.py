"""When the implicit pass spends an LLM call, and when it must not.

    python3 tests/test_implicit_gate.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _bootstrap import import_submodule  # noqa: E402

hook_module = import_submodule("hooks.implicit_classify")

VOICE = '[The user sent a voice message. Transcript: "Memo, try the north shore for crappie"]'
PLAIN = "what is on my schedule today?"


class _Result:
    content_type = "json"
    parsed = {"fragments": [{"category": "ideas", "text": "x", "confidence": 0.99}]}


class _Llm:
    def __init__(self):
        self.calls = 0

    def complete_structured(self, **kwargs):
        self.calls += 1
        return _Result()


class _Ctx:
    def __init__(self):
        self.llm = _Llm()


def run(message, **options):
    ctx = _Ctx()
    hook = hook_module.make_implicit_classify_hook(ctx, lambda: ["ideas"], **options)
    out = hook("s", "t", "u", message, False)
    return ctx.llm.calls, out


def test_default_still_classifies_ordinary_messages():
    calls, out = run(PLAIN)
    assert calls == 1 and out


def test_keyword_only_skips_ordinary_messages():
    assert run(PLAIN, keyword_only=True) == (0, None)


def test_keyword_only_still_catches_a_spoken_memo():
    calls, out = run(VOICE, keyword_only=True)
    assert calls == 1 and out


def test_keyword_only_matches_whole_words():
    assert run("send the memorandum over today", keyword_only=True) == (0, None)


def test_keyword_only_skips_the_keyword_hooks_own_rewrite():
    text = "[memo-router] The user declined. Reply with a brief acknowledgement only."
    assert run(text, keyword_only=True) == (0, None)


def test_keyword_only_honours_a_custom_keyword():
    assert run("jot: call the dentist", keyword_only=True, keyword="jot")[0] == 1
    assert run("memo: call the dentist", keyword_only=True, keyword="jot")[0] == 0


def test_disabled_wins():
    assert run(VOICE, keyword_only=True, enabled=False) == (0, None)


if __name__ == "__main__":
    tests = [(n, f) for n, f in list(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except AssertionError as exc:
            failed += 1
            print("FAIL", name, exc)
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
