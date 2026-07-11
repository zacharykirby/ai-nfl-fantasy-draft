#!/usr/bin/env python3
"""Normalize a licensed or user-authored projection CSV into the app contract."""

from pathlib import Path
from typing import Dict

import pandas as pd


ALIASES: Dict[str, str] = {
    "player": "name",
    "player_name": "name",
    "pos": "position",
    "tm": "team",
    "bye": "bye_week",
    "byeweek": "bye_week",
    "fpts": "projected_fantasy_points",
    "fantasy_points": "projected_fantasy_points",
    "projected_points": "projected_fantasy_points",
    "overall_rank": "rank",
    "rk": "rank",
    "average_draft_position": "adp",
}
REQUIRED = {"name", "position", "projected_fantasy_points"}


def import_projection_csv(path: Path, scoring: str, source_name: str = "User supplied CSV") -> pd.DataFrame:
    path = Path(path)
    frame = pd.read_csv(path)
    normalized = {
        column: str(column).strip().lower().replace(" ", "_")
        for column in frame.columns
    }
    frame = frame.rename(columns=normalized)
    frame = frame.rename(columns={column: ALIASES.get(column, column) for column in frame.columns})

    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ValueError("Projection CSV is missing required columns: {}".format(", ".join(missing)))

    frame["name"] = frame["name"].astype(str).str.strip()
    frame["position"] = frame["position"].astype(str).str.upper().str.replace(r"\d+$", "", regex=True)
    frame = frame[frame["position"].isin(["QB", "RB", "WR", "TE"])].copy()
    frame["projected_fantasy_points"] = pd.to_numeric(
        frame["projected_fantasy_points"], errors="coerce"
    )
    frame = frame.dropna(subset=["name", "projected_fantasy_points"])
    frame = frame[frame["projected_fantasy_points"] > 0]
    if frame.duplicated(["name", "position"]).any():
        raise ValueError("Projection CSV contains duplicate player/position rows")

    if "rank" not in frame:
        frame = frame.sort_values("projected_fantasy_points", ascending=False)
        frame["rank"] = range(1, len(frame) + 1)
    frame["rank"] = pd.to_numeric(frame["rank"], errors="coerce")
    missing_rank = frame["rank"].isna()
    frame.loc[missing_rank, "rank"] = range(1, int(missing_rank.sum()) + 1)
    frame["rank"] = frame["rank"].astype(int)

    for column, default in {
        "team": "",
        "bye_week": "N/A",
        "adp": None,
        "tier": None,
    }.items():
        if column not in frame:
            frame[column] = default
    if frame["tier"].isna().any():
        frame["tier"] = pd.cut(
            frame["rank"], [0, 24, 60, 100, 160, float("inf")], labels=[1, 2, 3, 4, 5]
        ).astype(int)

    frame["projection_method"] = "user_supplied"
    frame["team_conflict"] = False
    frame["source"] = source_name
    output = frame[[
        "rank", "name", "position", "team", "bye_week", "projected_fantasy_points",
        "tier", "adp", "projection_method", "team_conflict", "source",
    ]].sort_values(["rank", "projected_fantasy_points"], ascending=[True, False])
    output.attrs["provider"] = "user_csv"
    output.attrs["scoring"] = scoring
    output.attrs["projection_sources"] = [str(path.resolve())]
    return output
