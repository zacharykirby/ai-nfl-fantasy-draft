"""Draft-night preflight checks for artifacts, tests, browser, and deployment."""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from fantasy_draft.board import (
    load_board,
    validate_board_path,
    verify_board_fingerprint,
    verify_fallback_fingerprint,
    write_cheatsheet,
)


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    detail: str


def artifact_checks(board_path: Path, fallback_path: Path) -> List[PreflightCheck]:
    """Validate the board, regenerate its fallback, and prove exact agreement."""
    board_path = Path(board_path)
    fallback_path = Path(fallback_path)
    try:
        board = load_board(board_path)
        health = validate_board_path(board_path)
    except (OSError, ValueError) as exc:
        return [PreflightCheck("board readiness", False, str(exc))]

    readiness = PreflightCheck(
        "board readiness",
        health.get("can_create_session") is True,
        "{} ({} errors, {} warnings)".format(
            health.get("status", "unknown"),
            health.get("error_count", 0),
            health.get("warning_count", 0),
        ),
    )
    fingerprint = verify_board_fingerprint(board)
    fingerprint_check = PreflightCheck(
        "board fingerprint",
        fingerprint["matches"],
        fingerprint["actual"] if fingerprint["matches"] else "missing or mismatched fingerprint",
    )
    if not readiness.passed or not fingerprint_check.passed:
        return [readiness, fingerprint_check]

    write_cheatsheet(board, fallback_path, health)
    fallback = verify_fallback_fingerprint(board, fallback_path)
    fallback_check = PreflightCheck(
        "fallback fingerprint",
        fallback["matches"],
        fallback.get("fallback") or "missing fingerprint in emergency sheet",
    )
    return [readiness, fingerprint_check, fallback_check]


def deployment_checks(
    project_root: Path,
    sessions_dir: Path,
    deployment: str,
    environment: Optional[Dict[str, str]] = None,
) -> List[PreflightCheck]:
    """Report explicit supported runtime and hosting assumptions."""
    environment = dict(os.environ if environment is None else environment)
    checks = [
        PreflightCheck(
            "python runtime",
            sys.version_info >= (3, 12),
            "Python {}.{}.{}; supported version is 3.12+".format(*sys.version_info[:3]),
        )
    ]
    worker_values = {
        key: environment.get(key)
        for key in ("WEB_CONCURRENCY", "UVICORN_WORKERS")
        if environment.get(key)
    }
    invalid_workers = {
        key: value for key, value in worker_values.items() if str(value).strip() != "1"
    }
    checks.append(PreflightCheck(
        "single worker configuration",
        not invalid_workers,
        "process lock enabled"
        if not invalid_workers
        else "unsupported worker settings: {}".format(invalid_workers),
    ))

    sessions_dir = Path(sessions_dir)
    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
        writable = os.access(sessions_dir, os.W_OK)
    except OSError:
        writable = False
    checks.append(PreflightCheck(
        "sessions directory",
        writable,
        str(sessions_dir.resolve()),
    ))

    if deployment == "tailscale-linux":
        linux = sys.platform.startswith("linux")
        checks.append(PreflightCheck(
            "supported host",
            linux,
            sys.platform if linux else "Tailscale launcher requires Linux with user systemd",
        ))
        for command in ("bash", "systemctl", "tailscale"):
            location = shutil.which(command)
            checks.append(PreflightCheck(
                "{} available".format(command),
                location is not None,
                location or "not found on PATH",
            ))
        runtime_files = [
            Path(project_root) / "venv" / "bin" / "python",
            Path(project_root) / "venv" / "bin" / "draft-server",
        ]
        checks.append(PreflightCheck(
            "launcher virtualenv",
            all(path.is_file() for path in runtime_files),
            ", ".join(str(path) for path in runtime_files),
        ))
    else:
        checks.append(PreflightCheck(
            "supported host",
            True,
            "local loopback deployment on {}".format(sys.platform),
        ))
    return checks


def _pytest_check(name: str, root: Path, marker: str, require_executed: bool) -> PreflightCheck:
    with tempfile.TemporaryDirectory(prefix="fantasy-preflight-") as temporary:
        report = Path(temporary) / "pytest.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            marker,
            "--junitxml",
            str(report),
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
        if report.is_file():
            xml_root = ET.parse(report).getroot()
            suite: Iterable[ET.Element]
            suite = [xml_root] if xml_root.tag == "testsuite" else xml_root.findall("testsuite")
            for element in suite:
                for key in counts:
                    counts[key] += int(element.attrib.get(key, 0))
        executed = counts["tests"] - counts["skipped"]
        passed = completed.returncode == 0 and (not require_executed or executed > 0)
        if require_executed and executed <= 0:
            detail = "critical-path tests did not execute ({} skipped)".format(counts["skipped"])
        else:
            detail = "{} executed, {} failed, {} skipped".format(
                executed,
                counts["failures"] + counts["errors"],
                counts["skipped"],
            )
        return PreflightCheck(name, passed, detail)


def test_checks(project_root: Path) -> List[PreflightCheck]:
    """Run unit and browser suites separately; skipped browser coverage is failure."""
    project_root = Path(project_root)
    return [
        _pytest_check("unit tests", project_root, "not browser", require_executed=True),
        _pytest_check("browser critical path", project_root, "browser", require_executed=True),
    ]


def render_report(checks: Iterable[PreflightCheck]) -> str:
    lines = ["DRAFT-NIGHT PREFLIGHT"]
    for check in checks:
        lines.append("[{}] {}: {}".format(
            "PASS" if check.passed else "FAIL",
            check.name,
            check.detail,
        ))
    result = "READY" if all(check.passed for check in checks) else "NOT READY"
    lines.extend(["", "Result: {}".format(result)])
    return "\n".join(lines)
