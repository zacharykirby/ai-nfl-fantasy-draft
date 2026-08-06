"""Generate a compact, printable emergency board from the stable board contract."""

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fantasy_draft.board.fingerprint import board_fingerprint


# Minimum printable depth plus league-size multipliers. A 12-team sheet carries
# three QB/TE options per team and five RB/WR options per team.
MINIMUM_POSITION_LIMITS = {"QB": 15, "RB": 30, "WR": 30, "TE": 15, "DST": 10, "K": 10}
POSITION_DEPTH_PER_TEAM = {"QB": 3, "RB": 5, "WR": 5, "TE": 3, "DST": 0, "K": 0}
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

# Intentionally small and easy to edit before draft night. These are personal
# decision prompts, not inputs to the ranking model.
PLAYER_MARKERS = {
    "Josh Allen": "⬇️", "Lamar Jackson": "⬇️", "Jalen Hurts": "🔥",
    "Drake Maye": "🔥", "Jayden Daniels": "⚠️", "Joe Burrow": "🔥",
    "Caleb Williams": "🎲", "Bo Nix": "🎲", "Brock Purdy": "🎲",
    "Aaron Rodgers": "🛑",
    "Josh Jacobs": "🔥", "Chase Brown": "🔥", "Derrick Henry": "⬇️",
    "Christian McCaffrey": "⚠️", "TreVeyon Henderson": "🎲",
    "Bucky Irving": "⚠️", "Ashton Jeanty": "🔥", "Omarion Hampton": "🎲",
    "Amon-Ra St. Brown": "🔥", "Jaxon Smith-Njigba": "🔥",
    "Puka Nacua": "⚠️", "Rashee Rice": "⚠️", "Tetairoa McMillan": "🎲",
    "George Pickens": "⬇️", "Trey McBride": "🔥", "Brock Bowers": "⚠️",
    "Tyler Warren": "🎲", "George Kittle": "⚠️", "Travis Kelce": "⬇️",
    "Colston Loveland": "🎲",
}


def position_limits(board: Dict[str, Any]) -> Dict[str, int]:
    league_size = int((board.get("league") or {}).get("league_size") or 10)
    return {
        position: max(MINIMUM_POSITION_LIMITS[position], league_size * per_team)
        for position, per_team in POSITION_DEPTH_PER_TEAM.items()
    }


def _number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _risk(player: Dict[str, Any]) -> str:
    risk = player.get("risk") or {}
    notes = [str(risk.get("level") or "Unknown")]
    flags = {str(flag).casefold() for flag in (player.get("flags") or [])}
    if risk.get("injury_flag") or "availability risk" in flags:
        notes.append("availability")
    if "age risk" in flags:
        notes.append("age")
    if player.get("projection_method") == "adp_estimate":
        notes.append("estimate")
    return "; ".join(notes)


def _text(value: Any) -> str:
    """Keep arbitrary source text from breaking a Markdown table row."""
    return str(value if value not in (None, "") else "-").replace("|", "\\|")


def _news(player: Dict[str, Any]) -> str:
    news = player.get("news") or {}
    count = int(news.get("headline_count") or 0)
    if not count:
        return "-"
    event = news.get("latest_event") or {}
    if isinstance(event, dict) and event.get("event_type") not in (None, "none"):
        detail = (
            event.get("injury_status")
            if event.get("event_type") in {"injury", "recovery"}
            else event.get("role_direction")
            if event.get("event_type") == "role_change"
            else event.get("event_direction")
        )
        return f"{event.get('event_type')}: {detail or 'update'} ({count})"
    return f"{count} report{'s' if count != 1 else ''}; no rank event"


def _marker(player: Dict[str, Any]) -> str:
    news = player.get("news") or {}
    if news.get("latest_event") or (player.get("risk") or {}).get("injury_flag"):
        return "⚠️"
    return PLAYER_MARKERS.get(str(player.get("player") or ""), "")


def _priority_table(players: Iterable[Dict[str, Any]]) -> List[str]:
    lines = [
        "| Rank | Player | Pos | Team | Tier | ADP | VORP |",
        "| ---: | --- | :---: | :---: | ---: | ---: | ---: |",
    ]
    for index, player in enumerate(players, 1):
        lines.append(
            "| {rank} | {player} | {position} | {team} | {tier} | {adp} | {vorp} |".format(
                rank=index,
                player=_text(player.get("player", "Unknown")),
                position=_text(player.get("position") or "-"),
                team=_text(player.get("team") or "FA"),
                tier=player.get("tier", "—"),
                adp=_number(player.get("adp")),
                vorp=_number(player.get("vorp")),
            )
        )
    return lines


