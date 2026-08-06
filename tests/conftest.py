import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.draft.session import DraftSession


def _player(name, position, position_rank, overall_rank, tier=1):
    player = {
        "player": name,
        "position": position,
        "team": "TST",
        "position_rank": position_rank,
        "overall_rank": overall_rank,
        "tier": tier,
        "projected_points": 250 - overall_rank,
        "vorp": 70 - overall_rank,
        "adp": float(overall_rank),
        "projection_method": "published",
        "risk": {"level": "Low", "injury_flag": False},
        "flags": ["High Upside"] if position in {"RB", "WR"} else [],
    }
    if position in {"DST", "K"}:
        player.update({
            "overall_rank": None,
            "vorp": None,
            "late_round_only": True,
            "ranking_basis": "week_1_matchup_projection" if position == "DST" else "season_projection",
        })
    return player


@pytest.fixture
def web_draft(tmp_path):
    names = {
        "RB": ["Jahmyr Gibbs", "Bijan Robinson", "Saquon Barkley"],
        "WR": ["Ja'Marr Chase", "Puka Nacua", "CeeDee Lamb"],
        "QB": ["Josh Allen", "Lamar Jackson", "Joe Burrow"],
        "TE": ["Trey McBride", "Brock Bowers", "George Kittle"],
        "DST": [f"Fixture Defense {number} D/ST" for number in range(1, 11)],
        "K": [f"Fixture Kicker {number}" for number in range(1, 11)],
    }
    overall = 1
    roles = {}
    for position, players in names.items():
        roles[position] = []
        for position_rank, name in enumerate(players, 1):
            roles[position].append(
                _player(name, position, position_rank, overall, tier=1 if position_rank < 3 else 2)
            )
            overall += 1

    projection_path = tmp_path / "players_2026_positions_bye.csv"
    projection_rows = []
    for position, count in {"QB": 20, "RB": 40, "WR": 50, "TE": 15, "K": 10, "DST": 10}.items():
        for number in range(count):
            projection_rows.append(
                "{rank},Fixture {position} {number},{position},TST,7,100,1,{rank},published,False,Fixture".format(
                    rank=len(projection_rows) + 1,
                    position=position,
                    number=number,
                )
            )
    projection_path.write_text(
        "rank,name,position,team,bye_week,projected_fantasy_points,tier,adp,projection_method,team_conflict,source\n"
        + "\n".join(projection_rows)
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "projection_metadata_2026.json").write_text(
        json.dumps(
            {
                "season": 2026,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "sources": {"projections": ["https://example.test"]},
            }
        ),
        encoding="utf-8",
    )

    board = {
        "schema_version": "1.0",
        "metadata": {
            "generated_at": "2026-07-19T12:00:00+00:00",
            "season": 2026,
            "projection_source": str(projection_path),
            "news_source": "none",
        },
        "league": {
            "scoring": "half_ppr",
            "league_size": 4,
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1},
            "bench_size": 1,
        },
        "roles": roles,
        "health": {"status": "ready", "error_count": 0, "warning_count": 0, "issues": []},
    }
    board_path = tmp_path / "draft_board.json"
    board_path.write_text(json.dumps(board), encoding="utf-8")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    session = DraftSession.create(
        sessions_dir / "phone-test.json",
        board_path,
        "phone-test",
        league_size=4,
        rounds=2,
        user_team=2,
    )
    session.draft("Jahmyr Gibbs")
    return {
        "board_path": board_path,
        "sessions_dir": sessions_dir,
        "session": session,
    }

