"""The tool-call ceiling -- spec-v1.6.0 section 10 (REQ-V160-TQ-05..07).

T10's own tests: the `tool_calls_max` check kind and factory, the six new
scenarios S13...S18 appended to `SCENARIOS`, and the catalogue's new
tool-call-ceiling validation rule.

Offline, deterministic, no Docker, no network, no live LLM calls -- this
module never runs a scenario, only inspects the catalogue and the check
evaluator.
"""

from __future__ import annotations

import pytest

from devtools import bench, bench_scenarios
from devtools.bench_scenarios import SCENARIOS, Scenario, tool_calls_max, tool_used
from tests.test_bench import tool_row


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
    expected_max_calls = {"S13": 4, "S14": 4, "S15": 3, "S16": 4, "S17": 4, "S18": 3}
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
