import pytest

from fantasy_draft.draft.cockpit import DraftCockpitService


def test_cockpit_snapshot_composes_domain_state(web_draft):
    snapshot = DraftCockpitService(web_draft["session"]).snapshot()

    assert snapshot["schema_version"] == "1.0"
    assert snapshot["session"]["current_pick"] == 2
    assert snapshot["session"]["current_team"] == 2
    assert snapshot["session"]["picks_until_user"] == 0
    assert snapshot["recent_picks"][0]["player"] == "Jahmyr Gibbs"
    assert snapshot["recommendation"]["primary"]["player"] != "Jahmyr Gibbs"
    assert set(snapshot["top_available_by_position"]) == {"QB", "RB", "WR", "TE", "DST", "K"}
    assert snapshot["health"]["autosave"] == "ok"
    assert "autosave_path" not in snapshot["health"]


def test_search_prioritizes_prefixes_and_only_returns_available_players(web_draft):
    service = DraftCockpitService(web_draft["session"])

    assert [player["player"] for player in service.search("bi")] == ["Bijan Robinson"]
    assert [player["player"] for player in service.search("NaCu")] == ["Puka Nacua"]
    assert [player["player"] for player in service.search("lam")][:2] == [
        "Lamar Jackson",
        "CeeDee Lamb",
    ]
    assert service.search("jahmyr") == []
    assert all(player["position"] == "WR" for player in service.search("a", position="WR"))


def test_search_result_count_is_bounded_by_requested_limit(web_draft):
    results = DraftCockpitService(web_draft["session"]).search("a", limit=3)

    assert len(results) <= 3


def test_available_rejects_unknown_position(web_draft):
    with pytest.raises(ValueError, match="position must be"):
        DraftCockpitService(web_draft["session"]).available("P")

