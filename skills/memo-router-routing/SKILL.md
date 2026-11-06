---
name: memo-router-routing
description: "Use when the memo-router plugin's memo_route tool needs guidance on category discovery, backend selection, or first-run setup. Explains the discovery-based taxonomy and pluggable backend design."
version: 0.1.0
author: memo-router plugin
license: MIT
metadata:
  hermes:
    tags: [memo-router, notes, classification]
---

# memo-router routing

This plugin deliberately does NOT ship a fixed category taxonomy or a
fixed notes-destination. Two things to keep in mind when helping a user
configure or troubleshoot it:

## Categories are discovered, not hardcoded

The `local_markdown` backend treats whatever `.md` files already exist
under the user's configured `backend_config.base_dir` as the category
list. If a user says "memo: check out this trail," classify it against
*their* existing files (e.g. `hiking-spots.md` → category `hiking-spots`),
not against some built-in enum. If no existing file matches well,
propose a new short lowercase hyphenated category name and file it
under `unsorted_file` until the user creates a real file for it.

## First-run setup

If `memo_route` returns an error saying no destination is configured,
ask the user where they already keep notes (a folder path — could be
`~/notes`, `~/Obsidian/vault`, `~/my-docs`, anything) and tell them to
set it via `backend_config.base_dir` in the plugin's settings. Don't
guess a path and create it silently.

## Backends are pluggable

If a user asks for Notion, Todoist, Google Keep, or another
destination that isn't the shipped `local_markdown` backend, explain
that adding one means implementing `backends/base.py::Backend` and
registering it — the classification/trigger logic in `hooks/` and
`tools/` never needs to change. Point them at the plugin's README
"Adding a backend" section.
