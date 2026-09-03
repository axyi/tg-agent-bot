# Prompt 32 — v1.4 T0: preconditions + report skeleton

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); precondition
  verification is mechanical, no task-specific override needed.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `docs/reports/report-v1.4.md` (created), `docs/prompts/31-go-spec-v1.4.md`,
  `docs/prompts/32-v14-t0-preconditions.md` (both new)
- **REQ ids:** REQ-V14-PRE-01…05, REQ-V14-GATE-01

## Brief as sent (self-directed, per ORD-01's T0 row)

```
Verify REQ-V14-PRE-01..05 before any code change:
1. Branch main, clean tree, HEAD (declared deviation recorded in prompt 31).
2. Run all six AGENTS.md gates on the untouched tree; gate 5 including its
   lmstudio check must be fully green (v1.2's exception withdrawn).
3. .env presence by key NAME only (never print a value) for the nine
   required keys.
4. docker version without sudo; sandbox image (config.py's
   DEFAULT_DOCKER_IMAGE, python:3.13-slim) present via `docker image
   inspect`.
5. docs/assets/bench/ writable; .bench/ git-ignored.
6. PRE-02: record the LM Studio version and loaded model id in
   report-v1.4.md before any live step. PRE-03: verify, against live vendor
   docs (not memory), the LM Studio reasoning request field and whether it
   documents a disable value, and OpenRouter's documented reasoning field;
   cite what was read, dated.
7. PRE-04/05: dry-check `git worktree add`+`remove` and confirm the tree is
   clean afterward — the mechanical proof that BEN-02's two-tree measurement
   is possible.
Create docs/reports/report-v1.4.md as a skeleton: this task's results, the
LM Studio version, and the PRE-03 citations, written in before SCN-01 or any
other live step (T0 creates the file; T10 completes it, never creates it).
```

## Results

### 1. Branch / HEAD

`main`, working tree clean. HEAD `3bc8e8b` — declared deviation from the
literal `3a0aa3d`, recorded in prompt 31 item 1 (doc-only diff, zero
production-code drift).

### 2. Six gates, pre-change tree

