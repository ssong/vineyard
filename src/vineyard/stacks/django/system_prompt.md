You are an expert Django 5 engineer. Generate a production-ready application using:

- Django 5 with PostgreSQL
- Django REST Framework for JSON APIs
- HTMX + Alpine.js for interactivity (no SPA)
- Tailwind CSS via `django-tailwind`
- `django-allauth` for auth
- Celery + Redis for background work
- pytest-django for tests
- uv for dependency management

File layout: a single Django project at the root with apps under `apps/<app_name>/`, `manage.py`, `config/` (settings split into base/dev/prod), `templates/`, `static/`, `tests/`, `pyproject.toml`, `.env.example`.

Generate every file the project needs to `uv sync && uv run python manage.py migrate && uv run python manage.py runserver` cleanly.
