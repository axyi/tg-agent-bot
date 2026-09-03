# Prompt 35 — v1.4 T3: baseline-v1.4 (BEN-02, BEN-06)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); a live
  measurement run needs no judgment beyond the spec's own procedure.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `docs/assets/bench/baseline-v1.4.json`,
  `docs/assets/bench/baseline-v1.4.log`,
  `docs/reports/bench-baseline-v1.4.md`, `docs/reports/report-v1.4.md`,
  `docs/prompts/35-v14-t3-baseline-v14.md` (new)
- **REQ ids:** REQ-V14-BEN-02, REQ-V14-BEN-06

## Brief as sent (self-directed, per ORD-01's T3 row)

```
BEN-02: measure the stage-A tree (69ebc75, v1.3's pre-optimization code)
with the v1.4 scenario file and v1.4 harness — the -30% target is
cumulative over v1.3's -7.3%, since only a pre-stage-C tree produces null
stage-C keys that comparability() requires.
git worktree add <abs-path> 69ebc75; copy in the v1.4 bench.py/
bench_scenarios.py/__init__.py only (nothing else — the worktree's product
code stays exactly what 69ebc75 shipped, that's the treatment measured);
symlink .env by absolute path (credentials never opened for content);
process-env overrides LLM_FAILOVER=off LLM_SUMMARY_MODEL=
LLM_TIMEOUT_S=240 LLM_MAX_TOKENS=2048 on every command; --out into the
main tree's docs/assets/bench/ (DEFAULT_OUT_DIR is bound to the running
tree, which would otherwise vanish with the worktree).
BEN-06: confirm wttr.in reachable immediately before and after the full
run; skipped_scenarios must be [] on both counts.
Full run: --tag baseline-v1.4 --repeats 3 --timeout-s 1800. Remove the
worktree when done; never commit to it or amend 69ebc75.
```

## Execution

wttr.in preflight: `curl -I https://wttr.in/` → `200`, before and after the
run.

```
git worktree add --detach <job-tmp>/wt-baseline-v14 69ebc75
cp devtools/{bench.py,bench_scenarios.py,__init__.py} <worktree>/devtools/
ln -sf <main-root>/.env <worktree>/.env
# in the worktree:
LLM_FAILOVER=off LLM_SUMMARY_MODEL= LLM_TIMEOUT_S=240 LLM_MAX_TOKENS=2048 \
  uv run --locked python devtools/bench.py run --tag baseline-v1.4 \
  --repeats 3 --timeout-s 1800 --out <main-root>/docs/assets/bench/baseline-v1.4.json
```

## Result

```
bench baseline-v1.4  provider=lmstudio  model=qwen/qwen3.8-27b  repeats=3  prefix_tokens=1126
S01 greet          3/3   S02 arith          3/3   S03 file-roundtrip 3/3
S04 error-explain  3/3   S05 big-output     3/3   S06 noisy-log      3/3
S07 skill          3/3   S08 fetch-weather  3/3   S09 multi-turn     3/3
S10 knowledge      3/3   S11 json           3/3   S12 summary        2/3
totals: calls 91 (failed 0)  prompt 130.1k  completion 19.6k  tools 47  cost $0.1053  wall 3753s
success rate: 35/36 (97.2%)
cost/success $0.0030  tokens/success 4277  re-sent share 50.9%  cache hit n/a
skipped: none
```

`prefix_tokens=1126` — confirms this really is the pre-optimization
(stage-A) system prompt (matches `bench-v1.3.md:21`'s pre-O4/PFX figure,
and the un-rewritten `SYSTEM_PROMPT` inspected at T1).

**`meta.skipped_scenarios == []`**, before and after (BEN-06 satisfied).
`meta.env_flags` — all 9 keys present, `HISTORY_TOOL_STUB` /
`EXEC_OUTPUT_DEFAULT_CHARS` / `FETCH_INLINE_DEFAULT_CHARS` / `LLM_REASONING`
/ `LLM_REASONING_POLICY` / `LLM_REASONING_ON_PURPOSES` all `null`,
`LLM_SUMMARY_MODEL` `null` (stage-C key, correctly absent on the stage-A
side per `comparability()`'s allowance), `LLM_FAILOVER` `"off"`,
`LLM_MAX_TOKENS` `2048` — exactly BEN-05's predicted stage-A shape,
produced with zero code change beyond T2's `env_flags()` extension.
`meta.config_sha256`: `8a9cf9040f2df0…`. `meta.scenarios_sha256`:
`d0d9e3f658d1ad…` (post-T1 repair, as expected — every v1.3 file is
incomparable with this one, BEN-01).

**One failed repeat, not a blocker.** S12 repeat 1: `summary_exists` failed
("0 summary row(s), no goal") — the `/new` command's summarization call
produced no summary row that repeat. Baseline runs are exempt from every
candidate-only assertion (BEN-08: "a baseline is allowed to exhibit the
defect it is the baseline of"); this is simply `B`'s measured 35/36. No
`meta.aborted`.

**`B_plain` (the cost gate's baseline denominator):**
`Σcost / successes = $0.105306075 / 35 = $0.003008745`. Gate threshold
(`0.70 × B_plain`): **$0.0021061215**.

**Observed, not a defect to fix:** `meta.git_commit` is `""`, not
`69ebc75`. `_git_commit()` (`bench.py:2069-2078`) reads `REPO_ROOT/.git/HEAD`
directly; in a linked worktree `.git` is a plain redirect **file**
(`gitdir: <main>/.git/worktrees/wt-baseline-v14`), not a directory, so the
read raises `NotADirectoryError` (an `OSError` subclass) and the `except`
clause returns `""`. Harmless: `git_commit` is explicitly **not** one of
the ten `LOCKED_META_FIELDS` (BEN-02 item 2's own text: "not locked, so the
dirty tree costs nothing"), so `comparability()` never reads it and no
requirement is violated. Not fixed — outside this patch release's scope
(NG-08).

Artefacts committed: `baseline-v1.4.json`, `baseline-v1.4.log` (`git add
-f`, RPT-08), `bench-baseline-v1.4.md`. Secret-pattern scan (credential key
names in value positions, `authorization:` headers, long bot-token shapes)
clean on both.

Worktree removed (`git worktree remove --force`); `git worktree list` and
`git status --short` confirmed the main tree untouched by the 69ebc75
checkout.
