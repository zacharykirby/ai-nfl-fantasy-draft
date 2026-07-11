#!/usr/bin/env python3
"""Validation for projection CSVs and their source manifests."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


REQUIRED_COLUMNS = {
    "rank", "name", "position", "team", "bye_week",
    "projected_fantasy_points", "tier", "adp", "projection_method", "team_conflict", "source",
}
MINIMUM_POSITION_COUNTS = {"QB": 20, "RB": 40, "WR": 50, "TE": 15}


def _issue(severity: str, code: str, message: str, **details: Any) -> Dict[str, Any]:
    result = {"severity": severity, "code": code, "message": message}
    if details:
        result["details"] = details
    return result


def _parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def validate_projection_file(
    projection_path: Path,
    metadata_path: Optional[Path] = None,
    expected_season: Optional[int] = None,
    max_age_days: int = 14,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    projection_path = Path(projection_path)
    metadata_path = Path(metadata_path or projection_path.with_name(
        "projection_metadata_{}.json".format(expected_season or datetime.now().year)
    ))
    issues: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}

    if not projection_path.exists():
        issues.append(_issue("error", "projection_file_missing", "Projection CSV does not exist"))
        return _report(issues, metrics)
    try:
        frame = pd.read_csv(projection_path)
    except Exception as exc:
        issues.append(_issue("error", "projection_file_unreadable", str(exc)))
        return _report(issues, metrics)

    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        issues.append(_issue(
            "error", "projection_columns_missing",
            "Projection CSV is missing required columns",
            columns=missing_columns,
        ))

    metrics["row_count"] = len(frame)
    if "position" in frame:
        counts = frame["position"].value_counts().to_dict()
        metrics["position_counts"] = {str(key): int(value) for key, value in counts.items()}
        for position, minimum in MINIMUM_POSITION_COUNTS.items():
            actual = int(counts.get(position, 0))
            if actual < minimum:
                issues.append(_issue(
                    "error", "position_coverage_low",
                    "{} has {} players; minimum is {}".format(position, actual, minimum),
                    position=position, actual=actual, minimum=minimum,
                ))

    if {"name", "position"} <= set(frame.columns):
        duplicates = frame[frame.duplicated(["name", "position"], keep=False)]
        metrics["duplicate_player_position_count"] = len(duplicates)
        if not duplicates.empty:
            issues.append(_issue(
                "error", "duplicate_player_position",
                "Projection CSV contains duplicate player/position identities",
                examples=duplicates[["name", "position"]].head(10).to_dict("records"),
            ))

    if "projected_fantasy_points" in frame:
        points = pd.to_numeric(frame["projected_fantasy_points"], errors="coerce")
        invalid_points = int((points.isna() | (points <= 0)).sum())
        metrics["invalid_projection_count"] = invalid_points
        if invalid_points:
            issues.append(_issue(
                "error", "invalid_projected_points",
                "{} players have missing or nonpositive projections".format(invalid_points),
            ))

    if "projection_method" in frame:
        methods = frame["projection_method"].value_counts(dropna=False).to_dict()
        metrics["projection_method_counts"] = {str(key): int(value) for key, value in methods.items()}
        estimated = int((frame["projection_method"] != "published").sum())
        estimated_rate = estimated / len(frame) if len(frame) else 1.0
        metrics["estimated_projection_count"] = estimated
        metrics["estimated_projection_rate"] = round(estimated_rate, 4)
        if estimated_rate > 0.25:
            issues.append(_issue(
                "error", "estimated_projection_rate_high",
                "{:.1%} of projections are estimates; maximum is 25%".format(estimated_rate),
            ))
        elif estimated:
            issues.append(_issue(
                "warning", "estimated_projections_present",
                "{} players use ADP-derived projection estimates".format(estimated),
            ))

    if "team_conflict" in frame:
        conflicts = frame["team_conflict"].fillna(False).astype(bool)
        count = int(conflicts.sum())
        metrics["team_conflict_count"] = count
        if count:
            issues.append(_issue(
                "error", "player_team_conflicts",
                "{} players have conflicting teams between sources".format(count),
                examples=frame.loc[conflicts, ["name", "position", "team"]].head(10).to_dict("records"),
            ))

    for column, code, label in (
        ("team", "team_coverage_low", "team"),
        ("bye_week", "bye_week_coverage_low", "bye week"),
    ):
        if column not in frame:
            continue
        missing = frame[column].fillna("").astype(str).str.strip().isin(["", "N/A", "nan"])
        count = int(missing.sum())
        rate = count / len(frame) if len(frame) else 1.0
        metrics["missing_{}_count".format(column)] = count
        # Bye weeks are often absent for deep projection-only players. Warn rather
        # than block when the top draftable pool still has broad coverage.
        severity = "error" if column == "team" and rate > 0.05 else "warning"
        if count:
            issues.append(_issue(
                severity, code,
                "{} players are missing {} data ({:.1%})".format(count, label, rate),
            ))

    metadata: Dict[str, Any] = {}
    if not metadata_path.exists():
        issues.append(_issue("error", "projection_metadata_missing", "Projection source manifest is missing"))
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(_issue("error", "projection_metadata_unreadable", str(exc)))

    if metadata:
        metrics["retrieved_at"] = metadata.get("retrieved_at")
        if expected_season is not None and metadata.get("season") != expected_season:
            issues.append(_issue(
                "error", "projection_season_mismatch",
                "Manifest season {} does not match {}".format(metadata.get("season"), expected_season),
            ))
        retrieved_at = _parse_date(metadata.get("retrieved_at"))
        if retrieved_at is None:
            issues.append(_issue("error", "projection_retrieval_time_missing", "Manifest has no valid retrieval time"))
        else:
            current = now or datetime.now(timezone.utc)
            age_days = (current - retrieved_at).total_seconds() / 86400
            metrics["age_days"] = round(age_days, 2)
            if age_days > max_age_days:
                issues.append(_issue(
                    "error", "projection_data_stale",
                    "Projection data is {:.1f} days old; maximum is {}".format(age_days, max_age_days),
                ))
        if not metadata.get("sources"):
            issues.append(_issue("error", "projection_sources_missing", "Manifest has no source URLs"))

    return _report(issues, metrics)


def _report(issues: List[Dict[str, Any]], metrics: Dict[str, Any]) -> Dict[str, Any]:
    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "status": "ready" if errors == 0 else "not_ready",
        "error_count": errors,
        "warning_count": warnings,
        "metrics": metrics,
        "issues": issues,
    }
