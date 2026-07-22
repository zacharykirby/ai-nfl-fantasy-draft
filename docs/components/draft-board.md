# Draft Board Contract

`outputs/draft_board.json` is the boundary between data preparation and live draft
reasoning. It prioritizes players independently within QB, RB, WR, and TE and does
not prescribe a snake-draft sequence.

Implementation: `src/fantasy_draft/board/builder.py`. The legacy
`scripts/draft_board.py` module is a compatibility wrapper.

## Build and inspect

```bash
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
python scripts/cli.py --show-board --position WR --top 15
python scripts/cli.py --validate-board
```

The canonical default is 330 players: QB 40, RB 110, WR 140, and TE 40. The
RB/WR weighting preserves late-round skill-position depth. Use `--board-top N`
to apply one explicit limit to every role.

Board metadata reports the source ranking count, eligible counts after the
positive-projection/position/identity filters, final role counts, and exclusions
caused by role limits. This makes a shallow upstream source distinguishable from a
deliberately capped board.

## Top-level structure

```json
{
  "schema_version": "1.0",
  "metadata": {},
  "league": {},
  "roles": {"QB": [], "RB": [], "WR": [], "TE": []},
  "health": {"status": "ready", "issues": []}
}
```

Every player includes position and overall ranks, tier, projected points, VORP,
ADP, risk, news signals, flags, and auditable scoring evidence. Consumers should
treat those values as facts supplied by the application and use a model only to
reason over them.

## Health behavior

`health.status` is `not_ready` when the board should not power live advice. Checks
cover missing target season or projections, historical fallback, empty roles,
duplicate players, position mismatches, and rank gaps.

Board generation still writes diagnostic output when health checks fail. The
separate validation command exits with status 1 so automation can enforce readiness.

Projection validation is also available independently:

```bash
python scripts/cli.py --fetch-projections --season 2026
python scripts/cli.py --validate-projections --season 2026
```

The projection manifest records source URLs, retrieval time, coverage, estimates,
missing values, duplicates, and player/team conflicts. Projection quality issues are
copied into board health so downstream clients have one readiness decision.

The primary provider parses the official ESPN Mike Clay projection guide and merges
it with FantasyPros ADP/bye context. Its PPR totals can be converted to PPR,
half-PPR, or standard scoring using projected receptions. A provider-neutral CSV
import is available through `--import-projections CSV` for licensed exports or
manually curated projections.
