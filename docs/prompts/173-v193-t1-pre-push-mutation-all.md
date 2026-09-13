# Prompt 173 — v1.9.3 T1 commit A: pre-push profile runs `mutation-all`

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5
- **Model reason:** a bounded, well-specified config/paperwork change against
  an existing task brief (`docs/spec/task-briefs/v193-T1.md`) — a profile
  membership swap and its spec/test/comment fallout, no open-ended design
  decision.
- **Harness:** Claude Code
- **Stage:** v1.9.3 T1 commit A (patch, no new spec file — precedent v1.5.1,
  v1.9.1 T2, v1.9.2 T3)
- **Owner of:** `config/quality_gates.yaml`,
  `docs/spec/spec-v1.9.0-delta-1.md`, `tests/test_mutation_check.py`,
  `docs/spec/task-briefs/v193-T1.md` (and `-T2.md`/`-T3.md`/`-T4.md`,
  committed alongside), `docs/reports/report-v1.9.3.md`,
  `docs/llm-usage.md`
- **REQ ids:** REQ-V190-EC-12, REQ-V15-GATE-11

## Goal

Operator's decision (`docs/spec/task-briefs/v193-T1.md`, verbatim): "1.
Делай [pre-push → mutation-all]." `config/quality_gates.yaml`'s `pre-push`
profile runs `mutation-all` instead of the five `mutation-v15…mutation-v190`
subset gates; the five gate definitions stay (they remain useful
`--select` measurement units for this release's own T2/T3 tasks), but no
*hook* profile (pre-commit/pre-push/full) references them any more. The
config loader's own orphan-gate invariant
(`devtools/checks.py:538-550`) requires every gate be named by some
`profiles:` entry, so a new, inert `mutation-subsets` profile — outside
`checks.py run --profile`'s three-way `choices` — names them instead,
never wired to any hook. `docs/spec/spec-v1.9.0-delta-1.md`'s gate matrix
table is updated to match (the parser
`tests/test_v15_standards.py:1735` reads it directly), and
`tests/test_mutation_check.py::test_t_v160_gate_02_mutation_v160_gate_mirrors_mutation_v15`
is repointed, not deleted, to the new home. Grepped `AGENTS.md`/`README.md`
for `pre-push`/`mutation-v`/`five`/`subsets`: no prose sentence there
claims pre-push runs the five subsets (the three hits are about
branch-name enforcement, hook wiring and the profile CLI) — nothing to
change in either file.

## Constraints

- The five `mutation-v*` gate definitions are not deleted.
- `--list`/`--only`/`--select` fail-loud semantics unchanged; the shrink
  guard unchanged.
- `.env` never read; `data/`, `evals/rag/corpus` never opened. No push, no
  `--no-verify`.
- The four untracked `docs/spec/task-briefs/v193-T*.md` briefs are
  committed in this commit.

## Acceptance

- `uv run --locked python devtools/checks.py doctor` — exit 0.
- `uv run --locked pytest tests/test_v15_standards.py -k "profile_matrix or gate_05"` — exit 0.
- `uv run --locked pytest` — exit 0, 1601 collected (unchanged).
- `uv run --locked ruff check .` / `ruff format --check .` — exit 0, 0.
- `uv run --locked python devtools/checks.py lint-docs` — exit 0.
- `uv run --locked python bot.py --selftest` — exit 0.

The real pre-push run (the eleven-minute `mutation-all` wall) happens when
the operator pushes; it is not run inside this prompt.

## Stop

If the config loader's orphan-gate check cannot be satisfied without
either deleting a gate definition or wiring a subset gate into a real hook
profile — stop and report rather than picking silently.
