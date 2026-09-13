# Prompt 176 — v1.9.3 T1+T2 review: SIGTERM reaches the process group; child termination covered; pre-push dirty-tree refusal surfaced

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** closing a clean-context review's findings against three
  already-landed commits (`bff8dc4`, `07bb158`, `aa8d576`) — each finding
  names its own fix precisely; the two investigations (findings 6/7) are
  measure-then-report, not open-ended design.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T1+T2 review (patch, no new spec file), one commit
- **Owner of:** `devtools/checks.py`, `devtools/mutation_check.py`,
  `tests/test_v15_standards.py`, `tests/test_mutation_check.py`,
  `config/quality_gates.yaml`, `AGENTS.md`, `README.md`,
  `docs/prompts/174-v193-t1-mutation-dirty-tree-sigterm.md`,
  `docs/reports/report-v1.9.3.md`, `docs/llm-usage.md`
- **REQ ids:** REQ-V12-MUT-01..04, REQ-V15-GATE-06/07/08

## Goal

Close every finding in `docs/spec/task-briefs/v193-T12-review.md` (read in
full) against `bff8dc4`+`07bb158`+`aa8d576` — no 🔴, three 🟠, eight 🟡 — in
this one commit, without rewriting any of the three reviewed commits.

Three 🟠: (1) rewrite the SIGTERM test with a grandchild process so it
actually proves process-group signalling, not direct-child-only, with a
new mutation entry killed by it; (2) add unit-test coverage for
`_CURRENT_CHILD`/`_terminate_current_child`/the signal handler's call
order, with a new mutation entry killed by it; (3) a failed `exit_status`
gate's message now includes the last five non-empty stderr lines of the
child (bounded, plain — no `config.redact`, which would pull
`python-dotenv` into this standard-library-only module for a secrets
registry it never populates), plus one sentence each in `AGENTS.md` and
`README.md` disclosing that pre-push now refuses a tree with uncommitted
edits to a mutation path.

Eight 🟡: the refusal message's own git guidance (`git diff HEAD --
<path>` / `git restore --staged --worktree <path>`, not `git checkout --
<path>`, which loops on a staged edit); the 680→814s wall-time comment's
wrong attribution (the dirty-tree check is one `git show` per distinct
path, sub-second total, not "two calls per mutation"); the `rag-eval`
gate's timeout comment re-derived from this release's own slowest
measured wall (268.8s, still under 580s with margin); an in-process
instrumented gate-7 run (an outside wrapper — `agent.run_agent_outcome`,
`rag.Searcher.search`, `devtools.rag_eval.index_corpus` each wrapped with
wall-clock timestamps, `rag.py`/`devtools/rag_eval.py` untouched) locating
the slow phase (the smoke turn's own chat completions, not rerank, not
ingest, not the ten deterministic items) and capturing turn 2's full
outcome (no tool call, a direct arithmetic answer from turn-1 context —
model behaviour, not a defect: no code path from T2's fix touches the
agent's tool-decision logic); stale `checks.py` line citations and the
two amended-away hashes (`ceb4a11`/`0fde4c3`) repointed to `07bb158`/
`aa8d576`; prompt 174's own title corrected (the brief's original title
stays as history); the dirty-tree killer test now fakes `_shrink_counts`
too, so a mutated run never shells out to real `pytest --collect-only`;
the report gains a T2 acceptance line, noting the count-bearing lines in
`AGENTS.md`/`tests/test_v190_agents.py` move at T4 by precedent.

## Constraints

Do not rewrite `bff8dc4`, `07bb158`, or `aa8d576`. No push. Nothing
concurrent with any mutation run or gate-7 run. `.env` never read;
`data/`, `evals/rag/corpus` never opened as content.

## Acceptance

```
uv run --locked ruff check .                                          # 0
uv run --locked ruff format --check .                                 # 0
uv run --locked pytest                                                # 0
uv run --locked python devtools/checks.py lint-docs                   # 0
uv run --locked python devtools/checks.py doctor                      # 0
uv run --locked python devtools/checks.py run --profile pre-commit    # 0
<drift script>                                                        # 114/114
uv run --locked python devtools/mutation_check.py --only v193-gate-timeout-kills-direct-child-only   # killed
uv run --locked python devtools/mutation_check.py --only v193-signal-handler-leaves-child-running    # killed
uv run --locked pytest tests/test_v15_standards.py -k sigterm --count=5  # (or 5 sequential invocations) 5/5
uv run --locked python devtools/rag_eval.py                            # 0 (the single instrumented run, item 6)
```

## Stop

If finding 7's investigation shows turn 2 skipped its tool call because of
something the T2 fix actually changed (double-routing, a changed
`conv_id`, a swallowed exception in the tool path) rather than ordinary
model behaviour — stop and report with the captured evidence instead of
writing it up as advisory.
