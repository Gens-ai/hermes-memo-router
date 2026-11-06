# memo-router

Classifies memos — spoken or typed — and files them into **your own**
notes system, not a system this plugin invents. It ships with one
backend (plain markdown files in a folder you already use) and is built
so a Notion, Todoist, Google Keep, Apple Notes, or Obsidian-specific
backend can be added later without touching the classification or
trigger logic at all.

## Why this is a plugin, not a skill

Two triggers run on every message, in every session, on every
platform, before the model ever sees the content:

- **`pre_gateway_dispatch`** — scans every incoming gateway message for
  the word "memo" (configurable) *before* auth/dispatch. On a hit, it
  rewrites the message to ask the user to confirm filing, and resolves
  a following yes/no reply using a small per-session pending-state
  store. This can't be replicated by a skill: skills only run when
  loaded into a session that's already decided to use them; this hook
  runs unconditionally, on message traffic a skill was never invoked on.
- **`pre_llm_call`** — a second, lower-confidence pass over every
  message right before the LLM call, catching memo-worthy content that
  never said the keyword (this is what covers voice messages: Hermes's
  own STT already turns them into plain text by this point, so one
  classifier handles both typed and spoken memos with no special
  casing).

## Disclosures (per Hermes plugin-catalog admission rule 13)

- **Reads/writes outside the plugin's own data directory.** The
  `local_markdown` backend reads and appends to markdown files inside
  the user-configured `backend_config.base_dir` — this is **not** the
  plugin's isolated `plugin_data_dir()`, it's wherever the user already
  keeps notes. No other filesystem access.
- **LLM calls.** Classification uses `ctx.llm.complete_structured()` —
  host-owned credentials, whatever provider/model the user already has
  active. No separate API key, no plugin-held credential.
- **No network calls, no subprocesses, no telemetry.**
- **Internal state only:** a small JSON file under the plugin's own
  `plugin_data_dir()` holding short-TTL per-session pending
  confirmations (quoted memo text + timestamp). Cleared on resolution
  or TTL expiry.

## Config

```json
{
  "backend": "local_markdown",
  "backend_config": {
    "base_dir": "~/notes",
    "category_overrides": { "idea": "lists/ideas.md" },
    "unsorted_file": "lists/unsorted-memos.md"
  },
  "keyword": "memo",
  "confirmation_ttl_seconds": 300
}
```

`base_dir` is the only thing you need to set for the default backend —
point it at wherever you already keep markdown notes (`~/notes`,
`~/my-docs`, an Obsidian vault, whatever). Categories are **discovered**
from the `.md` files already there, not a fixed list the plugin ships
with.

## Adding a backend

Implement `backends/base.py::Backend` (`route()`, `list_categories()`)
and register it in `backends/registry.py`. Nothing in `hooks/` or
`tools/` needs to change — that separation is the point.

## Manual use / demo

`/memo <text>` or ask the model to use the `memo_route` tool directly,
useful for testing without waiting on the hook triggers.

## Status

Live-tested end-to-end on a real Hermes gateway (Telegram):

- `/memo <text>` command — files to the correct existing category file,
  or falls back to `unsorted_file` when no match exists, with the
  fallback destination's own append style mirrored.
- `pre_llm_call` implicit classification — fires on every message,
  confirmed via real `ctx.llm.complete_structured()` calls in logs.
- `pre_gateway_dispatch` keyword-watch — confirmed intercepting a
  real inbound Telegram message containing the keyword, rewriting it
  into a confirmation prompt, then resolving the yes/no reply and
  handing off to the tool. Verified on disk.

No network calls, no subprocesses, no credentials held by the plugin —
see Disclosures above.
