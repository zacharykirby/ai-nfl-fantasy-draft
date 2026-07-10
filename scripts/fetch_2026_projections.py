#!/usr/bin/env python3
"""Fetch 2026 fantasy football projections and ADP into the ranker input format."""

import logging
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd


FANTASYPROS_PROJECTION_URLS: Dict[str, str] = {
    "QB": "https://www.fantasypros.com/nfl/projections/qb.php?week=draft",
    "RB": "https://www.fantasypros.com/nfl/projections/rb.php?week=draft",
    "WR": "https://www.fantasypros.com/nfl/projections/wr.php?week=draft",
    "TE": "https://www.fantasypros.com/nfl/projections/te.php?week=draft",
}
FANTASYPROS_ADP_URL = "https://draftwizard.fantasypros.com/football/adp/mock-drafts/"

OUTPUT_FILE = Path("data") / "players_2026_positions_bye.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten pandas MultiIndex columns from FantasyPros tables."""
    if isinstance(df.columns, pd.MultiIndex):
        flattened: List[str] = []
        seen: Dict[str, int] = {}
        for parts in df.columns:
            clean_parts = [str(part).strip() for part in parts if "Unnamed:" not in str(part)]
            name = "_".join(clean_parts) if clean_parts else str(parts[-1]).strip()
            name = re.sub(r"\s+", "_", name).upper()
            seen[name] = seen.get(name, 0) + 1
            if seen[name] > 1:
                name = f"{name}_{seen[name]}"
            flattened.append(name)
        df = df.copy()
        df.columns = flattened
    else:
        df = df.copy()
        df.columns = [re.sub(r"\s+", "_", str(col).strip()).upper() for col in df.columns]
    return df


def split_player_team(value: object) -> tuple[str, str]:
    """Split FantasyPros player cells such as 'Josh Allen BUF' into name/team."""
    text = str(value).strip()
    match = re.match(r"^(?P<name>.+?)\s+(?P<team>[A-Z]{2,3})$", text)
    if not match:
        return text, ""
    return match.group("name").strip(), match.group("team").strip()


def parse_position_rank(value: object) -> str:
    match = re.match(r"([A-Z]+)", str(value).strip())
    return match.group(1) if match else ""


def parse_position_rank_number(value: object) -> int:
    match = re.search(r"(\d+)", str(value).strip())
    return int(match.group(1)) if match else 999


def estimate_points_from_adp(row: pd.Series) -> float:
    """Estimate fantasy points for ADP-only rows when projections are paginated/truncated."""
    position = str(row.get("position", ""))
    pos_rank = parse_position_rank_number(row.get("position_rank", ""))
    curves = {
        "QB": (335, 7.0, 90),
        "RB": (275, 4.0, 35),
        "WR": (230, 2.4, 35),
        "TE": (170, 3.2, 25),
    }
    if position not in curves:
        return 0.0
    start, slope, floor = curves[position]
    return max(floor, start - ((pos_rank - 1) * slope))


def estimate_overall_rank(row: pd.Series) -> float:
    """Estimate overall rank for projection-only players without ADP."""
    position = str(row.get("position", ""))
    pos_rank = pd.to_numeric(row.get("projection_rank", None), errors="coerce")
    if pd.isna(pos_rank):
        pos_rank = parse_position_rank_number(row.get("position_rank", ""))
    curves = {
        "RB": (0, 3.0),
        "WR": (0, 2.6),
        "TE": (12, 6.0),
        "QB": (18, 6.5),
    }
    offset, multiplier = curves.get(position, (100, 4.0))
    return offset + (float(pos_rank) * multiplier)


def fetch_projection_rows() -> pd.DataFrame:
    rows = []
    for position, url in FANTASYPROS_PROJECTION_URLS.items():
        logger.info("Fetching %s projections from %s", position, url)
        table = flatten_columns(pd.read_html(url)[0])
        for idx, row in table.iterrows():
            player_name, team = split_player_team(row.get("PLAYER", ""))
            if not player_name:
                continue
            rows.append(
                {
                    "name": player_name,
                    "position": position,
                    "team": team,
                    "projected_fantasy_points": row.get("MISC_FPTS", row.get("FPTS", 0)),
                    "projection_rank": idx + 1,
                }
            )
    projections = pd.DataFrame(rows)
    projections["projected_fantasy_points"] = pd.to_numeric(
        projections["projected_fantasy_points"], errors="coerce"
    ).fillna(0)
    return projections


