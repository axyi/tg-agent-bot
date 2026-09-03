"""spec-v1.4: honored reasoning control, S01 check repair, errata.

One test per T-V14-* id of section 12.2. Offline discipline unchanged
(REQ-V14-TST-01): no test touches the network, DNS or a real Docker daemon;
every LLM interaction is faked.
"""

import json
import re

import pytest

from config import ConfigError, load_config
from devtools import bench, bench_scenarios
from tests.test_bench import fake_doc, fake_run, make_config
from tests.test_config import base_env


def _s01_answer_regex_pattern() -> str:
    s01 = next(s for s in bench_scenarios.SCENARIOS if s.id == "S01")
    check = next(c for c in s01.checks if c.kind == bench_scenarios.ANSWER_REGEX)
    return check.pattern


_S01_ONLY = [s for s in bench_scenarios.SCENARIOS if s.id == "S01"]

# T-V14-BEN-01: a literal `llm_calls` row shaped exactly like the v1.3
# column set (REQUIRED_LLM_ROW_KEYS) — hand-authored, not derived from
# `bench.REQUIRED_LLM_ROW_KEYS` or `bench.LLM_ROW_KEYS`.
_V13_SHAPED_LLM_ROW = {
    "id": 1, "conv_seq": 1, "turn_id": 1, "purpose": "agent", "round": 1,
    "attempt": 1, "ts": "2026-01-01T00:00:00Z", "provider": "lmstudio",
    "model": "m", "prompt_tokens": 100, "completion_tokens": 20,
    "total_tokens": 120, "cached_tokens": None, "reasoning_tokens": None,
    "reasoning_chars": 0, "prompt_chars": 300, "prompt_chars_by_role": "{}",
    "messages_n": 2, "tools_exposed": 3, "latency_ms": 500,
    "finish_reason": "stop", "tool_calls_n": 0, "error_kind": None,
    "cost_usd": None, "cost_basis": None,
}


def test_t_v14_ben_01_row_key_rule_accepts_a_v13_shaped_row():
    """T-V14-BEN-01 (BEN-03): a v1.3-shaped fixture row (no
    reasoning_requested/reasoning_honored — those land later, OBS-01)
    validates; a row missing a required key is rejected naming it; a row
    with an unknown key is rejected naming it."""
    valid = fake_doc([fake_run("S01", llm_rows=[dict(_V13_SHAPED_LLM_ROW)])],
                     repeats=1)
    assert bench.check_document(valid, _S01_ONLY) == (0, "valid")

    missing_row = {k: v for k, v in _V13_SHAPED_LLM_ROW.items() if k != "cost_basis"}
    missing = fake_doc([fake_run("S01", llm_rows=[missing_row])], repeats=1)
    code, reason = bench.check_document(missing, _S01_ONLY)
    assert code == 1
    assert "cost_basis" in reason

    unknown_row = {**_V13_SHAPED_LLM_ROW, "not_a_real_column": 1}
    unknown = fake_doc([fake_run("S01", llm_rows=[unknown_row])], repeats=1)
    code, reason = bench.check_document(unknown, _S01_ONLY)
    assert code == 1
    assert "not_a_real_column" in reason


def test_t_v14_ben_02_env_flags_holds_nine_keys_null_for_a_stage_a_config(tmp_path):
    """T-V14-BEN-02 (BEN-05): `meta.env_flags` holds nine keys; a
    stage-A-shaped `Config` (both policy fields absent — the running tree
    has no such fields yet) yields `null` for both."""
    flags = bench.env_flags(make_config(tmp_path))
    assert len(flags) == 9
    assert set(flags) == {
        "HISTORY_TOOL_STUB", "EXEC_OUTPUT_DEFAULT_CHARS",
        "FETCH_INLINE_DEFAULT_CHARS", "LLM_REASONING", "LLM_SUMMARY_MODEL",
        "LLM_FAILOVER", "LLM_MAX_TOKENS", "LLM_REASONING_POLICY",
        "LLM_REASONING_ON_PURPOSES",
    }
    assert flags["LLM_REASONING_POLICY"] is None
    assert flags["LLM_REASONING_ON_PURPOSES"] is None


def test_t_v14_ben_03_constants_and_summarize_are_policy_independent():
    """T-V14-BEN-03 (BEN-04): `meta.constants` is byte-equal between two
    calls (the function takes no `Config`/policy argument by construction,
    so nothing a reasoning policy could vary reaches it), and
    `summarize()`'s output is unchanged for a v1.3-shaped document (no
    `reasoning_requested`/`reasoning_honored` columns anywhere in its rows)."""
    assert json.dumps(bench.constants(), sort_keys=True) == json.dumps(
        bench.constants(), sort_keys=True
    )
    assert "reasoning" not in {key.lower() for key in bench.constants()}
    assert "reasoning" not in {
        key.lower() for key in bench.llm_base.REQUEST_DEFAULTS
    }

    run = fake_run("S01", llm_rows=[dict(_V13_SHAPED_LLM_ROW)])
    summary = bench.summarize([run], [], 1)
    assert summary["runs"] == 1
    assert summary["successes"] == 1
    assert summary["totals"]["prompt_tokens"] == 100
    assert summary["totals"]["completion_tokens"] == 20


