# Prompt 19 — v1.3 TC1: O1 token-aware tool output (stage C)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Owner of:** `tools.py`, `config.py` (the two window vars), `.env.example`,
  `tests/test_tool_output.py` (new)
- **REQ ids:** REQ-V13-TOO-01 … TOO-10 (TOO-03 was reassigned to TC2, whose
  measurement point is in `agent.py`)

## Brief as sent (abridged)

```
Implement section 10.1 exactly. The REQ-V13-TOO-01 algorithm is NORMATIVE:
MARKER_RESERVE=50, 40/60 head/tail, error-context re-anchoring, step-7 fallback;
fixtures byte-exact; property test len(result) <= max_chars over random inputs.
Redaction BEFORE compaction; strip_secret_fragment on the head part and on the
assembled result. The fetch save is fail-closed and never follows a link:
O_NOFOLLOW/O_DIRECTORY, unlink-then-O_EXCL, no O_TRUNC anywhere; test the
symlinked dir, symlinked target and hard-linked target cases.
TOO-07's envelope has exactly the listed keys in the listed order.
Add EXEC_OUTPUT_DEFAULT_CHARS (1500, 200-4096) and FETCH_INLINE_DEFAULT_CHARS
(5000, 500-20000). Never change EXEC_MAX_STREAM_BYTES (4096, the security
ceiling), FETCH_MAX_BYTES, or any meta.constants value.
```
