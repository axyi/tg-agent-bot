import pytest

import config
from config import ConfigError, load_config

TOKEN = "123456789:sentinel-telegram-token-value"
OR_KEY = "sk-or-sentinel-api-key-value"


def base_env(**overrides):
    env = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "ALLOWED_TG_IDS": "424242",
        "LMSTUDIO_MODEL": "test-model",
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


def test_t_cfg_01_missing_token():
    env = base_env()
    del env["TELEGRAM_BOT_TOKEN"]
    with pytest.raises(ConfigError) as exc:
        load_config(env=env, load_env_file=False)
    assert "TELEGRAM_BOT_TOKEN" in str(exc.value)


@pytest.mark.parametrize("value", ["", ",", "abc", "0", "-5", "1,x"])
def test_t_cfg_02_allowed_ids_invalid(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(ALLOWED_TG_IDS=value), load_env_file=False)
    assert "ALLOWED_TG_IDS" in str(exc.value)


def test_t_cfg_03_allowed_ids_parsed():
    cfg = load_config(env=base_env(ALLOWED_TG_IDS=" 1, 2 ,2 "), load_env_file=False)
    assert cfg.allowed_tg_ids == frozenset({1, 2})


def test_t_cfg_04_openrouter_requires_key():
    env = base_env(LLM_PROVIDER="openrouter", OPENROUTER_MODEL="some/model")
    with pytest.raises(ConfigError) as exc:
        load_config(env=env, load_env_file=False)
    assert "OPENROUTER_API_KEY" in str(exc.value)

    env = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "ALLOWED_TG_IDS": "424242",
        "LLM_PROVIDER": "openrouter",
        "OPENROUTER_API_KEY": OR_KEY,
        "OPENROUTER_MODEL": "some/model",
    }
    cfg = load_config(env=env, load_env_file=False)
    assert cfg.llm_provider == "openrouter"
    assert cfg.openrouter_model == "some/model"


def test_t_cfg_05_provider_normalisation():
    cfg = load_config(env=base_env(LLM_PROVIDER="LMSTUDIO "), load_env_file=False)
    assert cfg.llm_provider == "lmstudio"
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_PROVIDER="ollama"), load_env_file=False)
    assert "LLM_PROVIDER" in str(exc.value)


@pytest.mark.parametrize("value", ["0", "-1", "abc", "601"])
def test_t_cfg_06_timeout_invalid(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_TIMEOUT_S=value), load_env_file=False)
    assert "LLM_TIMEOUT_S" in str(exc.value)


def test_t_cfg_06_timeout_valid():
    cfg = load_config(env=base_env(LLM_TIMEOUT_S="12.5"), load_env_file=False)
    assert cfg.llm_timeout_s == 12.5


def test_t_cfg_07_default_paths_under_project_root(tmp_path):
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.exec_workdir == tmp_path / "sandbox"
    assert cfg.db_path == tmp_path / "bot.db"
    assert cfg.exec_workdir.is_dir()


def test_t_cfg_08_redact():
    load_config(
        env={
            "TELEGRAM_BOT_TOKEN": TOKEN,
            "ALLOWED_TG_IDS": "424242",
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": OR_KEY,
            "OPENROUTER_MODEL": "some/model",
        },
        load_env_file=False,
    )
    text = f"prefix {TOKEN} middle {OR_KEY} suffix"
    redacted = config.redact(text)
    assert TOKEN not in redacted
    assert OR_KEY not in redacted
    assert redacted.count("***REDACTED***") == 2
    assert redacted.startswith("prefix ") and redacted.endswith(" suffix")


def test_t_cfg_09_env_mapping_wins_over_os_environ(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bogus-without-colon")
    monkeypatch.setenv("ALLOWED_TG_IDS", "not-an-id")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.telegram_bot_token == TOKEN
    assert cfg.allowed_tg_ids == frozenset({424242})
    assert cfg.llm_provider == "lmstudio"
