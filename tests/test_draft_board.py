import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.board.builder import DraftBoardBuilder, LeagueConfig, format_board, validate_board
from fantasy_draft.board.fingerprint import verify_board_fingerprint


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
    minimums = {"QB": 20, "RB": 40, "WR": 50, "TE": 15, "K": 10, "DST": 10}
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
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
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
                    "replacement_model": {
                        "league_size": 10,
                        "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
                        "method": "league_starters_flex_projection_allocation",
                    },
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

    assert [player["player"] for player in board["roles"]["RB"]] == ["RB Two", "Running Back"]
    assert [player["position_rank"] for player in board["roles"]["RB"]] == [1, 2]
    assert board["metadata"]["role_counts"] == {
        "QB": 1, "RB": 2, "WR": 1, "TE": 1, "DST": 10, "K": 10
    }
    assert board["metadata"]["ranking_replacement_model"]["league_size"] == 10
    assert board["health"]["status"] == "ready"


def test_final_vorp_controls_position_priority(tmp_path):
    players = complete_players() + [
        ranking("Higher VORP", "WR", 80, 50, 180, score=60),
        ranking("Higher Score", "WR", 3, 5, 180, score=90),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build()
    names = [player["player"] for player in board["roles"]["WR"]]

    assert names.index("Higher VORP") < names.index("Higher Score")
    assert board["metadata"]["ranking_method"] == "position_vorp_then_score_then_source_rank"


def test_vorp_then_source_rank_break_blended_score_ties(tmp_path):
    players = complete_players() + [
        ranking("Lower VORP", "WR", 3, 5, 180, score=60),
        ranking("Higher VORP", "WR", 80, 50, 180, score=60),
        ranking("Same VORP Worse Rank", "WR", 90, 50, 180, score=60),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build()
    names = [player["player"] for player in board["roles"]["WR"]]

    assert names.index("Higher VORP") < names.index("Same VORP Worse Rank")
    assert names.index("Same VORP Worse Rank") < names.index("Lower VORP")


def test_vorp_gaps_define_rb_tier_boundaries(tmp_path):
    players = complete_players() + [
        ranking("RB One", "RB", 1, 129.8, 250),
        ranking("RB Two Gap", "RB", 2, 125.3, 245),
        ranking("RB Three", "RB", 3, 108.2, 240),
        ranking("RB Four", "RB", 4, 96.2, 235),
        ranking("RB Five", "RB", 5, 93.2, 230),
    ]

    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build()
    backs = board["roles"]["RB"][:5]

    assert [player["player"] for player in backs] == [
        "RB One", "RB Two Gap", "RB Three", "RB Four", "RB Five"
    ]
    assert [player["tier"] for player in backs] == [1, 1, 2, 3, 3]
    assert backs[2]["evidence"]["tier_gap_from_previous"] == pytest.approx(17.1)
    assert backs[2]["evidence"]["tier_boundary_reason"] == "vorp_gap"
    assert backs[3]["evidence"]["tier_gap_from_previous"] == pytest.approx(12.0)


def test_max_tier_size_splits_a_large_flat_group(tmp_path):
    flat = [
        ranking("Flat WR {}".format(number), "WR", number, 200 - number, 200)
        for number in range(1, 12)
    ]

    board = DraftBoardBuilder(write_rankings(tmp_path, complete_players() + flat)).build()
    receivers = board["roles"]["WR"][:11]

    assert [player["tier"] for player in receivers[:10]] == [1] * 10
    assert receivers[10]["tier"] == 2
    assert receivers[10]["evidence"]["tier_boundary_reason"] == "max_tier_size"


def test_build_deduplicates_name_aliases_and_backfills_role_limit(tmp_path):
    players = complete_players() + [
        ranking("D.J. Moore", "WR", 3, 30, 210, score=80),
        ranking("DJ Moore", "WR", 4, 29, 209, score=79),
        ranking("D.J. Moore Jr.", "WR", 6, 18, 190, score=68),
        ranking("Backfill Receiver", "WR", 5, 20, 200, score=70),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build(
        limits={"QB": 1, "RB": 1, "WR": 3, "TE": 1}
    )

    receivers = board["roles"]["WR"]
    assert [player["player"] for player in receivers] == [
        "Receiver",
        "D.J. Moore",
        "Backfill Receiver",
    ]
    assert [player["position_rank"] for player in receivers] == [1, 2, 3]


def test_build_deduplicates_cam_and_cameron_ward(tmp_path):
    players = complete_players() + [
        ranking("Cameron Ward", "QB", 2, 30, 219, score=80),
        ranking("Cam Ward", "QB", 3, 29, 174, score=79),
        ranking("Backfill Quarterback", "QB", 4, 20, 170, score=70),
    ]
    board = DraftBoardBuilder(write_rankings(tmp_path, players)).build(
        limits={"QB": 3, "RB": 1, "WR": 1, "TE": 1}
    )

    quarterbacks = board["roles"]["QB"]
    names = [player["player"] for player in quarterbacks]
    assert "Cameron Ward" in names
    assert "Cam Ward" not in names
    assert "Backfill Quarterback" in names
    assert len(quarterbacks) == 3
    assert [player["position_rank"] for player in quarterbacks] == [1, 2, 3]


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


def test_validation_detects_punctuation_alias_duplicate():
    board = {
        "schema_version": "1.0",
        "metadata": {
            "season": 2026,
            "projection_source": "historical_fantasy_points_fallback",
        },
        "roles": {
            "QB": [
                {"player": "D.J. Moore", "position": "QB", "position_rank": 1, "projected_points": 100},
                {"player": "DJ Moore", "position": "QB", "position_rank": 2, "projected_points": 90},
            ],
            "RB": [],
            "WR": [],
            "TE": [],
        },
    }

    report = validate_board(board)
    assert "duplicate_player" in {issue["code"] for issue in report["issues"]}


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


def test_special_teams_are_required_and_excluded_from_skill_vorp(tmp_path):
    board = DraftBoardBuilder(write_rankings(tmp_path, complete_players())).build()

    assert len(board["roles"]["DST"]) == 10
    assert len(board["roles"]["K"]) == 10
    assert all(player["vorp"] is None for player in board["roles"]["DST"])
    assert all(player["vorp"] is None for player in board["roles"]["K"])
    assert board["metadata"]["special_teams_ranking_method"] == {
        "DST": "week_1_matchup_projection",
        "K": "season_projection",
        "excluded_from_skill_vorp": True,
    }

    board["roles"]["K"] = []
    report = validate_board(board)

    assert report["status"] == "not_ready"
    assert "empty_role" in {issue["code"] for issue in report["issues"]}


def test_special_teams_pool_below_ten_is_not_ready(tmp_path):
    board = DraftBoardBuilder(write_rankings(tmp_path, complete_players())).build()
    board["roles"]["DST"] = board["roles"]["DST"][:9]

    report = validate_board(board)

    assert report["status"] == "not_ready"
    assert "special_teams_coverage_low" in {
        issue["code"] for issue in report["issues"]
    }


def test_board_writer_stamps_exact_artifact_fingerprint(tmp_path):
    builder = DraftBoardBuilder(write_rankings(tmp_path, complete_players()))
    board = builder.build()
    path = builder.write(board, tmp_path / "outputs" / "draft_board.json")

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert verify_board_fingerprint(saved)["matches"] is True


def test_default_board_universe_is_350_and_weighted_to_rb_wr(tmp_path):
    players = []
    available = {"QB": 42, "RB": 138, "WR": 194, "TE": 80}
    overall = 1
    for position, count in available.items():
        for rank in range(1, count + 1):
            players.append({
                "name": f"{position} Player {rank}",
                "pos": position,
                "team": "TST",
                "score": 1000 - overall,
                "VORP": 500 - overall,
                "projected_fantasy_points": 300 - (rank / 10),
                "projection_rank": overall,
            })
            overall += 1

    path = write_rankings(tmp_path, players)
    board = DraftBoardBuilder(path).build()

    assert board["metadata"]["role_counts"] == {
        "QB": 40, "RB": 110, "WR": 140, "TE": 40, "DST": 10, "K": 10,
    }
    assert sum(board["metadata"]["role_counts"].values()) == 350
    assert board["metadata"]["eligible_role_counts"] == {**available, "DST": 10, "K": 10}
    assert board["metadata"]["role_limit_exclusions"] == {
        "QB": 2, "RB": 28, "WR": 54, "TE": 40, "DST": 0, "K": 0,
    }
