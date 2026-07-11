import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ranker import PlayerRanker


def sample_player_row(**overrides):
    data = {
        "name": "Test Runner",
        "position": "QB",
        "team": "BUF",
        "age": 27,
        "projected_fantasy_points": 400,
        "projection_tier": 1,
        "projection_rank": 8,
        "historical_consistency_score": 75,
        "points_2024": 300,
        "points_2023": 200,
        "games_played": 16,
        "carries": 80,
        "targets": 0,
        "receptions": 0,
    }
    data.update(overrides)
    return pd.Series(data)


def test_build_score_features_uses_explicit_weighted_components():
    ranker = PlayerRanker()
    features = ranker.build_score_features(sample_player_row())

    assert features == pytest.approx(
        {
            "projected_points_component": 157.0,
            "historical_points_component": 65.0,
            "consistency_component": 11.25,
            "usage_component": 1.0,
            "team_offense_component": 10.0,
            "projection_tier_component": 15.0,
            "projection_rank_component": 10.0,
            "news_component": 0.0,
        }
    )
    assert ranker.calculate_raw_score(sample_player_row()) == pytest.approx(sum(features.values()))


def test_build_historical_features_weights_recent_seasons():
    ranker = PlayerRanker()
    history = pd.DataFrame(
        [
            {
                "player_name": "Test Runner",
                "season": 2024,
                "fantasy_points_ppr": 200,
                "consistency_score": 3.0,
            },
            {
                "player_name": "Test Runner",
                "season": 2023,
                "fantasy_points_ppr": 100,
                "consistency_score": 2.0,
            },
            {
                "player_name": "Old Season",
                "season": 2022,
                "fantasy_points_ppr": 999,
                "consistency_score": 5.0,
            },
        ]
    )

    features = ranker.build_historical_features(history)
    player = features[features["player_name"] == "Test Runner"].iloc[0]

    assert player["weighted_historical_points"] == pytest.approx(160)
    assert player["historical_consistency_score"] == pytest.approx(52)
    assert player["historical_seasons_count"] == 2
    assert player["points_2024"] == 200
    assert player["points_2023"] == 100


def test_score_prefers_real_historical_features_over_legacy_points():
    ranker = PlayerRanker()
    row = sample_player_row(
        weighted_historical_points=160,
        points_2024=999,
        points_2023=999,
    )

    assert ranker.calculate_weighted_historical_average(row) == 160


def test_news_adjustment_is_small_and_capped():
    ranker = PlayerRanker()

    positive = sample_player_row(
        news_sentiment_score=0.8,
        news_buzz_score=0.9,
        news_headline_count=3,
        news_role_change_flag=True,
    )
    injured = sample_player_row(
        news_sentiment_score=-0.6,
        news_buzz_score=0.7,
        news_headline_count=2,
        news_injury_flag=True,
    )

    assert ranker.calculate_news_adjustment(positive) == pytest.approx(6.0)
    assert ranker.calculate_news_adjustment(injured) == pytest.approx(-15.0)


def test_merge_news_features_normalizes_analyzer_output(tmp_path):
    news_dir = tmp_path / "news"
    news_dir.mkdir()
    (news_dir / "player_features.json").write_text(
        json.dumps(
            {
                "player_features": {
                    "Test Runner": {
                        "player": "Test Runner",
                        "avg_sentiment": 0.5,
                        "avg_buzz": 0.4,
                        "headline_count": 2,
                        "has_injury": False,
                        "has_role_change": True,
                        "all_topics": ["depth chart"],
                    }
                }
            }
        )
    )
    ranker = PlayerRanker(news_dir=news_dir)
    df = pd.DataFrame([{"name": "Test Runner"}, {"name": "No News"}])

    merged = ranker.merge_news_features(df)

    player = merged[merged["name"] == "Test Runner"].iloc[0]
    no_news = merged[merged["name"] == "No News"].iloc[0]
    assert player["news_sentiment_score"] == pytest.approx(0.5)
    assert player["news_buzz_score"] == pytest.approx(0.4)
    assert player["news_headline_count"] == 2
    assert player["news_role_change_flag"] is True or player["news_role_change_flag"] == True
    assert player["news_topics"] == ["depth chart"]
    assert no_news["news_headline_count"] == 0


def test_add_score_features_persists_components_and_raw_score():
    ranker = PlayerRanker()
    df = pd.DataFrame([sample_player_row(), sample_player_row(name="Test Receiver", position="WR", team="CAR")])

    scored = ranker.add_score_features(df)

    for column in ranker.score_feature_columns:
        assert column in scored.columns
    assert "raw_score" in scored.columns
    assert scored.loc[0, "raw_score"] == pytest.approx(
        scored.loc[0, ranker.score_feature_columns].sum()
    )


def test_export_rankings_includes_score_breakdown(tmp_path):
    ranker = PlayerRanker(outputs_dir=tmp_path)
    row = sample_player_row()
    scored = ranker.add_score_features(pd.DataFrame([row]))
    scored["adjusted_score"] = scored["raw_score"]
    scored["VORP"] = 12.5
    scored["tier"] = "Tier 1"
    scored["flags"] = [["High Projection"]]
    scored["BYE WEEK"] = "7"

    ranker.export_rankings(scored)

    payload = json.loads((tmp_path / "player_rankings.json").read_text())
    player = payload["rankings"][0]
    assert set(player["score_breakdown"]) == set(ranker.score_feature_columns)
    assert sum(player["score_breakdown"].values()) == pytest.approx(player["raw_score"], abs=0.02)
    assert "news_component" in player["score_breakdown"]
    assert "news_headline_count" in player
    assert "projection_method" in player
    assert "projection_data_source" in player


def test_vorp_baseline_uses_replacement_range_average():
    ranker = PlayerRanker()
    df = pd.DataFrame(
        {
            "position": ["QB"] * 14,
            "adjusted_score": list(range(140, 0, -10)),
        }
    )

    baseline = ranker.calculate_vorp_baseline(df, "QB")

    assert baseline == pytest.approx(30.0)


def test_projection_team_is_preferred_over_historical_team(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        [
            {
                "player_name": "Current Player",
                "season": 2025,
                "position": "WR",
                "team": "OLD",
                "fantasy_points": 100,
                "fantasy_points_ppr": 120,
                "games": 17,
                "consistency_score": 1,
            }
        ]
    ).to_csv(data_dir / "nfl_player_data.csv", index=False)
    pd.DataFrame(
        [
            {
                "name": "Current Player",
                "position": "WR",
                "team": "NEW",
                "bye_week": 7,
                "projected_fantasy_points": 200,
                "tier": 1,
                "rank": 10,
            }
        ]
    ).to_csv(data_dir / "players_2026_positions_bye.csv", index=False)

    loaded = PlayerRanker(data_dir=data_dir, target_season=2026).load_data()

    assert loaded.iloc[0]["team"] == "NEW"
