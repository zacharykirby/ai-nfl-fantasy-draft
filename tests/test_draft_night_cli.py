import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fantasy_draft.cli.draft_night import DraftNightShell
from fantasy_draft.draft.session import DraftSession


class OfflineClient:
    api_key = None
    model = "offline/test"

    def chat(self, **kwargs):
        return "Error: offline test"


def player(name, position, rank):
    return {
        "player": name,
        "position": position,
        "team": "TST",
        "overall_rank": rank,
        "position_rank": 1 if rank % 2 else 2,
        "tier": 1 if rank <= 4 else 2,
        "projected_points": 250 - rank,
        "vorp": 80 - rank,
        "adp": rank,
        "projection_method": "published",
        "risk": {"level": "Low", "injury_flag": False},
        "flags": [],
    }


def make_session(tmp_path):
    board = {
        "schema_version": "1.0",
        "metadata": {"season": 2026, "generated_at": "2026-07-11T00:00:00"},
        "health": {"status": "ready"},
        "league": {
            "scoring": "half_ppr",
            "starters": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "FLEX": 1},
            "bench_size": 1,
        },
        "roles": {
            "QB": [player("Quarterback One", "QB", 7), player("Quarterback Two", "QB", 8)],
            "RB": [player("Runner One", "RB", 1), player("Runner Two", "RB", 4)],
            "WR": [player("Receiver One", "WR", 2), player("Receiver Two", "WR", 5)],
            "TE": [player("Tight End One", "TE", 3), player("Tight End Two", "TE", 6)],
        },
    }
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board))
    return DraftSession.create(tmp_path / "session.json", board_path, "shell", 2, 4, 1)


def shell(tmp_path, inputs=None):
    outputs = []
    commands = iter(inputs or [])
    instance = DraftNightShell(
        make_session(tmp_path),
        client=OfflineClient(),
        input_func=lambda _prompt: next(commands),
        output_func=outputs.append,
    )
    return instance, outputs


def test_dashboard_contains_draft_night_state(tmp_path):
    instance, _ = shell(tmp_path)

    dashboard = instance.render_dashboard()

    assert "shell | ACTIVE | Pick 1" in dashboard
    assert "YOUR PICK" in dashboard
    assert "Model: OFFLINE (deterministic)" in dashboard
    assert "Autosave:" in dashboard
    assert "Runner One" in dashboard
    assert "Tier alerts:" in dashboard


def test_draft_undo_and_roster_commands_mutate_only_explicitly(tmp_path):
    instance, outputs = shell(tmp_path)

    assert instance.execute("draft Runner One") is True
    assert instance.session.current_pick == 2
    instance.execute("roster 1")
    instance.execute("undo")

    assert instance.session.current_pick == 1
    assert any("Recorded pick 1" in line for line in outputs)
    assert any("Team 1 roster:" in line for line in outputs)
    assert any("Undid pick 1" in line for line in outputs)


def test_available_and_recommendation_commands_are_read_only(tmp_path):
    instance, outputs = shell(tmp_path)

    before = list(instance.session.payload["events"])
    instance.execute("available RB 1")
    instance.execute("recommend upside")

    assert instance.session.payload["events"] == before
    assert any("Runner One" in line for line in outputs)
    assert any(line.startswith("UPSIDE:") for line in outputs)


def test_bare_question_uses_assistant_fallback_without_mutation(tmp_path):
    instance, outputs = shell(tmp_path)
    before = list(instance.session.payload["events"])

    instance.execute("Who should I take here?")

    assert instance.session.payload["events"] == before
    assert "Thinking with bounded draft context..." in outputs
    assert any(line.startswith("FALLBACK:") for line in outputs)


def test_bad_commands_report_errors_and_keep_running(tmp_path):
    instance, outputs = shell(tmp_path)

    assert instance.execute("draft") is True
    assert instance.execute("recommend chaos") is True
    assert instance.execute("available RB nope") is True

    assert sum(line.startswith("ERROR:") for line in outputs) == 3
    assert instance.session.current_pick == 1


def test_run_loop_handles_help_status_and_quit(tmp_path):
    instance, outputs = shell(tmp_path, inputs=["help", "status", "quit"])

    instance.run()

    assert any("Commands:" in line for line in outputs)
    assert sum("shell | ACTIVE" in line for line in outputs) >= 2
    assert any("Good luck!" in line for line in outputs)
    assert instance.session.path.exists()
