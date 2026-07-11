# Draft Board Contract

`outputs/draft_board.json` is the boundary between data preparation and live draft
reasoning. It prioritizes players independently within QB, RB, WR, and TE and does
not prescribe a snake-draft sequence.

## Build and inspect

```bash
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
python scripts/cli.py --show-board --position WR --top 15
python scripts/cli.py --validate-board
```

Default role limits are QB 20, RB 50, WR 60, and TE 20. Use `--board-top N` to
apply one limit to every role.

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
