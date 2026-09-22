"""spec-v1.11.0 T2: `/stats` as one `<pre>` table (REQ-V1110-STA-01..-03).

Builds on T1's outbound table path (`tables.py`, `bot.send_pre`). Reuses
`tests/test_observability.py`'s fixtures (`add_call`/`add_tool`/
`seed_conversation`/`make_cfg`/`process`/`update`/`USER_ID`) -- the same
fixtures `tests/test_v160_observability.py` itself imports from there.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import storage
import tables
from tests.fakes import FakeTelegram
from tests.test_observability import (
    USER_ID,
    add_call,
    add_tool,
    make_cfg,
    process,
    seed_conversation,
    update,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_README_MD = _REPO_ROOT / "README.md"

# REQ-V1110-STA-01: the ten paired-row labels, then the four single-value
# labels, in the order `_render_stats` must emit them.
STATS_LABELS_IN_ORDER = [
    "LLM calls",
    "errors",
    "tokens in",
    "cached",
    "reasoning",
    "tokens out",
    "est. cost",
    "cost basis",
    "avg prompt/call",
    "re-sent share",
    "Top tools:",
    "Last turn:",
    "Errors:",
    "Summaries:",
]


def _row(text: str, label: str, *values: str) -> bool:
    """`label` followed, in order and tolerant of table padding/whitespace,
    by each of `values` -- REQ-V1110-PIN-01's presence/contiguity rewrite
    form, never a whole-line equality."""
    pattern = re.escape(label) + r"\s+" + r"\s+".join(re.escape(v) for v in values)
    return re.search(pattern, text) is not None


def _stats_body(conn, cfg, update_id=1) -> str:
    """Drives `/stats` through `process_update` on a real `FakeTelegram`
    (the default `RecordingTelegram` in `test_observability.py` has no
    `send_message_html`), asserts the table path was used, and returns the
    plain, unescaped `<pre>` body."""
    tg = process(conn, cfg, update(text="/stats", update_id=update_id), tg=FakeTelegram())
    assert len(tg.sent) == 1  # one table-path message
    assert tg.sent_payloads[-1].get("parse_mode") == "HTML"
    raw = tg.sent[0][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    return html.unescape(raw[len("<pre>") : -len("</pre>")])


def test_t_v1110_sta_01_stats_table_labels_and_cells(conn, tmp_path):
    cfg = make_cfg(tmp_path)

    # An empty database: labels present in order; n/a and n/a (no pricing)
    # as cell content; the "none" single-value cases.
    empty_body = _stats_body(conn, cfg, update_id=1)
    positions = [empty_body.index(label) for label in STATS_LABELS_IN_ORDER]
    assert positions == sorted(positions)
    assert _row(empty_body, "LLM calls", "0", "0")
    assert _row(empty_body, "errors", "0", "0")
    assert _row(empty_body, "tokens in", "n/a", "n/a")
    assert _row(empty_body, "est. cost", "n/a (no pricing)", "n/a (no pricing)")
    assert "Top tools: none" in empty_body
    assert "Last turn: none" in empty_body
    # A read-only command never opens a conversation.
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0

    # A mixed cost basis (several bases on the same side) and the percent
    # rendering of re-sent share, on a real conversation.
    seed_conversation(conn, basis=("provider", "openrouter-list-stale"))
    mixed_body = _stats_body(conn, cfg, update_id=2)
    assert _row(mixed_body, "cost basis", "mixed", "mixed")
    assert re.search(r"re-sent share\s+\d+%\s+\d+%", mixed_body)
    assert _row(mixed_body, "LLM calls", "2", "2")
    assert _row(mixed_body, "tokens in", "6492", "6492")


def test_t_v1110_sta_02_stats_fit_drops_whole_lines(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    add_call(conn, conv)
    add_tool(conn, conv, tool="x" * 5000, output_tokens_est=100)

    body = _stats_body(conn, cfg)
    lines = body.splitlines()
    assert len(body) <= 3500
    assert "metric" in lines[0]  # the table header survives the drop
    assert lines[-1].startswith("… ") and lines[-1].endswith(" more")
    assert all(tables.utf16_length(line) <= 72 for line in lines)

    # The wrapping step itself (before `fit_lines` ever drops a whole line):
    # continuation lines are indented by two spaces, each within the
    # 72-unit ceiling, never split inside a scalar.
    import bot

    long_line = f"Top tools: {'x' * 5000} 100 (100%)"
    wrapped = bot._wrap_line(long_line)
    assert len(wrapped) > 1
    assert all(tables.utf16_length(w) <= 72 for w in wrapped)
    assert all(w.startswith("  ") for w in wrapped[1:])
    assert 50 <= len(wrapped) - 1 <= 90  # "≈70 continuation lines" per the brief


def test_t_v1110_sta_03_readme_stats_sample_labels():
    text = _README_MD.read_text(encoding="utf-8")
    stats_idx = text.index("### `/stats`")
    next_idx = text.index("### What is recorded")
    section = text[stats_idx:next_idx]
    for label in STATS_LABELS_IN_ORDER:
        assert label in section, f"missing /stats label in README: {label!r}"
    positions = [section.index(label) for label in STATS_LABELS_IN_ORDER]
    assert positions == sorted(positions)
