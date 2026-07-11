#!/usr/bin/env python3
"""Position-first draft board generation and validation.

The draft board is the stable contract between data/ranking code and live draft
clients. It intentionally contains facts and evidence, not round-by-round picks.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from projection_validator import validate_projection_file


POSITIONS = ("QB", "RB", "WR", "TE")
DEFAULT_POSITION_LIMITS = {"QB": 20, "RB": 50, "WR": 60, "TE": 20}
SCHEMA_VERSION = "1.0"


@dataclass
class LeagueConfig:
    """Settings that influence how a board should eventually be interpreted."""

    name: str = "Default half-PPR league"
    scoring: str = "half_ppr"
    league_size: int = 10
    starters: Dict[str, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1}
    )
    bench_size: int = 6

    def validate(self) -> List[str]:
        errors = []
        if self.scoring not in {"standard", "half_ppr", "ppr"}:
            errors.append("scoring must be standard, half_ppr, or ppr")
        if not 2 <= self.league_size <= 32:
            errors.append("league_size must be between 2 and 32")
        if self.bench_size < 0:
            errors.append("bench_size cannot be negative")
        if any(value < 0 for value in self.starters.values()):
            errors.append("starter counts cannot be negative")
        return errors


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str


class DraftBoardBuilder:
    """Transform ranking output into top-N lists for each fantasy position."""

    def __init__(self, rankings_path: Path = Path("outputs/player_rankings.json")):
        self.rankings_path = Path(rankings_path)

    def load_rankings(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        if not self.rankings_path.exists():
            raise FileNotFoundError("Ranking file not found: {}".format(self.rankings_path))
        with self.rankings_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return {}, payload
        if not isinstance(payload, dict) or not isinstance(payload.get("rankings"), list):
            raise ValueError("Ranking file must be a list or contain a rankings list")
        metadata = payload.get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}, payload["rankings"]

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return default if value is None else float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _integer(value: Any, default: int = 0) -> int:
        try:
            return default if value is None else int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _tier(value: Any) -> int:
        text = str(value or "")
        digits = "".join(char for char in text if char.isdigit())
        return int(digits) if digits else 99

    def _player(self, raw: Dict[str, Any], position_rank: int) -> Dict[str, Any]:
        position = str(raw.get("pos", raw.get("position", "Unknown"))).upper()
        projection_rank = self._integer(raw.get("projection_rank"), 999)
        flags = raw.get("flags", [])
        if not isinstance(flags, list):
            flags = [str(flags)]
        return {
            "player": str(raw.get("name", raw.get("player", "Unknown"))),
            "team": str(raw.get("team", "Unknown")),
            "position": position,
            "position_rank": position_rank,
            "overall_rank": projection_rank,
            "tier": self._tier(raw.get("projection_tier", raw.get("tier"))),
            "projected_points": round(self._number(raw.get("projected_fantasy_points")), 2),
            "vorp": round(self._number(raw.get("VORP", raw.get("vorp_score"))), 2),
            "score": round(self._number(raw.get("score", raw.get("total_score"))), 2),
            "adp": round(self._number(raw.get("adp")), 2) if raw.get("adp") is not None else (
                projection_rank if projection_rank < 999 else None
            ),
            "projection_method": str(raw.get("projection_method", "unknown")),
            "projection_source": str(raw.get("projection_data_source", "unknown")),
            "age": self._integer(raw.get("age")) or None,
            "bye_week": self._integer(raw.get("bye_week")) or None,
            "risk": {
                "level": str(raw.get("injury_risk", "Unknown")),
                "injury_flag": bool(raw.get("news_injury_flag", False)),
            },
            "news": {
                "sentiment": round(self._number(raw.get("news_sentiment_score")), 3),
                "buzz": round(self._number(raw.get("news_buzz_score")), 3),
                "headline_count": self._integer(raw.get("news_headline_count")),
            },
            "flags": [str(flag) for flag in flags],
            "evidence": {
                "weighted_historical_points": round(
                    self._number(raw.get("weighted_historical_points")), 2
                ),
                "historical_seasons": self._integer(raw.get("historical_seasons_count")),
                "score_breakdown": raw.get("score_breakdown", {}),
            },
        }

    @staticmethod
    def _sort_key(player: Dict[str, Any]) -> Tuple[float, float, int]:
        score = DraftBoardBuilder._number(player.get("score", player.get("total_score")))
        vorp = DraftBoardBuilder._number(player.get("VORP", player.get("vorp_score")))
        rank = DraftBoardBuilder._integer(player.get("projection_rank"), 999)
        return -score, -vorp, rank

    def build(
        self,
        league: Optional[LeagueConfig] = None,
        limits: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        league = league or LeagueConfig()
        league_errors = league.validate()
        if league_errors:
            raise ValueError("Invalid league config: {}".format("; ".join(league_errors)))
        limits = dict(DEFAULT_POSITION_LIMITS if limits is None else limits)
        metadata, rankings = self.load_rankings()

        roles: Dict[str, List[Dict[str, Any]]] = {}
        for position in POSITIONS:
            candidates = [
                player for player in rankings
                if str(player.get("pos", player.get("position", ""))).upper() == position
                and self._number(player.get("projected_fantasy_points")) > 0
            ]
            candidates.sort(key=self._sort_key)
            limit = max(0, int(limits.get(position, 0)))
            roles[position] = [
                self._player(player, index)
                for index, player in enumerate(candidates[:limit], 1)
            ]

        board = {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "season": metadata.get("target_season"),
                "source_rankings": str(self.rankings_path),
                "source_generated_at": metadata.get("generated_at"),
                "projection_source": metadata.get("projection_source"),
                "news_source": metadata.get("news_source", "none"),
                "ranking_method": "blended_score_then_vorp_then_source_rank",
                "ranking_count": len(rankings),
                "role_counts": {position: len(players) for position, players in roles.items()},
            },
            "league": asdict(league),
            "roles": roles,
        }
        report = validate_board(board, project_root=self.rankings_path.parent.parent)
        board["health"] = report
        return board

    def write(self, board: Dict[str, Any], output_path: Path = Path("outputs/draft_board.json")) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(board, handle, indent=2)
            handle.write("\n")
        return output_path


def _normalize_source_path(source: Any) -> Optional[Path]:
    if not source or source in {"unknown", "none", "historical_fantasy_points_fallback"}:
        return None
    return Path(str(source).replace("\\", "/"))


def validate_board(board: Dict[str, Any], project_root: Path = Path(".")) -> Dict[str, Any]:
    """Return a machine-readable board health report without mutating the board."""
    issues: List[ValidationIssue] = []
    metadata = board.get("metadata", {})
    roles = board.get("roles", {})

    if board.get("schema_version") != SCHEMA_VERSION:
        issues.append(ValidationIssue("error", "schema_version", "Unsupported board schema version"))
    if not metadata.get("season"):
        issues.append(ValidationIssue("error", "missing_season", "Board has no target season"))

    source = metadata.get("projection_source")
    if source == "historical_fantasy_points_fallback":
        issues.append(ValidationIssue(
            "error", "historical_projection_fallback",
            "Historical results are being used as future projections",
        ))
    else:
        source_path = _normalize_source_path(source)
        if source_path is None:
            issues.append(ValidationIssue("error", "missing_projection_source", "Projection source is missing"))
        elif not source_path.is_absolute() and not (Path(project_root) / source_path).exists():
            issues.append(ValidationIssue(
                "error", "projection_source_not_found",
                "Projection source does not exist locally: {}".format(source_path),
            ))
        else:
            resolved_source = source_path if source_path.is_absolute() else Path(project_root) / source_path
            season = metadata.get("season")
            try:
                expected_season = int(season)
            except (TypeError, ValueError):
                expected_season = None
            manifest = resolved_source.with_name(
                "projection_metadata_{}.json".format(expected_season or datetime.now().year)
            )
            projection_report = validate_projection_file(
                resolved_source,
                metadata_path=manifest,
                expected_season=expected_season,
            )
            for issue in projection_report["issues"]:
                issues.append(ValidationIssue(
                    issue["severity"],
                    issue["code"],
                    issue["message"],
                ))

    seen = set()
    for position in POSITIONS:
        players = roles.get(position)
        if not isinstance(players, list) or not players:
            issues.append(ValidationIssue("error", "empty_role", "{} rankings are empty".format(position)))
            continue
        for expected_rank, player in enumerate(players, 1):
            name = str(player.get("player", "")).strip()
            if not name or name == "Unknown":
                issues.append(ValidationIssue("error", "missing_player_name", "A {} player has no name".format(position)))
            identity = (name.casefold(), position)
            if identity in seen:
                issues.append(ValidationIssue("error", "duplicate_player", "Duplicate player: {} ({})".format(name, position)))
            seen.add(identity)
            if player.get("position") != position:
                issues.append(ValidationIssue("error", "position_mismatch", "{} is in the wrong role list".format(name)))
            if player.get("position_rank") != expected_rank:
                issues.append(ValidationIssue("error", "position_rank_gap", "{} has an invalid position rank".format(name)))
            if not player.get("projected_points"):
                issues.append(ValidationIssue("warning", "missing_projection", "{} has no projected points".format(name)))

    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    return {
        "status": "ready" if errors == 0 else "not_ready",
        "error_count": errors,
        "warning_count": warnings,
        "issues": [asdict(issue) for issue in issues],
    }


def load_board(path: Path = Path("outputs/draft_board.json")) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Draft board must be a JSON object")
    return payload


def format_board(board: Dict[str, Any], top_n: int = 10, position: Optional[str] = None) -> str:
    selected = [position.upper()] if position else list(POSITIONS)
    lines = []
    for role in selected:
        lines.append("{} PRIORITIES".format(role))
        for player in board.get("roles", {}).get(role, [])[:top_n]:
            lines.append(
                "{rank:>2}. {name:<24} {team:<4} Tier {tier:<2} Proj {points:>6.1f} VORP {vorp:>6.1f}".format(
                    rank=player["position_rank"], name=player["player"], team=player["team"],
                    tier=player["tier"], points=player["projected_points"], vorp=player["vorp"],
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip()
