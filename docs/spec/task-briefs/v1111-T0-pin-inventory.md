# v1111-T0 pin inventory

Built by grepping the live tree (base `2431034`, tag `v1.11.0`) per brief
`docs/spec/task-briefs/v1111-T0.md`, extending `REQ-V1111-PIN-01`
(`docs/spec/spec-v1.11.1.md:567-598`) and the eleven VER-01 sites
(`docs/spec/spec-v1.11.1.md:816-828`). Never copied from the spec text
verbatim — every literal below was re-read from the file:line named
(the eleven VER-01 sites landed within a line or two of the spec's own
citation, expected per `docs/spec/spec-v1.11.1.md:1040`'s "±5 lines").
Extension greps run tree-wide over `tests/` for each literal/constant
named below (`EMBED_BATCH_SIZE`, `Use /delete <filename>`, the `"f" * 23`
width, `report-v1.11.0.md`/`report_path`, `v1110-T<N>`, `as of
spec-v1.11.0 T8`, `2384`, `"1.11.0"`, `this release`, and `/documents`'/
`/model`'s width constants `[12, 44]`/`[16, 40]` per TAB-01/TAB-02) to
catch sites the spec's own list does not name — three such sites turned
up (rows 19-21 below).

| site (file:line) | literal | task that rewrites it | rewrite form |
|---|---|---|---|
| `tests/test_v1110_doc.py:200-202` | `truncated = "f" * 23 + "…"` / `assert tables.utf16_length(truncated) == 24` | T2 | in-place width literal, presence/contiguity |
| `tests/test_v1110_doc.py:378` | `monkeypatch.setattr(documents, "EMBED_BATCH_SIZE", 1)` | T2 | batch-size patch site, in place |
| `tests/test_v1110_ing.py:548` | `monkeypatch.setattr(documents, "EMBED_BATCH_SIZE", 1)` | T2 | batch-size patch site, in place |
| `tests/test_v190_agents.py:300` | `"Limit of 20 documents reached. Use /delete <filename>.",` (`DOC_LIMIT_REPLY`, `bot.py:109`) | T2 | string literal rewritten in place to the `/delete #<id>` form |
| `tests/test_v1110_ver.py:135` | `assert "documents.EMBED_BATCH_SIZE" in readme_text` | T2 | README batch-name pin, in place |
| `tests/test_v1110_mod.py:324` | `assert bot.utf16_length(inner) <= 4096` | none — checked, unaffected (generic Telegram 4096 cap, not a T2 width pin) | — |
| `tests/test_v1110_out.py` (width helpers, e.g. `:104-155`, `:188-219`, `:309-542`) | property-based random `max_width`; the file's own `"…"` literals (`:116`, `:219`, `:309`, `:337`, `:393`, `:542`) are the generic ellipsis/fit-lines marker, none pinned to T2's specific width value | none — checked, unaffected | — |
| `tests/test_v1110_ver.py:75-78` | `def test_t_v1110_ver_01_live_version_is_1_11_0(): ... live_version == "1.11.0"` | T6 | repointed exactly as `REQ-V1110-VER-01` repointed `test_v1104_version.py`: only the live read becomes `git show v1.11.0:pyproject.toml` == `"1.11.0"`, function/module unrenamed |
| `tests/test_v1110_ver.py:57` | `_MEASURED_TEST_COUNT = 2384` | T6 | count rewritten in place to the T6-measured post-edit figure |
| `tests/test_v1110_ver.py:106-112` (live content runs `:106-113`) | `assert f"{_MEASURED_TEST_COUNT}" in agents_text` / `"152 entries"` / `"as of spec-v1.11.0 T8"` in; `"2311"`, `"144 entries"`, `"as of spec-v1.10.4 T5"` not in | T6 | count + `as of spec-v1.11.1 T6` rewritten in place; the `not in` guards' retired figures follow |
| `tests/test_v190_agents.py:138-162` (`test_t_v1104_rpt_03_agents_md_count_lines_landed_at_t5`) | `assert "2384" in text` / `"152 entries"` / `"as of spec-v1.11.0 T8"` in; `"2311 tests as of spec-v1.10.4 T5"`, `"144 entries as of spec-v1.10.4 T5"` not in | T6 | T6's numbers and the one history sentence rewritten in place |
| `tests/test_v190_agents.py:92-99` (`test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104`) | `assert "docs/spec/task-briefs/v1110-T<N>.md" in text` / `"docs/spec/task-briefs/v1104-T<N>.md" not in text` | T6 | token rewritten to `v1111-T<N>.md` in place (function name stays, per PIN-01) |
| `tests/test_v1104_docs.py:141` | `assert "docs/spec/task-briefs/v1110-T<N>.md" in text` | T6 | token rewritten to `v1111-T<N>.md` in place |
| `tests/test_v1102_docs.py:167` | `assert "docs/spec/task-briefs/v1110-T<N>.md" in text` | T6 | token rewritten to `v1111-T<N>.md` in place |
| `tests/test_v190_agents.py:331-332` | `assert "report_path: docs/reports/report-v1.11.0.md" in text` / `"report_path: docs/reports/report-v1.10.4.md" not in text` | T6 | `report_path` value rewritten to `report-v1.11.1.md` in place |
| `tests/test_v170_bench.py:329` | `assert lint_docs["report_path"] == "docs/reports/report-v1.11.0.md"` | T6 | `report_path` value rewritten in place |
| `tests/test_v1102_gates.py:49` | `assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.11.0.md"` | T6 | `report_path` value rewritten in place |
| `tests/test_v1104_gates.py:212-216` | `:212` `assert lint_docs["report_path"] == "docs/reports/report-v1.11.0.md"`; `:215-216` `report = .../"report-v1.11.0.md"` / `checks._lint_report_delegation(report) == []` | T6 | `report_path` value rewritten in place, both occurrences |
| `tests/test_v1101_gates.py:259` | `assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.11.0.md"` | T6 (**found by extension, not in the spec's eleven-site list**) | same "report_path tracks the current release" family as the sites above; rewritten in place |
| `tests/test_v1103_gates.py:61` | `assert lint_docs["report_path"] == "docs/reports/report-v1.11.0.md"` | T6 (**found by extension, not in the spec's eleven-site list**) | same "report_path tracks the current release" family; rewritten in place |
| `tests/test_v1104_version.py:108` | `assert live_version == "1.11.0"` (`T-V1104-VER-02`'s own trailing live-tree literal; its docstring at `:8-13` already names this as a disclosed-amendment site, updated at each release bump: `"1.10.4"` → `"1.11.0"` at v1.11.0 T8) | T6 (**found by extension, not in the spec's eleven-site list**) | disclosed-amendment live-version literal rewritten to `"1.11.1"` in place; the property proved (a version delta from `f3ce1a5` exists) is unaffected |
| `tests/test_v1110_pin.py:100-120` | `err_01_needles` tuple, rows 1-17 (no `DOC_LIMIT_REPLY`/row-16 "Limit of 20 documents" string in this list) | none — checked, unaffected by T2's `DOC_LIMIT_REPLY` rewrite | — |
| `tests/test_v1110_err.py:119-199` (rows 10, 17) | row 10 `"❌ Interrupted by restart."`, row 17 `"Indexing is already finishing."` | none — checked, unaffected | — |
| `tests/test_v1110_ver.py:116-124` | `:116` `"\| v1.11.0 \| 1.11.0 \|"` present; `:121-124` the `v1.10.4` row lacks `"; this release"` | none — checked, both pins still true after VER-01's README rewrite (neither asserts `"; this release"` is present on the `v1.11.0` row) | — |
| `tests/test_v190_agents.py:285-306` | the other ERR-01 needles (every row except `:300`'s `DOC_LIMIT_REPLY`, already listed above) | none — checked, unaffected | — |
| `tests/test_v1110_inventory.py` (`_SPEC_TEST_FUNCTIONS`, `:44-106`, asserted at `:110`) | 61 `(module, function)` pairs, `assert len(_SPEC_TEST_FUNCTIONS) == 61` | none — recorded **unchanged**: no `v1110` test renamed, no `v1111` test added to it (`git diff v1.11.0 -- tests/test_v1110_inventory.py` empty) | — |

26 rows: 5 T2 rewrite sites, 2 checked-no-width-pin sites, 14 T6
`REQ-V1111-VER-01` pin sites (11 named by the spec's own list plus 3
found by tree-wide extension — `tests/test_v1101_gates.py:259` and
`tests/test_v1103_gates.py:61` (the same "report_path tracks the
current release" family as the four the spec already names) and
`tests/test_v1104_version.py:108` (VER-02's own trailing live-version
literal)), 4 checked-unaffected sites, 1 unchanged-inventory-list site.

**The spec's own text says "Eleven pin sites" (`docs/spec/spec-v1.11.1.md:816`);
this inventory found three more in the same rewrite family that
T6's brief (`v1111-T6.md`) will need, not just the eleven named.**

Tree-wide extension greps also checked `EMBED_BATCH_SIZE` and
`Use /delete <filename>` beyond the named sites: no further live-assertion
pin sites turned up (the only other hits are comments/docstrings at
`tests/test_v1110_doc.py:372`, `tests/test_v1110_ing.py:540`, and
non-test files `bot.py:109`, `README.md:993`, `documents.py:386-558`,
none of which are test-literal pins). The `/documents`/`/model` width
constants (`bot.py:1545`'s `[12, 44]` → `[16, 40]`, TAB-02) are not pinned
by any test as a raw literal list — checked, no additional width-pin site.
