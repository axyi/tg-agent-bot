"""spec-v1.9.0 T3 (docs/spec/spec-v1.9.0.md §3, REQ-V190-DOC-01, -02, -06):
`documents.classify`/`clean_filename`, `documents.extract` for txt/md/docx/pdf
(including the DOC-02 pre-parse guards and the corrupted-document exception
boundaries), and `devtools/pdf_fixture.write_pdf`.

Offline and deterministic. Every fixture is generated at test time: txt/md as
literals, DOCX via `python-docx` into `io.BytesIO`, PDF via
`devtools.pdf_fixture.write_pdf`; corrupted variants are the first half of
the valid bytes, or a zip missing `word/document.xml`. Nothing binary is
committed.
"""

import inspect
import io
import zipfile

import docx as docx_lib
import docx.opc.exceptions
import pypdf
import pytest

import documents
from devtools.pdf_fixture import write_pdf

# ---------------------------------------------------------------------------
# T-V190-DOC-01: classify / clean_filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("report.txt", "txt"),
        ("notes.md", "md"),
        ("letter.docx", "docx"),
        ("Report.PDF", "pdf"),
        ("archive.PDF.exe", None),
        ("noextension", None),
        ("file.doc", None),
        ("file.TXT", "txt"),
    ],
)
def test_t_v190_doc_01_classify_by_lowercase_extension(filename, expected):
    assert documents.classify(filename) == expected


def test_t_v190_doc_01_classify_ignores_mime_type():
    # classify takes only a filename -- there is no mime_type parameter to
    # pass in the first place, which is the point: Telegram's mime_type is
    # structurally unreachable from this function.
    params = inspect.signature(documents.classify).parameters
    assert list(params) == ["filename"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("a/b\\c.txt", "abc.txt"),
        ("bad\x00\x1fname\x7f.txt", "badname.txt"),
        ("  spaced.txt  ", "spaced.txt"),
    ],
)
def test_t_v190_doc_01_clean_filename_strips_and_normalises(raw, expected):
    assert documents.clean_filename(raw) == expected


def test_t_v190_doc_01_clean_filename_caps_at_120_chars():
    cleaned = documents.clean_filename("x" * 150 + ".txt")
    assert cleaned is not None
    assert len(cleaned) == 120


def test_t_v190_doc_01_clean_filename_empty_after_cleaning_is_none():
    assert documents.clean_filename("/\\\x00\x1f\x7f") is None


# ---------------------------------------------------------------------------
# T-V190-DOC-02: extract -- txt/md
# ---------------------------------------------------------------------------


def test_t_v190_doc_02_txt_decodes_utf8_sig():
    data = "Hello А".encode("utf-8-sig")
    extracted = documents.extract(data, "txt")
    assert extracted == documents.Extracted(
        pages=(documents.ExtractedPage(text="Hello А", page=None),),
        page_numbered=False,
    )


def test_t_v190_doc_02_md_decodes_cp1251_fallback():
    data = "Привет".encode("cp1251")
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8-sig")
    extracted = documents.extract(data, "md")
    assert extracted.pages == (
        documents.ExtractedPage(text="Привет", page=None),
    )
    assert extracted.page_numbered is False


def test_t_v190_doc_02_txt_keeps_markdown_syntax_as_text():
    data = "# Heading\n\n*bold*".encode("utf-8-sig")
    extracted = documents.extract(data, "md")
    assert extracted.pages[0].text == "# Heading\n\n*bold*"


# ---------------------------------------------------------------------------
# T-V190-DOC-02: extract -- docx
# ---------------------------------------------------------------------------


