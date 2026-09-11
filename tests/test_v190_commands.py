"""spec-v1.9.0 T7 (docs/spec/spec-v1.9.0.md Sec.7, REQ-V190-CMD-01..07;
Sec.8, REQ-V190-ERR-01's Telegram-facing rows and REQ-V190-ERR-02; Sec.9,
REQ-V190-SEC-04's handler half): the document upload flow end to end
through `bot._handle_document`/`bot.process_update`, `TelegramClient.
get_file`/`download_file`, `/documents` and `/delete`.

Offline throughout: `tests.fakes.FakeTelegram`/`FakeEmbedder`/`FakeLLM`
stand in for Telegram, the embeddings endpoint and the LLM, except for
`T-V190-CMD-10`'s own two tests, which prove the download-timeout clause
order at the *real* `TelegramClient.download_file` boundary through a real
`httpx.Client` wired to `httpx.MockTransport` -- no socket either way.
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import sqlite3
import zipfile

import httpx
import pypdf.errors
import pytest

import bot
import config
import documents
import rag
import storage
from devtools.pdf_fixture import write_pdf
from llm.base import LLMResponse
from llm.embeddings import EmbeddingError, EmbeddingTimeoutError
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-command-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
NOW = "2026-09-11T00:00:00Z"


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    before = set(config._secrets)
    yield
    config._secrets.clear()
    config._secrets.update(before)


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": TOKEN,
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "test.db",
        "audit_log_path": tmp_path / "exec_audit.jsonl",
        "embedding_base_url": "http://localhost:1234/v1",
        "embedding_model": "embed-m",
        "embedding_dim": 16,
    }
    fields.update(overrides)
    return config.Config(**fields)


def new_conn(tmp_path, name="a.db", *, dim=16):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model="embed-m")
    return conn


def document_update(*, file_id="f1", file_name="notes.txt", file_size=20, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id, "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "document": {"file_id": file_id, "file_name": file_name, "file_size": file_size},
        },
    }


def text_update(text, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id, "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "text": text,
        },
    }


def process(conn, cfg, upd, *, tg=None, llm=None, embedder=None, **kwargs):
    tg = tg if tg is not None else FakeTelegram()
    llm = llm if llm is not None else FakeLLM([])
    bot.process_update(
        upd, conn=conn, tg=tg, cfg=cfg, llm=llm, skills={}, runner=RecordingRunner(),
        bot_username=BOT_USERNAME, embedder=embedder, **kwargs,
    )
    return tg


def _seq_clock(*values):
    values = list(values)
    state = {"i": 0}

    def _mono():
        i = min(state["i"], len(values) - 1)
        state["i"] += 1
        return values[i]

    return _mono


def _raise(exc):
    def _fn(*_a, **_k):
        raise exc
    return _fn


def _assert_prechecked_refused(tg, reply):
    """Rows 1, 5a-pre, 13-pre, 14: a plain reply, no status message, no
    `getFile` call (CMD-03)."""
    assert tg.sent == [(USER_ID, reply)]
    assert tg.get_file_calls == []
    assert tg.edited == []


def _assert_failure_kept(tg, reply):
    """CMD-04's failure ending: the status message is edited to `reply` and
    kept (never deleted)."""
    assert tg.deleted == []
    assert tg.edited and tg.edited[-1][2] == reply


# --------------------------------------------------------------------------
# REQ-V190-CMD-01 -- the document branch's position, the limiter, the
# per-turn `Searcher`.
# --------------------------------------------------------------------------


def test_t_v190_cmd_01_document_branch_precedes_the_text_only_guard(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"Some short valid text content for indexing purposes here."
    process(conn, cfg, document_update(), tg=tg, embedder=FakeEmbedder(dim=16))
    assert bot.NON_TEXT_REPLY not in [text for _c, text in tg.sent]
    assert tg.get_file_calls == ["f1"]
    conn.close()


def test_t_v190_cmd_01_rate_limit_applies_before_any_download(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    limiter = bot.RateLimiter(0, 60.0)  # zero tokens: always refused
    process(conn, cfg, document_update(), tg=tg, embedder=FakeEmbedder(dim=16), limiter=limiter)
    assert tg.sent == [(USER_ID, bot.RATE_LIMIT_REPLY)]
    assert tg.get_file_calls == []
    conn.close()


def test_t_v190_cmd_01_no_embedder_document_refused_rag_not_configured(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    process(conn, cfg, document_update(), tg=tg, embedder=None)
    assert tg.sent == [(USER_ID, bot.DOC_RAG_NOT_CONFIGURED_REPLY)]
    assert tg.get_file_calls == []
    conn.close()


def test_t_v190_cmd_01_rag_disabled_document_refused_even_with_an_embedder(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path, embedding_model="", embedding_dim=None)
    assert cfg.rag_enabled is False
    tg = FakeTelegram()
    process(conn, cfg, document_update(), tg=tg, embedder=FakeEmbedder(dim=16))
    assert tg.sent == [(USER_ID, bot.DOC_RAG_NOT_CONFIGURED_REPLY)]
    conn.close()


def test_t_v190_cmd_01_searcher_not_constructed_when_no_embedder(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)

    def _forbidden(*_a, **_k):
        raise AssertionError("Searcher must not be constructed when embedder is None")

    monkeypatch.setattr(rag, "Searcher", _forbidden)
    tg = FakeTelegram()
    process(
        conn, cfg, text_update("hello"), tg=tg, embedder=None,
        llm=FakeLLM([LLMResponse("hi", [], "stop")]),
    )
    assert tg.sent == [(USER_ID, "hi")]
    conn.close()


def test_t_v190_cmd_01_searcher_constructed_per_turn_bound_to_from_id(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    captured = {}

    class _Spy:
        def __init__(self, conn_, *, user_id, embedder, llm, cfg, conv_id, resolve_cost):
            captured["user_id"] = user_id
            captured["embedder"] = embedder
            captured["conv_id"] = conv_id
            self.calls = []

    monkeypatch.setattr(rag, "Searcher", _Spy)
    embedder = FakeEmbedder(dim=16)
    tg = FakeTelegram()
    process(
        conn, cfg, text_update("hello"), tg=tg, embedder=embedder,
        llm=FakeLLM([LLMResponse("hi", [], "stop")]),
    )
    assert captured["user_id"] == USER_ID
    assert captured["embedder"] is embedder
    assert captured["conv_id"] is not None
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-CMD-02 -- `get_file`/`download_file`; T-V190-CMD-10's clause
# order, proved at the real boundary.
# --------------------------------------------------------------------------


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_t_v190_cmd_02_get_file_posts_file_id_and_unwraps_result():
    def handler(request):
        assert request.url.path.endswith("/getFile")
        assert json.loads(request.content) == {"file_id": "f1"}
        return httpx.Response(200, json={"ok": True, "result": {"file_path": "documents/f1"}})

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    assert tg.get_file("f1") == {"file_path": "documents/f1"}


def test_t_v190_cmd_02_download_file_returns_bytes_under_the_cap():
    def handler(_request):
        return httpx.Response(200, content=b"hello world")

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    assert tg.download_file("documents/f1", max_bytes=1000) == b"hello world"


def test_t_v190_cmd_02_download_file_caps_the_streamed_buffer():
    def handler(_request):
        return httpx.Response(200, content=b"x" * 5000)

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    with pytest.raises(bot.DocumentTooLarge):
        tg.download_file("documents/f1", max_bytes=100)


def test_t_v190_cmd_02_download_file_non_200_is_a_plain_telegram_error():
    def handler(_request):
        return httpx.Response(404)

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    with pytest.raises(bot.TelegramError) as exc_info:
        tg.download_file("documents/f1", max_bytes=1000)
    assert not isinstance(exc_info.value, bot.TelegramDownloadTimeout)
    assert TOKEN not in str(exc_info.value)


def test_t_v190_cmd_10_download_timeout_via_the_real_boundary_raises_the_typed_exception():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    with pytest.raises(bot.TelegramDownloadTimeout):
        tg.download_file("documents/f1", max_bytes=1000)


def test_t_v190_cmd_10_a_non_timeout_transport_error_is_never_mistaken_for_a_timeout():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    with pytest.raises(bot.TelegramError) as exc_info:
        tg.download_file("documents/f1", max_bytes=1000)
    assert not isinstance(exc_info.value, bot.TelegramDownloadTimeout)


def test_t_v190_cmd_10_telegram_download_timeout_is_a_telegram_error_subclass():
    assert issubclass(bot.TelegramDownloadTimeout, bot.TelegramError)


# --------------------------------------------------------------------------
# REQ-V190-CMD-03 -- the five pre-checks, in order; the classify/clean_filename
# ordering hazard.
# --------------------------------------------------------------------------


def test_t_v190_cmd_03_started_at_is_the_handlers_first_action(tmp_path):
    """Proves ordering, not just that `monotonic` is called: a shared
    `markers` list records both the clock read and the one Telegram call
    this refusal path makes, and the clock must land first."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    markers = []

    def clock():
        markers.append("monotonic")
        return 0.0

    real_send = tg.send_message

    def spy_send(chat_id, text):
        markers.append("send")
        return real_send(chat_id, text)

    tg.send_message = spy_send

    # rag not configured -- returns immediately after the one plain reply,
    # but `started_at` must still have been captured before it.
    bot._handle_document(
        {"file_id": "f1", "file_name": "a.txt", "file_size": 10},
        conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=None, monotonic=clock,
    )
    assert markers == ["monotonic", "send"]
    conn.close()


