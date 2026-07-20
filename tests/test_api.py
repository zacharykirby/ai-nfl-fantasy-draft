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


def test_api_errors_are_structured_and_api_is_read_only(web_draft, tmp_path):
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

    methods = {
        method
        for path in client.get("/openapi.json").json()["paths"].values()
        for method in path
    }
    assert methods == {"get"}
