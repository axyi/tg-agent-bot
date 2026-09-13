# Prompt 168 — v1.9.2 T2: pytest under xdist, fixture and grace-period costs

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a fully specified performance change against a
  measured, pre-derived contract (`docs/spec/task-briefs/v192-T2.md`
  sections 3-4) — the xdist worker-count plateau, the fixture fix and the
  grace-period literals were all fixed by the brief; no open-ended design
  decision.
- **Harness:** Claude Code
- **Stage:** v1.9.2 T2 (patch, no new spec file — precedent v1.5.1)
- **Owner of:** `pyproject.toml`, `uv.lock`, `config/quality_gates.yaml`,
  `tests/test_exec.py`, `tests/test_v160_dashboard.py`,
  `tests/test_v180_conversations.py`, `devtools/mutation_check.py` (the
  `-n 0` opt-out only), `docs/prompts/168-v192-pytest-time.md`,
  `docs/llm-usage.md` (row 78)
- **REQ ids:** none new — a performance change, no behaviour/interface
  change

## Goal

Cut the pytest gate's own wall clock by adopting `pytest-xdist` (measured
plateau at 8 workers in the brief, `-n auto` adopted since the machine has
16 cores) and by removing two cheap, real costs the brief measured:
`live_server` fixtures' default `poll_interval` (0.5s, ~10s of teardown
across the suite) and `test_exec`'s two grace-period tests exercising
production-sized `EXEC_KILL_GRACE_S`/`EXEC_DRAIN_GRACE_S` values (~10s).
Also close the brief's honest-answer requirement on duplicates (section 4):
scan cheaply, remove only with mutation-gate proof, and say plainly that
the suite's time is not in duplicate tests.

## Constraints

- Everything the brief states verbatim is the contract. The mutation
  runner (`devtools/mutation_check.py:default_runner`, prompt 167's own
  file) stays single-process: `-n 0` is added there in *this* commit
  because `pytest-xdist` becomes an installed dependency only now — adding
  it a commit earlier made `-n 0` an unrecognized pytest argument (verified
  empirically, exit 4).
- Exactly one of `test_t_ex_04`/`test_t_ex_05` keeps its grace constant at
  the real production value, per the brief; the other is monkeypatched
  down with its `elapsed <` bound scaled to match.
- Count-bearing / version-pin tests are repointed, never deleted
  (REQ-V190-EC-03) — not triggered this prompt, no count changed.
- `.env` never read; `data/`, `evals/rag/corpus` never opened. No version
  bump, no tag, no push, never `--no-verify`.

## Acceptance

`uv sync --locked` exit 0 (pytest-xdist 3.8.0 added); `uv run --locked
ruff check .` and `ruff format --check .` exit 0; `uv run --locked pytest`
exit 0 (1598 collected, unchanged from prompt 167 — no tests added or
removed this prompt); `uv run --locked python bot.py --selftest` exit 0;
`uv run --locked python devtools/checks.py lint-docs` exit 0; the
throw-away drift script reports 109/109 matched, 0 drifted;
`devtools/mutation_check.py --only v192-mutation-order-shrink-unchecked`
killed; `devtools/mutation_check.py --select v190-` killed 7/7; five
consecutive `pytest -q` (`-n auto`) runs plus one `--dist loadfile` run,
all exit 0, `git status --short` shows only this run's own in-progress
edits after each (no test-leaked files).

## Stop

If xdist fails or leaks on any of the six isolation runs, xdist is
reported, not adopted, and sections 3.1/3.2's fixture and grace-period
fixes still ship on their own. If a duplicates candidate's proof run
(`mutation_check.py --only <entry>`) shows a survivor after the proposed
removal, the removal is not made.
