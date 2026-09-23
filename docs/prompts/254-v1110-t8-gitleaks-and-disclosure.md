# Prompt 254 — v1.11.0 T8: gitleaks-tree properly run, a process deviation disclosed

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a docs-only disclosure plus one corrected read-only
  scan — orchestrator, main context, no delegation.
- **Harness:** Claude Code (background session, orchestrator)
- **Stage:** T8 (final, follow-up)
- **Owner of:** `docs/reports/report-v1.11.0.md` (`## T7`'s Phase E
  section, the disclosure)
- **REQ ids:** REQ-V1110-EC-07, REQ-V1110-REV-02

## Goal

Run `gitleaks-tree` the way `config/quality_gates.yaml` actually defines
it — against a tracked-only export (`git archive HEAD | tar -x`), not
the raw working directory (which holds `.env` and other git-ignored
content) — after an earlier attempt at this same check went wrong: the
orchestrator ran `uv run --locked python devtools/checks.py run
--profile full` instead, which bundles `rag-eval`/`agent-eval`
(gates 7/8) with `gitleaks-tree`. That command ran synchronously without
an extended timeout, was killed by the harness's 120s default partway
through `mutation-all`, and left evidence (`.pyc` cache regeneration for
`agent_eval.py`/`llm/*`/`rag.py`) that cannot rule out gates 7/8 having
started and possibly completed a second time within that window, before
the kill landed later in `mutation-all`.

## Constraints

No gate bundling this task — `gitleaks-tree` run as a standalone
`gitleaks dir` invocation against a `git archive` export, never through
a multi-gate profile that could touch gates 6/7/8 again. The disclosure
records what did and did not happen as precisely as the available
evidence allows, without overstating certainty either way.

## Acceptance

`gitleaks-tree` (run correctly, against the tracked-only export):
**no leaks found**. The disclosure is recorded in `docs/reports/report-v1.11.0.md`'s
`## T7` Phase E section (not a new stop, not a correction to the
recorded gate-8 verdict — T7's original execution remains the one this
release's compliance record relies on, per REQ-V1110-REV-02's own reuse
path). `git status --porcelain` clean before and after every command
this task ran.

## Stop

Not applicable — this is itself the disclosure and the corrected check;
no gate outcome this release depends on changed.
