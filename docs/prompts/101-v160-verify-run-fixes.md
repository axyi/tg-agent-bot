# Prompt 101 — spec-v1.6.0 post-freeze verify-run docs corrections

- **Date:** 2026-09-06
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** docs-only fixes from `/verify-run`'s audit of the
  resumed v1.6.0 run, sourced from this project's own git/tag objects and
  Claude Code session transcripts — no design decision, no code
- **Harness:** Claude Code
- **Stage:** post-freeze, post-tag (after T18 and the `v1.6.0` tag)
- **Owner of:** `docs/reports/report-v1.6.0.md` (four inaccuracies fixed
  in place, one new "Tag `v1.6.0` created" section, one new "Deviations —
  compiled" section), `docs/reports/tg-post-v1.6.0.md` (tag-created note,
  prompt count), `docs/llm-usage.md` (72–92 backfill replacing the known
  gap, new rows for prompts 99–101), this prompt file (new)
- **REQ ids:** REQ-V160-VER-04, E14 (tag record); REQ-V160-RPT-02 items 7
  and 13; AGENTS.md § Reporting; `standards/reporting.md` § Prompt chain

## Goal

Fix four `/verify-run` findings against the resumed spec-v1.6.0 run, now
that T18 is complete and the operator has approved and created the
`v1.6.0` tag:

1. `report-v1.6.0.md` claimed in three places that the tag "has not yet
   been requested" / "not yet created" — stale since 2026-09-06T21:00:23
   CEST (tagger timestamp) on commit `0d33af4`. Add a "Tag `v1.6.0`
   created" section recording when, on which commit, the annotated-tag
   message verbatim, and the operator's in-session approval quoted
   (sourced from this session's own `AskUserQuestion`/`Bash` tool record),
   and fix the three stale sentences.
2. The report's own account of S18 repeat 3's root cause said both the
   original summary call and its retry "truncated the same way"
   (`finish_reason="length"` both times). Read from the actual baseline
   evidence (`docs/assets/bench/baseline-v1.6.0.json`, S18/repeat 3's
   embedded `llm_calls`), attempt 2 did not truncate — it hit the
   operator's own 600 s `LLM_TIMEOUT_S` ceiling (`error_kind="transport"`,
   `latency_ms=600089`, no tokens). Correct the ledger row and the
   erratum-6 evidence sentence; leave the frozen spec text as originally
   disclosed, with one reconciling sentence.
3. The report's own three-option list for the erratum-6 decision was
   silently reordered from how `AskUserQuestion` actually presented it
   (option 1 = "Authorise erratum 6 (Recommended)", per this session's own
   tool-call record) — restore the real order/labels, source-cited.
   Separately, close the "compiled into the final §13 Deviations at T17"
   promise the running-log Deviations heading made, which T17 named as an
   open item but never actually produced.
4. `docs/llm-usage.md`: note the tag's creation is out of scope here (it
   changed no session-usage figures); add rows for prompts 99 (T17), 100
   (T18) and 101 (this correction); replace the "Known gap, not
   backfilled" placeholder for prompts 72–92 with real numbers, measured
   directly from that execution's own local Claude Code session
   transcript (`aee4c17e-2b90-40ba-9a01-cfc50b6cb1e6.jsonl`, the same
   methodology row 25 already established for this table:
   per-request `usage`, deduplicated by `requestId`).

## Constraints

- Documentation-only: `docs/spec/spec-v1.6.0.md` is frozen post-tag and
  is **not** touched, even though item 2 above corrects a claim the
  spec's own erratum-6 block also makes — the report gets a reconciling
  sentence instead of a spec edit.
- No `.py` file, no `config/`, no `.env` is touched.
- Every new claim in `report-v1.6.0.md` is sourced from a primary
  artefact already on disk or in this session's own tool-call record
  (the tag object, the baseline JSON, the `AskUserQuestion`/`Bash`
  entries in this project's session transcripts) — never asserted from
  memory.
- `docs/llm-usage.md`'s existing rows (1–52) are not renumbered or
  edited beyond the one placeholder row being replaced; new material is
  appended as new rows, per this table's own established convention
  (rows 36/43/44/46/49 all correct forward rather than rewrite history).
- One prompt → one commit, referencing this file per `AGENTS.md`'s
  commit-format rule.

## Acceptance

- `uv run --locked python devtools/checks.py lint-docs` — clean (this
  prompt file's header/blocks, and the report's ledger-row cell count
  unchanged).
- `report-v1.6.0.md`'s ledger row, header Status line, and "The tag"
  section all agree that `v1.6.0` exists, created on `0d33af4`.
- `report-v1.6.0.md`'s S18-repeat-3 paragraph and the erratum-6 evidence
  sentence both distinguish attempt 1 (truncated) from attempt 2
  (transport timeout).
- `docs/reports/tg-post-v1.6.0.md` stays **under 1500 characters** by
  `wc -m` after the tag-created edit; the report's RPT-03 line quotes
  the re-measured count.
- `docs/llm-usage.md` has no remaining "Known gap, not backfilled" row
  for prompts 72–92, and carries rows for prompts 99, 100 and 101.
- `git status --short` shows only docs files touched; exactly one commit
  is created.

## Stop

Do not run the six-gate block — docs-only change, no source/test/config
touched. Do not edit `docs/spec/spec-v1.6.0.md`. Do not push. If any of
the four findings turns out to already match the current file contents
on inspection, leave it unedited and say so rather than editing for the
sake of editing.
