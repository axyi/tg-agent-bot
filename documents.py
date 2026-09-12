"""spec-v1.9.0 T3+T4 (docs/spec/spec-v1.9.0.md Sec.3, REQ-V190-DOC-01..05):
filename/type classification, in-memory extraction, paragraph-aware
offset-based chunking (T3), and the indexing pipeline `index_document` that
ties classify -> extract -> chunk -> embed -> store together with DOC-04's
limits and budget (T4).

Extraction runs entirely on in-memory `bytes`: no temporary file, no
`Path`, no `open()` anywhere in this module (`T-V190-SEC-04` greps it).
Neither this module nor `rag.py` (T5) imports `bot`.
"""

import hashlib
import io
import re
import sqlite3
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass

import docx
import pypdf
import sqlite_vec
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

import storage

# ---------------------------------------------------------------------------
# REQ-V190-DOC-01: type by lowercase extension; the filename contract.
# ---------------------------------------------------------------------------

_KNOWN_EXTENSIONS = frozenset({"txt", "md", "docx", "pdf"})

# clean_filename's cap (STO-02's documents.filename, the /documents display
# name, the /delete match key and the attribution string).
CLEAN_FILENAME_MAX_CHARS = 120

_PATH_SEPARATORS = ("/", "\\")


def classify(filename: str) -> str | None:
    """Lowercase-extension-only type detection. MIME type, magic bytes and
    Telegram's `mime_type` are never consulted."""
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext if ext in _KNOWN_EXTENSIONS else None


def clean_filename(raw: str | None) -> str | None:
    """Strip path separators and control characters, strip whitespace, cap at
    `CLEAN_FILENAME_MAX_CHARS`. `None`/empty in, or an empty result, yields
    `None`."""
    if not raw:
        return None
    kept = [ch for ch in raw if ch not in _PATH_SEPARATORS and ord(ch) >= 32 and ord(ch) != 0x7F]
    cleaned = "".join(kept).strip()[:CLEAN_FILENAME_MAX_CHARS]
    return cleaned or None


# ---------------------------------------------------------------------------
# REQ-V190-DOC-02: extraction per type, from memory.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedPage:
    text: str
    page: int | None  # PDF's 1-based physical page number; None otherwise.


@dataclass(frozen=True)
class Extracted:
    pages: tuple[ExtractedPage, ...]
    page_numbered: bool


class DocumentTooLargeError(Exception):
    """Base class for a DOC-02 pre-parse guard that refuses a document
    before parsing begins (ERR-01 row 5b). T4/T7 map every instance of this
    family to that one row; the two concrete subclasses below exist so the
    row's differing log detail (`docx archive bounds <detail>` vs.
    `pdf pages <n>`) can still be told apart."""


class DocxArchiveTooLargeError(DocumentTooLargeError):
    """The DOCX zip archive exceeds DOC-02's member-count, size or
    compression-ratio bounds. Raised before `python-docx` touches the
    bytes."""


class PdfTooManyPagesError(DocumentTooLargeError):
    """The PDF has more than `PDF_MAX_PAGES` pages. Raised before any
    `extract_text()` call, so it can never be mistaken for a corrupted
    PDF (ERR-01 row 2)."""


_UTF8_SIG = "utf-8-sig"
_CP1251_FALLBACK = "cp1251"

DOCX_MAX_MEMBERS = 2_000
DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DOCX_MAX_MEMBER_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
DOCX_MAX_COMPRESSION_RATIO = 100

PDF_MAX_PAGES = 500


def extract(
    data: bytes,
    file_type: str,
    *,
    monotonic: Callable[[], float] | None = None,
    started_at: float | None = None,
    budget_s: float | None = None,
) -> Extracted:
    """`monotonic`/`started_at`/`budget_s` are DOC-04's between-pages budget
    check, threaded through only as far as `_extract_pdf`'s per-page loop --
    `txt`/`md`/`docx` extraction has no internal loop to check between, so
    they ignore the three. `started_at is None` (the default, and every T3
    call site unchanged) skips the check entirely."""
    if file_type in ("txt", "md"):
        return _extract_text(data)
    if file_type == "docx":
        return _extract_docx(data)
    if file_type == "pdf":
        return _extract_pdf(data, monotonic=monotonic, started_at=started_at, budget_s=budget_s)
    raise ValueError(f"unsupported file_type: {file_type!r}")


