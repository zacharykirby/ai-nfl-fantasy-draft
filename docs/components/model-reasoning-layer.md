# Controlled Model Reasoning Layer

The live model layer explains and compares deterministic draft evidence. It does not
own player facts, availability, rankings, or session state.

## Usage

```bash
python scripts/live_draft.py ask home-league \
  "Who should I take, and can I wait at quarterback?" \
  --mode balanced

python scripts/live_draft.py ask home-league \
  "Compare the best RB and WR choices" \
  --mode upside --json
```

Options include `--model`, `--timeout`, `--mode`, and `--json`.

## Context boundary

The model receives:

- League scoring, size, starters, and user team
- Current pick, team, and next user pick
- User roster
- Up to eight recent selections
- Deterministic primary and alternatives
- Deterministic roster, tier, run, risk, and survival signals
- Top available players by position
- A deduplicated candidate allowlist

It does not receive the entire board. Typical context includes roughly 12–18
candidates rather than hundreds of player records.

## Response validation

The model must return schema version `1.0` with an answer, optional recommendation,
up to three alternatives, confidence, rationale, cautions, and an agreement flag.

Validation rejects:

- Missing or incorrectly typed fields
- Unsupported schema versions
- Recommendations outside the candidate allowlist
- Unavailable alternatives
- Duplicate primary/alternative entries
- Confidence outside zero to one
- An agreement flag inconsistent with the deterministic primary

Invalid output is never partially accepted.

## Fallback behavior

The assistant fails fast to deterministic advice when:

- The OpenRouter key is unavailable
- The request times out or fails
- The response is not valid JSON
- Schema validation fails
- A recommended player is unavailable or unknown

Fallback responses use the same outward schema and include the failure reason in
`cautions`. Session events are never changed by `ask`; selections remain explicit
`live_draft.py draft` commands.

## Prompt policy

The system prompt requires the model to use only supplied facts, forbids external
memory for player data, forbids state mutation, and requests concise conclusions
rather than hidden chain-of-thought. OpenRouter requests use structured JSON mode,
low temperature, a bounded output budget, and an explicit timeout.
