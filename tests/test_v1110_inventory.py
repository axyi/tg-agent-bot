"""spec-v1.11.0 T8 (REQ-V1110-EC-03 (a), `T-V1110-INV-01`): the frozen
spec-test inventory.

Section 11.3's test table names "Sixty-two test ids, each naming its
`module::function`" -- the 62nd is `T-V1110-INV-01` itself (this file's
own `test_every_spec_test_function_exists`), whose own row reads "the
frozen list of the sixty-one other `module::function` pairs of this
table" (`docs/spec/spec-v1.11.0.md:1284`). "Of this table" spans every
other row, including `T-V1110-VER-01..04` (`tests/test_v1110_ver.py`,
also landed at T8, in this same commit) -- so `_SPEC_TEST_FUNCTIONS`
below holds 57 pairs from T1 through T7's own `tests/test_v1110_<group>.py`
files plus the 4 `T-V1110-VER-*` pairs T8 itself adds, 61 total, none of
them this file's own function (which would make it 62 and self-
referential).

Built mechanically, not by hand: `sed -n '1223,1283p'
docs/spec/spec-v1.11.0.md | grep -o
'tests/test_v1110_[a-z]*\\.py::test_t_v1110_[a-z0-9_]*'` over the table's
own OUT-01..ERR-01 rows (INV-01's own row, 1284, is outside that range) --
61 lines, no duplicates, and every one of the 57 non-VER pairs already
exists in the landed `tests/test_v1110_<group>.py` files this task found
at T8 (T1-T7 landed several more test functions than the table names --
extra sub-variants and regression coverage beyond the frozen list, e.g.
`tests/test_v1110_ing.py`'s `test_t_v1110_ing_07_worker_maps_stream_*`
pair and `test_t_v1110_ing_12/13_*`, `tests/test_v1110_err.py`'s second
`err_01_row_10_*` function -- none of those extras are in this frozen
list, since the table names one canonical function per `T-V1110-*` id,
not every test function that happens to exist).

Structural regression check (EC-02 carve-out): may be green on first
execution.

Offline: `importlib.import_module` + `hasattr` only, no network, no live
LLM.
"""

from __future__ import annotations

import importlib

