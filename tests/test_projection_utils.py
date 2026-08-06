import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_2026_projections import (
    assign_tiers,
    estimate_overall_rank,
    estimate_points_from_adp,
    fill_bye_weeks_from_team,
    fetch_special_teams_rows,
    flatten_columns,
    parse_position_rank,
    parse_position_rank_number,
    split_player_team,
    TEAM_NORMALIZATION,
    normalize_player_name,
)


def test_split_player_team_handles_standard_fantasypros_cell():
    assert split_player_team("Josh Allen BUF") == ("Josh Allen", "BUF")
    assert split_player_team("Player Without Team") == ("Player Without Team", "")


def test_parse_position_rank_helpers():
    assert parse_position_rank("WR12") == "WR"
    assert parse_position_rank_number("WR12") == 12
    assert parse_position_rank_number("DST") == 999


def test_team_normalization_covers_provider_aliases():
    assert TEAM_NORMALIZATION["JAC"] == "JAX"
    assert TEAM_NORMALIZATION["LA"] == "LAR"


def test_player_name_normalization_matches_provider_suffixes():
    assert normalize_player_name("James Cook III") == normalize_player_name("James Cook")
    assert normalize_player_name("Kyle Pitts Sr.") == normalize_player_name("Kyle Pitts")
    assert normalize_player_name("D.J. Moore") == normalize_player_name("DJ Moore")
    assert normalize_player_name("Kenny Gainwell") == normalize_player_name("Kenneth Gainwell")
    assert normalize_player_name("Ken Walker III") == normalize_player_name("Kenneth Walker")


def test_estimates_points_and_overall_rank_from_position_curves():
    rb_row = pd.Series({"position": "RB", "position_rank": "RB10"})
    wr_row = pd.Series({"position": "WR", "projection_rank": 12})

    assert estimate_points_from_adp(rb_row) == 239
    assert estimate_overall_rank(wr_row) == pytest.approx(31.2)


def test_assign_tiers_uses_overall_rank_bins():
    df = pd.DataFrame({"rank": [1, 25, 61, 101, 200]})

    assert assign_tiers(df).tolist() == [1, 2, 3, 4, 5]


def test_fill_bye_weeks_from_team_covers_projection_only_players():
    df = pd.DataFrame(
        [
            {"name": "ADP player", "team": "BUF", "bye_week": 7},
            {"name": "Projection player", "team": "BUF", "bye_week": None},
            {"name": "Free agent", "team": "", "bye_week": None},
        ]
    )

    result = fill_bye_weeks_from_team(df)

    assert result["bye_week"].tolist() == [7, 7, "N/A"]


def test_flatten_columns_handles_multiindex_and_duplicates():
    df = pd.DataFrame(
        [[1, 2]],
        columns=pd.MultiIndex.from_tuples(
            [
                ("Passing", "YDS"),
                ("Receiving", "YDS"),
            ]
        ),
    )

    flattened = flatten_columns(df)

    assert flattened.columns.tolist() == ["PASSING_YDS", "RECEIVING_YDS"]


def test_special_teams_rows_use_week_one_dst_and_season_kicker_sources(monkeypatch):
    def fake_read_html(url):
        if "dst.php" in url:
            return [pd.DataFrame({"Player": ["Denver Broncos"], "FPTS": [8.3]})]
        return [pd.DataFrame({"Player": ["Brandon Aubrey DAL"], "FPTS": [153.0]})]

    monkeypatch.setattr(pd, "read_html", fake_read_html)

    rows = fetch_special_teams_rows().set_index("position")

    assert rows.loc["DST", "name"] == "Denver Broncos D/ST"
    assert rows.loc["DST", "team"] == "DEN"
    assert rows.loc["DST", "ranking_basis"] == "week_1_matchup_projection"
    assert rows.loc["K", "name"] == "Brandon Aubrey"
    assert rows.loc["K", "ranking_basis"] == "season_projection"
