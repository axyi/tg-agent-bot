"""spec-v1.7.0: the summary wall-clock budget (SUM-01…-05).

Offline and deterministic (REQ-V170-TST-01): no network, no Docker, no
`.env`, no live LLM. Every clock and every LLM in a test is a fake.

REQ-V170-TREE-01 splits this release's tests three ways by requirement
group; `tests/test_v170_reasoning.py` (RSN-*, POL-*, OBS-*) and
`tests/test_v170_bench.py` (BEN-*, CAR-*, VER-*, RPT-02, ACC-03) hold the
other two.
"""

from __future__ import annotations

import json

import pytest

import storage
from agent import summarize_conversation
from config import ConfigError, load_config
from llm.base import REASONING_DEFAULT, LLMError, LLMResponse, ReasoningRequest
from tests.fakes import FakeLLM
from tests.test_config import base_env
from tests.test_summary import VALID_SUMMARY


def _llm_rows(conn):
    return conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall()


# --------------------------------------------------------------------------
# T-V170-SUM-05
# --------------------------------------------------------------------------


def test_t_v170_sum_05_raises_below_the_summary_floor():
    # Discriminates the new check from the pre-existing `_check_timeout_budget`
    # (REQ-V14-REL-01): with LLM_MAX_TOKENS == LLM_SUMMARY_MAX_TOKENS == 1536,
    # the pre-existing check's own floor is 21.1 + 0.093*1536 = 163.948s --
    # 180s clears it -- while this check's floor adds the 30s rescue-retry
    # floor on top (193.948s), which 180s does not clear. A timeout that
    # merely satisfies the older check must not also satisfy this one.
    with pytest.raises(ConfigError) as exc:
        load_config(
            env=base_env(LLM_TIMEOUT_S="180", LLM_MAX_TOKENS="1536", LLM_SUMMARY_MAX_TOKENS="1536"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_SUMMARY_MAX_TOKENS" in message


def test_t_v170_sum_05_does_not_raise_at_shipped_defaults():
    cfg = load_config(env=base_env(LLM_TIMEOUT_S="240"), load_env_file=False)
    assert cfg.llm_timeout_s == 240.0 and cfg.llm_summary_max_tokens == 1536


def test_t_v170_sum_05_does_not_raise_at_the_1_7_0_instrument():
    cfg = load_config(env=base_env(LLM_TIMEOUT_S="600", LLM_MAX_TOKENS="4096"), load_env_file=False)
    assert cfg.llm_timeout_s == 600.0


def test_t_v170_sum_05_preexisting_check_message_unchanged():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_TIMEOUT_S="120"), load_env_file=False)
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_MAX_TOKENS" in message


# --------------------------------------------------------------------------
# T-V170-SUM-01…-04, N5 -- the summary wall-clock budget
# --------------------------------------------------------------------------


class _FakeClock:
    """A stateful, injectable clock. `t` is advanced by the fake LLM below,
    simulating the wall-clock time one `complete()` call actually consumed --
    the only realistic place to inject that, since `summarize_conversation`
    itself calls the clock only around request decisions, never mid-request.
    """

    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t


class _ClockAdvancingLLM:
    """Each scripted item is `(advance_seconds, response_or_error)`. Records
    every `(reasoning, timeout_s)` pair it actually receives."""

    def __init__(self, clock: _FakeClock, script):
        self.clock = clock
        self.script = list(script)
        self.calls: list[tuple[ReasoningRequest, float | None]] = []

    def describe(self):
        return ("fake", "fake-model")

    def complete(
        self, messages, tools, *, max_tokens=None, reasoning=REASONING_DEFAULT, timeout_s=None
    ):
        self.calls.append((reasoning, timeout_s))
        advance, item = self.script.pop(0)
        self.clock.t += advance
        if isinstance(item, LLMError):
            raise item
        return item


def _summary_conn_with_content(conn):
    conv = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv, "hello")
    storage.add_assistant_message(conn, conv, "hi")
    return conv


def test_t_v170_sum_01_deadline_taken_once_both_requests_issued(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (40.0, LLMResponse("cut off", [], "length")),
            (50.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
        ],
    )
    result = summarize_conversation(
        conn,
        conv,
        llm,
        None,
        budget_s=100.0,
        clock=clock,
    )
    assert result is not None
    assert len(llm.calls) == 2  # both issued: 100 - 40 = 60 >= 30 floor


