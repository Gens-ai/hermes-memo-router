# memo-router

**You say "memo" in a sentence and the thing you said ends up in the note
file you already keep.** Two hooks watch every incoming message, classify it
against the markdown files that already exist in your notes directory, and
ask once before writing — with the destination shown up front.

```
you    memo - bookmark https://pine64.org/devices/pinetime/ for an open source smartwatch
agent  File this as a memo under 'bookmarks' (~/notes/bookmarks.md)?
       Reply yes, no, or name a different category.
you    yes
agent  Filed under bookmarks → ~/notes/bookmarks.md
```

What landed in the file is `- https://pine64.org/devices/pinetime/ for an
open source smartwatch`. The word you said to the robot is not part of your
note.

## Install

```bash
hermes plugins install memo-router                   # catalog, at the reviewed pin (after this entry merges)
hermes plugins install Gens-ai/hermes-memo-router    # straight from Git, works today
```

Then point it at the notes you already have — in `~/.hermes/config.yaml`:

```yaml
plugins:
  entries:
    memo-router:
      settings:
        backend: local_markdown
        backend_config:
          base_dir: ~/notes
```

(The Desktop and TUI Plugins hub write the same keys from a settings form.)
That is the whole setup. Categories are **discovered** from the `.md` files
already in that directory — the plugin ships no taxonomy of its own.

## What it registers

| Surface | Name | What it is |
|---|---|---|
| Tool | `memo_route` | Classify text and file it. The model calls this after you confirm. |
| Command | `/memo <text>` | File something directly, without waiting for a trigger. |
| Hook | `pre_gateway_dispatch` | Keyword watch on every inbound gateway message. |
| Hook | `pre_llm_call` | Implicit classification pass on every message. |
| Skill | `memo-router-routing` | Category-discovery and first-run guidance for the model. |

