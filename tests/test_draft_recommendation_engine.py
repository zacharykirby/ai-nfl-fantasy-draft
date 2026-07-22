import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.draft.recommendations import DraftRecommendationEngine, survival_probability
from fantasy_draft.draft.session import DraftSession


def player(name, position, rank, pos_rank, vorp, tier=1, flags=None, injury=False, risk="Low", adp=None):
    return {
        "player": name,
        "position": position,
        "team": "TST",
        "overall_rank": rank,
        "position_rank": pos_rank,
        "tier": tier,
        "projected_points": 250 - rank,
        "vorp": vorp,
        "adp": adp if adp is not None else rank,
        "projection_method": "published",
        "flags": flags or [],
        "risk": {"injury_flag": injury, "level": risk},
    }


def make_session(tmp_path, user_team=1):
    roles = {
        "QB": [
            player("Elite QB", "QB", 8, 1, 45, flags=["High Projection"]),
            player("Value QB", "QB", 25, 2, 20, tier=2),
        ],
        "RB": [
            player("Risky Star", "RB", 1, 1, 80, flags=["High Upside", "Elite Tier"], injury=True, risk="High"),
            player("Safe Runner", "RB", 3, 2, 65, flags=["High Projection"]),
            player("Runner Three", "RB", 10, 3, 35, tier=2),
        ],
        "WR": [
            player("Receiver One", "WR", 2, 1, 60),
            player("Receiver Two", "WR", 4, 2, 50),
            player("Receiver Three", "WR", 6, 3, 40, tier=2),
            player("Receiver Four", "WR", 12, 4, 30, tier=2),
        ],
        "TE": [
            player("Tight End One", "TE", 15, 1, 35),
            player("Tight End Two", "TE", 35, 2, 10, tier=2),
            player("Tight End Reserve", "TE", 99, 3, -20, tier=3),
        ],
    }
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "generated_at": "2026-07-10T00:00:00"},
        "health": {"status": "ready"},
        "league": {
            "scoring": "half_ppr",
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
            "bench_size": 4,
        },
        "roles": roles,
    }
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board))
    return DraftSession.create(
        tmp_path / "session.json", board_path, "recommend", 2, 5, user_team
    )


def test_survival_probability_tracks_adp_relative_to_next_pick():
    assert survival_probability(5, next_pick=20) < 0.1
    assert survival_probability(35, next_pick=20) > 0.9
    assert survival_probability(None, next_pick=20) is None


def test_recommendation_has_auditable_contract_and_signals(tmp_path):
    session = make_session(tmp_path)

    result = DraftRecommendationEngine(session).recommend("balanced", alternatives=3)

    assert result["schema_version"] == "1.0"
    assert result["primary"]["player"]
    assert len(result["alternatives"]) == 3
    assert "bye_week" in result["primary"]
    assert result["primary"]["score_components"]
    assert result["primary"]["reasons"]
    assert result["signals"]["roster_needs"]["RB"]["needed"] is True
    assert result["generated_for"]["is_user_pick"] is True


def test_safe_and_upside_modes_treat_risk_differently(tmp_path):
    session = make_session(tmp_path)
    engine = DraftRecommendationEngine(session)

    safe = engine.recommend("safe")
    upside = engine.recommend("upside")

    assert safe["primary"]["player"] != "Risky Star"
    assert upside["primary"]["player"] == "Risky Star"
    assert safe["mode"] == "safe"
    assert upside["mode"] == "upside"


def test_tier_state_flags_last_players_before_drop(tmp_path):
    session = make_session(tmp_path)
    session.draft("Risky Star")
    session.draft("Receiver One")
    engine = DraftRecommendationEngine(session)

    tiers = engine.tier_state()

    assert tiers["RB"]["best_tier"] == 1
    assert tiers["RB"]["remaining_in_best_tier"] == 1
    assert tiers["RB"]["tier_drop_imminent"] is True


def test_position_run_uses_recent_selection_window(tmp_path):
    session = make_session(tmp_path)
    session.draft("Receiver One")
    session.draft("Receiver Two")
    session.draft("Receiver Three")

    run = DraftRecommendationEngine(session).position_run(window=6, threshold=3)

    assert run["active"] is True
    assert run["positions"] == ["WR"]
    assert run["counts"]["WR"] == 3


def test_roster_needs_update_after_user_selection(tmp_path):
    session = make_session(tmp_path, user_team=1)
    session.draft("Safe Runner")
    session.draft("Receiver One")
    engine = DraftRecommendationEngine(session)

    needs = engine.roster_needs()

    assert needs["RB"]["rostered"] == 1
    assert needs["RB"]["open_base_slots"] == 1
    assert needs["WR"]["rostered"] == 0


def test_invalid_mode_and_complete_draft_are_rejected(tmp_path):
    engine = DraftRecommendationEngine(make_session(tmp_path))
    with pytest.raises(ValueError, match="mode"):
        engine.recommend("reckless")
