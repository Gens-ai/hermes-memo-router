"""memo-router: classify memos (voice or text) and file them into the
user's existing notes system via a pluggable backend.

See README.md for the design rationale and PLUGIN-008 in
Gens-ai/homie-space for the full decision log.
"""

from __future__ import annotations

import logging

from .backends.registry import get_backend
from .hooks.implicit_classify import make_implicit_classify_hook
from .hooks.keyword_watch import make_keyword_watch_hook
from .pending_store import PendingStore
from .tools.memo_route import make_memo_route_handler
from .schemas.memo_route import MEMO_ROUTE

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    try:
        from plugins.plugin_storage import plugin_data_dir
        data_dir = plugin_data_dir("memo-router")
    except Exception:
        from pathlib import Path
        data_dir = Path.home() / ".hermes" / "plugin-data" / "memo-router"

    backend_name = ctx.get_config("backend", "local_markdown")
    backend_config = ctx.get_config("backend_config", {}) or {}
    keyword = ctx.get_config("keyword", "memo")
    ttl = int(ctx.get_config("confirmation_ttl_seconds", 300))
    implicit_confidence_threshold = float(ctx.get_config("implicit_confidence_threshold", 0.85))

    def _get_backend():
        return get_backend(backend_name, backend_config)

    pending_store = PendingStore(data_dir, ttl_seconds=ttl)

    memo_route_handler = make_memo_route_handler(ctx, _get_backend)

    ctx.register_tool(
        name="memo_route",
        toolset="memo-router",
        schema=MEMO_ROUTE,
        handler=memo_route_handler,
    )

    def _memo_command(raw_args: str) -> str:
        text = raw_args.strip()
        if not text:
            return "Usage: /memo <text>"
        import json as _json
        result = _json.loads(memo_route_handler({"text": text}))
        if not result.get("success"):
            return f"Couldn't file that: {result.get('error', 'unknown error')}"
        lines = [f"- {f['category']} -> {f['destination']}" for f in result["filed"]]
        return "Filed:\n" + "\n".join(lines)

    ctx.register_command(
        name="memo",
        handler=_memo_command,
        description="Classify and file text as a memo (manual/demo entrypoint).",
        args_hint="<text>",
    )

    ctx.register_hook(
        "pre_gateway_dispatch",
        make_keyword_watch_hook(keyword, pending_store, ctx, _get_backend),
    )

    ctx.register_hook(
        "pre_llm_call",
        make_implicit_classify_hook(
            ctx,
            lambda: _get_backend().list_categories(),
            confidence_threshold=implicit_confidence_threshold,
        ),
    )

    try:
        from pathlib import Path as _Path
        skill_path = _Path(__file__).parent / "skills" / "memo-router-routing" / "SKILL.md"
        ctx.register_skill(
            "memo-router-routing",
            skill_path,
            description="Category discovery + backend-registry guidance for memo_route.",
        )
    except Exception:
        logger.warning("memo-router: could not register bundled skill", exc_info=True)

    logger.info("memo-router registered (backend=%s, keyword=%s)", backend_name, keyword)