def _extract_text(data: bytes) -> Extracted:
    try:
        text = data.decode(_UTF8_SIG)
    except UnicodeDecodeError:
        text = data.decode(_CP1251_FALLBACK)
    return Extracted(pages=(ExtractedPage(text=text, page=None),), page_numbered=False)


def _check_docx_archive_bounds(data: bytes) -> None:
    """Opens the DOCX bytes as a zip and bounds the archive before
    `python-docx` is touched at all. `zipfile.BadZipFile` from the open
    itself is left to propagate un-wrapped -- it is part of the
    corrupted-DOCX class (ERR-01 row 3), not this "too large" family."""
    archive = zipfile.ZipFile(io.BytesIO(data))
    infos = archive.infolist()
    if len(infos) > DOCX_MAX_MEMBERS:
        raise DocxArchiveTooLargeError(
            f"{len(infos)} members exceeds the {DOCX_MAX_MEMBERS}-member bound"
        )
    total_uncompressed = 0
    total_compressed = 0
    for info in infos:
        if info.file_size > DOCX_MAX_MEMBER_UNCOMPRESSED_BYTES:
            raise DocxArchiveTooLargeError(
                f"member {info.filename!r} is {info.file_size} bytes uncompressed, "
                f"over the {DOCX_MAX_MEMBER_UNCOMPRESSED_BYTES}-byte bound"
            )
        total_uncompressed += info.file_size
        total_compressed += info.compress_size
    if total_uncompressed > DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise DocxArchiveTooLargeError(
            f"{total_uncompressed} bytes uncompressed exceeds the "
            f"{DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES}-byte bound"
        )
    if total_compressed > 0:
        ratio = total_uncompressed / total_compressed
        if ratio > DOCX_MAX_COMPRESSION_RATIO:
            raise DocxArchiveTooLargeError(
                f"compression ratio {ratio:.1f} exceeds the {DOCX_MAX_COMPRESSION_RATIO}x bound"
            )


def _extract_docx(data: bytes) -> Extracted:
    _check_docx_archive_bounds(data)
    # zipfile.BadZipFile, docx.opc.exceptions.PackageNotFoundError and
    # KeyError from here on are the corrupted-DOCX class (ERR-01 row 3);
    # none of them is caught here, they propagate to the caller by type.
    document = docx.Document(io.BytesIO(data))
    parts: list[str] = []
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            parts.append(Paragraph(child, document).text)
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rows = ["\t".join(cell.text for cell in row.cells) for row in table.rows]
            parts.append("\n".join(rows))
    text = "\n".join(parts)
    return Extracted(pages=(ExtractedPage(text=text, page=None),), page_numbered=False)


def _extract_pdf(
    data: bytes,
    *,
    monotonic: Callable[[], float] | None = None,
    started_at: float | None = None,
    budget_s: float | None = None,
) -> Extracted:
    # Only exceptions from PdfReader, from page enumeration or from
    # extract_text() are the corrupted-PDF class (ERR-01 row 2); none of
    # them is caught here, they propagate to the caller by type.
    # `_check_budget` (raising `IndexBudgetExceeded`) sits outside that
    # implicit boundary too -- it is never wrapped in a try here, so it can
    # never be mistaken for a corrupted PDF (DOC-02, ERR-01 row 2 vs 10c).
    reader = pypdf.PdfReader(io.BytesIO(data))
    if len(reader.pages) > PDF_MAX_PAGES:
        raise PdfTooManyPagesError(
            f"{len(reader.pages)} pages exceeds the {PDF_MAX_PAGES}-page bound"
        )
    pages = []
    for physical_index, page in enumerate(reader.pages, start=1):
        if started_at is not None:
            _check_budget(monotonic, started_at, budget_s, stage="pdf extraction")
        text = page.extract_text()
        if text.strip():
            pages.append(ExtractedPage(text=text, page=physical_index))
    return Extracted(pages=tuple(pages), page_numbered=True)


# ---------------------------------------------------------------------------
# REQ-V190-DOC-03: chunking is character-based and paragraph-aware.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    text: str
    char_start: int
    char_end: int


# A text this short yields one chunk if it clears this floor, else none
# (DOC-04 turns zero chunks into the "empty document" refusal). Distinct
# from the `minimum` parameter, which governs only the final-chunk tail
# merge below.
_MIN_NONWHITESPACE_CHARS_FOR_ONE_CHUNK = 20

