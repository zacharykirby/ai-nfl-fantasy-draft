import sys
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from draft_recommender import DraftRecommender


def sample_board():
    return pd.DataFrame(
        [
            {"name": "Jahmyr Gibbs", "position": "RB", "team": "DET", "projection_rank": 1, "projection_tier": 1, "projected_fantasy_points": 300, "vorp_score": 70, "bye_week": "6"},
            {"name": "Bijan Robinson", "position": "RB", "team": "ATL", "projection_rank": 2, "projection_tier": 1, "projected_fantasy_points": 290, "vorp_score": 65, "bye_week": "11"},
            {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN", "projection_rank": 3, "projection_tier": 1, "projected_fantasy_points": 215, "vorp_score": 36, "bye_week": "6"},
            {"name": "Puka Nacua", "position": "WR", "team": "LAR", "projection_rank": 4, "projection_tier": 1, "projected_fantasy_points": 233, "vorp_score": 15, "bye_week": "11"},
            {"name": "Jaxon Smith-Njigba", "position": "WR", "team": "SEA", "projection_rank": 5, "projection_tier": 1, "projected_fantasy_points": 213, "vorp_score": 27, "bye_week": "11"},
            {"name": "Jonathan Taylor", "position": "RB", "team": "IND", "projection_rank": 6, "projection_tier": 1, "projected_fantasy_points": 266, "vorp_score": 58, "bye_week": "13"},
            {"name": "Christian McCaffrey", "position": "RB", "team": "SF", "projection_rank": 7, "projection_tier": 1, "projected_fantasy_points": 263, "vorp_score": 58, "bye_week": "8"},
            {"name": "Brock Bowers", "position": "TE", "team": "LV", "projection_rank": 22, "projection_tier": 1, "projected_fantasy_points": 147, "vorp_score": 26, "bye_week": "13"},
            {"name": "Josh Allen", "position": "QB", "team": "BUF", "projection_rank": 28, "projection_tier": 2, "projected_fantasy_points": 372, "vorp_score": 46, "bye_week": "7"},
        ]
    )


def recommender():
    return DraftRecommender(allow_stale_rankings=True)


def test_pick_pool_excludes_players_projected_gone_before_pick():
    rec = recommender()
    board = rec.prepare_draft_board(sample_board())

    likely = rec._top_candidates(board, overall_pick=5, league_size=8, selected_names=set(), pool="likely")

    assert "Jahmyr Gibbs" not in set(likely["name"])
    assert "Bijan Robinson" not in set(likely["name"])
    assert "Puka Nacua" in set(likely["name"])


def test_position_candidate_starts_near_current_pick():
    rec = recommender()
    board = rec.prepare_draft_board(sample_board())

    rb = rec._candidate_for_position(board, "RB", overall_pick=5, league_size=8, selected_names=set())

    assert rb["name"] == "Jonathan Taylor"


def test_local_plan_does_not_make_rank_one_player_pick_five_primary():
    rec = recommender()
    board = rec.prepare_draft_board(sample_board())

    plan = rec.generate_local_draft_plan(board, pick_position=5, league_size=8, rounds=1)

    first_primary = next(line for line in plan.splitlines() if line.startswith("Primary Target:"))
    assert "Jahmyr Gibbs" not in first_primary
    assert "Likely available board:" in plan
    assert "Possible fallers" in plan


def test_snake_picks_are_overall_pick_numbers():
    rec = recommender()

    assert rec._calculate_snake_picks(pick_position=5, league_size=8, rounds=4) == [5, 12, 21, 28]


def test_stale_rankings_are_rejected_without_override(tmp_path):
    rankings_dir = tmp_path / "outputs"
    rankings_dir.mkdir()
    (rankings_dir / "player_rankings.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "generated_at": "2025-01-01T00:00:00",
                    "target_season": 2025,
                    "projection_source": "data/players_2025_positions_bye.csv",
                },
                "rankings": [
                    {
                        "name": "Test Player",
                        "pos": "RB",
                        "team": "TST",
                        "score": 1,
                        "VORP": 1,
                        "projected_fantasy_points": 1,
                    }
                ],
            }
        )
    )
    rec = DraftRecommender(allow_stale_rankings=False)
    rec.rankings_dir = rankings_dir

    with pytest.raises(ValueError, match="looks stale"):
        rec.load_ranking_data()


def test_stale_rankings_can_be_loaded_with_override(tmp_path):
    rankings_dir = tmp_path / "outputs"
    rankings_dir.mkdir()
    (rankings_dir / "player_rankings.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "generated_at": "2025-01-01T00:00:00",
                    "target_season": 2025,
                    "projection_source": "data/players_2025_positions_bye.csv",
                },
                "rankings": [
                    {
                        "name": "Test Player",
                        "pos": "RB",
                        "team": "TST",
                        "score": 1,
                        "VORP": 1,
                        "projected_fantasy_points": 1,
                    }
                ],
            }
        )
    )
    rec = DraftRecommender(allow_stale_rankings=True)
    rec.rankings_dir = rankings_dir

    df = rec.load_ranking_data()

    assert df.iloc[0]["name"] == "Test Player"
