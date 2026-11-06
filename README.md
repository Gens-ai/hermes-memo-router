# memo-router

Classifies memos — spoken or typed — and files them into **your own**
notes system, not a system this plugin invents. It ships with one
backend (plain markdown files in a folder you already use) and is built
so a Notion, Todoist, Google Keep, Apple Notes, or Obsidian-specific
backend can be added later without touching the classification or
trigger logic at all.

## How it catches memos

Two triggers run on every message, in every session, on every
platform, before you ever have to ask for anything:

- **Keyword watch** (`pre_gateway_dispatch`) — scans every incoming
  message for the word "memo" (configurable) as it arrives. On a hit,
  it asks you to confirm filing, then resolves your yes/no reply and
  hands off to the tool. No slash command, no remembering syntax —
  just say "memo" somewhere in your message.
- **Implicit classification** (`pre_llm_call`) — a second, lower-confidence
  pass over every message, catching memo-worthy content that never said
  the keyword. This is also what covers voice messages: by the time
  Hermes's own speech-to-text turns them into plain text, they look
  exactly like a typed message, so the same classifier handles both
  with no special casing.

## Disclosures

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
