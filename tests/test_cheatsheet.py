import json

from fantasy_draft.board import board_fingerprint
from fantasy_draft.board.cheatsheet import position_limits, render_cheatsheet, write_cheatsheet


def test_emergency_cheatsheet_contains_board_health_tiers_and_recovery(web_draft, tmp_path):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    board["roles"]["RB"][0]["flags"] = ["Availability Risk"]
    text = render_cheatsheet(board, {"status": "ready", "issues": []})

    assert text.startswith("---\naliases:")
    assert "# Fantasy Draft Cheat Sheet" in text
    assert "tags:\n  - fantasy-football\n  - draft\n  - cheat-sheet" in text
    assert f"league_size: {board['league']['league_size']}" in text
    assert "> [!tip] Draft workflow" in text
    assert "## Draft status" in text
    assert "### My roster" in text
    assert "> [!warning] League tendencies" in text
    assert "> [!tip] On the clock" in text
    assert "Do not draft from positional need alone" in text
    assert "## QB room tracker" in text
    assert "**Teams with QB:** 0 / 4" in text
    assert "## Roster checkpoints" in text
    assert "> [!danger] Draft-night traps" in text
    assert "🔥 Priority target" in text
    assert "[[#Running Backs (RB)|RB]]" in text
    assert "[[#Defense / Special Teams (D/ST)|D/ST]]" in text
    assert "Status: **READY**" in text
    assert "## Overall Priorities by VORP" in text
    assert "## Running Backs (RB)" in text
    assert "## Defense / Special Teams (D/ST)" in text
    assert "## Kickers (K)" in text
    assert "Draft one in the second-to-last round" in text
    assert "Draft one in the final round" in text
    assert "Jahmyr Gibbs" in text
    assert "Start with overall value" in text
    assert "| Rank | Player | Pos | Team | Tier | ADP | VORP |" in text
    assert "- [ ] **1. Jahmyr Gibbs**" in text
    assert "- [ ] ⬇️ **1. Josh Allen**" in text
    assert "- [ ] ⚠️ **2. Puka Nacua**" in text
    assert "Low; availability" in text
    assert f"Board fingerprint: `{board_fingerprint(board)}`" in text
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
    assert "> [!warning] Data warnings" in text
    assert "ERROR — projection_data_stale" in text
    assert "Projection data is stale" in text


def test_position_depth_scales_for_twelve_team_league(web_draft):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    board["league"]["league_size"] = 12

    assert position_limits(board) == {
        "QB": 36, "RB": 60, "WR": 60, "TE": 36, "DST": 10, "K": 10
    }


def test_obsidian_tasks_match_position_depth_without_priority_duplicates(web_draft):
    board = json.loads(web_draft["board_path"].read_text(encoding="utf-8"))
    board["league"]["league_size"] = 12

    text = render_cheatsheet(board, {"status": "ready", "issues": []})

    limits = position_limits(board)
    expected_tasks = sum(
        min(len(board["roles"].get(position, [])), limits[position])
        for position in ("RB", "WR", "QB", "TE", "DST", "K")
    )
    assert text.count("- [ ] ") == expected_tasks
    priorities = text.split("## Overall Priorities by VORP", 1)[1].split(
        "## Running Backs (RB)", 1
    )[0]
    assert "- [ ]" not in priorities
