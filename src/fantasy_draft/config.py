"""Application environment loading shared by packaged entry points."""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment() -> None:
    """Load the repository-local environment without overriding process values."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
