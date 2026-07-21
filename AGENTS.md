# Repository Guidelines

## Project Structure & Module Organization

Core application code lives in `src/fantasy_draft/`. Domain logic is grouped into `draft/`, `board/`, `assistant/`, and `validation/`; FastAPI routes and schemas are under `api/`, while packaged command-line entry points are in `cli/`. Use `scripts/` for data pipelines and compatibility CLIs, not for reusable domain logic. The mobile interface is plain HTML, CSS, and JavaScript in `frontend/`. Tests live in `tests/`, documentation in `docs/`, checked-in inputs in `data/`, and generated rankings or boards in `outputs/`.

## Build, Test, and Development Commands

Create and activate a Python 3.12 virtual environment, then install dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

- `pytest` runs the complete test suite configured in `pyproject.toml`.
- `pytest tests/test_api.py -q` runs one focused module.
- `draft-server` starts the local FastAPI server at `127.0.0.1:8000`.
- `python scripts/cli.py --validate-board` checks the current draft-board artifact.
- `python scripts/live_draft.py interactive <session>` opens the terminal draft workflow.

## Coding Style & Naming Conventions

Follow standard PEP 8 conventions: four-space indentation, `snake_case` for functions and modules, `PascalCase` for classes, and uppercase constants. Add type hints to public interfaces and keep domain state deterministic and auditable. Prefer small modules in `src/fantasy_draft/` over expanding legacy scripts. No formatter or linter is currently configured; match surrounding code and keep imports grouped as standard library, third-party, then local.

## Testing Guidelines

Pytest is the test framework. Name files `test_<feature>.py` and tests `test_<behavior>`. Put shared fixtures in `tests/conftest.py`. Cover successful behavior and failure cases, especially session persistence, pick validation, API mutations, and deterministic fallback behavior. Run the full suite before submitting changes; no numeric coverage threshold is enforced.

## Commit & Pull Request Guidelines

Recent commits use short, informal summaries describing the delivered behavior. Prefer a concise imperative subject such as `add tier-aware board filters`, and keep each commit focused. Pull requests should explain user-visible impact, list verification commands, link relevant issues, and call out changes to data contracts or generated artifacts. Include screenshots for `frontend/` changes. Never commit `.env`, API keys, private session files, or credentials embedded in logs and screenshots.
