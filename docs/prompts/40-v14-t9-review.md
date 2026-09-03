# Prompt 40 — v1.4 T9: code review (REQ-V14-REV-01)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); the
  executor's own work is dispatching the review, applying its findings,
  and recording dispositions — the review's judgment itself belongs to
  the clean-context `code-reviewer` subagent below, not a model swap for
  this session.
- **Reviewer:** `code-reviewer` subagent, clean context (no access to this
  session's writing context, per REV-01's own requirement)
- **Harness:** Claude Code CLI
- **Stage:** review
- **Owner of:** `devtools/bench.py` (finding 4 fix), `devtools/mutation_check.py`
  (finding 2 fix — third `v14-*` entry), `docs/reports/report-v1.4.md`,
  `docs/prompts/40-v14-t9-review.md` (new)
- **REQ ids:** REQ-V14-REV-01

## Brief as sent

Full diff `git diff 3bc8e8b..HEAD` (this run's 8 commits, 30c7a16…3fe860a)
against the spec and `AGENTS.md`, five focus areas: REL-01's
implementation correctness; mutation coverage for policy/verdict-affecting
lines (REV-01's own text: "no mutation entry is a finding, not an
observation"); the BEN-03 row-key rule and the baseline-v1.4 worktree
procedure; the S01 check repair's continued discriminating power; general
code quality. Full prompt: see the `Agent` tool call in this session's
transcript (not reproduced verbatim here — the review ran as a background
subagent, not a second executor invocation with its own numbered prompt
per se; this file records its brief and findings, satisfying REV-01's
"its own numbered file" requirement for the review as a whole).

## Findings and disposition

**Verdict returned: request changes** (procedural, not shipped-code
correctness — see below).

1. **🟡 Process — T9 shipped without REV-01 tracked as outstanding
   anywhere in `report-v1.4.md`.** True at the moment the review ran
   (prompt 39/commit `3fe860a` covered TST-05 only). **Fixed by this very
   prompt/commit** — the review's own findings are now the T9 REV-01
   deliverable, tracked in the report's T9 section below.

2. **🟡 Real gap — BEN-03's "missing required column" half had no
   mutation entry.** The first attempt at covering BEN-03 (prompt 39)
   correctly identified that a literal "⊆ restored to ==" mutation is
   vacuous in this tree (`REQUIRED_LLM_ROW_KEYS == LLM_ROW_KEYS`, no
   OBS-01 column added on the STOP branch) and pivoted to the *unknown*-
   column half — but then stopped, leaving the *missing*-column half
   uncovered. The reviewer found the correct, non-vacuous form for that
   half too: `missing = required - row_keys` → `missing = set()`,
   independently verified against `tests/test_bench.py::test_check_rejects_a_row_missing_a_required_column`
   (asserts `code == 1`, `"cost_basis" in reason` for a row missing that
   column) and `tests/test_v14_patch.py::test_t_v14_ben_01_row_key_rule_accepts_a_v13_shaped_row`'s
   `missing_row` case. **Fixed**: added as a third `v14-*` entry,
   `v14-ben-03-missing-column-accepted`, `devtools/mutation_check.py`.
   Total mutation count: 65 existing + 3 v1.4 = **68**.

3. **🟡 Waiver formalization — `tests/test_v1_guardrails.py`'s literal
   change (T6).** Already disclosed in commit `e5fc230`, prompt 37, and
   `report-v1.4.md`'s Reliability section — but never logged as a formal
   REV-01 waiver, only as a "deviation." **Disposition: waived, not
   re-opened.** REL-01's own arithmetic makes `LLM_MAX_TOKENS=8192`
   unreachable at any legal `LLM_TIMEOUT_S` (`21.1 + 0.093 × 8192 =
   782.956s > 600s` ceiling) — this is not an implementation choice to
   revisit, it is REL-01's own stated consequence
   ("ceiling 600, so `LLM_MAX_TOKENS ≤ 6224`"). Per REV-01's own tier
   classification, a test-only fix "invalidates nothing" (tier 3) — no
   replay is owed. `advisor()` was genuinely unavailable both times it
   was tried (temporarily overloaded); the resolution rests on REL-01's
   own textual evidence, independently re-confirmed by this review.
   **Formally waived here, REV-01 satisfied for this item.**

4. **🟡 Dead code — `env_flags()`'s frozenset-serialization branch
   (T2).** Confirmed: `Config` has no `llm_reasoning_on_purposes` field
   on the STOP branch (T5 never executed), so
   `isinstance(purposes, (frozenset, set))` was always `False` — the
   branch never executed and had no test or mutation coverage.
   `REQ-V14-BEN-05`'s own text confirms the field-absence→`None` fallback
   alone satisfies the requirement on this branch ("`env_flags()`...
   already resolves a `Config` field absent at the running commit to
   `None`... with no code change"); the serialization is POL-01's own
   future responsibility, not this run's. **Fixed**: branch removed,
   `env_flags()` reduced to the fallback dict comprehension alone, with a
   docstring note explaining why. `devtools/bench.py`.

5. **🟢 Note — S01's widened regex's negation blind spot.** Pre-existing
   weakness class (the original pattern had the identical blind spot via
   `команд`/`exec`), not introduced by this run's repair, and
   `bench_scenarios.py` is now BEN-10-frozen (any further change forces a
   T3 re-baseline per REV-01 tier 1). **Not fixed — recorded as a known
   limitation** in the report's known-defects list (T10).

6. **🟢 Note — `TOOL_ROW_KEYS`'s "why not a separate REQUIRED constant"
   justification lived only as a source comment**, not in the report, as
   BEN-03's text asks ("apply the same rule to `TOOL_ROW_KEYS`, or state
   in the report why not"). **Fixed** by copying the justification (tool
   schema unchanged by this spec, so REQUIRED == current for that row
   type) into the report's Harness readiness (T2) section below.

7–9. **🟢 Notes, no action needed** — BEN-02 item 5 dry-run cleanup
   verified clean (no leaked artefacts); old v1.3 `baseline.json`/
   `optimized.json` confirmed never read by the current gating pipeline;
   general code quality clean (no dead RSN scratch-patch remnants, no
   unused imports, `_check_timeout_budget` correctly placed before any
   disk-mutating `_prepare_*` call, REL-01's boundary arithmetic
   hand-verified against the spec's own worked examples).

## Re-verification after fixes 2 and 4

`ruff check .`: all checks passed. `pytest -q`: 728 passed (no test file
changed by either fix — `test_check_rejects_a_row_missing_a_required_column`
and `test_t_v14_ben_01_row_key_rule_accepts_a_v13_shaped_row` already
exercise the newly-covered mutation; no test referenced the removed
frozenset branch). `devtools/mutation_check.py`: **68 mutations, 68
killed**, 0 survived/errored/drifted (full log in this task's report
row).

## Gates

All six green — see the report's Gates table, T9 (review fixes) row.
