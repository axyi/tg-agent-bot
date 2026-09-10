# Task brief — v1.8.0 T8 review-finding fixes

REQ-V180-REV-01's clean-context review (already run) found two must/should-fix
items. Fix both, in one commit.

## Fix 1 (🔴 must-fix) — `reading_strip_section` never wired into `/`

`dashboard_render.py`'s `reading_strip_section(*, calls, total_tokens,
cost_usd, error_rate)` (T4, REQ-V180-DSH-05: "`/`'s reading strip... taking
already-computed totals") is built and unit-tested but never called from
`dashboard_server.py`'s `_page_usage` (around line 676) — the `/` page never
shows it. Wire it in: `_page_usage` already computes `totals` (the same
shape `_usage_totals()` returns / `usage_section` consumes — read that
function first to find the exact keys: `calls`, likely `input_tokens` +
`output_tokens` or a combined total, `cost` cells, `error_rate`/`errors`
vs `calls`). Call `dashboard_render.reading_strip_section(...)` with the
right totals and prepend its output to `_page_usage`'s `body` list, before
`usage_section`'s own totals table. Add or extend one test asserting the
reading strip actually appears in `/`'s rendered output (in
`tests/test_v180_dashboard.py` or `tests/test_dashboard.py`, whichever
already has a `_page_usage`-level fixture to extend).

## Fix 2 (🟡 should-fix) — `_TypingIndicator.start()` can raise into `process_update`

`bot.py`'s `_TypingIndicator.start()` calls `self._thread.start()`
unguarded (around `bot.py:797`'s call site,
`threading.Thread.start()` inside the class's own `start()` method).
`threading.Thread.start()` can raise `RuntimeError` under thread-resource
exhaustion, and today that propagates straight out of `process_update`,
violating REQ-V180-CHAT-06 ("neither mechanism may raise out of
`process_update`") and the same discipline `_StatusMessage`/the indicator's
own `_run` loop already follow (catch, log one redacted warning, disable,
never raise). Wrap `self._thread.start()` in try/except matching that
pattern: on failure, log `config.redact()`-wrapped warning, mark the
indicator disabled/no-op (so `stop()` is still safe to call), and do not
raise. Add a negative test mirroring `T-V180-CHAT-07`'s shape but for
`Thread.start()` raising instead of `tg.call` raising (a fake/monkeypatched
`threading.Thread` that raises `RuntimeError` from `start()`).

## Constraints

- Only `dashboard_server.py`, `bot.py`, and the one test file each fix
  needs. No other file.
- No file outside this repository is read or written (EC-01).
- Conventional commit `fix:`. Header ≤ 72 Unicode characters, no trailing
  period. Body references
  `(prompt: docs/prompts/136-v180-t8-review-fixes.md)`. End with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FnGubtn2ec8m9fan73tGzZ
  ```
- Write your own prompt file first at
  `docs/prompts/136-v180-t8-review-fixes.md` using
  `docs/prompts/TEMPLATE.md`'s exact shape, committed together with your
  changes.
- Run `uv run --locked ruff check .` and the whole `uv run --locked
  pytest` suite before returning — must be fully green (currently 1217
  collected, 1216 passed + 1 skipped, plus your new test(s)).
- If a pre-existing test file breaks unexpectedly, STOP and report back
  rather than fixing it yourself.

## Report back

A summary only: the two diffs (`file:line`), the commit sha, full pytest
result. Do not paste full file contents back.
