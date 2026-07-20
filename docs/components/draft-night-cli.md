# Draft-Night Interactive CLI

The interactive CLI combines session state, deterministic recommendations, and the
controlled model layer in one laptop-friendly loop.

Implementation: `src/fantasy_draft/cli/`. The packaged `live-draft` command and the
legacy `scripts/live_draft.py` entry point use the same code.

## Start

```bash
python scripts/live_draft.py interactive home-league
```

## Dashboard

The compact dashboard includes:

- Session and active/complete status
- Current overall pick, round, and selecting team
- User team and next user pick
- Model online/offline state
- Autosave path and board snapshot size
- User roster
- Five recent selections
- Imminent tier-drop alerts
- Five best available players

The dashboard redraws after `draft` and `undo`, or on demand with `status`.

## Commands

```text
draft PLAYER             Record the next selection (d)
undo                     Undo the latest selection (u)
recommend [MODE]         Offline safe/balanced/upside advice (r)
ask QUESTION             Controlled model reasoning with fallback (q)
available [POS] [N]      Best available players (a)
roster [TEAM]            User or opponent roster
status                   Redraw dashboard (s)
help                     Command reference (h)
quit                     Save and leave (exit, x)
```

Bare sentences and questions are passed to `ask`. State mutation always requires an
explicit `draft` or `undo` command, even if a natural-language request asks the model
to record a selection.

## Failure behavior

- Command errors are printed without terminating the shell.
- Ambiguous players show candidates and do not alter state.
- Model failure immediately uses deterministic advice.
- EOF and Ctrl-C save the session before exit.
- Every selection and undo is already atomically autosaved by the session engine.
- Existing noninteractive commands remain available for recovery and scripting.