# The 61 other `module::function` pairs of docs/spec/spec-v1.11.0.md's
# §11.3 table (T-V1110-OUT-01 through T-V1110-ERR-01, in the table's own
# order; T-V1110-INV-01, this file's own row, is not in this list).
_SPEC_TEST_FUNCTIONS: list[tuple[str, str]] = [
    ("tests.test_v1110_out", "test_t_v1110_out_01_render_table_properties_and_width_ceiling"),
    ("tests.test_v1110_out", "test_t_v1110_out_02_send_pre_payload_and_escape"),
    ("tests.test_v1110_out", "test_t_v1110_out_03_redact_before_escape"),
    ("tests.test_v1110_out", "test_t_v1110_out_04_fit_lines_at_4096_units"),
    ("tests.test_v1110_out", "test_t_v1110_out_05_plain_fallback_once_on_400"),
    ("tests.test_v1110_out", "test_t_v1110_out_06_agent_reply_path_unchanged"),
    ("tests.test_v1110_out", "test_t_v1110_out_07_fake_telegram_grows_compatibly"),
    ("tests.test_v1110_out", "test_t_v1110_out_08_edit_pre_hostile_and_4097_unit_bodies"),
    ("tests.test_v1110_sta", "test_t_v1110_sta_01_stats_table_labels_and_cells"),
    ("tests.test_v1110_sta", "test_t_v1110_sta_02_stats_fit_drops_whole_lines"),
    ("tests.test_v1110_sta", "test_t_v1110_sta_03_readme_stats_sample_labels"),
    ("tests.test_v1110_doc", "test_t_v1110_doc_01_documents_table"),
    ("tests.test_v1110_doc", "test_t_v1110_doc_02_documents_empty_reply_plain"),
    ("tests.test_v1110_doc", "test_t_v1110_doc_03_delete_by_id_owner_scoped"),
    ("tests.test_v1110_doc", "test_t_v1110_doc_04_refusal_wording_split"),
    ("tests.test_v1110_doc", "test_t_v1110_doc_05_inflight_line_after_table"),
    ("tests.test_v1110_ses", "test_t_v1110_ses_01_list_conversations_and_schema_6"),
    ("tests.test_v1110_ses", "test_t_v1110_ses_02_activate_conversation_ownership"),
    ("tests.test_v1110_ses", "test_t_v1110_ses_03_sessions_table"),
    ("tests.test_v1110_ses", "test_t_v1110_ses_04_session_switch_and_context"),
    ("tests.test_v1110_ses", "test_t_v1110_ses_05_new_reply_names_id"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_01_allowed_updates_and_callback_branch"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_02_intruder_callback_one_ack"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_03_callback_guards_and_cursor"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_04_ack_once_first"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_05_stale_and_malformed_data"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_06_client_methods_and_same_message_edit"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_07_callback_data_grammar_and_64_bytes"),
    ("tests.test_v1110_cbq", "test_t_v1110_cbq_08_callback_edits_ride_edit_pre"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_01_model_step_one"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_02_model_step_two_sets_two_keys"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_03_auto_clears_both"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_04_model_text_form"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_05_catalogue_from_env"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_06_override_reaches_client"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_07_catalogue_bounded_at_20"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_08_reordered_catalogue_is_stale"),
    ("tests.test_v1110_mod", "test_t_v1110_mod_09_display_form_in_rows_and_buttons"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_01_caps_and_find_line"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_02_worker_split_and_thread_owned_connection"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_03_second_upload_refused"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_04_queue_full"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_05_cancel_mid_embedding"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_06_queued_cancel_no_getfile"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_07_cancel_during_download"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_08_connect_failure_releases_slot"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_09_cancel_in_commit_phase"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_10_reservation_race_before_status_send"),
    ("tests.test_v1110_ing", "test_t_v1110_ing_11_shutdown_drains_queued_jobs"),
    ("tests.test_v1110_ext", "test_t_v1110_ext_01_commands_table_and_setmycommands"),
    ("tests.test_v1110_ext", "test_t_v1110_ext_02_help_and_start"),
    ("tests.test_v1110_ext", "test_t_v1110_ext_03_readme_commands_rows"),
    ("tests.test_v1110_pin", "test_t_v1110_pin_01_no_retired_literal_in_tests"),
    ("tests.test_v1110_pin", "test_t_v1110_pin_02_readme_limits_and_error_rows"),
    ("tests.test_v1110_mut", "test_t_v1110_mut_01_eight_entries_in_mutations"),
    ("tests.test_v1110_ver", "test_t_v1110_ver_01_live_version_is_1_11_0"),
    ("tests.test_v1110_ver", "test_t_v1110_ver_02_dependency_diff_version_only"),
    ("tests.test_v1110_ver", "test_t_v1110_ver_03_agents_md_and_release_row"),
    ("tests.test_v1110_ver", "test_t_v1110_ver_04_readme_deliverables"),
    ("tests.test_v1110_sec", "test_t_v1110_sec_01_nothing_new_executed_written_reached_or_leaked"),
    ("tests.test_v1110_err", "test_t_v1110_err_01_error_matrix_strings"),
]


def test_every_spec_test_function_exists():
    assert len(_SPEC_TEST_FUNCTIONS) == 61
    # EC-03(a): no duplicate function name.
    assert len({func for _mod, func in _SPEC_TEST_FUNCTIONS}) == 61

    for module_name, function_name in _SPEC_TEST_FUNCTIONS:
        module = importlib.import_module(module_name)
        assert hasattr(module, function_name), f"missing spec test: {module_name}::{function_name}"
