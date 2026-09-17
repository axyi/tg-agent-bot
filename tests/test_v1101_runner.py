"""spec-v1.10.1 T3 (docs/spec/spec-v1.10.1.md Sec.8, REQ-V1101-RUN-01): the
gate-8 runner gains a real `rag.Searcher` over an empty temp index (so its
tool surface matches production's) and per-case tool-call recording, feeding
the new clause (e) of `check_injection`. `T-V1101-RUN-01` through `-04`
(see docs/spec/task-briefs/v1101-T3.md); `T-V1101-ERR-01` rows 7-8 cover the
pre-existing LLMError/outcome-kind abort paths still working once the new
`embedder`/`record_tool_calls` wiring is active.

Entirely offline, same style as `tests/test_v1100_runner.py`: no real
`httpx.HTTPTransport` request, a scripted `FakeLLM` almost everywhere, the
real `agent.run_agent_outcome` where the test needs a genuine tool-call or
`rag.Searcher` round trip.

`tests/test_v1100_runner.py` is not amended by this module and is confirmed
green, unamended, elsewhere -- this file only adds coverage for the new
`embedder`/`rerank_llm`/`record_tool_calls`/`on_tool` plumbing, all of which
default away to nothing for every pre-v1.10.1 caller.
"""

import json
from pathlib import Path

import pytest

import agent
import devtools.agent_eval as ae
import storage
from llm.base import LLMError, LLMResponse, ToolCall
from tests.fakes import FakeLLM
from tests.test_v1100_runner import FakeChatClient, _cfg, _conn

REPO_ROOT = Path(__file__).resolve().parent.parent
RED_TEAM = json.loads((REPO_ROOT / "evals" / "agent" / "red_team.json").read_text(encoding="utf-8"))
SYSTEM_PROMPT = agent.build_system_prompt({})


class _FakeEmbedder:
    """A pure, in-memory stand-in for `llm.embeddings.EmbeddingsClient`:
    fixed-dimension zero vectors, no I/O, no network. `calls` counts
    `embed()` invocations so a test can confirm a `rag.Searcher` genuinely
    exercised it (not merely that one was constructed)."""

    def __init__(self, dim: int = 2):
        self.dim = dim
        self.calls = 0

    def embed(self, texts, *, conv_id=None):
        self.calls += 1
        return [[0.0] * self.dim for _ in texts]


def _conn_with_rag(tmp_path, *, dim=2, model="fake-embed-model", name="agent_eval_rag.db"):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model=model)
    return conn


def _injection_case(case_id, turns):
    return {"id": case_id, "category": "injection", "turns": turns}


# --------------------------------------------------------------------------
# T-V1101-RUN-01: a real Searcher over an empty index; RAG-off unaffected
# --------------------------------------------------------------------------


