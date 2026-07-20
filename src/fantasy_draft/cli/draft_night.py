#!/usr/bin/env python3
"""Interactive draft-night terminal shell."""

import shlex
from collections import Counter
from typing import Callable, List, Optional

from fantasy_draft.assistant.service import LiveDraftAssistant
from fantasy_draft.draft.recommendations import DraftRecommendationEngine, MODES
from fantasy_draft.draft.session import AmbiguousPlayerError, DraftSession, DraftSessionError
from fantasy_draft.providers.openrouter import OpenRouterClient


HELP_TEXT = """Commands:
  draft PLAYER             Record the next selection (alias: d)
  undo                     Undo the latest selection (alias: u)
  recommend [MODE]         Show offline advice: safe, balanced, or upside (alias: r)
  ask QUESTION             Ask the model with deterministic fallback (alias: q)
  available [POS] [N]      Show best available players (alias: a)
  roster [TEAM]            Show your roster or another team's roster
  status                   Redraw the compact dashboard (alias: s)
  help                     Show commands (alias: h)
  quit                     Save and leave the session (aliases: exit, x)

A bare sentence or question is treated as `ask`. Quote player names only when needed."""


class DraftNightShell:
    def __init__(
        self,
        session: DraftSession,
        client: Optional[OpenRouterClient] = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ):
        self.session = session
        self.client = client or OpenRouterClient()
        self.input = input_func
        self.output = output_func

    def _write(self, value: str = "") -> None:
        self.output(value)

    def render_dashboard(self) -> str:
        summary = self.session.summary()
        current_pick = summary["current_pick"]
        round_number = ((current_pick - 1) // self.session.league_size) + 1
        model_state = "ONLINE ({})".format(self.client.model) if self.client.api_key else "OFFLINE (deterministic)"
        roster = summary["user_roster"]
        roster_text = ", ".join(
            "{} {}".format(player["position"], player["player"]) for player in roster
        ) or "empty"
        recent = self.session.active_selections()[-5:]
        recent_text = " | ".join(
            "{} {}:{}".format(event["overall_pick"], event["position"], event["player"])
            for event in recent
        ) or "none"
        available = self.session.available_players()[:5]
        available_text = "\n".join(
            "  {}. {} — {}{} — Tier {}".format(
                index, player["player"], player["position"], player["position_rank"], player["tier"]
            )
            for index, player in enumerate(available, 1)
        ) or "  none"
        tiers = DraftRecommendationEngine(self.session).tier_state()
        alerts = [
            "{}: {} left in Tier {}".format(
                position, state["remaining_in_best_tier"], state["best_tier"]
            )
            for position, state in tiers.items()
            if state["tier_drop_imminent"]
        ]
        alert_text = " | ".join(alerts) or "none"
        turn = "YOUR PICK" if summary["current_team"] == self.session.user_team else "Team {}".format(summary["current_team"])
        return "\n".join([
            "=" * 78,
            "{} | {} | Pick {} (Round {}) | {}".format(
                summary["name"], summary["status"].upper(), current_pick, round_number, turn
            ),
            "Your team: {} | Next pick: {} | Model: {}".format(
                self.session.user_team, summary["next_user_pick"], model_state
            ),
            "Autosave: {} | Board snapshot: {} players".format(
                self.session.path, self.session.payload["board"]["player_count"]
            ),
            "-" * 78,
            "Your roster: {}".format(roster_text),
            "Recent: {}".format(recent_text),
            "Tier alerts: {}".format(alert_text),
            "Best available:",
            available_text,
            "=" * 78,
        ])

    def _show_players(self, players: List[dict], limit: int) -> None:
        if not players:
            self._write("No matching available players.")
            return
        for player in players[:limit]:
            self._write(
                "{}{} {:<25} {:<4} Tier {} | Proj {:.1f} | VORP {:.1f}".format(
                    player["position"], player["position_rank"], player["player"],
                    player.get("team", ""), player.get("tier", 99),
                    float(player.get("projected_points", 0)), float(player.get("vorp", 0)),
                )
            )

    def _show_recommendation(self, mode: str) -> None:
        result = DraftRecommendationEngine(self.session).recommend(mode=mode, alternatives=4)
        primary = result["primary"]
        self._write("{}: {} ({}, {}) — confidence {:.0%}".format(
            mode.upper(), primary["player"], primary["position"], primary["team"], result["confidence"]
        ))
        for reason in primary["reasons"]:
            self._write("  - {}".format(reason))
        self._write("  Alternatives: {}".format(
            ", ".join("{} ({})".format(item["player"], item["position"]) for item in result["alternatives"])
        ))

    def _ask(self, question: str, mode: str = "balanced") -> None:
        self._write("Thinking with bounded draft context...")
        response = LiveDraftAssistant(self.session, client=self.client).ask(question, mode=mode)
        label = "MODEL" if response["source"] == "model" else "FALLBACK"
        self._write("{}: {}".format(label, response["answer"]))
        if response.get("recommendation"):
            self._write("  Recommendation: {} ({:.0%})".format(
                response["recommendation"], response["confidence"]
            ))
        if response.get("alternatives"):
            self._write("  Alternatives: {}".format(", ".join(response["alternatives"])))
        for caution in response.get("cautions", []):
            self._write("  Caution: {}".format(caution))

    def execute(self, command_line: str) -> bool:
        """Execute one command. Return False when the shell should exit."""
        command_line = command_line.strip()
        if not command_line:
            return True
        try:
            tokens = shlex.split(command_line)
        except ValueError as exc:
            self._write("ERROR: {}".format(exc))
            return True
        command = tokens[0].casefold()
        args = tokens[1:]

        try:
            if command in {"quit", "exit", "x"}:
                self.session.save()
                self._write("Saved {}. Good luck!".format(self.session.path))
                return False
            if command in {"help", "h", "?"}:
                self._write(HELP_TEXT)
            elif command in {"status", "s"}:
                self._write(self.render_dashboard())
            elif command in {"draft", "d"}:
                if not args:
                    raise DraftSessionError("Usage: draft PLAYER")
                event = self.session.draft(" ".join(args))
                self._write("Recorded pick {}: Team {} — {} ({})".format(
                    event["overall_pick"], event["team"], event["player"], event["position"]
                ))
                self._write(self.render_dashboard())
            elif command in {"undo", "u"}:
                event = self.session.undo()
                self._write("Undid pick {}: {}".format(event["overall_pick"], event["player"]))
                self._write(self.render_dashboard())
            elif command in {"recommend", "r"}:
                mode = args[0].casefold() if args else "balanced"
                if mode not in MODES:
                    raise DraftSessionError("Mode must be safe, balanced, or upside")
                self._show_recommendation(mode)
            elif command in {"ask", "q"}:
                if not args:
                    raise DraftSessionError("Usage: ask QUESTION")
                self._ask(" ".join(args))
            elif command in {"available", "a"}:
                position = None
                limit = 10
                if args and args[0].upper() in {"QB", "RB", "WR", "TE"}:
                    position = args.pop(0).upper()
                if args:
                    limit = int(args[0])
                self._show_players(self.session.available_players(position), limit)
            elif command == "roster":
                team = int(args[0]) if args else self.session.user_team
                roster = self.session.roster(team)
                self._write("Team {} roster:".format(team))
                self._show_players(roster, len(roster))
            else:
                # Natural language is read-only; explicit commands remain required
                # for every state mutation.
                self._ask(command_line)
        except (DraftSessionError, AmbiguousPlayerError, ValueError) as exc:
            self._write("ERROR: {}".format(exc))
        return True

    def run(self) -> None:
        self._write(self.render_dashboard())
        self._write("Type `help` for commands. Bare questions go to the assistant.")
        while True:
            try:
                command = self.input("draft> ")
            except (EOFError, KeyboardInterrupt):
                self._write("")
                self.session.save()
                self._write("Session saved.")
                break
            if not self.execute(command):
                break
