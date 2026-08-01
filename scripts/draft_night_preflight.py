#!/usr/bin/env python3
"""Run the complete draft-night readiness gate."""

import argparse
from pathlib import Path

from fantasy_draft.preflight import artifact_checks, deployment_checks, render_report, test_checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=Path("outputs/draft_board.json"))
    parser.add_argument(
        "--fallback",
        type=Path,
        default=Path("outputs/emergency_draft_cheatsheet.md"),
    )
    parser.add_argument("--sessions-dir", type=Path, default=Path("sessions"))
    parser.add_argument(
        "--deployment",
        choices=("local", "tailscale-linux"),
        default="local",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip slow suites for diagnostics only; the launcher never uses this",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    checks = deployment_checks(root, args.sessions_dir, args.deployment)
    checks.extend(artifact_checks(args.board, args.fallback))
    if not args.skip_tests:
        checks.extend(test_checks(root))
    print(render_report(checks))
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
