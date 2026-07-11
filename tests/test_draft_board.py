import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from draft_board import DraftBoardBuilder, LeagueConfig, format_board, validate_board


def ranking(name, position, rank, vorp=10, points=100, **extra):
    player = {
        "name": name,
        "pos": position,
        "team": "TST",
        "projection_rank": rank,
        "projection_tier": 1,
        "projected_fantasy_points": points,
        "VORP": vorp,
        "score": 50,
        "score_breakdown": {"projected_points_component": 20},
    }
    player.update(extra)
    return player


def write_rankings(tmp_path, players, projection_source=None):
    projection_source = projection_source or tmp_path / "projections.csv"
    projection_source = Path(projection_source)
    rows = []
    minimums = {"QB": 20, "RB": 40, "WR": 50, "TE": 15}
    for position, count in minimums.items():
        for number in range(count):
            rows.append(
                "{rank},Source {position} {number},{position},TST,7,100,1,{rank},published,False,Test".format(
                    rank=len(rows) + 1, position=position, number=number
                )
            )
    projection_source.write_text(
        "rank,name,position,team,bye_week,projected_fantasy_points,tier,adp,projection_method,team_conflict,source\n"
        + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    (projection_source.parent / "projection_metadata_2026.json").write_text(
        json.dumps(
            {
                "season": 2026,
                "retrieved_at": "2026-07-10T00:00:00+00:00",
                "sources": {"projections": ["https://example.test"]},
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "outputs" / "player_rankings.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "metadata": {
                    "target_season": 2026,
                    "generated_at": "2026-07-10T00:00:00",
                    "projection_source": str(projection_source),
                },
                "rankings": players,
            }
        ),
        encoding="utf-8",
    )
    return path


def complete_players():
    return [
        ranking("Quarterback", "QB", 10, 20, 300),
        ranking("Running Back", "RB", 1, 60, 250),
        ranking("Receiver", "WR", 2, 40, 220),
        ranking("Tight End", "TE", 20, 30, 180),
    ]


def test_build_groups_and_ranks_players_by_position(tmp_path):
    players = complete_players() + [
        ranking("RB Two", "RB", 5, 80, 240),
        ranking("No Projection", "RB", 3, 100, 0),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build(
        limits={"QB": 1, "RB": 2, "WR": 1, "TE": 1}
    )

    assert [player["player"] for player in board["roles"]["RB"]] == ["Running Back", "RB Two"]
    assert [player["position_rank"] for player in board["roles"]["RB"]] == [1, 2]
    assert board["metadata"]["role_counts"] == {"QB": 1, "RB": 2, "WR": 1, "TE": 1}
    assert board["health"]["status"] == "ready"


def test_adp_rank_controls_priority_then_vorp_breaks_ties(tmp_path):
    players = complete_players() + [
        ranking("Same Rank Low", "WR", 8, 5, 180),
        ranking("Same Rank High", "WR", 8, 50, 180),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build()
    names = [player["player"] for player in board["roles"]["WR"]]

    assert names.index("Same Rank High") < names.index("Same Rank Low")


def test_historical_fallback_marks_board_not_ready(tmp_path):
    path = write_rankings(tmp_path, complete_players())
    payload = json.loads(path.read_text())
    payload["metadata"]["projection_source"] = "historical_fantasy_points_fallback"
    path.write_text(json.dumps(payload))

    board = DraftBoardBuilder(path).build()

    assert board["health"]["status"] == "not_ready"
    assert "historical_projection_fallback" in {
        issue["code"] for issue in board["health"]["issues"]
    }


def test_missing_projection_file_marks_board_not_ready(tmp_path):
    path = write_rankings(tmp_path, complete_players())
    payload = json.loads(path.read_text())
    payload["metadata"]["projection_source"] = "data/missing.csv"
    path.write_text(json.dumps(payload))

    board = DraftBoardBuilder(path).build()

    assert board["health"]["status"] == "not_ready"
    assert "projection_source_not_found" in {
        issue["code"] for issue in board["health"]["issues"]
    }


def test_validation_detects_duplicate_and_rank_gap():
    player = {
        "player": "Duplicate",
        "position": "QB",
        "position_rank": 2,
        "projected_points": 100,
    }
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "projection_source": "historical_fantasy_points_fallback"},
        "roles": {"QB": [player, player], "RB": [], "WR": [], "TE": []},
    }

    report = validate_board(board)
    codes = {issue["code"] for issue in report["issues"]}

    assert report["status"] == "not_ready"
    assert {"duplicate_player", "position_rank_gap", "empty_role"} <= codes


def test_league_config_and_text_format(tmp_path):
    with pytest.raises(ValueError, match="Invalid league config"):
        DraftBoardBuilder(write_rankings(tmp_path, complete_players())).build(
            league=LeagueConfig(scoring="points_per_first_down")
        )

    board = DraftBoardBuilder(tmp_path / "outputs" / "player_rankings.json").build()
    output = format_board(board, top_n=1, position="RB")
    assert "RB PRIORITIES" in output
    assert "Running Back" in output
    assert "QB PRIORITIES" not in output
