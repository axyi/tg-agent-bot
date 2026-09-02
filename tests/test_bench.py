"""The benchmark harness — spec-v1.3 sections 7 and 13.3 (REQ-V13-BEN-01…14).

Offline by construction: `FakeLLM` / `RecordingRunner` / `FakeFetcher` stand in
for inference, Docker and the network, and the only subprocess is the CLI
exit-code test. The autouse guards of `tests/conftest.py` (no HTTP, no DNS,
`config.PROJECT_ROOT` pointed at a temp directory) apply here too.
"""

import copy
import dataclasses
import json
import logging
import sqlite3
import threading

import pytest

import config
import metrics
import storage
from devtools import bench, bench_scenarios
from devtools.bench_scenarios import SCENARIOS, Check, Scenario, answer_regex
from llm.base import LLMError, LLMResponse, ToolCall, Usage
from tests.fakes import FakeFetcher, RecordingRunner

TG_ID = 424242
BASELINE_FLAGS = {
    "HISTORY_TOOL_STUB": None,
    "EXEC_OUTPUT_DEFAULT_CHARS": None,
    "FETCH_INLINE_DEFAULT_CHARS": None,
    "LLM_REASONING": None,
    "LLM_SUMMARY_MODEL": "",
    "LLM_FAILOVER": "off",
    "LLM_MAX_TOKENS": 2048,
}
CANDIDATE_FLAGS = {**BASELINE_FLAGS, "HISTORY_TOOL_STUB": "on",
                   "EXEC_OUTPUT_DEFAULT_CHARS": 1500,
                   "FETCH_INLINE_DEFAULT_CHARS": 5000, "LLM_REASONING": "auto"}
PRICING = {
    "basis": "reference:some/model",
    "model": "some/model",
    "input_usd_per_mtok": 1.0,
    "output_usd_per_mtok": 1.0,
    "cached_input_usd_per_mtok": None,
    "fetched_at": "2026-01-01T00:00:00Z",
}


# --------------------------------------------------------------------------
# fixture builders: a document that is self-consistent by construction, so a
# deliberately tampered one is unambiguous
# --------------------------------------------------------------------------

def llm_row(row_id, *, conv_seq=1, purpose="agent", round_no=1, prompt=1000,
            completion=100, cached=None, reasoning=None, reasoning_chars=0,
            error_kind=None, cost=None, latency=500, tools_exposed=3, turn_id=1,
            by_role=None):
    total = None if prompt is None or completion is None else prompt + completion
    roles = by_role or {"system": 100, "tools": 50, "user": 10, "assistant": 0, "tool": 0}
    return {
        "id": row_id, "conv_seq": conv_seq, "turn_id": turn_id, "purpose": purpose,
        "round": round_no, "attempt": 1, "ts": "2026-01-01T00:00:00Z",
        "provider": "lmstudio", "model": "m",
        "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total,
        "cached_tokens": cached, "reasoning_tokens": reasoning,
        "reasoning_chars": reasoning_chars, "prompt_chars": (prompt or 0) * 3,
        "prompt_chars_by_role": json.dumps(roles, sort_keys=True),
        "messages_n": 2, "tools_exposed": tools_exposed, "latency_ms": latency,
        "finish_reason": "stop", "tool_calls_n": 0, "error_kind": error_kind,
        "cost_usd": cost, "cost_basis": None if cost is None else "reference:some/model",
    }


def tool_row(row_id, *, conv_seq=1, tool="exec", output_tokens_est=200, turn_id=1):
    return {
        "id": row_id, "conv_seq": conv_seq, "turn_id": turn_id,
        "tool_call_id": f"call_{row_id}", "tool": tool, "ts": "2026-01-01T00:00:00Z",
        "input_chars": 20, "raw_output_chars": 600, "output_chars": 600,
        "output_tokens_est": output_tokens_est, "duration_ms": 30, "outcome": "ok",
    }


def fake_run(scenario_id, repeat=1, *, llm_rows=None, tool_rows=None, success=True,
             failure=None, answers=("ok",), wall_ms=1000, checks=None):
    llm_rows = [llm_row(1)] if llm_rows is None else list(llm_rows)
    tool_rows = [] if tool_rows is None else list(tool_rows)
    if checks is None:
        checks = [{"kind": "answer_regex", "ok": success,
                   "detail": "ok" if success else "pattern not found"}]
    return {
        "scenario": scenario_id, "repeat": repeat, "success": success,
        "failure": None if success else (failure or "checks"),
        "checks": checks, "answers": list(answers),
        "llm_calls": llm_rows, "tool_calls": tool_rows,
        "totals": bench.totals_from_rows(llm_rows, tool_rows, wall_ms),
    }


def fake_doc(runs=None, *, repeats=1, skipped=(), flags=None, **meta):
    skipped = list(skipped)
    if runs is None:
        runs = [fake_run(scenario.id, repeat)
                for scenario in SCENARIOS if scenario.id not in skipped
                for repeat in range(1, repeats + 1)]
    document = {
        "bench_schema": 1,
        "meta": {
            "tag": "t", "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T01:00:00Z", "git_commit": "0" * 40,
            "provider": "lmstudio", "model": "m", "context_length": 42496,
            "repeats": repeats, "timeout_s": 600.0, "prefix_tokens": 900,
            "scenarios_sha256": bench.scenarios_sha256(),
            "pricing": dict(PRICING), "skipped_scenarios": skipped, "only": None,
            "env_flags": dict(flags or BASELINE_FLAGS), "config_sha256": "c" * 64,
            "constants": bench.constants(),
        },
        "runs": runs,
        "summary": bench.summarize(runs, skipped, repeats),
    }
    document["meta"].update(meta)
    return document


def make_config(tmp_path, **overrides):
    base = config.Config(
        telegram_bot_token="123:secret-token-value",
        allowed_tg_ids=frozenset({TG_ID}),
        llm_provider="lmstudio",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="local-model",
        openrouter_api_key="",
        openrouter_model="",
        llm_timeout_s=30.0,
        exec_workdir=tmp_path / "base" / "sandbox",
        db_path=tmp_path / "base" / "bot.db",
        audit_log_path=tmp_path / "base" / "audit.jsonl",
        llm_failover="off",
    )
    return dataclasses.replace(base, **overrides) if overrides else base


class ScriptedLLM:
    """Answers every request the same way unless a script is given."""

    def __init__(self, script=None, answer="ответ 396 три 332 30 50 Orion KV cache",
                 usage=None):
        self.script = list(script) if script is not None else None
        self.answer = answer
        self.usage = usage if usage is not None else Usage(prompt_tokens=100,
                                                           completion_tokens=10)
        self.calls = 0

    def describe(self):
        return ("fake", "fake-model")

    def complete(self, messages, tool_definitions, *, max_tokens=None):
        self.calls += 1
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return LLMResponse(self.answer, [], "stop", usage=self.usage)


class BlockingLLM:
    """Completes `before` calls, then blocks on an event until teardown."""

    def __init__(self, before=0, tool_call=False):
        self.event = threading.Event()
        self.before = before
        self.tool_call = tool_call
        self.calls = 0

    def describe(self):
        return ("fake", "fake-model")

    def complete(self, messages, tool_definitions, *, max_tokens=None):
        self.calls += 1
        if self.calls <= self.before:
            calls = [ToolCall("raw", "exec", json.dumps({"argv": ["echo", "hi"]}))]
            return LLMResponse(
                "", calls if self.tool_call else [], "tool_calls",
                usage=Usage(prompt_tokens=10, completion_tokens=1),
            )
        self.event.wait(30)
        return LLMResponse("late", [], "stop", usage=Usage(prompt_tokens=1,
                                                           completion_tokens=1))


@pytest.fixture
def blocking_llm():
    fake = BlockingLLM()
    yield fake
    fake.event.set()


@pytest.fixture(autouse=True)
def restore_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def run_kwargs(tmp_path, **overrides):
    cfg = overrides.pop("cfg", None) or make_config(tmp_path)
    kwargs = {
        "cfg": cfg,
        "llm_factory": lambda run_cfg: ScriptedLLM(),
        "runner_factory": lambda run_cfg: RecordingRunner(),
        "fetcher_factory": lambda run_cfg: FakeFetcher(),
        "telegram_factory": bench.BenchTelegram,
        "repeats": 1,
        "timeout_s": 30.0,
        "clock": _fake_clock(),
        "sleep": lambda _seconds: None,
        "network_preflight": lambda: False,
        "skills": {},
        "runs_root": tmp_path / ".bench" / "t",
    }
    kwargs.update(overrides)
    return kwargs


def _fake_clock():
    state = {"now": 0.0}

    def clock():
        state["now"] += 0.5
        return state["now"]
    return clock


