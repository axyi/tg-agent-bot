# v1.9.2 T2 — clean-context review findings to close (prompt 170, one commit)

Review of `92b667c` + `c3a38ea` + `260c7e1`. Reproduced clean: shrink counts
(1598, 1598); killer test kills on counts; tiers match §2.1 for four entries;
`-x -n 0` stops at first failure; two false-kill orderings exit 0; xdist ×2
exit 0 with an empty `git status`; grace/fixture changes preserve the
properties under test; `pytest-xdist` 3.8.0 is PyPI's latest. No 🔴. Two 🟠
are real defects in the new runner and the new timeouts; close everything
below in **one commit**, `fix: mutation runner shrink guard fails closed,
survivor-safe gate timeouts (v1.9.2 T2 review)`, prompt
`docs/prompts/170-v192-t2-review-findings.md`, `docs/llm-usage.md` row 80.

1. 🟠 **Shrink guard fails open.** `devtools/mutation_check.py:1420-1435`
   `_collect_count` sums `path: N` lines that pytest prints only at
   verbosity −2 (`addopts` `-q` plus argv `-q`); with a single `-q` the
   regex sums to 0, `completed.returncode` is never read, so a collection
   error or a verbosity change gives 0 == 0 and the guard passes vacuously.
   Fix: pass `-qq` explicitly on both collect invocations (do not rely on
   `addopts`), require `returncode == 0`, require both counts `> 0`, and
   fail loudly naming which condition failed. Fix the docstring at `:1425`
   (the format belongs to `-qq`, not "this pytest version"). Add a unit
   test for the zero/zero and non-zero-returncode cases and one mutation
   entry `v192-mutation-order-shrink-zero-accepted` (drop the `> 0`
   condition) that the test kills; `--only` it.
2. 🟠 **Three mutation timeouts cannot report a survivor.**
   `config/quality_gates.yaml` `mutation-v15` 30 s, `mutation-v170` 60 s,
   `mutation-v190` 50 s are below one single-process suite run (~69 s,
   `-n 0`). A surviving mutation runs the whole suite, the gate wall
   passes the timeout, `devtools/checks.py:1104-1110` SIGKILLs
   `mutation_check.py` (which traps only SIGINT/SIGTERM, `:1490-1491`), and
   the mutated file stays on disk with no survivor id. Fix the sizing rule
   for mutation gates and write it in the comment block once, above the
   first mutation gate: `timeout = 2 × measured killed-path wall + one
   full single-process suite run (70 s, measured), rounded up to 10 s` —
   then re-size all five subsets and check `mutation-all` under the same
   rule (its measured value is T3's; leave the number, add the note that
   T2 did not re-measure it and that the rule applies at T3). The SIGKILL
   hazard itself is pre-existing runner behaviour: note it in the report
   as a v1.10.0 item, do not change `checks.py` here.
3. 🟠 Report `docs/reports/report-v1.9.2.md:549` says "No count-bearing /
   version-pin test needed repointing". `AGENTS.md:160` (1593 tests),
   `:169` (108 entries) and `tests/test_v190_agents.py:139-140` pin figures
   the tree has moved past (1598 / 109). Reword: "stale count-bearing lines
   at … — deferred to T3's version-bump commit, which owns them".
4. 🟡 `quality_gates.yaml` `mutation-all` comment (`:423-438`): add the
   "not re-measured in T2; T3 measures under the rule above" line.
5. 🟡 `pytest` gate comment (`:146-152`): the 60 s is 2× a `-n auto` run on
   the 16-core operator box; say "this box, 16 cores; serial run 70 s;
   4 workers 26.9 s" so a smaller runner's operator knows what to re-measure.
6. 🟡 **Ordering misses common import shapes** (performance only, but it
   decides the `mutation-all` projection: 34 `v13-` entries are mostly
   `devtools/bench.py`, and tier 3 is empty for every bench entry).
   `_imports` (`:1358-1361`) does not match `from devtools import bench`,
   `from llm import …`, or indented imports; `llm/__init__.py` maps to
   `llm.__init__`; tier 4 scans only top-level `*.py` (`:1401`). Fix:
   match `from <pkg> import <mod>` and indented imports; map
   `pkg/__init__.py` to `pkg`; scan `llm/` and `devtools/` in tier 4.
   Re-print the tiers for `v13-bench-gate-threshold` and one `llm/` entry
   in the report, and re-measure `--select v13-` once (alone) to replace
   the projection with a number.
7. 🟡 `_shrink_counts()` (`:1588`) runs before the unknown-id / empty-prefix
   checks (`:1600`, `:1607`); move it after them so `--only typo` fails
   instantly as before.
8. 🟡 Report duplicates section (`:517-538`): scans (b) and (c) have no
   command; add the commands or scripts you ran so the "0 removed" is
   reproducible.

Acceptance, sequential, nothing concurrent: `ruff check .` 0; `ruff format
--check .` 0; `pytest` 0 (report collected count — it grows by the new
tests); `checks.py lint-docs` 0; drift script all entries (110); `--only
v192-mutation-order-shrink-zero-accepted` killed; `--only
v192-mutation-order-shrink-unchecked` killed; `--select v13-` killed n/n with
wall; `--select v15-` killed 4/4 with wall. Return the commit hash, the exit
codes, and the two `--select` walls only.
