#!/usr/bin/env python3
"""Position-first draft board generation and validation.

The draft board is the stable contract between data/ranking code and live draft
clients. It intentionally contains facts and evidence, not round-by-round picks.
"""

import json
import csv
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fantasy_draft.validation.projections import validate_projection_file
from fantasy_draft.board.tiers import VORP_TIER_CONFIG, rank_and_tier_by_vorp


SKILL_POSITIONS = ("QB", "RB", "WR", "TE")
SPECIAL_TEAMS_POSITIONS = ("DST", "K")
POSITIONS = (*SKILL_POSITIONS, *SPECIAL_TEAMS_POSITIONS)
# The canonical live-draft universe is deliberately deeper than a normal league.
# RB and WR receive most of the reserve because late-round picks, handcuffs, and
# waiver-adjacent depth are concentrated at those positions.
DEFAULT_POSITION_LIMITS = {"QB": 40, "RB": 110, "WR": 140, "TE": 40, "DST": 10, "K": 10}
MINIMUM_SPECIAL_TEAMS_ENTRIES = 10
SCHEMA_VERSION = "1.0"
FRESHNESS_ISSUE_CODES = {
    "projection_data_stale",
    "projection_retrieval_time_missing",
}
NAME_SUFFIX_PATTERN = re.compile(r"\s+(?:jr|sr|ii|iii|iv|v)$", re.IGNORECASE)
PLAYER_NAME_ALIASES = {
    "cam ward": "cameron ward",
    "ken walker": "kenneth walker",
}


