# Prompt 252 — v1.11.0 T8 follow-up: three README factual corrections

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** three small, independently-verified factual
  corrections under every §5.1 threshold — orchestrator, main context,
  no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T8 (follow-up)
- **Owner of:** `README.md`
- **REQ ids:** REQ-V1110-VER-02

## Goal

T8's delegated subagent (commit `fde9fd4`) found, via its own
post-commit advisor review, three factual inaccuracies in the README
prose it had just written and flagged them for a follow-up rather than
amending its own commit. All three independently re-verified against
the actual source before fixing:

1. `README.md`'s `/documents` sample section claimed the table is
   "ordered newest first" — `storage.list_documents`
   (`storage.py:1186-1189`) orders `created_at, id` **ascending**, i.e.
   oldest first. Confirmed directly against the function.
2. The same section claimed the filename truncation "uses the same
   truncation rule `/sessions`' `title` column uses" — false:
   `/documents`' filename cuts at 23 UTF-16 units + `…`, `/sessions`'
   title cuts at 40 characters + `…`. Different limits; the parenthetical
   is simply removed rather than corrected to name two different limits
   inline (the surrounding sentence already states `/documents`' own
   limit).
3. The new `v1.11.0` release-table row described the `/model` menu's
   `callback_data` grammar as "signed" — `bot._catalogue_hash` is a
   plain unkeyed SHA-256 truncated to 8 hex digits over the catalogue's
   JSON encoding, a staleness fingerprint (MOD-08/CBQ-05's stale-menu
   detection), not a cryptographic signature (no key, no
   tamper-proofing claim holds). Reworded to describe what it actually
   does.

## Constraints

Docs only — no source or test file touched. `lint-docs` and `ruff check
.` must stay green (they don't touch `README.md`'s content, but confirm
nothing else broke).

## Acceptance

All three corrections landed verbatim in `README.md` as described above.
Gates 1-4 green (`pytest`: 2381 passed, 1 skipped, 2 xfailed — the
measured T8 collection count, 2384, is unaffected by a docs-only
change). `lint-docs` green.

## Stop

Not applicable — this is itself the correction.