def _task_list(players: Iterable[Dict[str, Any]], rank_key: str) -> List[str]:
    """Render real Markdown tasks that Obsidian can query and check off."""
    lines = []
    for index, player in enumerate(players, 1):
        rank = player.get(rank_key) or index
        marker = "{} ".format(_marker(player)) if _marker(player) else ""
        lines.append(
            "- [ ] {marker}**{rank}. {player}** · {team} · Bye {bye} · T{tier} · "
            "ADP {adp} · Proj {projection} · VORP {vorp} · {news} · Risk: {risk}".format(
                rank=rank,
                marker=marker,
                player=_text(player.get("player", "Unknown")),
                team=_text(player.get("team") or "FA"),
                bye=player.get("bye_week") or "-",
                tier=player.get("tier", "—"),
                adp=_number(player.get("adp")),
                projection=_number(player.get("projected_points")),
                vorp=_number(player.get("vorp")),
                news=_news(player),
                risk=_risk(player),
            )
        )
    return lines


def _special_teams_tasks(players: Iterable[Dict[str, Any]]) -> List[str]:
    lines = []
    for index, player in enumerate(players, 1):
        points_label = "W1 proj" if player.get("position") == "DST" else "Season proj"
        lines.append(
            "- [ ] **{rank}. {player}** · {team} · Bye {bye} · {label} {points}".format(
                rank=player.get("position_rank") or index,
                player=_text(player.get("player", "Unknown")),
                team=_text(player.get("team") or "FA"),
                bye=player.get("bye_week") or "-",
                label=points_label,
                points=_number(player.get("projected_points")),
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
    limits = position_limits(board)
    all_players = [
        player for position in SKILL_POSITIONS for player in roles.get(position, [])
    ]
    priorities = sorted(
        all_players,
        key=lambda player: (
            -float(player.get("vorp") or 0),
            -float(player.get("score") or 0),
            int(player.get("overall_rank") or 9999),
        ),
    )[:20]
    starters = league.get("starters", {})
    fingerprint = board_fingerprint(board)
    generated_at = str(metadata.get("generated_at") or "unknown")
    status = str(health.get("status", "unknown")).casefold()

    lines = [
        "---",
        "aliases:",
        f"  - Fantasy Draft Cheat Sheet {metadata.get('season', '')}",
        "tags:",
        "  - fantasy-football",
        "  - draft",
        "  - cheat-sheet",
        f"season: {metadata.get('season', 'null')}",
        f"scoring: {str(league.get('scoring', 'unknown')).replace('_', '-')}",
        f"league_size: {league.get('league_size', 'null')}",
        f"board_status: {status}",
        f'generated: "{generated_at}"',
        "---",
        "",
        "# Fantasy Draft Cheat Sheet",
        "",
        "> [!tip] Draft workflow",
        "> Start with overall value, then check tier scarcity, ADP, and roster context. Do not force a position merely because a slot is open.",
        "> This note is static; the live app remains authoritative for availability and roster-aware advice.",
        "",
        "## Quick navigation",
        "",
        "[[#Running Backs (RB)|RB]] · [[#Wide Receivers (WR)|WR]] · "
        "[[#Quarterbacks (QB)|QB]] · [[#Tight Ends (TE)|TE]] · "
        "[[#Defense / Special Teams (D/ST)|D/ST]] · [[#Kickers (K)|K]] · "
        "[[#Draft status|Status]] · [[#QB room tracker|QB room]] · "
        "[[#Roster checkpoints|Checkpoints]] · [[#Draft strategy|Strategy]] · "
        "[[#Recovery commands|Recovery]]",
        "",
        "## Draft status",
        "",
        "**My pick:** __________",
        "**Current round:** __________",
        "**Next pick:** __________",
        "",
        "### My roster",
        "",
        "- QB:",
        "- RB:",
        "- RB:",
        "- WR:",
        "- WR:",
        "- TE:",
        "- FLEX:",
        "- BENCH:",
        "- BENCH:",
        "- BENCH:",
        "- BENCH:",
        "- BENCH:",
        "- BENCH:",
        "- D/ST:",
        "- K:",
        "",
        "> [!warning] League tendencies",
        "> - Expect quarterbacks to go in rounds 1–2.",
        "> - Managers may draft kickers and defenses unusually early.",
        "> - Do not chase bad picks just because a run starts.",
        "> - Every early K or D/ST pick pushes a useful RB/WR/TE down the board.",
        "> - Do not start the QB run, but avoid falling multiple QB tiers behind.",
        "",
        "> [!tip] On the clock",
        "> 1. Look at the best unchecked overall values.",
        "> 2. Check whether a positional tier is about to end.",
        "> 3. Use ADP to estimate whether the player returns.",
        "> 4. Break close ties toward RB/WR upside.",
        "> 5. Do not draft from positional need alone.",
        "",
        "> [!info] Player markers",
        "> 🔥 Priority target · ⬇️ Only if falling · 🎲 Upside bench pick · 🛑 Avoid at cost · ⚠️ Verify news/role",
        "> Markers are a small editable watchlist; they do not affect rankings.",
        "",
        "## QB room tracker",
        "",
        f"**Teams with QB:** 0 / {league.get('league_size', 12)}",
        "",
        "### My acceptable QB tiers",
        "",
        "**Pay-up**",
        "- Josh Allen",
        "- Lamar Jackson",
        "",
        "**Preferred value**",
        "- Jalen Hurts",
        "- Drake Maye",
        "- Jayden Daniels",
        "- Joe Burrow",
        "",
        "**Wait targets**",
        "- Patrick Mahomes",
        "- Bo Nix",
        "- Brock Purdy",
        "",
        "**Emergency**",
        "- Best remaining starter",
        "",
        "## Board Health",
        "",
        f"- Status: **{str(health.get('status', 'unknown')).upper()}**",
        f"- Season/scoring: {metadata.get('season', '—')} / {str(league.get('scoring', 'unknown')).replace('_', '-')} ",
        f"- Board generated: {metadata.get('generated_at', 'unknown')}",
        f"- News analyzed: {metadata.get('news_analyzed_at') or 'not included'}; "
        f"{metadata.get('news_headlines_analyzed', 0)} headlines / "
        f"{metadata.get('news_players_found', 0)} players",
        "- News ranking adjustments: "
        f"**{'ENABLED' if metadata.get('news_ranking_adjustments_enabled') else 'OFF'}** "
        "(news remains visible as annotation)",
        f"- Board fingerprint: `{fingerprint}`",
        f"- League: {league.get('league_size', '—')} teams; starters "
        f"QB {starters.get('QB', 0)}, RB {starters.get('RB', 0)}, WR {starters.get('WR', 0)}, "
        f"TE {starters.get('TE', 0)}, FLEX {starters.get('FLEX', 0)}; bench {league.get('bench_size', '—')}",
    ]
    issues = health.get("issues") or []
    if issues:
        lines.extend(["", "> [!warning] Data warnings"])
        lines.extend(
            f"> - **{str(issue.get('severity', 'warning')).upper()} — {issue.get('code', 'unknown')}:** {issue.get('message', '')}"
            for issue in issues
        )
    else:
        lines.extend(["", "- No board-health issues reported."])

    lines.extend([
        "",
        "## Roster checkpoints",
        "",
        "### After 3 picks",
        "- Ideally 2 RB/WR plus one more elite RB, WR, TE, or QB value.",
        "- Do not force balance.",
        "",
        "### After 6 picks",
        "- At least 4 RB/WR total.",
        "- Preferably one strong starting RB pair or strong WR core.",
        "- QB or TE only if the price was reasonable.",
        "",
        "### After 9 picks",
        "- Starting lineup mostly filled.",
        "- At least 2–3 bench players with real upside.",
        "- Know the remaining acceptable QB and TE tiers.",
        "",
        "### Final rounds",
        "- Favor upside RB/WR before backup QB or backup TE.",
        "- D/ST near the end.",
        "- Kicker last unless league rules force otherwise.",
        "",
        "> [!danger] Draft-night traps",
        "> - Do not draft a player solely because he is next in ADP.",
        "> - Do not chase a position after the value has already disappeared.",
        "> - Do not take a second QB or TE early in a one-QB league.",
        "> - Do not fill the bench with low-upside veterans.",
        "> - Do not overreact to bye weeks during the early rounds.",
        "> - Do not let the draft room’s weird picks redefine value.",
    ])

    lines.extend(["", "## Overall Priorities by VORP", ""])
    lines.extend(_priority_table(priorities))

    position_titles = {
        "RB": "Running Backs (RB)",
        "WR": "Wide Receivers (WR)",
        "QB": "Quarterbacks (QB)",
        "TE": "Tight Ends (TE)",
    }
    for position in ("RB", "WR", "QB", "TE"):
        lines.extend(["", f"## {position_titles[position]}", ""])
        lines.extend(_task_list((roles.get(position) or [])[: limits[position]], "position_rank"))

    lines.extend(["", "## Defense / Special Teams (D/ST)", ""])
    lines.extend(_special_teams_tasks((roles.get("DST") or [])[: limits["DST"]]))
    lines.extend([
        "",
        "> [!tip] D/ST timing",
        "> Draft one in the second-to-last round. Prefer the strongest Week 1 matchup, be willing to stream, and do not chase an early run.",
        "",
        "## Kickers (K)",
        "",
    ])
    lines.extend(_special_teams_tasks((roles.get("K") or [])[: limits["K"]]))
    lines.extend([
        "",
        "> [!tip] Kicker timing",
        "> Draft one in the final round. Favor a productive offense, do not reach, and let other managers start the run.",
    ])

    lines.extend(
        [
            "",
            "## Draft strategy",
            "",
            "- Treat tiers as decision boundaries: prefer the final player in a scarce tier over a small cross-position score edge.",
            "- Use VORP to compare positional leverage; use ADP only to judge whether a target may survive to the next pick.",
            "- Fill RB/WR/FLEX volume without forcing a position when a clearly stronger tier remains available.",
            "- Recheck injury, role, team, and bye-week warnings before relying on any estimated or incomplete row.",
            "- D/ST belongs in the second-to-last round and kicker in the final round; preserve bench lottery tickets even when another manager starts a run.",
            "- This sheet has no live availability or model reasoning. Cross off every selection immediately.",
            "",
            "## Recovery commands",
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
    temporary = output.with_name(".{}.{}.tmp".format(output.name, os.getpid()))
    temporary.write_text(render_cheatsheet(board, health), encoding="utf-8")
    temporary.replace(output)
    return output
