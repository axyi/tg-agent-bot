"""spec-v1.10.2 T3 (docs/spec/spec-v1.10.2.md Sec.9 REQ-V1102-GATE-03,
Sec.10 REQ-V1102-RPT-01 first sentence): `lint-docs.report_path` repointed
to this release's report, and the gate-matrix test in
`tests/test_v15_standards.py` repointed at `docs/spec/spec-v1.10.2.md`'s
own §9 table (which already carries the `mutation_check.py --select
v1102-` row verbatim, per the task brief).

Offline: `devtools.checks.load_gate_config()` reads the committed yaml off
disk, no network, no live LLM.

T5 (docs/spec/task-briefs/v1102-T5.md, REQ-V1102-GATE-02) adds
`T-V1102-GATE-01`/`T-V1102-GATE-02`: the six `v1102-*` mutation table
entries and the `mutation-v1102`/`mutation-subsets`/`mutation-all`
registration below, mirroring `tests/test_v1101_gates.py`'s own
`T-V1101-GATE-01`/`-02` shape.
"""

from __future__ import annotations

import re
from pathlib import Path

import devtools.mutation_check as mc
from devtools import checks
from tests.test_v15_standards import _GATE_MATRIX_LABEL_TO_NAME, _parse_gate_matrix

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_V1102 = _REPO_ROOT / "docs" / "spec" / "spec-v1.10.2.md"
_EXPECTED_MUTATION_KEYS = {"id", "path", "find", "replace", "why"}
_V1102_IDS = [
    "v1102-secrets-line-dropped",
    "v1102-first-clause-only",
    "v1102-tool-log-not-filled",
    "v1102-tool-log-unredacted",
    "v1102-inj-gap-marker-dropped",
    "v1102-hal-gap-marker-dropped",
]


def _v1102_mutations() -> list[dict]:
    return [m for m in mc.MUTATIONS if m["id"].startswith("v1102-")]


def test_t_v1102_rpt_01_lint_docs_repointed_to_this_release():
    # v1.11.0 T6 (REQ-V1110-VER-03): repointed again, disclosed amendment
    # (not in T0's pin inventory) -- function name kept stable, matching
    # every other "report_path tracks the current release" site. Repointed
    # again at spec-v1.11.1 T6 (REQ-V1111-VER-01, found by tree-wide
    # extension, not in this task's own brief's starting list): 1.11.0 ->
    # 1.11.1.
    config = checks.load_gate_config()
    assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.11.1.md"


def test_t_v1102_gate_03_gate_matrix_label_dict_matches_spec_v1102_table():
    # Light duplicate of test_v15_standards.py's own
    # test_v15_gate_04_profile_matrix_agrees_with_the_spec_table (already
    # repointed at spec-v1.10.2.md there) -- this asserts the same
    # precondition directly against the new label, per the task brief.
    #
    # v1.10.3 T4 repair cycle 3/3 (ERR-01 row 9, RPT-01 item 18): the
    # original body looped over every key in the live, ever-growing
    # _GATE_MATRIX_LABEL_TO_NAME dict and demanded each be present in the
    # frozen spec-v1.10.2.md table -- true only by accident, since no
    # later release had yet added its own label when this test was
    # written. The first time one does (v1.10.3's "mutation_check.py
    # --select v1103-"), the loop fails deterministically against a
    # spec file that can never contain a label from a release that did
    # not exist yet -- spec-v1.10.2.md:125 lists this test as "verified
    # unaffected", an assertion this run disproves. Narrowed to what the
    # test's own docstring always said its intent was: prove the v1102
    # label specifically is in both the dict and the v1.10.2 table --
    # never every label a future release might add. spec-v1.10.2.md
    # itself is not edited (history, matching NG-11's spirit even though
    # its literal list names only the report/handoff files).
    assert "`mutation_check.py --select v1102-`" in _GATE_MATRIX_LABEL_TO_NAME
    assert _GATE_MATRIX_LABEL_TO_NAME["`mutation_check.py --select v1102-`"] == "mutation-v1102"

    spec_text = _SPEC_V1102.read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    assert "`mutation_check.py --select v1102-`" in matrix, (
        "spec-v1.10.2.md table row not found: '`mutation_check.py --select v1102-`'"
    )


