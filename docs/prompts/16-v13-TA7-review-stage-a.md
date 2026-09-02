# Prompt 16 — v1.3 TA7: clean-context review of stage A

- **Sent to:** `code-reviewer` subagent (own clean context, AGENTS.md § Review)
- **Scope:** the whole stage-A diff (C1 tree, before commit), i.e. carry-over,
  observability layer, pricing, benchmark harness, dashboard, A-mutations
- **REQ ids:** section 13.5 of spec-v1.3 ("after stage A, before B1")

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot. Review the uncommitted
stage-A work: `git status` + `git diff` against HEAD (plus untracked new files
metrics.py, llm/pricing.py, devtools/bench.py, devtools/bench_scenarios.py,
devtools/dashboard.py, tests/test_v13_carryover.py, tests/test_observability.py,
tests/test_pricing.py, tests/test_bench.py, tests/test_dashboard.py).
Contract: docs/spec/spec-v1.3.md sections 5, 6, 7, 8, 11.1-11.4, 12 (rows
tagged A). A harness defect found after the baseline benchmark costs a full
re-run, so weight correctness of devtools/bench.py highest — especially the
7.4 arithmetic contract, the exit codes, the abort paths and the recursive
redaction.
Report findings with severity and file:line. Check in particular: secrets or
Telegram ids reachable in any output; SQL migration idempotency; thread/
connection ownership in run_bench; NULL handling in every sum; off-by-one in
turn addressing; anything that silently returns 0 where the spec says None.
NEVER open .env. Do not edit any file — review only.
Return findings as a list; no file dumps.
```
