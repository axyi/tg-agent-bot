"""spec-v1.10.1 T4 (docs/spec/spec-v1.10.1.md Sec.9, REQ-V1101-PRM-01,
REQ-V1101-PRM-02, REQ-V1101-PRM-03): the prompt/tool-literal change that
compels a document search. `T-V1101-PRM-01` (the new docs line occurs
exactly once and the old, pre-T4 137-char docs line is gone) and
`T-V1101-PRM-03` (the rendered prompt's exact char count) live here.

REV-01 review fix (docs/prompts/208-v1101-t5-review.md): PRM-03's
"exactly 736 chars" assertion was originally added inline at
`tests/test_v190_tool.py` and mislabeled `prm_01`; moved here under its
correct id, alongside the PRM-01 assertions the spec actually requires
and which were previously missing entirely.

Offline: no LLM call, no I/O beyond importing `agent`.
"""

import agent

# The new docs line (T4), byte-identical to tests/test_v190_tool.py's
# PROMPT_LINE constant.
PROMPT_LINE = (
    "Docs: when the user has uploaded files, call search_documents BEFORE answering "
    "anything they could answer; answer from returned passages only, cite Source: "
    "<filename> (page N); else say the docs lack it."
)

# The old, pre-T4 docs line PROMPT_LINE replaced.
OLD_PROMPT_LINE = (
    "Docs: search_documents finds user files; answer from returned passages only, "
    "cite Source: <filename> (page N); else say the docs lack it."
)


def test_t_v1101_prm_01_the_new_docs_line_occurs_exactly_once():
    assert agent.SYSTEM_PROMPT.count(PROMPT_LINE) == 1


def test_t_v1101_prm_01_the_old_docs_line_is_absent():
    assert OLD_PROMPT_LINE not in agent.SYSTEM_PROMPT


def test_t_v1101_prm_03_the_rendered_prompt_is_exactly_939_chars():
    assert len(agent.SYSTEM_PROMPT.replace("{skill_lines}", "")) == 939