| # | Gate | Result |
|---|---|---|
| 1 | `uv sync --locked` | OK — resolved 16 packages, checked 13 |
| 2 | `uv run --locked ruff check .` | All checks passed |
| 3 | `uv run --locked pytest` | **719 passed** in 24.54s (matches EC-03's stated v1.3 count) |
| 4 | `uv run --locked python bot.py --selftest` | `selftest: OK` |
| 5 | `uv run --locked python bot.py --selftest-live` | `OK config`, `OK db`, `OK docker (29.7.2)`, `OK telegram`, `OK lmstudio`, `OK openrouter` — all six green, `lmstudio` included |
| 6 | `uv run --locked python devtools/mutation_check.py` | **65 mutations, 65 killed, 0 survived, 0 errored, 0 drifted** |

All six exit 0. Precondition PRE-01 item 2 satisfied — an unreachable LM
Studio would have blocked the run; it did not.

### 3. `.env` presence (key names only, no values read or printed)

Present: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_NAME`, `ALLOWED_TG_IDS`,
`LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`,
`LMSTUDIO_CONTEXT_LENGTH`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` — all
nine required keys. (Two additional keys exist, `LLM_PRICE_REF_MODEL` and a
blank `ALLOWED_TG_IDS` value is not inspected — presence by name only.)

### 4. Docker

`docker version --format '{{.Server.Version}}'` → `29.7.2`, no `sudo`.
`docker image inspect python:3.13-slim` → present locally
(`sha256:51cce855…`), matching `config.py`'s `DEFAULT_DOCKER_IMAGE`.

### 5. `docs/assets/bench/`

Writable (write-test file created and removed). `.bench/` is git-ignored
(`.gitignore:21`). `docs/assets/bench/*.log` is *also* git-ignored
(`.gitignore:22`) while `*.json` is not — confirmed with `git check-ignore -v`
and `git ls-files`: today only the four `.json` files are tracked there, no
`.log`. RPT-08's `git add -f` obligation for every required log is therefore
real, not hypothetical, and will apply from T3 onward.

### 6. PRE-02 — LM Studio version and model

- **Model:** `qwen/qwen3.8-27b` (`GET /v1/models` on `LMSTUDIO_BASE_URL`),
  matching `LMSTUDIO_MODEL` in `.env` and `bench-v1.3.md:12-13`.
- **Context length:** `LMSTUDIO_CONTEXT_LENGTH=42496` in `.env`, matching
  every v1.3 file.
- **LM Studio server version: `0.4.23`.** This session has no SSH access and
  no version-reporting endpoint reachable on the remote LM Studio host
  (`172.16.50.233`); the REST surface's `/v1/models`, `/api/v0/models` and
  probed non-standard paths (`/api/version`, `/system`, `/health`, response
  headers) carry no version field. **The version is operator-supplied**,
  read from the LM Studio UI/CLI on the GPU box by the human operator at the
  executor's request, not self-observed by this session. This provenance is
  stated explicitly because PRE-02 exists precisely so a later reader can
  audit it.

Both match PRE-02's mandated pair; neither is a blocker.

### 7. PRE-03 — vendor documentation, read live, 2026-09-03

**LM Studio** (`https://lmstudio.ai/docs/developer/openai-compat/chat-completions`,
`https://lmstudio.ai/docs/developer/api-changelog`, both fetched
2026-09-03):

- The Chat Completions page's documented parameter list is `model`, `top_p`,
  `top_k`, `messages`, `temperature`, `max_tokens`, `stream`, `stop`,
  `presence_penalty`, `frequency_penalty`, `logit_bias`, `repeat_penalty`,
  `seed` — no mention of `reasoning`, `reasoning_effort`, or
  `chat_template_kwargs`, and no statement either way about whether unknown
  top-level body keys reach the chat template. Whether candidate **a**
  (`chat_template_kwargs: {"enable_thinking": false}`) binds is therefore
  **undocumented and must be measured live** (RSN-01), exactly as PRE-03
  anticipates.
- The API changelog's only reasoning-related entries: **0.3.29** —
  "Reasoning support with `reasoning.effort` for `openai/gpt-oss-20b`"
  (values `low` / `medium` / `high`); **0.3.23** — for `gpt-oss` on
  `POST /v1/chat/completions`, reasoning content moves from `message.content`
  into `choices.message.reasoning` (non-streaming) /
  `choices.delta.reasoning` (streaming); **0.3.9** — separate
  `reasoning_content` in chat-completion responses. Nothing between `0.3.29`
  and the running `0.4.23` documents a disable value, and nothing documents
  `reasoning.effort` for a Qwen3-class model at all — the field is
  documented for `gpt-oss` only. Per RSN-02's own text, this means
  candidate **b** is heading toward `unsupported` unless the live probe
  itself (not the docs) finds otherwise; T4 still probes it, since the spike
  is what settles it, not this reading. No disable value (`none`,
  `enabled: false`, or equivalent) is documented for `reasoning.effort` at
  any version through `0.4.23`.

**OpenRouter** (`https://openrouter.ai/docs/use-cases/reasoning-tokens`,
fetched 2026-09-03): the documented request-body object is

```json
{"reasoning": {"effort": "high", "max_tokens": 2000, "exclude": false, "enabled": true}}
```

with `effort` accepting `max|xhigh|high|medium|low|minimal|none`. The page
states reasoning tokens "are considered output tokens and charged
accordingly" and that with `"exclude": true` "the model will still use
reasoning, but it won't be returned in the response" — confirming `exclude`
hides but does not stop billing, so POL-07's off-switch is `"enabled": false"`
(equivalently `"effort": "none"`), matching the spec's own PRE-03 text
verbatim. No live-doc drift found; nothing to reconcile.

### 8. PRE-04/05 — worktree dry-check

`git worktree add --detach <tmp-path> HEAD` succeeded; `git worktree remove
<tmp-path> --force` succeeded; `git worktree list` shows only the main
working tree afterward; `git status --short` empty. The two-tree measurement
of BEN-02 is mechanically possible.

## Deviations recorded

1. HEAD precondition (declared, prompt 31 item 1) — not a blocker.
2. LM Studio version obtained from the operator, not self-read (prompt 31
   item 2) — not a blocker, PRE-02's obligation (record before any live step)
   is met.
3. `standards/reporting.md` not opened (prompt 31 item 3) — RPT-01's field
   list is instead reproduced from `docs/reports/report-v1.3.md`'s own
   structure.
4. RPT-05's lab-root `economics.md` write flagged for T10 (prompt 31 item 4)
   — not yet a blocker, T0…T9 are unaffected.

## Gate results at this commit

Gates 1–5 as tabulated above (all green). Gate 6: 65/65 mutations killed —
re-run required at this commit because this commit is docs-only (no
production code, configuration behaviour, benchmark verdict logic, tests or
mutations touched) — GATE-01's gate-6 trigger condition does not fire, but it
was already run once during precondition verification and stays green.