def test_t_v190_cmd_03_classify_runs_on_the_cleaned_name_not_the_raw_one(tmp_path):
    """T3's finding: a raw filename with a trailing space classifies as
    `None` even for a valid extension ("report.pdf " -> unsupported) while
    the cleaned name classifies correctly. `classify` must run on the
    already-cleaned filename."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Employees accrue paid leave over the calendar year, details follow after this."
    tg.files["documents/f1"] = data
    raw_name = "notes.txt "  # trailing space
    assert documents.classify(raw_name) is None  # sanity: the raw name alone misclassifies
    assert documents.classify(documents.clean_filename(raw_name)) == "txt"

    doc = {"file_id": "f1", "file_name": raw_name, "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    # Proceeded past the type check to a real download+index, not refused.
    assert tg.get_file_calls == ["f1"]
    assert any(text.startswith("✅ notes.txt:") for _c, text in tg.sent)
    conn.close()


def test_t_v190_err_01_row_13_pre_check_replace_at_20_is_not_the_limit(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    for i in range(19):
        storage.add_document(
            conn, user_id=USER_ID, filename=f"d{i}.txt", file_type="txt",
            created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
            chunk_count=1, sha256="x" * 8,
        )
    storage.add_document(
        conn, user_id=USER_ID, filename="existing.txt", file_type="txt",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    tg = FakeTelegram()
    data = b"Fresh content that replaces the existing file, long enough to chunk."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "existing.txt", "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert tg.get_file_calls == ["f1"]  # not refused -- proceeded to download
    assert storage.document_count(conn, user_id=USER_ID) == 20
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-CMD-04 -- progress strings, typing indicator, the two endings.
# --------------------------------------------------------------------------


def test_t_v190_cmd_04_progress_strings_and_success_ending_txt(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Vacation policy: employees accrue paid leave across the year, details follow soon."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "policy.txt", "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    edited_texts = [t for _c, _m, t in tg.edited]
    assert edited_texts[0].startswith("📄 extracted: ") and edited_texts[0].endswith(" chars")
    assert edited_texts[1] == "📄 chunked: 1"
    assert edited_texts[2] == "📄 embedding: 1/1"
    assert tg.sent[0] == (USER_ID, "📄 received")
    assert tg.deleted == [(USER_ID, 101)]  # the "📄 received" message, deleted on success
    assert tg.sent[-1][1] == "✅ policy.txt: 1 chunks. Ask me about it."
    conn.close()


def test_t_v190_cmd_04_success_ending_pdf_carries_pages(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = write_pdf(["Page one has enough readable text to form a chunk on its own here."])
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "report.pdf", "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert tg.sent[-1][1] == "✅ report.pdf: 1 chunks, 1 pages. Ask me about it."
    edited_texts = [t for _c, _m, t in tg.edited]
    assert edited_texts[0].startswith("📄 extracted: 1 pages, ")
    assert edited_texts[0].endswith(" chars")
    conn.close()


def test_t_v190_cmd_04_typing_indicator_ceiling_is_the_index_budget(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    captured = {}
    real_init = bot._TypingIndicator.__init__

    def spy_init(self, tg, chat_id, *, ceiling_s, **kwargs):
        captured["ceiling_s"] = ceiling_s
        real_init(self, tg, chat_id, ceiling_s=ceiling_s, **kwargs)

    monkeypatch.setattr(bot._TypingIndicator, "__init__", spy_init)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"short but valid enough content for one chunk to be produced okay."
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert captured["ceiling_s"] == documents.INDEX_BUDGET_S_DEFAULT == 300.0
    conn.close()


def test_t_v190_cmd_04_status_disabled_falls_back_to_send_exactly_one_error(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram(fail_on=1, error=bot.TelegramError("boom"))
    tg.files["documents/f1"] = b"hi"
    doc = {"file_id": "f1", "file_name": "empty.txt", "file_size": 2}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert tg.sent == [(USER_ID, bot.DOC_EMPTY_REPLY)]
    assert tg.edited == []
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-CMD-05 -- /documents
# --------------------------------------------------------------------------


def test_t_v190_cmd_05_documents_empty(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/documents"))
    assert tg.sent == [(USER_ID, bot.DOCUMENTS_EMPTY_REPLY)]
    conn.close()


def test_t_v190_cmd_05_documents_lists_uploaded_files(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    storage.add_document(
        conn, user_id=USER_ID, filename="a.txt", file_type="txt",
        created_at="2026-01-02T03:04:05Z", size_bytes=5, text_chars=5,
        page_count=None, chunk_count=2, sha256="x" * 8,
    )
    storage.add_document(
        conn, user_id=USER_ID, filename="b.pdf", file_type="pdf",
        created_at="2026-01-03T00:00:00Z", size_bytes=5, text_chars=5,
        page_count=3, chunk_count=4, sha256="y" * 8,
    )
    tg = process(conn, cfg, text_update("/documents"))
    reply = tg.sent[0][1]
    assert reply.startswith("Your documents (2):")
    assert "a.txt — txt, 2 chunks, 2026-01-02" in reply
    assert "b.pdf — pdf, 4 chunks, 3 pages, 2026-01-03" in reply
    conn.close()


def test_t_v190_cmd_05_filenames_are_redacted(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    sentinel = "CANARY-documents-listing-filename-secret-should-not-leak-here"
    config.register_secret(sentinel)
    storage.add_document(
        conn, user_id=USER_ID, filename=sentinel, file_type="txt",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    tg = process(conn, cfg, text_update("/documents"))
    assert sentinel not in tg.sent[0][1]
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-CMD-06 -- /delete <filename>
# --------------------------------------------------------------------------


def test_t_v190_cmd_06_delete_no_argument_is_usage(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/delete"))
    assert tg.sent == [(USER_ID, bot.DELETE_USAGE_REPLY)]
    conn.close()


def test_t_v190_cmd_06_delete_unknown_filename(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/delete missing file.txt"))
    assert tg.sent == [(USER_ID, "No document named missing file.txt.")]
    conn.close()


def test_t_v190_cmd_06_delete_exact_match_removes_it(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    doc_id = storage.add_document(
        conn, user_id=USER_ID, filename="my file.txt", file_type="txt",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    storage.add_chunks(conn, user_id=USER_ID, document_id=doc_id, chunks=[(0, "hi", None, 0, 2)])
    tg = process(conn, cfg, text_update("/delete my file.txt"))
    assert tg.sent == [(USER_ID, "Deleted my file.txt.")]
    assert storage.document_count(conn, user_id=USER_ID) == 0
    conn.close()


def test_t_v190_cmd_06_delete_is_exact_no_casefold_no_prefix(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    storage.add_document(
        conn, user_id=USER_ID, filename="Report.TXT", file_type="txt",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    tg = process(conn, cfg, text_update("/delete report.txt"))
    assert tg.sent == [(USER_ID, "No document named report.txt.")]
    assert storage.document_count(conn, user_id=USER_ID) == 1
    conn.close()


def test_t_v190_cmd_06_delete_is_scoped_to_the_caller(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    other_user = USER_ID + 1
    storage.add_document(
        conn, user_id=other_user, filename="a.txt", file_type="txt",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    tg = process(conn, cfg, text_update("/delete a.txt"))
    assert tg.sent == [(USER_ID, "No document named a.txt.")]
    assert storage.document_count(conn, user_id=other_user) == 1
    conn.close()


def test_t_v190_cmd_06_delete_argument_may_contain_spaces(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    storage.add_document(
        conn, user_id=USER_ID, filename="quarterly report v2.docx", file_type="docx",
        created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
        chunk_count=1, sha256="x" * 8,
    )
    tg = process(conn, cfg, text_update("/delete quarterly report v2.docx"))
    assert tg.sent == [(USER_ID, "Deleted quarterly report v2.docx.")]
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-ERR-01 -- the Telegram-facing rows this task owns.
# --------------------------------------------------------------------------


def test_t_v190_err_01_row_1_no_filename_is_unsupported(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    doc = {"file_id": "f1", "file_name": None, "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_prechecked_refused(tg, bot.DOC_UNSUPPORTED_REPLY)
    conn.close()


def test_t_v190_err_01_row_1_unknown_extension_is_unsupported(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    doc = {"file_id": "f1", "file_name": "notes.exe", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_prechecked_refused(tg, bot.DOC_UNSUPPORTED_REPLY)
    conn.close()


def test_t_v190_err_01_row_2_corrupted_pdf(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"not really a pdf but long enough to pass the size check okay"
    monkeypatch.setattr(documents, "extract", _raise(pypdf.errors.PdfStreamError("boom")))
    doc = {"file_id": "f1", "file_name": "report.pdf", "file_size": 60}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_CORRUPTED_PDF_REPLY)
    conn.close()


def test_t_v190_err_01_row_3_corrupted_docx(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"not really a docx but long enough to pass the size check yes"
    monkeypatch.setattr(documents, "extract", _raise(zipfile.BadZipFile("boom")))
    doc = {"file_id": "f1", "file_name": "report.docx", "file_size": 60}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_CORRUPTED_DOCX_REPLY)
    conn.close()


def test_t_v190_err_01_row_4_empty_document(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"hi"
    doc = {"file_id": "f1", "file_name": "empty.txt", "file_size": 2}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_EMPTY_REPLY)
    assert storage.document_count(conn, user_id=USER_ID) == 0
    conn.close()


def test_t_v190_err_01_row_5a_pre_file_size_too_large(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    doc = {"file_id": "f1", "file_name": "big.txt", "file_size": bot.DOCUMENT_MAX_BYTES + 1}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_prechecked_refused(tg, bot.DOC_TOO_LARGE_REPLY)
    conn.close()


def test_t_v190_err_01_row_5a_mid_stream_exceeds_the_cap(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"x" * (bot.DOCUMENT_MAX_BYTES + 1)
    doc = {"file_id": "f1", "file_name": "big.txt", "file_size": 10}  # understates its own size
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_TOO_LARGE_REPLY)
    conn.close()


@pytest.mark.parametrize("exc", [
    documents.ExtractedTextTooLargeError("text too large"),
    documents.DocxArchiveTooLargeError("archive too large"),
    documents.PdfTooManyPagesError("too many pages"),
])
def test_t_v190_err_01_row_5b_variants_map_to_the_same_reply(tmp_path, monkeypatch, exc):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"enough bytes to pass the pre-download size check comfortably"
    monkeypatch.setattr(documents, "extract", _raise(exc))
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 60}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_TEXT_TOO_LARGE_REPLY)
    conn.close()


def test_t_v190_err_01_row_6_embedding_error(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Enough content here to reach the embedding stage of indexing, please."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": len(data)}
    embedder = FakeEmbedder(dim=16, script=[EmbeddingError("boom")])
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID, embedder=embedder,
    )
    _assert_failure_kept(tg, bot.DOC_EMBEDDING_ERROR_REPLY)
    conn.close()


def test_t_v190_err_01_row_7_sqlite_error(tmp_path, monkeypatch, caplog):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Enough content here to reach the store stage of the index pipeline okay."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": len(data)}
    monkeypatch.setattr(storage, "add_document", _raise(sqlite3.OperationalError("boom")))
    with caplog.at_level(logging.ERROR):
        bot._handle_document(
            doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
            embedder=FakeEmbedder(dim=16),
        )
    _assert_failure_kept(tg, bot.DOC_STORAGE_ERROR_REPLY)
    assert storage.document_count(conn, user_id=USER_ID) == 0
    conn.close()


def test_t_v190_err_01_row_10a_download_timeout(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.download_errors["documents/f1"] = bot.TelegramDownloadTimeout("download timed out")
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_DOWNLOAD_TIMEOUT_REPLY)
    conn.close()


def test_t_v190_err_01_row_10b_embedding_timeout_before_row_6(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Enough content here to reach the embedding stage of indexing, please."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": len(data)}
    embedder = FakeEmbedder(dim=16, script=[EmbeddingTimeoutError("boom")])
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID, embedder=embedder,
    )
    _assert_failure_kept(tg, bot.DOC_EMBEDDING_TIMEOUT_REPLY)  # not row 6's string
    conn.close()


def test_t_v190_err_01_row_10c_and_cmd_09_budget_counts_pre_index_time(tmp_path):
    """T-V190-CMD-09: `started_at` is captured before every pre-check and
    the download, so even though nothing between the handler's first line
    and `index_document`'s first internal budget check calls `monotonic`
    again, the elapsed time `index_document` computes already reflects that
    whole span."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    data = b"Some readable content that would normally index just fine right here."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": len(data)}
    clock = _seq_clock(0.0, 400.0)
    embedder = FakeEmbedder(dim=16)
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=embedder, monotonic=clock,
    )
    _assert_failure_kept(tg, bot.DOC_BUDGET_EXCEEDED_REPLY)
    assert embedder.calls == []  # never reached the embed stage
    conn.close()


