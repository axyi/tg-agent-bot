# Prompt 237 — v1.11.0 T1: the outbound table path

- **Date:** 2026-09-22
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (EC-04), brief
  `docs/spec/task-briefs/v1110-T1.md`; test-first source/test work, within
  this one subagent's single context.
- **Harness:** Claude Code (subagent)
- **Stage:** T1
- **Owner of:** `tables.py` (new), `bot.py`, `tests/fakes.py`,
  `tests/test_v1110_out.py` (new), `docs/prompts/237-v1110-t1-table-path.md`,
  `docs/llm-usage.md` (row 148), `docs/reports/report-v1.11.0.md` (`## T1`)
- **REQ ids:** REQ-V1110-OUT-01, REQ-V1110-OUT-02, REQ-V1110-OUT-03,
  REQ-V1110-OUT-04, REQ-V1110-OUT-05

## Goal

Build the outbound table path per `docs/spec/spec-v1.11.0.md` sec.3: a new
`tables.py` at the repository root (`render_table`, `fit_lines`, and
`utf16_length` moved from `bot.py`), `bot.py`'s shared `_pre_text` (redact
before fit, fit before escape, escape before wrapping) and its two public
wrappers `send_pre`/`edit_pre`, the two new `TelegramClient` methods
(`send_message_html`, `edit_message_html`), the one-time plain-text
fallback on a non-fatal table-path failure, and `tests/fakes.py`'s
`FakeTelegram` growth (`sent_payloads`, `edited_payloads`,
`callback_answers`, `commands_set`, `fail_html_with`). Test-first (EC-02):
`tests/test_v1110_out.py` written and watched red (`AttributeError` on the
not-yet-existing `bot.send_pre`/`edit_pre`/`tables` module and
`FakeTelegram.send_message_html`) before any production code landed.

## Constraints

Do not touch `tests/test_v1100_sanitization.py:293-323` (stays green,
unamended). Do not run gate 5 (`bot.py --selftest-live`),
`devtools/mutation_check.py`, `devtools/rag_eval.py` or
`devtools/agent_eval.py` — gates 1-4 only. Do not run `ruff format` (whole-
file reformat risk), only `ruff check .`. Never print, quote or commit
either of this repo's two secret values (`config.py:351`, `:379`) — env
variable names only. `--no-verify` never used.

## Acceptance

`T-V1110-OUT-01`…`-08` in `tests/test_v1110_out.py` green;
`test_t_v1100_out_04_send_payload_is_exactly_chat_id_and_text`,
`test_t_v1100_out_04_send_message_source_has_no_parse_mode_or_entities`
and `test_t_v1100_out_05_markdownv2_specials_delivered_verbatim` still pass
unamended (imported from `tests/test_v1100_sanitization.py` and called
directly inside `T-V1110-OUT-06`, matching
`tests/test_v1103_gates.py`'s own precedent for that pattern). Gates 1-4
green: `uv sync --locked` (25 resolved, 23 checked), `uv run --locked ruff
check .` (all checks passed), `uv run --locked pytest` (2322 collected,
2311 baseline + 8 new `test_v1110_out.py` functions + 3 pytest-recollected
imported functions, exit 0), `uv run --locked python bot.py --selftest`
(`selftest: OK`).

## Stop

A cited `file:line` drifting more than 5 lines from the live tree, or a
cited mechanism being absent, stops the task for a report rather than a
guess (none triggered this task — see the report's drift note). An
advisor review flagged that the first fallback implementation caught every
`TelegramError` uniformly, including the fatal 401/404 case the spec's
parenthetical ("the existing 401/404 fatal classification stands
unchanged") actually pins as excluded from the fallback; fixed in the same
prompt before the gate run recorded above, with a new negative case in
`T-V1110-OUT-05`/`-08` (a 401 producing exactly one request and `None`,
no second attempt).
