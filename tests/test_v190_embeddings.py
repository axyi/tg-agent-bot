"""spec-v1.9.0 T2 (docs/spec/spec-v1.9.0.md Sec.5, REQ-V190-RET-01, -08):
`llm.embeddings.EmbeddingsClient` -- batching, the retry/timeout
classification, the dimension check, and the one CLIENT span per request --
plus `bot._live_embeddings`, the live-selftest embeddings check.

Offline and deterministic: every client here is built on `httpx.MockTransport`
through `tests.fakes.mock_llm_transport`; no socket is ever reached.

`T-V190-RET-09` is tested here against `bot._live_embeddings` directly, not
through `bot.run_selftest_live`: wiring `failures += _live_embeddings(cfg,
client)` into `run_selftest_live` (as REQ-V190-RET-08 specifies) breaks two
pre-existing tests in `tests/test_v1_guardrails.py`
(`test_t_v1_lv_01_all_checks_pass`, `test_t_v1_lv_01_missing_openrouter_key_is_a_skip`)
that are not in REQ-V190-EC-03's exhaustive amendment list -- disclosed to
the orchestrator, wiring withheld pending its decision (see
`docs/prompts/144-v190-t2-embeddings-config.md`).
"""

import json
from pathlib import Path

import httpx
import pytest

import bot as bot_module
import config
import tracing
from llm.embeddings import EmbeddingError, EmbeddingsClient, EmbeddingTimeoutError
from tests.fakes import mock_llm_transport

BASE_URL = "http://localhost:1234/v1"


def client_for(handler):
    return httpx.Client(transport=mock_llm_transport(handler))


def vector_response(vectors, *, shuffle=False):
    entries = [{"index": i, "embedding": v} for i, v in enumerate(vectors)]
    if shuffle:
        entries = list(reversed(entries))
    return {"data": entries}


def test_t_v190_ret_01_request_shape():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=vector_response([[0.1, 0.2, 0.3]]))

    emb = EmbeddingsClient(BASE_URL, "embed-model", 3, 5.0, client_for(handler))
    vectors = emb.embed(["hello"])
    assert vectors == [[0.1, 0.2, 0.3]]
    request = seen[0]
    assert str(request.url) == f"{BASE_URL}/embeddings"
    body = json.loads(request.read())
    assert body == {"model": "embed-model", "input": ["hello"]}


def test_t_v190_ret_01_describe():
    emb = EmbeddingsClient(BASE_URL, "embed-model", 3, 5.0, client_for(lambda r: None))
    assert emb.describe() == ("lmstudio", "embed-model")


def test_t_v190_ret_01_batches_of_32():
    seen_batches = []

    def handler(request):
        payload = json.loads(request.read())
        batch = payload["input"]
        seen_batches.append(len(batch))
        return httpx.Response(200, json=vector_response([[0.0] * 3] * len(batch)))

    emb = EmbeddingsClient(BASE_URL, "m", 3, 5.0, client_for(handler))
    texts = [f"t{i}" for i in range(65)]
    vectors = emb.embed(texts)
    assert seen_batches == [32, 32, 1]
    assert len(vectors) == 65


def test_t_v190_ret_01_entries_ordered_by_index_not_response_order():
    def handler(request):
        payload = json.loads(request.read())
        n = len(payload["input"])
        vectors = [[float(i)] for i in range(n)]
        return httpx.Response(200, json=vector_response(vectors, shuffle=True))

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    vectors = emb.embed(["a", "b", "c"])
    assert vectors == [[0.0], [1.0], [2.0]]


def test_t_v190_ret_01_http_error():
    emb = EmbeddingsClient(
        BASE_URL, "m", 3, 5.0, client_for(lambda r: httpx.Response(500, text="boom"))
    )
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert str(exc.value) == "embeddings http 500"


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        {},
        {"data": "not a list"},
        {"data": [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [2.0]}]},
    ],
)
def test_t_v190_ret_01_malformed_response(body):
    def handler(request):
        if isinstance(body, str):
            return httpx.Response(200, text=body)
        return httpx.Response(200, json=body)

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert str(exc.value) == "embeddings malformed response"


def test_t_v190_ret_01_non_numeric_vector_elements_are_malformed():
    """A wrong *element* type inside an otherwise correctly-shaped vector
    (e.g. a string instead of a float) must not escape as a bare
    `TypeError`/`ValueError` -- it is `EmbeddingError("embeddings malformed
    response")`, the same as a wrong container type."""
    emb = EmbeddingsClient(
        BASE_URL,
        "m",
        2,
        5.0,
        client_for(lambda r: httpx.Response(200, json=vector_response([[1.0, "oops"]]))),
    )
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert str(exc.value) == "embeddings malformed response"


