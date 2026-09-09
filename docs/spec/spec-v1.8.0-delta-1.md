# spec-v1.8.0-delta-1 — the gate matrix

Overflow file of `docs/spec/spec-v1.8.0.md`, created because that file is at
`standards/workflow.md` §12's ~80 KB ceiling (REQ-V180-EC-01, "The spec's own
budget"). It is **normative**: REQ-V180-EC-12 makes this table the one
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1727-1741`) parses, in place of
`spec-v1.7.0.md`. Nothing else belongs in this file.

## The gate matrix (REQ-V180-EC-12)

REQ-V170-GATE-03's table, yes/— verbatim, plus the `mutation_check.py --select
v180-` row REQ-V180-EC-10 adds, minus the `note` column the parser never
reads. It is load-bearing markup: the parser finds the header by the literal
`| gate | pre-commit` and takes rows until the first line not starting with
`|`, and every label must match `_GATE_MATRIX_LABEL_TO_NAME`
(`tests/test_v15_standards.py:1685-1707`) byte-for-byte.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `mutation_check.py --select v15-` | — | yes | — |
| `mutation_check.py --select v160-` | — | yes | — |
| `mutation_check.py --select v170-` | — | yes | — |
| `mutation_check.py --select v180-` | — | yes | — |
| `mutation_check.py` (all) | — | — | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |
