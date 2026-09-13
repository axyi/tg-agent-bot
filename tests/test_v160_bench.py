"""The tool-call ceiling -- spec-v1.6.0 section 10 (REQ-V160-TQ-05..07) -- and
`bench_schema` 2, the locked instrument -- spec-v1.6.0 section 11
(REQ-V160-BEN-03..05).

T10's own tests: the `tool_calls_max` check kind and factory, the six new
scenarios S13...S18 appended to `SCENARIOS`, and the catalogue's new
tool-call-ceiling validation rule.

T11's own tests (this file's final section): `BENCH_SCHEMA = 2` and
`runs[].spans`, `_validate`'s `mode` parameter and the `check`/`report`/
`report --gate` split, the six new locked `meta` instrument fields, the
`baseline-*` dirty-tree refusal, and the bench.py:1420-1422 report-text fix.

Offline, deterministic, no Docker, no network, no live LLM calls -- this
module never runs a scenario against a real model (the spans section drives
`run_bench` with the same fakes `tests/test_bench.py` already uses), only
inspects the catalogue, the check evaluator and the documents themselves.
"""

from __future__ import annotations

import argparse
import json

import pytest

import storage
from devtools import bench, bench_scenarios
from devtools.bench_scenarios import SCENARIOS, Scenario, tool_calls_max, tool_used
from tests.test_bench import (
    CANDIDATE_FLAGS,
    TG_ID,
    _stub_cli,
    _write,
    fake_doc,
    fake_run,
    llm_row,
    make_config,
    run_kwargs,
    tool_row,
)


def _scenario(checks: list) -> Scenario:
    return Scenario(id="TX", title="t", turns=["вопрос"], checks=list(checks))


# --------------------------------------------------------------------------
# the factory and the kind (REQ-V160-TQ-06)
# --------------------------------------------------------------------------


def test_tool_calls_max_rejects_a_non_positive_n():
    with pytest.raises(ValueError):
        tool_calls_max(0)
    with pytest.raises(ValueError):
        tool_calls_max(-1)


def test_tool_calls_max_is_a_valid_kind_but_not_an_answer_kind():
    assert bench_scenarios.TOOL_CALLS_MAX in bench_scenarios.KINDS
    assert bench_scenarios.TOOL_CALLS_MAX not in bench_scenarios.ANSWER_KINDS


def test_tool_calls_max_check_carries_no_turn_and_the_given_ceiling():
    check = tool_calls_max(3)
    assert check.kind == bench_scenarios.TOOL_CALLS_MAX
    assert check.turn is None
    assert check.max_calls == 3
    # A scenario accepts it with no turn: Scenario.__post_init__ needed no
    # change (REQ-V160-TQ-06's third point).
    _scenario([check])


def test_max_calls_is_additive_and_defaults_to_zero_on_every_other_kind():
    assert tool_used("exec").max_calls == 0
    assert bench_scenarios.answer_regex("x").max_calls == 0


# --------------------------------------------------------------------------
# evaluation (REQ-V160-TQ-06's fourth point) -- lives in bench.py
# --------------------------------------------------------------------------


def test_tool_calls_max_check_passes_exactly_at_the_ceiling():
    scenario = _scenario([tool_calls_max(3)])
    obs = bench.Observation(answers=["ok"], tool_rows=[tool_row(i) for i in range(1, 4)])
    result = bench.evaluate_checks(scenario, obs)[0]
    assert result == {"kind": "tool_calls_max", "ok": True, "detail": "ok"}


def test_tool_calls_max_check_fails_one_call_over_the_ceiling():
    scenario = _scenario([tool_calls_max(3)])
    obs = bench.Observation(answers=["ok"], tool_rows=[tool_row(i) for i in range(1, 5)])
    result = bench.evaluate_checks(scenario, obs)[0]
    assert result["ok"] is False
    assert result["detail"] == "4 tool call(s) > max 3"


def test_tool_calls_max_counts_rejected_and_refused_repeat_rows_too():
    """REQ-V160-TQ-06: every outcome is counted, `rejected` and
    `refused_repeat` among them -- not only `ok`/`error`."""
    scenario = _scenario([tool_calls_max(2)])
    rows = [
        tool_row(1, tool="exec"),
        {**tool_row(2, tool="exec"), "outcome": "rejected"},
        {**tool_row(3, tool="exec"), "outcome": "refused_repeat"},
    ]
    obs = bench.Observation(answers=["ok"], tool_rows=rows)
    result = bench.evaluate_checks(scenario, obs)[0]
    assert result["ok"] is False
    assert result["detail"] == "3 tool call(s) > max 2"


def test_tool_calls_max_at_zero_tool_calls_still_passes_a_positive_ceiling():
    scenario = _scenario([tool_calls_max(1)])
    obs = bench.Observation(answers=["ok"], tool_rows=[])
    assert bench.evaluate_checks(scenario, obs)[0]["ok"] is True


# --------------------------------------------------------------------------
# catalogue self-validation (REQ-V160-TQ-07)
# --------------------------------------------------------------------------


def test_validate_catalog_rejects_a_ceiling_below_the_distinct_tool_used_count():
    bad = Scenario(
        id="TBAD",
        title="t",
        turns=["вопрос"],
        checks=[tool_used("exec"), tool_used("fetch"), tool_calls_max(1)],
    )
    with pytest.raises(ValueError, match="tool_calls_max"):
        bench_scenarios._validate_catalog([bad])


def test_validate_catalog_accepts_a_ceiling_at_or_above_the_distinct_tool_used_count():
    exact = Scenario(
        id="TOK1",
        title="t",
        turns=["вопрос"],
        checks=[tool_used("exec"), tool_used("fetch"), tool_calls_max(2)],
    )
    above = Scenario(
        id="TOK2",
        title="t",
        turns=["вопрос"],
        checks=[tool_used("exec"), tool_used("fetch"), tool_calls_max(5)],
    )
    bench_scenarios._validate_catalog([exact, above])  # must not raise


def test_validate_catalog_counts_distinct_tools_not_repeated_checks():
    # Two `tool_used("exec")` checks name one distinct tool, so ceiling 1 is
    # sufficient even though there are two `tool_used` checks.
    repeated = Scenario(
        id="TREP",
        title="t",
        turns=["вопрос"],
        checks=[tool_used("exec"), tool_used("exec"), tool_calls_max(1)],
    )
    bench_scenarios._validate_catalog([repeated])  # must not raise


def test_full_catalog_validates_without_raising():
    bench_scenarios._validate_catalog(SCENARIOS)


# --------------------------------------------------------------------------
# S13...S18 (REQ-V160-TQ-05): imports cleanly, ids unique, S01...S12 untouched
# --------------------------------------------------------------------------


def test_all_eighteen_scenarios_are_present_and_unique():
    ids = [scenario.id for scenario in SCENARIOS]
    assert len(ids) == 18
    assert len(set(ids)) == 18
    for expected in ("S13", "S14", "S15", "S16", "S17", "S18"):
        assert expected in ids


def test_s01_through_s12_are_unchanged():
    """No existing scenario's id, title, turns or checks may change
    (REQ-V160-TQ-05). S01 is checked field-by-field as the representative
    case; the rest are checked by checks-shape and turns-count, which would
    catch an accidental edit, truncation or reordering of any of them."""
    by_id = {scenario.id: scenario for scenario in SCENARIOS}
    s01 = by_id["S01"]
    assert s01.title == "greet"
    assert s01.turns == ["Привет! Что ты умеешь? Ответь кратко."]
    assert [check.kind for check in s01.checks] == [
        bench_scenarios.NO_TOOLS,
        bench_scenarios.ANSWER_REGEX,
        bench_scenarios.ANSWER_MAX_CHARS,
    ]
    assert s01.network is False

    expected_check_counts = {
        "S01": 3,
        "S02": 2,
        "S03": 2,
        "S04": 3,
        "S05": 2,
        "S06": 2,
        "S07": 2,
        "S08": 2,
        "S09": 2,
        "S10": 3,
        "S11": 2,
        "S12": 2,
    }
    for scenario_id, count in expected_check_counts.items():
        assert len(by_id[scenario_id].checks) == count, scenario_id
        # None of the pre-existing checks carry a `tool_calls_max` -- that
        # kind was introduced by this task and only S13...S18 use it.
        assert all(
            check.kind != bench_scenarios.TOOL_CALLS_MAX for check in by_id[scenario_id].checks
        ), scenario_id


def test_s13_to_s18_each_carry_exactly_one_tool_calls_max_check():
    by_id = {scenario.id: scenario for scenario in SCENARIOS}
    expected_max_calls = {"S13": 5, "S14": 4, "S15": 3, "S16": 4, "S17": 4, "S18": 3}
    for scenario_id, expected in expected_max_calls.items():
        ceilings = [
            check
            for check in by_id[scenario_id].checks
            if check.kind == bench_scenarios.TOOL_CALLS_MAX
        ]
        assert len(ceilings) == 1, scenario_id
        assert ceilings[0].max_calls == expected, scenario_id


def test_s17_is_the_only_new_network_scenario():
    by_id = {scenario.id: scenario for scenario in SCENARIOS}
    for scenario_id in ("S13", "S14", "S15", "S16", "S18"):
        assert by_id[scenario_id].network is False, scenario_id
    assert by_id["S17"].network is True


# --------------------------------------------------------------------------
# T11: `BENCH_SCHEMA` 1 -> 2, `runs[].spans` (REQ-V160-BEN-03, -04)
# --------------------------------------------------------------------------


def test_span_row_keys_is_derived_and_excludes_attributes_json_and_conv_id():
    """REQ-V160-BEN-03: the formula, verbatim -- not hand-listed, so it widens
    with the schema exactly as `LLM_ROW_KEYS`/`TOOL_ROW_KEYS` do."""
    expected = frozenset(storage.SPAN_COLUMNS) - {"conv_id", "attributes_json"} | {
        "conv_seq",
        "attributes",
    }
    assert expected == bench.SPAN_ROW_KEYS
    assert "attributes_json" not in bench.SPAN_ROW_KEYS
    assert "conv_id" not in bench.SPAN_ROW_KEYS
    assert "attributes" in bench.SPAN_ROW_KEYS


def test_required_span_row_keys_names_attributes_never_attributes_json():
    assert "attributes" in bench.REQUIRED_SPAN_ROW_KEYS
    assert "attributes_json" not in bench.REQUIRED_SPAN_ROW_KEYS
    assert "attributes_json" not in bench.LLM_ROW_KEYS
    assert "attributes_json" not in bench.TOOL_ROW_KEYS


def test_required_tool_row_keys_excludes_exactly_trace_id_and_span_id():
    """T11: discovered while checking REQ-V160-BEN-02's standing
    `docs/assets/bench/baseline-v1.4.json` against `mode="informational"`.
    `TOOL_ROW_KEYS` used to double as its own REQUIRED bound (a comment,
    since corrected, claimed the tool_calls schema was unchanged by this
    spec) -- stale since T2/T3 added `trace_id`/`span_id` to
    `storage.TOOL_CALL_COLUMNS` with no REQUIRED fallback of their own, so a
    v1.3-shaped `tool_calls` row (this standing baseline's own shape) was
    silently unreadable, masked only because a bare `bench_schema` mismatch
    always raised first."""
    assert bench.TOOL_ROW_KEYS - {"trace_id", "span_id"} == bench.REQUIRED_TOOL_ROW_KEYS


def test_a_v13_shaped_tool_calls_row_validates_without_trace_id_or_span_id():
    """`tool_row()` already produces exactly the v1.3 shape (12 columns, no
    `trace_id`/`span_id`) -- proving the fix above actually reads it."""
    row = tool_row(1)
    assert "trace_id" not in row and "span_id" not in row
    document = fake_doc()
    run = document["runs"][0]
    run["tool_calls"] = [row]
    run["totals"] = bench.totals_from_rows(run["llm_calls"], [row], run["totals"]["wall_ms"])
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench.check_document(document) == (0, "valid")


