import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from data_ingest import FantasyDataIngester


def test_nflverse_seasonal_fallback_normalizes_current_schema(monkeypatch):
    ingester = FantasyDataIngester()
    current = pd.DataFrame(
        [
            {
                "player_id": "player-1",
                "player_name": "J.Doe",
                "player_display_name": "Jane Doe",
                "position": "WR",
                "position_group": "WR",
                "recent_team": "BUF",
                "season": 2025,
                "passing_interceptions": 2,
                "fantasy_points_ppr": 100,
            }
        ]
    )
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: current.copy())

    result = ingester._get_nflverse_player_stats(2025, "reg")

    assert result.loc[0, "interceptions"] == 2
    assert "position" not in result
    assert "recent_team" not in result
    assert "player_name" not in result


def test_ingestion_refuses_to_save_partial_historical_window(monkeypatch):
    ingester = FantasyDataIngester()
    monkeypatch.setattr(
        ingester,
        "get_seasonal_data",
        lambda years: pd.DataFrame([{"player_id": "p", "season": 2024}]),
    )
    monkeypatch.setattr(ingester, "get_weekly_data", lambda years: pd.DataFrame())
    monkeypatch.setattr(ingester, "get_roster_data", lambda years: pd.DataFrame())
    monkeypatch.setattr(ingester, "get_combine_data", lambda: pd.DataFrame())

    with pytest.raises(RuntimeError, match="2025"):
        ingester.get_fantasy_data([2024, 2025])
