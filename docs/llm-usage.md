# LLM usage

| # | Stage | Model | Tokens | Cost |
|---|-------|-------|--------|------|
| 1 | spec authoring (writer agent, 3 iterations incl. gate-chain and exec-recipe proof runs) | claude (lab session) | ~213k (harness-reported aggregate; in/out split not exposed) | — (flat-rate session) |
| 2 | spec review (reviewer agent, clean context, 3 passes) | claude (lab session) | ~270k (aggregate) | — |
| 3 | implementation (`go docs/spec/spec-v0.md`) | *to be filled by the implementation run* | | |
| **Σ** | | | | |

Notes: rows 1–2 are the authoring cost of the specification, recorded per
the lab reporting standard; runtime data and secrets are never logged here.
The implementation run appends exact input/output token counts and money
cost from its harness.
