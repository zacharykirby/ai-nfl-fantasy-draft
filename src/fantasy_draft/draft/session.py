#!/usr/bin/env python3
"""Persistent, event-backed live fantasy draft sessions."""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4


SESSION_SCHEMA_VERSION = "1.0"
BOARD_POSITIONS = ("QB", "RB", "WR", "TE")


class DraftSessionError(ValueError):
    pass


class PlayerNotFoundError(DraftSessionError):
    pass


class AmbiguousPlayerError(DraftSessionError):
    def __init__(self, query: str, candidates: List[str]):
        self.query = query
        self.candidates = candidates
        super().__init__(
            "Ambiguous player '{}'. Matches: {}".format(query, ", ".join(candidates))
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("’", "'").replace(".", "")
    text = re.sub(r"\s+(?:jr|sr|ii|iii|iv|v)$", "", text, flags=re.IGNORECASE)
    normalized = re.sub(r"[^a-z0-9']+", " ", text).strip()
    return {"ken walker": "kenneth walker"}.get(normalized, normalized)


def snake_team_for_pick(overall_pick: int, league_size: int) -> int:
    if overall_pick < 1:
        raise ValueError("overall_pick must be positive")
    round_number = ((overall_pick - 1) // league_size) + 1
    offset = (overall_pick - 1) % league_size
    return offset + 1 if round_number % 2 else league_size - offset


def next_pick_for_team(current_pick: int, team: int, league_size: int, max_rounds: int) -> Optional[int]:
    total_picks = league_size * max_rounds
    for pick in range(current_pick, total_picks + 1):
        if snake_team_for_pick(pick, league_size) == team:
            return pick
    return None


def load_json(path: Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise DraftSessionError("JSON file must contain an object")
    return payload


def atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".{}.{}.tmp".format(path.name, uuid4().hex))
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def board_players(board: Dict[str, Any]) -> List[Dict[str, Any]]:
    players = []
    seen = set()
    for position in BOARD_POSITIONS:
        for raw in board.get("roles", {}).get(position, []):
            name = str(raw.get("player", "")).strip()
            identity = "{}:{}".format(position, normalize_name(name))
            if not name or identity in seen:
                continue
            seen.add(identity)
            player = dict(raw)
            player["player_id"] = identity
            players.append(player)
    return players


@dataclass
class PlayerMatch:
    player: Dict[str, Any]
    score: float


class DraftSession:
    def __init__(self, payload: Dict[str, Any], path: Path):
        self.payload = payload
        self.path = Path(path)
        self._validate_payload()

    @classmethod
    def create(
        cls,
        path: Path,
        board_path: Path,
        name: str,
        league_size: int,
        rounds: int,
        user_team: int,
        request_id: Optional[str] = None,
    ) -> "DraftSession":
        if not 2 <= league_size <= 32:
            raise DraftSessionError("league_size must be between 2 and 32")
        if not 1 <= user_team <= league_size:
            raise DraftSessionError("user_team must be between 1 and league_size")
        if rounds < 1:
            raise DraftSessionError("rounds must be positive")
        board = load_json(board_path)
        if board.get("health", {}).get("status") != "ready":
            raise DraftSessionError("Draft board is not ready for a live session")
        players = board_players(board)
        if not players:
            raise DraftSessionError("Draft board contains no players")
        required_players = league_size * rounds
        if len(players) < required_players:
            raise DraftSessionError(
                "Draft board has {} players but this draft requires {}. Rebuild with larger role limits.".format(
                    len(players), required_players
                )
            )

        now = utc_now()
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session": {
                "id": uuid4().hex,
                "name": name,
                "created_at": now,
                "updated_at": now,
                "status": "active",
            },
            "league": {
                "league_size": league_size,
                "rounds": rounds,
                "user_team": user_team,
                "scoring": board.get("league", {}).get("scoring", "unknown"),
                "starters": board.get("league", {}).get("starters", {}),
                "bench_size": board.get("league", {}).get("bench_size"),
            },
            "board": {
                "path": str(Path(board_path)),
                "schema_version": board.get("schema_version"),
                "generated_at": board.get("metadata", {}).get("generated_at"),
                "season": board.get("metadata", {}).get("season"),
                "player_count": len(players),
                "players": players,
            },
            "events": [],
        }
        if request_id:
            payload["session"]["creation_request_id"] = request_id
        session = cls(payload, path)
        session.save()
        return session

    @classmethod
    def load(cls, path: Path) -> "DraftSession":
        return cls(load_json(path), path)

    def _validate_payload(self) -> None:
        if self.payload.get("schema_version") != SESSION_SCHEMA_VERSION:
            raise DraftSessionError("Unsupported draft session schema")
        league = self.payload.get("league", {})
        if not league.get("league_size") or not league.get("rounds"):
            raise DraftSessionError("Draft session has invalid league settings")
        if not isinstance(self.payload.get("events"), list):
            raise DraftSessionError("Draft session events must be a list")
        players = self.payload.get("board", {}).get("players")
        if not isinstance(players, list) or not players:
            raise DraftSessionError("Draft session board snapshot is empty")

        active = set()
        expected_pick = 1
        for event in self.payload["events"]:
            if event.get("type") == "selection":
                if event.get("overall_pick") != expected_pick:
                    raise DraftSessionError("Selection history has a pick gap")
                player_id = event.get("player_id")
                if player_id in active:
                    raise DraftSessionError("Selection history drafts a player twice")
                active.add(player_id)
                expected_pick += 1
            elif event.get("type") == "undo":
                target_id = event.get("target_event_id")
                target = next(
                    (item for item in reversed(self.payload["events"][:self.payload["events"].index(event)])
                     if item.get("id") == target_id),
                    None,
                )
                if not target or target.get("type") != "selection":
                    raise DraftSessionError("Undo references an invalid selection")
                active.discard(target.get("player_id"))
                expected_pick -= 1
            else:
                raise DraftSessionError("Unknown draft event type")

    @property
    def league_size(self) -> int:
        return int(self.payload["league"]["league_size"])

    @property
    def rounds(self) -> int:
        return int(self.payload["league"]["rounds"])

    @property
    def user_team(self) -> int:
        return int(self.payload["league"]["user_team"])

    def active_selections(self) -> List[Dict[str, Any]]:
        active: List[Dict[str, Any]] = []
        undone = {
            event["target_event_id"] for event in self.payload["events"] if event["type"] == "undo"
        }
        for event in self.payload["events"]:
            if event["type"] == "selection" and event["id"] not in undone:
                active.append(event)
        return active

    @property
    def current_pick(self) -> int:
        return len(self.active_selections()) + 1

    @property
    def current_team(self) -> Optional[int]:
        if self.current_pick > self.league_size * self.rounds:
            return None
        return snake_team_for_pick(self.current_pick, self.league_size)

    def player_index(self) -> Dict[str, Dict[str, Any]]:
        return {player["player_id"]: player for player in self.payload["board"]["players"]}

    def drafted_ids(self) -> set:
        return {event["player_id"] for event in self.active_selections()}

    def available_players(self, position: Optional[str] = None) -> List[Dict[str, Any]]:
        drafted = self.drafted_ids()
        selected_position = position.upper() if position else None
        players = [
            player for player in self.payload["board"]["players"]
            if player["player_id"] not in drafted
            and (selected_position is None or player.get("position") == selected_position)
        ]
        return sorted(
            players,
            key=lambda player: (
                int(player.get("overall_rank") or 999),
                int(player.get("position_rank") or 999),
                -float(player.get("vorp") or 0),
            ),
        )

    def match_player(self, query: str, position: Optional[str] = None) -> Dict[str, Any]:
        normalized_query = normalize_name(query)
        if not normalized_query:
            raise PlayerNotFoundError("Player query cannot be empty")
        candidates = self.available_players(position=position)

        exact = [player for player in candidates if normalize_name(player["player"]) == normalized_query]
        if len(exact) == 1:
            return exact[0]

        suffix = [
            player for player in candidates
            if normalize_name(player["player"]).endswith(" " + normalized_query)
        ]
        if len(suffix) == 1:
            return suffix[0]
        if len(suffix) > 1:
            raise AmbiguousPlayerError(query, [player["player"] for player in suffix[:8]])

        prefix = [player for player in candidates if normalize_name(player["player"]).startswith(normalized_query)]
        if len(prefix) == 1:
            return prefix[0]
        if len(prefix) > 1:
            raise AmbiguousPlayerError(query, [player["player"] for player in prefix[:8]])

        scored = sorted(
            [
                PlayerMatch(
                    player,
                    SequenceMatcher(None, normalized_query, normalize_name(player["player"])).ratio(),
                )
                for player in candidates
            ],
            key=lambda match: match.score,
            reverse=True,
        )
        if not scored or scored[0].score < 0.72:
            suggestions = [match.player["player"] for match in scored[:3] if match.score >= 0.5]
            suffix = ". Suggestions: {}".format(", ".join(suggestions)) if suggestions else ""
            raise PlayerNotFoundError("No available player matched '{}'{}".format(query, suffix))
        if len(scored) > 1 and scored[1].score >= scored[0].score - 0.04:
            raise AmbiguousPlayerError(query, [match.player["player"] for match in scored[:5]])
        return scored[0].player

    def draft(
        self,
        query: str,
        team: Optional[int] = None,
        position: Optional[str] = None,
        request_id: Optional[str] = None,
        batch_request_id: Optional[str] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        if self.current_team is None:
            raise DraftSessionError("Draft is already complete")
        expected_team = self.current_team
        selected_team = expected_team if team is None else int(team)
        if selected_team != expected_team:
            raise DraftSessionError(
                "Pick {} belongs to team {}, not team {}".format(self.current_pick, expected_team, selected_team)
            )
        player = self.match_player(query, position=position)
        event = {
            "id": uuid4().hex,
            "type": "selection",
            "created_at": utc_now(),
            "overall_pick": self.current_pick,
            "round": ((self.current_pick - 1) // self.league_size) + 1,
            "team": selected_team,
            "player_id": player["player_id"],
            "player": player["player"],
            "position": player["position"],
        }
        if request_id:
            event["request_id"] = request_id
        if batch_request_id:
            event["batch_request_id"] = batch_request_id
        self.payload["events"].append(event)
        self.payload["session"]["updated_at"] = event["created_at"]
        if self.current_pick > self.league_size * self.rounds:
            self.payload["session"]["status"] = "complete"
        if persist:
            self.save()
        return event

    def undo(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        selections = self.active_selections()
        if not selections:
            raise DraftSessionError("There is no selection to undo")
        target = selections[-1]
        event = {
            "id": uuid4().hex,
            "type": "undo",
            "created_at": utc_now(),
            "target_event_id": target["id"],
            "overall_pick": target["overall_pick"],
            "player_id": target["player_id"],
            "player": target["player"],
        }
        if request_id:
            event["request_id"] = request_id
        self.payload["events"].append(event)
        self.payload["session"]["updated_at"] = event["created_at"]
        self.payload["session"]["status"] = "active"
        self.save()
        return event

    def roster(self, team: Optional[int] = None) -> List[Dict[str, Any]]:
        selected_team = self.user_team if team is None else int(team)
        index = self.player_index()
        return [
            index[event["player_id"]]
            for event in self.active_selections()
            if event["team"] == selected_team
        ]

    def summary(self) -> Dict[str, Any]:
        next_user_pick = next_pick_for_team(
            self.current_pick, self.user_team, self.league_size, self.rounds
        )
        return {
            "name": self.payload["session"]["name"],
            "status": self.payload["session"]["status"],
            "created_at": self.payload["session"]["created_at"],
            "updated_at": self.payload["session"]["updated_at"],
            "league_size": self.league_size,
            "rounds": self.rounds,
            "user_team": self.user_team,
            "current_pick": self.current_pick,
            "current_team": self.current_team,
            "next_user_pick": next_user_pick,
            "selections": len(self.active_selections()),
            "available": len(self.available_players()),
            "user_roster": self.roster(),
        }

    def save(self) -> None:
        atomic_write_json(self.path, self.payload)
