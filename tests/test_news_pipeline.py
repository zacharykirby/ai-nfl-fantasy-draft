import json
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import news_analyzer
import news_fetcher


def test_projection_roster_drives_headline_player_matching(tmp_path, monkeypatch):
    (tmp_path / "players_2026_positions_bye.csv").write_text(
        "name,position\nCam Skattebo,RB\nJames Cook III,RB\n",
        encoding="utf-8",
    )
    names = news_fetcher.load_current_player_names(tmp_path)
    monkeypatch.setattr(news_fetcher, "load_current_player_names", lambda: names)

    assert news_fetcher.extract_player_names("Cam Skattebo earns the starting job") == [
        "Cam Skattebo"
    ]
    assert news_fetcher.extract_player_names("James Cook breaks out at camp") == [
        "James Cook III"
    ]
    quality = news_fetcher.assess_headline_quality(
        "Cam Skattebo earns the starting RB job",
        "NFL training camp role update",
    )
    assert quality["is_high_quality"] is True
    assert quality["player_names"] == ["Cam Skattebo"]


def test_analysis_prompt_bounds_model_to_detected_players():
    prompt = news_analyzer.create_analysis_prompt(
        "Cam Skattebo earns the starting job",
        candidate_players=["Cam Skattebo"],
    )

    assert "Current fantasy players identified" in prompt
    assert "Cam Skattebo" in prompt
    assert "Do not invent a different player" in prompt


def test_multi_player_model_response_never_positionally_copies_events():
    normalized = news_analyzer.normalize_analysis_payload(
        [
            {
                "player": "Invented Player",
                "sentiment_score": 0.8,
                "buzz_score": 0.6,
                "injury_flag": False,
                "role_change": True,
                "topics": ["role"],
            },
            {
                "player": "Another Invention",
                "sentiment_score": -0.2,
                "buzz_score": 0.9,
                "injury_flag": True,
                "role_change": False,
                "topics": ["injury"],
            },
        ],
        ["Patrick Mahomes", "Josh Allen"],
    )

    assert [item["player"] for item in normalized] == ["Patrick Mahomes", "Josh Allen"]
    assert normalized[0]["sentiment_score"] == pytest.approx(0)
    assert normalized[0]["injury_flag"] is False
    assert normalized[1]["sentiment_score"] == pytest.approx(0)
    assert normalized[1]["injury_flag"] is False
    assert all(item["actionable"] is False for item in normalized)


def test_suffix_normalized_model_name_matches_candidate():
    normalized = news_analyzer.normalize_analysis_payload(
        {
            "analyses": [{
                "player": "Michael Penix",
                "event_type": "role_change",
                "event_direction": "positive",
                "actionable": True,
                "confidence": 0.9,
                "role_direction": "gained",
            }]
        },
        ["Michael Penix Jr."],
    )

    assert normalized[0]["player"] == "Michael Penix Jr."
    assert normalized[0]["role_direction"] == "gained"
    assert normalized[0]["actionable"] is True


def test_analyze_headlines_honors_limit_and_writes_features(tmp_path, monkeypatch):
    input_path = tmp_path / "headlines.json"
    output_path = tmp_path / "features.json"
    input_path.write_text(
        json.dumps(
            {
                "headlines": [
                    {
                        "title": f"Player {index}",
                        "summary": "",
                        "source": "test",
                        "published": "2026-08-05T00:00:00",
                        "player_names": [f"Player {index}"],
                    }
                    for index in range(3)
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        news_analyzer,
        "setup_llm_client",
        lambda: SimpleNamespace(model="test-model"),
    )
    monkeypatch.setattr(news_analyzer, "load_nfl_roster", lambda: set())
    monkeypatch.setattr(
        news_analyzer,
        "analyze_headline",
        lambda client, headline: [
            {
                "player": headline["player_names"][0],
                "original_headline": headline["title"],
                "source": headline["source"],
                "published": headline["published"],
                "sentiment_score": 0.5,
                "buzz_score": 0.7,
                "injury_flag": False,
                "role_change": True,
                "event_type": "role_change",
                "event_direction": "positive",
                "actionable": True,
                "confidence": 0.9,
                "role_direction": "gained",
                "source_quality": 1.0,
                "topics": ["depth chart"],
            }
        ],
    )

    result = news_analyzer.analyze_headlines(
        str(input_path),
        str(output_path),
        max_headlines=2,
    )

    assert result["metadata"]["source_headline_count"] == 3
    assert result["metadata"]["total_headlines_analyzed"] == 2
    assert len(result["player_features"]) == 2
    assert output_path.exists()


def test_newer_recovery_supersedes_older_injury():
    common = {
        "player": "Test Runner",
        "source": "test",
        "source_quality": 1.0,
        "link": "https://example.test/story",
        "sentiment_score": 0,
        "buzz_score": 0,
        "role_change": False,
        "topics": ["injury"],
    }
    injury = {
        **common,
        "original_headline": "Test Runner injured",
        "published": "2026-08-01T00:00:00",
        "event_type": "injury",
        "event_direction": "negative",
        "actionable": True,
        "confidence": 0.9,
        "injury_flag": True,
        "injury_status": "new",
    }
    recovery = {
        **common,
        "original_headline": "Test Runner cleared",
        "published": "2026-08-05T00:00:00",
        "event_type": "recovery",
        "event_direction": "positive",
        "actionable": True,
        "confidence": 0.9,
        "injury_flag": False,
        "injury_status": "cleared",
    }

    features = news_analyzer.aggregate_player_features([injury, recovery], set())["Test Runner"]

    assert features["has_injury"] is False
    assert len(features["actionable_events"]) == 1
    assert features["latest_actionable_event"]["event_type"] == "recovery"


def test_headline_dedupe_uses_canonical_url_and_same_player_overlap():
    base = {"player_names": ["Test Runner"]}
    assert news_fetcher.headlines_are_duplicate(
        {**base, "title": "Runner returns to full practice", "link": "https://example.test/a?utm=x"},
        {**base, "title": "Different wording", "link": "https://example.test/a"},
    )
    assert news_fetcher.headlines_are_duplicate(
        {**base, "title": "Test Runner returns to full practice", "link": ""},
        {**base, "title": "Runner returns to full practice", "link": ""},
    )