def fetch_adp_rows() -> pd.DataFrame:
    logger.info("Fetching ADP from %s", FANTASYPROS_ADP_URL)
    adp = pd.read_html(FANTASYPROS_ADP_URL)[0]
    adp = adp.rename(
        columns={
            "Position": "position_rank",
            "Overall": "rank",
            "Player": "name",
            "Team (Bye)": "team_bye",
            "Avg Pick": "adp",
        }
    )
    parsed_team_bye = adp["team_bye"].astype(str).str.extract(r"(?P<team>[A-Z]{2,3})\s+\((?P<bye_week>[^)]+)\)")
    adp["team"] = parsed_team_bye["team"].fillna("")
    adp["bye_week"] = parsed_team_bye["bye_week"].fillna("N/A")
    adp["position"] = adp["position_rank"].apply(parse_position_rank)
    adp["adp"] = pd.to_numeric(adp["adp"], errors="coerce")
    adp["rank"] = pd.to_numeric(adp["rank"], errors="coerce")
    return adp[["rank", "name", "position_rank", "position", "team", "bye_week", "adp"]]


def assign_tiers(df: pd.DataFrame) -> pd.Series:
    fallback_rank = pd.Series(df.index + 1, index=df.index)
    rank = pd.to_numeric(df["rank"], errors="coerce").fillna(fallback_rank)
    return pd.cut(
        rank,
        bins=[0, 24, 60, 100, 160, float("inf")],
        labels=[1, 2, 3, 4, 5],
        include_lowest=True,
    ).astype(int)


def build_projection_file() -> pd.DataFrame:
    projections = fetch_projection_rows()
    adp = fetch_adp_rows()

    merged = adp.merge(
        projections,
        on=["name", "position"],
        how="outer",
        suffixes=("_adp", "_proj"),
    )
    merged["team"] = merged["team_adp"].fillna("").where(
        merged["team_adp"].fillna("") != "", merged["team_proj"].fillna("")
    )
    merged["rank"] = pd.to_numeric(merged["rank"], errors="coerce")
    missing_rank = merged["rank"].isna()
    merged.loc[missing_rank, "rank"] = merged[missing_rank].apply(estimate_overall_rank, axis=1)
    merged["adp"] = pd.to_numeric(merged["adp"], errors="coerce")
    merged["bye_week"] = merged["bye_week"].fillna("N/A")
    merged["projected_fantasy_points"] = pd.to_numeric(
        merged["projected_fantasy_points"], errors="coerce"
    )
    missing_projection = merged["projected_fantasy_points"].isna() | (merged["projected_fantasy_points"] <= 0)
    merged.loc[missing_projection, "projected_fantasy_points"] = merged[missing_projection].apply(
        estimate_points_from_adp, axis=1
    )
    merged["tier"] = assign_tiers(merged)
    merged["source"] = "FantasyPros projections + DraftWizard ADP"

    output = merged[
        [
            "rank",
            "name",
            "position",
            "team",
            "bye_week",
            "projected_fantasy_points",
            "tier",
            "adp",
            "source",
        ]
    ].copy()
    output = output[output["position"].isin(["QB", "RB", "WR", "TE"])]
    output = output[pd.to_numeric(output["projected_fantasy_points"], errors="coerce").fillna(0) > 0]
    output = output.sort_values(["rank", "projected_fantasy_points"], ascending=[True, False])
    output["rank"] = output["rank"].round(0).astype(int)
    output["projected_fantasy_points"] = output["projected_fantasy_points"].round(1)
    output["adp"] = output["adp"].round(2)
    return output


def main() -> None:
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    output = build_projection_file()
    output.to_csv(OUTPUT_FILE, index=False)
    logger.info("Wrote %s projection rows to %s", len(output), OUTPUT_FILE)


if __name__ == "__main__":
    main()