def _docx_bytes(build) -> bytes:
    doc = docx_lib.Document()
    build(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_t_v190_doc_02_docx_paragraphs_and_tables_in_document_order():
    def build(doc):
        doc.add_paragraph("First paragraph")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "a"
        table.cell(0, 1).text = "b"
        table.cell(1, 0).text = "c"
        table.cell(1, 1).text = "d"
        doc.add_paragraph("Last paragraph")

    data = _docx_bytes(build)
    extracted = documents.extract(data, "docx")
    assert extracted.pages == (
        documents.ExtractedPage(
            text="First paragraph\na\tb\nc\td\nLast paragraph", page=None
        ),
    )
    assert extracted.page_numbered is False


def test_t_v190_doc_02_docx_truncated_is_bad_zip_file():
    data = _docx_bytes(lambda doc: doc.add_paragraph("hello"))
    with pytest.raises(zipfile.BadZipFile):
        documents.extract(data[: len(data) // 2], "docx")


def test_t_v190_doc_02_docx_zip_without_document_xml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("not_a_docx.txt", "hello")
    with pytest.raises((docx.opc.exceptions.PackageNotFoundError, KeyError)):
        documents.extract(buf.getvalue(), "docx")


def test_t_v190_doc_02_docx_archive_too_many_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(documents.DOCX_MAX_MEMBERS + 1):
            zf.writestr(f"f{i}.txt", "x")
    with pytest.raises(documents.DocxArchiveTooLargeError):
        documents.extract(buf.getvalue(), "docx")


def test_t_v190_doc_02_docx_archive_member_too_large():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("big.bin", b"\x00" * (documents.DOCX_MAX_MEMBER_UNCOMPRESSED_BYTES + 1))
    with pytest.raises(documents.DocxArchiveTooLargeError):
        documents.extract(buf.getvalue(), "docx")


def test_t_v190_doc_02_docx_archive_compression_ratio_too_high():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("bomb.bin", b"\x00" * (5 * 1024 * 1024))
    with pytest.raises(documents.DocxArchiveTooLargeError):
        documents.extract(buf.getvalue(), "docx")


def test_t_v190_doc_02_docx_archive_guard_fires_before_python_docx():
    # A zip that is missing word/document.xml (python-docx would raise
    # PackageNotFoundError/KeyError for it) AND violates the member bound:
    # the archive-bounds guard must win, proving it runs before python-docx
    # ever touches the bytes.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(documents.DOCX_MAX_MEMBERS + 1):
            zf.writestr(f"f{i}.txt", "x")
    with pytest.raises(documents.DocxArchiveTooLargeError):
        documents.extract(buf.getvalue(), "docx")


# ---------------------------------------------------------------------------
# T-V190-DOC-02: extract -- pdf
# ---------------------------------------------------------------------------


def test_t_v190_doc_02_pdf_per_page_text_and_physical_numbering():
    data = write_pdf(["Page one text", "Page three text"])
    extracted = documents.extract(data, "pdf")
    assert extracted.page_numbered is True
    assert [p.page for p in extracted.pages] == [1, 2]
    assert extracted.pages[0].text.strip() == "Page one text"
    assert extracted.pages[1].text.strip() == "Page three text"


def test_t_v190_doc_02_pdf_empty_pages_are_skipped_and_numbering_stays_physical():
    data = write_pdf(["Page one text", "", "Page three text"])
    extracted = documents.extract(data, "pdf")
    assert extracted.page_numbered is True
    assert [p.page for p in extracted.pages] == [1, 3]
    assert [p.text.strip() for p in extracted.pages] == ["Page one text", "Page three text"]


def test_t_v190_doc_02_pdf_no_page_numbers_field_and_extracted_shape():
    data = write_pdf(["hello"])
    extracted = documents.extract(data, "pdf")
    assert not hasattr(extracted, "page_numbers")
    assert isinstance(extracted.pages, tuple)
    assert isinstance(extracted, documents.Extracted)
    assert isinstance(extracted.pages[0], documents.ExtractedPage)


def test_t_v190_doc_02_pdf_truncated_is_corrupted_pdf_class():
    # documents._extract_pdf catches nothing from PdfReader/page enumeration/
    # extract_text() -- the corrupted-PDF class propagates by its own native
    # type. For this truncation (first 20 bytes: past "%PDF-1.4\n" but into
    # the middle of the first indirect object, well before any xref/trailer)
    # pypdf raises PdfStreamError, a PdfReadError, a PyPdfError -- verified
    # empirically, not assumed: the bare `except Exception` this replaces
    # would also pass if the wrong exception type leaked through.
    data = write_pdf(["hello world"])
    with pytest.raises(pypdf.errors.PdfStreamError):
        documents.extract(data[:20], "pdf")


def test_t_v190_doc_02_too_many_pages_is_not_the_corrupted_pdf_class():
    # DOC-02's exact exception-boundary rule, which T4 depends on: the
    # too-many-pages refusal and the corrupted-PDF class must be genuinely
    # distinguishable by type, not merely by message text -- an `except`
    # clause written for the corrupted-PDF family (pypdf's own
    # PdfReadError/PyPdfError, which PdfStreamError above subclasses) must
    # NOT also swallow PdfTooManyPagesError.
    data = write_pdf(["x"] * (documents.PDF_MAX_PAGES + 1))
    with pytest.raises(documents.PdfTooManyPagesError) as exc_info:
        documents.extract(data, "pdf")
    assert not isinstance(exc_info.value, pypdf.errors.PdfReadError)
    assert not isinstance(exc_info.value, pypdf.errors.PyPdfError)


def test_t_v190_doc_02_pdf_over_500_pages_refuses_before_extract_text():
    data = write_pdf(["x"] * (documents.PDF_MAX_PAGES + 1))
    with pytest.raises(documents.PdfTooManyPagesError):
        documents.extract(data, "pdf")


def test_t_v190_doc_02_pdf_500_pages_exactly_is_accepted():
    data = write_pdf(["x"] * documents.PDF_MAX_PAGES)
    extracted = documents.extract(data, "pdf")
    assert len(extracted.pages) == documents.PDF_MAX_PAGES


def test_t_v190_doc_02_too_large_family_shares_a_common_base():
    assert issubclass(documents.DocxArchiveTooLargeError, documents.DocumentTooLargeError)
    assert issubclass(documents.PdfTooManyPagesError, documents.DocumentTooLargeError)


def test_t_v190_doc_02_unsupported_file_type_raises_value_error():
    with pytest.raises(ValueError):
        documents.extract(b"data", "exe")


# ---------------------------------------------------------------------------
# T-V190-DOC-06: devtools/pdf_fixture.write_pdf
# ---------------------------------------------------------------------------


def test_t_v190_doc_06_write_pdf_round_trips_through_pypdf():
    data = write_pdf(["First page\nSecond line", "Second page"])
    reader = pypdf.PdfReader(io.BytesIO(data))
    assert len(reader.pages) == 2
    assert "First page" in reader.pages[0].extract_text()
    assert "Second line" in reader.pages[0].extract_text()
    assert "Second page" in reader.pages[1].extract_text()


def test_t_v190_doc_06_write_pdf_escapes_special_characters():
    data = write_pdf(["Text (with parens) and \\backslash\\"])
    reader = pypdf.PdfReader(io.BytesIO(data))
    text = reader.pages[0].extract_text()
    assert "(with parens)" in text
    assert "\\backslash\\" in text


def test_t_v190_doc_06_write_pdf_rejects_non_ascii():
    with pytest.raises(ValueError):
        write_pdf(["café"])


def test_t_v190_doc_06_write_pdf_rejects_over_60_lines():
    with pytest.raises(ValueError):
        write_pdf(["\n".join(str(i) for i in range(61))])


def test_t_v190_doc_06_write_pdf_accepts_exactly_60_lines():
    data = write_pdf(["\n".join(str(i) for i in range(60))])
    reader = pypdf.PdfReader(io.BytesIO(data))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "0" in text
    assert "59" in text
