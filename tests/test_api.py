from pathlib import Path

from fastapi.testclient import TestClient

from fantasy_draft.api.app import create_app


ROOT = Path(__file__).resolve().parents[1]


def make_client(web_draft):
    app = create_app(
        sessions_dir=web_draft["sessions_dir"],
        board_path=web_draft["board_path"],
        frontend_dir=ROOT / "frontend",
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


def test_non_mutating_text_is_classified_as_question(web_draft):
    client = make_client(web_draft)

    response = client.post(
        "/api/v1/sessions/phone-test/commands/interpret",
        json={"text": "Who should I take?"},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "question"
    assert web_draft["session"].current_pick == 2


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
        "/api/v1/sessions/{session_name}/commands/interpret",
        "/api/v1/sessions/{session_name}/picks",
        "/api/v1/sessions/{session_name}/picks/bulk",
        "/api/v1/sessions/{session_name}/picks/bulk/preview",
        "/api/v1/sessions/{session_name}/undo",
    }
