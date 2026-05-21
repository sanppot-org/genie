# Repository Guidelines

## Project Structure & Module Organization

`genie` is a Python 3.12 FastAPI trading system with a Next.js dashboard. Backend code lives in `src/`: `api/` for routes and schemas, `service/` for business logic, `database/` for SQLAlchemy repositories and models, `strategy/` for trading strategies, and provider modules such as `hantu/` and `bithumb/`. Tests mirror these areas under `tests/`. Database migrations are in `alembic/versions/`, scripts in `scripts/`, docs in `docs/`, and frontend code in `web/` (`app/`, `components/`, `lib/`, `public/`). Agent role notes are in `AGENTS/`; project state notes are in `SOT/`.

## Build, Test, and Development Commands

- `uv sync`: install Python dependencies from `pyproject.toml` and `uv.lock`.
- `uv run uvicorn app:app --host 0.0.0.0 --port 8000`: run the backend API locally.
- `uv run pytest tests/`: run the Python test suite.
- `uv run ruff check src/ tests/`: lint imports, style, annotations, and bug-prone patterns.
- `uv run mypy src/`: type-check backend code.
- `uv run alembic upgrade head`: apply migrations after confirming the target database.
- `pnpm --dir web install`, `pnpm --dir web dev`, `pnpm --dir web build`, `pnpm --dir web lint`: manage and validate the frontend.

## Coding Style & Naming Conventions

Use Ruff and MyPy settings from `pyproject.toml`: Python 3.12, 180-character line limit, first-party imports under `src`, and Ruff rules `E,F,W,I,N,UP,ANN,B,A,C4`. Prefer typed functions for production code. Use `snake_case` for Python files, functions, and variables; `PascalCase` for classes and Pydantic/SQLAlchemy models. Frontend code uses TypeScript and existing Next.js/shadcn patterns.

## Testing Guidelines

Place tests under `tests/<domain>/test_*.py`, matching the changed module. Focus on business logic, data transformations, API behavior, repositories, and provider adapters. Mock exchange, DART, Google Sheets, Slack, and other network-facing clients unless an integration test requires them. Run `uv run pytest tests/` before backend submissions; add `pnpm --dir web lint` and `pnpm --dir web build` for frontend work.

## Commit & Pull Request Guidelines

Git history uses Conventional Commit prefixes such as `feat:`, `fix:`, and `docs:`; follow that style with concise Korean or English summaries. PRs should describe the change, list validation commands run, call out database migrations or scheduler changes, link relevant issues, and include screenshots for UI changes.

## Security & Configuration Tips

Never commit API keys, database passwords, Slack webhooks, or trading credentials. Environment files live under `config/genie/` and `web/.env.local`. Before any DB write command, confirm the resolved database host and profile; production and local profiles can be easy to confuse.
