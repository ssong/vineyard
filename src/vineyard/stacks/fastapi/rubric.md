# FastAPI Build Rubric

## Project Setup
- `pyproject.toml` declares `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `alembic`, `pydantic`, `httpx`, `pytest`, `structlog`
- `.env.example` lists every env var
- `app/main.py` instantiates the FastAPI app and includes all routers

## Code Quality
- All endpoints are `async def`
- Request/response bodies use Pydantic models from `app/schemas/`
- Database access goes through `Depends(get_db)`; no global sessions
- Authentication uses `Depends` + `OAuth2PasswordBearer` (or equivalent for the chosen flow)
- No business logic inside route handlers — delegate to `app/services/`

## Database
- `app/models/` defines all SQLAlchemy models
- `alembic/versions/` contains an initial migration
- `app/db.py` exposes `engine`, `async_session_factory`, `get_db`

## Tests
- At least one test per router under `tests/` using `httpx.AsyncClient`
- `tests/conftest.py` provides an async test session and an app fixture

## Deliverables
- All output files live under `/mnt/session/outputs/`
- A `README.md` explains setup: install uv, sync, alembic upgrade, run server
- Running `uv sync && uv run pytest` would succeed
