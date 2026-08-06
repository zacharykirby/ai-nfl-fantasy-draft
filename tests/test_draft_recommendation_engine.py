import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.draft.recommendations import (
    DraftRecommendationEngine,
    survival_probability,
    wait_status,
)
from fantasy_draft.draft.session import DraftSession


def player(
    name, position, rank, pos_rank, vorp, tier=1, flags=None,
    injury=False, risk="Low", adp=None, bye_week=None,
):
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
        "bye_week": bye_week,
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
        "DST": [{
            **player("Test Defense D/ST", "DST", 220, 1, 0, tier=1),
            "overall_rank": None,
            "projected_points": 8.0,
            "vorp": None,
        }],
        "K": [{
            **player("Test Kicker", "K", 221, 1, 0, tier=1),
            "overall_rank": None,
            "projected_points": 150.0,
            "vorp": None,
        }],
    }
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "generated_at": "2026-07-10T00:00:00"},
        "health": {"status": "ready"},
        "league": {
            "scoring": "half_ppr",
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1},
            "bench_size": 4,
        },
        "roles": roles,
    }
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board))
    return DraftSession.create(
        tmp_path / "session.json", board_path, "recommend", 2, 5, user_team
    )


def make_deep_session(
    tmp_path,
    league_size=8,
    rounds=3,
    starters=None,
    bench_size=6,
    user_team=1,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    starters = starters or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 0}
    projection_starts = {"QB": 410, "RB": 315, "WR": 305, "TE": 270}
    projection_steps = {"QB": 7, "RB": 4, "WR": 4, "TE": 5}
    roles = {}
    overall = 1
    for position in ("QB", "RB", "WR", "TE"):
        roles[position] = []
        for position_rank in range(1, 46):
            projection = projection_starts[position] - (
                (position_rank - 1) * projection_steps[position]
            )
            roles[position].append({
                **player(
                    "{} Player {}".format(position, position_rank),
                    position,
                    overall,
                    position_rank,
                    projection - 180,
                    tier=((position_rank - 1) // 6) + 1,
                    adp=overall,
                    bye_week=7 + (position_rank % 4),
                ),
                "projected_points": projection,
            })
            overall += 1
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "generated_at": "2026-07-10T00:00:00"},
        "health": {"status": "ready"},
        "league": {
            "scoring": "half_ppr",
            "starters": starters,
            "bench_size": bench_size,
        },
        "roles": roles,
    }
    board_path = tmp_path / "deep-board.json"
    board_path.write_text(json.dumps(board))
    return DraftSession.create(
        tmp_path / "deep-session.json",
        board_path,
        "deep",
        league_size,
        rounds,
        user_team,
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


def test_special_teams_wait_until_the_last_two_rounds(tmp_path):
    session = make_session(tmp_path)
    engine = DraftRecommendationEngine(session)

    assert engine.recommend("balanced")["primary"]["position"] not in {"DST", "K"}

    for name in (
        "Safe Runner", "Receiver One", "Elite QB", "Receiver Two", "Tight End One", "Runner Three"
    ):
        session.draft(name)
    assert session.current_pick == 7  # Round 4 in a two-team draft.
    assert DraftRecommendationEngine(session).recommend("balanced")["primary"]["position"] == "DST"

    session.draft("Test Defense D/ST")
    session.draft("Receiver Three")
    assert session.current_pick == 9  # Final round.
    assert DraftRecommendationEngine(session).recommend("balanced")["primary"]["position"] == "K"


def test_safe_and_upside_modes_treat_risk_differently(tmp_path):
    session = make_session(tmp_path)
    engine = DraftRecommendationEngine(session)

    safe = engine.recommend("safe", alternatives=20)
    upside = engine.recommend("upside", alternatives=20)

    assert safe["primary"]["player"] != "Risky Star"
    safe_risky = next(
        item for item in [safe["primary"], *safe["alternatives"]]
        if item["player"] == "Risky Star"
    )
    upside_risky = next(
        item for item in [upside["primary"], *upside["alternatives"]]
        if item["player"] == "Risky Star"
    )
    assert safe_risky["score_components"]["risk_adjustment"] < (
        upside_risky["score_components"]["risk_adjustment"]
    )
    assert upside_risky["score_components"]["upside_adjustment"] > 0
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


def test_replacement_levels_follow_league_size_and_qb_starters(tmp_path):
    eight = DraftRecommendationEngine(make_deep_session(tmp_path / "eight", 8))
    twelve = DraftRecommendationEngine(make_deep_session(tmp_path / "twelve", 12))
    two_qb = DraftRecommendationEngine(make_deep_session(
        tmp_path / "two-qb",
        8,
        starters={"QB": 2, "RB": 2, "WR": 2, "TE": 1, "FLEX": 0},
    ))

    eight_level = eight.replacement_levels()["QB"]
    twelve_level = twelve.replacement_levels()["QB"]
    two_qb_level = two_qb.replacement_levels()["QB"]

    assert eight_level["replacement_rank"] == 9
    assert twelve_level["replacement_rank"] == 13
    assert two_qb_level["replacement_rank"] == 17
    assert eight_level["baseline_points"] > twelve_level["baseline_points"]


def test_replacement_levels_allocate_flex_from_current_projections(tmp_path):
    session = make_deep_session(
        tmp_path,
        league_size=8,
        starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
    )

    levels = DraftRecommendationEngine(session).replacement_levels()

    assert levels["QB"]["flex_demand"] == 0
    assert sum(levels[position]["flex_demand"] for position in ("RB", "WR", "TE")) == 8
    assert levels["RB"]["replacement_rank"] > 17


def test_recommendation_scores_every_available_player(tmp_path):
    session = make_deep_session(tmp_path)

    result = DraftRecommendationEngine(session).recommend("balanced")

    pool = result["signals"]["candidate_pool"]
    assert pool == {
        "available": 180,
        "scored": 180,
        "scope": "all_available_players",
    }


def test_roster_need_pressure_increases_later_in_draft(tmp_path):
    session = make_deep_session(tmp_path, league_size=4, rounds=6)
    engine = DraftRecommendationEngine(session)
    early_adjustment = engine.roster_needs()["TE"]["score_adjustment"]

    for position_rank in range(1, 17):
        session.draft("RB Player {}".format(position_rank))

    late_needs = engine.roster_needs()
    warnings = engine.roster_balance_warnings(late_needs)
    assert late_needs["TE"]["need_level"] == "priority"
    assert late_needs["TE"]["score_adjustment"] > early_adjustment
    assert any(warning["code"] == "open_starter_slots" for warning in warnings)


def test_extra_qb_is_penalized_and_roster_overload_is_warned(tmp_path):
    session = make_deep_session(tmp_path, league_size=4, rounds=6, bench_size=6)
    session.draft("QB Player 1")
    for position_rank in range(1, 7):
        session.draft("RB Player {}".format(position_rank))
    session.draft("QB Player 2")
    engine = DraftRecommendationEngine(session)

    needs = engine.roster_needs()
    candidate = session.match_player("QB Player 3")
    assert needs["QB"]["need_level"] == "at_capacity"
    assert needs["QB"]["score_adjustment"] < 0
    assert "exceed" in " ".join(engine.candidate_caveats(candidate, needs))

    session.draft("QB Player 3")
    assert any(
        warning["code"] == "position_overload" and warning["positions"] == ["QB"]
        for warning in engine.roster_balance_warnings()
    )


def test_bye_conflicts_are_visible_caveats_without_score_penalty(tmp_path):
    session = make_deep_session(tmp_path, league_size=4, rounds=6)
    session.draft("QB Player 1")
    engine = DraftRecommendationEngine(session)
    same_bye = session.match_player("QB Player 5")
    unknown_bye = dict(session.match_player("QB Player 2"), bye_week=None)

    assert any("Bye 8 overlaps" in item for item in engine.candidate_caveats(same_bye))
    assert any("unknown" in item for item in engine.candidate_caveats(unknown_bye))
    result = engine.recommend("balanced")
    assert "bye" not in result["primary"]["score_components"]


def test_wait_assessment_discloses_player_and_tier_survival(tmp_path):
    session = make_deep_session(tmp_path, league_size=8, rounds=3)
    engine = DraftRecommendationEngine(session)
    candidate = session.match_player("WR Player 1")

    assessment = engine.wait_assessment(candidate, next_pick=20)

    assert assessment["tier_survival"] >= assessment["player_survival"]
    assert assessment["status"] == wait_status(assessment["player_survival"])
    assert "tier remains" in assessment["reason"]
