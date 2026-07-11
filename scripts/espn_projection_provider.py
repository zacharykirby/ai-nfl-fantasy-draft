#!/usr/bin/env python3
"""ESPN Mike Clay projection guide adapter.

The official PDF contains stable positional tables with PPR fantasy points and
receptions. Receptions allow exact conversion from PPR to half-PPR or standard.
"""

import re
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import requests
from pypdf import PdfReader


ESPN_PROJECTION_URL_TEMPLATE = (
    "https://g.espncdn.com/s/ffldraftkit/{short_year}/"
    "NFLDK{season}_CS_ClayProjections{season}.pdf"
)
POSITION_PAGES = {
    "QB": [34],
    "RB": [35, 36, 37],
    "WR": [38, 39, 40, 41, 42],
    "TE": [43, 44],
}
TEAM_NORMALIZATION = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU"}
ROW_PATTERN = re.compile(
    r"^\s*(?P<name>.+?)\s{2,}(?P<team>[A-Z]{2,3})\s+"
    r"(?P<position_rank>\d+)\s+(?P<ppr_points>\d+)\s+(?P<games>\d+)\s+(?P<stats>.+)$"
)


def projection_url(season: int) -> str:
    return ESPN_PROJECTION_URL_TEMPLATE.format(short_year=str(season)[-2:], season=season)


def download_projection_pdf(season: int, timeout: int = 30) -> bytes:
    response = requests.get(projection_url(season), timeout=timeout)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError("ESPN projection response is not a PDF")
    return response.content


def _receptions(position: str, stats: str) -> int:
    if position == "QB":
        return 0
    values = stats.split()
    # RB/WR/TE columns after games: carries, rush yards, rush TD, targets,
    # receptions, receiving yards, receiving TD, carry share, target share.
    if len(values) < 5:
        raise ValueError("Projection row is missing reception columns")
    return int(values[4])


def convert_ppr_points(ppr_points: float, receptions: int, scoring: str) -> float:
    if scoring == "ppr":
        return float(ppr_points)
    if scoring == "half_ppr":
        return float(ppr_points) - (0.5 * receptions)
    if scoring == "standard":
        return float(ppr_points) - receptions
    raise ValueError("scoring must be standard, half_ppr, or ppr")


def parse_projection_pdf(
    pdf_content: bytes,
    scoring: str = "half_ppr",
    source_url: Optional[str] = None,
) -> pd.DataFrame:
    reader = PdfReader(BytesIO(pdf_content))
    if len(reader.pages) < 45:
        raise ValueError("ESPN projection PDF has fewer pages than expected")

    rows: List[Dict[str, object]] = []
    for position, pages in POSITION_PAGES.items():
        for page_number in pages:
            text = reader.pages[page_number].extract_text(extraction_mode="layout")
            for line in text.splitlines():
                match = ROW_PATTERN.match(line)
                if not match:
                    continue
                raw = match.groupdict()
                receptions = _receptions(position, raw["stats"])
                ppr_points = float(raw["ppr_points"])
                rows.append(
                    {
                        "name": raw["name"].strip(),
                        "position": position,
                        "team": TEAM_NORMALIZATION.get(raw["team"], raw["team"]),
                        "projected_fantasy_points": convert_ppr_points(
                            ppr_points, receptions, scoring
                        ),
                        "projection_rank": int(raw["position_rank"]),
                        "games": int(raw["games"]),
                        "receptions": receptions,
                        "ppr_projected_points": ppr_points,
                        "projection_method": "published",
                        "projection_source": source_url or "ESPN Mike Clay Projection Guide",
                    }
                )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No offensive projection rows were parsed from ESPN PDF")
    duplicates = frame.duplicated(["name", "position"])
    if duplicates.any():
        raise ValueError("ESPN projection PDF produced duplicate player/position rows")
    return frame


def fetch_espn_projection_rows(season: int, scoring: str = "half_ppr") -> pd.DataFrame:
    url = projection_url(season)
    return parse_projection_pdf(download_projection_pdf(season), scoring=scoring, source_url=url)
