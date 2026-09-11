"""spec-v1.9.0 T3 (docs/spec/spec-v1.9.0.md Sec.3, REQ-V190-DOC-01, -02, -03):
filename/type classification, in-memory extraction and paragraph-aware,
offset-based chunking. `documents.index_document` (DOC-04, DOC-05) is T4's
job, built on top of the pieces defined here.

Extraction runs entirely on in-memory `bytes`: no temporary file, no
`Path`, no `open()` anywhere in this module (`T-V190-SEC-04` greps it).
Neither this module nor `rag.py` (T5) imports `bot`.
"""

import io
import re
import zipfile
from dataclasses import dataclass

import docx
import pypdf
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

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
    kept = [
        ch
        for ch in raw
        if ch not in _PATH_SEPARATORS and ord(ch) >= 32 and ord(ch) != 0x7F
    ]
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


def extract(data: bytes, file_type: str) -> Extracted:
    if file_type in ("txt", "md"):
        return _extract_text(data)
    if file_type == "docx":
        return _extract_docx(data)
    if file_type == "pdf":
        return _extract_pdf(data)
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
                f"compression ratio {ratio:.1f} exceeds the "
                f"{DOCX_MAX_COMPRESSION_RATIO}x bound"
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


def _extract_pdf(data: bytes) -> Extracted:
    # Only exceptions from PdfReader, from page enumeration or from
    # extract_text() are the corrupted-PDF class (ERR-01 row 2); none of
    # them is caught here, they propagate to the caller by type. This loop
    # is deliberately left plain and linear -- T4 threads DOC-04's
    # between-pages budget check through it without restructuring.
    reader = pypdf.PdfReader(io.BytesIO(data))
    if len(reader.pages) > PDF_MAX_PAGES:
        raise PdfTooManyPagesError(
            f"{len(reader.pages)} pages exceeds the {PDF_MAX_PAGES}-page bound"
        )
    pages = []
    for physical_index, page in enumerate(reader.pages, start=1):
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
