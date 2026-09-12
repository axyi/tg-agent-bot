"""spec-v1.9.0 T7 (docs/spec/spec-v1.9.0.md Sec.7/8, REQ-V190-CMD-01..07
wired end to end with T1-T6's storage/embeddings/parsing/indexing/
retrieval/attribution): `T-V190-E2E-01..03` (see
docs/spec/spec-v1.9.0-delta-1.md's test table) -- upload, list, ask,
delete, ask again -- through `bot.process_update`, exercising the *real*
`rag.Searcher`, `documents.index_document` and `storage`, with only the
network edge (Telegram, the LLM, the embeddings endpoint) faked.

Offline throughout: `tests.fakes.FakeTelegram`/`FakeEmbedder`/`FakeLLM`.
`rag_rerank="off"` throughout -- irrelevant to these three scenarios (each
retrieval here resolves to at most one candidate before the rerank gate,
since `rerank_attempted` requires >= 2 passages) and it keeps the scripted
`FakeLLM` down to exactly the two calls each scenario needs.
"""

from __future__ import annotations

import json

import pytest

import bot
import config
import storage
from devtools.pdf_fixture import write_pdf
from llm.base import LLMResponse, ToolCall
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-e2e-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
EMBED_DIM = 64  # wider than the commands file's 16 to keep hash collisions rare


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


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
        "embedding_dim": EMBED_DIM,
        "rag_rerank": "off",
    }
    fields.update(overrides)
    return config.Config(**fields)


def new_conn(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=EMBED_DIM, embedding_model="embed-m")
    return conn


def document_update(*, file_id, file_name, file_size, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "document": {"file_id": file_id, "file_name": file_name, "file_size": file_size},
        },
    }


def text_update(text, update_id):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "text": text,
        },
    }


def process(conn, cfg, upd, *, tg, llm, embedder):
    bot.process_update(
        upd,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        embedder=embedder,
    )


def search_call(index, query):
    return ToolCall(f"call_{index}", "search_documents", json.dumps({"query": query}))


