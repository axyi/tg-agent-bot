"""REQ-V1110-OUT-03: `render_table`, a pure function with no I/O -- and
`fit_lines`/`utf16_length`, the two small utilities the outbound table path
(`bot.py`'s `_pre_text`/`send_pre`/`edit_pre`, spec-v1.11.0 sec.3) builds on.

`utf16_length` moved here from `bot.py` (spec-v1.11.0 T1); `bot.py`
re-imports it so `bot.utf16_length` keeps its name and behaviour for every
existing caller.

Placed at the repository root (not `devtools/`) -- it joins
`GATE8_DEPENDENCIES` by the `*.py` glob, which is intentional (gate 8 runs
once, later, at T7).
"""

from collections.abc import Sequence

ELLIPSIS = "…"  # U+2026 HORIZONTAL ELLIPSIS, one UTF-16 unit
MAX_TABLE_LINE_UNITS = 72
_COLUMN_SEPARATOR = "  "  # two spaces, REQ-V1110-OUT-03


def utf16_length(text: str) -> int:
    """Telegram counts UTF-16 code units, exactly as `bot.split_message` does
    (an astral code point such as U+1F600 costs two units, everything on the
    Basic Multilingual Plane costs one)."""
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def _cell_str(value: object) -> str:
    return "n/a" if value is None else str(value)


def _is_numeric(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _truncate_cell(text: str, max_width: int) -> str:
    """Truncate `text` to fit `max_width` UTF-16 units, never splitting a
    Unicode scalar (an astral character is kept whole or dropped whole) and
    reserving one unit for the trailing `...` so the result always satisfies
    `utf16_length(result) <= max_width`."""
    if utf16_length(text) <= max_width:
        return text
    budget = max_width - 1  # one unit reserved for the ellipsis
    kept: list[str] = []
    used = 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > budget:
            break
        kept.append(char)
        used += width
    return "".join(kept) + ELLIPSIS


def _column_alignments(
    n_cols: int,
    rows: Sequence[Sequence[object]],
    align: Sequence[str] | None,
) -> list[str]:
    result = []
    for col in range(n_cols):
        forced = align[col] if align is not None and col < len(align) else None
        if forced:
            result.append(forced)
            continue
        values = [row[col] for row in rows if col < len(row) and row[col] is not None]
        if values and all(_is_numeric(v) for v in values):
            result.append("r")
        else:
            result.append("l")
    return result


def _pad(text: str, width: int, alignment: str) -> str:
    gap = width - utf16_length(text)
    if gap <= 0:
        return text
    filler = " " * gap
    return filler + text if alignment == "r" else text + filler


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    align: Sequence[str] | None = None,
    max_width: Sequence[int | None] | None = None,
) -> str:
    """REQ-V1110-OUT-03. Returns raw, unescaped text -- `bot._pre_text` does
    the HTML-escaping once the table is embedded in a `<pre>` block. Raises
    `ValueError` when the rendered line width would exceed 72 UTF-16 units;
    callers choose `max_width` values that keep every table under that
    ceiling."""
    n_cols = len(headers)

    str_rows: list[list[str]] = [[_cell_str(v) for v in row] for row in rows]
    if max_width is not None:
        for row_idx in range(len(rows)):
            for col in range(n_cols):
                width = max_width[col] if col < len(max_width) else None
                if width is not None:
                    str_rows[row_idx][col] = _truncate_cell(str_rows[row_idx][col], width)

    alignments = _column_alignments(n_cols, rows, align)

    col_widths = []
    for col in range(n_cols):
        widest = utf16_length(headers[col])
        for row in str_rows:
            widest = max(widest, utf16_length(row[col]))
        col_widths.append(widest)

    line_width = sum(col_widths) + len(_COLUMN_SEPARATOR) * max(n_cols - 1, 0)
    if line_width > MAX_TABLE_LINE_UNITS:
        raise ValueError(
            f"render_table: rendered line width {line_width} exceeds the "
            f"{MAX_TABLE_LINE_UNITS}-unit ceiling -- narrow max_width or drop a column"
        )

    header_line = _COLUMN_SEPARATOR.join(
        _pad(headers[col], col_widths[col], alignments[col]) for col in range(n_cols)
    )
    rule_line = _COLUMN_SEPARATOR.join("-" * col_widths[col] for col in range(n_cols))
    lines = [header_line, rule_line]
    lines.extend(
        _COLUMN_SEPARATOR.join(
            _pad(row[col], col_widths[col], alignments[col]) for col in range(n_cols)
        )
        for row in str_rows
    )
    return "\n".join(lines)


def fit_lines(lines: Sequence[str], *, limit: int) -> str:
    """REQ-V1110-OUT-01. Fit `lines` to `limit` UTF-16 units, joined by
    `"\\n"` with no trailing newline. Whole lines are dropped from the end
    and a final `"... N more"` line appended until it fits -- over lines,
    never a hard slice inside a line."""
    all_lines = list(lines)
    joined = "\n".join(all_lines)
    if utf16_length(joined) <= limit:
        return joined

    total = len(all_lines)
    kept = list(all_lines)
    while kept:
        kept.pop()
        dropped = total - len(kept)
        marker = f"{ELLIPSIS} {dropped} more"
        candidate = "\n".join([*kept, marker])
        if utf16_length(candidate) <= limit:
            return candidate
    return f"{ELLIPSIS} {total} more"
