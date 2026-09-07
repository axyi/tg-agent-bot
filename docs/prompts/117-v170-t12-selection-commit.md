# Prompt 117 — spec-v1.7.0 T12: the selection commit

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T12
- **Owner of:** `config.py`, `pyproject.toml`, `.env.example`, `README.md`,
  `docs/prompts/117-v170-t12-selection-commit.md` (new)
- **REQ ids:** REQ-V170-POL-07, REQ-V170-VER-01, REQ-V170-ACC-03,
  REQ-V170-BEN-07, REQ-V170-REV-01 item 8

## Goal

Land the single post-measurement selection commit: C1
(`by-purpose`/`tool-round`, the sole quality-passing candidate per T11) as
the shipped default, `pyproject.toml` `1.6.0` -> `1.7.0`, and the two
default-value echoes in `.env.example` and `README.md` — the exhaustive
change-set REQ-V170-POL-07/ACC-03 permit, nothing else.

## Constraints

- Exhaustive five-file allowlist: `config.py`, `pyproject.toml`,
  `.env.example`, `README.md`, `AGENTS.md`. This commit touches four of the
  five — see Stop.
- `T-V170-ACC-03`'s third half asserts every changed line in `config.py`
  names one of the two variables, `pyproject.toml`'s diff touches only its
  `version` line, and the documentation files' diffs touch only lines
  naming a variable or a version string — verified empirically against the
  real validator (`_acc03_validate_selection_commit_hunks`) before
  committing, not merely reasoned about.
- Only `LLM_REASONING_POLICY`'s literal moves (`model-default` ->
  `by-purpose`, at both `config.py:151`'s dataclass default and
  `config.py:309`'s `_parse_choice` call-site default). C1's
  `LLM_REASONING_ON_PURPOSES` (`["tool-round"]`) already equals the
  existing compatibility default (`"tool-round"`) — no edit needed, and
  none made.
- No test file edited (not in the allowlist regardless of T12).

## Acceptance

- `T-V170-ACC-03`'s equivalence half passes: `load_config()`'s resolution
  matches exactly one committed `cand-v170-*.json`
  (`cand-v170-by-purpose-tool`).
- `T-V170-ACC-03`'s version half passes: `pyproject.toml` reads `1.7.0`.
- `T-V170-ACC-03`'s third half (once this commit exists): `git diff
  --name-only` from this commit's first parent lists no path outside the
  five-file allowlist and its hunks pass `_acc03_validate_selection_commit_hunks`.

## Stop

None triggered on the selection itself. Two things handled without a full
stop, both empirically verified against the real validator functions
before acting, not inferred from reading the code:

1. **`uv.lock` cannot ride in this commit.** Bumping `pyproject.toml`'s
   version requires `uv.lock` to be regenerated (`uv sync --locked`
   otherwise refuses: "the lockfile ... needs to be updated") — but
   `uv.lock` is not in the five-file allowlist, and `_acc03_validate_...`
   flags any path outside it unconditionally. Splitting the version bump
   into its own earlier commit (before this one) was considered and
   rejected: `T-V170-ACC-03`'s version half requires `pyproject.toml` and
   `config.py`'s resolved default to move together, atomically, in the
   same commit — an intermediate commit with the version bumped alone
   would read `1.7.0` while resolving to the old default, failing that
   half at that intermediate commit. Resolution: `uv.lock` lands in its
   own immediately-following `chore:` commit, referencing a **different**
   prompt file whose name does not match
   `docs/prompts/\d+-v170-t12-[\w.-]*\.md` — `_acc03_find_selection_commit`
   locates the selection commit by that regex against the commit body, and
   a second match would make it ambiguous (return `None`, a recorded skip,
   not a failure, but it would defeat the check's purpose). Verified:
   `checks.py replay` does not run `uv sync --locked` per historical
   commit at all (`_replay_one_commit` runs only ruff-on-blob, gitleaks
   and commit-msg checks) — so a `uv.lock` briefly behind `pyproject.toml`
   between these two adjacent commits is not a replay-visible regression.
2. **`AGENTS.md`'s stated default cannot be corrected in this commit
   either**, for the same structural reason as the `.env.example` wording
   defect T11 found: the phrase "default `model-default`" sits on a line
   that does not itself contain `LLM_REASONING_POLICY` (that appears one
   line above), so editing it necessarily removes a line the validator
   rejects regardless of the replacement text — confirmed by writing the
   edit and running `_acc03_validate_selection_commit_hunks` against the
   real diff before deciding, not by reasoning alone. Both this and the
   `.env.example` `LLM_REASONING_ON_PURPOSES` wording inversion land in an
   immediate follow-up `docs:` commit, again citing a non-`t12`-matching
   prompt, once this selection commit already exists (the freeze lifts
   here, and `_acc03_find_selection_commit` only ever inspects the one
   commit its regex matches).
