"""spec-v1.11.0 T7 Phase A (docs/spec/spec-v1.11.0.md REQ-V1110-MUT-01,
docs/spec/task-briefs/v1110-T7.md): proves the shape of the eight
`v1110-*` entries appended to `devtools/mutation_check.py`'s `MUTATIONS`
list -- presence, order, `find`-uniqueness against the committed `HEAD`
blob (never the possibly-dirty working tree), each `why`'s named killer
test id(s) resolving to a real, importable test function, the new total
of 152, and NG-12 (no `mutation-v1110` gate in
`config/quality_gates.yaml`).

This test does not itself run `--only`/`--select` -- those runs are
blocked in Phase A by the pre-existing v1.9.3 dirty-tree guard
(`devtools/mutation_check.py:2229`, `_dirty_mutation_paths`): that guard
refuses to start any run while `devtools/mutation_check.py` (itself the
`path` of seven pre-existing entries) differs from the committed `HEAD`
blob, which it necessarily does while these eight entries sit
uncommitted. See the T7 Phase A handback for the ordering conflict this
creates against the "do not commit in Phase A" instruction.

Offline: no network, no live LLM, no Docker -- reads only the repository's
own committed files (via `git show HEAD:<path>`) and the working tree's
`devtools/mutation_check.py`/`config/quality_gates.yaml`.

`T-V1110-MUT-01`.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import devtools.mutation_check as mc

REPO_ROOT = Path(__file__).resolve().parent.parent

# The eight ids in the exact append order the brief specifies.
_V1110_IDS = [
    "v1110-callback-allowlist-dropped",
    "v1110-activate-ownership-dropped",
    "v1110-table-path-escape-dropped",
    "v1110-agent-reply-gains-parse-mode",
    "v1110-inflight-guard-dropped",
    "v1110-cancel-flag-ignored",
    "v1110-model-index-unbounded",
    "v1110-document-cap-tenfold",
]

# Spec table's killer test id(s) per entry (docs/spec/spec-v1.11.0.md's
# REQ-V1110-MUT-01 table); entry 7 has two, matching the spec's own
# "killed by both" wording.
_EXPECTED_KILLERS = {
    "v1110-callback-allowlist-dropped": ["T-V1110-CBQ-02"],
    "v1110-activate-ownership-dropped": ["T-V1110-SES-02"],
    "v1110-table-path-escape-dropped": ["T-V1110-OUT-02"],
    "v1110-agent-reply-gains-parse-mode": ["T-V1110-OUT-06"],
    "v1110-inflight-guard-dropped": ["T-V1110-ING-03"],
    "v1110-cancel-flag-ignored": ["T-V1110-ING-05"],
    "v1110-model-index-unbounded": ["T-V1110-CBQ-05", "T-V1110-MOD-08"],
    "v1110-document-cap-tenfold": ["T-V1110-ING-01"],
}

# Killer test id -> (dotted test module, function name), resolved by grep
# against the landed tests/test_v1110_*.py files (not a guess -- each was
# located with `grep -n "def test_t_v1110_..." tests/test_v1110_*.py`
# during this task).
_KILLER_FUNCTIONS = {
    "T-V1110-CBQ-02": ("tests.test_v1110_cbq", "test_t_v1110_cbq_02_intruder_callback_one_ack"),
    "T-V1110-SES-02": (
        "tests.test_v1110_ses",
        "test_t_v1110_ses_02_activate_conversation_ownership",
    ),
    "T-V1110-OUT-02": ("tests.test_v1110_out", "test_t_v1110_out_02_send_pre_payload_and_escape"),
    "T-V1110-OUT-06": (
        "tests.test_v1110_out",
        "test_t_v1110_out_06_agent_reply_path_unchanged",
    ),
    "T-V1110-ING-03": ("tests.test_v1110_ing", "test_t_v1110_ing_03_second_upload_refused"),
    "T-V1110-ING-05": ("tests.test_v1110_ing", "test_t_v1110_ing_05_cancel_mid_embedding"),
    "T-V1110-CBQ-05": ("tests.test_v1110_cbq", "test_t_v1110_cbq_05_stale_and_malformed_data"),
    "T-V1110-MOD-08": ("tests.test_v1110_mod", "test_t_v1110_mod_08_reordered_catalogue_is_stale"),
    "T-V1110-ING-01": ("tests.test_v1110_ing", "test_t_v1110_ing_01_caps_and_find_line"),
}


def _head_blob(rel_path: str) -> str:
    """The committed `HEAD` content of `rel_path`, read via `git show` --
    the same git-objects-only source of truth `_dirty_mutation_paths` and
    `checks.py`'s own `replay` command use, never the working tree (which
    may be mid-mutation or hold an unrelated edit)."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


def test_t_v1110_mut_01_eight_entries_in_mutations():
    ids = [m["id"] for m in mc.MUTATIONS]

    # Presence and order: the eight v1110-* ids appear, in exactly the
    # brief's append order, as a contiguous run (nothing interleaved --
    # they were appended as one block).
    v1110_positions = [i for i, mid in enumerate(ids) if mid in _V1110_IDS]
    assert [ids[i] for i in v1110_positions] == _V1110_IDS
    assert v1110_positions == list(range(v1110_positions[0], v1110_positions[0] + 8))

    by_id = {m["id"]: m for m in mc.MUTATIONS}

    for mutation_id in _V1110_IDS:
        entry = by_id[mutation_id]
        assert set(entry) == {"id", "path", "find", "replace", "why"}

        # Each find occurs exactly once in its path at the committed HEAD
        # blob -- not the possibly-dirty working tree.
        head_text = _head_blob(entry["path"])
        assert head_text.count(entry["find"]) == 1, (
            f"{mutation_id}: find does not occur exactly once in HEAD:{entry['path']}"
        )

        # Each why names its killing T-V1110-* test id(s), and each of
        # those ids resolves to a real, importable test function.
        for killer_id in _EXPECTED_KILLERS[mutation_id]:
            assert killer_id in entry["why"], f"{mutation_id}: why does not name killer {killer_id}"
            module_name, func_name = _KILLER_FUNCTIONS[killer_id]
            module = importlib.import_module(module_name)
            func = getattr(module, func_name, None)
            assert callable(func), (
                f"{killer_id}: {module_name}.{func_name} does not exist or is not callable"
            )

    # entry 8's own disambiguation requirement: the pre-existing v190
    # find line must stay untouched and still occur exactly once in
    # bot.py's HEAD blob after this entry.
    v190_entry = by_id["v190-size-precheck-disabled"]
    assert v190_entry["path"] == "bot.py"
    bot_head = _head_blob("bot.py")
    assert bot_head.count(v190_entry["find"]) == 1

    # mutation-all's new wall: 144 (spec-v1.10.4 T5) + 8 = 152.
    assert len(mc.MUTATIONS) == 152

    # NG-12: T7 does not add a mutation-v1110 subset gate (unlike the
    # earlier mutation-v1100/-v1101/-v1102/-v1103 subset gates) -- the
    # spec's own REQ-V1110-MUT-01 names only mutation-all as the wall.
    gates_text = (REPO_ROOT / "config" / "quality_gates.yaml").read_text(encoding="utf-8")
    assert "mutation-v1110" not in gates_text
