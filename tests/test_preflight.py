import json
from pathlib import Path

from fantasy_draft.board import (
    board_fingerprint,
    render_cheatsheet,
    stamp_board_fingerprint,
    verify_board_fingerprint,
    verify_fallback_fingerprint,
)
from fantasy_draft.preflight import artifact_checks, deployment_checks, render_report


def _stamp_fixture_board(web_draft):
    path = web_draft["board_path"]
    board = json.loads(path.read_text(encoding="utf-8"))
    stamp_board_fingerprint(board)
    path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    return board


def test_fingerprint_is_stable_and_detects_board_changes(web_draft):
    board = _stamp_fixture_board(web_draft)
    saved = board["metadata"]["board_fingerprint"]

    assert saved == board_fingerprint(board)
    assert verify_board_fingerprint(board)["matches"] is True

    board["league"]["league_size"] = 12
    report = verify_board_fingerprint(board)
    assert report["matches"] is False
    assert report["actual"] != saved


def test_artifact_preflight_regenerates_exact_fallback(web_draft, tmp_path):
    board = _stamp_fixture_board(web_draft)
    fallback = tmp_path / "emergency.md"

    checks = artifact_checks(web_draft["board_path"], fallback)

    assert all(check.passed for check in checks)
    assert [check.name for check in checks] == [
        "board readiness",
        "board fingerprint",
        "fallback fingerprint",
    ]
    assert verify_fallback_fingerprint(board, fallback)["matches"] is True

    fallback.write_text(fallback.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    # The fingerprint identifies the source board, so unrelated sheet edits do not
    # masquerade as a different board. Regeneration restores the canonical content.
    checks = artifact_checks(web_draft["board_path"], fallback)
    assert all(check.passed for check in checks)
    assert not fallback.read_text(encoding="utf-8").endswith("tampered\n")

    wrong_fingerprint = "sha256:" + "0" * 64
    fallback.write_text(
        render_cheatsheet(board).replace(board_fingerprint(board), wrong_fingerprint),
        encoding="utf-8",
    )
    assert verify_fallback_fingerprint(board, fallback)["matches"] is False


def test_artifact_preflight_rejects_changed_board_before_rewriting_fallback(web_draft, tmp_path):
    board = _stamp_fixture_board(web_draft)
    fallback = tmp_path / "emergency.md"
    fallback.write_text("keep me", encoding="utf-8")
    board["roles"]["RB"][0]["projected_points"] += 1
    web_draft["board_path"].write_text(json.dumps(board), encoding="utf-8")

    checks = artifact_checks(web_draft["board_path"], fallback)

    assert any(check.name == "board fingerprint" and not check.passed for check in checks)
    assert fallback.read_text(encoding="utf-8") == "keep me"


def test_deployment_checks_reject_multiworker_environment(tmp_path):
    checks = deployment_checks(
        tmp_path,
        tmp_path / "sessions",
        "local",
        environment={"WEB_CONCURRENCY": "2"},
    )

    worker = next(check for check in checks if check.name == "single worker configuration")
    assert worker.passed is False
    assert "WEB_CONCURRENCY" in worker.detail
    assert "Result: NOT READY" in render_report(checks)
