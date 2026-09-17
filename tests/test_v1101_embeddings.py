"""docs/spec/spec-v1.10.1.md §4 REQ-V1101-EMB-01/-02, §5 REQ-V1101-G5-01/-02,
§11 REQ-V1101-SEC-01, §12 T-V1101-CFG-05, T-V1101-EMB-01...04,
T-V1101-EMB-05A, T-V1101-G5-01...03, T-V1101-ERR-01 rows 1-2, T-V1101-SEC-01:
`EmbeddingsClient`'s optional bearer header, `describe()`'s provider
awareness, the three pre-existing constructor sites, `_live_lmstudio`'s
route rule and `_live_embeddings`'s authenticated-only round-trip.

Row 13 of `T-V1101-ERR-01` (the `db_empty=False` `ConfigError` case) is
pinned in `tests/test_v1101_config.py`'s `T-V1101-EC-02` tests, not
duplicated here.

Offline: every client is built on `httpx.MockTransport` through
`tests.fakes.mock_llm_transport`, exactly like `tests/test_v190_embeddings.py`.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

import bot as bot_module
from config import load_config
from llm.embeddings import EmbeddingError, EmbeddingsClient
from tests.fakes import mock_llm_transport
from tests.test_config import base_env
from tests.test_v190_embeddings import minimal_cfg

REPO_ROOT = Path(__file__).resolve().parent.parent
LMSTUDIO_URL = "http://localhost:1234/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
SECRET_KEY = "sk-or-v1-1101-sentinel-embeddings-key"


def client_for(handler):
    return httpx.Client(transport=mock_llm_transport(handler))


def _no_requests_handler(request):
    raise AssertionError(f"unexpected request: {request.url}")


def _vector_ok_handler(*, dim=2):
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0] * dim}]})

    return handler


# --------------------------------------------------------------------------
# T-V1101-CFG-05 -- the fresh-interpreter import smoke test
# --------------------------------------------------------------------------


def test_t_v1101_cfg_05_fresh_interpreter_import_has_no_cycle():
    result = subprocess.run(
        [sys.executable, "-c", "import config; import llm.embeddings"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# --------------------------------------------------------------------------
# T-V1101-EMB-01/-02 -- the optional bearer header
# --------------------------------------------------------------------------


def test_t_v1101_emb_01_nonempty_key_sends_bearer_header_body_unchanged():
    seen = []

    def handler(request):
        seen.append(request)
        return _vector_ok_handler()(request)

    emb = EmbeddingsClient(
        OPENROUTER_URL, "m", 2, 5.0, client_for(handler), api_key="sk-secret-header-key"
    )
    vectors = emb.embed(["hi"])
    assert vectors == [[0.0, 0.0]]
    request = seen[0]
    assert request.headers["authorization"] == "Bearer sk-secret-header-key"
    body = json.loads(request.read())
    assert body == {"model": "m", "input": ["hi"]}


def test_t_v1101_emb_02_empty_key_sends_no_header():
    seen = []

    def handler(request):
        seen.append(request)
        return _vector_ok_handler()(request)

    emb = EmbeddingsClient(LMSTUDIO_URL, "m", 2, 5.0, client_for(handler), api_key="")
    emb.embed(["hi"])
    assert "authorization" not in seen[0].headers


def test_t_v1101_emb_02_positional_construction_still_works_no_header():
    # tests/test_v190_embeddings.py's existing 5-positional-argument call
    # sites must keep constructing a valid client -- `api_key` defaults to
    # "" and sends no header.
    seen = []

    def handler(request):
        seen.append(request)
        return _vector_ok_handler()(request)

    emb = EmbeddingsClient(LMSTUDIO_URL, "m", 2, 5.0, client_for(handler))
    emb.embed(["hi"])
    assert "authorization" not in seen[0].headers


# --------------------------------------------------------------------------
# T-V1101-EMB-03 / T-V1101-CFG-04 (the `describe()` half) -- provider-aware
# describe() and the span attribute that follows it
# --------------------------------------------------------------------------


def test_t_v1101_emb_03_describe_by_host():
    openrouter = EmbeddingsClient(OPENROUTER_URL, "m", 2, 5.0, client_for(_no_requests_handler))
    lmstudio = EmbeddingsClient(LMSTUDIO_URL, "m", 2, 5.0, client_for(_no_requests_handler))
    assert openrouter.describe() == ("openrouter", "m")
    assert lmstudio.describe() == ("lmstudio", "m")


def test_t_v1101_emb_03_span_attribute_follows_describe(monkeypatch):
    import tracing

    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    emb = EmbeddingsClient(OPENROUTER_URL, "m", 2, 5.0, client_for(_vector_ok_handler()))
    emb.embed(["hi"])
    assert captured["span"].attributes["gen_ai.provider.name"] == "openrouter"


@pytest.mark.parametrize(
    "url,is_openrouter",
    [
        ("https://openrouter.ai", True),
        ("https://openrouter.ai/api/v1/", True),
        ("https://OPENROUTER.AI/api/v1", True),
        ("http://openrouter.ai/api/v1", False),
        ("https://openrouter.ai.evil/api/v1", False),
        ("https://notopenrouter.ai/api/v1", False),
    ],
)
def test_t_v1101_cfg_04_embedding_api_key_iff_describe_is_openrouter(url, is_openrouter):
    cfg = load_config(
        env=base_env(OPENROUTER_API_KEY=SECRET_KEY, EMBEDDING_BASE_URL=url), load_env_file=False
    )
    emb = EmbeddingsClient(
        cfg.embedding_base_url,
        "m",
        2,
        5.0,
        client_for(_no_requests_handler),
        api_key=cfg.embedding_api_key,
    )
    assert (cfg.embedding_api_key != "") == is_openrouter
    assert (emb.describe()[0] == "openrouter") == is_openrouter


# --------------------------------------------------------------------------
# T-V1101-EMB-04 / T-V1101-ERR-01 rows 1-2 / T-V1101-SEC-01 -- error
# messages carry status codes and shapes only, never the key
# --------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
def test_t_v1101_err_01_row1_auth_error_message_has_no_key(status):
    emb = EmbeddingsClient(
        OPENROUTER_URL,
        "m",
        2,
        5.0,
        client_for(lambda r: httpx.Response(status, text="nope")),
        api_key="sk-secret-leak-key",
    )
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["hi"])
    assert str(exc.value) == f"embeddings http {status}"
    assert "sk-secret-leak-key" not in str(exc.value)
    assert "sk-secret-leak-key" not in repr(exc.value)


def test_t_v1101_err_01_row2_dimension_mismatch_message():
    emb = EmbeddingsClient(LMSTUDIO_URL, "m", 8, 5.0, client_for(_vector_ok_handler(dim=3)))
    with pytest.raises(EmbeddingError, match=r"^embeddings dimension 3 != 8$"):
        emb.embed(["hi"])


def test_t_v1101_sec_01_key_never_appears_in_describe():
    emb = EmbeddingsClient(
        OPENROUTER_URL, "m", 2, 5.0, client_for(_no_requests_handler), api_key="sk-secret-leak-key"
    )
    provider, model = emb.describe()
    assert "sk-secret-leak-key" not in (provider, model)
    assert "sk-secret-leak-key" not in repr(emb.describe())


# --------------------------------------------------------------------------
# T-V1101-EMB-05A -- the three pre-existing constructor sites
# --------------------------------------------------------------------------


def _embeddings_client_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "EmbeddingsClient"
    ]


def test_t_v1101_emb_05a_three_constructor_sites_pass_the_configured_key():
    bot_calls = _embeddings_client_calls(REPO_ROOT / "bot.py")
    rag_eval_calls = _embeddings_client_calls(REPO_ROOT / "devtools" / "rag_eval.py")
    # bot.py carries exactly two constructor sites at T1 (`_live_embeddings`,
    # `main()`); the fourth site in the whole tree (the gate-8 runner) is
    # T3's job, not this file's.
    assert len(bot_calls) == 2
    assert len(rag_eval_calls) == 1
    for call in [*bot_calls, *rag_eval_calls]:
        keys = {kw.arg: kw.value for kw in call.keywords}
        assert "api_key" in keys, f"line {call.lineno} is missing api_key="
        assert ast.unparse(keys["api_key"]) == "cfg.embedding_api_key"


# --------------------------------------------------------------------------
# T-V1101-G5-01/-02 -- _live_lmstudio's route rule
# --------------------------------------------------------------------------


def test_t_v1101_g5_01_skips_when_nothing_routes_to_it(capsys):
    cfg = minimal_cfg(
        llm_provider="openrouter",
        llm_summary_model="",
        llm_rerank_model="",
        llm_eval_chat_model="",
        llm_judge_model="",
    )
    code = bot_module._live_lmstudio(cfg, client_for(_no_requests_handler))
    out = capsys.readouterr().out
    assert code == 0
    assert out == "live: SKIP lmstudio (no route uses it)\n"


def test_t_v1101_g5_02_runs_and_succeeds_when_provider_is_lmstudio(capsys):
    cfg = minimal_cfg()  # llm_provider == "lmstudio" by default
    code = bot_module._live_lmstudio(
        cfg, client_for(lambda r: httpx.Response(200, json={"data": [{"id": "m"}]}))
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out == "live: OK lmstudio\n"


def test_t_v1101_g5_02_runs_and_fails_when_provider_is_lmstudio(capsys):
    cfg = minimal_cfg()
    code = bot_module._live_lmstudio(cfg, client_for(lambda r: httpx.Response(500, text="boom")))
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL lmstudio" in out


def test_t_v1101_g5_02_runs_when_a_purpose_routes_to_it_despite_other_provider(capsys):
    cfg = minimal_cfg(llm_provider="openrouter", llm_rerank_model="lmstudio:small")
    code = bot_module._live_lmstudio(
        cfg, client_for(lambda r: httpx.Response(200, json={"data": [{"id": "m"}]}))
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out == "live: OK lmstudio\n"


def test_t_v1101_g5_02_can_still_fail_when_a_purpose_routes_to_it(capsys):
    cfg = minimal_cfg(llm_provider="openrouter", llm_judge_model="lmstudio:small")
    code = bot_module._live_lmstudio(
        cfg, client_for(lambda r: httpx.Response(200, json={"data": [{"id": "other-model"}]}))
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL lmstudio" in out
    assert "m is not loaded" in out


# --------------------------------------------------------------------------
# T-V1101-G5-03 -- _live_embeddings: no GET, one authenticated POST
# --------------------------------------------------------------------------


def test_t_v1101_g5_03_one_authenticated_post_no_get_succeeds(capsys):
    seen = []

    def handler(request):
        seen.append(request)
        return _vector_ok_handler(dim=3)(request)

    cfg = minimal_cfg(
        embedding_base_url=OPENROUTER_URL,
        embedding_model="m",
        embedding_dim=3,
        embedding_api_key="sk-secret-g5-03-key",
    )
    code = bot_module._live_embeddings(cfg, client_for(handler))
    out = capsys.readouterr().out
    assert code == 0
    assert out == "live: OK embeddings\n"
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert request.url.path.endswith("/embeddings")
    assert request.headers["authorization"] == "Bearer sk-secret-g5-03-key"


def test_t_v1101_g5_03_dimension_mismatch_fails(capsys):
    cfg = minimal_cfg(
        embedding_base_url=OPENROUTER_URL,
        embedding_model="m",
        embedding_dim=3,
        embedding_api_key="sk-secret-g5-03-key",
    )
    code = bot_module._live_embeddings(cfg, client_for(_vector_ok_handler(dim=4)))
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL embeddings" in out
    assert "embeddings dimension 4 != 3" in out
