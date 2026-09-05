# Prompt 89 — spec-v1.6.0 T15: offline gates + live preflight — STOP

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** T15 is orchestrator work — running the six gates plus
  the `full` profile verbatim, resolving LM Studio (PRE-03), and executing
  the mandatory inference preflight (PRE-04) — the same session that ran
  T0–T14, with no delegation per §14.1 (T15 is "only commands run," no file
  scope).
- **Harness:** Claude Code
- **Stage:** T15
- **Owner of:** `.env` (`LMSTUDIO_BASE_URL` line only, via `sed -i`),
  `docs/reports/report-v1.6.0.md`, this prompt file
- **REQ ids:** REQ-V160-PRE-03, REQ-V160-PRE-04

## Goal

Run gates 1–4 and 6 verbatim, plus the `full` profile's non-live members;
resolve the LM Studio address (PRE-03) and rewrite `.env` accordingly; run
gate 5 (`bot.py --selftest-live`) and identify the instrument (PRE-04's four
values); run the one-completion inference preflight
(`max_tokens=16`, no tools, the fixed prompt) that PRE-04 requires before
`smoke-v160`. On every offline gate green and a passing preflight, proceed
to `smoke-v160` (REQ-V160-BEN-07) and record the T15 report section. On a
failed preflight, PRE-04 states plainly this "stops the run at T15, before
the baseline" — emit that stop instead of proceeding.

## Constraints

- No production/test/config file may be touched (T15 has no file scope
  per §14.1; the `.env` rewrite is the one permitted exception, and only
  via the single-line `sed -i` REQ-V160-EC-04 names — never a full read or
  print of the file).
- Gates run in the spec's own order, unconditionally, offline first.
- Gate 5 and the live preflight are not simulated, faked, or skipped for
  convenience — a real HTTP round trip against the resolved LM Studio
  address, using the project's own `llm.build_llm_client`, is required.
- No reinterpretation of REQ-V160-PRE-04's MUST: a failed preflight is a
  stop, not a threshold to negotiate downward from inside this task.
- No commit until the report section reflects the true, current outcome
  (STOP or pass) — never a report written ahead of the evidence.

## Acceptance

- Gates 1, 2, 3, 4, 6 — exit 0 (`uv sync --locked`; `ruff check .`;
  `pytest`, 1015 collected, all pass; `bot.py --selftest`; `mutation_check.py`,
  83/83 killed).
- `checks.py doctor`, `install_hooks.py --check`, `checks.py lint-docs` —
  PASS. A synthetic `checks.py run --profile pre-push --stdin-refs` line
  (hand-constructed, mirroring git's real pre-push protocol) — exit 0
  across every member gate, `skylos`'s 19 findings noted as non-blocking.
- `.env`'s `LMSTUDIO_BASE_URL` resolved to a reachable address, verified via
  `grep -q`, not by printing the file.
- `bot.py --selftest-live` — exit 0, all six live checks OK.
- PRE-04's four values recorded: served model id (live), LM Studio version
  and loaded context length (operator, carried from T0), generation
  settings (from source).
- The inference preflight either returns non-empty content (pass →
  `smoke-v160` runs next) or does not (STOP, recorded per PRE-04's own
  instruction) — this run resulted in the latter.

## Stop

**STOP.** The literal preflight (`max_tokens=16`) returns
`finish_reason=length`, `completion_tokens=15`, `reasoning_tokens=15`,
empty content — `qwen/qwen3.8-27b` spends its entire tiny budget on hidden
reasoning before emitting any visible answer text. This is a genuine,
reproducible failure of PRE-04's stated MUST, not a connectivity or
model-availability problem (the model is confirmed present and responsive:
gate 5 all-green, `served_model_id` matches, and a second diagnostic call
at `max_tokens=2048` — production's actual `LLM_MAX_TOKENS` — returns
`finish_reason=stop` with non-empty content `'\n\nready'`).

Before treating this as a spec-defect artefact rather than a real stop,
consulted `advisor()` (this run's established pattern for the
non-mechanical judgment calls, per T10's `QUALITY_GATE_SLACK` precedent).
Guidance received and followed exactly: the spec anticipated this
possibility and gave the answer directly (REQ-V160-PRE-01's "on failure
stop and emit the blocker template instead of guessing"; PRE-04's "a
failed preflight... stops the run at T15, before the baseline"); v1.4's own
RSN-06 STOP (`docs/prompts/36-v14-t4-rsn-spike.md`, commit `485fcc5`)
already proved reasoning cannot be disabled on this model/LM-Studio
combination, which makes reasoning-token consumption a permanent property
of the instrument, not a preflight quirk to route around; and this session
has no authority to reinterpret a MUST. The one diagnostic run
(`max_tokens=2048`) was performed to give the operator real evidence rather
than a bare assertion, not as a basis for unilaterally continuing.

Full record — both measurements, the served-model-id confirmation, gate 5's
result, and the RSN-06 cross-reference — is in
`docs/reports/report-v1.6.0.md` under "Live preflight and STOP (T15)".
`smoke-v160` was not run; T16 was not started. The operator's decision is
requested among three options recorded there: amend REQ-V160-PRE-04's
`max_tokens=16` to a reasoning-aware floor and re-run; load a
non-reasoning model and re-run PRE-03/PRE-04/the preflight against it; or
accept the STOP and end the v1.6.0 run at T15.