def test_t_v190_err_01_row_11_get_file_without_a_file_path(tmp_path):
    """`file_path` is optional on Telegram's `File` object; a reply without
    it must map to row 11, never fall through to a corrupted-document class
    further down the exception chain (e.g. `KeyError`, which the docx
    clause also catches)."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.get_file = lambda _file_id: {}
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_TELEGRAM_ERROR_REPLY)
    conn.close()


def test_t_v190_err_01_row_11_other_telegram_error(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.download_errors["documents/f1"] = bot.TelegramError("telegram file download http 500")
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_failure_kept(tg, bot.DOC_TELEGRAM_ERROR_REPLY)
    conn.close()


def test_t_v190_err_01_row_12_confirmation_send_failure_document_still_stored(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    data = b"Enough readable text content here to produce exactly one chunk for storage."
    # 1st send ("received") succeeds; 2nd (the confirmation) fails.
    tg = FakeTelegram(fail_on=2, error=bot.TelegramError("boom"))
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "notes.txt", "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert storage.document_count(conn, user_id=USER_ID) == 1
    assert tg.deleted  # the status message was still deleted -- a success, not a failure
    conn.close()


def test_t_v190_err_01_row_13_pre_check_limit_reached_plain_reply(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    for i in range(20):
        storage.add_document(
            conn, user_id=USER_ID, filename=f"d{i}.txt", file_type="txt",
            created_at=NOW, size_bytes=5, text_chars=5, page_count=None,
            chunk_count=1, sha256="x" * 8,
        )
    tg = FakeTelegram()
    doc = {"file_id": "f1", "file_name": "new.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    _assert_prechecked_refused(tg, bot.DOC_LIMIT_REPLY)
    assert storage.document_count(conn, user_id=USER_ID) == 20
    conn.close()


def test_t_v190_err_01_row_13_transactional_recheck_via_the_handler(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    calls = {"n": 0}

    def fake_count(_conn, *, user_id):
        calls["n"] += 1
        return 19 if calls["n"] == 1 else 20  # pre-check sees 19; the recheck sees 20

    monkeypatch.setattr(storage, "document_count", fake_count)
    tg = FakeTelegram()
    data = b"Enough content here to produce one real chunk for the index pipeline."
    tg.files["documents/f1"] = data
    doc = {"file_id": "f1", "file_name": "new.txt", "file_size": len(data)}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert tg.get_file_calls == ["f1"]  # the pre-check passed
    _assert_failure_kept(tg, bot.DOC_LIMIT_REPLY)  # the transactional recheck caught it
    conn.close()


def test_t_v190_err_01_row_14_rag_not_configured(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 10}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID, embedder=None,
    )
    _assert_prechecked_refused(tg, bot.DOC_RAG_NOT_CONFIGURED_REPLY)
    conn.close()


def test_t_v190_err_01_row_15_catch_all(tmp_path, monkeypatch, caplog):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"enough bytes to pass the pre-download size check comfortably"
    monkeypatch.setattr(documents, "extract", _raise(ZeroDivisionError("boom")))
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 60}
    with caplog.at_level(logging.WARNING):
        bot._handle_document(
            doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
            embedder=FakeEmbedder(dim=16),
        )
    _assert_failure_kept(tg, bot.DOC_HANDLER_FAILED_REPLY)
    assert any(
        r.levelname == "ERROR" and "document handler failed" in r.getMessage()
        for r in caplog.records
    )
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-CMD-07 -- one exception boundary; T-V190-CMD-08: the poll loop
# survives, and a second update in the same batch is still processed.
# --------------------------------------------------------------------------


def test_t_v190_cmd_08_exception_in_document_handler_lets_poll_loop_continue(
    tmp_path, monkeypatch, caplog
):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(documents, "extract", _raise(ZeroDivisionError("boom")))
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"some readable content, long enough for a chunk to form here."
    updates = [
        document_update(file_id="f1", file_name="notes.txt", file_size=30, update_id=1),
        text_update("hello", update_id=2),
    ]

    call_count = {"n": 0}

    def get_updates(_offset):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return updates
        bot._shutdown = True  # stop the loop only after the batch is fully processed
        return []

    tg.get_updates = get_updates
    llm = FakeLLM([LLMResponse("hi there", [], "stop")])
    with caplog.at_level(logging.WARNING):
        rc = bot.poll_loop(
            conn=conn, tg=tg, cfg=cfg, llm=llm, skills={}, runner=RecordingRunner(),
            bot_username=BOT_USERNAME, sleep=lambda _s: None, embedder=FakeEmbedder(dim=16),
        )
    assert rc == 0
    assert tg.edited[-1][2] == bot.DOC_HANDLER_FAILED_REPLY
    assert not any("Traceback" in t for _c, _m, t in tg.edited)
    assert not any("Traceback" in t for _c, t in tg.sent)
    # The second update in the same batch was still processed.
    assert tg.sent[-1] == (USER_ID, "hi there")
    assert storage.get_state(conn, "last_update_id") == "2"
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-ERR-02 -- no traceback to the user; every log line redacted.
# --------------------------------------------------------------------------


def test_t_v190_err_02_no_traceback_text_reaches_the_user(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"plenty of readable text content goes here for indexing."
    monkeypatch.setattr(
        documents, "extract", _raise(ZeroDivisionError("division by zero at line 42"))
    )
    doc = {"file_id": "f1", "file_name": "notes.txt", "file_size": 30}
    bot._handle_document(
        doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    all_text = [t for _c, _m, t in tg.edited] + [t for _c, t in tg.sent]
    assert not any("Traceback" in t or "ZeroDivisionError" in t for t in all_text)


def test_t_v190_err_02_a_secret_sentinel_in_the_filename_never_reaches_the_user_or_the_log(
    tmp_path, caplog
):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    sentinel = "CANARY-document-filename-secret-value-should-never-leak-anywhere"
    config.register_secret(sentinel)
    tg = FakeTelegram()
    raw_name = f"{sentinel}.exe"  # unsupported extension -> row 1
    doc = {"file_id": "f1", "file_name": raw_name, "file_size": 10}
    with caplog.at_level(logging.WARNING):
        bot._handle_document(
            doc, conn=conn, tg=tg, cfg=cfg, chat_id=USER_ID, from_id=USER_ID,
            embedder=FakeEmbedder(dim=16),
        )
    assert sentinel not in tg.sent[0][1]
    assert not any(sentinel in record.getMessage() for record in caplog.records)
    conn.close()


# --------------------------------------------------------------------------
# REQ-V190-SEC-04, the handler half -- no file on disk. `T-V190-SEC-04` is
# already T6's (for SEC-02, see the spec test-id collision this brief
# discloses); this is this task's own test, named with a `b` suffix to
# avoid colliding with T6's.
# --------------------------------------------------------------------------


def _forbidden_file_io(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            found.add("open(")
        if isinstance(node, ast.Name) and node.id == "Path":
            found.add("Path")
        if isinstance(node, ast.Attribute) and node.attr == "write_bytes":
            found.add("write_bytes")
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "tempfile" for alias in node.names
        ):
            found.add("tempfile")
        if isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            found.add("tempfile")
    return found


def test_t_v190_sec_04b_no_file_writes_in_the_document_handler():
    """`inspect.getsource` on the handler function itself, never a
    whole-file grep: `bot.py` legitimately uses `Path`/`tempfile`/`open`
    elsewhere (`run_selftest`, sandbox cleanup), none of which this
    function-scoped check may see."""
    source = inspect.getsource(bot._handle_document)
    assert _forbidden_file_io(source) == set()
