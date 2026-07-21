#!/usr/bin/env python3
"""Fetch current fantasy football projections and ADP into the ranker input format."""

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from espn_projection_provider import fetch_espn_projection_rows, projection_url


FANTASYPROS_PROJECTION_URLS: Dict[str, str] = {
    "QB": "https://www.fantasypros.com/nfl/projections/qb.php?week=draft",
    "RB": "https://www.fantasypros.com/nfl/projections/rb.php?week=draft",
    "WR": "https://www.fantasypros.com/nfl/projections/wr.php?week=draft",
    "TE": "https://www.fantasypros.com/nfl/projections/te.php?week=draft",
}
FANTASYPROS_ADP_URL = "https://draftwizard.fantasypros.com/football/adp/mock-drafts/"

DEFAULT_SEASON = datetime.now().year
TEAM_NORMALIZATION = {"JAC": "JAX", "LA": "LAR", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}
NAME_SUFFIX_PATTERN = re.compile(r"\s+(?:JR\.?|SR\.?|II|III|IV|V)$", re.IGNORECASE)
PLAYER_NAME_ALIASES = {
    "kenny gainwell": "kenneth gainwell",
    "chig okonkwo": "chigoziem okonkwo",
    "ken walker": "kenneth walker",
}

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


def normalize_player_name(value: object) -> str:
    """Create a conservative cross-provider identity key."""
    text = re.sub(r"\s+", " ", str(value).strip())
    text = NAME_SUFFIX_PATTERN.sub("", text)
    normalized = text.replace("’", "'").replace(".", "").casefold()
    return PLAYER_NAME_ALIASES.get(normalized, normalized)


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
                    "projection_method": "published",
                    "projection_source": url,
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
    adp["team"] = adp["team"].replace(TEAM_NORMALIZATION)
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


def build_projection_file(
    season: int = DEFAULT_SEASON,
    scoring: str = "half_ppr",
    provider: str = "espn",
) -> pd.DataFrame:
    if provider == "espn":
        logger.info("Fetching ESPN Mike Clay %s projections for %s", scoring, season)
        projections = fetch_espn_projection_rows(season, scoring=scoring)
        projection_sources = [projection_url(season)]
    elif provider == "fantasypros":
        projections = fetch_projection_rows()
        projection_sources = list(FANTASYPROS_PROJECTION_URLS.values())
    else:
        raise ValueError("provider must be espn or fantasypros")
    adp = fetch_adp_rows()

    projections = projections.copy()
    adp = adp.copy()
    projections["match_name"] = projections["name"].apply(normalize_player_name)
    adp["match_name"] = adp["name"].apply(normalize_player_name)

    merged = adp.merge(
        projections,
        on=["match_name", "position"],
        how="outer",
        suffixes=("_adp", "_proj"),
    )
    merged["name"] = merged["name_adp"].fillna(merged["name_proj"])
    merged["team"] = merged["team_adp"].fillna("").where(
        merged["team_adp"].fillna("") != "", merged["team_proj"].fillna("")
    )
    merged["team_conflict"] = (
        merged["team_adp"].fillna("").ne("")
        & merged["team_proj"].fillna("").ne("")
        & merged["team_adp"].fillna("").ne(merged["team_proj"].fillna(""))
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
    merged["projection_method"] = merged["projection_method"].fillna("adp_estimate")
    merged.loc[missing_projection, "projection_method"] = "adp_estimate"
    merged.loc[missing_projection, "projected_fantasy_points"] = merged[missing_projection].apply(
        estimate_points_from_adp, axis=1
    )
    merged["tier"] = assign_tiers(merged)
    merged["source"] = merged["projection_source"].fillna("Local ADP estimate")

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
            "projection_method",
            "team_conflict",
            "source",
        ]
    ].copy()
    output = output[output["position"].isin(["QB", "RB", "WR", "TE"])]
    output = output[pd.to_numeric(output["projected_fantasy_points"], errors="coerce").fillna(0) > 0]
    output = output.sort_values(["rank", "projected_fantasy_points"], ascending=[True, False])
    output["rank"] = output["rank"].round(0).astype(int)
    output["projected_fantasy_points"] = output["projected_fantasy_points"].round(1)
    output["adp"] = output["adp"].round(2)
    output.attrs["provider"] = provider
    output.attrs["scoring"] = scoring
    output.attrs["projection_sources"] = projection_sources
    return output


def build_metadata(output: pd.DataFrame, season: int, output_file: Path) -> Dict[str, object]:
    """Build a source and coverage manifest alongside the generated CSV."""
    position_counts = output["position"].value_counts().to_dict()
    method_counts = output["projection_method"].value_counts().to_dict()
    return {
        "schema_version": "1.0",
        "season": season,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "output_file": str(output_file),
        "sources": {
            "projections": output.attrs.get("projection_sources", sorted(output["source"].unique().tolist())),
            "adp": FANTASYPROS_ADP_URL,
        },
        "provider": output.attrs.get("provider", "unknown"),
        "scoring": output.attrs.get("scoring", "unknown"),
        "row_count": len(output),
        "position_counts": {str(key): int(value) for key, value in position_counts.items()},
        "projection_method_counts": {str(key): int(value) for key, value in method_counts.items()},
        "missing_team_count": int(output["team"].fillna("").eq("").sum()),
        "missing_bye_week_count": int(
            output["bye_week"].fillna("N/A").astype(str).isin(["", "N/A", "nan"]).sum()
        ),
        "missing_adp_count": int(output["adp"].isna().sum()),
        "duplicate_player_position_count": int(output.duplicated(["name", "position"]).sum()),
        "team_conflict_count": int(output["team_conflict"].fillna(False).astype(bool).sum()),
        "team_conflict_examples": output.loc[
            output["team_conflict"].fillna(False).astype(bool), ["name", "position", "team"]
        ].head(20).to_dict("records"),
    }


def write_projection_artifacts(
    output: pd.DataFrame,
    season: int,
    output_file: Optional[Path] = None,
    metadata_file: Optional[Path] = None,
) -> Tuple[Path, Path]:
    output_file = Path(output_file or Path("data") / f"players_{season}_positions_bye.csv")
    metadata_file = Path(metadata_file or Path("data") / f"projection_metadata_{season}.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    with metadata_file.open("w", encoding="utf-8") as handle:
        json.dump(build_metadata(output, season, output_file), handle, indent=2)
        handle.write("\n")
    return output_file, metadata_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch full-season projections and DraftWizard ADP")
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--scoring", choices=["standard", "half_ppr", "ppr"], default="half_ppr")
    parser.add_argument("--provider", choices=["espn", "fantasypros"], default="espn")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--metadata-output", type=Path, default=None)
    args = parser.parse_args()

    output = build_projection_file(season=args.season, scoring=args.scoring, provider=args.provider)
    output_file = args.output or Path("data") / f"players_{args.season}_positions_bye.csv"
    metadata_file = args.metadata_output or Path("data") / f"projection_metadata_{args.season}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    with metadata_file.open("w", encoding="utf-8") as handle:
        json.dump(build_metadata(output, args.season, output_file), handle, indent=2)
        handle.write("\n")
    logger.info("Wrote %s projection rows to %s", len(output), output_file)
    logger.info("Wrote projection metadata to %s", metadata_file)


if __name__ == "__main__":
    main()