def test_a_missing_spans_key_is_tolerated_like_an_older_llm_row():
    """REQ-V160-BEN-03: `spans` is new at this schema. The writer
    (`_run_record`) always emits the key (proven below by a real run); the
    validator tolerates its absence the same way it tolerates an older
    `llm_calls` row missing `trace_id`/`span_id` -- a document that predates
    this task (or a hand-built fixture) is not thereby invalid."""
    document = fake_doc()
    assert "spans" not in document["runs"][0]
    assert bench.check_document(document) == (0, "valid")


def test_required_span_row_keys_enforced_only_at_schema_2():
    incomplete_span = {"id": 1}
    document = fake_doc()
    document["runs"][0]["spans"] = [incomplete_span]

    # strict: `bench_schema` is always `BENCH_SCHEMA` (2), so this row's
    # missing columns are caught.
    code, reason = bench.check_document(document)
    assert code == 1
    assert "spans" in reason

    # informational, `bench_schema: 1`: the same malformed row is never even
    # looked at -- an informational v1.4-shaped document has no spans.
    document["bench_schema"] = 1
    assert bench.check_document(document, mode="informational") == (0, "valid")


def test_spans_round_trip_through_a_real_run(tmp_path):
    """REQ-V160-BEN-04: a real `run_bench` call (the same fakes
    `tests/test_bench.py` uses) produces real `spans` rows -- `attributes` is
    the parsed object, `conv_id` never appears, and the document validates."""
    scenarios = [scenario for scenario in SCENARIOS if scenario.id == "S01"]
    result = bench.run_bench(scenarios, tag="v160-t11", **run_kwargs(tmp_path))
    run = result.runs[0]
    assert run["spans"], "a real scenario turn must produce at least one span row"
    row = run["spans"][0]
    assert set(row) == set(bench.SPAN_ROW_KEYS)
    assert "attributes_json" not in row
    assert "conv_id" not in row
    assert isinstance(row["attributes"], dict)
    assert bench._is_int(row["conv_seq"]) and row["conv_seq"] >= 1

    document = bench.redact_document(result.document(), [TG_ID])
    document["meta"].update(
        {
            "tag": "v160-t11",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:10:00Z",
            "git_commit": "0" * 40,
            "prefix_tokens": 900,
            "pricing": None,
        }
    )
    assert bench.check_document(document, scenarios) == (0, "valid")


# --------------------------------------------------------------------------
# T11: `_validate`'s `mode`, the `check`/`report`/`report --gate` split
# (REQ-V160-BEN-03)
# --------------------------------------------------------------------------


def _old_shaped_doc(**meta):
    """A `bench_schema: 1` document whose `scenarios_sha256` also no longer
    matches the live catalogue -- REQ-V160-BEN-02's actual v1.4-vs-v1.6.0
    shape, and T-V160-BEN-01's fixture."""
    document = fake_doc(scenarios_sha256="0" * 64, **meta)
    document["bench_schema"] = 1
    return document


def test_check_refuses_a_bench_schema_1_document(tmp_path):
    path = _write(tmp_path, "old.json", _old_shaped_doc())
    assert bench.main(["check", str(path)]) == 1


def test_report_without_gate_accepts_schema_1_and_prints_the_informational_banner(tmp_path, capsys):
    path = _write(tmp_path, "old.json", _old_shaped_doc())
    code = bench.main(["report", "--baseline", str(path)])
    assert code == 0
    err = capsys.readouterr().err
    assert "informational comparison: meta.scenarios_sha256" in err
    assert "deltas are indicative, not measured" in err


def test_report_gate_refuses_the_schema_1_pair(tmp_path):
    path = _write(tmp_path, "old.json", _old_shaped_doc())
    code = bench.main(["report", "--baseline", str(path), "--gate"])
    assert code == bench.EXIT_NOT_COMPARABLE


