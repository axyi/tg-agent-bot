# Prompt 39 — v1.4 T9: mutations, STOP branch (TST-05, narrowed)

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code, background session)
- **Model reason:** continues the run's pinned model (prompt 31); adding
  two mutation entries and correcting a stale comment, no judgment beyond
  verifying each entry is genuinely killed.
- **Harness:** Claude Code CLI
- **Stage:** generation
- **Owner of:** `devtools/mutation_check.py`, `docs/reports/report-v1.4.md`,
  `docs/prompts/39-v14-t9-mutations.md` (new)
- **REQ ids:** REQ-V14-TST-05 (STOP-branch minimum only)

## Brief as sent (self-directed, per ORD-01's T9 row, GATE-02-narrowed)

```
STOP branch: TST-05's six-entry minimum reduces to the v14-* entries
defending shipped code only — BEN-03's row-key rule, REL-01's boundary.
Also fix the stale "64 in all" header comment (65 entries exist pre-v1.4,
confirmed by direct count). Each entry: dict with exactly id/path/find/
replace/why in that order, id of form v14-<kebab-description>, why opens
with the REQ id, find occurs exactly once in its target file, and each
MUST make `pytest -x -q` exit exactly 1 (KILLED).
```

## Header comment fix

`grep`-confirmed pre-existing count: 65 (`len(mc.MUTATIONS)`), while the
comment read "64 in all" — a genuine staleness the spec's own GATE-01
text names explicitly. Corrected to "65 in all," and a new paragraph
records the v1.4 STOP-branch addition bringing the total to 67.

## REL-01's boundary — first attempt, correct

`config.py`'s new `_check_timeout_budget`: `if llm_timeout_s < floor:` →
`if False and llm_timeout_s < floor:` (disables the raise). Verified
killed in the full 67-entry run: `T-V14-REL-01`'s first `pytest.raises`
block ("DID NOT RAISE ConfigError") fails.

## BEN-03's row-key rule — first attempt survived, corrected

First attempt mutated the *missing* half of the check (`missing =
required - row_keys` → `missing = allowed - row_keys`), matching TST-05's
literal phrasing ("⊆ restored to =="). **This survived** the real gate
run (67 mutations, 66 killed, 1 survived). Root cause, confirmed by
direct inspection: `REQUIRED_LLM_ROW_KEYS == LLM_ROW_KEYS` byte-for-byte
in the *current* tree — there is no OBS-01 column addition on the STOP
branch (T5 never ran), so `required` and `allowed` are the same
frozenset content. Swapping one symbol for the other in the *missing*
half is therefore observationally identical for every possible row:
the ⊆-vs-== distinction TST-05's phrasing describes only becomes
observable once a future `OBS-01`-style column widens `allowed` beyond
`required`, which this STOP-branch run never does.

Corrected to mutate the *unknown*-column half instead (`unknown =
row_keys - allowed` → `unknown = set()`), which is real and observable
right now, independent of `required`/`allowed` equality: it neutralizes
the "carries unknown column(s)" rejection. `id` renamed
`v14-ben-03-unknown-column-accepted` to describe what it actually does,
rather than the abandoned ⊆-vs-== framing. Verified killed in a second
full clean run (67 mutations, **67 killed**, 0 survived/errored/drifted):
`test_t_v14_ben_01_row_key_rule_accepts_a_v13_shaped_row`'s
`unknown_row` case ("not_a_real_column" in reason) fails to raise.

**Process note — a self-caused false "killed" reading.** Between the two
full-suite runs, an isolated `--only v14-ben-03-...` check was run
*concurrently* with the still-running full gate (both processes mutating
files in the same working tree). It reported "killed," but for the wrong
reason — an unrelated test failing due to the concurrently-running
process's own transient mutation of a different file, not the BEN-03
mutation itself. The real signal (SURVIVED) only appeared in the clean,
non-concurrent full run. `git diff` was checked immediately afterward
and showed no residual corruption (each process only touches the file(s)
its own mutation targets), but running two `mutation_check.py` instances
against the same working tree at once was a mistake, not repeated for
the second verification pass.

## Two new entries (final)

```python
{
    "id": "v14-ben-03-unknown-column-accepted",
    "path": "devtools/bench.py",
    "find": "            unknown = row_keys - allowed\n",
    "replace": "            unknown = set()\n",
    "why": "REQ-V14-BEN-03: a row carrying a key neither REQUIRED nor ALLOWED "
           "expects must be rejected, naming it — this mutation accepts any "
           "unknown column silently",
},
{
    "id": "v14-rel-01-timeout-budget-boundary-disabled",
    "path": "config.py",
    "find": "    if llm_timeout_s < floor:\n",
    "replace": "    if False and llm_timeout_s < floor:\n",
    "why": "REQ-V14-REL-01: an LLM_TIMEOUT_S/LLM_MAX_TOKENS pair under the "
           "latency-model floor must be refused before it ever reaches a live "
           "request, not silently accepted",
},
```

`tests/test_mutation_check.py` needed **no change**: both
`test_t_v12_mut_04_at_least_28_entries_each_with_a_unique_id` and
`test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo`
already iterate `mc.MUTATIONS` generically, so they cover the two new
entries automatically (section 12.1's own prediction, confirmed).

## Gates

All six green on the corrected entries: `uv sync --locked` rc=0;
`ruff check .` rc=0; `pytest` rc=0 — 728 passed (no test change);
`bot.py --selftest` rc=0; `bot.py --selftest-live` rc=0, all six OK;
`devtools/mutation_check.py` rc=0 — **67 mutations, 67 killed**, 0
survived/errored/drifted.
