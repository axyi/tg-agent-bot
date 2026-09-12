# Prompt 158 — v190 T12: the version bump

- **Date:** 2026-09-12
- **Executor model:** claude-sonnet-5
- **Model reason:** small, mechanical version-literal change plus
  reporting artefacts; two structurally-broken pre-existing tests
  discovered along the way each needed a one-line judgement call, not a
  large-context task — orchestrator context, no delegation needed.
- **Harness:** Claude Code
- **Stage:** T12
- **Owner of:** `pyproject.toml`, `uv.lock`, `tests/test_v190_version.py`,
  `tests/test_v190_agents.py`, `tests/test_v180_version.py`, `README.md`,
  `AGENTS.md`, `docs/llm-usage.md`, `docs/reports/report-v1.9.0.md`
  (Ledger row section only), `docs/reports/tg-post-v1.9.0.md`
- **REQ ids:** REQ-V190-VER-01, REQ-V190-RPT-02, REQ-V190-RPT-03,
  REQ-V190-RPT-04

## Goal

Land the release stamp: `pyproject.toml`'s `project.version` moves
`1.8.0` → `1.9.0`, `uv.lock` regenerated to match, and
`tests/test_v190_version.py` proves it (`T-V190-VER-01`, red before the
bump — confirmed empirically by writing the test against the target
`"1.9.0"` string while the tree still read `1.8.0`, `AssertionError:
assert '1.8.0' == '1.9.0'` — then green after). `README.md`'s
`## Versioning` table gets the `v1.9.0` row; `AGENTS.md`'s gate-3/gate-6
lines get the real, measured test and mutation counts. Close out this
run's reporting: `docs/llm-usage.md` rows for prompts 142–158,
`docs/reports/report-v1.9.0.md`'s Ledger row (real, complete, no
self-referential SHA), and `docs/reports/tg-post-v1.9.0.md`.

## Constraints

`docs/reports/report-v1.9.0.md`: Ledger row section only — every other
section is the orchestrator's/T13's own running record. This commit's own
SHA must not appear anywhere inside that report (REQ-V190-REV-02's
"no self-referential SHA" rule — it is not knowable until after this
commit exists anyway). No `devtools/mutation_check.py` or any live gate
this task — offline, documentation-plus-one-version-string only.

**Deviation 1 — README's Versioning table.** The brief assumed existing
`v1.7.0`/`v1.8.0` rows to match format against; neither exists —
`git log -p` confirms v1.7.0's own T12 (`17578b1`) and v1.8.0's own T9
(`30207af`) never touched this table, so it has stopped at `v1.6.0` since
that release. Added only the `v1.9.0` row in the table's existing format,
did not backfill the gap (out of this task's scope), and dropped
`v1.6.0`'s stale "this release" label since my own addition makes it
false.

**Deviation 2 — the test-count literal, 1560 not 1559.** The brief's
resolved fact (1559) is the pre-T12 floor. `T-V190-VER-01` itself adds
one collected test, and `AGENTS.md`'s line explicitly tags itself "as of
spec-v1.9.0 T12" — it must describe the tree *after* this task's own
edit. Verified via `git stash` (tracked files only, so the new untracked
test file stayed in place) that the pre-T12 tracked-tree count was
exactly 1559; the post-T12 tree collects 1560 (`pytest --collect-only -q`,
summed since `rtk`'s dedicated collect-only filter emits per-file counts
rather than a single total line). Operator-ratified after being put to
them directly.

**Deviation 3 (operator-ratified EC-03-class extension) —
`tests/test_v190_agents.py:126-132`.** This task's required edit to
`AGENTS.md`'s two count-bearing lines broke
`test_t_v190_ec_01_agents_md_count_bearing_lines_untouched`, a T10-era
test asserting the two lines *still* carried their pre-T10 literals
(`"1220"`, `"98 entries"`) — correct proof T10 left them alone. The
test's own comment already named T12 as the point both literals change:
"AGENTS.md:146's test count and :155's mutation count are written once,
in T12 -- T10 must not touch them." Confirmed via direct reproduction
(`pytest -k count_bearing` → `AssertionError: assert '1220' in ...`) that
this is a designed, anticipated consequence, not a defect. Not in
REQ-V190-EC-03's original amendment list; stopped and reported before
touching it, per instruction. Ratified fix applied exactly as proposed:
renamed to `test_t_v190_rpt_05_agents_md_count_lines_landed_at_t12`,
comment rewritten to describe T12 having landed the real figures, both
asserted literals changed to `"1560"` and `"105 entries"` (the verified
post-T12 numbers, not the brief's stale pre-edit 1559).

**Deviation 4 (operator-ratified, first-of-its-kind decision) —
`tests/test_v180_version.py`.** The same required `pyproject.toml` bump
broke `test_t_v180_ver_01_pyproject_version_is_1_8_0`, v1.8.0's own
version-pin test, whose assertion (`project.version == "1.8.0"`) is now
permanently false by design — `pyproject.toml` will never read `1.8.0`
again. My first proposal (delete the file — its job was already proven
and tagged, a stale pin test asserting a permanently-false fact serves no
future purpose) was **explicitly rejected**: REQ-V190-EC-03 is a hard
"no test may be deleted" rule, not something either party may waive.
Resolution, ratified: repoint rather than delete or leave red. Reading
`tests/test_v170_bench.py`'s own `test_t_v170_acc_03_version_half`
showed this exact problem was already solved once, at v1.8.0's own T9 —
that test reads `pyproject.toml` from the frozen `v1.7.0:` git-tag blob
(`git show v1.7.0:pyproject.toml`) instead of the live tree, "immune to
every future release's own version bump" per its own docstring. Applied
the identical pattern here: `test_t_v180_ver_01_pyproject_version_is_1_8_0`
renamed to `test_t_v180_ver_01_v180_was_tagged`, now asserts
`git show v1.8.0:pyproject.toml`'s blob reads `1.8.0` (subprocess pattern
matching `devtools/checks.py:677`'s `_run_git`/`test_v170_bench.py`'s
`_acc03_run_git_readonly`), with a docstring naming why deletion was
rejected and why git-tag-repointing was chosen instead. **This
establishes a repo convention, not a one-off**: every future
`test_vXXX_version.py` gets this identical treatment (rename +
`git show v<its-version>:pyproject.toml`) at whatever release retires
its version — `T-V190-VER-01`'s own `tests/test_v190_version.py` will
need it too, at v1.9.0's own retirement; expected, not a bug to fix now.

**Deviation 5 — `uv.lock` included.** Not in the brief's file list, but
`uv sync --locked` refuses a stale lockfile against the bumped
`project.version`; `uv.lock` is the identical addition v1.8.0's own T9
commit (`30207af`) made for the same reason.

## Acceptance

`T-V190-VER-01` red before (empirically), green after. Full `pytest`
(1559 passed, 1 skipped = 1560 collected), `ruff check .`,
`bot.py --selftest`, `checks.py lint-docs` all exit 0. The report's
Ledger row is structurally complete, no `TBD`, no self-referential SHA.

## Stop

Stopped twice mid-task on pre-existing tests structurally broken by this
task's required edits, outside REQ-V190-EC-03's original amendment list
(`tests/test_v190_agents.py`'s count-bearing-lines check, then
`tests/test_v180_version.py`'s stale version pin) — reported each with
file:line and the exact proposed mechanical fix, applied only after
explicit operator ratification, per standing instruction not to
self-resolve this class of finding.
