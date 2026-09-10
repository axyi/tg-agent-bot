# Task brief — v1.8.0 T2 erratum 1 (EC-03 amendment-list gap, operator-authorized)

`docs/spec/spec-v1.8.0.md` REQ-V180-EC-03 lists four exhaustive test-amendment
sites. T2 (commit `30d76b4`) implemented REQ-V180-CHAT-02 (delete-on-success,
`STATUS_DONE` removed) and REQ-V180-CHAT-04 (the production call site moves
to `agent.run_agent_outcome`) exactly as those MUSTs require, and this
structurally breaks two **pre-existing** tests the four-site list omitted.
Full `pytest` on T2's tree: 1161 passed, 2 failed, 1 skipped (unrelated).
The operator was asked and **authorized extending the amendment list by
two sites** — this is not an implementation defect, it is a disclosed spec
erratum. Do not touch anything else; do not re-open T2's design.

## The two amendments, exact and scoped

1. **`tests/test_pricing.py::test_prc02_the_resolver_reaches_run_agent`** —
   currently monkeypatches `agent.run_agent`; the production call site now
   correctly calls `agent.run_agent_outcome` (REQ-V180-CHAT-04, `bot.py`'s
   call site). Patch `agent.run_agent_outcome` instead of `agent.run_agent`;
   the fake should return `agent.AgentOutcome(reply="ok", failed=False,
   kind=None)` (or equivalent matching whatever the test actually needs from
   the resolver path — read the test first). Read the test fully before
   editing (it's one test function); do not touch anything else in that
   file.

2. **`tests/test_v1_guardrails.py::test_t_v1_vis_01_status_message`** (around
   line 1063) — asserts the last status edit is `"✅ done"`, the exact text
   REQ-V180-CHAT-02 replaces with delete-on-success. Its `RecordingTelegram`
   fake (around lines 76-93) needs a `deleted` list and a `delete_message`
   method, matching the shape `_SelftestTelegram`/`_FakeSelftestTg` already
   use elsewhere in this run (`bot.py:1118-1134`,
   `tests/test_v12_patch.py:141-146` — grep those for the exact shape to
   mirror). The assertion at line ~1063 becomes a deletion assertion instead
   of an edit-to-`"✅ done"` assertion — work out the exact expected message
   id from `RecordingTelegram.send_message`'s own numbering scheme (read the
   fake first) the same way `_SelftestTelegram`'s does (`{"message_id": 1}`
   for the status send). Read the test and its fake fully before editing;
   do not touch anything else in that file.

## Constraints

- Only these two test files, only the sites described. No source file
  changes — `bot.py`/`agent.py` from T2 are correct and final; this is a
  test-only follow-up.
- No file outside this repository is read or written (EC-01).
- Conventional commit `test:`. Header ≤ 72 Unicode characters, no trailing
  period. Body references
  `(prompt: docs/prompts/130-v180-t2-erratum-1-test-amendment.md)`. End the
  commit message with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FnGubtn2ec8m9fan73tGzZ
  ```
- Write your own prompt file first at
  `docs/prompts/130-v180-t2-erratum-1-test-amendment.md` using
  `docs/prompts/TEMPLATE.md`'s exact shape; note in `## Goal` that this is
  an operator-authorized erratum to REQ-V180-EC-03's amendment list, not a
  new spec task. Commit it together with the two test edits.
- Run the **whole** `uv run --locked pytest` suite and `uv run --locked
  ruff check .` before returning. Every test must pass (no skips beyond the
  one pre-existing unrelated skip already known: `test_v170_bench.py:553`).

## Report back

A summary only: the two diffs (`file:line`), the commit sha, and the final
full-suite pass count. Do not paste full file contents back.
