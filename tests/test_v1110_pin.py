"""spec-v1.11.0 T6 (docs/spec/spec-v1.11.0.md sec.12, REQ-V1110-PIN-01,
REQ-V1110-PIN-02): the frozen-pin negative check and the README
Limits/Error-behaviour presence check. See
`docs/spec/task-briefs/v1110-T6.md`.

Rewrite form throughout (the v1.10.4 rule, `README.md:918`): presence,
never equality with a frozen matrix.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_README = _REPO_ROOT / "README.md"
_TESTS_DIR = _REPO_ROOT / "tests"
_T0_INVENTORY = _REPO_ROOT / "docs" / "spec" / "task-briefs" / "v1110-T0-pin-inventory.md"

# Quote-wrapped where the bare fragment would also match the *current*,
# still-live string it is a prefix of (`"Usage: /model [...]"` is a prefix
# of the live `MODEL_USAGE_REPLY`; `"500 pages"`/`"300 s"` would otherwise
# match unrelated current numbers like "2,000 pages"/"1800 s" mid-word, and
# also match prose that merely *names* the old figure for context); bare
# otherwise, matching the brief's own presentation.
_RETIRED_LITERAL_PATTERNS = (
    '"New conversation started."',
    "over 10 MiB",
    "over 500,000 characters",
    "over 300 s",
    '"Usage: /model [lmstudio|openrouter|auto]"',
    "10,485,760",
    '"500 pages"',
    '"300 s"',
    '"allowed_updates": ["message"]',
)


def _scanned_test_files():
    """Every `tests/**/*.py` file except this one and any `git show
    <tag>:`-reading version test (those legitimately read historical git
    blobs and file content at old tags, which may itself carry a retired
    literal as an old, correctly-superseded artefact -- not a live pin)."""
    this_file = Path(__file__).resolve()
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        if path.resolve() == this_file:
            continue
        text = path.read_text(encoding="utf-8")
        if "git show" in text:
            continue
        yield path, text


def test_t_v1110_pin_01_no_retired_literal_in_tests():
    violations = [
        f"{path.relative_to(_REPO_ROOT)}: {pattern!r}"
        for path, text in _scanned_test_files()
        for pattern in _RETIRED_LITERAL_PATTERNS
        if pattern in text
    ]
    assert violations == [], "retired literal(s) found: " + "; ".join(violations)

    assert _T0_INVENTORY.exists(), f"{_T0_INVENTORY} is missing"
    inventory_text = _T0_INVENTORY.read_text(encoding="utf-8")
    missing = [
        pattern for pattern in _RETIRED_LITERAL_PATTERNS if pattern.strip('"') not in inventory_text
    ]
    assert missing == [], f"T0 inventory never mentions: {missing!r}"


def _limits_section() -> str:
    text = _README.read_text(encoding="utf-8")
    start = text.index("## Limits")
    end = text.index("## Error behaviour")
    return text[start:end]


def _error_behaviour_section() -> str:
    text = _README.read_text(encoding="utf-8")
    start = text.index("## Error behaviour")
    end = text.index("## Versioning")
    return text[start:end]


def test_t_v1110_pin_02_readme_limits_and_error_rows():
    limits = _limits_section()
    for needle in (
        "20,000,000",
        "2,000,000",
        "1800 s",
        "2,000 pages",
        "one in flight per user",
        "/cancel",
    ):
        assert needle in limits, f"README Limits section missing: {needle!r}"

    error_section = _error_behaviour_section()
    # The seventeen ERR-01 row strings (spec-v1.11.0.md:1128-1144); row 18
    # (a 400 from Telegram on the table path) carries no fixed string.
    err_01_needles = (
        "File too large (over 20 MB).",  # row 1
        "Document too large (over 2,000,000 characters).",  # row 2
        "Document too large (DOCX archive bounds).",  # row 3
        "Document too large (over 2,000 pages).",  # row 4
        "Indexing timed out (over 1800 s). Nothing was saved.",  # row 5
        "Still indexing",  # row 6 (dynamic <name>, fixed prefix)
        "Indexing queue is full; try again later.",  # row 7
        "Cancelling",  # row 8 (dynamic <name>, fixed prefix)
        "Cancelled.",  # row 8 (the status this becomes)
        "Nothing to cancel.",  # row 9
        "Interrupted by restart.",  # row 10
        "Usage: /session <id> (see /sessions)",  # row 11
        "No session #",  # row 12 (dynamic <id>, fixed prefix)
        "No document named",  # row 13 (dynamic <argument>, fixed prefix)
        "Usage: /delete <filename>",  # row 14 (fixed prefix)
        "Expired — send the command again.",  # row 15
        "Unknown model for",  # row 16 (dynamic <provider>, fixed prefix)
        "Usage: /model [lmstudio\\|openrouter\\|auto] [<model>]",  # row 16 (alt, markdown-escaped)
        "Indexing is already finishing.",  # row 17
    )
    for needle in err_01_needles:
        assert needle in error_section, f"README Error behaviour section missing: {needle!r}"
