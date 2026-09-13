# v1.9.4 T1–T4 — clean-context review findings to close (prompt 186, one commit)

Review of `505bbf7` `b5db300` `4667d16` `4253678` `fcb7ec8` (opus, clean
context; every probe re-run; six `--only` kills; one instrumented gate-7
run on the `gpt-4o-mini` route). No 🔴. The T2 measurement conclusion is
**confirmed**: the eval-chat route sends `tools=4`, `tool_choice=auto`,
identical budgets; `gpt-4o-mini` answers turn 1 from general knowledge
(«Согласно Трудовому кодексу … 28 календарных дней …») with
`search_documents` in front of it. That is a prompt/tool-description
observation for v1.10 (the system prompt does not compel a document search
when documents exist), not a route defect. One 🟠 and six 🟡 below — close
in **one commit** `fix: rag_eval logs at WARNING; smoke turn 3 checks
evidence; review paperwork (v1.9.4)`, prompt
`docs/prompts/186-v194-review-findings.md`, llm-usage row 96. Do not
rewrite the five commits.

1. 🟠 `devtools/rag_eval.py:597-602` — the new root logging setup uses
   `setLevel(logging.INFO)`; before T1 root was WARNING (lastResort), so
   gate 7 now emits ~88 INFO lines per run (`httpx` POSTs, `storage
   llm_call` rows) on stderr, and `checks.py`'s five-line stderr tail on a
   failing gate becomes INFO noise. Set `WARNING` — the brief asked for
   gate 7's *warnings* to be redacted, nothing more. Test: the per-entry-
   point test for `rag_eval` asserts the level too.
2. 🟡 `config.py:225` — `super().format()` caches the **unredacted**
   traceback in `record.exc_text`; a second handler on the same record
   without the redacting formatter would emit it raw (latent: every entry
   point installs exactly one handler). Close it: after rendering, set
   `record.exc_text` to the redacted `formatException` output (or `None`
   so a later formatter re-renders — then it must also redact, so prefer
   storing the redacted text). Extend the chained-exception test: two
   handlers on one logger, the second with a plain `Formatter` — the
   second's output must still be masked because the cached text is.
3. 🟡 `devtools/rag_eval.py:440-443` — turn 3's matcher is filename-only
   while the scored path's `first_hit` (`:293-304`) needs filename **and**
   `contains_evidence`; and turn 3's gold file equals turn 1's, so any
   vacation-related search passes — the verdict proves "found the vacation
   policy", not "carried the context to the *transfer* rule". Tighten:
   reuse the scored path's matcher (filename + `expected_evidence` «не
   более 10 дней» of `questions.json` item 1) so the passage that answers
   the *follow-up* must be among turn 3's returned passages. Update the
   three offline cases (the "miss" case: right file, wrong passage → fail
   naming the sources) and the mutation entry's `find` if the line moved;
   `--only v194-smoke-turn3-gold-unchecked` killed. State in the report
   what the verdict now proves and what it still does not (a query that
   names the transfer rule without using turn 1's context would also
   pass — the TOOL-06 pin covers context carry, turn 3 covers "went to
   the documents for the new fact").
4. 🟡 Report Cost paragraph (`report-v1.9.4.md:242-253`): tally the
   addendum's C1/C2 paid calls (the reviewer's C1 repeat: 1579 prompt /
   136 completion tokens on `gpt-4o-mini`) and fix "All five runs'" to the
   actual run count.
5. 🟡 `docs/llm-usage.md:238` row 94: "`PTH*` (19 hits" → 18 PTH + 1
   RUF043 = 19 total.
6. 🟡 T3 acceptance `--select v15-` killed 4/4 with wall is recorded
   nowhere: run it once (alone) and record the wall in the report's T3
   section and prompt 183's acceptance line via the report (do not amend
   the commit).
7. 🟡 Gate-7 wall attribution (report T2, `config/quality_gates.yaml:229-241`):
   the growth 268 → 557 s is attributed to the third turn, but the report's
   own per-turn table shows turns 1+2 went 253 s (v1.9.3) → 386–394 s;
   turn 3 is ~150 s of the delta. Name the remaining ~140 s honestly as
   what the D1/D2 rows suggest — LM Studio unloading the chat model when
   the embedding model is called between turns (the local 9B showed no
   JIT speed-up on its repeat) — as a **hypothesis with the numbers**, not
   a finding, and list "measure LM Studio model swaps during gate 7" as a
   v1.10 item. Prompt 185 says "sixteen-row table"; it has 9 rows — fix.
8. 🟡 The gpt-4o-mini observation above goes into the report's T2 section
   as a v1.10 candidate: "the agent's system prompt / `search_documents`
   description does not compel a document search for a user who has
   documents; a general-knowledge model answers the vacation question from
   the Labour Code" — with the quoted 200 chars.

After any amend or added commit, re-read every place a count or hash is
named. Acceptance, sequential, nothing concurrent: `ruff check .` 0;
`ruff format --check .` 0; `pytest` 0 (collected count); `bot.py --selftest`
0; `checks.py lint-docs` 0; drift 119/119; `--only
v194-smoke-turn3-gold-unchecked` killed; `--only
v194-redacting-formatter-skips-redact` killed; `--select v15-` 4/4 with
wall; gate 7 on the production route once (alone), exit 0, both smoke
lines and the wall recorded. Return the commit hash, exit codes, the two
walls only.
