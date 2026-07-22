# Live Draft Session Engine

The live session engine records draft state independently of any language model. It
uses a ready `outputs/draft_board.json`, snapshots its players, and persists an event
history after every selection or undo.

Implementation: `src/fantasy_draft/draft/session.py`. Existing commands continue
through the `scripts/live_draft.py` compatibility entry point.

## Commands

```bash
python scripts/live_draft.py new home-league --league-size 10 --rounds 15 --user-team 5
python scripts/live_draft.py draft home-league "Jahmyr Gibbs"
python scripts/live_draft.py status home-league
python scripts/live_draft.py available home-league --position WR --top 15
python scripts/live_draft.py roster home-league --team 5
python scripts/live_draft.py undo home-league
python scripts/live_draft.py list
```

A bare session name resolves to `sessions/<name>.json`. An explicit JSON path can be
used instead.

## State guarantees

- Session creation is blocked unless board health is `ready`.
- The board must cover all planned selections plus a meaningful reserve: at least
  one additional league round or 10% of scheduled picks, whichever is larger.
- Snake-order ownership is validated for every pick.
- A player cannot be selected twice.
- Ambiguous fuzzy matches never mutate state.
- Every mutation is written through an atomic temporary-file replacement.
- Undo is represented as an event and restores availability and pick position.
- Reloading validates event continuity and duplicate selections.
- Active sessions retain their original board snapshot even if outputs are refreshed.

## Event contract

Selection events record overall pick, round, team, player identity, position, event
identifier, and timestamp. Undo events reference the selection event they reverse.
Current availability and rosters are reconstructed from active selection events.

The event structure is intended to become the source of truth for the deterministic
recommendation engine and the future model context builder.
