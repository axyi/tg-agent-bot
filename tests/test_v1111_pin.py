"""spec-v1.11.1 T0 (REQ-V1111-PIN-01, REQ-V1111-PIN-02): the T0 pin
inventory and the T0 floor artefacts, plus the "no v1.10 test renamed or
listed" guard. See `docs/spec/task-briefs/v1111-T0.md` and
`docs/spec/spec-v1.11.1.md:565-598`, `:700-701`.

Both tests are structural (EC-02's carve-out) and are excluded from the
T0 floor by construction -- they are written only after the floor and
the node-id list are measured. Rewrite form throughout: presence,
contiguity, order -- never a "nothing follows" assertion (REQ-V1104-NG-10).
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INVENTORY_MD = _REPO_ROOT / "docs" / "spec" / "task-briefs" / "v1111-T0-pin-inventory.md"
_NODEIDS_TXT = _REPO_ROOT / "docs" / "spec" / "task-briefs" / "v1111-T0-nodeids.txt"

_FLOOR = 2384

# PIN-01's own list of sites (docs/spec/spec-v1.11.1.md:567-598), named
# literally here so the test can assert each one is present in the
# inventory table -- never re-derived from the table itself.
_PIN_01_SITES = (
    "tests/test_v1110_doc.py:200-202",
    "tests/test_v1110_doc.py:378",
    "tests/test_v1110_ing.py:548",
    "tests/test_v190_agents.py:300",
    "tests/test_v1110_ver.py:135",
    "tests/test_v1110_mod.py",
    "tests/test_v1110_out.py",
    "tests/test_v1110_ver.py:75-78",
    "tests/test_v1110_ver.py:57",
    "tests/test_v1110_ver.py:106-112",
    "tests/test_v190_agents.py:138-162",
    "tests/test_v190_agents.py:92-99",
    "tests/test_v1104_docs.py:141",
    "tests/test_v1102_docs.py:167",
    "tests/test_v190_agents.py:331-332",
    "tests/test_v170_bench.py:329",
    "tests/test_v1102_gates.py:49",
    "tests/test_v1104_gates.py:212-216",
    # Found by tree-wide extension (never in the spec's own list): the
    # same "report_path tracks the current release" family as the four
    # sites above, plus VER-02's own trailing live-version literal.
    "tests/test_v1101_gates.py:259",
    "tests/test_v1103_gates.py:61",
    "tests/test_v1104_version.py:108",
    "tests/test_v1110_pin.py:100-120",
    "tests/test_v1110_err.py:119-199",
    "tests/test_v1110_ver.py:116-124",
    "tests/test_v190_agents.py:285-306",
    "tests/test_v1110_inventory.py",
)


def test_t_v1111_pin_01_inventory_artefacts_exist():
    # -- the inventory md: exists, four-column header, every PIN-01 site named --
    assert _INVENTORY_MD.is_file()
    inventory_text = _INVENTORY_MD.read_text(encoding="utf-8")
    assert "| site (file:line) | literal | task that rewrites it | rewrite form |" in inventory_text
    assert "|---|---|---|---|" in inventory_text
    missing = [site for site in _PIN_01_SITES if site not in inventory_text]
    assert missing == [], f"pin-inventory.md is missing site(s): {missing}"

    # -- the node-id list: exists, sorted, >= floor, every line carries '::' --
    assert _NODEIDS_TXT.is_file()
    lines = _NODEIDS_TXT.read_text(encoding="utf-8").splitlines()
    # Sortedness is checked with the same tool the generating command used
    # (`... | sort`, ambient locale, no LC_ALL override) -- Python's
    # `sorted()` is codepoint order and disagrees with the ambient locale's
    # collation (confirmed: this file sorts clean under the ambient locale
    # but `LC_ALL=C sort -c` reports disorder). This check therefore
    # inherits whatever locale the test process runs under, same as the
    # generating command did.
    sort_check = subprocess.run(
        ["sort", "-c", str(_NODEIDS_TXT)], check=False, capture_output=True, text=True
    )
    assert sort_check.returncode == 0, f"nodeids.txt not sorted: {sort_check.stderr}"
    assert len(lines) >= _FLOOR
    non_test_lines = [line for line in lines if "::" not in line]
    assert non_test_lines == [], f"node-id line(s) without '::': {non_test_lines}"


def test_t_v1111_pin_02_no_v1110_test_renamed_or_listed():
    inventory = importlib.import_module("tests.test_v1110_inventory")
    spec_test_functions = inventory._SPEC_TEST_FUNCTIONS

    assert len(spec_test_functions) == 61

    for module_name, function_name in spec_test_functions:
        module = importlib.import_module(module_name)
        assert hasattr(module, function_name), f"missing spec test: {module_name}::{function_name}"
        assert "test_v1111_" not in module_name

    diff = subprocess.run(
        ["git", "diff", "v1.11.0", "--", "tests/test_v1110_inventory.py"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert diff.stdout == ""
