import json

import pytest

from fantasy_draft.assistant.strategy import (
    DraftStrategyContextBuilder,
    DraftStrategyService,
    StrategyResponseError,
    validate_strategy_response,
)
from fantasy_draft.draft.session import DraftSession


def valid_response(primary="Bijan Robinson"):
    return {
        "summary": "Running back is the strongest value and the tier is thinning.",
        "strategy": "take_primary_if_available",
        "primary_player": primary,
        "fallback_players": ["Ja'Marr Chase"],
        "position_priority": ["RB", "WR", "QB"],
        "wait_positions": ["TE"],
        "cautions": ["Do not chase a position after its tier ends."],
        "confidence": 0.81,
    }


def test_strategy_context_is_bounded_and_includes_team_needs(web_draft):
    context = DraftStrategyContextBuilder(web_draft["session"]).build()

    assert len(context["team_roster_construction"]) == 4
    assert all(set(team["counts"]) == {"QB", "RB", "WR", "TE"} for team in context["team_roster_construction"])
    assert context["intervening_before_following_pick"]["teams"]
    assert all("needs" in team for team in context["intervening_before_following_pick"]["teams"])
    assert context["top_available_by_position"]["QB"]
    assert context["deterministic_recommendation"]["primary"]
    assert "tier_state" in context and "position_run" in context
    assert len(context["candidate_pool"]) < len(web_draft["session"].payload["board"]["players"])


def test_strategy_validation_accepts_valid_and_rejects_bad_values():
    allowed = {"Bijan Robinson", "Ja'Marr Chase"}
    assert validate_strategy_response(valid_response(), allowed)["confidence"] == 0.81

    mutations = [
        ("primary_player", "Unavailable Player"),
        ("strategy", "invented"),
        ("position_priority", ["DST"]),
        ("fallback_players", ["Ja'Marr Chase", "Ja'Marr Chase"]),
        ("confidence", 1.1),
    ]
    for field, value in mutations:
        payload = valid_response()
        payload[field] = value
        with pytest.raises(StrategyResponseError):
            validate_strategy_response(payload, allowed)

    malformed = valid_response()
    malformed["unexpected"] = True
    with pytest.raises(StrategyResponseError):
        validate_strategy_response(malformed, allowed)


def test_strategy_service_returns_model_result_without_mutating(web_draft):
    class Client:
        model = "google/gemini-test"

        def chat(self, **kwargs):
            assert kwargs["timeout"] == 5
            return json.dumps(valid_response())

    path = web_draft["session"].path
    before = path.read_bytes()
    result = DraftStrategyService(path, Client()).assess(generated_for_pick=2)

    assert result["source"] == "model"
    assert result["freshness"]["stale"] is False
    assert path.read_bytes() == before


def test_strategy_service_returns_local_fallback(web_draft):
    class OfflineClient:
        model = "offline/test"

        def chat(self, **kwargs):
            return "Error: offline"

    result = DraftStrategyService(web_draft["session"].path, OfflineClient()).assess()
    assert result["source"] == "deterministic_fallback"
    assert result["assessment"]["primary_player"] == "Bijan Robinson"


def test_strategy_marks_changed_session_and_drafted_primary_stale(web_draft):
    path = web_draft["session"].path

    class AdvancingClient:
        model = "google/gemini-test"

        def chat(self, **kwargs):
            latest = DraftSession.load(path)
            latest.draft("Bijan Robinson")
            return json.dumps(valid_response())

    result = DraftStrategyService(path, AdvancingClient()).assess()
    assert result["freshness"]["stale"] is True
    assert result["freshness"]["primary_available"] is False


def test_strategy_frontend_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    script = (root / "frontend" / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'id="strategy-card"' in html
    assert 'id="analyze-strategy"' in html
    assert "AUTO_STRATEGY_THRESHOLD = 2" in script
    assert "result.freshness.stale" in script
    assert "render(cockpit)" in script
