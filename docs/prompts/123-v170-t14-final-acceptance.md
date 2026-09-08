# Prompt 123 — spec-v1.7.0: T14 final acceptance evidence

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T14 (final acceptance)
- **Owner of:** `docs/reports/report-v1.7.0.md`,
  `docs/prompts/123-v170-t14-final-acceptance.md` (new)
- **REQ ids:** REQ-V170-ACC-01, REQ-V170-ACC-02, REQ-V170-ACC-03

## Goal

Re-run the six verbatim gates against `<implementation-tip>`
(`48e9db2`, T13's own commit), run `checks.py run --profile full --since
<base>` and `checks.py replay --range <base>..<implementation-tip>`,
execute Appendix B against the repository and record pass/fail/N-A per
scenario with how each was driven, confirm the REQ-V170-ACC-02 regression
check, and land the single evidence-only commit. Per REQ-V170-BEN-07's
FAIL-cost-gate verdict already established at T11, **no `v1.7.0` tag is
created** — the evidence-only commit records `<implementation-tip>`, the
replay output and the intended tag name, and states explicitly that the
tag was withheld and why.

## Constraints

- The evidence-only commit touches `docs/reports/*` and nothing else
  (REQ-V170-ACC-03) — this prompt file therefore lands in its own,
  separate, preceding commit, not inside the evidence commit.
- No source, test or config file may change (the freeze is still in
  effect; T14 is read-only against the shipped tree).
- `git tag -a v1.7.0` is forbidden on this branch. Nothing is pushed.

## Acceptance

- Six verbatim gates of `AGENTS.md` all exit 0 against `48e9db2`.
- `uv run --locked python devtools/checks.py run --profile full --since
  706c690d35f34d96d1ee0fbcb8e9be08bafa30e7` exits 0.
- `uv run --locked python devtools/checks.py replay --range
  706c690d35f34d96d1ee0fbcb8e9be08bafa30e7..48e9db2` exits 0.
- `docs/reports/report-v1.7.0.md` carries the Appendix B table (13 rows),
  the ACC-02 regression statement, and the explicit no-tag record.
- `git tag -l` unchanged (`v1.3`, `v1.3-baseline`, `v1.6.0` only).

## Stop

None. A transient re-occurrence of the GPU box's floating IP moving (4th
this run) was handled the same way as T1/T5/T10: re-probed, re-pinned via
the one permitted `sed -i` idiom, gate 5 reconfirmed — not a stop
condition.
