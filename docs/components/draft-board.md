# Draft Board Contract

`outputs/draft_board.json` is the boundary between data preparation and live draft
reasoning. It prioritizes players independently within QB, RB, WR, and TE and does
not prescribe a snake-draft sequence.
K and D/ST use separate late-round pools: kicker is season-projection based, while
D/ST is ranked by its Week 1 matchup projection. Neither enters skill-position VORP.

Each skill-position list is ordered by the same final VORP value used for its tiers.
Starting from the highest-VORP player, a new tier begins when the drop from the
previous player is greater than the position threshold. A maximum tier size also
splits unusually flat groups:

| Position | VORP gap | Maximum tier size |
| --- | ---: | ---: |
| QB | 8.0 | 6 |
| RB | 10.0 | 10 |
| WR | 10.0 | 10 |
| TE | 8.0 | 6 |

The board records every player's adjacent gap, boundary reason, threshold, and
maximum size in `evidence`. The complete configuration is also captured in
`metadata.tiering_method`, making every boundary reproducible and auditable.

Implementation: `src/fantasy_draft/board/builder.py`. The legacy
`scripts/draft_board.py` module is a compatibility wrapper.

## Build and inspect

```bash
python scripts/cli.py --build-board --league-size 10 --scoring half_ppr
python scripts/cli.py --show-board --position WR --top 15
python scripts/cli.py --validate-board
```

The canonical default is 350 entries: QB 40, RB 110, WR 140, TE 40, D/ST 10,
and K 10. The
RB/WR weighting preserves late-round skill-position depth. Use `--board-top N`
to apply one explicit limit to each skill role; special teams remain fixed at ten.

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
  "roles": {"QB": [], "RB": [], "WR": [], "TE": [], "DST": [], "K": []},
  "health": {"status": "ready", "issues": []}
}
```

Every player includes position and overall ranks, tier, projected points, VORP,
ADP, risk, news signals, flags, and auditable scoring evidence. Consumers should
treat those values as facts supplied by the application and use a model only to
reason over them.

## Health behavior

Runtime health is authoritative. It recomputes three components instead of trusting
the health block saved when the board was built:

- `snapshot` checks the portable board contract, roles, identities, and ranks.
- `source` checks the referenced normalized projection data and manifest.
- `freshness` checks the manifest retrieval time against the age policy.

The combined `status` is `ready`, and `can_create_session` is true, only when all
three components are ready. Existing sessions remain usable during a later source or
freshness failure because each session owns its immutable board snapshot; only new
session creation is blocked.

Board generation still writes diagnostic output when health checks fail. The
separate validation command exits with status 1 so automation can enforce readiness.

Projection validation is also available independently:

```bash
python scripts/cli.py --fetch-projections --season 2026
python scripts/cli.py --validate-projections --season 2026
```

The projection manifest records source URLs, retrieval time, coverage, estimates,
missing values, duplicates, and player/team conflicts. Runtime clients receive the
same split health report from `/api/v1/health` and `/api/v1/board/summary`.

The normalized 2026 projection snapshot is intentionally packaged at
`data/players_2026_positions_bye.csv` so a clean checkout can reproduce runtime
validation. Board writes add a canonical `metadata.board_fingerprint`. The emergency
sheet prints that same fingerprint, and draft-night preflight regenerates the sheet
and fails unless both artifacts match exactly.

The primary provider parses the official ESPN Mike Clay projection guide and merges
it with FantasyPros ADP/bye context. Its PPR totals can be converted to PPR,
half-PPR, or standard scoring using projected receptions. A provider-neutral CSV
import is available through `--import-projections CSV` for licensed exports or
manually curated projections.
