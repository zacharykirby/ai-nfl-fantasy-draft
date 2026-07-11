# Deterministic Draft Recommendation Engine

The recommendation engine evaluates an active `DraftSession` without calling a
language model. Its structured response will become the factual recommendation input
for the future conversational layer.

## Usage

```bash
python scripts/live_draft.py recommend home-league --mode balanced
python scripts/live_draft.py recommend home-league --mode safe --alternatives 3
python scripts/live_draft.py recommend home-league --mode upside --json
```

## Modes

- `safe` applies stronger injury, age-risk, and uncertain-source penalties and gives
  a modest bonus to high-projection flags.
- `balanced` combines board position, VORP, tiers, roster construction, and risk.
- `upside` increases the VORP weight and rewards explicit high-upside and elite-tier
  flags while retaining an injury penalty.

## Independent signals

Every candidate retains separate score components for:

- Overall board value
- Position rank value
- VORP
- Tier value and imminent tier drops
- Open base starter slots
- Recent position runs
- Published versus ADP-estimated projection confidence
- Risk adjustment
- Upside adjustment
- Low estimated survival to the user's next pick

The components are intentionally visible. A future model may explain or challenge the
result using supplied evidence, but it must not manufacture replacement facts.

## Roster and scarcity behavior

Base QB, RB, WR, and TE requirements come from the session league settings. FLEX
eligibility is reported separately so the engine does not pretend that positional
balance always outweighs elite value. Tier state reports the best remaining tier,
players left in that tier, the next tier, and whether a drop is imminent.

A position run is active when at least three of the last six selections share a
position. This is a small urgency signal rather than an instruction to chase a run.

## Survival estimate

Player survival uses a deterministic logistic curve comparing market ADP with the
user's next overall pick. It is a heuristic—not a simulated room—and is returned as
an explicit probability so callers can describe it honestly.

## Response contract

The versioned JSON response includes:

- Primary recommendation and alternatives
- Recommendation mode and confidence
- Candidate evidence and reasons
- Per-component scoring
- Current pick, current team, user team, and next user pick
- Roster needs by position
- Tier state by position
- Recent position-run state
