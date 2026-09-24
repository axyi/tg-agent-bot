"""spec-v1.10.4 T1 (docs/spec/spec-v1.10.4.md Sec.3 REQ-V1104-PIN-01,
REQ-V1104-PIN-02, Sec.6 REQ-V1104-TST-01): proves the property EC-02's
amendment table rewrites for -- every frozen-list pin now asserts
presence, contiguity and order of its own release's group, never
equality with the whole tail, and the "is now" anchor is release-agnostic
and narrowed to the `mutation-all` comment block. These tests call the
rewritten test functions directly (imported by name), with `mc.MUTATIONS`
or `checks.DEFAULT_CONFIG_PATH` monkeypatched, rather than re-deriving the
same assertions -- the point is to prove the *rewritten* tests behave
correctly under a probe/mutation, not to duplicate them.

Offline: no network, no live LLM, no Docker -- reads only the repository's
own committed files (and `tmp_path` fixtures this module writes itself).

`T-V1104-PIN-01` .. `T-V1104-PIN-08`, `T-V1104-RPT-01`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import devtools.mutation_check as mc
from devtools import checks
from tests.test_v15_standards import (
    _GATE_MATRIX_LABEL_TO_NAME,
    _parse_gate_matrix,
    test_v15_gate_04_profile_matrix_agrees_with_the_spec_table,
)
from tests.test_v1100_gates import (
    test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order,
)
from tests.test_v1101_gates import (
    test_v1101_gate02_mutation_all_comment_count_matches_len_mutations,
)
from tests.test_v1102_gates import (
    _mutation_all_comment_block,
    test_t_v1102_gate_01_six_v1102_mutations_follow_the_last_v1101_entry,
    test_t_v1102_gate_02_mutation_all_comment_count_matches_len_mutations,
)
from tests.test_v1103_gates import (
    test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_V1104 = _REPO_ROOT / "docs" / "spec" / "spec-v1.10.4.md"

_PROBE_MUTATION = {
    "id": "v9999-probe",
    "path": "tools.py",
    "find": "probe-find-unique-string",
    "replace": "probe-replace-unique-string",
    "why": "T-V1104-PIN probe entry",
}


def test_t_v1104_pin_01_appended_probe_leaves_the_two_rewritten_group_tests_green(monkeypatch):
    monkeypatch.setattr(mc, "MUTATIONS", [*list(mc.MUTATIONS), dict(_PROBE_MUTATION)])
    test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order()
    test_t_v1102_gate_01_six_v1102_mutations_follow_the_last_v1101_entry()


def test_t_v1104_pin_02_probe_inside_a_group_or_a_reordered_block_breaks_both(monkeypatch):
    original = list(mc.MUTATIONS)
    ids = [m["id"] for m in original]

    v1102_indices = [i for i, mid in enumerate(ids) if mid.startswith("v1102-")]
    mutated = list(original)
    mutated.insert(v1102_indices[3], dict(_PROBE_MUTATION))
    monkeypatch.setattr(mc, "MUTATIONS", mutated)
    with pytest.raises(AssertionError):
        test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order()
    with pytest.raises(AssertionError):
        test_t_v1102_gate_01_six_v1102_mutations_follow_the_last_v1101_entry()

    v1101_indices = [i for i, mid in enumerate(ids) if mid.startswith("v1101-")]
    reordered = list(original)
    block = [reordered[i] for i in v1101_indices]
    for idx, entry in zip(v1101_indices, reversed(block), strict=True):
        reordered[idx] = entry
    monkeypatch.setattr(mc, "MUTATIONS", reordered)
    with pytest.raises(AssertionError):
        test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order()


_PIN03_FIXTURE_TEXT = (
    "  # mutation-all: spec-v9.9.9 T9 appended one entry; "
    "`len(devtools.mutation_check.MUTATIONS)` is now 145\n"
    "  mutation-all:\n"
    "    kind: command\n"
)


def test_t_v1104_pin_03_release_agnostic_anchor_reads_any_dated_is_now_sentence(
    tmp_path, monkeypatch
):
    fixture = tmp_path / "quality_gates.yaml"
    fixture.write_text(_PIN03_FIXTURE_TEXT, encoding="utf-8")
    monkeypatch.setattr(checks, "DEFAULT_CONFIG_PATH", fixture)
    monkeypatch.setattr(mc, "MUTATIONS", [{}] * 145)
    test_v1101_gate02_mutation_all_comment_count_matches_len_mutations()
    test_t_v1102_gate_02_mutation_all_comment_count_matches_len_mutations()


def test_t_v1104_pin_04_is_now_count_narrowed_to_the_mutation_all_block(tmp_path, monkeypatch):
    outside_extra = "  mutation-v1103:\n    # note: is now a registered gate\n    kind: command\n"
    fixture_ok = tmp_path / "quality_gates_ok.yaml"
    fixture_ok.write_text(outside_extra + _PIN03_FIXTURE_TEXT, encoding="utf-8")
    monkeypatch.setattr(checks, "DEFAULT_CONFIG_PATH", fixture_ok)
    monkeypatch.setattr(mc, "MUTATIONS", [{}] * 145)
    test_t_v1102_gate_02_mutation_all_comment_count_matches_len_mutations()

    block_two_is_now = (
        "  # mutation-all: spec-v9.9.9 T9 appended one entry; "
        "`len(devtools.mutation_check.MUTATIONS)` is now 145; a second "
        "sentence, is now redundant, appears here too\n"
        "  mutation-all:\n"
        "    kind: command\n"
    )
    fixture_bad = tmp_path / "quality_gates_bad.yaml"
    fixture_bad.write_text(block_two_is_now, encoding="utf-8")
    monkeypatch.setattr(checks, "DEFAULT_CONFIG_PATH", fixture_bad)
    with pytest.raises(AssertionError):
        test_t_v1102_gate_02_mutation_all_comment_count_matches_len_mutations()

    real_text = (_REPO_ROOT / "config" / "quality_gates.yaml").read_text(encoding="utf-8")
    real_block = _mutation_all_comment_block(real_text)
    assert real_block.startswith("  # mutation-all:")
    assert real_text.index("\n  mutation-all:\n") == real_text.index(real_block) + len(real_block)


def test_t_v1104_pin_05_gate_matrix_parses_29_rows_containing_every_label():
    spec_text = _SPEC_V1104.read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    assert len(matrix) == 29
    for label in _GATE_MATRIX_LABEL_TO_NAME:
        assert label in matrix, f"spec-v1.10.4.md table row not found: {label!r}"

    test_v15_gate_04_profile_matrix_agrees_with_the_spec_table()
    test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table()


def test_t_v1104_pin_07_lint_report_delegation_prefix_is_v1104(tmp_path):
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    good = good_dir / "report-v1.10.4.md"
    good.write_text(
        "## T1\n\n"
        "- T1 | delegated: yes | to: probe | brief: "
        "docs/spec/task-briefs/v1104-T1.md | map vs actual: matches\n",
        encoding="utf-8",
    )
    assert checks._lint_report_delegation(good) == []

    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    bad = bad_dir / "report-v1.10.4.md"
    bad.write_text(
        "## T1\n\n"
        "- T1 | delegated: yes | to: probe | brief: "
        "docs/spec/task-briefs/v1103-T1.md | map vs actual: matches\n",
        encoding="utf-8",
    )
    problems = checks._lint_report_delegation(bad)
    assert problems == [
        "report-v1.10.4.md: T1: cell 4 is neither brief: — nor a v1104 task-brief path"
    ]


def test_t_v1104_pin_08_future_label_passes_dropped_or_swapped_v1103_label_fails(monkeypatch):
    import tests.test_v1103_gates as t1103

    original = dict(t1103._GATE_MATRIX_LABEL_TO_NAME)
    labels = list(original.items())
    all_index = next(
        i for i, (label, _name) in enumerate(labels) if label == "`mutation_check.py` (all)"
    )
    future = ("`mutation_check.py --select v9999-`", "mutation-v9999")
    with_future = dict([*labels[:all_index], future, *labels[all_index:]])
    monkeypatch.setattr(t1103, "_GATE_MATRIX_LABEL_TO_NAME", with_future)
    t1103.test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table()

    dropped = dict(labels)
    del dropped["`mutation_check.py --select v1103-`"]
    monkeypatch.setattr(t1103, "_GATE_MATRIX_LABEL_TO_NAME", dropped)
    with pytest.raises(AssertionError):
        t1103.test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table()

    swapped_items = list(labels)
    v1102_label = "`mutation_check.py --select v1102-`"
    v1103_label = "`mutation_check.py --select v1103-`"
    v1102_pos = next(i for i, (label, _name) in enumerate(swapped_items) if label == v1102_label)
    v1103_pos = next(i for i, (label, _name) in enumerate(swapped_items) if label == v1103_label)
    swapped_items[v1102_pos], swapped_items[v1103_pos] = (
        swapped_items[v1103_pos],
        swapped_items[v1102_pos],
    )
    monkeypatch.setattr(t1103, "_GATE_MATRIX_LABEL_TO_NAME", dict(swapped_items))
    with pytest.raises(AssertionError):
        t1103.test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table()


def test_t_v1110_rpt_01_lint_docs_config_and_own_report_are_green():
    # v1.11.0 T6 (REQ-V1110-VER-03): renamed from
    # test_t_v1104_rpt_01_lint_docs_config_and_own_report_are_green -- see
    # the rename mapping in docs/spec/task-briefs/v1110-T0-pin-inventory.md.
    # Repointed again at spec-v1.11.1 T6 (REQ-V1111-VER-01): 1.11.0 -> 1.11.1,
    # both occurrences.
    config = checks.load_gate_config()
    lint_docs = config["gates"]["lint-docs"]
    assert lint_docs["report_path"] == "docs/reports/report-v1.11.1.md"
    assert lint_docs["delegation_record"] is True

    report = _REPO_ROOT / "docs" / "reports" / "report-v1.11.1.md"
    assert checks._lint_report_delegation(report) == []


# ---------------------------------------------------------------------------
# v1.10.4 T2 (docs/spec/task-briefs/v1104-T2.md, REQ-V1104-MUT-01,
# REQ-V1104-MUT-02): the five `v1103-*` entries, pinned verbatim from
# spec-v1.10.4.md Sec.3 (lines 277-293) -- byte-exact, not re-derived, not
# read back from `mc.MUTATIONS` (that lookup is what the tests below
# exercise). `_V1103_ENTRIES` carries only the four keys these tests pin;
# `why` is the stash's own prose and is not re-asserted verbatim here.
# ---------------------------------------------------------------------------

_EXPECTED_MUTATION_KEYS_V1103 = {"id", "path", "find", "replace", "why"}

_V1103_ENTRIES = [
    {
        "id": "v1103-exec-guard-dropped",
        "path": "tools.py",
        "find": ("    if os.path.basename(argv[0]) in EXEC_DENY_PROGRAMS:  # noqa: PTH119\n"),
        "replace": "    if False:  # v1103-exec-guard-dropped  # noqa: PTH119\n",
    },
    {
        "id": "v1103-exec-guard-env-file-dropped",
        "path": "tools.py",
        "find": (
            '        os.path.basename(e) == ".env" or os.path.basename(e).startswith('
            '".env.")  # noqa: PTH119\n'
        ),
        "replace": "        False  # v1103-exec-guard-env-file-dropped\n",
    },
    {
        "id": "v1103-exec-guard-proc-environ-dropped",
        "path": "tools.py",
        "find": "    if any(_PROCFS_ENVIRON_RE.fullmatch(e) for e in argv):\n",
        "replace": "    if False:  # v1103-exec-guard-proc-environ-dropped\n",
    },
    {
        "id": "v1103-delegation-lint-dropped",
        "path": "devtools/checks.py",
        "find": '    if gate.get("delegation_record") is True:\n',
        "replace": "    if False:  # v1103-delegation-lint-dropped\n",
    },
    {
        "id": "v1103-hal-noun-first-marker-dropped",
        "path": "devtools/agent_eval.py",
        "find": (
            '    r"(?:информации|данных|сведений)\\b(?:(?!\\b(?:но|а|однако|зато)\\b)'
            '[^.?!;…]){0,120}\\bнет\\b",\n'
        ),
        "replace": "",
    },
]


def test_t_v1104_mut_01_five_v1103_entries_form_one_contiguous_block_in_order():
    # T-V1104-MUT-01: pre-apply this is red -- `ids[anchor:anchor+5]` is
    # `[]` (139 entries total, nothing after the v1102 tail) != the five
    # expected ids.
    ids = [m["id"] for m in mc.MUTATIONS]
    anchor = ids.index("v1102-hal-gap-marker-dropped") + 1
    expected_ids = [entry["id"] for entry in _V1103_ENTRIES]
    assert ids[anchor : anchor + len(expected_ids)] == expected_ids

    by_id = {m["id"]: m for m in mc.MUTATIONS}
    for entry in _V1103_ENTRIES:
        assert set(by_id[entry["id"]]) == _EXPECTED_MUTATION_KEYS_V1103

    # NG-10: never `==` here -- a frozen `== 144` is exactly the "ends
    # here" defect class this release retires.
    assert len(mc.MUTATIONS) >= 144


def test_t_v1104_mut_02_finds_match_once_and_registry_is_byte_exact():
    # T-V1104-MUT-02: pre-apply this is red -- `by_id[entry["id"]]` raises
    # KeyError, since none of the five ids are registered yet.
    by_id = {m["id"]: m for m in mc.MUTATIONS}
    for entry in _V1103_ENTRIES:
        path = _REPO_ROOT / entry["path"]
        text = path.read_text(encoding="utf-8")
        assert text.count(entry["find"]) == 1

        registered = by_id[entry["id"]]
        assert registered["find"] == entry["find"]
        assert registered["replace"] == entry["replace"]

    # Negative: a `find` with one character changed counts 0 (the pre-image
    # is byte-pinned, so a one-byte drift must not silently still match).
    first = _V1103_ENTRIES[0]
    drifted_find = first["find"][:-2] + "Z\n"
    assert drifted_find != first["find"]
    drifted_text = (_REPO_ROOT / first["path"]).read_text(encoding="utf-8")
    assert drifted_text.count(drifted_find) == 0


def test_t_v1104_mut_03_mutation_v1103_gate_shape_and_subset_membership():
    # T-V1104-MUT-03: pre-apply this is red -- `gates["mutation-v1103"]`
    # raises KeyError, the gate does not exist yet.
    config = checks.load_gate_config()
    gates = config["gates"]
    v1103_gate = gates["mutation-v1103"]
    v1102_gate = gates["mutation-v1102"]

    assert set(v1103_gate) == set(v1102_gate)
    assert v1103_gate["argv"] == [
        "uv",
        "run",
        "--locked",
        "python",
        "devtools/mutation_check.py",
        "--select",
        "v1103-",
    ]
    assert v1103_gate["blocking"] is True
    assert v1103_gate["diff_scoped"] is False

    subsets = config["profiles"]["mutation-subsets"]
    assert subsets.index("mutation-v1103") == subsets.index("mutation-v1102") + 1
    for profile_name, members in config["profiles"].items():
        if profile_name != "mutation-subsets":
            assert "mutation-v1103" not in members

    assert gates["mutation-all"]["argv"] == [
        "uv",
        "run",
        "--locked",
        "python",
        "devtools/mutation_check.py",
    ]


def test_t_v1104_mut_04_mutation_all_comment_block_has_exactly_one_is_now():
    # T-V1104-MUT-04: green structurally already, pre- and post-apply --
    # the block holds exactly one "is now" sentence (139 pre-apply, 144
    # post-apply) and it always parses to `len(mc.MUTATIONS)`.
    text = checks.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    block = _mutation_all_comment_block(text)
    assert block.count("is now") == 1
    match = re.search(r"MUTATIONS\)`\s*is now (\d+)", block, re.DOTALL)
    assert match, "mutation-all's dated comment paragraph not found in the block"
    assert int(match.group(1)) == len(mc.MUTATIONS)


def test_t_v1104_mut_05_five_mutants_parse_and_row_five_hal_markers_has_17():
    # T-V1104-MUT-05: green structurally already, pre- and post-apply --
    # this reads only the pinned `find`/`replace` pairs against the live
    # `f3ce1a5`-equivalent sources, never the registry.
    for entry in _V1103_ENTRIES:
        source = (_REPO_ROOT / entry["path"]).read_text(encoding="utf-8")
        mutated = source.replace(entry["find"], entry["replace"], 1)
        ast.parse(mutated)

    hal_entry = _V1103_ENTRIES[4]
    source = (_REPO_ROOT / hal_entry["path"]).read_text(encoding="utf-8")
    mutated = source.replace(hal_entry["find"], hal_entry["replace"], 1)
    tree = ast.parse(mutated)

    def _targets_hal_markers(node: ast.AST) -> bool:
        return isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HAL_MARKERS" for target in node.targets
        )

    hal_markers_assign = next(node for node in ast.walk(tree) if _targets_hal_markers(node))
    assert len(hal_markers_assign.value.elts) == 17


def test_t_v1104_err_01_run_one_drifted_on_double_match_else_killed_and_restored(tmp_path):
    # T-V1104-ERR-01: green structurally already -- exercises `run_one`
    # directly, never depends on the five entries being registered.
    entry = dict(_V1103_ENTRIES[0])
    target = tmp_path / entry["path"]
    target.parent.mkdir(parents=True, exist_ok=True)

    calls = []

    def spy(mutation):
        calls.append(mutation)
        return 1

    doubled = entry["find"] * 2
    target.write_text(doubled, encoding="utf-8")
    outcome, exit_code = mc.run_one(entry, runner=spy, root=tmp_path, restorer=mc._Restorer())
    assert (outcome, exit_code) == (mc.DRIFTED, None)
    assert calls == []
    assert target.read_text(encoding="utf-8") == doubled

    single = entry["find"]
    target.write_text(single, encoding="utf-8")
    outcome2, exit_code2 = mc.run_one(entry, runner=spy, root=tmp_path, restorer=mc._Restorer())
    assert outcome2 == mc.KILLED
    assert exit_code2 == 1
    assert len(calls) == 1
    assert target.read_text(encoding="utf-8") == single
