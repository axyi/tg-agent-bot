# Prompt 216 — v1.10.2 T3: repoints and paperwork (minus the numbers, which land at T6)

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (spec-v1.10.2 T3: offline
  documentation/config repoints); subagent, briefed by
  `docs/spec/task-briefs/v1102-T3.md`.
- **Harness:** Claude Code (subagent)
- **Stage:** T3
- **Owner of:** `config/quality_gates.yaml`, `.env.example`, `README.md`,
  `AGENTS.md`, `docs/reports/report-v1.10.0.md`, `docs/llm-usage.md`
  (row 108), `tests/test_v15_standards.py`, `tests/test_v1101_gates.py`,
  `tests/test_v170_bench.py`, `tests/test_v190_agents.py`,
  `tests/test_v1102_gates.py` (new), `tests/test_v1102_docs.py` (new)
- **REQ ids:** REQ-V1102-GATE-03, REQ-V1102-RPT-01 (first sentence),
  REQ-V1102-RPT-02 (T3 half), REQ-V1102-RPT-03 (T3 half), REQ-V1102-RPT-04,
  REQ-V1101-CFG-01

## Goal

Land v1.10.1's own T7/T8 paperwork together with v1.10.2's, since v1.10.1
stopped at T6 and that paperwork never ran: `lint-docs.report_path`
repointed to `docs/reports/report-v1.10.2.md`; the gate-matrix test
repointed at `docs/spec/spec-v1.10.2.md`'s own §9 table with the
`mutation_check.py --select v1102-` label added; `.env.example`'s routing
defaults flipped so `LLM_PROVIDER` defaults to `openrouter` (LM Studio
becomes the empty, opt-in alternative) and the embeddings route defaults to
OpenRouter (`openai/text-embedding-3-small`, dim 1536, per
spec-v1.10.1.md:244's lab-verified pair); README's `## Configure` and
`## Switch provider` sections reworded to match, plus the two stopped-run
release-table rows (`v1.10.0`, `v1.10.1`, both "not tagged"); AGENTS.md's
gate count corrected to "All eight", the gate-5 sentence updated to reflect
LM Studio's SKIP-when-unconfigured behaviour, the brief-path token moved to
`v1102-T<N>`, and a benchmark-waiver paragraph added (v1.10.1's waiver
carried forward, v1.10.2 renewing it); `docs/reports/report-v1.10.0.md`'s
T6 line and `docs/llm-usage.md` row 108 both corrected to record that T6
was not actually delegated (a `standards/workflow.md` §5.1 deviation found
and disclosed now, not silently).

## Constraints

Offline throughout, no live LLM call. `docs/spec/spec-v1.10.1.md`,
`docs/reports/report-v1.10.1.md`, `docs/handoff-v1.10.1.md` untouched
(frozen history). No real secret value written anywhere, including
`.env.example` (placeholders/examples only). README's "pending (T9)" table
and the release table's `v1.9.5`/`v1.10.2` rows untouched (T6's job).
AGENTS.md's two count lines (mutation-entry count, pytest count) untouched
(T6's job, since T5 moves both numbers). Test-first per EC-02: both new
test files (`tests/test_v1102_gates.py`, `tests/test_v1102_docs.py`) were
written and run red against the unedited tree before any production edit
landed.

## Acceptance

Every id in the brief green (`T-V1102-GATE-03`, `T-V1102-RPT-01`,
`T-V1102-CFG-01`, `T-V1102-RPT-02`'s T3 function, `T-V1102-RPT-03`'s T3
function, `T-V1102-RPT-04`); `test_v15_gate_04_profile_matrix_agrees_with_
the_spec_table` green against the repointed spec; `checks.py doctor` and
`checks.py lint-docs` both green; `ruff check .` green; full offline suite
green (2154 passed / 1 skipped, up from 2153/1 at `b4d7e0c`), no test
deleted.

## Stop

One EC-02-shaped gap beyond the brief's own named one
(`tests/test_v1101_gates.py:254-256`) was found and disclosed, not
silently fixed: `tests/test_v190_agents.py:69-81`
(`test_t_v190_ec_01_agents_md_seven_gate_block_present`) hardcoded "All
seven MUST exit 0" and a seven-command list missing `agent_eval.py`, which
this task's required AGENTS.md edit (`v1.10.2` T3 §6, "All eight MUST exit
0") made stale. Renamed to `test_t_v1102_ec_01_agents_md_eight_gate_block_
present`, literal bumped to "All eight", `agent_eval.py` added to the
command list, with an inline comment naming this a v1.10.2 T3 amendment --
the same precedent `tests/test_v1101_gates.py:254-256`'s own rename/repoint
(this brief's named EC-02 item) and v1.10.1 T3's `526e19d` marker-pin bumps
already established for this repository. Flagged to the orchestrator as a
mechanical, precedented, out-of-explicit-brief-scope edit for audit,
per the brief's own instruction to report rather than silently fix.

README's "LM Studio is the default" grep sweep additionally reworded
`README.md`'s RAG `### Embeddings` subsection (the `.env.example` default
changing away from LM Studio made its "served locally by LM Studio ...
no API cost" framing read as the general default rather than this specific
deployment's own confirmed pair) to name both the new OpenRouter default
and this deployment's actual local pair, while keeping
`tests/test_v190_agents.py:177`'s pinned `text-embedding-nomic-embed-
text-v1.5` literal intact and green.