def test_scenarios_sha256_mismatch_is_fatal_for_check(tmp_path):
    document = fake_doc(scenarios_sha256="0" * 64)
    path = _write(tmp_path, "stale.json", document)
    code, _reason = bench.check_document(json.loads(path.read_text(encoding="utf-8")))
    assert code == 1
    assert bench.main(["check", str(path)]) == 1


def test_scenarios_sha256_mismatch_is_a_note_only_for_plain_report(tmp_path, capsys):
    document = fake_doc(scenarios_sha256="0" * 64)
    path = _write(tmp_path, "stale.json", document)
    assert bench.main(["report", "--baseline", str(path)]) == 0
    err = capsys.readouterr().err
    assert "informational comparison: meta.scenarios_sha256" in err


def test_scenarios_sha256_mismatch_is_fatal_for_report_gate(tmp_path):
    baseline = fake_doc(scenarios_sha256="0" * 64)
    candidate = fake_doc(flags=CANDIDATE_FLAGS, tag="optimized")
    base_path = _write(tmp_path, "baseline.json", baseline)
    cand_path = _write(tmp_path, "candidate.json", candidate)
    code = bench.main(
        [
            "report",
            "--baseline",
            str(base_path),
            "--candidate",
            str(cand_path),
            "--gate",
        ]
    )
    assert code != 0


def test_check_document_mode_default_is_unchanged_for_every_existing_caller():
    """`check_document(document, scenarios=None, *, mode="strict")` keeps its
    exact signature and default -- a caller that never passes `mode` sees
    exactly today's strict behaviour."""
    assert bench.check_document(fake_doc()) == (0, "valid")
    assert bench.check_document(fake_doc(), SCENARIOS) == (0, "valid")


# --------------------------------------------------------------------------
# T11: `meta` gains six locked instrument fields (REQ-V160-BEN-05)
# --------------------------------------------------------------------------


_SIX_NEW_META_KEYS = (
    "lmstudio_version",
    "served_model_id",
    "lmstudio_context_length",
    "generation_settings",
    "prompt_tools_sha256",
    "obs_capture_content",
)


def test_locked_meta_fields_holds_the_six_new_keys_and_not_git_commit():
    assert set(_SIX_NEW_META_KEYS) <= set(bench.LOCKED_META_FIELDS)
    assert len(bench.LOCKED_META_FIELDS) == 16
    assert "git_commit" not in bench.LOCKED_META_FIELDS


def _instrument_meta(**overrides):
    meta = {
        "lmstudio_version": "0.3.9",
        "served_model_id": "local-model",
        "lmstudio_context_length": 8192,
        "generation_settings": {
            "agent": {"temperature": 0, "max_tokens": 2048, "stream": False, "tool_choice": "auto"}
        },
        "prompt_tools_sha256": "a" * 64,
        "obs_capture_content": False,
    }
    meta.update(overrides)
    return meta


def test_instrument_meta_nulls_off_lmstudio(tmp_path):
    cfg = make_config(
        tmp_path, llm_provider="openrouter", openrouter_api_key="k", openrouter_model="m"
    )
    arguments = argparse.Namespace(
        lmstudio_version="0.3.9",
        served_model_id="local-model",
        lmstudio_context_length=8192,
    )
    assert bench._instrument_meta(cfg, arguments) == {
        "lmstudio_version": None,
        "served_model_id": None,
        "lmstudio_context_length": None,
    }


def test_instrument_meta_threads_the_operator_values_through_on_lmstudio(tmp_path):
    cfg = make_config(tmp_path)  # llm_provider="lmstudio"
    arguments = argparse.Namespace(
        lmstudio_version="0.3.9",
        served_model_id="local-model",
        lmstudio_context_length=8192,
    )
    assert bench._instrument_meta(cfg, arguments) == {
        "lmstudio_version": "0.3.9",
        "served_model_id": "local-model",
        "lmstudio_context_length": 8192,
    }


