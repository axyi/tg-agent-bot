"""docs/spec/spec-v1.10.1.md §3 REQ-V1101-CFG-02, §12 T-V1101-CFG-01/-02/-04,
T-V1101-EC-02: `is_openrouter_url`, `Config.embedding_api_key`'s resolution,
and the storage preflight's own expression (REV-04 Stage 0 check 2,
REQ-V1101-EC-04 precondition 3).

Offline: `load_config(env=..., load_env_file=False)` only, exactly like
`tests/test_config.py` and `tests/test_v1100_config.py`; `tmp_path` sqlite
databases for T-V1101-EC-02.
"""

import pytest

import config
import storage
from config import ConfigError, is_openrouter_url, load_config
from tests.test_config import base_env

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1"
SECRET_KEY = "sk-or-v1-1101-sentinel-embeddings-key"

# --------------------------------------------------------------------------
# T-V1101-CFG-04 -- is_openrouter_url
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://openrouter.ai",
        "https://openrouter.ai/api/v1/",
        "https://OPENROUTER.AI/api/v1",
    ],
)
def test_t_v1101_cfg_04_openrouter_urls_are_true(url):
    assert is_openrouter_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://openrouter.ai/api/v1",
        "https://openrouter.ai.evil/api/v1",
        "https://notopenrouter.ai/api/v1",
    ],
)
def test_t_v1101_cfg_04_non_openrouter_urls_are_false(url):
    assert is_openrouter_url(url) is False


# --------------------------------------------------------------------------
# T-V1101-CFG-01/-02 -- Config.embedding_api_key
# --------------------------------------------------------------------------


def test_t_v1101_cfg_01_openrouter_embedding_url_resolves_the_registered_key():
    cfg = load_config(
        env=base_env(OPENROUTER_API_KEY=SECRET_KEY, EMBEDDING_BASE_URL=OPENROUTER_EMBEDDINGS_URL),
        load_env_file=False,
    )
    assert cfg.embedding_api_key == SECRET_KEY
    # `register_secret(openrouter_api_key)` (config.py:361) runs unconditionally
    # -- `embedding_api_key` rides the same already-registered secret, no new
    # registration call of its own.
    assert config.redact(SECRET_KEY) == config.REDACTION


def test_t_v1101_cfg_02_lmstudio_embedding_url_key_is_empty():
    # `EMBEDDING_BASE_URL` unset -> falls back to `LMSTUDIO_BASE_URL`'s
    # default, never an OpenRouter host, even though a key is present.
    cfg = load_config(env=base_env(OPENROUTER_API_KEY=SECRET_KEY), load_env_file=False)
    assert cfg.embedding_api_key == ""


def test_t_v1101_cfg_02_http_openrouter_url_key_is_empty():
    cfg = load_config(
        env=base_env(
            OPENROUTER_API_KEY=SECRET_KEY,
            EMBEDDING_BASE_URL="http://openrouter.ai/api/v1",
        ),
        load_env_file=False,
    )
    assert cfg.embedding_api_key == ""


def test_t_v1101_cfg_02_no_openrouter_key_at_all_is_empty():
    cfg = load_config(
        env=base_env(EMBEDDING_BASE_URL=OPENROUTER_EMBEDDINGS_URL), load_env_file=False
    )
    assert cfg.embedding_api_key == ""


# --------------------------------------------------------------------------
# T-V1101-EC-02 -- the storage preflight's own expression (REV-04 Stage 0
# check 2, spec-v1.10.1.md:1119-1140). Not new production code: the exact
# expression Stage 0's `uv run --offline --locked python -c` one-liner runs
# over `config.load_config()` and `storage`. Pinned offline on a `tmp_path`
# database -- the two count cases pin an existing-API invariant (no red
# phase, by design); the `ConfigError` case pins the preflight's own
# handling and has a red phase like any other new-code test.
# --------------------------------------------------------------------------


def _db_empty(conn, *, embedding_dim, embedding_model):
    try:
        storage.init_schema(conn, embedding_dim=embedding_dim, embedding_model=embedding_model)
    except ConfigError:
        return False
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return storage.document_count_all(conn) == 0 and chunks == 0


def _add_document_with_chunk(conn):
    doc_id = storage.add_document(
        conn,
        user_id=1,
        filename="a.txt",
        file_type="txt",
        created_at="x",
        size_bytes=1,
        text_chars=5,
        page_count=None,
        chunk_count=1,
        sha256="x" * 8,
    )
    storage.add_chunks(conn, user_id=1, document_id=doc_id, chunks=[(0, "hello", None, 0, 5)])
    return doc_id


def test_t_v1101_ec_02_fresh_database_is_empty(tmp_path):
    conn = storage.connect(tmp_path / "fresh.db")
    try:
        assert _db_empty(conn, embedding_dim=8, embedding_model="m") is True
    finally:
        conn.close()


def test_t_v1101_ec_02_indexed_document_is_not_empty(tmp_path):
    conn = storage.connect(tmp_path / "indexed.db")
    try:
        storage.init_schema(conn, embedding_dim=8, embedding_model="m")
        _add_document_with_chunk(conn)
        assert _db_empty(conn, embedding_dim=8, embedding_model="m") is False
    finally:
        conn.close()


def test_t_v1101_ec_02_mismatched_pair_reports_empty_false_never_raises(tmp_path):
    conn = storage.connect(tmp_path / "mismatched.db")
    try:
        storage.init_schema(conn, embedding_dim=8, embedding_model="m")
        _add_document_with_chunk(conn)
        # `init_schema` itself raises the indexed-pair mismatch `ConfigError`
        # (storage.py:600-604): a different pair, a document already
        # indexed. The expression must never let that propagate -- it
        # reports `db_empty=False`, exactly as ERR-01 row 13 requires.
        assert _db_empty(conn, embedding_dim=16, embedding_model="other") is False
    finally:
        conn.close()
