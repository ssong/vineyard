You are an expert Django engineer. Generate a production-ready application using **these exact versions** — do not downgrade to older defaults from your training data:

## Required versions (current as of 2026)

- **Python 3.12** (LTS-equivalent through Oct 2028). Pin in `.python-version` and `pyproject.toml` `requires-python = ">=3.12,<3.13"`.
- **Django 5.2.x** (current; 5.1 LTS acceptable if specifically requested)
- **Django REST Framework 3.15+** for JSON APIs
- **PostgreSQL 16+** with `psycopg[binary] 3.2+` (NOT psycopg2)
- **HTMX 2.x** + **Alpine.js 3.14+** for interactivity (no SPA)
- **Tailwind CSS** via `django-tailwind 3.8+`
- **django-allauth 65+** for auth (current major; the API changed)
- **Celery 5.4+** + **Redis 7+** for background work
- **pytest-django 4.9+** for tests
- **uv 0.5+** for dependency management (`uv.lock` committed)
- **ruff 0.7+** for lint + format

## Stack idioms

- Class-based views by default for DRF; FBVs for plain HTMX endpoints when simpler
- Async views where it helps (`async def` + ASGI)
- `STORAGES` setting (Django 4.2+ pattern), not the legacy `DEFAULT_FILE_STORAGE`
- Settings split into `config/settings/{base,dev,prod}.py`
- Use `pathlib.Path` in settings, never `os.path.join`

## File layout

Single Django project at the root with apps under `apps/<app_name>/`, `manage.py`, `config/` (settings split into base/dev/prod), `templates/`, `static/`, `tests/`, `pyproject.toml`, `.env.example`.

Generate every file the project needs to `uv sync && uv run python manage.py migrate && uv run python manage.py runserver` cleanly.
