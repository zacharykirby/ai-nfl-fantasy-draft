import json
from pathlib import Path

from fastapi.testclient import TestClient

from fantasy_draft.api.app import create_app


ROOT = Path(__file__).resolve().parents[1]


def make_client(web_draft, assistant_client_factory=None):
    app = create_app(
        sessions_dir=web_draft["sessions_dir"],
        board_path=web_draft["board_path"],
        frontend_dir=ROOT / "frontend",
        assistant_client_factory=assistant_client_factory,
    )
    return TestClient(app)


def test_health_board_and_frontend(web_draft):
    client = make_client(web_draft)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["board"]["status"] == "ready"
    assert health.json()["sessions"]["count"] == 1
    assert health.headers["cache-control"] == "no-store"
    assert "path" not in health.json()["board"]

    board = client.get("/api/v1/board/summary")
    assert board.status_code == 200
    assert board.json()["role_counts"] == {"RB": 3, "WR": 3, "QB": 3, "TE": 3}

    frontend = client.get("/")
    assert frontend.status_code == 200
    assert "Draft Cockpit" in frontend.text
    assert "Someone got Gibbs" in frontend.text
    assert "Undo last" in frontend.text
    assert "Catch up" in frontend.text
    assert "Who should I take here?" in frontend.text
    assert "assistant-cancel" in frontend.text
    assert "Choose or create a draft" in frontend.text
    assert "new-session-form" in frontend.text
    assert "Delete session" in frontend.text
    assert "sessions/.trash" in frontend.text
    assert "Tier-aware priorities" in frontend.text
    assert "Roster detail" in frontend.text
    assert "Complete pick log" in frontend.text
    assert "player-detail-dialog" in frontend.text
    assert 'id="current-team"' in frontend.text
    assert 'id="draft-primary"' in frontend.text
    assert 'id="player-search"' in frontend.text
    assert 'id="position-run"' in frontend.text
    assert 'id="health-autosave"' in frontend.text
    assert 'id="health-connectivity"' in frontend.text
    assert frontend.headers["x-frame-options"] == "DENY"


def test_session_reads_match_domain_state(web_draft):
    client = make_client(web_draft)

    sessions = client.get("/api/v1/sessions").json()["sessions"]
    assert sessions[0]["name"] == "phone-test"
    assert sessions[0]["current_pick"] == web_draft["session"].current_pick

    detail = client.get("/api/v1/sessions/phone-test")
    assert detail.status_code == 200
    assert detail.json()["summary"]["selections"] == 1
    assert "players" not in detail.json()["board"]

    cockpit = client.get("/api/v1/sessions/phone-test/cockpit")
    assert cockpit.status_code == 200
    assert cockpit.json()["session"]["current_pick"] == 2
    assert cockpit.json()["recent_picks"][0]["player"] == "Jahmyr Gibbs"