_BLANK_LINE = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"[.!?]+\s+")


def _nonwhitespace_len(s: str) -> int:
    return sum(1 for ch in s if not ch.isspace())


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Paragraph content spans, separators excluded -- but never lost: a
    chunk spanning several paragraphs is always sliced from the first
    paragraph's start to the last one's end, so any separator between them
    survives untouched inside that slice."""
    spans = []
    pos = 0
    for m in _BLANK_LINE.finditer(text):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def _split_long_span(text: str, start: int, end: int, target: int) -> list[tuple[int, int]]:
    """Splits one paragraph span too long for `target` into sentence-bounded
    pieces of at most `target` characters; a sentence still too long is
    hard-cut at exactly `target`, never at `hard_max`."""
    breakpoints = [start + m.end() for m in _SENTENCE_END.finditer(text, start, end)]
    pieces = []
    pos = start
    while pos < end:
        reachable = [b for b in breakpoints if pos < b <= min(pos + target, end)]
        piece_end = max(reachable) if reachable else min(pos + target, end)
        pieces.append((pos, piece_end))
        pos = piece_end
    return pieces


def _atomic_spans(text: str, target: int) -> list[tuple[int, int]]:
    spans = []
    for start, end in _paragraph_spans(text):
        if end - start <= target:
            spans.append((start, end))
        else:
            spans.extend(_split_long_span(text, start, end, target))
    return spans


def _start_new_chunk(
    raw_chunks: list[tuple[int, int]],
    span_start: int,
    span_end: int,
    overlap: int,
    hard_max: int,
) -> tuple[int, int, int]:
    """Returns `(char_start, new_material_start, current_end)` for a chunk
    beginning at `span_start`. `char_start` reaches back `overlap`
    characters into the previous chunk's text (rule 4); for the very first
    chunk it is just `span_start`. `new_material_start` anchors at the
    previous chunk's own end (not at `span_start`), so a separator gap
    between the two counts against the new-material budget rather than
    silently inflating the chunk beyond it. The first atomic span of a new
    chunk is always included (a chunk must make progress); if that alone --
    plus the separator gap before it -- would push the chunk past
    `hard_max`, `char_start` is pulled forward just enough to hold the line
    (rule 2 is an absolute ceiling, taking priority over the full `overlap`
    prefix in this rare case)."""
    if raw_chunks:
        prev_start, prev_end = raw_chunks[-1]
        char_start = max(prev_start, prev_end - overlap)
        new_material_start = prev_end
    else:
        char_start = span_start
        new_material_start = span_start
    char_start = max(char_start, span_end - hard_max)
    return char_start, new_material_start, span_end


def chunk_text(
    text: str,
    *,
    target: int = 1000,
    hard_max: int = 1200,
    overlap: int = 200,
    minimum: int = 50,
) -> list[Chunk]:
    """DOC-03's offset-based, paragraph-aware chunker. Deterministic: same
    input, same output, no randomness, no clock."""
    atomic = _atomic_spans(text, target)
    if not atomic:
        return []

    raw_chunks: list[tuple[int, int]] = []
    char_start = new_material_start = current_end = None
    for span_start, span_end in atomic:
        if char_start is None:
            char_start, new_material_start, current_end = _start_new_chunk(
                raw_chunks, span_start, span_end, overlap, hard_max
            )
            continue
        if span_end - new_material_start <= target:
            current_end = span_end
        else:
            raw_chunks.append((char_start, current_end))
            char_start, new_material_start, current_end = _start_new_chunk(
                raw_chunks, span_start, span_end, overlap, hard_max
            )
    raw_chunks.append((char_start, current_end))

    chunks = [Chunk(text=text[s:e], char_start=s, char_end=e) for s, e in raw_chunks]

    if len(chunks) == 1:
        if _nonwhitespace_len(chunks[0].text) >= _MIN_NONWHITESPACE_CHARS_FOR_ONE_CHUNK:
            return chunks
        return []

    last = chunks[-1]
    if _nonwhitespace_len(last.text) < minimum:
        prev = chunks[-2]
        merged_start, merged_end = prev.char_start, last.char_end
        if merged_end - merged_start <= hard_max:
            merged = Chunk(
                text=text[merged_start:merged_end],
                char_start=merged_start,
                char_end=merged_end,
            )
            chunks = [*chunks[:-2], merged]
    return chunks


# ---------------------------------------------------------------------------
# REQ-V190-DOC-04/-05: the indexing pipeline. `index_document` never touches
# Telegram -- `progress` is its only output channel besides the return value
# and the exceptions below, which are distinguished by type (never by
# message) so `bot.py` (T7) can match them in its ERR-01 handlers.
# ---------------------------------------------------------------------------

MAX_EXTRACTED_TEXT_CHARS = 500_000
EMBED_BATCH_SIZE = 32
INDEX_BUDGET_S_DEFAULT = 300.0
DOCUMENT_LIMIT = 20


class EmptyDocumentError(Exception):
    """DOC-04 row 4: fewer than 20 non-whitespace characters were extracted,
    summed over every page -- raised after extraction, before chunking.
    Also raised after chunking, before embedding, when extraction clears
    that summed floor but chunking still yields zero chunks overall (a
    multi-page PDF where every page individually falls under chunk_text's
    own per-call floor). Both paths are the identical user-facing outcome,
    so both raise this one class."""


class ExtractedTextTooLargeError(DocumentTooLargeError):
    """DOC-04 row 5b, the post-extraction half: the extracted text (summed
    over every page) exceeds `MAX_EXTRACTED_TEXT_CHARS`. Subclasses
    `DocumentTooLargeError` alongside `DocxArchiveTooLargeError` and
    `PdfTooManyPagesError` so `except documents.DocumentTooLargeError` in
    `bot.py` catches every row-5b variant with one clause, while the three
    concrete classes still let the log line's differing detail be told
    apart."""


class IndexBudgetExceeded(Exception):
    """DOC-04 row 10c: `monotonic() - started_at > budget_s` at a stage
    boundary (after extraction, after chunking, after an embeddings batch)
    or between PDF pages inside extraction. A plain `Exception` subclass,
    not a `DocumentTooLargeError` and not caught anywhere in this module, so
    it can never be folded into row 2's corrupted-PDF class or row 5b's
    too-large class -- it always propagates to the caller unmapped."""


class DocumentLimitExceededError(Exception):
    """ERR-01 row 13: the user already has `DOCUMENT_LIMIT` (20) documents
    and this filename is not one of them -- so this upload would not be a
    replace. `index_document` raises this from the transactional recheck
    immediately before the document row is inserted; `bot.py` (T7) raises
    the same exception class from CMD-03's earlier, advisory pre-check, so
    both call sites map to the identical row-13 string through one
    `except documents.DocumentLimitExceededError` clause."""


@dataclass(frozen=True)
class IndexResult:
    chunk_count: int
    page_count: int | None
    text_chars: int
    replaced: bool


def _check_budget(
    monotonic: Callable[[], float], started_at: float, budget_s: float, *, stage: str
) -> None:
    elapsed = monotonic() - started_at
    if elapsed > budget_s:
        raise IndexBudgetExceeded(f"budget exceeded after {stage}: {elapsed:.1f}s > {budget_s}s")


def _document_chunks(extracted: Extracted) -> list[tuple[int | None, Chunk]]:
    """DOC-03's per-page chunking rule: for a PDF, `chunk_text` runs once per
    (non-empty) page -- a chunk never spans pages, and the page number
    carried alongside it is that page's 1-based physical index. For every
    other type there is exactly one page and `page` is `None`. Order is
    document order; `index_document` assigns the 0-based `chunk_index`
    across every page from this order."""
    rows: list[tuple[int | None, Chunk]] = []
    for extracted_page in extracted.pages:
        page_number = extracted_page.page if extracted.page_numbered else None
        for chunk in chunk_text(extracted_page.text):
            rows.append((page_number, chunk))
    return rows


def index_document(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    data: bytes,
    embedder,
    progress: Callable[[str], None],
    now: str,
    started_at: float,
    monotonic: Callable[[], float] = time.monotonic,
    budget_s: float = INDEX_BUDGET_S_DEFAULT,
) -> IndexResult:
    """DOC-05's pipeline: classify -> extract -> chunk -> embed -> store.
    `started_at` has no default -- the caller (`bot.py`'s `_handle_document`)
    must supply its own first-action `monotonic()` reading, so the budget's
    origin can never be lost by omission. Emits exactly three progress
    strings (classify and store emit nothing); on any DOC-04 limit or budget
    failure, raises before any store -- no transaction has opened yet, so
    nothing is written."""
    file_type = classify(filename)

    extracted = extract(
        data, file_type, monotonic=monotonic, started_at=started_at, budget_s=budget_s
    )
    text_chars = sum(len(page.text) for page in extracted.pages)
    if extracted.page_numbered:
        progress(f"📄 extracted: {len(extracted.pages)} pages, {text_chars} chars")
    else:
        progress(f"📄 extracted: {text_chars} chars")

    if text_chars > MAX_EXTRACTED_TEXT_CHARS:
        raise ExtractedTextTooLargeError(
            f"extracted text {text_chars} chars exceeds the {MAX_EXTRACTED_TEXT_CHARS}-char bound"
        )
    nonwhitespace_chars = sum(_nonwhitespace_len(page.text) for page in extracted.pages)
    if nonwhitespace_chars < _MIN_NONWHITESPACE_CHARS_FOR_ONE_CHUNK:
        raise EmptyDocumentError(
            f"{nonwhitespace_chars} non-whitespace chars extracted, under the "
            f"{_MIN_NONWHITESPACE_CHARS_FOR_ONE_CHUNK}-char floor"
        )
    _check_budget(monotonic, started_at, budget_s, stage="extraction")

    chunk_rows = _document_chunks(extracted)
    progress(f"📄 chunked: {len(chunk_rows)}")
    if not chunk_rows:
        # Erratum found by T4 while writing the PDF test: DOC-04's
        # extraction-time floor sums non-whitespace chars across every page,
        # but DOC-03 chunks each PDF page independently, and chunk_text()
        # applies its own single-chunk floor per call. A multi-page PDF can
        # clear the summed floor while every individual page falls under
        # chunk_text()'s own floor, yielding zero chunks overall -- the same
        # user-facing outcome as an empty document, so it raises the same
        # exception class ERR-01 row 4 already maps downstream.
        raise EmptyDocumentError(
            f"chunking yielded 0 chunks from {nonwhitespace_chars} non-whitespace "
            "chars (each page/section fell under chunk_text's own floor)"
        )
    _check_budget(monotonic, started_at, budget_s, stage="chunking")

    texts = [chunk.text for _, chunk in chunk_rows]
    total_batches = (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    vectors: list[bytes] = []
    for batch_start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[batch_start : batch_start + EMBED_BATCH_SIZE]
        batch_vectors = embedder.embed(batch)
        vectors.extend(sqlite_vec.serialize_float32(vector) for vector in batch_vectors)
        batch_no = batch_start // EMBED_BATCH_SIZE + 1
        progress(f"📄 embedding: {batch_no}/{total_batches}")
        _check_budget(monotonic, started_at, budget_s, stage=f"embedding batch {batch_no}")

    page_count = len(extracted.pages) if extracted.page_numbered else None
    size_bytes = len(data)
    sha256 = hashlib.sha256(data).hexdigest()

    conn.execute("BEGIN IMMEDIATE")
    try:
        existing_id = storage.document_id_for(conn, user_id=user_id, filename=filename)
        if existing_id is None and storage.document_count(conn, user_id=user_id) >= DOCUMENT_LIMIT:
            raise DocumentLimitExceededError(
                f"user {user_id} already has {DOCUMENT_LIMIT} documents"
            )
        replaced = existing_id is not None
        if replaced:
            storage.delete_document(conn, user_id=user_id, document_id=existing_id)
        document_id = storage.add_document(
            conn,
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            created_at=now,
            size_bytes=size_bytes,
            text_chars=text_chars,
            page_count=page_count,
            chunk_count=len(chunk_rows),
            sha256=sha256,
        )
        chunk_ids = storage.add_chunks(
            conn,
            user_id=user_id,
            document_id=document_id,
            chunks=[
                (index, chunk.text, page, chunk.char_start, chunk.char_end)
                for index, (page, chunk) in enumerate(chunk_rows)
            ],
        )
        storage.add_vectors(conn, user_id=user_id, rows=list(zip(chunk_ids, vectors, strict=True)))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise

    return IndexResult(
        chunk_count=len(chunk_rows),
        page_count=page_count,
        text_chars=text_chars,
        replaced=replaced,
    )
