from fantasy_draft.draft.session import DraftSession
from fantasy_draft.draft.views import DraftViewsService


def test_position_board_groups_tiers_and_defaults_to_available(web_draft):
    service = DraftViewsService(DraftSession.load(web_draft["session"].path))

    board = service.board(position="RB")

    assert board["available_only"] is True
    assert set(board["positions"]) == {"RB"}
    assert board["positions"]["RB"]["count"] == 2
    assert [
        player["player"]
        for tier in board["positions"]["RB"]["tiers"]
        for player in tier["players"]
    ] == ["Bijan Robinson", "Saquon Barkley"]


def test_player_detail_reports_evidence_and_draft_status(web_draft):
    service = DraftViewsService(DraftSession.load(web_draft["session"].path))

    detail = service.player_detail("RB:jahmyr gibbs")

    assert detail["player"]["player"] == "Jahmyr Gibbs"
    assert detail["player"]["available"] is False
    assert detail["player"]["drafted"] == {"overall_pick": 1, "round": 1, "team": 1}
    assert detail["player"]["evidence"] == {}


def test_roster_detail_contains_needs_and_bye_summary(web_draft):
    session = DraftSession.load(web_draft["session"].path)
    session.draft("Bijan")

    roster = DraftViewsService(DraftSession.load(session.path)).roster()

    assert roster["team"] == 2
    assert roster["players"][0]["player"] == "Bijan Robinson"
    assert roster["players"][0]["drafted_at"]["overall_pick"] == 2
    assert roster["needs"]["RB"]["open_base_slots"] == 1
    assert roster["needs"]["RB"]["flex_eligible"] is True
    assert roster["bye_summary"]["missing"] == ["Bijan Robinson"]


def test_complete_log_keeps_undone_picks_and_filters_team(web_draft):
    session = DraftSession.load(web_draft["session"].path)
    session.draft("Bijan")
    session.undo()
    session.draft("Chase")

    log = DraftViewsService(DraftSession.load(session.path)).draft_log(team=2)

    assert [(pick["player"], pick["status"]) for pick in log["picks"]] == [
        ("Bijan Robinson", "undone"),
        ("Ja'Marr Chase", "active"),
    ]
    assert {pick["overall_pick"] for pick in log["picks"]} == {2}