def test_t_v14_rel_01_timeout_max_tokens_boundary():
    """T-V14-REL-01 (REL-01): `load_config` rejects an `LLM_TIMEOUT_S` /
    `LLM_MAX_TOKENS` pair under the latency-model floor
    (21.1 + 0.093 * max_tokens, report-v1.3.md:340) — the old v1.3
    default (120, 2048) itself now fails, naming both variables in the
    error text; so does a max_tokens too large for a fixed timeout. The
    shipped default (240, 2048) and the spec's own ceiling example
    (600, 6224) both load cleanly."""
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_TIMEOUT_S="120"), load_env_file=False)
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_MAX_TOKENS" in message

    with pytest.raises(ConfigError) as exc:
        load_config(
            env=base_env(LLM_TIMEOUT_S="240", LLM_MAX_TOKENS="8192"),
            load_env_file=False,
        )
    message = str(exc.value)
    assert "LLM_TIMEOUT_S" in message and "LLM_MAX_TOKENS" in message

    cfg = load_config(
        env=base_env(LLM_TIMEOUT_S="600", LLM_MAX_TOKENS="6224"), load_env_file=False
    )
    assert cfg.llm_timeout_s == 600.0 and cfg.llm_max_tokens == 6224

    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_timeout_s == 240.0 and cfg.llm_max_tokens == 2048


def test_t_v14_scn_01_s01_check_accepts_capability_paraphrase():
    """T-V14-SCN-01 (SCN-03, H1 branch only): the repaired S01 check passes
    on each of the three recorded v1.3 candidate answers
    (docs/assets/bench/optimized.json, S01 runs 1-3) and on the baseline's
    passing answers (docs/assets/bench/baseline.json, S01 runs 1-2), and
    still fails on an off-topic or refusing answer. Inlined as literals, per
    the requirement, never read from a benchmark file."""
    pattern = _s01_answer_regex_pattern()

    v13_candidate_answers = [
        "Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, "
        "писать и редактировать тексты, переводить, помогать с кодом, "
        "анализировать информацию и рассуждать над сложными задачами. Также "
        "у меня есть инструменты: могу узнать погоду в любом городе и "
        "рассказать о среде, в которой работаю. Чем помочь?",
        "Привет! Я — большая языковая модель Qwen. Могу отвечать на вопросы, "
        "писать и редактировать тексты, переводить, помогать с кодом, "
        "анализировать информацию и рассуждать над сложными задачами. Также "
        "у меня есть инструменты: могу узнать погоду в любом городе и "
        "рассказать о среде, в которой работаю. Чем помочь?",
        "Привет! Я отвечаю на вопросы, помогаю с текстами, переводами и "
        "идеями. Могу показать погоду и прогноз для любого города, запустить "
        "команды в изолированном Linux-контейнере и рассказать о его "
        "окружении. Спроси что-нибудь конкретное!",
    ]
    for answer in v13_candidate_answers:
        assert re.search(pattern, answer, re.I | re.S), answer

    v13_baseline_answers = [
        "Привет! Вот что я умею:\n\n- Отвечать на вопросы и объяснять темы\n"
        "- Показывать погоду и прогноз для любого города\n- Рассказывать о "
        "среде, в которой я работаю (контейнер, диск, Python)\n- Запускать "
        "программы в изолированном контейнере\n- Получать данные из сети по "
        "разрешённым адресам\n\nСпрашивай — помогу.",
        "Привет! Я умею:\n\n- Отвечать на вопросы и помогать с текстами, "
        "идеями, переводами\n- Показывать погоду и прогноз для любого "
        "города\n- Рассказывать о среде, в которой работаю (система, диск, "
        "Python)\n- Выполнять простые команды в изолированном контейнере\n\n"
        "Спрашивай — помогу!",
    ]
    for answer in v13_baseline_answers:
        assert re.search(pattern, answer, re.I | re.S), answer

    off_topic = (
        "Сегодня хорошая погода, а как у тебя дела? Расскажи о своих планах "
        "на выходные."
    )
    refusing = "Извините, я не могу ответить на этот вопрос."
    assert re.search(pattern, off_topic, re.I | re.S) is None
    assert re.search(pattern, refusing, re.I | re.S) is None
