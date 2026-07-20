#!/usr/bin/env python3
"""Compatibility entry point for the packaged live-draft CLI."""

from fantasy_draft.cli.live_draft import *  # noqa: F401,F403
from fantasy_draft.cli.live_draft import main


if __name__ == "__main__":
    raise SystemExit(main())
