# Deterministic Draft Recommendation Engine

The recommendation engine evaluates an active `DraftSession` without calling a
language model. Its structured response will become the factual recommendation input
for the future conversational layer.

Implementation: `src/fantasy_draft/draft/recommendations.py`.

## Usage

```bash
python scripts/live_draft.py recommend home-league --mode balanced
python scripts/live_draft.py recommend home-league --mode safe --alternatives 3
python scripts/live_draft.py recommend home-league --mode upside --json
```

## Modes

- `safe` applies stronger injury, age-risk, and uncertain-source penalties and gives
  a modest bonus to high-projection flags.
- `balanced` combines board position, league-adjusted VORP, tiers, roster construction,
  and risk.
- `upside` increases the VORP weight and rewards explicit high-upside and elite-tier
  flags while retaining an injury penalty.

## Independent signals

Every candidate retains separate score components for:

- Overall board value
- Position rank value
- League-adjusted VORP and the disclosed replacement rank/baseline
- Tier value and imminent tier drops
- Round-sensitive starter, FLEX, depth, and position-overload pressure
- Recent position runs
- Published versus ADP-estimated projection confidence
- Risk adjustment
- Upside adjustment
- Low estimated survival to the user's next pick

Every available player is scored; the engine no longer truncates evaluation at the
top 40 overall. The response reports available and scored counts so candidate breadth
is auditable.

The components are intentionally visible. A future model may explain or challenge the
result using supplied evidence, but it must not manufacture replacement facts.

## Roster and scarcity behavior

Base QB, RB, WR, and TE requirements come from the session league settings. FLEX demand
is allocated to the strongest projected eligible players after base starters. The
first player beyond that league-wide demand is the replacement rank; a three-player
projection window supplies a stable baseline. Raw board VORP remains visible as
`source_vorp`, but live scoring uses the league-adjusted value.

Roster need starts as a modest value signal and grows as the draft progresses. Once a
position reaches its starter/depth target, another player receives an explicit balance
adjustment. Deterministic warnings expose late open starters, actual QB/TE overload,
and clustered roster byes. Candidate bye overlap is a caveat only—there is no hidden
bye-week score penalty.

Tier state reports the best remaining tier, players left in that tier, the next tier,
and whether a drop is imminent.

A position run is active when at least three of the last six selections share a
position. This is a small urgency signal rather than an instruction to chase a run.

## Survival estimate

Player survival uses a deterministic logistic curve comparing market ADP with the
user's next overall pick. Tier survival estimates whether at least one current-tier
player remains and is labeled as an independence heuristic. Both probabilities feed a
restrained `yes` / `probably` / `risky` / `no` / `unknown` wait assessment; they are
not presented as a simulated room.

## Response contract

The versioned JSON response includes:

- Primary recommendation and alternatives
- Recommendation mode and confidence
- Candidate evidence and reasons
- Per-component scoring
- Current pick, current team, user team, and next user pick
- Roster needs by position
- Roster-balance warnings and candidate caveats
- League-aware replacement levels
- Tier state by position
- Player/tier survival and wait assessment
- Candidate-pool breadth
- Recent position-run state