# --------------------------------------------------------------------------
# the scenario catalog (REQ-V13-BEN-08, REQ-V13-BEN-09)
# --------------------------------------------------------------------------

def test_catalog_is_the_twelve_frozen_scenarios():
    assert len(SCENARIOS) == 12
    assert [scenario.id for scenario in SCENARIOS] == [f"S{n:02d}" for n in range(1, 13)]
    assert len({scenario.id for scenario in SCENARIOS}) == 12
    assert [scenario.id for scenario in SCENARIOS if scenario.network] == ["S08"]
    for scenario in SCENARIOS:
        assert scenario.turns and scenario.checks
        for check in scenario.checks:
            assert check.kind in bench_scenarios.KINDS


def test_no_regex_carries_the_markdown_escape():
    # Appendix C escapes the cell separator; a `\|` in a pattern would be the
    # spec's markdown leaking into a Python regex.
    for scenario in SCENARIOS:
        for check in scenario.checks:
            assert "\\|" not in check.pattern


def test_out_of_range_turn_is_rejected_at_load_time():
    with pytest.raises(ValueError):
        Scenario(id="X", title="x", turns=["a", "/new", "b"],
                 checks=[answer_regex("a", turn=3)])
    # Two non-command turns, so turn=2 is in range and turn=-1 is the last one.
    scenario = Scenario(id="X", title="x", turns=["a", "/new", "b"],
                        checks=[answer_regex("a", turn=2)])
    assert scenario.turn_index(2) == 1
    assert scenario.turn_index(-1) == 1


def test_unknown_check_kind_is_rejected():
    with pytest.raises(ValueError):
        Check(kind="nope")


def test_an_answer_check_without_a_turn_is_rejected():
    with pytest.raises(ValueError):
        Scenario(id="X", title="x", turns=["a"],
                 checks=[Check(kind=bench_scenarios.ANSWER_REGEX, pattern="a")])


# --------------------------------------------------------------------------
# check evaluation (section 7.3)
# --------------------------------------------------------------------------

def _scenario(checks, turns=("вопрос",)):
    return Scenario(id="T01", title="t", turns=list(turns), checks=list(checks))


def test_each_check_kind_against_crafted_answers():
    obs = bench.Observation(answers=["ответ 396"], tool_rows=[tool_row(1)],
                            exit_codes=[0, 2], summary_goals=["a goal"])
    kinds = [
        (bench_scenarios.answer_regex(r"\b396\b"), True),
        (bench_scenarios.answer_regex("отсутствует"), False),
        (bench_scenarios.answer_not_regex("отсутствует"), True),
        (bench_scenarios.answer_not_regex("396"), False),
        (bench_scenarios.answer_max_chars(900), True),
        (bench_scenarios.answer_max_chars(3), False),
        (bench_scenarios.tool_used("exec"), True),
        (bench_scenarios.tool_used("fetch"), False),
        (bench_scenarios.no_tools, False),
        (bench_scenarios.exit_code_seen(nonzero=True), True),
        (bench_scenarios.summary_exists, True),
    ]
    for check, expected in kinds:
        result = bench.evaluate_checks(_scenario([check]), obs)[0]
        assert result["ok"] is expected, check
        assert len(result["detail"]) <= 120


def test_json_keys_reads_the_first_object_and_reports_a_bounded_reason():
    obs = bench.Observation(answers=['вот: {"a": 1, "b": 2} — всё'])
    check = bench_scenarios.json_keys({"a": 1, "b": 2})
    assert bench.evaluate_checks(_scenario([check]), obs)[0]["ok"] is True

    obs = bench.Observation(answers=['{"a": 1, "b": 9}'])
    result = bench.evaluate_checks(_scenario([check]), obs)[0]
    assert result["ok"] is False
    assert result["detail"] == "1 of 2 keys matched"

    result = bench.evaluate_checks(
        _scenario([check]), bench.Observation(answers=["нет объекта"])
    )[0]
    assert result["detail"] == "no json object in the answer"


def test_json_keys_parses_a_nested_object_and_braces_inside_strings():
    """Section 7.3: the *first `{…}` object*, not the text up to the first `}`.
    A non-greedy regex mis-scores every answer whose JSON nests or quotes a
    brace, and the scenarios are frozen after C2."""
    nested = bench_scenarios.json_keys({"result": {"a": 1}})
    obs = bench.Observation(answers=['ответ: {"result": {"a": 1}} — готово'])
    assert bench.evaluate_checks(_scenario([nested]), obs)[0]["ok"] is True

    braced = bench_scenarios.json_keys({"a": "}", "b": 2})
    obs = bench.Observation(answers=['{"a": "}", "b": 2}'])
    assert bench.evaluate_checks(_scenario([braced]), obs)[0]["ok"] is True

    escaped = bench_scenarios.json_keys({"a": '"}', "b": 2})
    obs = bench.Observation(answers=['{"a": "\\"}", "b": 2}'])
    assert bench.evaluate_checks(_scenario([escaped]), obs)[0]["ok"] is True

    # An unterminated brace is not an object: the scan moves to the next one.
    plain = bench_scenarios.json_keys({"a": 1, "b": 2})
    obs = bench.Observation(answers=['{ оборванный {"a": 1, "b": 2}'])
    assert bench.evaluate_checks(_scenario([plain]), obs)[0]["ok"] is True

    obs = bench.Observation(answers=['{"a": 1, "b": 2'])
    result = bench.evaluate_checks(_scenario([plain]), obs)[0]
    assert result["detail"] == "no json object in the answer"


def test_turn_addressing_counts_only_non_command_turns():
    scenario = Scenario(id="T", title="t", turns=["a", "/new", "b", "c"],
                        checks=[answer_regex("first", turn=1),
                                answer_regex("second", turn=2),
                                answer_regex("third", turn=3)])
    obs = bench.Observation(answers=["first", "second", "third"])
    assert [check["ok"] for check in bench.evaluate_checks(scenario, obs)] == [True] * 3


def test_answer_max_chars_detail_is_never_an_excerpt():
    obs = bench.Observation(answers=["x" * 1800])
    result = bench.evaluate_checks(
        _scenario([bench_scenarios.answer_max_chars(1500)]), obs
    )[0]
    assert result["detail"] == "1800 > 1500 chars"
    assert "xxx" not in result["detail"]


def test_exit_code_check_fails_loudly_when_the_audit_log_is_unreadable():
    obs = bench.Observation(answers=["a"], audit_read=False)
    result = bench.evaluate_checks(
        _scenario([bench_scenarios.exit_code_seen(nonzero=True)]), obs
    )[0]
    assert result == {"kind": "exit_code_seen", "ok": False, "detail": "audit log unreadable"}


# --------------------------------------------------------------------------
# run_bench with fakes (REQ-V13-BEN-07)
# --------------------------------------------------------------------------

def test_run_bench_writes_a_document_check_accepts(tmp_path):
    result = bench.run_bench(SCENARIOS, **run_kwargs(tmp_path))
    document = bench.redact_document(result.document(), [TG_ID])
    document["meta"].update({
        "tag": "t", "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:10:00Z", "git_commit": "0" * 40,
        "prefix_tokens": 900, "pricing": None,
    })
    code, reason = bench.check_document(document)
    assert (code, reason) == (0, "valid"), reason
    assert result.meta["skipped_scenarios"] == ["S08"]
    assert len(result.runs) == 11
    assert result.summary["skipped"] == 1


def test_skip_logic_records_the_preflight_decision(tmp_path):
    skipped = bench.run_bench(SCENARIOS, **run_kwargs(tmp_path, repeats=3))
    assert skipped.meta["skipped_scenarios"] == ["S08"]
    assert skipped.summary["skipped"] == 3
    assert not any(run["scenario"] == "S08" for run in skipped.runs)
    assert "S08" not in skipped.summary["per_scenario"]

    one = [scenario for scenario in SCENARIOS if scenario.id == "S01"]
    reachable = bench.run_bench(one, **run_kwargs(tmp_path, network_preflight=lambda: True))
    assert reachable.meta["skipped_scenarios"] == []
    assert reachable.summary["skipped"] == 0


def test_factories_are_called_once_per_run_with_that_runs_config(tmp_path):
    seen = {"fetch": [], "runner": []}

    def fetcher_factory(cfg):
        seen["fetch"].append(cfg.exec_workdir)
        return FakeFetcher()

    def runner_factory(cfg):
        seen["runner"].append(cfg.exec_workdir)
        return RecordingRunner()

    scenarios = [scenario for scenario in SCENARIOS if scenario.id in ("S01", "S02")]
    bench.run_bench(scenarios, **run_kwargs(
        tmp_path, repeats=2, fetcher_factory=fetcher_factory, runner_factory=runner_factory
    ))
    assert len(seen["fetch"]) == 4 == len(seen["runner"])
    assert len(set(seen["fetch"])) == 4          # a fresh sandbox per run
    assert seen["fetch"] == seen["runner"]
    for workdir in seen["fetch"]:
        assert workdir.name == "sandbox"
        assert workdir.parent.parent == tmp_path / ".bench" / "t"


