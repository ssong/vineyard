You are an expert FastAPI engineer. Generate a production-ready API using:

- FastAPI with async endpoints
- SQLAlchemy 2.x async sessions
- Pydantic v2 for request/response models
- Alembic for migrations
- uv for dependency management
- pytest + httpx.AsyncClient for tests
- Structured logging via `structlog`

File layout: `app/main.py` (entry), `app/api/` (routers), `app/models/` (SQLAlchemy), `app/schemas/` (Pydantic), `app/services/`, `app/db.py`, `alembic/`, `tests/`, `pyproject.toml`, `.env.example`.

Generate every file the project needs to `uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app` cleanly.
