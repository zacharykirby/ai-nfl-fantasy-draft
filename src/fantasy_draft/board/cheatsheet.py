"""Generate a compact, printable emergency board from the stable board contract."""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


POSITION_LIMITS = {"QB": 10, "RB": 18, "WR": 18, "TE": 10}


def _number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _risk(player: Dict[str, Any]) -> str:
    risk = player.get("risk") or {}
    level = str(risk.get("level") or "Unknown")
    if player.get("projection_method") == "adp_estimate":
        return f"{level}; estimate"
    return level


def _table(players: Iterable[Dict[str, Any]], rank_key: Optional[str]) -> List[str]:
    lines = [
        "| Rank | Player | Team | Tier | ADP | Proj | VORP | Risk |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for index, player in enumerate(players, 1):
        rank = player.get(rank_key) or index if rank_key else index
        lines.append(
            "| {rank} | {player} | {team} | {tier} | {adp} | {projection} | {vorp} | {risk} |".format(
                rank=rank,
                player=player.get("player", "Unknown"),
                team=player.get("team") or "FA",
                tier=player.get("tier", "—"),
                adp=_number(player.get("adp")),
                projection=_number(player.get("projected_points")),
                vorp=_number(player.get("vorp")),
                risk=_risk(player),
            )
        )
    return lines


def render_cheatsheet(
    board: Dict[str, Any], health: Optional[Dict[str, Any]] = None
) -> str:
    """Return deterministic Markdown suitable for printing or offline reference."""
    metadata = board.get("metadata", {})
    league = board.get("league", {})
    health = health or board.get("health", {})
    roles = board.get("roles", {})
    all_players = [player for players in roles.values() for player in players]
    priorities = sorted(
        all_players,
        key=lambda player: (
            -float(player.get("vorp") or 0),
            -float(player.get("score") or 0),
            int(player.get("overall_rank") or 9999),
        ),
    )[:20]
    starters = league.get("starters", {})

    lines = [
        "# Emergency Fantasy Draft Cheatsheet",
        "",
        "> Static fallback only. Availability is not tracked here; cross off selections manually.",
        "",
        "## Board Health",
        "",
        f"- Status: **{str(health.get('status', 'unknown')).upper()}**",
        f"- Season/scoring: {metadata.get('season', '—')} / {str(league.get('scoring', 'unknown')).replace('_', '-')} ",
        f"- Board generated: {metadata.get('generated_at', 'unknown')}",
        f"- League: {league.get('league_size', '—')} teams; starters "
        f"QB {starters.get('QB', 0)}, RB {starters.get('RB', 0)}, WR {starters.get('WR', 0)}, "
        f"TE {starters.get('TE', 0)}, FLEX {starters.get('FLEX', 0)}; bench {league.get('bench_size', '—')}",
    ]
    issues = health.get("issues") or []
    if issues:
        lines.extend(["", "### Data warnings", ""])
        lines.extend(
            f"- **{str(issue.get('severity', 'warning')).upper()} — {issue.get('code', 'unknown')}:** {issue.get('message', '')}"
            for issue in issues
        )
    else:
        lines.extend(["", "- No board-health issues reported."])

    lines.extend(["", "## Overall Priorities by VORP", ""])
    lines.extend(_table(priorities, None))

    for position in ("RB", "WR", "QB", "TE"):
        lines.extend(["", f"## {position} Tiers", ""])
        lines.extend(_table((roles.get(position) or [])[: POSITION_LIMITS[position]], "position_rank"))

    lines.extend(
        [
            "",
            "## Draft Strategy Notes",
            "",
            "- Treat tiers as decision boundaries: prefer the final player in a scarce tier over a small cross-position score edge.",
            "- Use VORP to compare positional leverage; use ADP only to judge whether a target may survive to the next pick.",
            "- Fill RB/WR/FLEX volume without forcing a position when a clearly stronger tier remains available.",
            "- Recheck injury, role, team, and bye-week warnings before relying on any estimated or incomplete row.",
            "- This sheet has no live availability or model reasoning. Cross off every selection immediately.",
            "",
            "## Startup and Recovery",
            "",
            "```bash",
            "scripts/draft-night-server start",
            "scripts/draft-night-server status",
            "venv/bin/python scripts/cli.py --validate-board",
            "venv/bin/python scripts/live_draft.py interactive <session-name>",
            "```",
            "",
            "If the phone loses the cockpit, reconnect Tailscale and refresh. If the server remains unavailable, use the terminal command above and this sheet. Stop cleanly with `scripts/draft-night-server stop`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_cheatsheet(
    board: Dict[str, Any], output: Path, health: Optional[Dict[str, Any]] = None
) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_cheatsheet(board, health), encoding="utf-8")
    return output
