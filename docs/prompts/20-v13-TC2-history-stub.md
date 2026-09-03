# Prompt 20 — v1.3 TC2: O2 stale-tool-result stubbing + TOO-03 (stage C)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Owner of:** `agent.py` `_assemble_context`, `storage.py` loader hook,
  `config.py` (`HISTORY_TOOL_STUB`), `tests/test_history_stub.py` (new)
- **REQ ids:** REQ-V13-HST-01 … HST-05, REQ-V13-TOO-03

## Brief as sent (abridged)

```
JOB 1 — section 10.2 exactly: stub every tool-role message older than the
current user message IN THE REQUEST ONLY, with the four spec shapes, resolving
name/arguments via tool_call_id against the nearest preceding assistant message.
DB rows untouched. Newest load_skill per name verbatim (HST-02). User/assistant
never stubbed. Budget computed on the stubbed messages; HISTORY_TOOL_STUB=off
must equal the un-stubbed assembly (not a frozen v1.2 payload).
JOB 2 — REQ-V13-TOO-03, which TC1 could not do because the measurement point is
in agent.py: raw_output_chars vs output_chars measured on the STREAM TEXT at one
canonical point per tool, never on the serialized envelope.
Never change CONTEXT_WINDOW_MESSAGES or any meta.constants value.
```
