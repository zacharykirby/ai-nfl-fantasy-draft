import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.draft.session import (
    AmbiguousPlayerError,
    DraftSession,
    DraftSessionError,
    PlayerNotFoundError,
    next_pick_for_team,
    required_board_capacity,
    snake_team_for_pick,
)


def player(name, position, position_rank, overall_rank):
    return {
        "player": name,
        "position": position,
        "team": "TST",
        "position_rank": position_rank,
        "overall_rank": overall_rank,
        "tier": 1,
        "projected_points": 200,
        "vorp": 40,
    }


def write_board(tmp_path, ready=True):
    board = {
        "schema_version": "1.0",
        "metadata": {"generated_at": "2026-07-10T00:00:00", "season": 2026},
        "league": {
            "scoring": "half_ppr",
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1},
            "bench_size": 6,
        },
        "health": {"status": "ready" if ready else "not_ready"},
        "roles": {
            "QB": [player("Josh Allen", "QB", 1, 12), player("Joe Burrow", "QB", 2, 20), player("Lamar Jackson", "QB", 3, 24)],
            "RB": [player("Jahmyr Gibbs", "RB", 1, 1), player("Josh Jacobs", "RB", 2, 8), player("Bijan Robinson", "RB", 3, 9)],
            "WR": [player("Ja'Marr Chase", "WR", 1, 2), player("Puka Nacua", "WR", 2, 3), player("CeeDee Lamb", "WR", 3, 4)],
            "TE": [player("Brock Bowers", "TE", 1, 15), player("Trey McBride", "TE", 2, 18), player("George Kittle", "TE", 3, 22)],
        },
    }
    path = tmp_path / "draft_board.json"
    path.write_text(json.dumps(board), encoding="utf-8")
    return path


def create_session(tmp_path, **overrides):
    values = {"name": "test", "league_size": 4, "rounds": 2, "user_team": 2}
    values.update(overrides)
    return DraftSession.create(
        tmp_path / "session.json",
        write_board(tmp_path),
        values["name"],
        values["league_size"],
        values["rounds"],
        values["user_team"],
    )


def test_snake_team_and_next_pick_calculation():
    assert [snake_team_for_pick(pick, 4) for pick in range(1, 9)] == [1, 2, 3, 4, 4, 3, 2, 1]
    assert next_pick_for_team(3, team=2, league_size=4, max_rounds=3) == 7


def test_unique_last_name_matches_player(tmp_path):
    session = create_session(tmp_path)

    assert session.match_player("Gibbs")["player"] == "Jahmyr Gibbs"
    assert next_pick_for_team(12, team=1, league_size=4, max_rounds=3) is None


def test_player_matching_ignores_common_name_suffixes(tmp_path):
    board_path = write_board(tmp_path)
    board = json.loads(board_path.read_text(encoding="utf-8"))
    board["roles"]["RB"][0]["player"] = "Kenneth Walker III"
    board_path.write_text(json.dumps(board), encoding="utf-8")
    session = DraftSession.create(tmp_path / "suffix.json", board_path, "suffix", 4, 2, 2)

    assert session.match_player("Ken Walker")["player"] == "Kenneth Walker III"


def test_create_snapshots_ready_board_and_persists(tmp_path):
    session = create_session(tmp_path)

    assert session.path.exists()
    assert session.current_pick == 1
    assert session.current_team == 1
    assert session.payload["board"]["player_count"] == 12
    assert session.summary()["next_user_pick"] == 2
    assert DraftSession.load(session.path).payload["session"]["id"] == session.payload["session"]["id"]


def test_not_ready_board_cannot_start_live_session(tmp_path):
    with pytest.raises(DraftSessionError, match="not ready"):
        DraftSession.create(
            tmp_path / "session.json", write_board(tmp_path, ready=False), "bad", 4, 2, 1
        )