def test_t_v190_ret_01_dimension_mismatch():
    emb = EmbeddingsClient(
        BASE_URL,
        "m",
        4,
        5.0,
        client_for(lambda r: httpx.Response(200, json=vector_response([[1.0, 2.0]]))),
    )
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert str(exc.value) == "embeddings dimension 2 != 4"


def test_t_v190_ret_01_one_retry_then_success():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("down")
        return httpx.Response(200, json=vector_response([[1.0]]))

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    vectors = emb.embed(["x"])
    assert vectors == [[1.0]]
    assert len(calls) == 2


def test_t_v190_ret_01_retry_exhausted_timeout_raises_timeout_subtype():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    with pytest.raises(EmbeddingTimeoutError) as exc:
        emb.embed(["x"])
    assert str(exc.value) == "embeddings transport error: ReadTimeout"
    assert isinstance(exc.value, EmbeddingError)
    assert isinstance(exc.value.__cause__, httpx.ReadTimeout)


def test_t_v190_ret_01_retry_exhausted_non_timeout_stays_plain_error():
    def handler(request):
        raise httpx.ConnectError("down")

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert not isinstance(exc.value, EmbeddingTimeoutError)
    assert str(exc.value) == "embeddings transport error: ConnectError"


def test_t_v190_ret_01_final_failure_type_decides_not_the_first():
    """The first attempt times out, the retry fails with a *different*
    transport error: the exhausted-retry classification is decided by the
    final failure, exactly as REQ-V190-RET-01 states."""
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow")
        raise httpx.ConnectError("down")

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(handler))
    with pytest.raises(EmbeddingError) as exc:
        emb.embed(["x"])
    assert not isinstance(exc.value, EmbeddingTimeoutError)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(404, text="nope"),
        lambda r: httpx.Response(200, text="not json"),
    ],
)
def test_t_v190_ret_01_no_retry_on_non_transport_failure(handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    emb = EmbeddingsClient(BASE_URL, "m", 1, 5.0, client_for(wrapped))
    with pytest.raises(EmbeddingError):
        emb.embed(["x"])
    assert len(calls) == 1


def test_t_v190_ret_01_span_attributes(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    emb = EmbeddingsClient(
        BASE_URL,
        "embed-model",
        2,
        5.0,
        client_for(lambda r: httpx.Response(200, json=vector_response([[1.0, 2.0]]))),
    )
    emb.embed(["hello"], conv_id=42)
    span = captured["span"]
    assert span.name == "embeddings embed-model"
    assert span.kind == tracing.KIND_CLIENT
    assert span.conv_id == 42
    assert span.attributes["gen_ai.operation.name"] == "embeddings"
    assert span.attributes["gen_ai.provider.name"] == "lmstudio"
    assert span.attributes["gen_ai.request.model"] == "embed-model"
    assert span.attributes["tg_agent.embeddings.batch_size"] == 1
    assert span.attributes["tg_agent.embeddings.dim"] == 2


def test_t_v190_ret_01_indexing_defaults_conv_id_to_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        tracing.NullSink, "write", lambda self, span: captured.__setitem__("span", span)
    )
    emb = EmbeddingsClient(
        BASE_URL,
        "m",
        1,
        5.0,
        client_for(lambda r: httpx.Response(200, json=vector_response([[1.0]]))),
    )
    emb.embed(["hello"])
    assert captured["span"].conv_id is None


def test_t_v190_ret_01_not_recorded_in_llm_calls_by_construction():
    """`EmbeddingsClient` never touches `storage.add_llm_call` -- there is no
    `storage`/`conn` import in `llm/embeddings.py` at all, so a call cannot
    reach `llm_calls` even by accident."""
    import llm.embeddings as embeddings_module

    assert not hasattr(embeddings_module, "storage")


def test_fake_embedder_is_deterministic_and_shares_structure():
    """Not one of REQ-V190-RET-01's own tests -- sanity coverage for the test
    double T5+ (`T-V190-RET-03`, "meaningful ranking offline") builds on."""
    from tests.fakes import FakeEmbedder

    embedder = FakeEmbedder(dim=64)
    v1, v2, v3 = embedder.embed(
        ["the cat sat on the mat", "the cat sat on the mat", "wholly unrelated text"]
    )
    assert v1 == v2

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(v1, v2) == pytest.approx(1.0)
    assert cosine(v1, v3) < cosine(v1, v2)
    assert embedder.calls == [
        (["the cat sat on the mat", "the cat sat on the mat", "wholly unrelated text"], None)
    ]


def test_fake_embedder_script_mode_raises_scripted_errors():
    from tests.fakes import FakeEmbedder

    embedder = FakeEmbedder(dim=4, script=[[[1.0, 0.0, 0.0, 0.0]], EmbeddingError("boom")])
    assert embedder.embed(["x"]) == [[1.0, 0.0, 0.0, 0.0]]
    with pytest.raises(EmbeddingError, match="boom"):
        embedder.embed(["y"])


def test_t_v190_ret_01_error_hierarchy():
    from llm.base import LLMError

    assert issubclass(EmbeddingError, Exception)
    assert not issubclass(EmbeddingError, LLMError)
    assert issubclass(EmbeddingTimeoutError, EmbeddingError)


# --------------------------------------------------------------------------
# REQ-V190-RET-08 / T-V190-RET-09: bot._live_embeddings
# --------------------------------------------------------------------------


def minimal_cfg(**overrides):
    fields = dict(
        telegram_bot_token="123456789:sentinel-token-for-v190-ret-09",
        allowed_tg_ids=frozenset({1}),
        llm_provider="lmstudio",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="m",
        openrouter_api_key="",
        openrouter_model="",
        llm_timeout_s=120.0,
        exec_workdir=Path("/nonexistent/sandbox"),
        db_path=Path("/nonexistent/bot.db"),
    )
    fields.update(overrides)
    return config.Config(**fields)


def test_t_v190_ret_09_unset_pair_fails_offline_no_socket(capsys):
    def handler(request):
        raise AssertionError(f"unexpected request reached the network: {request.url}")

    cfg = minimal_cfg()
    assert cfg.rag_enabled is False
    code = bot_module._live_embeddings(cfg, client_for(handler))
    out = capsys.readouterr().out
    assert code == 1
    assert out == "live: FAIL embeddings (EMBEDDING_MODEL and EMBEDDING_DIM are not set)\n"


def embeddings_handler(*, models=("text-embedding-x",), dim=3, embeddings_status=200):
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": name} for name in models]})
        if request.url.path.endswith("/embeddings"):
            payload = json.loads(request.read())
            n = len(payload["input"])
            return httpx.Response(
                embeddings_status,
                json={"data": [{"index": i, "embedding": [0.0] * dim} for i in range(n)]},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    return handler


def test_t_v190_ret_09_configured_and_healthy_succeeds(capsys):
    cfg = minimal_cfg(
        embedding_base_url=BASE_URL, embedding_model="text-embedding-x", embedding_dim=3
    )
    assert cfg.rag_enabled is True
    code = bot_module._live_embeddings(
        cfg, client_for(embeddings_handler(models=("text-embedding-x",), dim=3))
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out == "live: OK embeddings\n"


def test_t_v190_ret_09_model_not_loaded_fails(capsys):
    cfg = minimal_cfg(embedding_base_url=BASE_URL, embedding_model="missing-model", embedding_dim=3)
    code = bot_module._live_embeddings(
        cfg, client_for(embeddings_handler(models=("other-model",), dim=3))
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL embeddings" in out
    assert "missing-model" in out


def test_t_v190_ret_09_dimension_mismatch_fails(capsys):
    cfg = minimal_cfg(
        embedding_base_url=BASE_URL, embedding_model="text-embedding-x", embedding_dim=8
    )
    code = bot_module._live_embeddings(
        cfg, client_for(embeddings_handler(models=("text-embedding-x",), dim=3))
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL embeddings" in out


def test_t_v190_ret_09_models_endpoint_http_error_fails(capsys):
    cfg = minimal_cfg(embedding_base_url=BASE_URL, embedding_model="m", embedding_dim=3)
    code = bot_module._live_embeddings(cfg, client_for(lambda r: httpx.Response(500, text="boom")))
    out = capsys.readouterr().out
    assert code == 1
    assert "live: FAIL embeddings" in out


def test_t_v190_ret_09_no_chat_completions_request_is_ever_made():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return embeddings_handler()(request)

    cfg = minimal_cfg(
        embedding_base_url=BASE_URL, embedding_model="text-embedding-x", embedding_dim=3
    )
    bot_module._live_embeddings(cfg, client_for(handler))
    assert not any("chat/completions" in url for url in seen)
