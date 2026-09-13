"""spec-v1.10.0 T3 (docs/spec/task-briefs/v1100-T3.md, REQ-V1100-CFG-01): the
judge route configuration -- `LLM_JUDGE_MODEL` / `Config.llm_judge_model` /
`build_llm_client(..., purpose="judge")`, mirroring `LLM_EVAL_CHAT_MODEL`
exactly.

Offline: `load_config(env=..., load_env_file=False)` only, exactly like
`tests/test_config.py` and `tests/test_v190_config.py`.
"""

from pathlib import Path

import httpx
import pytest

from config import ConfigError, load_config
from llm import build_llm_client
from llm.failover import FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.test_config import base_env

# --------------------------------------------------------------------------
# T-V1100-CFG-01 -- defaults and successful routing
# --------------------------------------------------------------------------


def test_t_v1100_cfg_01_default_is_empty():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_judge_model == ""


def test_t_v1100_cfg_01_routes_to_openrouter():
    cfg = load_config(
        env=base_env(
            OPENROUTER_API_KEY="key",
            OPENROUTER_MODEL="cloud/model",
            LLM_JUDGE_MODEL="openrouter:x/y",
        ),
        load_env_file=False,
    )
    assert cfg.llm_judge_model == "openrouter:x/y"


def test_t_v1100_cfg_01_routes_to_lmstudio():
    # base_env() already configures LM Studio (LMSTUDIO_MODEL, and
    # LMSTUDIO_BASE_URL defaults), so no extra overrides are needed.
    cfg = load_config(env=base_env(LLM_JUDGE_MODEL="lmstudio:z"), load_env_file=False)
    assert cfg.llm_judge_model == "lmstudio:z"


# --------------------------------------------------------------------------
# T-V1100-CFG-02 -- negative cases
# --------------------------------------------------------------------------


def test_t_v1100_cfg_02_unknown_provider_is_refused():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_JUDGE_MODEL="foo:bar"), load_env_file=False)
    assert "LLM_JUDGE_MODEL" in str(exc.value)


def test_t_v1100_cfg_02_unconfigured_openrouter_is_refused():
    env = base_env(
        OPENROUTER_API_KEY=None,
        OPENROUTER_MODEL=None,
        LLM_JUDGE_MODEL="openrouter:x",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(env=env, load_env_file=False)
    assert (
        str(exc.value) == "LLM_JUDGE_MODEL routes the judge to openrouter, which is not configured"
    )


def test_t_v1100_cfg_02_empty_model_after_colon_is_refused():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_JUDGE_MODEL="openrouter:"), load_env_file=False)
    assert "LLM_JUDGE_MODEL" in str(exc.value)


# --------------------------------------------------------------------------
# T-V1100-CFG-03 -- the judge purpose (llm/__init__.py)
# --------------------------------------------------------------------------


def test_t_v1100_cfg_03_judge_purpose_gets_the_routed_bare_client():
    cfg = load_config(
        env=base_env(
            OPENROUTER_API_KEY="key",
            OPENROUTER_MODEL="cloud/model",
            LLM_JUDGE_MODEL="openrouter:judge/model",
        ),
        load_env_file=False,
    )
    with httpx.Client() as http:
        routed = build_llm_client(cfg, client=http, purpose="judge")
    assert isinstance(routed, OpenRouterClient)
    assert not isinstance(routed, FailoverLLMClient)
    assert routed.describe() == ("openrouter", "judge/model")


def test_t_v1100_cfg_03_judge_purpose_can_route_to_lmstudio():
    cfg = load_config(env=base_env(LLM_JUDGE_MODEL="lmstudio:small"), load_env_file=False)
    with httpx.Client() as http:
        routed = build_llm_client(cfg, client=http, purpose="judge")
    assert isinstance(routed, LMStudioClient)
    assert routed.describe() == ("lmstudio", "small")


def test_t_v1100_cfg_03_unset_falls_through_to_the_main_client():
    cfg = load_config(env=base_env(), load_env_file=False)
    with httpx.Client() as http:
        main = build_llm_client(cfg, client=http)
        judge = build_llm_client(cfg, client=http, purpose="judge")
        agent = build_llm_client(cfg, client=http, purpose="agent")
    assert type(judge) is type(main)
    assert type(agent) is type(main)


def test_t_v1100_cfg_03_agent_purpose_is_unaffected_by_judge_routing():
    cfg = load_config(
        env=base_env(
            OPENROUTER_API_KEY="key",
            OPENROUTER_MODEL="cloud/model",
            LLM_JUDGE_MODEL="openrouter:judge/model",
        ),
        load_env_file=False,
    )
    with httpx.Client() as http:
        agent = build_llm_client(cfg, client=http, purpose="agent")
    # The agent purpose is untouched: llm_judge_model must not leak into it.
    assert isinstance(agent, FailoverLLMClient)
    assert agent.active_provider_name == "lmstudio"


# --------------------------------------------------------------------------
# T-V1100-CFG-04 -- .env.example documentation
# --------------------------------------------------------------------------


def _env_example_text():
    return Path(__file__).resolve().parent.parent.joinpath(".env.example").read_text()


def test_t_v1100_cfg_04_env_example_has_exactly_one_uncommented_line():
    text = _env_example_text()
    lines = text.splitlines()
    expected = "LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1"
    matches = [i for i, line in enumerate(lines) if line == expected]
    assert len(matches) == 1

    idx = matches[0]
    # No other uncommented LLM_JUDGE_MODEL= line exists anywhere else.
    assert sum(1 for line in lines if line.startswith("LLM_JUDGE_MODEL=")) == 1

    # It appears after the LLM_EVAL_CHAT_MODEL block.
    eval_chat_idx = next(i for i, line in enumerate(lines) if "LLM_EVAL_CHAT_MODEL=" in line)
    assert idx > eval_chat_idx

    # Preceded by a two-line `#` comment: the two lines immediately above it
    # are both comment lines.
    assert lines[idx - 1].startswith("#")
    assert lines[idx - 2].startswith("#")


def test_t_v1100_cfg_04_load_config_default_is_still_empty_without_env_var():
    source = dict(base_env())
    assert "LLM_JUDGE_MODEL" not in source
    cfg = load_config(env=source, load_env_file=False)
    assert cfg.llm_judge_model == ""
