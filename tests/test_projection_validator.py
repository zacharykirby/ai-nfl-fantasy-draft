import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_2026_projections import build_metadata
from projection_validator import validate_projection_file


def valid_frame():
    rows = []
    for position, count in {"QB": 20, "RB": 40, "WR": 50, "TE": 15}.items():
        for number in range(count):
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "name": "{} {}".format(position, number),
                    "position": position,
                    "team": "TST",
                    "bye_week": 7,
                    "projected_fantasy_points": 100,
                    "tier": 2,
                    "adp": len(rows) + 1,
                    "projection_method": "published",
                    "team_conflict": False,
                    "source": "Test",
                }
            )
    return pd.DataFrame(rows)


def write_artifacts(tmp_path, frame=None, retrieved_at="2026-07-10T00:00:00+00:00"):
    frame = valid_frame() if frame is None else frame
    csv_path = tmp_path / "players_2026_positions_bye.csv"
    metadata_path = tmp_path / "projection_metadata_2026.json"
    frame.to_csv(csv_path, index=False)
    metadata_path.write_text(
        json.dumps(
            {
                "season": 2026,
                "retrieved_at": retrieved_at,
                "sources": {"projections": ["https://example.test"], "adp": "https://example.test/adp"},
            }
        )
    )
    return csv_path, metadata_path


def test_valid_projection_artifacts_are_ready(tmp_path):
    csv_path, metadata_path = write_artifacts(tmp_path)

    report = validate_projection_file(
        csv_path,
        metadata_path,
        expected_season=2026,
        now=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert report["status"] == "ready"
    assert report["metrics"]["position_counts"] == {"WR": 50, "RB": 40, "QB": 20, "TE": 15}


def test_estimated_projection_rate_can_block_readiness(tmp_path):
    frame = valid_frame()
    frame.loc[:39, "projection_method"] = "adp_estimate"
    csv_path, metadata_path = write_artifacts(tmp_path, frame)

    report = validate_projection_file(
        csv_path,
        metadata_path,
        expected_season=2026,
        now=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert report["status"] == "not_ready"
    assert "estimated_projection_rate_high" in {issue["code"] for issue in report["issues"]}


def test_stale_manifest_is_rejected(tmp_path):
    csv_path, metadata_path = write_artifacts(tmp_path, retrieved_at="2026-06-01T00:00:00+00:00")

    report = validate_projection_file(
        csv_path,
        metadata_path,
        expected_season=2026,
        max_age_days=14,
        now=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert "projection_data_stale" in {issue["code"] for issue in report["issues"]}


def test_metadata_reports_coverage_and_provenance(tmp_path):
    frame = valid_frame()
    frame.loc[0, "projection_method"] = "adp_estimate"
    output = tmp_path / "players_2026_positions_bye.csv"

    metadata = build_metadata(frame, 2026, output)

    assert metadata["season"] == 2026
    assert metadata["projection_method_counts"] == {"published": 124, "adp_estimate": 1}
    assert metadata["sources"]["adp"].startswith("https://")