def normalize_player_identity(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("’", "'").replace(".", "")
    text = NAME_SUFFIX_PATTERN.sub("", text)
    normalized = re.sub(r"[^a-z0-9']+", " ", text).strip()
    return PLAYER_NAME_ALIASES.get(normalized, normalized)


@dataclass
class LeagueConfig:
    """Settings that influence how a board should eventually be interpreted."""

    name: str = "Default half-PPR league"
    scoring: str = "half_ppr"
    league_size: int = 10
    starters: Dict[str, int] = field(
        default_factory=lambda: {
            "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1
        }
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

    def load_special_teams(self, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Load K/DST directly from projections so they never enter skill VORP."""
        source = _normalize_source_path(metadata.get("projection_source"))
        if source is None:
            return []
        if not source.is_absolute():
            source = self.rankings_path.parent.parent / source
        if not source.exists():
            return []
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = []
            for row in csv.DictReader(handle):
                position = str(row.get("position") or "").upper()
                if position not in SPECIAL_TEAMS_POSITIONS:
                    continue
                rows.append({
                    "name": row.get("name"),
                    "pos": position,
                    "team": row.get("team"),
                    "bye_week": row.get("bye_week"),
                    "projection_rank": row.get("rank"),
                    "projection_tier": row.get("tier"),
                    "projected_fantasy_points": row.get("projected_fantasy_points"),
                    "adp": row.get("adp"),
                    "projection_method": row.get("projection_method"),
                    "projection_data_source": row.get("source"),
                    "ranking_basis": row.get("ranking_basis") or (
                        "week_1_matchup_projection" if position == "DST" else "season_projection"
                    ),
                })
        return rows

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
            "tier": self._integer(
                raw.get("vorp_tier"),
                self._tier(raw.get("tier", raw.get("projection_tier"))),
            ),
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
                "latest_event": raw.get("news_latest_event")
                if isinstance(raw.get("news_latest_event"), dict) else None,
                "actionable_events": raw.get("news_actionable_events")
                if isinstance(raw.get("news_actionable_events"), list) else [],
            },
            "flags": [str(flag) for flag in flags],
            "evidence": {
                "weighted_historical_points": round(
                    self._number(raw.get("weighted_historical_points")), 2
                ),
                "weighted_historical_points_per_game": round(
                    self._number(raw.get("weighted_historical_points_per_game")), 2
                ),
                "historical_availability_rate": round(
                    self._number(raw.get("historical_availability_rate")), 3
                ),
                "historical_seasons": self._integer(raw.get("historical_seasons_count")),
                "score_breakdown": raw.get("score_breakdown", {}),
                "tier_gap_from_previous": raw.get("tier_gap_from_previous"),
                "tier_boundary_reason": raw.get("tier_boundary_reason"),
                "tier_gap_threshold": raw.get("tier_gap_threshold"),
                "tier_max_size": raw.get("tier_max_size"),
            },
            "ranking_basis": raw.get("ranking_basis", "blended_skill_projection"),
        }

    def _special_player(self, raw: Dict[str, Any], position_rank: int) -> Dict[str, Any]:
        player = self._player(raw, position_rank)
        player["overall_rank"] = None
        player["vorp"] = None
        player["score"] = None
        player["tier"] = position_rank
        player["late_round_only"] = True
        player["news"] = {"sentiment": 0.0, "buzz": 0.0, "headline_count": 0,
                          "latest_event": None, "actionable_events": []}
        player["risk"] = {"level": "Not applicable", "injury_flag": False}
        player["evidence"] = {
            "ranking_basis": player["ranking_basis"],
            "projection_source": player["projection_source"],
        }
        return player

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
        requested_limits = limits or {}
        limits = dict(DEFAULT_POSITION_LIMITS)
        limits.update(requested_limits)
        metadata, rankings = self.load_rankings()
        special_teams = self.load_special_teams(metadata)

        roles: Dict[str, List[Dict[str, Any]]] = {}
        eligible_role_counts: Dict[str, int] = {}
        for position in POSITIONS:
            source_rows = rankings if position in SKILL_POSITIONS else special_teams
            candidates = [
                player for player in source_rows
                if str(player.get("pos", player.get("position", ""))).upper() == position
                and self._number(player.get("projected_fantasy_points")) > 0
            ]
            if position in SPECIAL_TEAMS_POSITIONS:
                candidates.sort(key=lambda player: (
                    -self._number(player.get("projected_fantasy_points")),
                    self._integer(player.get("projection_rank"), 999),
                ))
            else:
                candidates = rank_and_tier_by_vorp(candidates, position)
            unique_candidates = []
            seen_names = set()
            for player in candidates:
                identity = normalize_player_identity(
                    player.get("name", player.get("player", ""))
                )
                if not identity or identity in seen_names:
                    continue
                seen_names.add(identity)
                unique_candidates.append(player)
            eligible_role_counts[position] = len(unique_candidates)
            limit = max(0, int(limits.get(position, 0)))
            roles[position] = [
                (self._special_player if position in SPECIAL_TEAMS_POSITIONS else self._player)(player, index)
                for index, player in enumerate(unique_candidates[:limit], 1)
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
                "news_analyzed_at": metadata.get("news_analyzed_at"),
                "news_players_found": metadata.get("news_players_found", 0),
                "news_headlines_analyzed": metadata.get("news_headlines_analyzed", 0),
                "news_ranking_adjustments_enabled": bool(
                    metadata.get("news_ranking_adjustments_enabled", False)
                ),
                "ranking_replacement_model": metadata.get("replacement_model"),
                "ranking_method": "position_vorp_then_score_then_source_rank",
                "tiering_method": {
                    "method": "adjacent_vorp_gap_with_max_size",
                    "metric": "VORP",
                    "position_config": VORP_TIER_CONFIG,
                },
                "special_teams_ranking_method": {
                    "DST": "week_1_matchup_projection",
                    "K": "season_projection",
                    "excluded_from_skill_vorp": True,
                },
                "ranking_count": len(rankings),
                "role_counts": {position: len(players) for position, players in roles.items()},
                "eligible_role_counts": eligible_role_counts,
                "role_limit_exclusions": {
                    position: max(0, eligible_role_counts[position] - len(roles[position]))
                    for position in POSITIONS
                },
            },
            "league": asdict(league),
            "roles": roles,
        }
        report = validate_board(board, project_root=self.rankings_path.parent.parent)
        board["health"] = report
        return board

    def write(self, board: Dict[str, Any], output_path: Path = Path("outputs/draft_board.json")) -> Path:
        from fantasy_draft.board.fingerprint import stamp_board_fingerprint

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stamp_board_fingerprint(board)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(board, handle, indent=2)
            handle.write("\n")
        return output_path


def _normalize_source_path(source: Any) -> Optional[Path]:
    if not source or source in {"unknown", "none", "historical_fantasy_points_fallback"}:
        return None
    return Path(str(source).replace("\\", "/"))


def _health_report(
    issues: Iterable[ValidationIssue],
    metrics: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    issue_list = list(issues)
    errors = sum(issue.severity == "error" for issue in issue_list)
    warnings = sum(issue.severity == "warning" for issue in issue_list)
    return {
        "status": status or ("ready" if errors == 0 else "not_ready"),
        "error_count": errors,
        "warning_count": warnings,
        "issues": [asdict(issue) for issue in issue_list],
        **({"metrics": metrics or {}} if metrics is not None else {}),
    }


def _validate_board_snapshot(board: Dict[str, Any]) -> Dict[str, Any]:
    """Validate only the portable board contract, not its external provenance."""
    from fantasy_draft.board.fingerprint import verify_board_fingerprint

    issues: List[ValidationIssue] = []
    metadata = board.get("metadata", {})
    roles = board.get("roles", {})
    starters = (board.get("league") or {}).get("starters") or {}

    if board.get("schema_version") != SCHEMA_VERSION:
        issues.append(ValidationIssue("error", "schema_version", "Unsupported board schema version"))
    if not metadata.get("season"):
        issues.append(ValidationIssue("error", "missing_season", "Board has no target season"))
    if metadata.get("board_fingerprint") and not verify_board_fingerprint(board)["matches"]:
        issues.append(ValidationIssue(
            "error",
            "board_fingerprint_mismatch",
            "Board content no longer matches its saved fingerprint",
        ))

    seen = set()
    for position in POSITIONS:
        players = roles.get(position)
        required = position in SKILL_POSITIONS or int(starters.get(position, 0) or 0) > 0
        if not required and (not isinstance(players, list) or not players):
            continue
        if not isinstance(players, list) or not players:
            issues.append(ValidationIssue("error", "empty_role", "{} rankings are empty".format(position)))
            continue
        if position in SPECIAL_TEAMS_POSITIONS and len(players) < MINIMUM_SPECIAL_TEAMS_ENTRIES:
            issues.append(ValidationIssue(
                "error",
                "special_teams_coverage_low",
                "{} has {} entries; minimum is {}".format(
                    position, len(players), MINIMUM_SPECIAL_TEAMS_ENTRIES
                ),
            ))
        for expected_rank, player in enumerate(players, 1):
            name = str(player.get("player", "")).strip()
            if not name or name == "Unknown":
                issues.append(ValidationIssue("error", "missing_player_name", "A {} player has no name".format(position)))
            identity = (normalize_player_identity(name), position)
            if identity in seen:
                issues.append(ValidationIssue("error", "duplicate_player", "Duplicate player: {} ({})".format(name, position)))
            seen.add(identity)
            if player.get("position") != position:
                issues.append(ValidationIssue("error", "position_mismatch", "{} is in the wrong role list".format(name)))
            if player.get("position_rank") != expected_rank:
                issues.append(ValidationIssue("error", "position_rank_gap", "{} has an invalid position rank".format(name)))
            if not player.get("projected_points"):
                issues.append(ValidationIssue("warning", "missing_projection", "{} has no projected points".format(name)))
            if position in SPECIAL_TEAMS_POSITIONS and player.get("vorp") not in (None, 0, 0.0):
                issues.append(ValidationIssue(
                    "error", "special_teams_vorp_present",
                    "{} must not be included in skill-position VORP".format(name),
                ))
    return _health_report(issues)


def _validate_board_source(
    board: Dict[str, Any], project_root: Path
) -> Tuple[Dict[str, Any], bool]:
    """Validate the normalized projection source and return whether freshness is known."""
    metadata = board.get("metadata", {})
    source = metadata.get("projection_source")
    issues: List[ValidationIssue] = []
    if source == "historical_fantasy_points_fallback":
        issues.append(ValidationIssue(
            "error", "historical_projection_fallback",
            "Historical results are being used as future projections",
        ))
        return _health_report(issues, metrics={}), False

    source_path = _normalize_source_path(source)
    if source_path is None:
        issues.append(ValidationIssue("error", "missing_projection_source", "Projection source is missing"))
        return _health_report(issues, metrics={}), False

    resolved_source = source_path if source_path.is_absolute() else Path(project_root) / source_path
    if not resolved_source.exists():
        issues.append(ValidationIssue(
            "error", "projection_source_not_found",
            "Projection source does not exist locally: {}".format(source_path),
        ))
        return _health_report(issues, metrics={}), False

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
    freshness_known = bool(projection_report.get("metrics", {}).get("retrieved_at"))
    return _health_report(issues, metrics=projection_report.get("metrics", {})), freshness_known


def runtime_board_health(
    board: Dict[str, Any], project_root: Path = Path(".")
) -> Dict[str, Any]:
    """Return authoritative snapshot, source, and freshness readiness."""
    snapshot = _validate_board_snapshot(board)
    projection, freshness_known = _validate_board_source(board, Path(project_root))
    projection_issues = [ValidationIssue(**issue) for issue in projection["issues"]]
    source_issues = [
        issue for issue in projection_issues if issue.code not in FRESHNESS_ISSUE_CODES
    ]
    freshness_issues = [
        issue for issue in projection_issues if issue.code in FRESHNESS_ISSUE_CODES
    ]
    source = _health_report(source_issues, metrics=projection.get("metrics", {}))
    freshness_metrics = {
        key: projection.get("metrics", {}).get(key)
        for key in ("retrieved_at", "age_days")
        if key in projection.get("metrics", {})
    }
    freshness = _health_report(
        freshness_issues,
        metrics=freshness_metrics,
        status=None if freshness_known else "unknown",
    )
    components_ready = all(
        component["status"] == "ready"
        for component in (snapshot, source, freshness)
    )
    all_issues = [
        *[ValidationIssue(**issue) for issue in source["issues"]],
        *[ValidationIssue(**issue) for issue in freshness["issues"]],
        *[ValidationIssue(**issue) for issue in snapshot["issues"]],
    ]
    combined = _health_report(all_issues)
    return {
        **combined,
        "status": "ready" if components_ready else "not_ready",
        "can_create_session": components_ready,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": board.get("metadata", {}).get("generated_at"),
        "snapshot": snapshot,
        "source": source,
        "freshness": freshness,
    }


def validate_board(board: Dict[str, Any], project_root: Path = Path(".")) -> Dict[str, Any]:
    """Return authoritative board health without mutating the board."""
    return runtime_board_health(board, project_root=project_root)


def load_board(path: Path = Path("outputs/draft_board.json")) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Draft board must be a JSON object")
    return payload


def board_project_root(path: Path) -> Path:
    """Resolve relative provenance paths for canonical and standalone boards."""
    path = Path(path)
    return path.parent.parent if path.parent.name == "outputs" else path.parent


def validate_board_path(path: Path) -> Dict[str, Any]:
    """Load and authoritatively validate one configured board path."""
    path = Path(path)
    return runtime_board_health(load_board(path), project_root=board_project_root(path))


def format_board(board: Dict[str, Any], top_n: int = 10, position: Optional[str] = None) -> str:
    selected = [position.upper()] if position else list(POSITIONS)
    lines = []
    for role in selected:
        lines.append("{} PRIORITIES".format(role))
        for player in board.get("roles", {}).get(role, [])[:top_n]:
            if role in SPECIAL_TEAMS_POSITIONS:
                lines.append(
                    "{rank:>2}. {name:<30} {team:<4} Proj {points:>5.1f} ({basis})".format(
                        rank=player["position_rank"], name=player["player"], team=player["team"],
                        points=player["projected_points"], basis=player.get("ranking_basis", "projection"),
                    )
                )
            else:
                lines.append(
                    "{rank:>2}. {name:<24} {team:<4} Tier {tier:<2} Proj {points:>6.1f} VORP {vorp:>6.1f}".format(
                        rank=player["position_rank"], name=player["player"], team=player["team"],
                        tier=player["tier"], points=player["projected_points"], vorp=player["vorp"],
                    )
                )
        lines.append("")
    return "\n".join(lines).rstrip()
