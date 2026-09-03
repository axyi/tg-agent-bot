# Prompt 41 — v1.4 T10: report, post, errata, ledger

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); the
  final task assembles evidence already produced by T0–T9 into the
  report's remaining sections, plus three live/scripted acceptance
  checks (E5, E10, D1/D3-by-unchanged-code) — no new production code.
- **Harness:** Claude Code CLI
- **Stage:** report
- **Owner of:** `docs/reports/report-v1.4.md` (completed),
  `docs/reports/tg-post-v1.4.md` (new), `docs/llm-usage.md`,
  `docs/plan.md`, `docs/prompts/41-v14-t10-report.md` (new)
- **REQ ids:** REQ-V14-RPT-01…08, ACC-01, GATE-01, GATE-02

## Brief as sent (self-directed, per ORD-01's T10 row)

```
Complete report-v1.4.md: verdict against B_v1.4 (C_plain/C_conservative
not computed, T7 not-executed), GATE-02's full enumeration of released
REQs/test ids/artefacts/mutations, errata E1/E2 (RPT-04, read-only
against economics.md, no report-to-report edits), resolve the deferred
RPT-05/economics.md conflict (EC-01 wins, no lab-root write, row
content reproduced in-report instead), Appendix-B (E1-E10 + v1.2's
D1/D3 regression, ACC-01), known defects. Then tg-post-v1.4.md (RU,
<1500 chars), docs/llm-usage.md rows, docs/plan.md's status table +
v1.4 section. Final gates, sequentially, gate 6 last and alone.
```

## Advisor checkpoint

