# Prompt 31 — `go docs/spec/spec-v1.4.md`

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** spec-v1.4's own preamble pins claude-sonnet-5 for this run ("Executor model claude-sonnet-5: a bounded live experiment with a decision tree... A larger model is not needed and must not be substituted for reading carefully"); no override.
- **Harness:** Claude Code CLI, background job, working directory `projects/tg-agent-bot`
- **Stage:** generation
- **Owner of:** `docs/prompts/31-go-spec-v1.4.md` (this file) — dispatches to the per-task prompts of §14; no production file
- **REQ ids:** REQ-V14-EC-01…09 (execution contract, applies to the whole run)

## Prompt as sent

```
go docs/spec/spec-v1.4.md
```

## Interpretation (`AGENTS.md` § go protocol)

Execute `docs/spec/spec-v1.4.md` end-to-end, following its own § 1 "Execution
contract":

- one prompt → one commit, on `main`, per task of §14's order (T0…T10),
  numbered from `32`; this file (`31`) is the go prompt itself and, having no
  files of its own to change, is committed together with T0's prompt/commit
  (mirrors `docs/prompts/09-go-spec-v1.3.md` + `10-v13-TA1-carryover.md`,
  both landing in `69ebc75`);
- the six gate commands of §11, verbatim, in order; gates 1–5 at every
  commit, gate 6 additionally at every commit touching production code,
  configuration behaviour, benchmark verdict logic, tests or mutations, and
  on the final tree (GATE-01);
- a repair budget of 5 total repair-and-rerun cycles (§1, REQ-V14-EC-01);
  live benchmark steps are blocking but not gates and have their own retry
  rules (BEN-08);
- two possible early ends: SCN-03's **H2** (blocker at T1, before T2) and
  RSN-06's **STOP** (at T4, when no reasoning-suppression mechanism both
  binds and survives POL-05) — either narrows or ends the remaining tasks per
  GATE-02;
- RLM discipline unchanged (EC-08): bulk reads of `bench.py` go through
  targeted ranges or a subagent brief, never a full dump;
- every prompt sent to an LLM logged under `docs/prompts/`, tokens/cost in
  `docs/llm-usage.md`, run results in `docs/reports/`.

## Executor decisions recorded at the start of the run

1. **HEAD precondition, declared deviation.** PRE-01 item 1 asks for HEAD at
   `3a0aa3d`; the actual HEAD is `3bc8e8b` (`docs: spec-v1.4 — Codex
   cross-review rounds 1–4 fixes and debate log`). `git diff --stat
   3a0aa3d..HEAD` shows exactly two files changed:
   `docs/spec/spec-v1.4.md` (created, 1516 lines) and `docs/llm-usage.md`
   (+1 line) — the spec-authoring commits themselves, zero production-code
   drift. Treated as satisfied in substance (code state == `3a0aa3d`) and
   recorded here rather than blocking, mirroring how spec-v1.3 was invoked
   after its own spec-authoring commits sat on top of the code state it
   described.
2. **LM Studio version is operator-supplied, not self-read.** This session
   has no SSH access and no version endpoint on the remote LM Studio host
   (`172.16.50.233`, `.env`'s `LMSTUDIO_BASE_URL`) — the OpenAI-compatible
   REST surface exposes no version string, and probed non-standard endpoints
   (`/api/version`, `/system`, response headers) all 404. The operator was
   asked directly and supplied **`0.4.23`**, recorded here and in
   `report-v1.4.md` with this provenance note, per PRE-02's own point that
   the version is exactly what a later reader needs to reproduce or refute
   the spike.
3. **`standards/reporting.md` is not opened.** `AGENTS.md`: "Context
   boundaries: agents work inside this repository only. NEVER read or edit
   anything above the repository root." RPT-01 cites that external file's
   § "Run report" field list; `docs/reports/report-v1.3.md` already
   implements that same field list in full (produced by an earlier run under
   the identical standard) and is used in-repo as the structural template
   instead of opening the file above the repo root.
4. **A spec/`AGENTS.md` conflict is flagged for T10, not resolved yet.**
   RPT-05's last sentence — "Append the project's row to lab-root
   `economics.md`" — writes outside the repository root; REQ-V14-EC-01
   restates REQ-V1-EC-01 "absolutely," with BEN-02's worktree as the *only*
   exception. `AGENTS.md` § go protocol: "Where the spec and this file
   disagree, stop and ask." This will be surfaced to the operator at T10
   rather than decided unilaterally; every other T10 obligation is
   unaffected (RPT-04's E1 already quotes `economics.md`'s figures without
   writing to it).
