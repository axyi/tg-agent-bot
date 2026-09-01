"""The mutation gate's own safety tests (REQ-V12-MUT-03).

Every test here injects a fake runner and operates on a throwaway file tree
under `tmp_path` — never the real suite, never the real repository.
"""

import pytest

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

    code = mc.run_all([killed], runner=lambda: 1, root=tmp_path)
    assert code == 0
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"

    code = mc.run_all([survived], runner=lambda: 0, root=tmp_path)
    assert code == 1
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"


def test_t_v12_mut_01_errored_verdict_is_not_killed(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    mutation = _mutation("m-errored", target, "original")

    for code in (2, 3, 4, 5):
        outcome = mc.run_all([mutation], runner=lambda code=code: code, root=tmp_path)
        assert outcome == 1, f"exit code {code} must not be treated as a clean gate"
    assert target.read_text(encoding="utf-8") == "value = 'original'\n"


def test_t_v12_mut_02_drift_zero_or_two_occurrences_fails(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\nvalue = 'original'\n")
    twice = _mutation("m-drift-twice", target, "value = 'original'")
    zero = _mutation("m-drift-zero", target, "not present anywhere")

    before = target.read_text(encoding="utf-8")
    assert mc.run_all([twice], runner=lambda: 1, root=tmp_path) == 1
    assert target.read_text(encoding="utf-8") == before

    assert mc.run_all([zero], runner=lambda: 1, root=tmp_path) == 1
    assert target.read_text(encoding="utf-8") == before


def test_t_v12_mut_03_files_restored_after_a_normal_run(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-normal", target, "original")

    mc.run_all([mutation], runner=lambda: 1, root=tmp_path)

    assert target.read_bytes() == before


def test_t_v12_mut_03_files_restored_after_the_runner_raises(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-raises", target, "original")

    def exploding_runner():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        mc.run_all([mutation], runner=exploding_runner, root=tmp_path)

    assert target.read_bytes() == before


def test_t_v12_mut_03_files_restored_after_a_killed_verdict(tmp_path):
    target = _write(tmp_path / "target.py", "value = 'original'\n")
    before = target.read_bytes()
    mutation = _mutation("m-killed-restore", target, "original")

    mc.run_all([mutation], runner=lambda: 1, root=tmp_path)

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

    def runner():
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
