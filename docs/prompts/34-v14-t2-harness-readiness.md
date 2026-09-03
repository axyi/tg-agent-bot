# Prompt 34 — v1.4 T2: harness readiness (BEN-03, BEN-04, BEN-05, BEN-02 item 5)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); mechanical
  harness edits plus one judgment call (whether to patch stale test
  fixtures) resolved via the advisor tool, not a model swap.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `devtools/bench.py`, `tests/test_bench.py`,
  `tests/test_v14_patch.py`, `tests/fixtures/bench/baseline.json`,
  `tests/fixtures/bench/candidate.json` (declared deviation, see below),
  `docs/reports/report-v1.4.md`,
  `docs/prompts/34-v14-t2-harness-readiness.md` (new)
- **REQ ids:** REQ-V14-BEN-02 (item 5), REQ-V14-BEN-03, REQ-V14-BEN-04,
  REQ-V14-BEN-05

## Brief as sent (self-directed, per ORD-01's T2 row)

```
BEN-03: replace bench.py's `set(row) == set(keys)` row-key equality
(llm_calls/tool_calls validation) with REQUIRED ⊆ set(row) ⊆ allowed. Add
REQUIRED_LLM_ROW_KEYS as a literal frozen tuple/frozenset spelling the v1.3
column set — NOT derived from storage. TOOL_ROW_KEYS: state whether the
same rule applies (it does, degenerately: REQUIRED == current, since no
tool_calls schema change happens in this spec).
BEN-04: meta.constants and summarize() MUST NOT change — add regression
tests confirming both are policy-independent (constants() takes no config
argument by construction; summarize() ignores columns it doesn't read).
BEN-05: ENV_FLAG_FIELDS gains LLM_REASONING_POLICY and
LLM_REASONING_ON_PURPOSES (9 keys total); env_flags() serializes the
latter as a sorted comma-joined string when it's a frozenset; the stale
"exactly the seven documented keys" message is corrected to name the
count programmatically. Neither key joins STAGE_C_KEYS or
LOCKED_META_FIELDS; comparability() needs no change (no rule references
either key). Test-first throughout (EC-02).
Then BEN-02 item 5: prove the two-tree measurement is mechanically
possible — worktree at 69ebc75, copy in the v1.4 bench.py/
bench_scenarios.py/__init__.py, symlink .env, dry-run S01 on both trees,
report --gate expecting exit 0 or 1 (never 2/3), clean up.
```

## Implementation

### BEN-03 — the row-key rule

`LLM_ROW_KEYS`/`TOOL_ROW_KEYS` stay derived from the running tree's storage
columns (unchanged — that derivation itself is fine; only the *comparison*
against a loaded row was the hazard). Added `REQUIRED_LLM_ROW_KEYS`, a
literal `frozenset` spelling exactly the v1.3 `llm_calls` column set
(25 keys, `conv_id` → `conv_seq`), independent of `storage`. The validation
loop in `_validate_run` now checks, per row:
`required - row_keys` (missing, named in the error) and
`row_keys - allowed` (unknown, named in the error), instead of `==`.
`TOOL_ROW_KEYS` serves as both its own `required` and `allowed` bound — the
spec's explicit "state why not" option, since no tool-call schema change
lands in this run.

Verified live: the BEN-02 item 5 dry run below produced a stage-A
(`69ebc75`) `llm_calls` row with exactly the v1.3 column set, read
successfully by the v1.4 `report` command — the real-world case this rule
exists for.

### BEN-04 — regression guards, no production change

`constants()` and `summarize()` are untouched (the spec forbids touching
them). Added `test_t_v14_ben_03_constants_and_summarize_are_policy_independent`:
confirms `constants()` takes no `Config`/policy argument (so nothing a
reasoning policy could vary reaches it — byte-equal across two calls,
literally), that neither `constants()` nor `REQUEST_DEFAULTS` carries a
reasoning-named key, and that `summarize()` produces the expected
aggregate for a v1.3-shaped document (no `reasoning_requested`/
`reasoning_honored` anywhere in its rows).

### BEN-05 — nine `env_flags` keys