def test_t_v190_e2e_01_upload_documents_ask_reply_carries_the_filename(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    embedder = FakeEmbedder(dim=EMBED_DIM)
    tg = FakeTelegram()

    data = b"Vacation policy: employees accrue twenty paid vacation days every year."
    tg.files["documents/f1"] = data
    process(
        conn,
        cfg,
        document_update(file_id="f1", file_name="policy.txt", file_size=len(data)),
        tg=tg,
        llm=FakeLLM([]),
        embedder=embedder,
    )
    assert any(text.startswith("✅ policy.txt:") for _c, text in tg.sent)

    process(
        conn,
        cfg,
        text_update("/documents", update_id=2),
        tg=tg,
        llm=FakeLLM([]),
        embedder=embedder,
    )
    assert "policy.txt" in tg.sent[-1][1]

    llm = FakeLLM(
        [
            LLMResponse("", [search_call(0, "vacation days")], "tool_calls"),
            LLMResponse("You get twenty vacation days per year.", [], "stop"),
        ]
    )
    process(
        conn,
        cfg,
        text_update("How many vacation days do I get?", update_id=3),
        tg=tg,
        llm=llm,
        embedder=embedder,
    )

    tool_message = llm.calls[1][0][-1]
    assert json.loads(tool_message["content"])["passages"] == 1

    final_reply = tg.sent[-1][1]
    assert final_reply.startswith("You get twenty vacation days per year.")
    assert "policy.txt" in final_reply
    assert "Sources: policy.txt" in final_reply  # appended: the model's own text carried none
    conn.close()


def test_t_v190_e2e_02_pdf_three_pages_source_line_carries_the_page(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path, rag_top_k=1)  # keep the top-ranked (page 2) passage only
    embedder = FakeEmbedder(dim=EMBED_DIM)
    tg = FakeTelegram()

    pages = [
        "Introduction: this handbook covers general company procedures and policy overview.",
        "Refunds: the refund window for any purchase is exactly thirty days from delivery.",
        "Contacts: reach support at the address listed on the company website footer.",
    ]
    data = write_pdf(pages)
    tg.files["documents/f1"] = data
    process(
        conn,
        cfg,
        document_update(file_id="f1", file_name="handbook.pdf", file_size=len(data)),
        tg=tg,
        llm=FakeLLM([]),
        embedder=embedder,
    )
    assert any(text.startswith("✅ handbook.pdf:") for _c, text in tg.sent)

    llm = FakeLLM(
        [
            LLMResponse("", [search_call(0, "refund window days")], "tool_calls"),
            LLMResponse("The refund window is thirty days.", [], "stop"),
        ]
    )
    process(
        conn,
        cfg,
        text_update("What is the refund window?", update_id=2),
        tg=tg,
        llm=llm,
        embedder=embedder,
    )

    tool_message = llm.calls[1][0][-1]
    payload = json.loads(tool_message["content"])
    assert payload["passages"] == 1
    assert "page 2" in payload["text"]

    final_reply = tg.sent[-1][1]
    assert "handbook.pdf (page 2)" in final_reply
    conn.close()


def test_t_v190_e2e_03_delete_then_the_same_question_carries_no_source_line(tmp_path):
    """Per `spec-v1.9.0-delta-1.md`'s `T-V190-E2E-03` row: `/delete` -> the
    same question -> no source line, the model's "not covered" reply passes
    through unchanged.

    Deviation from the delta table's exact wording, disclosed here: with the
    single uploaded document removed, `documents_present` is `False` and
    the tool's rendered text is `tools.NO_DOCUMENTS_TEXT`, not the table's
    literal "No passages matched." (`tools.NO_PASSAGES_TEXT`) -- that string
    requires `documents_present=True` with zero retrieved passages, which
    real hybrid retrieval cannot guarantee deterministically (vector KNN has
    no similarity floor: with >= 1 vector still present for the user it
    always returns *something*, however dissimilar). Both empty-result
    strings share the one contract this test actually proves: zero passages
    -> `rag.attach_sources` strips/never adds a source line, and the
    scripted "not covered" reply is delivered unchanged. The delta table's
    literal "No passages matched." string is itself already covered at the
    unit level by T6's `test_t_v190_tool_02_documents_present_but_no_passages`
    (in tests/test_v190_tool.py), which builds that SearchResult directly --
    this test's job is the delete -> no-source-line contract end to end,
    not re-proving that string.
    """
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    embedder = FakeEmbedder(dim=EMBED_DIM)
    tg = FakeTelegram()

    data = b"Vacation policy: employees accrue twenty paid vacation days every year."
    tg.files["documents/f1"] = data
    process(
        conn,
        cfg,
        document_update(file_id="f1", file_name="policy.txt", file_size=len(data)),
        tg=tg,
        llm=FakeLLM([]),
        embedder=embedder,
    )

    process(
        conn,
        cfg,
        text_update("/delete policy.txt", update_id=2),
        tg=tg,
        llm=FakeLLM([]),
        embedder=embedder,
    )
    assert tg.sent[-1] == (USER_ID, "Deleted policy.txt.")
    assert storage.document_count(conn, user_id=USER_ID) == 0

    llm = FakeLLM(
        [
            LLMResponse("", [search_call(0, "vacation days")], "tool_calls"),
            LLMResponse("The documents do not cover that.", [], "stop"),
        ]
    )
    process(
        conn,
        cfg,
        text_update("How many vacation days do I get?", update_id=3),
        tg=tg,
        llm=llm,
        embedder=embedder,
    )

    tool_message = llm.calls[1][0][-1]
    payload = json.loads(tool_message["content"])
    assert payload["passages"] == 0
    assert "No documents uploaded" in payload["text"]

    final_reply = tg.sent[-1][1]
    assert final_reply == "The documents do not cover that."
    assert "Source" not in final_reply
    conn.close()
