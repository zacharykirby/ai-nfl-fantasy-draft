import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import espn_projection_provider as provider
from espn_projection_provider import convert_ppr_points, parse_projection_pdf, projection_url


class FakePage:
    def __init__(self, text=""):
        self.text = text

    def extract_text(self, extraction_mode=None):
        assert extraction_mode == "layout"
        return self.text


class FakeReader:
    def __init__(self, _content):
        self.pages = [FakePage() for _ in range(45)]
        self.pages[34] = FakePage(
            "   Josh Allen                   BUF          1      369      17      509 340 3945 26 12 36 116 579 12\n"
        )
        self.pages[35] = FakePage(
            "   Bijan Robinson                ATL          2      352      17      286 1371 8 99 76 708 3 66% 18%\n"
        )
        self.pages[38] = FakePage(
            "  Ja'Marr Chase                 CIN          2      336      17      4 21 0 172 119 1507 11 1% 30%\n"
        )
        self.pages[43] = FakePage(
            "   Trey McBride                 ARZ          1      252      17      0 0 0 155 112 1068 6 0% 27%\n"
        )


def test_scoring_conversion_uses_receptions():
    assert convert_ppr_points(300, 80, "ppr") == 300
    assert convert_ppr_points(300, 80, "half_ppr") == 260
    assert convert_ppr_points(300, 80, "standard") == 220
    with pytest.raises(ValueError, match="scoring"):
        convert_ppr_points(300, 80, "points_per_first_down")


def test_pdf_parser_extracts_positions_and_normalizes_teams(monkeypatch):
    monkeypatch.setattr(provider, "PdfReader", FakeReader)

    frame = parse_projection_pdf(b"fake", scoring="half_ppr", source_url="https://example.test/guide.pdf")

    assert set(frame["position"]) == {"QB", "RB", "WR", "TE"}
    bijan = frame[frame["name"] == "Bijan Robinson"].iloc[0]
    assert bijan["receptions"] == 76
    assert bijan["projected_fantasy_points"] == 314
    assert frame[frame["name"] == "Trey McBride"].iloc[0]["team"] == "ARI"
    assert set(frame["projection_method"]) == {"published"}


def test_projection_url_is_season_aware():
    assert projection_url(2026).endswith("/26/NFLDK2026_CS_ClayProjections2026.pdf")