def test_generation_settings_matches_what_build_payload_actually_sends(tmp_path):
    cfg = make_config(tmp_path)
    settings = bench._generation_settings(cfg)
    assert settings["agent"] == {
        "temperature": 0,
        "max_tokens": cfg.llm_max_tokens,
        "stream": False,
        "tool_choice": "auto",
    }
    assert settings["summary_initial"] == {
        "temperature": 0,
        "max_tokens": bench.agent.SUMMARY_MAX_TOKENS,
        "stream": False,
    }
    assert bench.agent.SUMMARY_MAX_TOKENS == 512
    assert settings["summary_retry"] == {
        "temperature": 0,
        "max_tokens": cfg.llm_summary_max_tokens,
        "stream": False,
    }
    assert settings["provider_defaults"] == ["seed", "stop", "top_p"]


def test_prompt_tools_sha256_is_a_sha256_hex_digest():
    digest = bench._prompt_tools_sha256({})
    assert isinstance(digest, str)
    assert len(digest) == 64
    int(digest, 16)  # must be valid hex


def test_gate_exits_not_comparable_when_a_new_locked_field_differs():
    baseline = fake_doc()
    baseline["meta"].update(_instrument_meta())
    candidate = fake_doc(flags=CANDIDATE_FLAGS, tag="optimized")
    candidate["meta"].update(_instrument_meta(obs_capture_content=True))
    reason = bench.comparability(baseline, candidate)
    assert reason == "locked meta field differs: obs_capture_content"


def test_gate_exits_not_comparable_when_a_new_locked_field_is_omitted_on_one_side():
    baseline = fake_doc()
    baseline["meta"].update(_instrument_meta())
    candidate = fake_doc(flags=CANDIDATE_FLAGS, tag="optimized")
    candidate["meta"].update(_instrument_meta())
    del candidate["meta"]["prompt_tools_sha256"]
    reason = bench.comparability(baseline, candidate)
    assert reason == "locked meta field differs: prompt_tools_sha256"


def test_gate_is_comparable_when_only_git_commit_differs():
    baseline = fake_doc()
    baseline["meta"].update(_instrument_meta())
    baseline["meta"]["git_commit"] = "a" * 40
    candidate = fake_doc(flags=CANDIDATE_FLAGS, tag="optimized")
    candidate["meta"].update(_instrument_meta())
    candidate["meta"]["git_commit"] = "b" * 40
    assert bench.comparability(baseline, candidate) is None


def test_cli_report_gate_flags_a_differing_new_locked_field(tmp_path):
    baseline = fake_doc()
    baseline["meta"].update(_instrument_meta())
    candidate = fake_doc(flags=CANDIDATE_FLAGS, tag="optimized")
    candidate["meta"].update(_instrument_meta(served_model_id="a-different-model"))
    base_path = _write(tmp_path, "baseline.json", baseline)
    cand_path = _write(tmp_path, "candidate.json", candidate)
    code = bench.main(
        [
            "report",
            "--baseline",
            str(base_path),
            "--candidate",
            str(cand_path),
            "--gate",
        ]
    )
    assert code == bench.EXIT_NOT_COMPARABLE


def test_the_six_new_meta_keys_are_present_after_a_run(tmp_path, monkeypatch):
    _stub_cli(monkeypatch, tmp_path)
    out = tmp_path / "assets" / "run.json"
    code = bench.main(
        [
            "run",
            "--tag",
            "run",
            "--repeats",
            "1",
            "--only",
            "S01",
            "--lmstudio-version",
            "0.3.9",
            "--served-model-id",
            "local-model",
            "--lmstudio-context-length",
            "8192",
        ]
    )
    assert code == 0
    meta = json.loads(out.read_text(encoding="utf-8"))["meta"]
    assert meta["lmstudio_version"] == "0.3.9"
    assert meta["served_model_id"] == "local-model"
    assert meta["lmstudio_context_length"] == 8192
    assert meta["generation_settings"]["agent"]["tool_choice"] == "auto"
    assert isinstance(meta["prompt_tools_sha256"], str) and len(meta["prompt_tools_sha256"]) == 64
    assert meta["obs_capture_content"] is False


