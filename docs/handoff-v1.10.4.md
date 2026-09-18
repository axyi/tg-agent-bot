# Handoff — v1.10.4, ready for `go`

What the `go` session reads first. Authored 2026-09-18 in the lab session;
the run happens in a different session (`standards/workflow.md` §14).

## The `go` line

```text
go docs/spec/spec-v1.10.4.md
```

No operator input. The run's `.env` is the v1.10.3 one with one key
rewritten by the lab on 2026-09-18 (checked at Stage 0 through
`load_config()` — the executor never reads the file):

| Key | Value | Role |
|---|---|---|
| `DB_PATH` | `data/run-v1104.db` | **rewritten** — fresh, absent at handoff; Stage 0 proves `db_empty=True` |
| `OPENROUTER_MODEL` | `openai/gpt-4.1` | unchanged — the model under test on the production route |
| `LLM_JUDGE_MODEL` | `openrouter:anthropic/claude-sonnet-5` | unchanged — one Stage-0 fallback to `openrouter:openai/gpt-5.6-sol` (v1.10.3 INS-01 by reference) |
| everything else | unchanged from v1.10.3 | OpenRouter embeddings and rerank, LM Studio empty |

Preconditions beyond `.env`: `OPENROUTER_API_KEY` set; the locked
environment synced; Docker reachable; **`git stash list` shows `stash@{0}`
with id `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`** ("v1103-T6 mutations
part: uncommitted at stop route …") — if it is absent or has another id,
the spec's Appendix D fallback applies and no stash is ever popped,
applied or dropped by the run. **Expected at T0**: gates 1–5 and 7 green on
the unchanged tree; gate 6 and 8 not run at T0.

**No push in this run.** The operator pushes `main` (now 77 commits ahead,
after this run more) and the tag `v1.10.4` together afterwards; the
pre-push hook reads the working-tree yaml. **Only if `git rev-parse
stash@{0}` still equals the pinned id after the run**, drop it after the
push (`git stash drop stash@{0}`); otherwise leave every stash alone.

## Models and effort

- **Executor: `claude-sonnet-5`**, orchestrator effort high, subagents
  default. **Reviewer:** the pinned `code-reviewer` (`sonnet`), clean
  context, T3.
- Briefs `docs/spec/task-briefs/v1104-T<n>.md` for T1, T2, T4 (the one
  yaml calibration hunk) and T5 (version, lock, tests, docs); T3 only iff
  it delegates a fix; T0 *commands only*; T4's live sequence *commands
  only*; T5's evidence commit *artefacts only*.
- Live cost is minutes: gate 5/7 at T0 and T4; gate 8 **exactly once**, at
  T4 (v1.10.2 RT-03's capture command, `v1104-gate8-${tested_tree}.log`);
  gate 6 once, directly, on a proved tree (~15 min for 144 entries) after
  the `--select v1103-` calibration run.

## What it is

1. **The five `v1103-*` mutation entries (MUT-01/02)** — from the stash's
   two non-test paths only (`git stash show -p stash@{0} | git apply
   --include='devtools/mutation_check.py' --include='config/quality_gates.yaml' -`,
   re-checked after T1), or Appendix D byte-exact; post-image blob ids
   verified; each entry proved killed in isolation by exact pytest node
   ids; `mutation-v1103` gate + subset; the `mutation-all` comment's single
   "is now" sentence re-anchored to this release (144). v1.10.3's GATE-02
   table is corrected in two rows (row 2's inner-predicate `False`, row 4's
   real killer LINT-09).
2. **Frozen-pin rewrites (PIN-01)** — every "list ends here" test becomes
   presence/contiguity/order: the `_V1102_IDS` tail, the v1100 tail (one
   assertion per release group), both "is now" anchors (release-agnostic,
   counted inside the `mutation-all` block), the README "no later row"
   tests, `tests/test_v1103_gates.py:73-81` (labels present and in
   historical order, no equality with the frozen matrix).
3. **Repoints (PIN-02)** — `lint-docs.report_path`, the five `report_path`
   pins, the spec-matrix reader, the brief-path token (`v1104-T<N>`), the
   README v1.10.3 stopped row at T1.
4. **The T0 inventory (EC-02)** — five parts, fail-closed: frozen-list
   patterns; every reference to `report_path`, the gate-label dict, the
   matrix parser, brief prefixes, version readers and count lines; absence
   and end-of-list forms; a deliberately broad grep; every hit classified
   before T1. **A pin missed after T0 is a disclosed amendment — it spends
   no repair cycle and never stops the run**; v1.10.3's per-pin budget rule
   is superseded with the reason recorded.
5. **Gates and stop routes (GATE-01/02, REV-03)** — gate 6 on a proved
   tree (`git diff --exit-code` + write-tree equality before and after; a
   wall over 1640 s is a construction defect with its own hunk and one
   rerun); gate 8 once, reused at T5 under the identity check; after T4's
   gate 5/7 no stop route touches a live gate; a stop-route table gives
   each stage (B′ at T4, B″ at T4, B at T5) its paths, prompt and commit
   rules; the verifier's informational green gate 8 on `f3ce1a5` is
   evidence about the instrument, never a release verdict.
6. **Version 1.10.4 (VER-01, T5)** — first commit: `pyproject.toml`,
   `uv lock`, `tests/test_v195_version.py` repointed to the tag blob,
   `tests/test_v1104_version.py`, AGENTS.md counts, the release row
   ("shipped judge default …; gate 8 judged by <effective judge>"), the
   five `pending (T9)` rows; evidence commit: exactly four paths; E1–E7
   before it, E8 post-commit/pre-tag; then the tag.

20 MUST, 10 NON-GOAL, 6 tasks (T0–T5), 22 test ids, 0 new mutation ids,
8 Gherkin, 15 ERR-01 rows, Appendix D (the two-path diff, sha256
`a54e5fae…`).

## Frozen decisions the run must not reopen (D1–D13)

- **1.10.4 is the version; 1.10.0–1.10.3 stay stopped, untagged runs.**
- **Instruments unchanged**; floors, no-rerun rule, temperature 0, stop
  route stand; the benchmark rule is not triggered (no prompt, tool-schema
  or model change).
- **No new mechanism, marker, prompt or model; no `v1104-*` mutation, no
  `mutation-v1104` gate; never `git stash pop`/`apply`/`drop`.**

## State

- Spec: `docs/spec/spec-v1.10.4.md`, 108,249 bytes (the 60 KB cap was
  overshot by the rounds and Appendix D). Commits: `5b17454` (draft, 179
  citations / 2 corrected, three audit contradictions applied), `e7690f1`
  (round 1), `8c9a2e1` (round 2), `2939aa2` (round 3). Authoring prompt
  `docs/prompts/227-…`; run prompts from **228**; `docs/llm-usage.md`
  from row 139.
- `[[VERIFY: …]]` markers: **3** — the `--select v1103-` calibration wall
  (the computed number always wins); the direct `mutation-all` wall
  (> 1640 s triggers ERR-01 row 8); the collected-test count after T2
  (T0's re-measure is the floor, T5 asserts ≥ floor + 22).

## Cross-review

Three rounds against OpenAI Codex `gpt-5.6-sol`: **20 findings, 19
accepted (4 adapted), 1 rejected** (a transport artefact: the anchor
regex's closing backtick dropped by the plan seam). Termination
**`round_limit`** — round 3 still returned two Critical (the fallback
route on a post-T1 patch-check failure; the write-tree proof) and two
High. **Residual findings may exist.**

Operator-visible consequences before `go`: `DB_PATH` points at
`data/run-v1104.db` (documents invisible until switched back); the stash
stays until the operator drops it after the push.
