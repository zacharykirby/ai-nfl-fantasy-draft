#!/usr/bin/env python3
"""Write the printable emergency draft board from the validated board contract."""

import argparse
import json
from pathlib import Path

from fantasy_draft.board import validate_board, write_cheatsheet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, default=Path("outputs/draft_board.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/emergency_draft_cheatsheet.md")
    )
    args = parser.parse_args()

    with args.board.open("r", encoding="utf-8") as handle:
        board = json.load(handle)
    health = validate_board(board, project_root=Path.cwd())
    output = write_cheatsheet(board, args.output, health)
    print(f"Wrote {output} ({health['status']}, {len(health['issues'])} issues)")


if __name__ == "__main__":
    main()