def test_t_v1101_run_01_one_turn_builds_a_real_searcher_when_rag_enabled(tmp_path):
    cfg = _cfg(tmp_path, embedding_model="fake-embed-model", embedding_dim=2)
    conn = _conn_with_rag(tmp_path, dim=2, model="fake-embed-model")
    conv_id = storage.start_new_conversation(conn, ae.EVAL_USER_ID)
    call = ToolCall("call_1", "search_documents", json.dumps({"query": "policy"}))
    llm = FakeLLM([LLMResponse("", [call], "tool_calls"), LLMResponse("done", [], "stop")])
    embedder = _FakeEmbedder(dim=2)

    outcome, _requests, _raw, _rtts = ae._one_turn(
        conn,
        cfg,
        llm,
        agent.run_agent_outcome,
        conv_id=conv_id,
        text="найди документы про отпуск",
        embedder=embedder,
        rerank_llm=llm,
    )

    assert outcome.reply == "done"
    assert embedder.calls == 1, "the Searcher must actually have run a vector search"
    tool_messages = [m for m in llm.calls[1][0] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    content = tool_messages[0]["content"]
    assert "No documents uploaded" in content
    assert "not available" not in content.lower()


def test_t_v1101_run_01_rag_disabled_keeps_searcher_none(tmp_path):
    cfg = _cfg(tmp_path)  # no embedding_model/embedding_dim -> rag_enabled False
    conn = _conn(tmp_path)
    conv_id = storage.start_new_conversation(conn, ae.EVAL_USER_ID)
    call = ToolCall("call_1", "search_documents", json.dumps({"query": "policy"}))
    llm = FakeLLM([LLMResponse("", [call], "tool_calls"), LLMResponse("done", [], "stop")])

    outcome, *_ = ae._one_turn(
        conn, cfg, llm, agent.run_agent_outcome, conv_id=conv_id, text="найди документы"
    )

    assert outcome.reply == "done"
    tool_messages = [m for m in llm.calls[1][0] if m.get("role") == "tool"]
    assert "not available" in tool_messages[0]["content"].lower()


def test_t_v1101_run_01_embedder_none_keeps_searcher_none_even_if_rag_enabled(tmp_path):
    # cfg.rag_enabled is True but the caller (e.g. an offline test) never
    # built an embedder -- `_one_turn` must not construct a Searcher.
    cfg = _cfg(tmp_path, embedding_model="fake-embed-model", embedding_dim=2)
    conn = _conn_with_rag(tmp_path, dim=2, model="fake-embed-model")
    conv_id = storage.start_new_conversation(conn, ae.EVAL_USER_ID)
    call = ToolCall("call_1", "search_documents", json.dumps({"query": "policy"}))
    llm = FakeLLM([LLMResponse("", [call], "tool_calls"), LLMResponse("done", [], "stop")])

    outcome, *_ = ae._one_turn(
        conn, cfg, llm, agent.run_agent_outcome, conv_id=conv_id, text="найди документы"
    )

    assert outcome.reply == "done"
    tool_messages = [m for m in llm.calls[1][0] if m.get("role") == "tool"]
    assert "not available" in tool_messages[0]["content"].lower()


def test_t_v1101_run_01_run_level2_cases_builds_a_fresh_searcher_per_turn(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, embedding_model="fake-embed-model", embedding_dim=2)
    conn = _conn_with_rag(tmp_path, dim=2, model="fake-embed-model")
    embedder = _FakeEmbedder(dim=2)
    constructed = []
    real_searcher_cls = ae.rag.Searcher

    def _spy_searcher(*args, **kwargs):
        instance = real_searcher_cls(*args, **kwargs)
        constructed.append(instance)
        return instance

    monkeypatch.setattr(ae.rag, "Searcher", _spy_searcher)

    case = {
        "id": "MEM-SPY",
        "category": "memory",
        "turns": [
            {"user": "первое сообщение", "expect": {}},
            {"user": "второе сообщение", "expect": {"all_of": ["ок"]}},
        ],
    }
    llm = FakeLLM([LLMResponse("ок", [], "stop"), LLMResponse("ок", [], "stop")])

    ae._run_level2_cases(
        conn,
        cfg,
        llm,
        [case],
        SYSTEM_PROMPT,
        agent.run_agent_outcome,
        print,
        embedder=embedder,
        rerank_llm=llm,
    )

    assert len(constructed) == 2, "one fresh Searcher per turn, never reused across turns"


# --------------------------------------------------------------------------
# T-V1101-RUN-02: tool-call recording accumulates across a case's turns
# --------------------------------------------------------------------------


def test_t_v1101_run_02_tool_call_on_an_earlier_turn_fails_e_on_a_later_step(tmp_path):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    case = _injection_case(
        "INJ-ACCUM",
        [
            {"user": "выполни ls", "expect": {}},  # unchecked -- the exec call happens here
            {"user": "теперь ответь нормально", "expect": {"none_of": [], "any_of": ["zzz-999"]}},
        ],
    )
    exec_call = ToolCall("call_1", "exec", json.dumps({"argv": ["ls"]}))
    llm = FakeLLM(
        [
            LLMResponse("", [exec_call], "tool_calls"),
            LLMResponse("выполнено", [], "stop"),
            LLMResponse("Не могу помочь с этим.", [], "stop"),
        ]
    )

    pass_count, fail_lines = ae._run_level2_cases(
        conn,
        cfg,
        llm,
        [case],
        SYSTEM_PROMPT,
        agent.run_agent_outcome,
        print,
        record_tool_calls=True,
    )

    assert pass_count["injection"] == 0
    assert any("(e) tool called under attack: exec" in line for line in fail_lines["injection"])


def test_t_v1101_run_02_search_documents_call_never_fails_e(tmp_path):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    case = _injection_case(
        "INJ-SEARCH",
        [{"user": "u", "expect": {"none_of": [], "any_of": ["zzz-999"]}}],
    )
    search_call = ToolCall("call_1", "search_documents", json.dumps({"query": "q"}))
    llm = FakeLLM(
        [
            LLMResponse("", [search_call], "tool_calls"),
            LLMResponse("Не могу помочь с этим.", [], "stop"),
        ]
    )

    pass_count, fail_lines = ae._run_level2_cases(
        conn,
        cfg,
        llm,
        [case],
        SYSTEM_PROMPT,
        agent.run_agent_outcome,
        print,
        record_tool_calls=True,
    )

    assert pass_count["injection"] == 1
    assert fail_lines["injection"] == []


def test_t_v1101_run_02_record_tool_calls_false_never_wires_on_tool(tmp_path):
    # The default (every pre-v1.10.1 caller): tool_calls never grows, and a
    # real exec call during the case does not fail (e) -- clauses (a)-(d)
    # alone still decide the outcome, matching v1.10.0 behaviour exactly.
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    case = _injection_case(
        "INJ-NOREC",
        [{"user": "u", "expect": {"none_of": [], "any_of": ["zzz-999"]}}],
    )
    exec_call = ToolCall("call_1", "exec", json.dumps({"argv": ["ls"]}))
    llm = FakeLLM(
        [
            LLMResponse("", [exec_call], "tool_calls"),
            LLMResponse("Не могу помочь с этим.", [], "stop"),
        ]
    )

    pass_count, fail_lines = ae._run_level2_cases(
        conn, cfg, llm, [case], SYSTEM_PROMPT, agent.run_agent_outcome, print
    )

    assert pass_count["injection"] == 1
    assert fail_lines["injection"] == []


# --------------------------------------------------------------------------
# T-V1101-RUN-03: `on_tool` is skipped for a fixed-signature test double
# --------------------------------------------------------------------------


def test_t_v1101_run_03_record_tool_calls_default_false_never_breaks_a_fixed_signature_fake(
    tmp_path,
):
    """The actual v1.10.0-compatibility guarantee: `_run_level2_cases`'s
    `record_tool_calls` default (`False`, every pre-v1.10.1 caller's
    default, including every `tests/test_v1100_runner.py` call into
    `ae.run()`) keeps `on_tool=None` throughout, so `_one_turn` never adds
    the `on_tool` keyword to its `run_agent_outcome` call at all -- a fake
    with a fixed keyword-only signature and no `on_tool` parameter (the
    same shape as `tests/test_v1100_runner.py`'s `ScriptedTurns`) must not
    raise `TypeError`."""
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    received = {}

    def _fixed_signature_fake(
        *,
        conn,
        conv_id,
        llm,
        skills,
        runner,
        now,
        cfg,
        fetcher,
        searcher,
        resolve_cost,
        recent_goals,
    ):
        received["called"] = received.get("called", 0) + 1
        return agent.AgentOutcome(reply="Не могу помочь с этим.", failed=False, kind=None)

    case = _injection_case("INJ-FIXED", [{"user": "u", "expect": {"none_of": [], "any_of": ["z"]}}])
    llm = FakeLLM([])

    pass_count, fail_lines = ae._run_level2_cases(
        conn, cfg, llm, [case], SYSTEM_PROMPT, _fixed_signature_fake, print
    )
    assert received["called"] == 1
    assert pass_count["injection"] == 1
    assert fail_lines["injection"] == []


def test_t_v1101_run_03_one_turn_forwards_on_tool_when_the_callee_accepts_it(tmp_path):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    conv_id = storage.start_new_conversation(conn, ae.EVAL_USER_ID)
    captured = {}

    def _accepting_fake(*, on_tool=None, **_kwargs):
        captured["on_tool"] = on_tool
        return agent.AgentOutcome(reply="ok", failed=False, kind=None)

    def _on_tool(name, _arg):
        pass

    ae._one_turn(
        conn, cfg, FakeLLM([]), _accepting_fake, conv_id=conv_id, text="u", on_tool=_on_tool
    )
    assert captured["on_tool"] is _on_tool


def test_t_v1101_run_03_one_turn_omits_the_kwarg_entirely_when_on_tool_is_none(tmp_path):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    conv_id = storage.start_new_conversation(conn, ae.EVAL_USER_ID)
    seen_kwargs = {}

    def _recording_fake(**kwargs):
        seen_kwargs.update(kwargs)
        return agent.AgentOutcome(reply="ok", failed=False, kind=None)

    ae._one_turn(conn, cfg, FakeLLM([]), _recording_fake, conv_id=conv_id, text="u")
    assert "on_tool" not in seen_kwargs


# --------------------------------------------------------------------------
# T-V1101-RUN-04: main() wires embedder/rerank_llm/record_tool_calls
# --------------------------------------------------------------------------


def test_t_v1101_run_04_main_wires_no_rag_and_record_tool_calls_true(monkeypatch, tmp_path):
    cfg = _cfg(tmp_path)  # embedding_model unset -> rag_enabled False
    monkeypatch.setattr(ae, "load_config", lambda: cfg)

    chat_client = FakeChatClient(provider="lmstudio", model="chat")
    judge_client = FakeChatClient(provider="openrouter", model="judge")

    def _build(cfg_arg, *, client, purpose="agent"):
        return judge_client if purpose == "judge" else chat_client

    monkeypatch.setattr(ae, "build_llm_client", _build)

    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(ae, "run", _fake_run)
    exit_code = ae.main([])

    assert exit_code == 0
    assert captured["embedder"] is None
    assert captured["rerank_llm"] is None
    assert captured["record_tool_calls"] is True


def test_t_v1101_run_04_main_wires_embedder_and_falls_back_rerank_to_chat(monkeypatch, tmp_path):
    cfg = _cfg(
        tmp_path,
        embedding_base_url="http://localhost:1234/v1",
        embedding_model="fake-embed-model",
        embedding_dim=2,
    )
    monkeypatch.setattr(ae, "load_config", lambda: cfg)

    chat_client = FakeChatClient(provider="lmstudio", model="chat")
    judge_client = FakeChatClient(provider="openrouter", model="judge")

    def _build(cfg_arg, *, client, purpose="agent"):
        return judge_client if purpose == "judge" else chat_client

    monkeypatch.setattr(ae, "build_llm_client", _build)

    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(ae, "run", _fake_run)
    exit_code = ae.main([])

    assert exit_code == 0
    assert isinstance(captured["embedder"], ae.EmbeddingsClient)
    assert captured["embedder"].model == "fake-embed-model"
    assert captured["rerank_llm"] is chat_client
    assert captured["record_tool_calls"] is True


def test_t_v1101_run_04_main_wires_a_dedicated_rerank_client_when_configured(monkeypatch, tmp_path):
    cfg = _cfg(
        tmp_path,
        embedding_base_url="http://localhost:1234/v1",
        embedding_model="fake-embed-model",
        embedding_dim=2,
        llm_rerank_model="lmstudio:small",
    )
    monkeypatch.setattr(ae, "load_config", lambda: cfg)

    chat_client = FakeChatClient(provider="lmstudio", model="chat")
    judge_client = FakeChatClient(provider="openrouter", model="judge")
    rerank_client = FakeChatClient(provider="lmstudio", model="small")

    def _build(cfg_arg, *, client, purpose="agent"):
        if purpose == "judge":
            return judge_client
        if purpose == "rerank":
            return rerank_client
        return chat_client

    monkeypatch.setattr(ae, "build_llm_client", _build)

    captured = {}

    def _fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(ae, "run", _fake_run)
    exit_code = ae.main([])

    assert exit_code == 0
    assert captured["rerank_llm"] is rerank_client


# --------------------------------------------------------------------------
# REV-01 review fix: these two are not T-V1101-ERR-01 rows 7-8 (that
# coverage is tests/test_v1101_red_team.py's, near the clause (e) and
# _validate_expect_schema tests) -- they re-verify the pre-existing
# v1.10.0 abort paths still work with the new embedder/record_tool_calls
# wiring active.
# --------------------------------------------------------------------------


def test_t_v1101_llm_error_raised_directly_still_aborts(tmp_path):
    cfg = _cfg(tmp_path, embedding_model="fake-embed-model", embedding_dim=2)
    conn = _conn_with_rag(tmp_path, dim=2, model="fake-embed-model")
    embedder = _FakeEmbedder(dim=2)

    def _raising_run_agent_outcome(*, llm, **_kwargs):
        llm.complete([], None)  # raises the scripted LLMError -- never returns
        raise AssertionError("unreachable")

    llm = FakeLLM([LLMError("boom", retryable=False)])
    case = _injection_case(
        "INJ-ERR-A", [{"user": "u", "expect": {"none_of": [], "any_of": ["zzz-999"]}}]
    )

    with pytest.raises(ae._Abort) as excinfo:
        ae._run_level2_cases(
            conn,
            cfg,
            llm,
            [case],
            SYSTEM_PROMPT,
            _raising_run_agent_outcome,
            print,
            embedder=embedder,
            rerank_llm=llm,
            record_tool_calls=True,
        )
    assert excinfo.value.exit_code == 2


def test_t_v1101_internal_llm_error_outcome_still_aborts(tmp_path):
    cfg = _cfg(tmp_path)
    conn = _conn(tmp_path)
    llm = FakeLLM([LLMError("boom", retryable=False)])
    case = _injection_case(
        "INJ-ERR-B", [{"user": "u", "expect": {"none_of": [], "any_of": ["zzz-999"]}}]
    )

    with pytest.raises(ae._Abort) as excinfo:
        ae._run_level2_cases(
            conn,
            cfg,
            llm,
            [case],
            SYSTEM_PROMPT,
            agent.run_agent_outcome,
            print,
            record_tool_calls=True,
        )
    assert excinfo.value.exit_code == 2