def test_t_v170_sum_01_budget_s_none_is_byte_identical_to_todays_behaviour(conn):
    conv = _summary_conn_with_content(conn)
    llm = FakeLLM([LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")])
    result = summarize_conversation(conn, conv, llm, None)
    assert result is not None
    assert llm.timeout_s_calls == [None]


def test_t_v170_sum_02_retry_skipped_below_floor_returns_none_one_row(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (80.0, LLMResponse("cut off", [], "length")),
        ],
    )
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert result is None
    assert len(llm.calls) == 1  # the retry was never issued
    assert len(_llm_rows(conn)) == 1
    assert any("budget exhausted" in r.message for r in caplog.records)


def test_t_v170_sum_02_repair_skipped_below_floor_returns_none_one_row(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (80.0, LLMResponse("not json at all", [], "stop")),
        ],
    )
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert result is None
    assert len(llm.calls) == 1
    assert len(_llm_rows(conn)) == 1
    assert any("budget exhausted" in r.message for r in caplog.records)


def test_t_v170_sum_03_attempt_1_timeout_is_the_remaining_budget_not_none_not_client_own(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
        ],
    )
    summarize_conversation(conn, conv, llm, None, budget_s=10.0, clock=clock)
    assert len(llm.calls) == 1
    _, timeout_s = llm.calls[0]
    assert timeout_s == 10.0  # not None, and not the client's own (irrelevant) 600


def test_t_v170_sum_03_retrys_timeout_equals_the_budget_remaining_then(conn):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (40.0, LLMResponse("cut off", [], "length")),
            (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
        ],
    )
    summarize_conversation(conn, conv, llm, None, budget_s=100.0, clock=clock)
    assert len(llm.calls) == 2
    _, second_timeout = llm.calls[1]
    assert second_timeout == 60.0  # 100 - 40


def test_n5_attempt_1_issued_at_10s_no_retry_below_floor(conn, caplog):
    clock = _FakeClock(0.0)
    conv = _summary_conn_with_content(conn)
    llm = _ClockAdvancingLLM(
        clock,
        [
            (0.0, LLMResponse("cut off", [], "length")),
        ],
    )
    with caplog.at_level("WARNING"):
        result = summarize_conversation(conn, conv, llm, None, budget_s=10.0, clock=clock)
    assert len(llm.calls) == 1  # attempt 1 WAS issued -- 10s remain, positive
    _, timeout_s = llm.calls[0]
    assert timeout_s == 10.0
    assert result is None  # no retry: remaining is still 10s < 30s floor


def test_t_v170_sum_04_retry_and_repair_forced_off_under_every_policy(conn):
    for policy, on_purposes in [
        ("model-default", frozenset()),
        ("off", frozenset()),
        ("by-purpose", frozenset({"summary"})),
    ]:
        conv = storage.get_or_create_active_conversation(conn, 42)
        storage.add_user_message(conn, conv, "hello")
        clock = _FakeClock(0.0)
        llm = _ClockAdvancingLLM(
            clock,
            [
                (0.0, LLMResponse("cut off", [], "length")),
                (0.0, LLMResponse(json.dumps(VALID_SUMMARY), [], "stop")),
            ],
        )
        cfg_stub = type(
            "Cfg",
            (),
            {
                "obs_capture_content": False,
                "llm_reasoning_policy": policy,
                "llm_reasoning_on_purposes": on_purposes,
            },
        )()
        summarize_conversation(conn, conv, llm, cfg_stub, budget_s=1000.0, clock=clock)
        assert len(llm.calls) == 2
        attempt1_reasoning, _ = llm.calls[0]
        retry_reasoning, _ = llm.calls[1]
        assert retry_reasoning.value == "off" and retry_reasoning.tag == "summary"
        if policy == "by-purpose":
            assert attempt1_reasoning.value == "on"  # summary is in on_purposes here


def test_t_v170_sum_05_module_constant_matches_config_local_copy():
    from agent import SUMMARY_BUDGET_FLOOR_S
    from config import _SUMMARY_BUDGET_FLOOR_S

    assert SUMMARY_BUDGET_FLOOR_S == _SUMMARY_BUDGET_FLOOR_S == 30.0
