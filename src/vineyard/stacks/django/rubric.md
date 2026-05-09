# Django Build Rubric

## Project Setup
- `pyproject.toml` declares `django>=5`, `djangorestframework`, `django-allauth`, `django-tailwind`, `psycopg`, `celery`, `pytest-django`
- `config/settings/base.py`, `dev.py`, `prod.py` exist and import correctly
- `manage.py` is at the project root and uses the dev settings module by default
- `.env.example` lists every env var

## Code Quality
- Each app under `apps/` has `models.py`, `views.py`, `urls.py`, `admin.py`, `serializers.py` (if it exposes API)
- Class-based views or DRF ViewSets used for API endpoints; function views for HTMX-driven HTML
- Django auth uses allauth providers configured for the chosen flow
- Celery tasks live in `apps/<app>/tasks.py`

## Database
- Migrations are present in `apps/<app>/migrations/`
- ForeignKey fields use `on_delete=` explicitly
- Indexes declared via `Meta.indexes` where queried frequently

## Tests
- At least one model test, one view test, one DRF API test under `tests/`
- `pytest.ini` (or `pyproject.toml [tool.pytest.ini_options]`) sets `DJANGO_SETTINGS_MODULE`

## Deliverables
- All output files live under `/mnt/session/outputs/`
- A `README.md` explains setup: install uv, sync, migrate, runserver
- Running `uv run python manage.py check` would succeed
