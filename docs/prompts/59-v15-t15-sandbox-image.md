# Prompt 59 — spec-v1.5 T15: sandbox image digest pin, byte smoke

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-IMG-01..05 fully specify the digest,
  the exact one test-file line to change, and the byte-comparison
  protocol; the judgment calls were empirical — pulling the incoming
  image, driving real `exec` calls through the tool layer for both
  images, and honestly reporting whichever the byte comparison showed
- **Harness:** Claude Code
- **Stage:** T15
- **Owner of:** `config.py` (`DEFAULT_DOCKER_IMAGE`), `.env.example`
  (`EXEC_DOCKER_IMAGE`), `tests/test_v1_guardrails.py:371`,
  `README.md` (`docker pull` line), `docs/reports/report-v1.5.md`
  (T15 section, RLM row), `docs/prompts/59-v15-t15-sandbox-image.md`
  (new)
- **REQ ids:** REQ-V15-IMG-01, REQ-V15-IMG-02, REQ-V15-IMG-03,
  REQ-V15-IMG-04, REQ-V15-IMG-05

## Goal

Pin the sandbox image by digest to
`python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`
across `config.py`, `.env.example`, `README.md` and the one test that
asserts the default, and prove via a byte-compared exec smoke test
whether the bump is benchmark-affecting.

## Constraints

- `config._parse_docker_image` must not change — a stricter validator
  is a forbidden behaviour change (REQ-V15-NG-07).
- Only `tests/test_v1_guardrails.py:371` (the one assertion of the
  *default*) changes; the other 48 occurrences of the old image string
  across five test files (fixtures, arbitrary image names into fakes)
  are untouched.
- The smoke test drives S02-shaped and S03-shaped commands through the
  tool layer directly, not the LLM; normalise nothing before
  comparing.
- If the bytes differ, this becomes a benchmark-affecting change and
  the escape hatch applies — defer to v1.6 (preferred) or run the full
  benchmark; never call a byte difference cosmetic.

## Acceptance

- Both digests, the pull date and `docker image inspect` sizes
  recorded in the report.
- The byte comparison's outcome recorded honestly, with SHA-256
  evidence, whichever way it goes.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0; `bot.py --selftest` and `--selftest-live` both
  green against the new live default.

## Stop

If the before/after bytes differ for either scenario, stop before
updating the pin further — record the exact diff and defer the bump
to v1.6 rather than accepting or masking the difference.
