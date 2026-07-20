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
    assert set(snapshot["top_available_by_position"]) == {"QB", "RB", "WR", "TE"}
    assert snapshot["health"]["autosave"] == "ok"
    assert "autosave_path" not in snapshot["health"]


def test_search_prioritizes_prefixes_and_only_returns_available_players(web_draft):
    service = DraftCockpitService(web_draft["session"])

    assert [player["player"] for player in service.search("bi")] == ["Bijan Robinson"]
    assert service.search("jahmyr") == []
    assert all(player["position"] == "WR" for player in service.search("a", position="WR"))


def test_available_rejects_unknown_position(web_draft):
    with pytest.raises(ValueError, match="position must be"):
        DraftCockpitService(web_draft["session"]).available("K")

