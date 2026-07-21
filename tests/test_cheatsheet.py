import json

from fantasy_draft.board.cheatsheet import render_cheatsheet, write_cheatsheet


def test_emergency_cheatsheet_contains_board_health_tiers_and_recovery(web_draft, tmp_path):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    text = render_cheatsheet(board, {"status": "ready", "issues": []})

    assert text.startswith("# Emergency Fantasy Draft Cheatsheet")
    assert "Status: **READY**" in text
    assert "## Overall Priorities by VORP" in text
    assert "## RB Tiers" in text
    assert "Jahmyr Gibbs" in text
    assert "Static fallback only" in text
    assert "scripts/draft-night-server start" in text
    assert "scripts/live_draft.py interactive <session-name>" in text

    output = write_cheatsheet(
        board,
        tmp_path / "nested" / "cheatsheet.md",
        {"status": "ready", "issues": []},
    )
    assert output.read_text(encoding="utf-8") == text


def test_emergency_cheatsheet_surfaces_health_errors(web_draft):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    health = {
        "status": "not_ready",
        "issues": [
            {
                "severity": "error",
                "code": "projection_data_stale",
                "message": "Projection data is stale",
            }
        ],
    }

    text = render_cheatsheet(board, health)
    assert "Status: **NOT_READY**" in text
    assert "ERROR — projection_data_stale" in text
    assert "Projection data is stale" in text