Consulted before starting (advisor was available again after two
earlier overloaded attempts, T6/T9). Eight points raised, all acted on:
(1) resolve RPT-05 now, don't write lab-root `economics.md`; (2)
`bench-v1.4.md` doesn't exist — say so explicitly, redirect the two
places that assume it; (3) verdict cause is "no honored reasoning
mechanism," not a cost-gate FAIL — state `B_plain`/threshold, mark
`C_plain`/`C_conservative`/gate outcomes/honored rate/DRIFT/
FINISH-LENGTH as not computed, not omitted; (4) GATE-02's enumeration as
a table; (5) state the 728/68 count arithmetic explicitly, and that the
`≥71` mutation minimum is conditional (doesn't bind on this branch); (6)
read RPT-04/Appendix-B verbatim before writing them, not from the
compaction summary; (7) post/ledger mechanics (`wc -m`, the harness's
tokens/cost note); (8) run gates strictly sequentially, gate 6 last and
alone, after learning the concurrent-mutation-gate lesson at T9.

## Appendix-B execution

- **E5 (timeout/budget mismatch), PASS** — scripted driver
  (`$CLAUDE_JOB_DIR/tmp/acc_e5_driver.py`, not committed — scratch, per
  BEN-02 item 5's precedent for throwaway driver scripts) calling
  `config.load_config` directly, unmocked: the spec's own bad example
  (120/2048) raised `ConfigError` naming both variables at exactly the
  computed floor (211.564s); the shipped defaults (240/2048) started
  cleanly.
- **E8, PASS (already executed at T1)** — per the spec's own "T-V14-SCN-01
  and Appendix B E8 execute only once" text, `s01-verify`'s 3/3 run is
  E8's execution; not re-driven.
- **E10 (no secret leaks), PASS** — a `grep`/Python scan across all 74
  files this run's `git diff --name-only 3bc8e8b..HEAD` names: authorization
  headers, URL user-info, credential key names in value positions, bare
  Telegram-bot-token shapes, generic API-key prefixes. Every match is a
  declared sentinel (`.env.example`'s own placeholder,
  `tests/test_v1_guardrails.py`'s `sentinel-telegram-token-...`); real
  credential values were neither read nor used as scanner inputs (`.env`
  not opened). Confirmed the "bench file's Telegram id" clause is
  inapplicable to this release's artefact shape — no Telegram-identity
  field exists anywhere in the bench JSON schema (walked every key of
  `baseline-v1.4.json`).
- **D1/D3 (v1.2 regression), PASS by unchanged-code evidence** —
  `git diff --stat 3bc8e8b..HEAD -- storage.py tools.py bot.py agent.py`
  is empty. The code these scenarios exercise (redaction at
  `storage.add_tool_call`, sandbox quota/clean-on-start in `tools.py`)
  received zero changes; combined with the full pytest suite (728/728)
  and mutation gate (68/68) both passing unchanged, the security posture
  is provably unweakened. Driven by the existing automated regression
  suite rather than a fresh live/scripted walk-through, since ACC-01's
  purpose (confirm nothing weakened) is fully served by "the code never
  moved."
- **E1–E4, E6, E7, E9 — not-executed**, one line each in the report's
  Appendix-B table: all depend on a shipped policy (E1–E4, E6) or a
  candidate run (E7, E9), neither of which exists on the RSN-06 STOP
  branch.

No fix cycle was consumed — every scenario passed on first drive or was
correctly classified not-executed by construction.

## RPT-05 / `economics.md` — resolved

Flagged since T0 (prompt 31/32), deferred through T1–T9 since nothing
blocked on it until T10 needed to act on RPT-05 for real. Re-verified
`EC-01`'s exact text (its one exception is BEN-02's `git worktree`,
which never touches `economics.md`) and `AGENTS.md`'s context boundary
independently. **Resolved in favor of `EC-01`: no write to lab-root
`economics.md`.** Full reasoning and the reproduced row content: report
section "Deferred conflict, resolved."

## `docs/llm-usage.md`

Rows 34 (this run's implementation session, `unknown` tokens/cost — no
session-transcript reconstruction tool was available to this harness,
matching rows 27/30–32's precedent rather than rows 25's) and 35 (the T9
`code-reviewer` subagent, 153,558 tokens — exact, from its
task-completion notification, matching rows 26/28's precedent), plus a Σ
row and an explanatory paragraph. Row 33 was already spec-v1.4's
authoring row (added before this `go` run started, per the established
per-version pattern) — so the implementation rows start at 34, not the
33 the spec's own RPT-05 text names (written before that authoring row
existed).

## `docs/reports/tg-post-v1.4.md`

Russian, `constraints → result → metrics → links`, 1449 characters
(`wc -m`, under the 1500 ceiling), names `claude-sonnet-5`, links
`https://github.com/axyi/tg-agent-bot`. Structure follows
`tg-post-v1.3.md`'s established compression style.

## `docs/plan.md`

Status-table row added for `spec-v1.4.md`/its implementation (RSN-06
STOP verdict, what shipped, commit/gate/test counts). The
"v1.4 (next) — candidates, none applied" section replaced: v1.4's own
delivered outcome (candidate table + verdict, mirroring the report),
then a renamed "v1.5 (next)" section listing exactly RPT-07's named
untried candidates (O6 routing, tokenizer-accurate budget, streaming,
semantic cache, levers 3/4/7 — `CONTEXT_WINDOW_MESSAGES`,
`EXEC_OUTPUT_DEFAULT_CHARS`, `FETCH_INLINE_DEFAULT_CHARS`). Lever 6
(starved summary, REL-02) deliberately not re-listed, matching RPT-07's
own enumeration, which omits it — noted as a released requirement
instead. Numbers throughout come from `baseline-v1.4.json`/
`report-v1.4.md`, never `bench-v1.4.md` (doesn't exist) or v1.3.

## Gates

Run strictly sequentially this time — T9's lesson (a concurrent
`mutation_check.py` instance produced a misleading "killed" reading via
an unrelated transient failure) is not repeated. Gate 6 last, alone,
after every other change in this final commit's content was already in
place. Results: see the report's Gates table, final row.
