# Prompt 204 — v1.10.1 T1: embeddings over OpenRouter, gate 5's route rule

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (§16.1: `delegate? yes`);
  general-purpose subagent, briefed by `docs/spec/task-briefs/v1101-T1.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T1
- **Owner of:** `config.py`, `llm/embeddings.py`, `bot.py:1862-1925`,
  `bot.py:2088-2100`, `devtools/rag_eval.py:750-756`,
  `tests/test_v1101_config.py`, `tests/test_v1101_embeddings.py`,
  `tests/test_v190_embeddings.py:381-389`, `:404-409` (renamed only)
- **REQ ids:** REQ-V1101-CFG-02, REQ-V1101-EMB-01, REQ-V1101-EMB-02,
  REQ-V1101-G5-01, REQ-V1101-G5-02, REQ-V1101-SEC-01

## Goal

`embedding_api_key` resolved from `OPENROUTER_API_KEY` through one
`is_openrouter_url(url)` helper in `config.py`; `EmbeddingsClient` sends an
`Authorization: Bearer` header only when given a non-empty key;
`describe()` becomes provider-aware over the same helper; `_live_lmstudio`
SKIPs when no routed purpose uses LM Studio; `_live_embeddings` drops the
unauthenticated `/models` listing step and keeps only the authenticated
embeddings round-trip. Then gate 5 and gate 7 run live, in sequence, and
must both exit 0.

## Constraints

Touch only the files listed in the task brief. No new dependency. The key
is never printed, logged, or present in any exception message. `.env`
never read directly — only through `load_config()`. Run gates 1–4 first,
offline, all green, before running anything live. Gate 6 and gate 8 are
not this task's job. `--no-verify` never used.

## Acceptance

Gates 1–4 exit 0. Gate 5 (`bot.py --selftest-live`) exits 0 with `live: OK
embeddings` and `live: SKIP lmstudio (no route uses it)`, no other line
red. Gate 7 (`devtools/rag_eval.py`) exits 0 with `hybrid` recall@5 at or
above its floor. `tests/test_v1_guardrails.py:1425-1445` stays green
unamended.

## Stop

Gate 7's `recall@5` red on the new embedder is not this task's problem to
fix by switching models — report back to the orchestrator instead (REV-04
Stage B″ is an orchestrator decision). Any other gate-5 or gate-7 red after
a genuine attempt is a normal repair-and-report.
