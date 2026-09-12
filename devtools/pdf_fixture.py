"""spec-v1.9.0 T3 (docs/spec/spec-v1.9.0.md Sec.3, REQ-V190-DOC-06): a
standard-library-only PDF-1.4 fixture writer, so `tests/test_v190_parsing.py`
and `devtools/rag_eval.py` (T8) never need to commit a binary fixture.

`write_pdf(pages)` hand-builds one Helvetica-12pt page per input string --
ASCII text only, lines drawn top-down at 14pt leading, at most 60 lines per
page -- with a correct `xref` table and `trailer` so `pypdf` 6.18.0 reads
every page back and `extract_text()` returns the lines.

`devtools/` is never imported by the bot (AGENTS.md); this module is
imported by tests and by `devtools/rag_eval.py` only, and imports nothing
from the bot's own modules.
"""

import argparse
from collections.abc import Sequence
from pathlib import Path

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
FONT_SIZE = 12
LEADING = 14
LEFT_MARGIN = 72
TOP_MARGIN = 720
MAX_LINES_PER_PAGE = 60


def _escape_pdf_text(line: str) -> str:
    """Escapes `\\`, `(` and `)` for a PDF literal string. Backslash first,
    so the parentheses' own escapes are not re-escaped."""
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_content_stream(text: str) -> bytes:
    lines = text.split("\n")
    if len(lines) > MAX_LINES_PER_PAGE:
        raise ValueError(f"page has {len(lines)} lines, over the {MAX_LINES_PER_PAGE}-line bound")
    ops = [
        b"BT",
        f"/F1 {FONT_SIZE} Tf".encode("ascii"),
        f"{LEFT_MARGIN} {TOP_MARGIN} Td".encode("ascii"),
    ]
    for i, line in enumerate(lines):
        if i > 0:
            ops.append(f"0 -{LEADING} Td".encode("ascii"))
        ops.append(f"({_escape_pdf_text(line)}) Tj".encode("ascii"))
    ops.append(b"ET")
    return b"\n".join(ops)


def write_pdf(pages: Sequence[str]) -> bytes:
    """A PDF-1.4 byte string with one page per element of `pages`, Helvetica
    12pt, drawn top-down. Raises `ValueError` for a non-ASCII character or
    for a page with more than `MAX_LINES_PER_PAGE` lines."""
    for text in pages:
        try:
            text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError(f"non-ASCII character in page text: {exc}") from exc

    content_streams = [_page_content_stream(text) for text in pages]

    n_pages = len(pages)
    # Object numbers: 1 catalog, 2 pages, 3 font, then a (page, content)
    # pair per page starting at 4.
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
    pages_dict = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("ascii")
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    objects: list[bytes] = [catalog, pages_dict, font]
    for i, stream_body in enumerate(content_streams):
        content_num = 5 + 2 * i
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_num} 0 R >>"
        ).encode("ascii")
        objects.append(page_dict)
        content_obj = (
            f"<< /Length {len(stream_body)} >>\nstream\n".encode("ascii")
            + stream_body
            + b"\nendstream"
        )
        objects.append(content_obj)

    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{idx} 0 obj\n".encode("ascii")
        buf += body
        buf += b"\nendobj\n"

    xref_offset = len(buf)
    n_objs = len(objects) + 1
    buf += f"xref\n0 {n_objs}\n".encode("ascii")
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode("ascii")
    buf += b"trailer\n"
    buf += f"<< /Size {n_objs} /Root 1 0 R >>\n".encode("ascii")
    buf += b"startxref\n"
    buf += f"{xref_offset}\n".encode("ascii")
    buf += b"%%EOF"
    return bytes(buf)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write a standard-library-only PDF fixture (REQ-V190-DOC-06)."
    )
    parser.add_argument("output", type=Path, help="output .pdf path")
    parser.add_argument("page", nargs="+", help="page text; one PDF page per argument")
    args = parser.parse_args(argv)
    data = write_pdf(args.page)
    args.output.write_bytes(data)
    print(f"wrote {len(data)} bytes, {len(args.page)} page(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