`ENV_FLAG_FIELDS` gains `LLM_REASONING_POLICY` → `llm_reasoning_policy` and
`LLM_REASONING_ON_PURPOSES` → `llm_reasoning_on_purposes` — added now, ahead
of the `Config` fields themselves (which land in a later task): the
existing absent-field fallback in `env_flags()` already resolves an
unmapped field to `null`, so this is safe today and needs no further
`bench.py` change once the fields exist. `env_flags()` additionally
special-cases `LLM_REASONING_ON_PURPOSES`: when its resolved value is a
`frozenset`/`set` (i.e. once the `Config` field is real), it is serialized
as a sorted, comma-joined string. The stale message at the meta-shape
validator is corrected to `f"...exactly the {len(ENV_FLAG_KEYS)}..."`.
Neither new key joins `STAGE_C_KEYS` or `LOCKED_META_FIELDS`; `comparability()`
is untouched — it has no rule referencing either key, so a baseline (both
null) beside a candidate (`"off"`/`""` or `"by-purpose"`/`"tool-round"`)
compares by construction. Pinned by two new fixture tests
(`test_ben_05_both_allowed_reasoning_policy_pairs_are_comparable`,
`test_ben_05_an_unrelated_env_flags_difference_still_blocks_the_gate`).

### Declared deviation — `tests/fixtures/bench/*.json` patched

Growing `ENV_FLAG_KEYS` to nine broke `tests/test_dashboard.py::
test_fixtures_are_arithmetically_valid_benchmark_documents`, an **unlisted**
test under REQ-V14-EC-03 — its fixtures
(`tests/fixtures/bench/baseline.json`/`candidate.json`, 7-key `env_flags`)
no longer validate. Consulted the advisor before acting, given EC-03's
explicit "stop and reconsider, do not edit the test." Conclusion, verified
by `grep -rn "docs/assets/bench" tests/ devtools/dashboard.py`: no test
loads a real committed `docs/assets/bench/*.json` measured artifact for
validation — the two failing files are `tests/fixtures/` **test data**, not
measured evidence. BEN-05's two MUSTs (nine keys; strict equality,
unchanged in kind) collide by construction with any 7-key document, and
this can't be deferred to a later task — BEN-02 item 2 copies the v1.4
`bench.py` into the `69ebc75` worktree, so `baseline-v1.4.json` itself would
face the identical failure at T3 if the fixtures (or the rule) weren't
fixed now. Patched: added the two new keys as `null` to both JSON files
(arithmetic untouched — `env_flags` enters no total or summary
computation) — a 4-line diff, confirmed with `git diff --stat`. **No
assertion in `tests/test_dashboard.py` was touched**; its documented
tolerance ("the one tolerated failure is a stale `scenarios_sha256`") is
restored, not weakened. No `docs/assets/bench/` measured artifact was
edited.

### BEN-02 item 5 — the dry run

```
git worktree add --detach <job-tmp>/wt-dryrun 69ebc75
cp devtools/{bench.py,bench_scenarios.py,__init__.py} <worktree>/devtools/
ln -sf <main-root>/.env <worktree>/.env
# in the worktree:
LLM_FAILOVER=off LLM_SUMMARY_MODEL= LLM_TIMEOUT_S=240 LLM_MAX_TOKENS=2048 \
  uv run --locked python devtools/bench.py run --only S01 --repeats 1 \
  --tag dryrun-base --out <main-root>/docs/assets/bench/dryrun-base.json
# in the v1.4 tree:
LLM_FAILOVER=off LLM_SUMMARY_MODEL= LLM_TIMEOUT_S=240 LLM_MAX_TOKENS=2048 \
  uv run --locked python devtools/bench.py run --only S01 --repeats 1 \
  --tag dryrun-cand --out docs/assets/bench/dryrun-cand.json
uv run --locked python devtools/bench.py report \
  --baseline docs/assets/bench/dryrun-base.json \
  --candidate docs/assets/bench/dryrun-cand.json --gate --out /dev/null
```

- `dryrun-base`: `prefix_tokens=1126` (stage-A, matches `bench-v1.3.md:21`'s
  pre-optimization figure) — confirms the worktree really is the
  pre-optimization tree.
- `dryrun-cand`: `prefix_tokens=842` (post-optimization, matches v1.3's
  candidate figure) — confirms the v1.4 tree is the treatment.
- `report --gate`: **exit 1** (`verdict: FAIL (cost gate failed)` — expected
  and meaningless on one scenario per the spec's own text). **Not 2 or 3.**
  The two-tree measurement, including BEN-03's row-key rule reading a real
  stage-A row and BEN-05's `env_flags()` resolving both new keys to `null`
  from the stage-A `Config` (which has neither field), is mechanically
  proven.

Cleanup: `docs/assets/bench/dryrun-{base,cand}.{json,log}` deleted (scratch,
per the spec); worktree removed (`git worktree remove --force`); `git
worktree list` and `git status --short` confirmed clean afterward.

## Gate results at this commit

720 → 726 tests (+6: two BEN-05 comparability fixtures, one unknown-column
row-key test, three new T-V14-BEN-0{1,2,3} tests in
`tests/test_v14_patch.py`; one test renamed, not counted as new). All six
gates green — gate 6 required (production code, config behaviour and tests
all changed).
