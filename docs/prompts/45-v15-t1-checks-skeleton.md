# Prompt 45 — spec-v1.5 T1: checks.py skeleton, YAML reader, config, CC functions

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** assigned by spec-v1.5 §"Executor: claude-sonnet-5";
  the config schema and §5's regexes are fully specified, no design choice
  a different model would make differently
- **Harness:** Claude Code
- **Stage:** T1
- **Owner of:** `devtools/checks.py` (new), `config/quality_gates.yaml`
  (new), `tests/test_v15_standards.py` (new), `docs/reports/report-v1.5.md`
  (T1 sections), `docs/prompts/45-v15-t1-checks-skeleton.md` (new)
- **REQ ids:** REQ-V15-GATE-01, REQ-V15-GATE-02, REQ-V15-GATE-03,
  REQ-V15-CC-01..05, REQ-V15-TREE-01, REQ-V15-TREE-02

## Goal

Lay the skeleton `devtools/checks.py` is built on for the rest of this run:
a small explicit reader for the YAML subset `config/quality_gates.yaml`
uses, the full schema validator for that config (REQ-V15-GATE-02's two gate
kinds and their disjoint required/forbidden key sets), and the §5
Conventional Commits functions shared by the `commit-msg` hook (from T8) and
`checks.py replay` (from T8). Write the full `config/quality_gates.yaml` —
all 18 gates named by REQ-V15-GATE-11's matrix, `tools:` pinned at T1's
currently-installed versions per REQ-V15-DEP-04.

## Constraints

- `checks.py` uses only the standard library — no imported YAML library, no
  third-party dependency (REQ-V15-EC-01, REQ-V15-NG-09).
- No policy value (a tool name, a flag, an argv fragment, a target path, a
  severity, a threshold, an exit code, a profile list) is a Python literal
  in `checks.py`; only adapter/parser/handler mechanism names are permitted
  literals (REQ-V15-GATE-02). A gate's own name is not itself a forbidden
  literal (used only for the four gate-specific extra-key allowlists).
- `config/` carries no `__init__.py` (must not shadow `config.py`).
- `tools:` in T1's config holds only the four already-installed tools
  (ruff, gitleaks, semgrep, rtk) at their measured T0 versions; trivy and
  skylos stay out of `tools:` until T4/T5 install them, even though they
  must already appear in `gates:` and every profile.
- `run`, `doctor`, `replay`, `lint-docs` subcommands are argparse-wired but
  not yet implemented — later tasks own their bodies.
- The v1.4 suite (728 tests) is untouched; only new tests are added.

## Acceptance

- `T-V15-CC-01` through `T-V15-CC-07` and `T-V15-GATE-01` through
  `T-V15-GATE-03` (and `T-V15-TREE-01`) all green in
  `tests/test_v15_standards.py`.
- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0, test count 783 (728 + 55).
- `config/quality_gates.yaml` parses via `checks.py.load_gate_config()` and
  is bijective against its own `profiles:` block.

## Stop

If the YAML subset needed by the real config turns out to need a construct
the small reader can't express without becoming a general-purpose parser,
stop and simplify the config's shape instead of growing the reader past
"the subset this file uses." Do not add a third-party YAML dependency under
any circumstance (REQ-V15-NG-09 is absolute).
