# v1.11.0 T0 — frozen-pin inventory

Built by grepping the live tree at HEAD `c29d533` (spec cites `295b01f`).
Per REQ-V1110-PIN-01: rewrite form is **presence/contiguity/order**
(`README.md:918`), never frozen-equality, except where a row is a literal
string a test asserts verbatim (those are still presence/`==` checks on the
*string*, not on the surrounding matrix). Drift is reported as
`cited → actual` where the two differ.

## Pin table

| site (file:line) | literal | task that rewrites it | rewrite form |
|---|---|---|---|
| `bot.py:66` | `NEW_CONVERSATION_REPLY = "New conversation started."` | T3 (SES-03) | definition site — literal replaced |
| `tests/test_telegram.py:244` | `"New conversation started."` | T3 (SES-03) | exact-string assert on `tg.sent` |
| `tests/test_summary.py:190` | `"New conversation started."` | T3 (SES-03) | exact-string assert |
| `tests/test_summary.py:208` | `"New conversation started."` | T3 (SES-03) | exact-string assert |
| `tests/test_summary.py:244` | `"New conversation started."` | T3 (SES-03) | exact-string assert |
| `tests/test_v1100_red_team.py:680` | `"New conversation started."` | T3 (SES-03) | exact-string assert |
| `bot.py:71` | `MODEL_USAGE_REPLY = "Usage: /model [lmstudio|openrouter|auto]"` | T4 (MOD-03) | definition site — literal replaced |
| `tests/test_failover.py:243` | `"Usage: /model [lmstudio|openrouter|auto]"` | T4 (MOD-03) | exact-string assert on `tg.sent` |
| `bot.py:97` | `DELETE_USAGE_REPLY = "Usage: /delete <filename>"` | T2 (DOC-02) | definition site — literal replaced |
| `tests/test_v190_commands.py:629` | `bot.DELETE_USAGE_REPLY` via attribute (currently `"Usage: /delete <filename>"`) | T2 (DOC-02) | attribute-based assert — no source-string duplication to fix |
| `bot.py:82` | `DOC_TOO_LARGE_REPLY = "File too large (over 10 MiB)."` | T5 (ING-01) | definition site |
| `bot.py:88` | `DOC_TEXT_TOO_LARGE_REPLY = "Document too large (over 500,000 characters)."` | T5 (DOC-03) | definition site |
| `bot.py:94` | `DOC_BUDGET_EXCEEDED_REPLY = "Indexing timed out (over 300 s). Nothing was saved."` | T5 (ING-01/DOC-03) | definition site |
| `tests/test_v190_agents.py:258-280` (`test_t_v190_ec_01_readme_error_behaviour_table_gains_document_rows`) | the 15-item `exact_string` list incl. the three strings above | T5 (ING-01/DOC-03), extended by T5/VER-02 to 17 items | presence-in-section loop — already list-membership, not order; adding 2 items is additive |
| `README.md:863` | `` `File too large (over 10 MiB).` `` (error table) | T5 (ING-01) | table-row string, presence |
| `README.md:864` | `` `Document too large (over 500,000 characters).` `` | T5 (DOC-03) | table-row string, presence |
| `README.md:869` | `` `Indexing timed out (over 300 s). Nothing was saved.` `` | T5 (ING-01/DOC-03) | table-row string, presence |
| `README.md:828` | `10,485,760 bytes` (`DOCUMENT_MAX_BYTES`) | T5 (ING-01) — unchanged unless the byte ceiling itself moves; listed because it sits inside the block T5 touches | table-row string, presence |
| `README.md:829` | `500,000 characters` | T5 (DOC-03) | table-row string, presence |
| `README.md:831` | `300 s` (`INDEX_BUDGET_S_DEFAULT`) | T5 (ING-01) | table-row string, presence |
| `README.md:833` | `500 pages` | T5 (DOC-03) | table-row string, presence |
| `tests/test_v190_agents.py:238-256` (`test_t_v190_ec_01_readme_limits_table_gains_rag_rows`) | the `needle` list incl. `10,485,760`, `500,000`, `300 s`, `500 pages` | T5 | presence loop over the `## Limits` section |
| `README.md:511-516` | narrative sentence: "10 MiB upload, 500,000 extracted characters, ... 500-page PDF ceiling" | T5 | prose mirror of the Limits table — presence only, not asserted by a test found in this pass |
| — (new insertion, no current site) | `` `❌ Interrupted by restart.` `` — new **row 10** of README's error table | T5 (VER-02) | pure addition; not present anywhere in `README.md` or `bot.py` today (confirmed absent) — insert into `## Error behaviour` table (`README.md:839-873` today, 31 data+header rows) |
| — (new insertion, no current site) | `` `Indexing is already finishing.` `` — new **row 17** of README's error table | T5 (VER-02) | pure addition; same table, confirmed absent from the live tree |
| `tests/test_observability.py:889-896` (`test_obs07_stats_layout`) | 8 exact `/stats` line-shape strings (`"Stats (this conversation \| all time)"`, `"LLM calls: 2 \| 2 ..."`, etc.) | T2 (STA-01) | exact-line assertions on `text.splitlines()` — a new session-related line would need this to become presence/contiguity per PIN-01's rule, not `==` |
| `tests/test_observability.py:904-905` (`test_obs07_stats_reports_no_pricing`) | `"Est. cost: n/a (no pricing)"`, `"LLM calls: 2 \|"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:911` (`test_obs07_stats_basis_is_mixed_when_the_rows_disagree`) | `"(basis: mixed \| mixed)"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:917-921` (`test_obs07_stats_on_an_empty_database`) | `"LLM calls: 0 \| 0 (errors 0 \| 0)"`, `"Tokens in: n/a \| n/a"`, `"Est. cost: n/a (no pricing)"`, `"Top tools by output tokens (all time): none"`, `"Last turn: none"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:934-935` (`test_obs07_stats_separates_this_conversation_from_all_time`) | `"LLM calls: 2 \| 3 (errors 0 \| 1)"`, `"Tokens in: 6492 \| 7492"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:942` (`test_obs07_stats_reports_cached_and_reasoning_when_present`) | `"(cached: 128 \| 128, reasoning: 12 \| 12)"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:949` (`test_obs07_status_carries_the_token_line`) | `"Tokens this conversation: in 6492 / out 298"` | T2 (STA-01) | substring presence (`/status`, not `/stats`, but same token-line machinery) |
| `tests/test_observability.py:955` (`test_obs07_status_token_line_without_a_conversation`) | `"Tokens this conversation: in 0 / out 0"` | T2 (STA-01) | substring presence |
| `tests/test_observability.py:1124-1125` (`test_obs07_stats_drops_whole_lines_before_it_cuts_one`) | `"Stats (this conversation \| all time)"`, `"LLM calls: 1 \| 1"` (startswith) | T2 (STA-01) | line-0 exact + line-1 prefix |
| `tests/test_v160_observability.py:1236-1240` (`test_stats_gains_two_lines_appended`) | `"Stats (this conversation \| all time)"`, `"Errors: "`/`"Summaries: "` prefixes | T2 (STA-01) | line-0 exact + prefix/position (`lines[-2]`, `lines[-1]`) — position-based, will need care if T2 appends more lines |
| `tests/test_pricing.py:631-633` (`test_prc03_every_basis_form_is_stored_and_rendered`) | `f"Est. cost: $0.0123 \| $0.0123 (basis: {basis} \| {basis})"` via `bot._render_stats` | T2 (STA-01) | line found by `startswith("Est. cost:")`, then exact-match |
| `bot.py:1132` (`_render_stats`) | the `/stats` renderer itself | T2 (STA-01) | source function T2 edits |
| note | spec §12 states **43 pins total** rewritten by T2/STA-01 across these three files; this pass located 24 individual assertion sites (grouped into the 12 rows above) plus the renderer. The remainder are line-shape assertions this grep pass did not itemise one-by-one (e.g. further `/stats`-adjacent metrics assertions in `tests/test_v160_observability.py`'s `met_02`/`met_03` tests were checked and found to assert on `usage_by`/`cache_hit_share` return values, not on rendered `/stats` text, so they are **not** pins and are excluded here) | — | — |
| `bot.py:1483` | `f"Your documents ({len(rows)}):"` | T2 (DOC-01) | definition site (f-string) |
| `tests/test_v190_commands.py:592` | `reply.startswith("Your documents (2):")` | T2 (DOC-01) | prefix assert |
| `bot.py:221` | `payload = {"timeout": LONG_POLL_TIMEOUT_S, "allowed_updates": ["message"]}` | T4 (CBQ-01) | definition site |
| `tests/test_telegram.py:272` | `body == {"timeout": 50, "allowed_updates": ["message"], "offset": 41}` | T4 (CBQ-01) | dict-equality assert — CBQ-01 adds `"callback_query"` (or similar) to the list, so this becomes a set/contains check per PIN-01's rule, not `==` |
| `bot.py:1381` | `_TypingIndicator(tg, chat_id, ceiling_s=documents.INDEX_BUDGET_S_DEFAULT)` | T5 (ING-05) | definition site |
| `tests/test_v190_commands.py:503-527` (`test_t_v190_cmd_04_typing_indicator_ceiling_is_the_index_budget`) | `captured["ceiling_s"] == documents.INDEX_BUDGET_S_DEFAULT == 300.0` (line 526) | T5 (ING-05) | value equality against the (possibly renamed) budget constant |
| `tests/test_v190_agents.py:226-235` (`test_t_v190_ec_01_readme_commands_table_gains_documents_and_delete`) | README commands-order: `/reload_skills` index `<` `/documents` index, both present between `## Commands` and `## Observability` | T6 (EXT-01) | presence + order (`section.index(a) < section.index(b)`) — already PIN-01-compliant |
| `tests/test_v190_agents.py:134-155` (`test_t_v1104_rpt_03_agents_md_count_lines_landed_at_t5`) | `AGENTS.md` `"2311"`, `"144 entries"`, `"as of spec-v1.10.4 T5"` | T8 (VER-01) — **rewritten in place under its existing function name**, not renamed | substring presence, plus a negative substring check (old figure absent) |
| `config/quality_gates.yaml:790` | `report_path: docs/reports/report-v1.10.4.md` | T6 (VER-03) | key-value line, presence |
| `tests/test_v170_bench.py:316-332` (`test_t_v1103_rpt_01_lint_docs_repointed_to_this_release`) | `lint_docs["report_path"] == "docs/reports/report-v1.10.4.md"` | T6 (VER-03) — renamed, see rename mapping | value equality against the config; the assert itself stays `==` (it's checking config keys, not a narrative order) |
| `tests/test_v1104_gates.py:206-213` (`test_t_v1104_rpt_01_lint_docs_config_and_own_report_are_green`) | `lint_docs["report_path"] == "docs/reports/report-v1.10.4.md"` + `report = .../report-v1.10.4.md` path | T6 (VER-03) — renamed, see rename mapping | value equality + a real filesystem path built from the literal |
| `tests/test_v190_agents.py:290-303` (`test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path`) — **disclosed amendment, not in the brief's starting list** | `"report_path: docs/reports/report-v1.10.4.md" in text` / `"report_path: docs/reports/report-v1.10.3.md" not in text` | T6 (VER-03) | third report_path pin site found by this grep pass; same repoint as the two above, function name is **not** renamed (the comment at line 299 says the name is deliberately left stable across releases) |
| `tests/test_v15_standards.py:1823` (cited `1824`, drift 1 line) | reads `docs/spec/spec-v1.10.4.md` to parse the gate-profile matrix | T6 (REV-02) | source-file-name literal inside `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` — becomes `spec-v1.11.0.md` |
| `docs/spec/spec-v1.md:135` | `"exactly five commands exist: /new, /status, /summary, /model, /reload_skills"` | docs only — **not edited** by v1.11.0 (spec-v1.md is a historical/superseded document) | N/A — noted per PIN-01, no rewrite |
| `tests/test_v1_guardrails.py:1320-1321` (`test_t_v1_cmd_01_status`) | `"Provider: lmstudio (override: none)"`, `"Provider failures: lmstudio=0, openrouter=0"` | **unchanged** — this is `/status`'s Provider line, not `/model`'s; no literal `/model` reply string was found anywhere in `test_v1_guardrails.py` (only `for text in ("/status", "/summary", "/model", ...)` dispatch-reachability at line 1376, which asserts no reply reaches an intruder, not a reply string) — listed to record that the file was checked, per the brief's instruction | checked, not rewritten |
| `tests/test_failover.py:219` | `"Provider: lmstudio (override: none, failures: lmstudio=0, openrouter=0)"` | unchanged | checked, not rewritten |
| `tests/test_failover.py:223` | `"Provider switched to openrouter."` | unchanged | checked, not rewritten |
| `tests/test_failover.py:234` | `"Provider: openrouter (override: openrouter, failures: lmstudio=0, openrouter=2)"` | unchanged | checked, not rewritten |

**Measurements (cited by command, not re-run — orchestrator's already-measured values):**

| measurement | value | source command |
|---|---|---|
| `len(MUTATIONS)` in `devtools/mutation_check.py` | `144` | confirmed independently in this pass via `"id":` key count in `devtools/mutation_check.py` = 144 |
| the v190 `find` string `    if isinstance(file_size, int) and file_size > DOCUMENT_MAX_BYTES:` in `bot.py` | occurs exactly once, at `bot.py:1355` | confirmed independently in this pass via `grep -c` |
| baseline node-id list | `docs/spec/task-briefs/v1110-T0-nodeids.txt`, 2311 lines | confirmed independently in this pass via `wc -l` |
| `bot_state` override count | `0` | cited from the orchestrator's measurement, not re-derived (the brief instructs citing this, not re-running gates; `storage.py:267` is `bot_state`'s `CREATE TABLE`, `PROVIDER_OVERRIDE_KEY` is the relevant key) |

## Rename mapping

| old node id | new node id |
|---|---|
| `tests/test_v170_bench.py::test_t_v1103_rpt_01_lint_docs_repointed_to_this_release` | `tests/test_v170_bench.py::test_t_v1110_rpt_01_lint_docs_repointed_to_this_release` |
| `tests/test_v1104_gates.py::test_t_v1104_rpt_01_lint_docs_config_and_own_report_are_green` | `tests/test_v1104_gates.py::test_t_v1110_rpt_01_lint_docs_config_and_own_report_are_green` |

Both renames follow the `…_v1110_rpt_01…` form the spec names at `spec-v1.11.0.md:1299-1300`;
the new function names above substitute the `v1103`/`v1104` segment for `v1110`
and keep the rest of each descriptive suffix unchanged, since the spec gives
the pattern but not the literal target names (the rename itself is T6's, not
yet applied at HEAD `c29d533`).

**Not in the rename mapping** (per spec's explicit carve-out,
`spec-v1.11.0.md:1301-1302`): `tests/test_v190_agents.py`'s
`test_t_v1104_rpt_03_agents_md_count_lines_landed_at_t5` (lines 134-155) is
rewritten in place under its existing name by T8 (VER-01).

## Drift summary

Comparing every spec-cited `file:line` (baseline `295b01f`) against the live
tree at `c29d533`: **no drift exceeding 5 lines was found.** One 1-line drift:
`tests/test_v15_standards.py` — spec cites `:1824`, the actual
`def test_v15_gate_04_profile_matrix_agrees_with_the_spec_table():` is at
`:1823`. Every other cited site (`tests/test_v190_agents.py:238-280`,
`README.md:828-833`, `README.md:863-864`, `README.md:511-517`,
`tests/test_v190_commands.py:592`, `tests/test_telegram.py:272`,
`tests/test_v190_commands.py:503`, `tests/test_v190_agents.py:226-235`,
`tests/test_v190_agents.py:134-152`, `tests/test_v170_bench.py:316-331`,
`tests/test_v1104_gates.py:206-215`, `spec-v1.md:135`) matched exactly or
fell fully inside the cited range.

## Amendments disclosed by this pass (not in the brief's starting list)

1. `tests/test_v190_agents.py:290-303` — a third `report_path` pin site
   (`test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path`), same
   `docs/reports/report-v1.10.4.md` value as the two VER-03-named sites, same
   task (T6, VER-03). Not renamed (function name is deliberately stable
   across releases per its own docstring).
2. `README.md:828`, `:831` and the prose sentence at `:511-516` — these sit
   inside the block T5 (ING-01) touches but are the *unchanged-unless-the-
   ceiling-moves* numbers (`10,485,760`, `300 s`) rather than the two numbers
   the spec's own list names (`500,000`, `500 pages`); included for
   completeness since a careless edit to the surrounding table would put them
   at risk.
3. `bot.py:1132` (`_render_stats`) and `bot.py:221`/`:1381`/`:1483` — the
   four source-side definition sites behind DOC-01/CBQ-01/ING-05/STA-01's
   test pins, added so the inventory names both the source and the test for
   every literal, not just the test.