# --------------------------------------------------------------------------
# T11: a dirty tree refuses a `baseline-*` run (REQ-V160-BEN-05)
# --------------------------------------------------------------------------


def test_baseline_tag_refuses_a_dirty_tree(tmp_path, monkeypatch, capsys):
    _stub_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(bench, "_tree_is_dirty", lambda: True)
    code = bench.main(["run", "--tag", "baseline-x", "--repeats", "1", "--only", "S01"])
    assert code == bench.EXIT_ERROR
    assert "dirty tree" in capsys.readouterr().err


def test_baseline_tag_proceeds_on_a_clean_tree(tmp_path, monkeypatch):
    _stub_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(bench, "_tree_is_dirty", lambda: False)
    code = bench.main(["run", "--tag", "baseline-x", "--repeats", "1", "--only", "S01"])
    assert code == 0


def test_smoke_tag_proceeds_regardless_of_tree_state(tmp_path, monkeypatch):
    _stub_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(bench, "_tree_is_dirty", lambda: True)
    code = bench.main(["run", "--tag", "smoke-x", "--repeats", "1", "--only", "S01"])
    assert code == 0


# --------------------------------------------------------------------------
# T15 resume, erratum 4: REQ-V160-BEN-08 -- `run` removes only its own tag
# directory (T-V160-BEN-08)
# --------------------------------------------------------------------------


def test_run_removes_only_its_own_tag_directory(tmp_path, monkeypatch):
    """Two consecutive `run` invocations with different tags leave both
    `.bench/<tag>/` documents on disk, and a sibling `--out` document written
    directly under `.bench/` (the `smoke-v160.json` shape) survives too; a
    third run reusing the first tag replaces only that tag's own directory."""
    _stub_cli(monkeypatch, tmp_path)
    bench_root = tmp_path / ".bench"

    assert bench.main(["run", "--tag", "tag-a", "--repeats", "1", "--only", "S01"]) == 0
    assert (bench_root / "tag-a").is_dir()

    sibling_out = bench_root / "sibling.json"
    sibling_out.write_text("{}", encoding="utf-8")

    assert bench.main(["run", "--tag", "tag-b", "--repeats", "1", "--only", "S01"]) == 0
    assert (bench_root / "tag-a").is_dir(), "sibling tag directory must survive"
    assert (bench_root / "tag-b").is_dir()
    assert sibling_out.exists(), "a sibling --out document under .bench/ must survive"

    marker = bench_root / "tag-a" / "marker"
    marker.write_text("stale", encoding="utf-8")
    assert bench.main(["run", "--tag", "tag-a", "--repeats", "1", "--only", "S01"]) == 0
    assert not marker.exists(), "a third run must replace tag-a's own directory"
    assert (bench_root / "tag-b").is_dir(), "tag-b must still survive"
    assert sibling_out.exists()


# --------------------------------------------------------------------------
# T11: the bench.py:1420-1422 report-text fix -- a computed pp figure, not a
# hardcoded "2.8-3.0 pp"
# --------------------------------------------------------------------------


def test_success_rate_line_states_a_computed_one_run_pp_figure():
    baseline = fake_doc(repeats=1)
    runs = [fake_run(scenario.id, 1, llm_rows=[llm_row(1)]) for scenario in SCENARIOS]
    runs[0] = fake_run(runs[0]["scenario"], runs[0]["repeat"], llm_rows=[llm_row(1)], success=False)
    candidate = fake_doc(runs, repeats=1, flags=CANDIDATE_FLAGS, tag="optimized")

    decision = bench.verdict(baseline, candidate)
    line = next(entry for entry in decision.lines if entry.startswith("success rate:"))
    total_runs = candidate["summary"]["runs"]
    expected_pp = 100 / total_runs
    assert f"{expected_pp:.1f} pp" in line
    assert "2.8" not in line
    assert "3.0" not in line
    assert f"at {total_runs} runs" in line