Most of what you will notice happens without a tool call: the two hooks run
on every message, one of them rewrites the message text and the other adds
context to the turn. See [Disclosures](#disclosures) for exactly what that
means.

## How it catches memos

- **Keyword watch** (`pre_gateway_dispatch`) — scans each incoming message
  for the word "memo" (configurable) as it arrives. On a hit it first asks
  the model whether this is really a request to file something, so talking
  *about* memos does not trigger it. Then it classifies the text and asks you
  to confirm with the destination already resolved, rather than a blind
  yes/no that only reveals where the memo went afterwards. Reply `yes`, `no`,
  or just name a different category to override it on the spot.
- **Implicit classification** (`pre_llm_call`) — a second, higher-bar pass
  over every message, catching memo-worthy content that never said the
  keyword. This is also what covers voice messages: by the time Hermes's own
  speech-to-text has turned them into plain text they look exactly like a
  typed message, so one classifier handles both with no special casing.

## What gets written is the memo, not the instruction

`memo - bookmark https://example.com for later` is filed as
`- https://example.com for later`, and a trailing `…, add to bookmarks` goes
too. Only a prefix at the very start or a filing clause at the very end is
removed, never anything mid-sentence, and a strip that would leave nothing
behind is discarded in favour of the original text — so the worst case is a
slightly chatty note rather than a lost one. An ordinary last word that
happens to belong to the filing vocabulary ("buy a new log") is left alone.

## Where it will and will not write

The memo destination comes from your config plus a slugified category, so a
category the model invents cannot carry `../` anywhere. That alone does not
make the write safe, so every backend write passes three gates first, and
each one fails closed:

1. **Containment** — the resolved target must stay inside the notes
   directory you configured. This catches an absolute or climbing
   `category_overrides` value and a note that is a symlink out of the tree.
2. **Hermes home** — nothing inside `~/.hermes`, ever, even if you point
   `base_dir` there. A denylist of known filenames would happily allow a
   *new* file next to them.
3. **Write denylist** — Hermes's own `agent.file_safety` list, the one its
   file tools enforce. A check that errors is a refusal, not a pass.

A refused write is reported back as an error; it is never silently skipped.
What this does **not** protect you from: a `base_dir` that points somewhere
you did not mean but that passes all three gates. The memo lands there, and
it is an append to a markdown file, but it is your directory and the plugin
takes you at your word.

## Disclosures

- **Reads and writes outside the plugin's own data directory.** Both
  backends read the markdown files under the user-configured
  `backend_config.base_dir` (or `vault_dir`) — filenames to discover
  categories, and the last lines of the target file to match its existing
  append style — then append to one of them. That directory is **not** the
  plugin's isolated `plugin_data_dir()`, it is wherever you already keep
  notes. No other filesystem access, and see
  [Where it will and will not write](#where-it-will-and-will-not-write).
- **It rewrites your incoming messages.** On a keyword hit (or a reply to a
  pending confirmation) the `pre_gateway_dispatch` hook replaces the message
  text with an instruction to the model, through the documented
  skip/rewrite/allow contract, so the confirmation question goes out on
  Hermes's own reply path instead of a direct send. Your original wording is
  quoted inside that instruction and is what gets filed.
- **It injects context into turns.** On a high-confidence implicit match the
  `pre_llm_call` hook adds a line to the turn's context offering to file the
  content. It never blocks or suppresses a turn.
- **An extra LLM call per classified message.** Classification and the
  intent check go through `ctx.llm.complete_structured()` — host-owned
  credentials, whatever provider and model you already have active, no
  separate API key. The implicit pass runs on every message longer than 8
  characters, so budget one small extra call per turn, including turns
  started by cron jobs. Set `implicit_enabled: false` and that cost goes
  away; the keyword trigger does not need it.
- **No network calls, no subprocesses, no stored credentials, no telemetry.**
- **Internal state only:** a small JSON file under the plugin's own
  `plugin_data_dir()` holding short-TTL per-session pending confirmations
  (the quoted memo text, its proposed category, and a timestamp). Cleared on
  resolution or TTL expiry.

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
  "implicit_confidence_threshold": 0.85,
  "implicit_enabled": true,
  "implicit_keyword_only": false
}
```

`base_dir` is the only thing you need to set for the default backend — point
it at wherever you already keep markdown notes (`~/notes`, `~/my-docs`,
whatever).

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

No Obsidian account, sync, or API token needed — a vault is just a folder on
disk; `vault_dir` can point at one Obsidian already has open, or any plain
folder you want to treat as one. Unlike `local_markdown`'s flat append, each
memo becomes its own atomic note under `memos_subdir`, with frontmatter
(`created`, `tags: [memo, <category>]`) — and if an existing vault note
matches the chosen category, a `[[wikilink]]` to the new note gets appended
there too, so it shows up in that note's backlinks and graph like any other
reference. Categories are discovered the same way as `local_markdown`
(existing `.md` files in the vault, excluding `memos_subdir` itself).

## Known limitations

- Classification quality depends entirely on the host LLM. The plugin
  sanity-checks the category it gets back (it must be a known category or a
  short, label-like string) and falls back to `unsorted` rather than file
  under something nonsensical, but it cannot fully correct a bad
  classification. Skim what actually got written, especially right after
  setup.
- `implicit_confidence_threshold` (default `0.85`) is a knob, not a
  guarantee. If the implicit pass fires too often or too rarely on your
  content, set it as a top-level plugin setting alongside `backend` and
  `keyword` — not inside `backend_config`.
- The implicit pass costs one LLM call per message. On a chatty session that
  is real token spend. Raise `implicit_confidence_threshold` if it speaks too
  often, or set `implicit_enabled: false` to switch the pass off entirely —
  the keyword trigger and `/memo` keep working, and you stop paying per
  message.
- The reply waits for that call, typically a few seconds. Set
  `implicit_keyword_only: true` to run it only on messages that contain the
  keyword: voice memos that say it are still caught, and everything else
  skips the call. You lose suggestions on messages that never say it.

## Adding a backend

Implement `backends/base.py::Backend` — `list_categories()` and
`route(category, text)` are required, `needs_setup()` and `preview()` are
optional — and add one line to `_REGISTRY` in `backends/registry.py` (plus
the name to `choices:` in `plugin.yaml`, so it shows up in the settings
dropdown). Nothing in `hooks/`, `tools/` or `classify.py` changes; that
separation is the point, and it is why a Notion, Todoist or Google Keep
destination can arrive without touching the classification or trigger logic.

The interface is not file-shaped. `tests/test_backend_seam.py` builds a
backend that writes to SQLite instead of markdown, registers it, and routes
a memo through it — and asserts that the core modules contain no filesystem
calls at all, so the claim above is checked rather than promised.

To be precise about the limit: this is modular, not plugin-loadable. There
is no config key that imports a backend from somewhere else, so adding one
means editing these files in your own copy. A separate Hermes plugin cannot
inject one.

## Tests

No Hermes process and no pytest required:

```bash
python3 tests/test_text_cleanup.py
python3 tests/test_implicit_gate.py
python3 tests/test_path_guard.py
python3 tests/test_backend_seam.py
# or, with pytest installed:
python3 -m pytest tests -q
```

`tests/test_path_guard.py` is the adversarial arm: traversal, absolute
paths, an escaping symlink, a `category_overrides` value pointed out of the
tree, and the Hermes home itself all have to come back refused, with the
ordinary memo still filed. `tests/test_backend_seam.py` covers the
extension point described above.

## Verified behaviour

Exercised end-to-end against a live Hermes gateway (Telegram), not only in
unit tests:

- `/memo <text>` files to the correct existing category file, or falls back
  to `unsorted_file` when no category matches, mirroring the fallback file's
  own append style.
- The `pre_llm_call` implicit pass fires on real messages, with the
  `ctx.llm.complete_structured()` calls confirmed in the gateway logs.
- The `pre_gateway_dispatch` keyword watch intercepts a real inbound
  message, classifies it before asking, resolves a `yes`/`no`/category
  override reply, and hands off to the tool. Checked on disk.
- The `obsidian` backend creates atomic notes with the right
  frontmatter and tags and appends `[[wikilinks]]` to matching category
  notes, both in unit tests and through the live gateway.
- The category sanity check (`classify.looks_like_category`) caught a real
  misclassification live — the model returned something that was neither a
  known category nor a plausible label — and fell back to `unsorted`.
