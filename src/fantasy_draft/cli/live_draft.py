#!/usr/bin/env python3
"""Noninteractive CLI for live draft session state."""

import argparse
import json
from pathlib import Path
from typing import Dict, List

from fantasy_draft.assistant.service import LiveDraftAssistant
from fantasy_draft.cli.draft_night import DraftNightShell
from fantasy_draft.draft.recommendations import DraftRecommendationEngine, MODES
from fantasy_draft.draft.session import AmbiguousPlayerError, DraftSession, DraftSessionError
from fantasy_draft.providers.openrouter import OpenRouterClient


DEFAULT_SESSIONS_DIR = Path("sessions")


def session_path(value: str) -> Path:
    path = Path(value)
    if path.suffix != ".json" and path.parent == Path("."):
        path = DEFAULT_SESSIONS_DIR / "{}.json".format(value)
    return path


def print_players(players: List[Dict], limit: int) -> None:
    for player in players[:limit]:
        print(
            "{position:<2} {rank:>2}  {name:<25} {team:<4} Tier {tier:<2} Proj {points:>6.1f}".format(
                position=player["position"],
                rank=player["position_rank"],
                name=player["player"],
                team=player.get("team", ""),
                tier=player.get("tier", 99),
                points=float(player.get("projected_points", 0)),
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live fantasy draft session state")
    commands = parser.add_subparsers(dest="command", required=True)

    new = commands.add_parser("new", help="Create a draft session")
    new.add_argument("name")
    new.add_argument("--board", type=Path, default=Path("outputs/draft_board.json"))
    new.add_argument("--league-size", type=int, default=10)
    new.add_argument("--rounds", type=int, default=15)
    new.add_argument("--user-team", type=int, required=True)

    for command in ("status", "undo", "available", "roster", "recommend", "ask", "interactive"):
        sub = commands.add_parser(command)
        sub.add_argument("session")
        if command == "available":
            sub.add_argument("--position", choices=["QB", "RB", "WR", "TE"])
            sub.add_argument("--top", type=int, default=10)
        if command == "roster":
            sub.add_argument("--team", type=int)
        if command == "recommend":
            sub.add_argument("--mode", choices=MODES, default="balanced")
            sub.add_argument("--alternatives", type=int, default=4)
            sub.add_argument("--json", action="store_true", dest="as_json")
        if command == "ask":
            sub.add_argument("question")
            sub.add_argument("--mode", choices=MODES, default="balanced")
            sub.add_argument("--model", default=None)
            sub.add_argument("--timeout", type=int, default=25)
            sub.add_argument("--json", action="store_true", dest="as_json")
        if command == "interactive":
            sub.add_argument("--model", default=None)

    draft = commands.add_parser("draft", help="Record the next selection")
    draft.add_argument("session")
    draft.add_argument("player")
    draft.add_argument("--position", choices=["QB", "RB", "WR", "TE"])
    draft.add_argument("--team", type=int)

    commands.add_parser("list", help="List saved sessions")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "new":
            path = session_path(args.name)
            if path.exists():
                raise DraftSessionError("Session already exists: {}".format(path))
            session = DraftSession.create(
                path, args.board, args.name, args.league_size, args.rounds, args.user_team
            )
            print("Created {}".format(path))
            print("Current pick: {} (team {})".format(session.current_pick, session.current_team))
            return 0

        if args.command == "list":
            DEFAULT_SESSIONS_DIR.mkdir(exist_ok=True)
            paths = sorted(DEFAULT_SESSIONS_DIR.glob("*.json"))
            if not paths:
                print("No saved sessions")
            for path in paths:
                session = DraftSession.load(path)
                summary = session.summary()
                print("{}: pick {} | {} | {} selections".format(
                    path.stem, summary["current_pick"], summary["status"], summary["selections"]
                ))
            return 0

        session = DraftSession.load(session_path(args.session))
        if args.command == "interactive":
            DraftNightShell(session, client=OpenRouterClient(model=args.model)).run()
            return 0
        if args.command == "draft":
            event = session.draft(args.player, team=args.team, position=args.position)
            print("Pick {overall_pick}: Team {team} drafted {player} ({position})".format(**event))
            if session.current_team:
                print("Next: pick {} (team {})".format(session.current_pick, session.current_team))
            else:
                print("Draft complete")
        elif args.command == "undo":
            event = session.undo()
            print("Undid pick {}: {}".format(event["overall_pick"], event["player"]))
        elif args.command == "status":
            summary = session.summary()
            print("{} | {}".format(summary["name"], summary["status"].upper()))
            print("Current pick: {} | Team: {} | Your next pick: {}".format(
                summary["current_pick"], summary["current_team"], summary["next_user_pick"]
            ))
            print("Selections: {} | Available board players: {}".format(
                summary["selections"], summary["available"]
            ))
            print("Your roster:")
            print_players(summary["user_roster"], len(summary["user_roster"]))
        elif args.command == "available":
            print_players(session.available_players(args.position), args.top)
        elif args.command == "roster":
            roster = session.roster(args.team)
            print_players(roster, len(roster))
        elif args.command == "recommend":
            recommendation = DraftRecommendationEngine(session).recommend(
                mode=args.mode, alternatives=args.alternatives
            )
            if args.as_json:
                print(json.dumps(recommendation, indent=2))
            else:
                context = recommendation["generated_for"]
                if not context["is_user_pick"]:
                    print("NOTE: Current pick belongs to team {}; your next pick is {}.".format(
                        context["current_team"], context["next_user_pick"]
                    ))
                primary = recommendation["primary"]
                print("{} recommendation: {} ({}, {})".format(
                    recommendation["mode"].upper(), primary["player"],
                    primary["position"], primary["team"],
                ))
                print("Confidence: {:.0%} | Score: {:.1f}".format(
                    recommendation["confidence"], primary["recommendation_score"]
                ))
                for reason in primary["reasons"]:
                    print("- {}".format(reason))
                print("Alternatives:")
                for candidate in recommendation["alternatives"]:
                    print("- {} ({}) — {:.1f}".format(
                        candidate["player"], candidate["position"], candidate["recommendation_score"]
                    ))
        elif args.command == "ask":
            response = LiveDraftAssistant(
                session, client=OpenRouterClient(model=args.model)
            ).ask(args.question, mode=args.mode, timeout=args.timeout)
            if args.as_json:
                print(json.dumps(response, indent=2))
            else:
                if response["source"] == "deterministic_fallback":
                    print("OFFLINE/VALIDATION FALLBACK")
                else:
                    print("MODEL: {}".format(response["model"]))
                print(response["answer"])
                if response.get("recommendation"):
                    print("Recommendation: {} | Confidence: {:.0%}".format(
                        response["recommendation"], response["confidence"]
                    ))
                if response.get("alternatives"):
                    print("Alternatives: {}".format(", ".join(response["alternatives"])))
                for caution in response.get("cautions", []):
                    print("Caution: {}".format(caution))
        return 0
    except AmbiguousPlayerError as exc:
        print("ERROR: {}".format(exc))
        return 2
    except (DraftSessionError, FileNotFoundError, ValueError) as exc:
        print("ERROR: {}".format(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
