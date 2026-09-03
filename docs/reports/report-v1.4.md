# Implementation report — spec-v1.4

**Status: IN PROGRESS.** This file is initialized at T0 (REQ-V14-PRE-02's
"T0 creates the file" rule) and completed at T10 — it is never created
retroactively. Sections below are filled in as their owning task lands;
pending sections say so explicitly rather than being silently absent.

Executor model: **claude-sonnet-5** (Claude Code harness, background
session), pinned by spec-v1.4's own preamble.
Prompt: `go docs/spec/spec-v1.4.md` — logged as
`docs/prompts/31-go-spec-v1.4.md`, task prompts from `32`.

Commits on `main` (grows per task; ORD-01 order):

| commit | task | contents |
|---|---|---|
| _pending_ | T0 | preconditions, this report's skeleton (`docs/prompts/31-…`, `32-…`) |

## Preconditions (T0 — REQ-V14-PRE-01…05)

### LM Studio version and model (PRE-02)

- **Model:** `qwen/qwen3.8-27b` (`LMSTUDIO_MODEL`, confirmed live via
  `GET /v1/models`), context length `LMSTUDIO_CONTEXT_LENGTH=42496` — both
  match every v1.3 file (`bench-v1.3.md:12-13`).
- **LM Studio server version: `0.4.23`.** Operator-supplied: this session has
  no SSH access and no version-reporting endpoint on the remote LM Studio
  host, so the version could not be self-observed and was read by the human
  operator from the LM Studio UI/CLI on request. See
  `docs/prompts/32-v14-t0-preconditions.md` § 6 for the full provenance
  note.

### Vendor documentation read live, 2026-09-03 (PRE-03)

**LM Studio** — `https://lmstudio.ai/docs/developer/openai-compat/chat-completions`
and `https://lmstudio.ai/docs/developer/api-changelog`:

- The documented Chat Completions body parameters are `model`, `top_p`,
  `top_k`, `messages`, `temperature`, `max_tokens`, `stream`, `stop`,
  `presence_penalty`, `frequency_penalty`, `logit_bias`, `repeat_penalty`,
  `seed`. No statement on whether unknown top-level keys reach the chat
  template — candidate **a** (`chat_template_kwargs: {"enable_thinking":
  false}`) is undocumented behaviour and must be measured (RSN-01).
- Changelog: **0.3.29** added `reasoning.effort` (`low|medium|high`) for
  `openai/gpt-oss-20b` only; **0.3.23** moved `gpt-oss` reasoning content to
  `choices.message.reasoning` / `choices.delta.reasoning`; **0.3.9**
  introduced separate `reasoning_content`. Nothing through the running
  `0.4.23` documents `reasoning.effort` for a Qwen3-class model, and nothing
  documents a disable value at any point — only `low|medium|high`. Per
  RSN-02, this points candidate **b** toward `unsupported`; T4 still probes
  it live, since the spike — not this reading — is what settles it.

**OpenRouter** — `https://openrouter.ai/docs/use-cases/reasoning-tokens`:
documented body is
`{"reasoning": {"effort": "high", "max_tokens": 2000, "exclude": false, "enabled": true}}`,
`effort ∈ {max, xhigh, high, medium, low, minimal, none}`. The page states
reasoning tokens are billed as output tokens and that `"exclude": true`
still lets the model reason, only hiding it from the response — confirming
`"exclude": true` MUST NOT be used as an off-switch (spec text) and that the
off-switch is `"enabled": false"` / `"effort": "none"`. Matches the spec's
own PRE-03 text; no drift found.

### Deviations recorded at T0

1. **HEAD precondition.** PRE-01 item 1 names `3a0aa3d`; actual HEAD at T0 is
   `3bc8e8b`. `git diff --stat 3a0aa3d..HEAD` — two files, both docs
   (`docs/spec/spec-v1.4.md` created, `docs/llm-usage.md` +1 line), zero
   production-code drift. Treated as satisfied in substance, not a blocker.
2. **LM Studio version is operator-supplied**, not self-read (see above) —
   PRE-02's obligation (recorded before any live step) is met regardless.
3. **`standards/reporting.md` is not opened** (outside the repository root,
   `AGENTS.md`'s context boundary). RPT-01's field list is instead
   reproduced from `docs/reports/report-v1.3.md`'s own structure, which
   already implements it.
4. **A spec / `AGENTS.md` conflict is flagged for T10**: RPT-05 asks for a
   row appended to lab-root `economics.md`, which sits outside the
   repository root; `AGENTS.md` says stop and ask when the spec and it
   disagree. Not yet a blocker — T0…T9 are unaffected, and RPT-04's E1
   already quotes `economics.md`'s existing figures without writing to it.

## Gates

Six gates, run verbatim, in the order of `AGENTS.md` / §11. One row per
commit; T0's row is the pre-change tree (no commit yet at the time these
were run — the gates that PRE-01 item 2 requires before touching anything).

| point | 1 `uv sync --locked` | 2 `ruff check .` | 3 `pytest` | 4 `--selftest` | 5 `--selftest-live` | 6 `mutation_check.py` |
|---|---|---|---|---|---|---|
| T0 (pre-change) | rc=0 | rc=0, all checks passed | rc=0 — **719 passed** | rc=0 | rc=0 — `config`/`db`/`docker (29.7.2)`/`telegram`/`lmstudio`/`openrouter` all OK | rc=0 — **65 mutations, 65 killed**, 0 survived, 0 errored, 0 drifted |

_(Further rows land as each task's commit completes — GATE-01's per-commit
rule: gates 1–5 always, gate 6 additionally at commits touching production
code, configuration behaviour, benchmark verdict logic, tests or mutations,
and on the final tree.)_

---

## Sections pending later tasks

The following REQ-V14-RPT-01 items are written by the task that produces
their evidence and are placeholders until then:

1. **Verdict against `B_v1.4`** (`B_plain`, `C_plain`, `C_conservative`,
   threshold, gate outcomes, honored rate, any `DRIFT:`/`FINISH-LENGTH:`
   line) — T7/T8/T10.
2. **The mechanism table** (RSN-04) — T4.
3. **The S01 root cause** (hypothesis, evidence, check diff if H1,
   `temperature: 0` note) — T1.
4. **Errata to earlier reports** (RPT-04, E1/E2) — T10.
5. **Gates table, full** and exact test/mutation counts — grows per commit,
   finalized T10.
6. **Appendix-B results**, how each was driven, deviations, fix cycles — T10.
7. **Known defects carried forward** (incl. REL-03's disposition) — T6/T10.
