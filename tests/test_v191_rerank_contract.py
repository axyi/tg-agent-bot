"""v1.9.1 T1 (docs/spec/task-briefs/v191-T1.md): the rerank contract fix --
a JSON-schema `response_format` on the rerank call, and budgets sized to what
was actually measured (`docs/reports/report-v1.9.1.md`) rather than to
another model's chain-of-thought.

Offline and deterministic: no transport, no LLM call.
"""

import rag


def test_t_v191_rerank_max_tokens_is_pinned_to_the_measured_ceiling():
    """Measured (docs/reports/report-v1.9.1.md): the passing completion
    length across every routed model, with the JSON schema below, never
    exceeds 53 tokens. 128 is pinned here rather than re-derived from
    rag.py, so a future edit to the constant fails this test loudly."""
    assert rag._RERANK_MAX_TOKENS == 128


def test_t_v191_rerank_timeout_is_pinned_to_the_measured_ceiling():
    """Measured (docs/reports/report-v1.9.1.md): median latency 0.83s on
    the model LLM_RERANK_MODEL routes to. 30.0 is pinned here rather than
    re-derived from rag.py."""
    assert rag._RERANK_TIMEOUT_S == 30.0


def test_t_v191_rerank_response_format_schema_shape():
    """The schema literally specified in the task brief, `<n>` bound to the
    candidate count actually passed -- 3, deliberately different from
    _HYBRID_CANDIDATES (10), so this test cannot pass vacuously on a call
    site that hardcodes the constant instead of the real count."""
    n = 3
    assert n != rag._HYBRID_CANDIDATES
    assert rag._rerank_response_format(n) == {
        "type": "json_schema",
        "json_schema": {
            "name": "rerank",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "order": {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 1, "maximum": n},
                        "minItems": 1,
                        "maxItems": n,
                    }
                },
                "required": ["order"],
                "additionalProperties": False,
            },
        },
    }


def test_t_v191_parse_rerank_reply_accepts_the_order_wrapped_shape():
    """The schema wraps the answer as `{"order": [...]}`; `_parse_rerank_reply`
    needs no change to read it -- its `re.search(r"\\[.*?\\]", ...)` already
    lifts the array out of the wrapping object."""
    assert rag._parse_rerank_reply('{"order": [3, 1, 2]}', 3) == [2, 0, 1]


def test_t_v191_parse_rerank_reply_still_accepts_a_bare_array():
    """The pre-schema shape (a bare JSON array, no wrapping object) must
    still parse -- REQ-V190-RET-06's original contract, kept deliberately,
    not incidentally."""
    assert rag._parse_rerank_reply("[3, 1, 2]", 3) == [2, 0, 1]
