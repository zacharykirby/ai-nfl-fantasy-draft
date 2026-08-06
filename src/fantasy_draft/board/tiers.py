"""Explainable VORP-gap tiers shared by ranking and board generation."""

from typing import Any, Dict, Iterable, List


VORP_TIER_CONFIG: Dict[str, Dict[str, float]] = {
    "QB": {"gap_threshold": 8.0, "max_tier_size": 6},
    "RB": {"gap_threshold": 10.0, "max_tier_size": 10},
    "WR": {"gap_threshold": 10.0, "max_tier_size": 10},
    "TE": {"gap_threshold": 8.0, "max_tier_size": 6},
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None else float(value)
    except (TypeError, ValueError):
        return default


def rank_and_tier_by_vorp(
    players: Iterable[Dict[str, Any]], position: str
) -> List[Dict[str, Any]]:
    """Sort one position by final VORP and derive tiers from adjacent drops."""
    config = VORP_TIER_CONFIG[position]
    threshold = float(config["gap_threshold"])
    max_size = int(config["max_tier_size"])
    ranked = sorted(
        (dict(player) for player in players),
        key=lambda player: (
            -_number(player.get("VORP", player.get("vorp_score"))),
            -_number(player.get("score", player.get("adjusted_score"))),
            int(_number(player.get("projection_rank"), 999)),
            str(player.get("name", player.get("player", ""))).casefold(),
        ),
    )

    tier = 1
    tier_size = 0
    previous_vorp = None
    for index, player in enumerate(ranked):
        vorp = _number(player.get("VORP", player.get("vorp_score")))
        gap = None if previous_vorp is None else previous_vorp - vorp
        reason = "position_leader" if index == 0 else "same_tier"
        if gap is not None and gap > threshold:
            tier += 1
            tier_size = 0
            reason = "vorp_gap"
        elif tier_size >= max_size:
            tier += 1
            tier_size = 0
            reason = "max_tier_size"
        tier_size += 1
        player["tier"] = "Tier {}".format(tier)
        player["vorp_tier"] = tier
        player["tier_gap_from_previous"] = None if gap is None else round(gap, 3)
        player["tier_boundary_reason"] = reason
        player["tier_gap_threshold"] = threshold
        player["tier_max_size"] = max_size
        previous_vorp = vorp
    return ranked