def test_board_requires_meaningful_capacity_above_planned_picks(tmp_path):
    assert required_board_capacity(4, 2) == (12, 4)
    assert required_board_capacity(12, 20) == (264, 24)

    with pytest.raises(DraftSessionError, match="requires at least 16"):
        DraftSession.create(
            tmp_path / "session.json", write_board(tmp_path), "too-deep", 4, 3, 1
        )


def test_draft_updates_availability_roster_and_autosaves(tmp_path):
    session = create_session(tmp_path, user_team=1)

    event = session.draft("Jahmyr Gibbs")

    assert event["overall_pick"] == 1
    assert session.current_pick == 2
    assert "Jahmyr Gibbs" not in {item["player"] for item in session.available_players()}
    assert [item["player"] for item in session.roster(team=1)] == ["Jahmyr Gibbs"]
    assert DraftSession.load(session.path).current_pick == 2


def test_wrong_team_and_duplicate_player_are_rejected(tmp_path):
    session = create_session(tmp_path)

    with pytest.raises(DraftSessionError, match="belongs to team 1"):
        session.draft("Jahmyr Gibbs", team=2)
    session.draft("Jahmyr Gibbs")
    with pytest.raises(PlayerNotFoundError, match="No available player"):
        session.draft("Jahmyr Gibbs")


def test_undo_restores_player_pick_and_persists_event_history(tmp_path):
    session = create_session(tmp_path)
    session.draft("Jahmyr Gibbs")

    event = session.undo()

    assert event["player"] == "Jahmyr Gibbs"
    assert session.current_pick == 1
    assert "Jahmyr Gibbs" in {item["player"] for item in session.available_players()}
    assert [event["type"] for event in session.payload["events"]] == ["selection", "undo"]
    assert DraftSession.load(session.path).current_pick == 1


def test_fuzzy_matching_is_safe_and_position_can_disambiguate(tmp_path):
    session = create_session(tmp_path)

    with pytest.raises(AmbiguousPlayerError, match="Josh"):
        session.match_player("Josh")
    assert session.match_player("Josh", position="QB")["player"] == "Josh Allen"
    assert session.match_player("Jahmyr Gibs")["player"] == "Jahmyr Gibbs"
    with pytest.raises(PlayerNotFoundError):
        session.match_player("Completely Unknown")


def test_available_players_are_position_filtered_and_board_ordered(tmp_path):
    session = create_session(tmp_path)

    assert [item["player"] for item in session.available_players("WR")] == [
        "Ja'Marr Chase", "Puka Nacua", "CeeDee Lamb"
    ]


def test_complete_draft_and_undo_reopen_session(tmp_path):
    session = create_session(tmp_path, league_size=2, rounds=1, user_team=1)
    session.draft("Jahmyr Gibbs")
    session.draft("Ja'Marr Chase")

    assert session.current_team is None
    assert session.payload["session"]["status"] == "complete"
    session.undo()
    assert session.current_team == 2
    assert session.payload["session"]["status"] == "active"


def test_full_draft_simulation_survives_reload(tmp_path):
    session = create_session(tmp_path)
    names = [
        "Jahmyr Gibbs", "Ja'Marr Chase", "Puka Nacua", "Josh Jacobs",
        "Josh Allen", "Brock Bowers", "Trey McBride", "Joe Burrow",
    ]

    for name in names:
        session.draft(name)

    resumed = DraftSession.load(session.path)
    assert resumed.payload["session"]["status"] == "complete"
    assert resumed.current_pick == 9
    assert resumed.current_team is None
    assert len(resumed.available_players()) == 4
    assert [item["player"] for item in resumed.roster(team=2)] == ["Ja'Marr Chase", "Trey McBride"]


def test_corrupt_selection_gap_is_rejected_on_load(tmp_path):
    session = create_session(tmp_path)
    payload = session.payload
    payload["events"] = [
        {
            "id": "bad",
            "type": "selection",
            "overall_pick": 2,
            "player_id": payload["board"]["players"][0]["player_id"],
        }
    ]
    session.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DraftSessionError, match="pick gap"):
        DraftSession.load(session.path)
