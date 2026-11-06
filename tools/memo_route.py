"""memo_route tool implementation — the manual/demo entrypoint and the
tool the model calls after a confirmed keyword-watch trigger."""

from __future__ import annotations

import json

from ..classify import classify


def make_memo_route_handler(ctx, get_backend):
    def handler(args: dict, **kw) -> str:
        text = (args.get("text") or "").strip()
        if not text:
            return json.dumps({"success": False, "error": "text is required"})

        backend = get_backend()
        if backend.needs_setup():
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "No notes destination configured yet. Ask the user where "
                        "they keep notes (e.g. ~/notes, ~/space, ~/my-docs) and "
                        "set memo-router's backend_config.base_dir."
                    ),
                }
            )

        explicit_category = args.get("category")
        if explicit_category:
            fragments = [{"text": text, "category": explicit_category, "confidence": 1.0}]
        else:
            fragments = classify(ctx, text, backend.list_categories(), purpose="memo-router.manual")
            if not fragments:
                fragments = [{"text": text, "category": "unsorted", "confidence": 0.0}]

        results = []
        for frag in fragments:
            result = backend.route(frag["category"], frag["text"])
            results.append(
                {
                    "category": frag["category"],
                    "destination": result.destination,
                    "ok": result.ok,
                    "error": result.error,
                    "new_destination": result.created_new_destination,
                }
            )

        return json.dumps({"success": all(r["ok"] for r in results), "filed": results})

    return handler
