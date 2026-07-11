import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from projection_importer import import_projection_csv


def test_importer_normalizes_common_columns(tmp_path):
    path = tmp_path / "licensed.csv"
    pd.DataFrame(
        [
            {"Player Name": "Runner One", "POS": "RB1", "TM": "TST", "FPTS": 250, "RK": 4},
            {"Player Name": "Receiver One", "POS": "WR", "TM": "TST", "FPTS": 240, "RK": 5},
        ]
    ).to_csv(path, index=False)

    output = import_projection_csv(path, scoring="half_ppr", source_name="Licensed export")

    assert output["name"].tolist() == ["Runner One", "Receiver One"]
    assert output["position"].tolist() == ["RB", "WR"]
    assert set(output["projection_method"]) == {"user_supplied"}
    assert output.attrs["provider"] == "user_csv"
    assert output.attrs["scoring"] == "half_ppr"


def test_importer_requires_projection_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([{"player": "No Points", "position": "RB"}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="projected_fantasy_points"):
        import_projection_csv(path, scoring="ppr")


def test_importer_rejects_duplicate_identity(tmp_path):
    path = tmp_path / "duplicates.csv"
    pd.DataFrame(
        [
            {"player": "Same Player", "position": "RB", "fpts": 200},
            {"player": "Same Player", "position": "RB", "fpts": 190},
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate"):
        import_projection_csv(path, scoring="ppr")
