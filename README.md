# memo-router

Classifies memos — spoken or typed — and files them into **your own**
notes system, not a system this plugin invents. It ships with two
backends (plain markdown files, and an Obsidian vault) and is built so
a Notion, Todoist, Google Keep, or any other destination can be added
later without touching the classification or trigger logic at all.

## How it catches memos

Two triggers run on every message, in every session, on every
platform, before you ever have to ask for anything:

- **Keyword watch** (`pre_gateway_dispatch`) — scans every incoming
  message for the word "memo" (configurable) as it arrives. On a hit,
  it classifies the text *first* and asks you to confirm filing with
  the destination shown up front (e.g. "File this as a memo under
  'fishing-spots' (~/notes/fishing-spots.md)?"), not a blind yes/no
  that only reveals where it went afterward. Reply `yes`, `no`, or
  just name a different category to override it on the spot — no
  slash command, no remembering syntax, just say "memo" somewhere in
  your message.
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
  "confirmation_ttl_seconds": 300,
  "implicit_confidence_threshold": 0.85
}
```

`base_dir` is the only thing you need to set for the default backend —
point it at wherever you already keep markdown notes (`~/notes`,
`~/my-docs`, whatever). Categories are **discovered** from the `.md`
files already there, not a fixed list the plugin ships with.

### Obsidian backend

```json
{
  "backend": "obsidian",
  "backend_config": {
    "vault_dir": "~/Documents/MyVault",
    "memos_subdir": "Memos",
    "link_from_category": true
  }
}
```

No Obsidian account, sync, or API token needed — a vault is just a
folder on disk; `vault_dir` can point at one Obsidian already has open,
or any plain folder you want to treat as one. Unlike `local_markdown`'s
flat append, each memo becomes its own atomic note under
`memos_subdir`, with frontmatter (`created`, `tags: [memo, <category>]`)
— and if an existing vault note matches the chosen category, a
`[[wikilink]]` to the new note gets appended there too, so it shows up
in that note's backlinks/graph like any other reference. Categories are
discovered the same way as `local_markdown` (existing `.md` files in
the vault, excluding `memos_subdir` itself).

## Known limitations

- Classification quality depends entirely on the host LLM — the
  plugin sanity-checks the category it gets back (must be a known
  category or a short, label-like string) and falls back to
  `unsorted` rather than file under something nonsensical, but it
  can't fully correct a bad classification. Always skim what actually
  got written, especially right after setup.
- `implicit_confidence_threshold` on the implicit pass (`pre_llm_call`,
  default `0.85`) is a knob, not a guarantee — if it's firing too often
  or too rarely on your content, set it as a top-level plugin setting
  (alongside `backend`, `keyword`, etc.), not inside `backend_config`.

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
  real inbound Telegram message containing the keyword, classifying it
  first to show the destination before asking, resolving the
  yes/no/category-override reply, and handing off to the tool.
  Verified on disk.
- `obsidian` backend — confirmed creating atomic notes with correct
  frontmatter/tags and appending `[[wikilinks]]` to matching category
  notes, both via direct unit testing and through the live gateway
  against a real plugin config.
- Category sanity-check (`classify.looks_like_category`) — confirmed
  live catching a real misclassification (the LLM returning something
  that wasn't a known category or a plausible label) and falling back
  to `unsorted` instead of surfacing it.

No network calls, no subprocesses, no credentials held by the plugin —
see Disclosures above.
