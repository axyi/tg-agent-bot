"""spec-v1.9.0 T2 (docs/spec/spec-v1.9.0.md Sec.5, REQ-V190-RET-02): the six
embeddings/retrieval config variables, the pairing rule, and `Config.rag_enabled`.

Offline: `load_config(env=..., load_env_file=False)` only, exactly like
`tests/test_config.py`.
"""

import pytest

from config import ConfigError, load_config
from tests.test_config import base_env


def test_t_v190_ret_02_defaults_are_unset_and_rag_disabled():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.embedding_model == ""
    assert cfg.embedding_dim is None
    assert cfg.rag_enabled is False
    assert cfg.embedding_timeout_s == 60.0
    assert cfg.rag_top_k == 5
    assert cfg.rag_rerank == "on"


def test_t_v190_ret_02_embedding_base_url_defaults_from_lmstudio_stripped():
    cfg = load_config(env=base_env(LMSTUDIO_BASE_URL="http://box:1234/v1/"), load_env_file=False)
    assert cfg.embedding_base_url == "http://box:1234/v1"


def test_t_v190_ret_02_embedding_base_url_explicit_overrides_lmstudio():
    cfg = load_config(
        env=base_env(
            LMSTUDIO_BASE_URL="http://box:1234/v1",
            EMBEDDING_BASE_URL="http://other:9999/v1/",
        ),
        load_env_file=False,
    )
    assert cfg.embedding_base_url == "http://other:9999/v1"


@pytest.mark.parametrize("value", ["ftp://x", "box:1234"])
def test_t_v190_ret_02_embedding_base_url_rejects_bad_scheme(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(EMBEDDING_BASE_URL=value), load_env_file=False)
    assert "EMBEDDING_BASE_URL" in str(exc.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"EMBEDDING_MODEL": "text-embedding-x"},
        {"EMBEDDING_DIM": "768"},
    ],
)
def test_t_v190_ret_02_pair_required_together(overrides):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(**overrides), load_env_file=False)
    assert "EMBEDDING_MODEL and EMBEDDING_DIM must be set together" in str(exc.value)


def test_t_v190_ret_02_pair_set_together_enables_rag():
    cfg = load_config(
        env=base_env(EMBEDDING_MODEL="text-embedding-x", EMBEDDING_DIM="768"),
        load_env_file=False,
    )
    assert cfg.embedding_model == "text-embedding-x"
    assert cfg.embedding_dim == 768
    assert cfg.rag_enabled is True


@pytest.mark.parametrize("value", ["0", "4097", "abc", "-1"])
def test_t_v190_ret_02_embedding_dim_out_of_range(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(EMBEDDING_MODEL="m", EMBEDDING_DIM=value), load_env_file=False)
    assert "EMBEDDING_DIM" in str(exc.value)


@pytest.mark.parametrize("value", ["1", "4096", "768"])
def test_t_v190_ret_02_embedding_dim_in_range(value):
    cfg = load_config(env=base_env(EMBEDDING_MODEL="m", EMBEDDING_DIM=value), load_env_file=False)
    assert cfg.embedding_dim == int(value)


@pytest.mark.parametrize("value", ["0", "-1", "601", "abc"])
def test_t_v190_ret_02_embedding_timeout_invalid(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(EMBEDDING_TIMEOUT_S=value), load_env_file=False)
    assert "EMBEDDING_TIMEOUT_S" in str(exc.value)


def test_t_v190_ret_02_embedding_timeout_valid():
    cfg = load_config(env=base_env(EMBEDDING_TIMEOUT_S="30"), load_env_file=False)
    assert cfg.embedding_timeout_s == 30.0


def test_t_v190_ret_02_llm_timeout_s_default_unaffected_by_parse_timeout_change():
    """Regression for the `_parse_timeout(raw, *, key=, default=)` signature
    change (REQ-V190-EC-05): the one pre-existing caller keeps its own
    key/default (`LLM_TIMEOUT_S`/240.0)."""
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_timeout_s == 240.0


@pytest.mark.parametrize("value", ["0", "11", "abc"])
def test_t_v190_ret_02_rag_top_k_out_of_range(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(RAG_TOP_K=value), load_env_file=False)
    assert "RAG_TOP_K" in str(exc.value)


def test_t_v190_ret_02_rag_top_k_valid():
    cfg = load_config(env=base_env(RAG_TOP_K="10"), load_env_file=False)
    assert cfg.rag_top_k == 10


def test_t_v190_ret_02_rag_rerank_off():
    cfg = load_config(env=base_env(RAG_RERANK="off"), load_env_file=False)
    assert cfg.rag_rerank == "off"


def test_t_v190_ret_02_rag_rerank_rejects_other_values():
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(RAG_RERANK="maybe"), load_env_file=False)
    assert "RAG_RERANK" in str(exc.value)


def test_t_v190_ret_02_twelve_files_style_minimal_env_still_loads():
    """The exact minimal shape the 12 pre-existing test files use (REQ-V190-EC-05):
    no embedding/RAG variable at all, and `load_config` must not raise."""
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.rag_enabled is False