def test_create_list_and_resume_session_from_browser_contract(web_draft):
    client = make_client(web_draft)
    request = {
        "name": "sunday-league",
        "league_size": 4,
        "rounds": 2,
        "user_team": 3,
        "request_id": "api-create-session-0001",
    }

    created = client.post("/api/v1/sessions", json=request)
    assert created.status_code == 201
    assert created.json()["replayed"] is False
    assert created.json()["session"]["name"] == "sunday-league"
    assert created.json()["session"]["user_team"] == 3
    assert created.json()["cockpit"]["session"]["current_pick"] == 1

    replay = client.post("/api/v1/sessions", json=request)
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    sessions = client.get("/api/v1/sessions").json()["sessions"]
    assert sessions[0]["name"] == "sunday-league"
    assert sessions[0]["league_size"] == 4
    resumed = client.get("/api/v1/sessions/sunday-league/cockpit")
    assert resumed.status_code == 200
    assert resumed.json()["session"]["name"] == "sunday-league"

    duplicate = client.post(
        "/api/v1/sessions",
        json={**request, "request_id": "api-create-session-0002"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "session_exists"


def test_session_creation_rejects_invalid_name_depth_and_unready_board(web_draft, tmp_path):
    client = make_client(web_draft)
    base = {
        "league_size": 4,
        "rounds": 2,
        "user_team": 1,
        "request_id": "api-create-invalid-0001",
    }

    invalid_name = client.post(
        "/api/v1/sessions", json={**base, "name": "bad session name"}
    )
    assert invalid_name.status_code == 400
    assert invalid_name.json()["error"]["code"] == "invalid_session_name"

    too_deep = client.post(
        "/api/v1/sessions",
        json={**base, "name": "too-deep", "rounds": 4},
    )
    assert too_deep.status_code == 409
    assert not (web_draft["sessions_dir"] / "too-deep.json").exists()

    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    board["health"]["status"] = "not_ready"
    unready_path = tmp_path / "unready-board.json"
    unready_path.write_text(json.dumps(board), encoding="utf-8")
    unready_client = TestClient(
        create_app(
            sessions_dir=tmp_path / "unready-sessions",
            board_path=unready_path,
            frontend_dir=ROOT / "frontend",
        )
    )
    unready = unready_client.post(
        "/api/v1/sessions", json={**base, "name": "not-ready"}
    )
    assert unready.status_code == 409
    assert "not ready" in unready.json()["error"]["message"]


def test_delete_session_is_confirmable_recoverable_and_idempotent(web_draft):
    client = make_client(web_draft)

    deleted = client.request(
        "DELETE",
        "/api/v1/sessions/phone-test",
        json={"request_id": "api-delete-session-0001"},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {
        "name": "phone-test",
        "deleted": True,
        "recoverable": True,
        "replayed": False,
    }
    assert client.get("/api/v1/sessions").json()["sessions"] == []
    assert not web_draft["session"].path.exists()
    assert len(list((web_draft["sessions_dir"] / ".trash").glob("phone-test.*.json"))) == 1

    replay = client.request(
        "DELETE",
        "/api/v1/sessions/phone-test",
        json={"request_id": "api-delete-session-0001"},
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True

    missing = client.request(
        "DELETE",
        "/api/v1/sessions/missing",
        json={"request_id": "api-delete-session-0002"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "session_not_found"


def test_available_search_and_recommendation_routes(web_draft):
    client = make_client(web_draft)

    available = client.get("/api/v1/sessions/phone-test/available?position=RB&limit=2")
    assert available.status_code == 200
    assert [player["player"] for player in available.json()["players"]] == [
        "Bijan Robinson",
        "Saquon Barkley",
    ]

    search = client.get("/api/v1/sessions/phone-test/players/search?q=puka")
    assert search.status_code == 200
    assert search.json()["players"][0]["player"] == "Puka Nacua"

    recommendation = client.get(
        "/api/v1/sessions/phone-test/recommendation?mode=upside&alternatives=2"
    )
    assert recommendation.status_code == 200
    assert recommendation.json()["recommendation"]["mode"] == "upside"
    assert len(recommendation.json()["recommendation"]["alternatives"]) == 2


def test_full_board_roster_player_detail_and_log_routes(web_draft):
    client = make_client(web_draft)

    board = client.get("/api/v1/sessions/phone-test/board?position=RB")
    assert board.status_code == 200
    assert board.json()["positions"]["RB"]["count"] == 2
    assert board.json()["available_only"] is True

    all_board = client.get(
        "/api/v1/sessions/phone-test/board?position=RB&available_only=false"
    )
    assert all_board.status_code == 200
    assert all_board.json()["positions"]["RB"]["count"] == 3

    detail = client.get("/api/v1/sessions/phone-test/players/RB%3Ajahmyr%20gibbs")
    assert detail.status_code == 200
    assert detail.json()["player"]["available"] is False

    roster = client.get("/api/v1/sessions/phone-test/roster")
    assert roster.status_code == 200
    assert roster.json()["team"] == 2
    assert roster.json()["needs"]["QB"]["open_base_slots"] == 1

    log = client.get("/api/v1/sessions/phone-test/draft-log?team=1")
    assert log.status_code == 200
    assert log.json()["picks"][0]["player"] == "Jahmyr Gibbs"
    assert log.json()["filters"]["team"] == 1


def test_board_summary_reports_canonical_session_capacity(web_draft, tmp_path):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    board["roles"]["RB"].append(dict(board["roles"]["RB"][0]))
    duplicate_path = tmp_path / "duplicate-board.json"
    duplicate_path.write_text(json.dumps(board), encoding="utf-8")
    client = TestClient(
        create_app(
            sessions_dir=web_draft["sessions_dir"],
            board_path=duplicate_path,
            frontend_dir=ROOT / "frontend",
        )
    )

    summary = client.get("/api/v1/board/summary")
    assert summary.status_code == 200
    assert summary.json()["role_counts"]["RB"] == 3
    assert sum(summary.json()["role_counts"].values()) == 12


def test_text_command_requires_confirmation_then_records_pick(web_draft):
    client = make_client(web_draft)

    interpretation = client.post(
        "/api/v1/sessions/phone-test/commands/interpret",
        json={"text": "someone got Bijan"},
    )
    assert interpretation.status_code == 200
    assert interpretation.json()["intent"] == "record_pick"
    assert interpretation.json()["player"]["player"] == "Bijan Robinson"
    assert interpretation.json()["confirmation"]["overall_pick"] == 2
    assert web_draft["session"].current_pick == 2

    recorded = client.post(
        "/api/v1/sessions/phone-test/picks",
        json={"player": "Bijan Robinson", "request_id": "api-pick-0001"},
    )
    assert recorded.status_code == 200
    assert recorded.json()["event"]["player"] == "Bijan Robinson"
    assert recorded.json()["cockpit"]["session"]["current_pick"] == 3
    assert recorded.json()["replayed"] is False

    replay = client.post(
        "/api/v1/sessions/phone-test/picks",
        json={"player": "Bijan Robinson", "request_id": "api-pick-0001"},
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["cockpit"]["session"]["current_pick"] == 3


def test_pick_route_rejects_confirmation_after_draft_advances(web_draft):
    client = make_client(web_draft)
    client.post(
        "/api/v1/sessions/phone-test/picks",
        json={"player": "Bijan Robinson", "request_id": "api-pick-fresh-0001"},
    )

    stale = client.post(
        "/api/v1/sessions/phone-test/picks",
        json={
            "player": "Puka Nacua",
            "request_id": "api-pick-stale-0001",
            "expected_pick": 2,
        },
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_mutation"
    assert client.get("/api/v1/sessions/phone-test/cockpit").json()["session"]["current_pick"] == 3


def test_non_mutating_text_is_classified_as_question(web_draft):
    client = make_client(web_draft)

    response = client.post(
        "/api/v1/sessions/phone-test/commands/interpret",
        json={"text": "Who should I take?"},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "question"
    assert web_draft["session"].current_pick == 2


def test_read_only_assistant_route_uses_deterministic_fallback(web_draft):
    class OfflineClient:
        model = "offline/test"

        def __init__(self):
            self.calls = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return "Error: simulated offline model"

    client = OfflineClient()
    api = make_client(web_draft, assistant_client_factory=lambda: client)
    before = web_draft["session"].path.read_bytes()

    response = api.post(
        "/api/v1/sessions/phone-test/assistant/ask",
        json={"question": "Who should I take here?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]["source"] == "deterministic_fallback"
    assert payload["answer"]["recommendation"] == "Bijan Robinson"
    assert payload["freshness"]["stale"] is False
    assert payload["timeout_seconds"] == 12
    assert client.calls[0]["timeout"] == 12
    assert web_draft["session"].path.read_bytes() == before


def test_undo_route_returns_refreshed_cockpit(web_draft):
    client = make_client(web_draft)

    target = client.get("/api/v1/sessions/phone-test/cockpit").json()["recent_picks"][-1]
    response = client.post(
        "/api/v1/sessions/phone-test/undo",
        json={
            "request_id": "api-undo-0001",
            "target_event_id": target["event_id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["event"]["player"] == "Jahmyr Gibbs"
    assert response.json()["cockpit"]["session"]["current_pick"] == 1


def test_bulk_preview_and_atomic_commit(web_draft):
    client = make_client(web_draft)

    preview = client.post(
        "/api/v1/sessions/phone-test/picks/bulk/preview",
        json={"text": "Bijan, Chase picked; Bowers"},
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["start_pick"] == 2
    assert [pick["player"] for pick in payload["picks"]] == [
        "Bijan Robinson",
        "Ja'Marr Chase",
        "Brock Bowers",
    ]

    committed = client.post(
        "/api/v1/sessions/phone-test/picks/bulk",
        json={
            "players": [pick["player"] for pick in payload["picks"]],
            "expected_start_pick": payload["start_pick"],
            "request_id": "api-bulk-0001",
        },
    )
    assert committed.status_code == 200
    assert len(committed.json()["events"]) == 3
    assert committed.json()["cockpit"]["session"]["current_pick"] == 5

    replay = client.post(
        "/api/v1/sessions/phone-test/picks/bulk",
        json={
            "players": [pick["player"] for pick in payload["picks"]],
            "expected_start_pick": payload["start_pick"],
            "request_id": "api-bulk-0001",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["cockpit"]["session"]["current_pick"] == 5


def test_invalid_mutation_payload_uses_public_error_contract(web_draft):
    client = make_client(web_draft)

    response = client.post(
        "/api/v1/sessions/phone-test/picks",
        json={"player": "Bijan", "request_id": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_payload"
    assert response.json()["error"]["recoverable"] is True


def test_api_errors_are_structured_and_mutations_are_explicit(web_draft, tmp_path):
    client = make_client(web_draft)

    missing = client.get("/api/v1/sessions/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "session_not_found"

    invalid = client.get("/api/v1/sessions/bad.name")
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "invalid_session_name"

    invalid_mode = client.get("/api/v1/sessions/phone-test/cockpit?mode=chaos")
    assert invalid_mode.status_code == 400
    assert invalid_mode.json()["error"]["recoverable"] is True

    missing_board_client = TestClient(
        create_app(
            sessions_dir=web_draft["sessions_dir"],
            board_path=tmp_path / "missing-board.json",
            frontend_dir=ROOT / "frontend",
        )
    )
    missing_board = missing_board_client.get("/api/v1/board/summary")
    assert missing_board.status_code == 404
    assert missing_board.json()["error"]["code"] == "board_not_found"

    paths = client.get("/openapi.json").json()["paths"]
    post_paths = {path for path, methods in paths.items() if "post" in methods}
    assert post_paths == {
        "/api/v1/sessions",
        "/api/v1/sessions/{session_name}/assistant/ask",
        "/api/v1/sessions/{session_name}/commands/interpret",
        "/api/v1/sessions/{session_name}/picks",
        "/api/v1/sessions/{session_name}/picks/bulk",
        "/api/v1/sessions/{session_name}/picks/bulk/preview",
        "/api/v1/sessions/{session_name}/undo",
    }
    delete_paths = {path for path, methods in paths.items() if "delete" in methods}
    assert delete_paths == {"/api/v1/sessions/{session_name}"}