def test_the_harness_never_constructs_a_telegram_client(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("TelegramClient must never be constructed by the harness")
    monkeypatch.setattr(bench.bot.TelegramClient, "__init__", forbidden)
    result = bench.run_bench(
        [scenario for scenario in SCENARIOS if scenario.id == "S01"], **run_kwargs(tmp_path)
    )
    assert len(result.runs) == 1


def test_run_directories_are_removed_after_a_completed_run(tmp_path):
    bench.run_bench(
        [scenario for scenario in SCENARIOS if scenario.id == "S01"], **run_kwargs(tmp_path)
    )
    assert not (tmp_path / ".bench" / "t" / "S01-1").exists()


def test_secrets_and_telegram_ids_never_reach_the_json(tmp_path):
    canary = "canary-CH4RL13-token"
    config.register_secret(canary)
    try:
        answers = f"я {canary} и {TG_ID}"
        result = bench.run_bench(
            [scenario for scenario in SCENARIOS if scenario.id == "S01"],
            **run_kwargs(tmp_path, llm_factory=lambda cfg: ScriptedLLM(answer=answers)),
        )
        document = bench.redact_document(result.document(), [TG_ID])
        text = json.dumps(document, ensure_ascii=False)
        assert canary not in text
        assert str(TG_ID) not in text
        assert "[tg-id]" in text
        assert config.REDACTION in text
    finally:
        config._secrets.discard(canary)


def test_a_provider_error_carrying_a_canary_is_redacted(tmp_path):
    canary = "canary-3RR0R-token"
    config.register_secret(canary)
    try:
        script = [LLMError(f"boom {canary}", retryable=False, kind="http")]
        result = bench.run_bench(
            [scenario for scenario in SCENARIOS if scenario.id == "S01"],
            **run_kwargs(tmp_path, llm_factory=lambda cfg: ScriptedLLM(script=script)),
        )
        document = bench.redact_document(result.document(), [TG_ID])
        assert canary not in json.dumps(document, ensure_ascii=False)
    finally:
        config._secrets.discard(canary)


def test_a_failed_invocation_is_recorded_and_counted(tmp_path):
    script = [LLMError("boom", retryable=False, kind="http")]
    result = bench.run_bench(
        [scenario for scenario in SCENARIOS if scenario.id == "S01"],
        **run_kwargs(tmp_path, llm_factory=lambda cfg: ScriptedLLM(script=script)),
    )
    run = result.runs[0]
    assert run["totals"]["failed_calls"] == 1
    assert run["totals"]["prompt_tokens"] == 0


# --------------------------------------------------------------------------
# aborts: timeout, SIGINT, cost cap (REQ-V13-BEN-05, REQ-V13-BEN-02)
# --------------------------------------------------------------------------

def test_a_timed_out_run_aborts_the_benchmark(tmp_path, blocking_llm):
    scenarios = [scenario for scenario in SCENARIOS if scenario.id in ("S01", "S02")]
    result = bench.run_bench(scenarios, **run_kwargs(
        tmp_path, timeout_s=0.2, llm_factory=lambda cfg: blocking_llm
    ))
    assert result.meta["aborted"] == "timeout:S01-1"
    assert len(result.runs) == 1
    assert result.runs[0]["failure"] == "timeout"
    assert result.runs[0]["success"] is False
    assert (tmp_path / ".bench" / "t" / "S01-1").exists()   # kept for inspection


def test_the_timeout_snapshot_holds_only_committed_rows(tmp_path):
    fake = BlockingLLM(before=1, tool_call=True)
    try:
        result = bench.run_bench(
            [scenario for scenario in SCENARIOS if scenario.id == "S02"],
            **run_kwargs(tmp_path, timeout_s=1.0, llm_factory=lambda cfg: fake),
        )
    finally:
        fake.event.set()
    assert result.meta["aborted"] == "timeout:S02-1"
    assert len(result.runs[0]["llm_calls"]) == 1
    assert result.runs[0]["totals"]["calls"] == 1


def test_sigint_takes_the_same_abort_path_immediately(tmp_path, monkeypatch):
    raised = {"done": False}
    original = threading.Thread.join

    def join(self, timeout=None):
        if not raised["done"]:
            raised["done"] = True
            raise KeyboardInterrupt
        return original(self, timeout)

    monkeypatch.setattr(threading.Thread, "join", join)
    scenarios = [scenario for scenario in SCENARIOS if scenario.id in ("S01", "S02")]
    result = bench.run_bench(scenarios, **run_kwargs(tmp_path))
    assert result.meta["aborted"] == "sigint"
    assert len(result.runs) == 1
    assert result.runs[0]["failure"] == "harness_error"


def test_the_cost_cap_aborts_after_the_run_that_crossed_it(tmp_path):
    usage = Usage(prompt_tokens=100, completion_tokens=10, provider_cost_usd=0.02)
    resolver = bench.pricing.make_resolver(make_config(tmp_path), {})
    scenarios = [scenario for scenario in SCENARIOS if scenario.id in ("S01", "S02")]
    result = bench.run_bench(scenarios, **run_kwargs(
        tmp_path, max_cost_usd=0.01, resolve_cost=resolver,
        llm_factory=lambda cfg: ScriptedLLM(usage=usage),
    ))
    assert result.meta["aborted"] == "cost_cap"
    assert len(result.runs) == 1
    assert result.runs[0]["totals"]["cost_usd"] == pytest.approx(0.02)


def _cli_env(monkeypatch, tmp_path, *, provider_env=None):
    """A complete, obviously fake environment for the real `_base_config`: the
    refusal must be keyed on the provider that would actually be used, so the
    test may not stub the function that resolves it."""
    monkeypatch.setattr(bench, "BENCH_ROOT", tmp_path / ".bench")
    monkeypatch.setattr(bench, "DEFAULT_OUT_DIR", tmp_path / "assets")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:not-a-real-token")
    monkeypatch.setenv("ALLOWED_TG_IDS", str(TG_ID))
    monkeypatch.setenv("LMSTUDIO_MODEL", "local-model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-real-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    monkeypatch.setenv("EXEC_WORKDIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "bot.db"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    if provider_env is None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("LLM_PROVIDER", provider_env)


def test_openrouter_refuses_to_run_without_a_cost_cap(tmp_path, monkeypatch, capsys):
    _cli_env(monkeypatch, tmp_path)
    code = bench.main(["run", "--tag", "t", "--provider", "openrouter"])
    assert code == 1
    assert "--max-cost-usd" in capsys.readouterr().err
    # The refusal happens before the run's own output is written.
    assert not (tmp_path / "assets").exists()


def test_openrouter_from_the_env_refuses_to_run_without_a_cost_cap(
        tmp_path, monkeypatch, capsys):
    """REQ-V13-BEN-02 caps the provider that spends, not the CLI flag: without
    `--provider` the harness pins nothing and `.env` decides."""
    _cli_env(monkeypatch, tmp_path, provider_env="openrouter")
    code = bench.main(["run", "--tag", "baseline"])
    assert code == 1
    assert "--max-cost-usd" in capsys.readouterr().err
    assert not (tmp_path / "assets").exists()


def test_an_openrouter_run_with_a_cap_is_not_refused(tmp_path, monkeypatch, capsys):
    """The other half of the gate: the refusal is about a *missing* cap, so a
    capped OpenRouter run must proceed all the way to its output file."""
    _cli_env(monkeypatch, tmp_path, provider_env="openrouter")
    monkeypatch.setattr(bench, "_resolve_pricing", lambda cfg, client: (None, None))
    monkeypatch.setattr(bench, "_prefix_tokens", lambda client, skills: 900)
    monkeypatch.setattr(bench.llm_module, "build_llm_client",
                        lambda cfg_, client=None, override=None: ScriptedLLM())
    runs = [fake_run("S01", 1)]
    monkeypatch.setattr(bench, "run_bench", lambda *args, **kwargs: bench.BenchResult(
        meta=dict(fake_doc()["meta"]), runs=runs, summary=bench.summarize(runs, [], 1)))

    code = bench.main(["run", "--tag", "capped", "--only", "S01", "--repeats", "1",
                       "--max-cost-usd", "0.01"])
    assert "--max-cost-usd" not in capsys.readouterr().err
    assert code == 0
    assert (tmp_path / "assets" / "capped.json").exists()


def test_a_pinned_lmstudio_provider_overrides_an_openrouter_env(tmp_path, monkeypatch):
    """The mirror image: `--provider lmstudio` is what will actually run, so an
    `.env` naming OpenRouter must not refuse the run."""
    _cli_env(monkeypatch, tmp_path, provider_env="openrouter")
    cfg = bench._base_config("t", "lmstudio")
    assert cfg.llm_provider == "lmstudio"


# --------------------------------------------------------------------------
# meta (REQ-V13-BEN-03, REQ-V13-BEN-10)
# --------------------------------------------------------------------------

def test_env_flags_are_exactly_the_seven_keys_with_null_for_absent_fields(tmp_path):
    flags = bench.env_flags(make_config(tmp_path))
    assert set(flags) == set(bench.ENV_FLAG_KEYS)
    assert len(flags) == 7
    present = {item.name for item in dataclasses.fields(config.Config)}
    for key, field_name in bench.ENV_FLAG_FIELDS.items():
        if field_name not in present:
            assert flags[key] is None, key
    assert flags["LLM_FAILOVER"] == "off"
    assert flags["LLM_MAX_TOKENS"] == 2048


def test_config_sha256_ignores_secrets_and_identifiers_but_not_the_treatment(tmp_path):
    base = make_config(tmp_path)
    digest = bench.config_sha256(base)
    assert digest == bench.config_sha256(
        dataclasses.replace(base, telegram_bot_token="999:another-secret-value")
    )
    assert digest == bench.config_sha256(
        dataclasses.replace(base, allowed_tg_ids=frozenset({111, 222}))
    )
    assert digest == bench.config_sha256(
        dataclasses.replace(base, exec_workdir=tmp_path / "elsewhere")
    )
    assert digest != bench.config_sha256(dataclasses.replace(base, llm_max_tokens=1024))


def test_constants_record_the_request_defaults_verbatim():
    recorded = bench.constants()
    assert recorded["REQUEST_DEFAULTS"] == bench.llm_base.REQUEST_DEFAULTS
    assert recorded["CONTEXT_WINDOW_MESSAGES"] == bench.agent.CONTEXT_WINDOW_MESSAGES
    assert recorded["HTTP_ATTEMPT_LIMIT"] == bench.agent.HTTP_ATTEMPT_LIMIT
    assert recorded["FETCH_MAX_BYTES"] == bench.tools.FETCH_MAX_BYTES


def test_run_config_places_the_three_paths_as_siblings(tmp_path):
    cfg = bench._run_config(make_config(tmp_path), tmp_path / ".bench" / "t" / "S01-1")
    assert cfg.exec_workdir == tmp_path / ".bench" / "t" / "S01-1" / "sandbox"
    assert cfg.db_path == cfg.exec_workdir.parent / "bot.db"
    assert cfg.audit_log_path == cfg.exec_workdir.parent / "audit.jsonl"
    assert cfg.exec_workdir.is_dir()


# --------------------------------------------------------------------------
# `check`: schema, run set, arithmetic (REQ-V13-BEN-01)
# --------------------------------------------------------------------------

# The one fixture whose expectations are hand-computed literals: everywhere
# else the expected value comes from `totals_from_rows` / `summarize`, which are
# the very functions `check` re-runs, so those assertions cannot catch an
# arithmetic that is wrong in both places at once (section 7.4).

_ARITH_ROLES_START = {"system": 100, "tools": 50, "user": 10, "assistant": 0, "tool": 0}
_ARITH_ROLES_GROWN = {"system": 100, "tools": 50, "user": 10, "assistant": 40, "tool": 200}


def _arithmetic_runs():
    """Two runs of one scenario, chosen so every branch of section 7.4 shows:
    an errored agent call, a summary call, a run with a single agent call, a
    reported `cached_tokens` of zero, no price at all, and an even number of
    repeats per scenario."""
    rows_a = [
        llm_row(1, purpose="agent", round_no=1, prompt=1000, completion=100,
                cached=0, latency=500, tools_exposed=3, by_role=_ARITH_ROLES_START),
        llm_row(2, purpose="agent", round_no=2, prompt=1400, completion=100,
                cached=0, latency=600, tools_exposed=3, error_kind="timeout",
                by_role=_ARITH_ROLES_GROWN),
        llm_row(3, purpose="agent", round_no=2, prompt=1400, completion=200,
                cached=0, latency=700, tools_exposed=3, by_role=_ARITH_ROLES_GROWN),
        llm_row(4, purpose="summary", round_no=1, prompt=300, completion=50,
                cached=0, latency=100, tools_exposed=0, by_role=_ARITH_ROLES_START),
    ]
    tools_a = [tool_row(1, tool="exec", output_tokens_est=300),
               tool_row(2, tool="fetch", output_tokens_est=200)]
    rows_b = [
        llm_row(1, purpose="agent", round_no=1, prompt=1400, completion=300,
                cached=0, latency=400, tools_exposed=3, by_role=_ARITH_ROLES_START),
    ]
    # prompts 1000 → 1400 → 1400 → 300: new = 1000 + 400 + 0 + 0 = 1400,
    # re-sent = 4100 − 1400 = 2700.
    totals_a = {
        "calls": 4, "failed_calls": 1, "prompt_tokens": 4100, "completion_tokens": 450,
        "cached_tokens": 0, "reasoning_tokens": 0, "tool_calls": 2,
        "tool_output_tokens_est": 500, "latency_ms": 1900, "cost_usd": None,
        "resent_tokens": 2700, "new_tokens": 1400, "wall_ms": 1000,
    }
    totals_b = {
        "calls": 1, "failed_calls": 0, "prompt_tokens": 1400, "completion_tokens": 300,
        "cached_tokens": 0, "reasoning_tokens": 0, "tool_calls": 0,
        "tool_output_tokens_est": 0, "latency_ms": 400, "cost_usd": None,
        "resent_tokens": 0, "new_tokens": 1400, "wall_ms": 2000,
    }
    run_a = {"scenario": "S01", "repeat": 1, "success": True, "failure": None,
             "checks": [{"kind": "answer_regex", "ok": True, "detail": "ok"}],
             "answers": ["ok"], "llm_calls": rows_a, "tool_calls": tools_a,
             "totals": totals_a}
    run_b = {"scenario": "S01", "repeat": 2, "success": False, "failure": "checks",
             "checks": [{"kind": "answer_regex", "ok": False, "detail": "pattern not found"}],
             "answers": ["no"], "llm_calls": rows_b, "tool_calls": [],
             "totals": totals_b}
    return run_a, run_b


def test_totals_from_rows_matches_hand_computed_arithmetic():
    run_a, run_b = _arithmetic_runs()
    assert bench.totals_from_rows(
        run_a["llm_calls"], run_a["tool_calls"], 1000) == run_a["totals"]
    assert bench.totals_from_rows(
        run_b["llm_calls"], run_b["tool_calls"], 2000) == run_b["totals"]


def test_summarize_matches_hand_computed_arithmetic():
    run_a, run_b = _arithmetic_runs()
    summary = bench.summarize([run_a, run_b], [], 1)

    # 2700 / 5500 — the only value that is not exact in binary.
    assert summary.pop("resent_share") == pytest.approx(0.490909, abs=1e-6)
    assert summary == {
        "runs": 2,
        "skipped": 0,
        "successes": 1,
        "success_rate": 0.5,
        "per_scenario": {
            "S01": {
                "success": 1,
                "of": 2,
                # An even count averages the two runs — never picks one of them.
                "median": {
                    "calls": 2.5, "failed_calls": 0.5, "prompt_tokens": 2750.0,
                    "completion_tokens": 375.0, "cached_tokens": 0.0,
                    "reasoning_tokens": 0.0, "tool_calls": 1.0,
                    "tool_output_tokens_est": 250.0, "latency_ms": 1150.0,
                    "cost_usd": None, "resent_tokens": 1350.0, "new_tokens": 1400.0,
                    "wall_ms": 1500.0,
                },
            },
        },
        "totals": {
            "calls": 5, "failed_calls": 1, "prompt_tokens": 5500,
            "completion_tokens": 750, "cached_tokens": 0, "reasoning_tokens": 0,
            "tool_calls": 2, "tool_output_tokens_est": 500, "latency_ms": 2300,
            "cost_usd": None, "resent_tokens": 2700, "new_tokens": 2800,
            "wall_ms": 3000,
        },
        "avg_per_task": {
            "tokens": 3125.0,
            # 3 agent calls with `error_kind IS NULL`, over 2 runs — the errored
            # agent call and the summary call are both out.
            "rounds": 1.5,
            "tool_calls": 1.0,
            "latency_ms": 1150.0,
        },
        "cost_per_success": None,
        "tokens_per_success": 6250.0,
        # `cached_tokens` was *reported* as zero, so the rate is 0.0, not null.
        "cache_hit_rate": 0.0,
        "top_tools": [{"name": "exec", "calls": 1, "output_tokens_est": 300},
                      {"name": "fetch", "calls": 1, "output_tokens_est": 200}],
        # Three rows tie at 1400; the strict `>` keeps the first of them.
        "top_turn": {"scenario": "S01", "repeat": 1, "turn": 1, "round": 2,
                     "prompt_tokens": 1400},
        # Run B has one agent call and grew by nothing — it stays in the
        # denominator, so the mean is half of run A's growth.
        "context_growth": {"system": 0.0, "tools": 0.0, "user": 0.0,
                           "assistant": 20.0, "tool": 100.0},
    }


def test_summarize_of_an_empty_run_set_matches_hand_computed_arithmetic():
    assert bench.summarize([], ["S08"], 2) == {
        "runs": 0,
        "skipped": 2,
        "successes": 0,
        "success_rate": 0.0,
        "per_scenario": {},
        "totals": {
            "calls": 0, "failed_calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "cached_tokens": 0, "reasoning_tokens": 0, "tool_calls": 0,
            "tool_output_tokens_est": 0, "latency_ms": 0, "cost_usd": None,
            "resent_tokens": 0, "new_tokens": 0, "wall_ms": 0,
        },
        "avg_per_task": {"tokens": 0.0, "rounds": 0.0, "tool_calls": 0.0,
                         "latency_ms": 0.0},
        "cost_per_success": None,
        "tokens_per_success": None,
        "resent_share": 0.0,
        # Nothing reported a cached count at all — null, not zero.
        "cache_hit_rate": None,
        "top_tools": [],
        "top_turn": None,
        "context_growth": {"system": 0.0, "tools": 0.0, "user": 0.0,
                           "assistant": 0.0, "tool": 0.0},
    }


def test_check_accepts_a_self_consistent_document():
    assert bench.check_document(fake_doc()) == (0, "valid")


def test_check_recomputes_every_summary_value():
    document = fake_doc()
    document["summary"]["totals"]["prompt_tokens"] += 1
    code, reason = bench.check_document(document)
    assert code == 1
    assert "summary.totals.prompt_tokens" in reason


def test_check_recomputes_every_run_total():
    document = fake_doc()
    document["runs"][0]["totals"]["latency_ms"] = 999999
    document["summary"] = bench.summarize(document["runs"], [], 1)
    code, reason = bench.check_document(document)
    assert code == 1
    assert "totals.latency_ms" in reason


def test_check_recomputes_the_derived_summary_ratios():
    document = fake_doc()
    document["summary"]["resent_share"] = 0.42
    assert bench.check_document(document)[0] == 1
    document = fake_doc()
    document["summary"]["success_rate"] = 0.5
    assert bench.check_document(document)[0] == 1
    document = fake_doc()
    document["summary"]["top_tools"] = []
    document["runs"][0]["tool_calls"] = [tool_row(1)]
    document["runs"][0]["totals"] = bench.totals_from_rows(
        document["runs"][0]["llm_calls"], document["runs"][0]["tool_calls"], 1000
    )
    assert bench.check_document(document)[0] == 1


def test_check_rejects_an_aborted_file():
    code, reason = bench.check_document(fake_doc(aborted="timeout:S01-1"))
    assert code == 2
    assert "aborted" in reason


def test_check_rejects_invalid_token_counts():
    document = fake_doc()
    document["runs"][0]["llm_calls"][0]["prompt_tokens"] = -5
    document["runs"][0]["totals"] = bench.totals_from_rows(
        document["runs"][0]["llm_calls"], [], 1000)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench.check_document(document)[0] == 3

    document = fake_doc()
    document["runs"][0]["llm_calls"][0]["cached_tokens"] = 5000
    document["runs"][0]["totals"] = bench.totals_from_rows(
        document["runs"][0]["llm_calls"], [], 1000)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    code, reason = bench.check_document(document)
    assert code == 3
    assert "cached_tokens > prompt_tokens" in reason


def test_usage_missing_on_a_successful_run_is_rejected_but_a_failed_call_is_not():
    missing = llm_row(1, prompt=None, completion=None)
    document = fake_doc()
    document["runs"][0]["llm_calls"] = [missing]
    document["runs"][0]["totals"] = bench.totals_from_rows([missing], [], 1000)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    code, reason = bench.check_document(document)
    assert code == 3
    assert "usage_missing" in reason

    failed = llm_row(1, prompt=None, completion=None, error_kind="http")
    document = fake_doc()
    document["runs"][0]["llm_calls"] = [failed]
    document["runs"][0]["totals"] = bench.totals_from_rows([failed], [], 1000)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench.check_document(document) == (0, "valid")
    assert document["runs"][0]["totals"]["failed_calls"] == 1


def test_check_enforces_the_run_set():
    document = fake_doc(repeats=3)
    document["runs"] = [run for run in document["runs"] if run["scenario"] != "S07"]
    document["summary"] = bench.summarize(document["runs"], [], 3)
    code, reason = bench.check_document(document)
    assert code == 1
    assert "missing run" in reason

    document = fake_doc(repeats=3)
    document["runs"].append(copy.deepcopy(document["runs"][7]))
    document["summary"] = bench.summarize(document["runs"], [], 3)
    code, reason = bench.check_document(document)
    assert code == 1
    assert "duplicate run" in reason

    document = fake_doc()
    document["runs"][0]["scenario"] = "S99"
    document["summary"] = bench.summarize(document["runs"], [], 1)
    code, reason = bench.check_document(document)
    assert code == 1
    assert "S99" in reason


def test_check_rejects_a_skip_of_a_non_network_scenario():
    document = fake_doc(skipped=["S01"])
    code, reason = bench.check_document(document)
    assert code == 1
    assert "not a network scenario" in reason


def test_a_narrowed_run_passes_check_and_renders_every_heading(tmp_path, monkeypatch,
                                                               capsys):
    """REQ-V13-AUD-03 and REQ-V13-RSN-02 report on files produced by `--only`,
    so a narrowed run must validate against its own selection."""
    _stub_cli(monkeypatch, tmp_path)
    assert bench.main(["run", "--tag", "smoke", "--only", "S02", "--repeats", "1"]) == 0
    capsys.readouterr()
    path = tmp_path / "assets" / "smoke.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["meta"]["only"] == ["S02"]
    assert [run["scenario"] for run in document["runs"]] == ["S02"]
    assert bench.check_document(document) == (0, "valid")

    out = tmp_path / "smoke.md"
    assert bench.main(["report", "--baseline", str(path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    for heading in ("## Meta", "## Per scenario", "## Totals\n", "## Totals by purpose",
                    "## Audit", "## Reasoning", "## Latency", "## Failures"):
        assert heading in text, heading
    capsys.readouterr()


def test_meta_only_says_missing_when_the_key_is_absent():
    """A document without `meta.only` is not a document with a bad `only`:
    the two failures need two messages (section 7.4)."""
    document = fake_doc()
    del document["meta"]["only"]
    code, missing = bench.check_document(document)
    assert code == 1
    assert "missing" in missing

    document = fake_doc()
    document["meta"]["only"] = []
    _code, malformed = bench.check_document(document)
    assert malformed == "meta.only must be null or a non-empty array of strings"
    assert missing != malformed


def test_meta_only_still_enforces_its_own_run_set():
    document = fake_doc([fake_run("S02", 1)], only=["S02", "S03"])
    code, reason = bench.check_document(document)
    assert code == 1
    assert "missing run" in reason and "S03-1" in reason

    document = fake_doc([fake_run("S02", 1), fake_run("S03", 1)], only=["S02"])
    code, reason = bench.check_document(document)
    assert code == 1
    assert "outside meta.only" in reason

    document = fake_doc([fake_run("S02", 1)], only=["S99"])
    code, reason = bench.check_document(document)
    assert code == 1
    assert "catalog" in reason


def test_gate_refuses_a_full_run_against_a_narrowed_one():
    baseline, candidate = _pair()
    candidate["meta"]["only"] = ["S02"]
    reason = bench.comparability(baseline, candidate)
    assert reason is not None and "only" in reason


def test_check_rejects_a_stale_scenarios_hash():
    document = fake_doc(scenarios_sha256="0" * 64)
    code, reason = bench.check_document(document)
    assert code == 1
    assert "scenarios_sha256" in reason


def test_check_validates_the_pricing_snapshot():
    manual = {"basis": "manual", "model": None, "input_usd_per_mtok": 1.0,
              "output_usd_per_mtok": 2.0, "cached_input_usd_per_mtok": None,
              "fetched_at": None}
    assert bench.check_document(fake_doc(pricing=manual)) == (0, "valid")
    assert bench.check_document(fake_doc(pricing=None)) == (0, "valid")

    stale = {**PRICING, "basis": "openrouter-list", "fetched_at": None}
    assert bench.check_document(fake_doc(pricing=stale))[0] == 1
    negative = {**PRICING, "input_usd_per_mtok": -1.0}
    assert bench.check_document(fake_doc(pricing=negative))[0] == 1


def test_conv_seq_resets_the_resent_arithmetic_at_a_new_conversation():
    rows = [llm_row(1, conv_seq=1, prompt=100), llm_row(2, conv_seq=1, prompt=300),
            llm_row(3, conv_seq=2, prompt=120), llm_row(4, conv_seq=2, prompt=400)]
    totals = bench.totals_from_rows(rows, [], 1000)
    # per group: (100 new) + (200 new, 100 re-sent); (120 new) + (280 new, 120 re-sent)
    assert totals["resent_tokens"] == 220
    assert totals["new_tokens"] == 700
    assert totals["resent_tokens"] + totals["new_tokens"] == totals["prompt_tokens"]

    document = fake_doc()
    document["runs"][0]["llm_calls"] = rows
    document["runs"][0]["totals"] = dict(totals)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench.check_document(document) == (0, "valid")

    # A writer that computed the metric over the flat row list would report the
    # single-conversation figure; `check` recomputes per group and refuses it.
    flat_resent, flat_new = bench.metrics.resent_tokens(rows)
    assert flat_resent != totals["resent_tokens"]
    document["runs"][0]["totals"]["resent_tokens"] = flat_resent
    document["runs"][0]["totals"]["new_tokens"] = flat_new
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench.check_document(document)[0] == 1


def test_check_rejects_a_row_missing_a_column():
    document = fake_doc()
    document["runs"][0]["llm_calls"][0].pop("cost_basis")
    code, reason = bench.check_document(document)
    assert code == 1
    assert "row columns" in reason


# --------------------------------------------------------------------------
# `report` and `--gate` (REQ-V13-BEN-14, section 13.3)
# --------------------------------------------------------------------------

def _pair(*, candidate_prompt=600, candidate_completion=60, repeats=1,
          candidate_extra_rows=(), candidate_success=True):
    baseline = fake_doc(repeats=repeats)
    runs = []
    for scenario in SCENARIOS:
        for repeat in range(1, repeats + 1):
            rows = [llm_row(1, prompt=candidate_prompt, completion=candidate_completion)]
            rows += [copy.deepcopy(row) for row in candidate_extra_rows]
            runs.append(fake_run(scenario.id, repeat, llm_rows=rows,
                                 success=candidate_success))
    candidate = fake_doc(runs, repeats=repeats, flags=CANDIDATE_FLAGS, tag="optimized")
    return baseline, candidate


def test_report_renders_every_required_heading():
    baseline, candidate = _pair()
    text = bench.render_report(baseline, candidate)
    for heading in ("## Meta", "## Per scenario", "## Totals\n", "## Totals by purpose",
                    "## Audit", "## Reasoning", "## Latency", "## Failures", "## Verdict"):
        assert heading in text, heading
    assert "env_flags.HISTORY_TOOL_STUB" in text
    assert "pricing.basis" in text


def test_report_of_a_single_file_has_no_verdict():
    text = bench.render_report(fake_doc())
    assert "## Verdict" not in text
    assert "## Failures" in text


def test_report_totals_by_purpose_and_latency_are_recomputed():
    rows = [llm_row(1, purpose="agent", prompt=100, completion=10, latency=200),
            llm_row(2, purpose="agent", prompt=300, completion=20, latency=400),
            llm_row(3, purpose="summary", prompt=50, completion=5, latency=600)]
    document = fake_doc()
    document["runs"][0]["llm_calls"] = rows
    document["runs"][0]["totals"] = bench.totals_from_rows(rows, [], 1000)
    document["summary"] = bench.summarize(document["runs"], [], 1)
    assert bench._purpose_value(document, "agent", "calls") == 2 + (len(document["runs"]) - 1)
    assert bench._purpose_value(document, "summary", "calls") == 1
    assert bench._purpose_value(document, "summary", "prompt_tokens") == 50
    assert bench._median_latency(document, "summary") == 600


def test_prefix_share_has_one_shared_implementation():
    """REQ-V13-OBS-08: the report and the dashboard read the same function."""
    document = fake_doc(runs=[fake_run("S01", 1, llm_rows=[llm_row(1, prompt=1000)])],
                        prefix_tokens=250)
    assert metrics.prefix_share(document) == 0.25
    assert metrics.prefix_share(fake_doc(prefix_tokens=None)) is None
    assert not hasattr(bench, "_prefix_share")
    assert "prefix_share" in bench.render_report(document)


def test_report_reasoning_block_splits_by_tools_exposed():
    """REQ-V13-BEN-14 / REQ-V13-RSN-02: the split is tools exposed vs withheld,
    and a tool-exposed agent round carries the *whole* toolset — `tools_exposed`
    is a count, never a flag, so the group must be selected with `> 0`."""
    rows = [
        llm_row(1, reasoning=0, tools_exposed=3),
        llm_row(2, reasoning=42, reasoning_chars=130, tools_exposed=3),
        llm_row(3, reasoning=0, tools_exposed=0),
    ]
    document = fake_doc(runs=[fake_run("S01", 1, llm_rows=rows)])
    text = bench.render_report(document)
    assert ("- reasoning observed: yes, max reasoning_tokens: 42, "
            "max reasoning_chars: 130, \u03a3 reasoning_tokens: 42, "
            "reasoning share: 0.1400") in text
    assert ("- tool-exposed calls: calls: 2, reasoning observed: yes, "
            "max reasoning_tokens: 42, max reasoning_chars: 130, "
            "\u03a3 reasoning_tokens: 42, reasoning share: 0.2100") in text
    # A provider that honestly reports zero renders 0.0000, never `n/a`.
    assert ("- tools-withheld calls: calls: 1, reasoning observed: no, "
            "max reasoning_tokens: 0, max reasoning_chars: 0, "
            "\u03a3 reasoning_tokens: 0, reasoning share: 0.0000") in text


def test_report_reasoning_share_is_chars_only_when_no_row_reports_tokens():
    """Section 7.8: `n/a (chars only: N)` is the branch for *no* row carrying
    `reasoning_tokens` at all — not for rows carrying a zero."""
    rows = [llm_row(1, reasoning=None, reasoning_chars=70),
            llm_row(2, reasoning=None, reasoning_chars=30)]
    text = bench.render_report(fake_doc(runs=[fake_run("S01", 1, llm_rows=rows)]))
    assert "reasoning share: n/a (chars only: 100)" in text

    silent = [llm_row(1, reasoning=None), llm_row(2, reasoning=None)]
    text = bench.render_report(fake_doc(runs=[fake_run("S01", 1, llm_rows=silent)]))
    assert "reasoning observed: no, max reasoning_tokens: 0" in text
    assert "reasoning share: n/a\n" in text


def test_report_reasoning_counts_only_the_error_free_calls_of_a_group():
    rows = [llm_row(1, reasoning=5, tools_exposed=3),
            llm_row(2, reasoning=5, tools_exposed=3, error_kind="timeout"),
            llm_row(3, reasoning=5, tools_exposed=0, error_kind="http_5xx")]
    text = bench.render_report(fake_doc(runs=[fake_run("S01", 1, llm_rows=rows)]))
    assert "- tool-exposed calls: calls: 1, " in text
    assert "- tools-withheld calls: calls: 0, " in text


def test_report_failures_section_truncates_and_says_none():
    assert "none" in bench._failures_section(fake_doc(), None)
    document = fake_doc()
    document["runs"][3] = fake_run(
        document["runs"][3]["scenario"], 1, success=False, failure="checks",
        answers=["y" * 400],
        checks=[{"kind": "answer_regex", "ok": False, "detail": "pattern not found"}],
    )
    document["summary"] = bench.summarize(document["runs"], [], 1)
    section = bench._failures_section(document, None)
    assert document["runs"][3]["scenario"] in section
    assert "answer_regex: pattern not found" in section
    assert "y" * 300 in section
    assert "y" * 301 not in section


@pytest.mark.parametrize("field_name,value", [
    ("provider", "openrouter"), ("model", "other"), ("context_length", 8192),
    ("repeats", 2), ("timeout_s", 300.0), ("scenarios_sha256", "f" * 64),
    ("config_sha256", "d" * 64),
])
def test_gate_refuses_two_files_whose_locked_meta_differs(field_name, value):
    baseline, candidate = _pair()
    candidate["meta"][field_name] = value
    reason = bench.comparability(baseline, candidate)
    assert reason is not None and field_name in reason


def test_gate_refuses_differing_skip_sets(tmp_path):
    baseline, candidate = _pair()
    candidate["meta"]["skipped_scenarios"] = ["S08"]
    assert "skipped_scenarios" in bench.comparability(baseline, candidate)


def test_gate_refuses_a_changed_request_default(tmp_path):
    baseline, candidate = _pair()
    candidate["meta"]["constants"] = copy.deepcopy(candidate["meta"]["constants"])
    candidate["meta"]["constants"]["REQUEST_DEFAULTS"]["temperature"] = 0.7
    assert "constants" in bench.comparability(baseline, candidate)


@pytest.mark.parametrize("side,key,value,needle", [
    ("baseline", "LLM_FAILOVER", "auto", "LLM_FAILOVER"),
    ("candidate", "LLM_FAILOVER", "auto", "LLM_FAILOVER"),
    ("baseline", "LLM_SUMMARY_MODEL", "openrouter:x", "LLM_SUMMARY_MODEL"),
    ("baseline", "LLM_MAX_TOKENS", 1024, "LLM_MAX_TOKENS"),
    ("baseline", "HISTORY_TOOL_STUB", "on", "HISTORY_TOOL_STUB"),
    ("candidate", "HISTORY_TOOL_STUB", "off", "HISTORY_TOOL_STUB"),
    ("candidate", "EXEC_OUTPUT_DEFAULT_CHARS", 1000, "EXEC_OUTPUT_DEFAULT_CHARS"),
    ("candidate", "LLM_REASONING", "off", "LLM_REASONING"),
])
def test_gate_enforces_the_ben_03_treatment_rule(side, key, value, needle):
    baseline, candidate = _pair()
    document = baseline if side == "baseline" else candidate
    document["meta"]["env_flags"][key] = value
    reason = bench.comparability(baseline, candidate)
    assert reason is not None and needle in reason


def test_a_correct_pair_is_comparable():
    baseline, candidate = _pair()
    assert bench.comparability(baseline, candidate) is None
    assert bench.verdict(baseline, candidate).passed is True


def test_the_gate_prices_both_sides_with_the_baseline_snapshot():
    baseline, candidate = _pair(candidate_prompt=1000, candidate_completion=100)
    # Identical tokens: no saving, whatever the candidate's own price list says.
    candidate["meta"]["pricing"] = {**PRICING, "input_usd_per_mtok": 0.01,
                                    "output_usd_per_mtok": 0.01}
    decision = bench.verdict(baseline, candidate)
    assert decision.passed is False
    assert "cost gate" in decision.reason


def test_the_conservative_cost_gate_charges_failed_invocations():
    failed = [llm_row(2, prompt=None, completion=None, error_kind="transport"),
              llm_row(3, prompt=None, completion=None, error_kind="transport")]
    baseline, candidate = _pair(candidate_prompt=600, candidate_completion=50,
                                candidate_extra_rows=failed)
    decision = bench.verdict(baseline, candidate)
    assert decision.passed is False
    text = "\n".join(decision.lines)
    assert "C_plain:" in text and "C_conservative:" in text and "B_plain:" in text
    assert "warning: failed_calls rose 0 → 24" in text

    clean_baseline, clean_candidate = _pair(candidate_prompt=600, candidate_completion=50)
    clean = bench.verdict(clean_baseline, clean_candidate)
    assert clean.passed is True
    assert "warning: failed_calls rose" not in "\n".join(clean.lines)


def test_the_quality_gate_allows_no_lost_run():
    baseline, candidate = _pair(repeats=3, candidate_prompt=100, candidate_completion=10)
    assert bench.verdict(baseline, candidate).passed is True
    lost = candidate["runs"][0]
    candidate["runs"][0] = fake_run(lost["scenario"], lost["repeat"],
                                    llm_rows=lost["llm_calls"], success=False)
    candidate["summary"] = bench.summarize(candidate["runs"], [], 3)
    decision = bench.verdict(baseline, candidate)
    assert decision.passed is False
    assert "quality gate: FAIL" in "\n".join(decision.lines)


def test_a_compensated_aggregate_cannot_hide_a_broken_scenario():
    baseline, candidate = _pair(repeats=3, candidate_prompt=100, candidate_completion=10)
    # baseline: S02 is 1/3, everything else 3/3.
    for index, run in enumerate(baseline["runs"]):
        if run["scenario"] == "S02" and run["repeat"] in (2, 3):
            baseline["runs"][index] = fake_run(
                "S02", run["repeat"], llm_rows=run["llm_calls"], success=False)
    baseline["summary"] = bench.summarize(baseline["runs"], [], 3)
    # candidate: S02 recovers to 3/3 but S03 collapses to 1/3 — same total.
    for index, run in enumerate(candidate["runs"]):
        if run["scenario"] == "S03" and run["repeat"] in (2, 3):
            candidate["runs"][index] = fake_run(
                "S03", run["repeat"], llm_rows=run["llm_calls"], success=False)
    candidate["summary"] = bench.summarize(candidate["runs"], [], 3)
    assert candidate["summary"]["successes"] == baseline["summary"]["successes"]
    decision = bench.verdict(baseline, candidate)
    assert decision.passed is False
    assert "regressed scenarios: S03 3/3 → 1/3" in "\n".join(decision.lines)


def test_no_successful_runs_is_a_fail_not_a_division_by_zero():
    baseline, candidate = _pair()
    candidate["runs"] = [fake_run(run["scenario"], run["repeat"],
                                  llm_rows=run["llm_calls"], success=False)
                         for run in candidate["runs"]]
    candidate["summary"] = bench.summarize(candidate["runs"], [], 1)
    decision = bench.verdict(baseline, candidate)
    assert decision.passed is False
    assert decision.reason == "no successful runs"


def test_without_a_price_snapshot_the_metric_is_tokens():
    baseline, candidate = _pair(candidate_prompt=600, candidate_completion=60)
    baseline["meta"]["pricing"] = None
    candidate["meta"]["pricing"] = None
    decision = bench.verdict(baseline, candidate)
    assert "metric: tokens per successful task" in decision.lines[0]
    assert decision.passed is True


# --------------------------------------------------------------------------
# the CLI (REQ-V13-BEN-01, REQ-V13-BEN-13)
# --------------------------------------------------------------------------

def _write(tmp_path, name, document):
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_cli_check_exit_codes(tmp_path, capsys):
    assert bench.main(["check", str(_write(tmp_path, "ok.json", fake_doc()))]) == 0
    aborted = _write(tmp_path, "aborted.json", fake_doc(aborted="sigint"))
    assert bench.main(["check", str(aborted)]) == 2
    broken = fake_doc()
    broken["summary"]["successes"] = 0
    assert bench.main(["check", str(_write(tmp_path, "bad.json", broken))]) == 1
    missing = tmp_path / "nope.json"
    assert bench.main(["check", str(missing)]) == 1
    capsys.readouterr()


def test_cli_report_gate_exit_codes(tmp_path):
    baseline, candidate = _pair()
    base_path = _write(tmp_path, "baseline.json", baseline)
    cand_path = _write(tmp_path, "optimized.json", candidate)
    out = tmp_path / "report.md"
    code = bench.main(["report", "--baseline", str(base_path), "--candidate",
                       str(cand_path), "--gate", "--out", str(out)])
    assert code == 0
    assert "## Verdict" in out.read_text(encoding="utf-8")

    candidate["meta"]["model"] = "another"
    cand_path = _write(tmp_path, "other.json", candidate)
    assert bench.main(["report", "--baseline", str(base_path), "--candidate",
                       str(cand_path), "--gate"]) == 2

    _, failing = _pair(candidate_prompt=1000, candidate_completion=100)
    fail_path = _write(tmp_path, "failing.json", failing)
    assert bench.main(["report", "--baseline", str(base_path), "--candidate",
                       str(fail_path), "--gate"]) == 1


def test_cli_report_propagates_a_validation_failure(tmp_path):
    document = fake_doc(aborted="timeout:S01-1")
    assert bench.main(["report", "--baseline", str(_write(tmp_path, "a.json", document))]) == 2


def _stub_cli(monkeypatch, tmp_path, *, llm=None, preflight=False):
    cfg = make_config(tmp_path)
    monkeypatch.setattr(bench, "BENCH_ROOT", tmp_path / ".bench")
    monkeypatch.setattr(bench, "DEFAULT_OUT_DIR", tmp_path / "assets")
    monkeypatch.setattr(bench, "INTER_RUN_SLEEP_S", 0.0)
    monkeypatch.setattr(bench, "_base_config", lambda tag, provider: cfg)
    monkeypatch.setattr(bench, "_resolve_pricing", lambda cfg_, client: (None, None))
    monkeypatch.setattr(bench, "_prefix_tokens", lambda client, skills: 900)
    monkeypatch.setattr(bench, "_network_preflight", lambda client: (lambda: preflight))
    monkeypatch.setattr(bench, "_real_runner_factory", lambda run_cfg: RecordingRunner())
    monkeypatch.setattr(bench, "_real_fetcher_factory",
                        lambda client: (lambda run_cfg: FakeFetcher()))
    monkeypatch.setattr(bench.llm_module, "build_llm_client",
                        lambda cfg_, client=None, override=None: llm or ScriptedLLM())
    return cfg


def test_cli_run_console_summary_stays_within_forty_lines(tmp_path, monkeypatch, capsys):
    _stub_cli(monkeypatch, tmp_path)
    out = tmp_path / "assets" / "run.json"
    code = bench.main(["run", "--tag", "run", "--repeats", "1"])
    captured = capsys.readouterr()
    lines = [line for line in (captured.out + captured.err).splitlines() if line]
    assert code == 0
    assert len(lines) <= bench.SUMMARY_LINE_LIMIT
    assert lines[0].startswith("bench run ")
    assert any(line.startswith("skipped: S08") for line in lines)
    assert out.exists()
    log_text = (tmp_path / "assets" / "run.log").read_text(encoding="utf-8")
    assert "llm_call " in log_text
    assert "llm_call " not in captured.out


def test_cli_run_exits_four_on_an_abort(tmp_path, monkeypatch, capsys):
    _stub_cli(monkeypatch, tmp_path)
    recorded = {}
    # `os._exit` flushes nothing: under a pipe the console summary would be
    # discarded with the buffer, so the streams are flushed before it.
    flushed = []
    monkeypatch.setattr(bench.sys.stdout, "flush", lambda: flushed.append("out"))
    monkeypatch.setattr(bench.sys.stderr, "flush", lambda: flushed.append("err"))
    monkeypatch.setattr(bench.os, "_exit",
                        lambda code: recorded.update(code=code, flushed=list(flushed)))
    monkeypatch.setattr(bench.bot, "_reap_orphaned_containers",
                        lambda: recorded.setdefault("reaped", True))
    aborted = bench.BenchResult(
        meta={**fake_doc()["meta"], "aborted": "timeout:S01-1"},
        runs=[fake_run("S01", 1)], summary=bench.summarize([fake_run("S01", 1)], [], 1),
    )
    monkeypatch.setattr(bench, "run_bench", lambda *args, **kwargs: aborted)
    bench.main(["run", "--tag", "aborted"])
    capsys.readouterr()
    assert recorded == {"code": 4, "reaped": True, "flushed": ["out", "err"]}
    assert (tmp_path / "assets" / "aborted.json").exists()


def test_cli_run_reports_usage_missing(tmp_path, monkeypatch, capsys):
    _stub_cli(monkeypatch, tmp_path)
    llm = ScriptedLLM(script=[LLMResponse("плоский ответ", [], "stop", usage=None)])
    monkeypatch.setattr(bench.llm_module, "build_llm_client",
                        lambda cfg_, client=None, override=None: llm)
    code = bench.main(["run", "--tag", "missing", "--only", "S01", "--repeats", "1"])
    capsys.readouterr()
    assert code == 3
    document = json.loads((tmp_path / "assets" / "missing.json").read_text(encoding="utf-8"))
    assert document["runs"][0]["failure"] == "usage_missing"


def test_cli_run_rejects_an_unknown_scenario(tmp_path, monkeypatch):
    _stub_cli(monkeypatch, tmp_path)
    with pytest.raises(SystemExit):
        bench.main(["run", "--tag", "t", "--only", "S99"])


def test_cli_module_runs_as_a_script():
    import subprocess
    import sys as system

    result = subprocess.run(
        [system.executable, str(bench.REPO_ROOT / "devtools" / "bench.py"), "check",
         str(bench.REPO_ROOT / "devtools" / "bench.py")],
        capture_output=True, cwd=str(bench.REPO_ROOT), timeout=120,
    )
    assert result.returncode == 1          # not valid json — but the module imported


# --------------------------------------------------------------------------
# row copying (REQ-V13-BEN-03, section 7.4)
# --------------------------------------------------------------------------

def test_rows_are_copied_without_conv_id_and_numbered_by_first_appearance(tmp_path):
    db_path = tmp_path / "rows.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    first = storage.get_or_create_active_conversation(conn, TG_ID)
    storage.add_llm_call(
        conn, conv_id=first, turn_id=1, purpose="agent", round_no=1, attempt=1,
        ts="t", provider="p", model="m", prompt_chars=10,
        prompt_chars_by_role={"system": 10}, messages_n=1, tools_exposed=1,
        latency_ms=5, prompt_tokens=10, completion_tokens=2,
    )
    second = storage.start_new_conversation(conn, TG_ID)
    storage.add_llm_call(
        conn, conv_id=second, turn_id=1, purpose="agent", round_no=1, attempt=1,
        ts="t", provider="p", model="m", prompt_chars=10,
        prompt_chars_by_role={"system": 10}, messages_n=1, tools_exposed=1,
        latency_ms=5, prompt_tokens=20, completion_tokens=2,
    )
    storage.add_tool_call(
        conn, conv_id=second, turn_id=1, tool_call_id="c1", tool="exec", ts="t",
        input_chars=1, raw_output_chars=2, output_chars=2, output_tokens_est=3,
        duration_ms=4, outcome="ok",
    )
    conn.close()

    llm_rows, tool_rows, goals = bench._read_rows(db_path)
    assert [row["conv_seq"] for row in llm_rows] == [1, 2]
    assert [row["conv_seq"] for row in tool_rows] == [2]
    assert all("conv_id" not in row for row in llm_rows + tool_rows)
    assert set(llm_rows[0]) == set(bench.LLM_ROW_KEYS)
    assert set(tool_rows[0]) == set(bench.TOOL_ROW_KEYS)
    assert goals == []


def test_reading_a_missing_database_degrades_to_no_rows(tmp_path):
    assert bench._read_rows(tmp_path / "absent.db") == ([], [], [])


def test_exit_codes_are_read_from_the_run_audit_log(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        json.dumps({"tool": "exec", "outcome": "ok", "exit_code": 0}) + "\n"
        + json.dumps({"tool": "exec", "outcome": "ok", "exit_code": 1}) + "\n"
        + "not json\n",
        encoding="utf-8",
    )
    assert bench._read_exit_codes(path) == ([0, 1], True)
    assert bench._read_exit_codes(tmp_path / "absent.jsonl") == ([], False)


def test_a_read_only_connection_sees_committed_rows_of_a_live_writer(tmp_path):
    db_path = tmp_path / "live.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    conv = storage.get_or_create_active_conversation(conn, TG_ID)
    storage.add_llm_call(
        conn, conv_id=conv, turn_id=1, purpose="agent", round_no=1, attempt=1, ts="t",
        provider="p", model="m", prompt_chars=1, prompt_chars_by_role={}, messages_n=1,
        tools_exposed=1, latency_ms=1, prompt_tokens=1, completion_tokens=1,
    )
    try:
        # The writer is still open, exactly as an abandoned worker would be.
        llm_rows, _tools, _goals = bench._read_rows(db_path)
        assert len(llm_rows) == 1
    finally:
        conn.close()


def test_summary_goals_are_read_for_the_summary_exists_check(tmp_path):
    db_path = tmp_path / "goals.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    conv = storage.get_or_create_active_conversation(conn, TG_ID)
    storage.add_summary(conn, conv, TG_ID, json.dumps({"goal": "запомнить Orion"}))
    conn.close()
    assert bench._read_rows(db_path)[2] == ["запомнить Orion"]


def test_a_read_only_connection_is_used_for_the_copy(tmp_path, monkeypatch):
    """The main thread must never write through the run's database."""
    opened = []
    original = sqlite3.connect

    def spy(target, *args, **kwargs):
        opened.append(str(target))
        return original(target, *args, **kwargs)

    db_path = tmp_path / "ro.db"
    conn = storage.connect(db_path)
    storage.init_schema(conn)
    conn.close()
    monkeypatch.setattr(sqlite3, "connect", spy)
    bench._read_rows(db_path)
    assert opened == [f"file:{db_path}?mode=ro"]
