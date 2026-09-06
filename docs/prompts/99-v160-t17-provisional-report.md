# Prompt 99 — spec-v1.6.0 T17: provisional report

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** closing out REQ-V160-RPT-02's remaining items against
  already-established facts (an upstream semconv check, one bounded live
  dashboard-startup capture, a scanner-suppression grep, and arithmetic
  already computed) — no design decision open
- **Harness:** Claude Code
- **Stage:** T17
- **Owner of:** `docs/reports/report-v1.6.0.md` (header status, Ledger row,
  the new "T17 — provisional report" section), `docs/reports/tg-post-v1.6.0.md`
  (new), `docs/llm-usage.md` (one new row), this prompt file
- **REQ ids:** REQ-V160-RPT-01, -02, -03, REQ-V160-ACC-03

## Goal

Land the provisional `report-v1.6.0.md` carrying every REQ-V160-RPT-02 item
except item 4's `<implementation-tip>` SHA and every T18 artefact (per
REQ-V160-ACC-03: "T17 lands a provisional report... that commit's
resulting SHA **is** `<implementation-tip>`"). Four RPT-02 items had never
been addressed anywhere in this report across T0–T16: item 2's final test
count, item 8's two VERIFY markers plus the span-name rule, item 9's
dashboard evidence, item 11's scanner-suppression summary, and item 12's
fix-cycle count — all closed in this prompt's new "T17" section. Also
write `docs/reports/tg-post-v1.6.0.md` (RPT-03) and append one
`docs/llm-usage.md` row for this prompt and the erratum-6/T16 prompts
(97–98).

## Constraints

- Documentation and evidence only — REQ-V160-BEN-07's freeze (source, test,
  config, scenario, tool-schema, model-setting, inference-setting) is in
  force since T16's commit.
- Item 8's upstream check is a live, real read against
  `open-telemetry/semantic-conventions-genai` (`gh api`, not assumed from
  memory or training data) — recorded with the exact commit SHA fetched
  against.
- Item 9's live dashboard-startup capture must never let Telegram polling
  process a real update or send a message: `bot.py` was started under
  `timeout 8`, its log captured, and the process killed before any
  `poll_loop` iteration could complete (dashboard binds and logs before
  polling starts, confirmed by reading `bot.py:1452-1480` first). The
  bot's own Telegram username is redacted in the report — public via
  Telegram regardless, but not necessary evidence and not worth publishing
  in a repository report.
- No re-verification of E3's `/status` text or E6's canary property via a
  fresh live run against production state — cited from the existing,
  passing automated suite instead (seeding a real canary into the running
  bot's own database for no additional evidentiary value was rejected).

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` — clean, Ledger row
  cell count unchanged (9 cells, matching the row's existing shape).
- `docs/reports/tg-post-v1.6.0.md` — Russian, 1477 characters by `wc -m`
  (quoted in the report).
- `git status --porcelain` — exactly the four owned files.
- This commit's own SHA is `<implementation-tip>` — recorded as such by
  T18's evidence-only commit, not asserted here.

## Stop

None — every remaining item was either a direct read (upstream repo, the
codebase's own boundary constants) or a bounded, already-safe live capture.
