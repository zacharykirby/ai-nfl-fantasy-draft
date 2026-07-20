"""Read models for the full mobile board, roster, and draft log."""

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from fantasy_draft.draft.cockpit import player_view
from fantasy_draft.draft.recommendations import DraftRecommendationEngine, tier_number
from fantasy_draft.draft.session import BOARD_POSITIONS, DraftSession, PlayerNotFoundError


class DraftViewsService:
    def __init__(self, session: DraftSession):
        self.session = session

    def board(
        self,
        position: Optional[str] = None,
        available_only: bool = True,
    ) -> Dict[str, Any]:
        positions = [position.upper()] if position else list(BOARD_POSITIONS)
        invalid = [item for item in positions if item not in BOARD_POSITIONS]
        if invalid:
            raise ValueError("position must be QB, RB, WR, or TE")
        drafted = self.session.drafted_ids()
        result = {}
        for role in positions:
            players = [
                player
                for player in self.session.payload["board"]["players"]
                if player.get("position") == role
                and (not available_only or player["player_id"] not in drafted)
            ]
            players.sort(
                key=lambda player: (
                    tier_number(player.get("tier")),
                    int(player.get("position_rank") or 999),
                )
            )
            tiers: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
            for player in players:
                item = player_view(player)
                item["available"] = player["player_id"] not in drafted
                tiers[tier_number(player.get("tier"))].append(item)
            result[role] = {
                "count": len(players),
                "tiers": [
                    {"tier": tier, "count": len(items), "players": items}
                    for tier, items in sorted(tiers.items())
                ],
            }
        return {
            "schema_version": "1.0",
            "available_only": available_only,
            "positions": result,
            "current_pick": self.session.current_pick,
        }

    def player_detail(self, player_id: str) -> Dict[str, Any]:
        player = self.session.player_index().get(player_id)
        if not player:
            raise PlayerNotFoundError("Player is not on this session board")
        selection = next(
            (
                event
                for event in self.session.active_selections()
                if event["player_id"] == player_id
            ),
            None,
        )
        detail = dict(player_view(player))
        detail.update(
            {
                "available": selection is None,
                "drafted": (
                    {
                        "overall_pick": selection["overall_pick"],
                        "round": selection["round"],
                        "team": selection["team"],
                    }
                    if selection else None
                ),
                "score": player.get("score"),
                "age": player.get("age"),
                "projection_source": player.get("projection_source"),
                "news": player.get("news", {}),
                "evidence": player.get("evidence", {}),
            }
        )
        return {"player": detail, "current_pick": self.session.current_pick}

    def roster(self) -> Dict[str, Any]:
        selections = [
            event
            for event in self.session.active_selections()
            if event["team"] == self.session.user_team
        ]
        index = self.session.player_index()
        players = []
        for event in selections:
            item = player_view(index[event["player_id"]])
            item["drafted_at"] = {
                "overall_pick": event["overall_pick"],
                "round": event["round"],
            }
            players.append(item)

        engine = DraftRecommendationEngine(self.session)
        needs = engine.roster_needs()
        bye_players: Dict[int, List[str]] = defaultdict(list)
        missing_byes = []
        for player in players:
            week = player.get("bye_week")
            if week:
                bye_players[int(week)].append(player["player"])
            else:
                missing_byes.append(player["player"])
        bye_weeks = [
            {"week": week, "players": names, "conflict": len(names) > 1}
            for week, names in sorted(bye_players.items())
        ]
        return {
            "schema_version": "1.0",
            "team": self.session.user_team,
            "players": players,
            "counts": dict(Counter(player["position"] for player in players)),
            "needs": needs,
            "bye_summary": {
                "weeks": bye_weeks,
                "conflict_count": sum(item["conflict"] for item in bye_weeks),
                "missing": missing_byes,
            },
            "current_pick": self.session.current_pick,
        }

    def draft_log(
        self,
        team: Optional[int] = None,
        position: Optional[str] = None,
    ) -> Dict[str, Any]:
        if team is not None and not 1 <= int(team) <= self.session.league_size:
            raise ValueError("team must be within the configured league size")
        selected_position = position.upper() if position else None
        if selected_position and selected_position not in BOARD_POSITIONS:
            raise ValueError("position must be QB, RB, WR, or TE")
        undos = {
            event["target_event_id"]: event
            for event in self.session.payload["events"]
            if event["type"] == "undo"
        }
        picks = []
        for event in self.session.payload["events"]:
            if event["type"] != "selection":
                continue
            if team is not None and event["team"] != int(team):
                continue
            if selected_position and event["position"] != selected_position:
                continue
            undo = undos.get(event["id"])
            picks.append(
                {
                    "event_id": event["id"],
                    "overall_pick": event["overall_pick"],
                    "round": event["round"],
                    "team": event["team"],
                    "player_id": event["player_id"],
                    "player": event["player"],
                    "position": event["position"],
                    "status": "undone" if undo else "active",
                    "undone_at": undo.get("created_at") if undo else None,
                }
            )
        return {
            "schema_version": "1.0",
            "filters": {"team": team, "position": selected_position},
            "league_size": self.session.league_size,
            "picks": picks,
            "count": len(picks),
            "current_pick": self.session.current_pick,
        }
