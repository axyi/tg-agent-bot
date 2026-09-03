# Prompt 26 — v1.3 TC8: fix the stage-C review findings

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Input:** the TC7 finding list; § 13.5 one fix round
- **REQ ids:** REQ-V13-TOO-02, TOO-07, TOO-09, REQ-V13-CCH-01

## Brief as sent (abridged)

```
Fix, test-first:
1 (BLOCKER, security) the FETCH_MAX_BYTES cut is not followed by
  strip_secret_fragment, so the SAVED sandbox file can end in a proper prefix of
  a live secret — and the tool description tells the model to grep that file.
  Make EVERY cut (byte cut, inline cut, HTML and non-HTML) strip the fragment,
  including the text written to disk. Also fix the narrower variant where
  `truncated` is false and the inline guard skips the strip.
2 spec-normative window constants are only asserted against themselves — pin
  1500/200/4096/5000/500/20000 to literals.
3 stale FakeFetcher payload in test_agent.py uses the dead v1.2 envelope, so the
  one end-to-end skill->fetch test no longer exercises TOO-07.
4 CCH-01 byte-stability is never tested on the budgeted branch D1 actually runs.
5 error_context widened beyond TOO-02's `exit_code != 0`.
6 `compacted` flips on an ANSI-only rewrite.
7 build_system_prompt accepts and ignores `now` — make the footgun catchable.
```