def test_t_v1102_gate_01_six_v1102_mutations_follow_the_last_v1101_entry():
    # T-V1102-GATE-01: exactly six v1102-* entries, in GATE-02's order, form
    # a contiguous block immediately after the last v1101-* entry -- never a
    # "nothing follows" pin (v1.10.4 T1, EC-02 row 1, REQ-V1104-PIN-01).
    ids = [m["id"] for m in mc.MUTATIONS]
    last_v1101_index = max(i for i, mid in enumerate(ids) if mid.startswith("v1101-"))
    start = last_v1101_index + 1
    assert ids[start : start + len(_V1102_IDS)] == _V1102_IDS
    assert _v1102_mutations() == [m for m in mc.MUTATIONS if m["id"] in _V1102_IDS]


def test_t_v1102_gate_01_mutations_have_five_keys_and_unique_find_strings():
    # T-V1102-GATE-01: the five keys present on each entry, and each
    # `find` string found exactly once in its named file -- the offline
    # uniqueness proof in place of the live mutation gate.
    for mutation in _v1102_mutations():
        assert set(mutation) == _EXPECTED_MUTATION_KEYS
        path = _REPO_ROOT / mutation["path"]
        assert path.exists(), mutation["id"]
        text = path.read_text(encoding="utf-8")
        assert text.count(mutation["find"]) == 1, mutation["id"]


def test_t_v1102_gate_02_mutation_v1102_registered_with_the_v1101_shape():
    config = checks.load_gate_config()
    gate = config["gates"]["mutation-v1102"]
    assert gate["kind"] == "command"
    assert gate["result_mode"] == "exit_status"
    assert gate["success_exit_codes"] == [0]
    assert gate["blocking"] is True
    assert gate["diff_scoped"] is False
    assert gate["timeout_seconds"] > 0
    assert gate["argv"] == [
        "uv",
        "run",
        "--locked",
        "python",
        "devtools/mutation_check.py",
        "--select",
        "v1102-",
    ]


def test_t_v1102_gate_02_is_in_mutation_subsets_and_no_hook_profile():
    config = checks.load_gate_config()
    assert "mutation-v1102" in config["profiles"]["mutation-subsets"]
    for profile_name, members in config["profiles"].items():
        if profile_name != "mutation-subsets":
            assert "mutation-v1102" not in members


def _mutation_all_comment_block(text: str) -> str:
    # v1.10.4 T1 (REQ-V1104-PIN-01): the block runs from `mutation-all`'s
    # first comment line to the `mutation-all:` key itself, so an "is now"
    # in another gate's own comment can never break the count below.
    # Module-level, imported by tests/test_v1104_gates.py -- not redefined.
    return text[text.index("  # mutation-all:") : text.index("\n  mutation-all:\n")]


def test_t_v1102_gate_02_mutation_all_comment_count_matches_len_mutations():
    # Redundant, offline-only re-check of tests/test_v1101_gates.py's
    # re-anchored test_v1101_gate02_mutation_all_comment_count_matches_
    # len_mutations (same underlying comment, same assertion) -- also
    # confirms exactly one "is now" sentence remains in the mutation-all
    # comment block (v1.10.4 T1, EC-02 row 4, REQ-V1104-PIN-01: narrowed
    # from the whole file to the block, so an "is now" in another gate's
    # comment cannot trip this).
    text = checks.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    assert _mutation_all_comment_block(text).count("is now") == 1
    match = re.search(
        r"MUTATIONS\)`\s*is now (\d+)",
        text,
        re.DOTALL,
    )
    assert match, "mutation-all's dated comment paragraph not found"
    assert int(match.group(1)) == len(mc.MUTATIONS)
