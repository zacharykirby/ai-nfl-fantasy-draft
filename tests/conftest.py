import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.draft.session import DraftSession


def _player(name, position, position_rank, overall_rank, tier=1):
    return {
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


@pytest.fixture
def web_draft(tmp_path):
    names = {
        "RB": ["Jahmyr Gibbs", "Bijan Robinson", "Saquon Barkley"],
        "WR": ["Ja'Marr Chase", "Puka Nacua", "CeeDee Lamb"],
        "QB": ["Josh Allen", "Lamar Jackson", "Joe Burrow"],
        "TE": ["Trey McBride", "Brock Bowers", "George Kittle"],
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

    board = {
        "schema_version": "1.0",
        "metadata": {"generated_at": "2026-07-19T12:00:00+00:00", "season": 2026},
        "league": {
            "scoring": "half_ppr",
            "league_size": 4,
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
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

