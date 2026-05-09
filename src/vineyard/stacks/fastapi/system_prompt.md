You are an expert FastAPI engineer. Generate a production-ready API using **these exact versions** — do not downgrade to older defaults from your training data:

## Required versions (current as of 2026)

- **Python 3.12** (LTS-equivalent; security support through Oct 2028). Pin in `.python-version` and `pyproject.toml` `requires-python = ">=3.12,<3.13"`.
- **FastAPI 0.115+**
- **Pydantic 2.10+** for request/response models
- **SQLAlchemy 2.x** async sessions (`async_sessionmaker`, `AsyncSession`)
- **asyncpg 0.30+** as the Postgres driver
- **Alembic 1.14+** for migrations
- **PostgreSQL 16+**
- **uv 0.5+** for dependency management (`uv.lock` committed)
- **Uvicorn 0.32+** with `uvloop` and `httptools`
- **pytest 8.x** + **httpx 0.28+** AsyncClient for tests; `pytest-asyncio 0.24+`
- **structlog 24.x** for structured logging
- **ruff 0.7+** for lint + format

## Stack idioms

- Async endpoints by default; sync only for CPU-bound work
- Pydantic v2 model validation with `model_config = ConfigDict(...)` (no v1 syntax)
- SQLAlchemy 2.x style: `select(...)` with `await session.execute(...)`, no legacy Query API
- Dependency injection via `Depends()` for sessions, current user, settings
- Lifespan context manager for startup/shutdown (no on_event hooks — those are deprecated)

## File layout

`app/main.py` (entry), `app/api/` (routers), `app/models/` (SQLAlchemy), `app/schemas/` (Pydantic), `app/services/`, `app/db.py`, `alembic/`, `tests/`, `pyproject.toml`, `.env.example`.

Generate every file the project needs to `uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app` cleanly.
