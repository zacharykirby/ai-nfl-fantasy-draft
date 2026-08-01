# Controlled Model Reasoning Layer

The live model layer explains and compares deterministic draft evidence. It does not
own player facts, availability, rankings, or session state.

Implementation: `src/fantasy_draft/assistant/service.py`, with the OpenRouter adapter
in `src/fantasy_draft/providers/openrouter.py`.

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

The mobile **Talk shop** drawer exposes the same layer through
`POST /api/v1/sessions/{name}/assistant/ask`. The web route uses a fixed 12-second
server timeout, reports latency and response source, and compares the session revision
again after the model returns. Advice generated across a state change is marked stale.

The phone cockpit also offers an explicit `POST .../assistant/oh-god` situation check.
It receives the current pick and exact draft revision, uses an `oh_god_context.v1`
packet capped at 18 candidate IDs, and returns `oh_god.v1`: a headline, urgency,
explanation, at most three distinct options, a wait assessment, caveats, and a compact
evidence summary. Unknown or drafted IDs and mismatched revisions are rejected. The
five-second model attempt falls back to the same deterministic evidence. Enumerated
follow-ups (`can_i_wait`, `why_not_safe`, and `more_upside`) are local, contextual, and
read-only.

Neither assistant route is called automatically. Chill mode is the default; it hides
the persistent recommendation. **OH GOD** and the collapsed **Talk shop** drawer each
require an explicit user action, and their controls never call a pick mutation.

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
pick, bulk-pick, undo, or `live_draft.py draft` commands.

## Prompt policy

The system prompt requires the model to use only supplied facts, forbids external
memory for player data, forbids state mutation, and requests concise conclusions
rather than hidden chain-of-thought. OpenRouter requests use structured JSON mode,
low temperature, a bounded output budget, and an explicit timeout.
