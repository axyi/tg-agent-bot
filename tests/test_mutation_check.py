"""The mutation gate's own safety tests (REQ-V12-MUT-03).

Every test here injects a fake runner and operates on a throwaway file tree
under `tmp_path` — never the real suite, never the real repository.
"""

import subprocess

import pytest

from devtools import checks
from devtools import mutation_check as mc


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def _mutation(id_, path, find, replace="mutated"):
    return {"id": id_, "path": str(path.name), "find": find, "replace": replace, "why": "test"}


def test_t_v12_mut_01_killed_and_survived_verdicts(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    killed = _mutation("m-killed", target, "original")
    survived = _mutation("m-survived", target, "original")

    code = mc.run_all([killed], runner=lambda _m: 1, root=tmp_path)
    assert code == 0
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"

    code = mc.run_all([survived], runner=lambda _m: 0, root=tmp_path)
    assert code == 1
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"


def test_t_v12_mut_01_errored_verdict_is_not_killed(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    mutation = _mutation("m-errored", target, "original")

    for code in (2, 3, 4, 5):
        outcome = mc.run_all([mutation], runner=lambda _m, code=code: code, root=tmp_path)
        assert outcome == 1, f"exit code {code} must not be treated as a clean gate"
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"


def test_t_v12_mut_02_drift_zero_or_two_occurrences_fails(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\nvalue = 'original'\n")
    twice = _mutation("m-drift-twice", target, "value = 'original'")
    zero = _mutation("m-drift-zero", target, "not present anywhere")

    before = target.read_text(encoding="utf-8")
    assert mc.run_all([twice], runner=lambda _m: 1, root=tmp_path) == 1
    assert target.read_text(encoding="utf-8") == before

    assert mc.run_all([zero], runner=lambda _m: 1, root=tmp_path) == 1
    assert target.read_text(encoding="utf-8") == before


def test_t_v12_mut_03_files_restored_after_a_normal_run(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-normal", target, "original")

    mc.run_all([mutation], runner=lambda _m: 1, root=tmp_path)

    assert target.read_bytes() == before


def test_t_v12_mut_03_files_restored_after_the_runner_raises(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-raises", target, "original")

    def exploding_runner(_m):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        mc.run_all([mutation], runner=exploding_runner, root=tmp_path)

    assert target.read_bytes() == before


def test_t_v12_mut_03_files_restored_after_a_killed_verdict(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-killed-restore", target, "original")

    mc.run_all([mutation], runner=lambda _m: 1, root=tmp_path)

    assert target.read_bytes() == before


def test_t_v12_mut_03_list_runs_nothing(tmp_path, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(mc, "run_all", lambda *a, **k: calls.append((a, k)) or 0)

    assert mc.main(["--list"]) == 0
    assert calls == []
    out = capsys.readouterr().out
    for mutation in mc.MUTATIONS:
        assert mutation["id"] in out


def test_t_v12_mut_04_only_selects_a_single_entry(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    seen = []
    mutations = [
        _mutation("first", target, "original", replace="first-mutated"),
    ]
    # A second mutation with a distinct id but the same file; --only must run
    # exactly one of them.
    other = _write(tmp_path / "other.py", "value = 'other'\n")
    mutations.append(_mutation("second", other, "other", replace="second-mutated"))

    def runner(_m):
        seen.append(target.read_text(encoding="utf-8"))
        return 1

    code = mc.run_all(mutations, runner=runner, only="first", root=tmp_path)
    assert code == 0
    assert seen == ["value = 'first-mutated'\n"]
    assert target.read_bytes() == b"value = 'original'\n"
    assert other.read_bytes() == b"value = 'other'\n"


def test_t_v12_mut_04_at_least_28_entries_each_with_a_unique_id():
    assert len(mc.MUTATIONS) >= 28
    ids = [m["id"] for m in mc.MUTATIONS]
    assert len(ids) == len(set(ids))


def test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo():
    for mutation in mc.MUTATIONS:
        text = (mc.REPO_ROOT / mutation["path"]).read_text(encoding="utf-8")
        assert text.count(mutation["find"]) == 1, mutation["id"]


# ---------------------------------------------------------------------------
# spec-v1.6.0 section 15.4 (REQ-V160-TST-03, -04, REQ-V160-GATE-02, -03):
# the ten table-named v160-* entries and the mutation-v160 gate that runs
# them, plus one eleventh entry T14 landed: `v160-content-redact-bypassed`
# is the table's own §15.4 row, unkillable at T13 (no test reached
# set_content_attribute's redact call with genuinely fresh content) and
# closed at T14 by a test that does
# (tests/test_v160_observability.py
# ::test_t_v160_trc_10_content_capture_on_redacts_a_fresh_never_stored_secret).
# `v160-status-message-redact-bypassed`, T13's stand-in proving a distinct
# mechanism (span error messages), stays -- neither removed nor renamed, per
# spec-v1.6.0 T14's own instruction not to erase a finding that honestly
# proves something else.
#
# `test_t_v12_mut_04_at_least_28_entries_each_with_a_unique_id` and
# `test_t_v12_mut_04_every_find_string_occurs_exactly_once_in_the_real_repo`
# above already cover every entry in MUTATIONS, new ones included -- no need
# to repeat the unique-match check here.
# ---------------------------------------------------------------------------

_V160_MUTATION_IDS = [
    "v160-bind-address-widened",
    "v160-capture-content-default-on",
    "v160-content-redact-bypassed",
    "v160-status-message-redact-bypassed",
    "v160-fingerprint-threshold-off-by-one",
    "v160-truncated-summary-accepted",
    "v160-selftest-starts-the-server",
    "v160-version-literal-not-pyproject",
    "v160-readonly-connection-writable",
    "v160-error-echoes-request-input",
    "v160-host-check-disabled",
]


def test_t_v160_tst_03_all_eleven_entries_are_present():
    ids = {m["id"] for m in mc.MUTATIONS}
    for expected_id in _V160_MUTATION_IDS:
        assert expected_id in ids, expected_id


def test_t_v160_tst_03_select_v160_matches_exactly_the_eleven_entries():
    selected = [m["id"] for m in mc.MUTATIONS if m["id"].startswith("v160-")]
    assert selected == _V160_MUTATION_IDS


def test_t_v160_gate_02_mutation_v160_gate_mirrors_mutation_v15():
    config = checks.load_gate_config()
    gates = config["gates"]
    assert "mutation-v160" in gates
    v15 = gates["mutation-v15"]
    v160 = gates["mutation-v160"]

    assert v160["kind"] == v15["kind"]
    assert v160["result_mode"] == v15["result_mode"]
    assert v160["blocking"] == v15["blocking"]
    assert v160["success_exit_codes"] == v15["success_exit_codes"]
    assert v160["diff_scoped"] == v15["diff_scoped"]
    assert v160["argv"] == [
        "uv",
        "run",
        "--locked",
        "python",
        "devtools/mutation_check.py",
        "--select",
        "v160-",
    ]
    # a spurious timeout must never block push/full for load, not correctness
    # (D2, v1.5.1) -- both gates follow the same 2x-measured rule
    assert isinstance(v160["timeout_seconds"], int) and v160["timeout_seconds"] > 0

    # v1.9.3 T1 (docs/spec/task-briefs/v193-T1.md commit A): `pre-push` now
    # runs `mutation-all` instead of the five `mutation-v*` subsets, which
    # moved to the inert `mutation-subsets` bookkeeping profile so the
    # config loader's orphan-gate check still passes -- repointed, not
    # deleted, per this task's own constraint.
    assert "mutation-v160" in config["profiles"]["mutation-subsets"]
    assert "mutation-v160" not in config["profiles"]["pre-push"]


# ---------------------------------------------------------------------------
# v1.9.2 T2 (docs/spec/task-briefs/v192-T2.md section 2): the ordered runner.
# ---------------------------------------------------------------------------


def test_t_v192_ordered_test_files_is_a_permutation_for_every_mutation():
    # Reordering is a pure performance property: every ordering must contain
    # exactly the same files as the bare glob, for every real mutation entry
    # -- never a subset (the silent-shrink hazard section 2.1 names).
    all_files = mc._all_test_files(mc.REPO_ROOT)
    for mutation in mc.MUTATIONS:
        ordered = mc.ordered_test_files(mutation, mc.REPO_ROOT)
        assert len(ordered) == len(all_files)
        assert set(ordered) == set(all_files)


def test_t_v192_ordered_test_files_tier1_is_the_version_prefixed_files_first():
    mutation = next(m for m in mc.MUTATIONS if m["id"] == "v160-bind-address-widened")
    ordered = mc.ordered_test_files(mutation, mc.REPO_ROOT)
    v160_files = {p.name for p in ordered if p.name.startswith("test_v160_")}
    assert v160_files == {
        "test_v160_bench.py",
        "test_v160_dashboard.py",
        "test_v160_observability.py",
    }
    leading = {p.name for p in ordered[: len(v160_files)]}
    assert leading == v160_files


def test_t_v192_ordered_test_files_cov_prefix_maps_to_v12_patch():
    mutation = next(m for m in mc.MUTATIONS if m["id"].startswith("cov-"))
    ordered = mc.ordered_test_files(mutation, mc.REPO_ROOT)
    assert ordered[0].name == "test_v12_patch.py"


def test_t_v192_ordered_test_files_tier2_is_the_same_named_module_file():
    # "sec-" has no tier1 test file (no test_sec_*.py), so tier 2 -- the
    # file named after the mutated module -- leads.
    mutation = next(m for m in mc.MUTATIONS if m["id"] == "sec-id-01-minted-id")
    assert mutation["path"] == "agent.py"
    ordered = mc.ordered_test_files(mutation, mc.REPO_ROOT)
    assert ordered[0].name == "test_agent.py"


def test_t_v192_mutation_order_shrink_check_blocks_before_running_anything(monkeypatch, capsys):
    # A killer test for `v192-mutation-order-shrink-unchecked`: with the real
    # (unmutated) check in place, a fabricated node-count mismatch (both
    # returncodes clean, both counts positive) must make main() fail loudly
    # and never reach run_all. If the mutation neuters the check (turns it
    # into `if False:`), main() falls through to the mocked run_all below
    # instead -- a different, wrong return code and a spurious call -- which
    # is exactly what "killed" means here. Never shells out to real pytest:
    # `_shrink_counts` and `run_all` are both faked.
    # v1.9.3 T1 commit B, fix 1 added an earlier main()-level guard (the
    # dirty-tree check) that also inspects the real repo tree; bypass it
    # here so this test still exercises only the shrink guard it names.
    monkeypatch.setattr(mc, "_dirty_mutation_paths", lambda *a, **k: [])
    monkeypatch.setattr(mc, "_shrink_counts", lambda root=mc.REPO_ROOT: (100, 99, 0, 0))
    calls = []
    monkeypatch.setattr(mc, "run_all", lambda *a, **k: calls.append((a, k)) or 0)

    code = mc.main(["--only", "v192-mutation-order-shrink-unchecked"])

    assert code == 1
    assert calls == []
    err = capsys.readouterr().err
    assert "100" in err
    assert "99" in err


def test_t_v192_mutation_order_shrink_check_rejects_zero_zero_collection(monkeypatch):
    # A killer test for `v192-mutation-order-shrink-zero-accepted` (review
    # finding 1): an empty collection (0, 0) with clean returncodes must be
    # rejected outright -- 0 == 0 would otherwise pass the equality check
    # too, so dropping only the `<= 0` guard falls all the way through to
    # run_all. Faked throughout, never shells out to real pytest.
    monkeypatch.setattr(mc, "_dirty_mutation_paths", lambda *a, **k: [])
    monkeypatch.setattr(mc, "_shrink_counts", lambda root=mc.REPO_ROOT: (0, 0, 0, 0))
    calls = []
    monkeypatch.setattr(mc, "run_all", lambda *a, **k: calls.append((a, k)) or 0)

    code = mc.main(["--only", "v192-mutation-order-shrink-zero-accepted"])

    assert code == 1
    assert calls == []


def test_t_v192_mutation_order_shrink_check_rejects_nonzero_returncode(monkeypatch, capsys):
    # Review finding 1: a collect-only failure (non-zero returncode) must
    # not be read through the counts at all -- even matching, positive
    # counts must not pass when either invocation errored.
    monkeypatch.setattr(mc, "_dirty_mutation_paths", lambda *a, **k: [])
    monkeypatch.setattr(mc, "_shrink_counts", lambda root=mc.REPO_ROOT: (1598, 1598, 2, 0))
    calls = []
    monkeypatch.setattr(mc, "run_all", lambda *a, **k: calls.append((a, k)) or 0)

    code = mc.main(["--only", "v192-mutation-order-shrink-unchecked"])

    assert code == 1
    assert calls == []
    err = capsys.readouterr().err
    assert "rc=2" in err


# ---------------------------------------------------------------------------
# v1.9.3 T1 commit B, fix 1 (docs/spec/task-briefs/v193-T1.md): refuse to
# start while a mutation path already differs from the committed HEAD blob.
# ---------------------------------------------------------------------------


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_t_v193_dirty_mutation_paths_detects_a_byte_difference_from_head(tmp_path):
    target = tmp_path / "target.py"
    target.write_text("value = 'original'\n", encoding="utf-8")
    _git(["init", "-q"], tmp_path)
    _git(["add", "target.py"], tmp_path)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"], tmp_path)

    # Clean: matches HEAD exactly.
    clean_mutation = {"id": "x", "path": "target.py", "find": "a", "replace": "b", "why": "w"}
    assert mc._dirty_mutation_paths([clean_mutation], root=tmp_path) == []

    # Plant a byte difference relative to the committed HEAD blob -- the same
    # shape a leftover mutation (or an operator's own uncommitted edit) takes.
    target.write_text("value = 'dirty'\n", encoding="utf-8")
    assert mc._dirty_mutation_paths([clean_mutation], root=tmp_path) == ["target.py"]


def test_t_v193_mutation_dirty_tree_check_blocks_before_running_anything(monkeypatch, capsys):
    # A killer test for `v193-mutation-dirty-tree-unchecked`: with the real
    # check in place, a fabricated dirty path must make main() refuse and
    # never reach run_all. If the mutation neuters the check (turns it into
    # `if False:`), main() falls through to the mocked run_all below instead
    # -- a different, wrong return code and a spurious call -- exactly what
    # "killed" means here. Never touches the real repo tree: the blob-vs-
    # working-tree comparison itself is faked, not exercised.
    monkeypatch.setattr(
        mc, "_dirty_mutation_paths", lambda mutations, root=mc.REPO_ROOT: ["devtools/checks.py"]
    )
    calls = []
    monkeypatch.setattr(mc, "run_all", lambda *a, **k: calls.append((a, k)) or 0)

    code = mc.main(["--only", "v193-mutation-dirty-tree-unchecked"])

    assert code == 1
    assert calls == []
    err = capsys.readouterr().err
    assert "devtools/checks.py" in err
