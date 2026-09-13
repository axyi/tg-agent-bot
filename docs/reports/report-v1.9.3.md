# tg-agent-bot v1.9.3 -- patch report

Operator's decision (`docs/spec/task-briefs/v193-T1.md`, verbatim,
2026-09-13): "1. Делай [pre-push → mutation-all]. 3. Закрывай хвосты все
сейчас, бамп версии 1.9.3!" Three tails `docs/reports/report-v1.9.2.md`
disclosed, closed on this order: **T1** -- pre-push runs `mutation-all`
instead of five subset gates, and the gate-timeout/SIGKILL-leaves-a-mutated-
tree hazard (report-v1.9.2.md disclosure b) is fixed; **T2** -- the rerank
third-attempt tail (three lines at the top of every gate-7 log since
v1.9.1 T3) is diagnosed and fixed; **T3** -- the ruff rule-family proposal
table is decided and applied. **T4** closes the patch (version bump,
paperwork, tag). Baseline: `5e62a4a` (tag `v1.9.2`, pushed, clean).

## T1 -- pre-push

Contract: `docs/spec/task-briefs/v193-T1.md` commit A (prompt 173).

`config/quality_gates.yaml`'s `pre-push` profile now runs `mutation-all`
instead of `mutation-v15, mutation-v160, mutation-v170, mutation-v180,
mutation-v190` -- one authoritative all-entries mutation run per push
instead of five partial subset runs. The five gate definitions are not
deleted: they stay useful `--select <prefix>` measurement units (this
release's own T2 and T3 tasks re-measure their touched subsets with them).
Removing them from every *hook* profile (pre-commit/pre-push/full) would
leave them unreferenced by any `profiles:` entry, which
`devtools/checks.py:538-550`'s `_validate_profiles` rejects outright
("gate(s) named by no profile") -- discovered by running `checks.py
doctor` against the first draft of this edit. Fixed with a new,
intentionally inert `mutation-subsets` profile naming the five gates:
`checks.py run --profile` only accepts `pre-commit`/`pre-push`/`full`
(`devtools/checks.py:1657`'s argparse `choices`), so this profile is
structurally unreachable from any hook or CLI invocation -- it exists
purely to satisfy the loader's "every gate belongs to some profile"
invariant, never to run anything.

`docs/spec/spec-v1.9.0-delta-1.md`'s gate matrix table (read directly by
`tests/test_v15_standards.py:1735`,
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`) is updated
to match: the five `mutation_check.py --select vNNN-` rows' `pre-push`
cell moves `yes` -> `—`; the `mutation_check.py` (all) row's `pre-push`
cell moves `—` -> `yes`. Every row stays present (the test also asserts
every label in `_GATE_MATRIX_LABEL_TO_NAME` is a row in the table).

One test pinned pre-push membership literally rather than through the
spec-table parser:
`tests/test_mutation_check.py::test_t_v160_gate_02_mutation_v160_gate_mirrors_mutation_v15`
asserted `"mutation-v160" in config["profiles"]["pre-push"]`. Repointed
(not deleted) to `"mutation-v160" in config["profiles"]["mutation-subsets"]`
plus an explicit `not in` check against `pre-push`, with a comment naming
why.

Grepped `AGENTS.md`/`README.md` for `pre-push`, `mutation-v`, `five`,
`subsets` per the brief's own instruction: the only hits (`AGENTS.md:137,
209, 222`) are about branch-name hook enforcement and the
`checks.py run --profile` CLI -- no sentence in either file claims
pre-push runs the five subsets, so nothing there needed changing. The
claim lived only in the YAML and the spec table, both fixed above.

Proof (per the brief's own note -- the real ~11-minute `mutation-all` run
happens when the operator pushes, not inside this prompt):
`checks.py doctor` exit 0; `pytest tests/test_v15_standards.py -k
"profile_matrix or gate_05"` exit 0; full `pytest` exit 0, 1601 collected
(unchanged); `ruff check .` / `ruff format --check .` exit 0/0;
`checks.py lint-docs` exit 0; `bot.py --selftest` exit 0.

## T1 -- gate timeout safety

<!-- filled by commit B, prompt 174 -->

## Delegation record

- T1 -- delegated, brief `docs/spec/task-briefs/v193-T1.md`.

## Ledger row (paste into `economics.md`)

<!-- filled at T4 (version bump), the same convention v1.9.2 T3 used -->

## Verdict

<!-- filled at T4 -->
