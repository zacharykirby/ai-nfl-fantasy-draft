"""Compose the read model used by draft-night interfaces."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fantasy_draft.draft.recommendations import DraftRecommendationEngine, MODES
from fantasy_draft.draft.session import BOARD_POSITIONS, DraftSession, normalize_name


def player_view(player: Dict[str, Any]) -> Dict[str, Any]:
    """Return the compact player contract shared with interface adapters."""
    return {
        "player_id": player.get("player_id"),
        "player": player.get("player"),
        "position": player.get("position"),
        "team": player.get("team"),
        "position_rank": player.get("position_rank"),
        "overall_rank": player.get("overall_rank"),
        "tier": player.get("tier"),
        "projected_points": player.get("projected_points"),
        "vorp": player.get("vorp"),
        "adp": player.get("adp"),
        "bye_week": player.get("bye_week"),
        "projection_method": player.get("projection_method"),
        "risk": player.get("risk", {}),
        "flags": player.get("flags", []),
    }


class DraftCockpitService:
    """Build one consistent snapshot from an active draft session."""

    def __init__(self, session: DraftSession):
        self.session = session

    def search(
        self,
        query: str,
        position: Optional[str] = None,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        normalized = normalize_name(query)
        if not normalized:
            return []
        position = position.upper() if position else None
        candidates = self.session.available_players(position)
        prefix = []
        contains = []
        for player in candidates:
            name = normalize_name(str(player.get("player", "")))
            if name.startswith(normalized):
                prefix.append(player)
            elif normalized in name:
                contains.append(player)
        return [player_view(player) for player in (prefix + contains)[:limit]]

    def available(
        self,
        position: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if position and position.upper() not in BOARD_POSITIONS:
            raise ValueError("position must be QB, RB, WR, or TE")
        return [
            player_view(player)
            for player in self.session.available_players(position)[:limit]
        ]

    def snapshot(self, mode: str = "balanced", per_position: int = 5) -> Dict[str, Any]:
        if mode not in MODES:
            raise ValueError("mode must be safe, balanced, or upside")
        summary = self.session.summary()
        current_pick = int(summary["current_pick"])
        next_user_pick = summary["next_user_pick"]
        recommendation = None
        signals: Dict[str, Any] = {
            "roster_needs": {},
            "tiers": {},
            "position_run": {},
        }
        if self.session.current_team is not None:
            recommendation = DraftRecommendationEngine(self.session).recommend(
                mode=mode, alternatives=4
            )
            signals = recommendation["signals"]

        tiers = signals.get("tiers", {})
        tier_alerts = [
            {
                "position": position,
                "tier": state.get("best_tier"),
                "remaining": state.get("remaining_in_best_tier", 0),
                "next_tier": state.get("next_tier"),
            }
            for position, state in tiers.items()
            if state.get("tier_drop_imminent")
        ]
        active = self.session.active_selections()
        session_meta = self.session.payload["session"]
        board = self.session.payload["board"]
        return {
            "schema_version": "1.0",
            "session": {
                "id": session_meta["id"],
                "name": session_meta["name"],
                "status": session_meta["status"],
                "revision": session_meta["updated_at"],
                "round": min(
                    self.session.rounds,
                    ((current_pick - 1) // self.session.league_size) + 1,
                ),
                "current_pick": current_pick,
                "current_team": summary["current_team"],
                "user_team": self.session.user_team,
                "next_user_pick": next_user_pick,
                "picks_until_user": (
                    max(0, int(next_user_pick) - current_pick)
                    if next_user_pick is not None else None
                ),
                "selections": summary["selections"],
                "available": summary["available"],
            },
            "league": dict(self.session.payload["league"]),
            "user_roster": [player_view(player) for player in self.session.roster()],
            "recent_picks": [
                {
                    "event_id": event["id"],
                    "overall_pick": event["overall_pick"],
                    "round": event["round"],
                    "team": event["team"],
                    "player": event["player"],
                    "position": event["position"],
                }
                for event in active[-8:]
            ],
            "recommendation": recommendation,
            "best_available": self.available(limit=5),
            "top_available_by_position": {
                position: self.available(position, per_position)
                for position in BOARD_POSITIONS
            },
            "tier_alerts": tier_alerts,
            "position_run": signals.get("position_run", {}),
            "health": {
                "board": "ready_snapshot",
                "board_generated_at": board.get("generated_at"),
                "model": "configured" if os.getenv("OPENROUTER_API_KEY") else "offline",
                "autosave": "ok" if self.session.path.exists() else "missing",
                "autosave_updated_at": _file_timestamp(self.session.path),
            },
        }


def _file_timestamp(path: Path) -> Optional[str]:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return modified.isoformat()
