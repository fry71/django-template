# Django Gateway — High Performance Django Template

A production-ready Django template showcasing modern web development: a fully **async REST API** built with **django-modern-rest**, **JWT** authentication, **real-time chat** (SSE + REST) with Django forms and templates, background jobs with Taskiq, and performance comparable to FastAPI — while keeping all Django batteries.

[![Python Version](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-6.1-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Features
- 🚀 **High Performance** — Async Django with performance comparable to FastAPI
- 🔧 **Async-first API** — django-modern-rest (DMR) controllers, fully async ORM (`aget`, `acreate`, `aiterator`)
- 📦 **All Django Batteries** — Admin, ORM, Auth, Forms, Templates
- 💬 **Real-time Chat** — Django form page wired via **Server-Sent Events (SSE)** + **REST**, session authentication
- 🧩 **Django 6.1 Template Partials** — `{% partialdef %}` / `{% partial %}` for server-rendered chat messages
- 🔐 **JWT Authentication** — token-based auth for the API (`/api/user/token`, `/api/user/refresh`)
- 🔄 **Background Tasks** — Taskiq jobs dispatched after DB commit (`task.kiq(...)`)
- 📚 **OpenAPI Documentation** — auto-generated Swagger UI
- 🗄️ **Modern ORM** — strict typing (PEP 695), `select_related` to avoid N+1, N+1 guard
- 🐳 **Docker Ready** — production-ready Docker setup
- 🛡️ **Security** — built-in security best practices

## Technologies
- [Django 6.1](https://www.djangoproject.com/) — High-level Python web framework
- [Python 3.14](https://www.python.org/) — Modern Python runtime
- [django-modern-rest](https://github.com/django-modern-rest/django-modern-rest) — Fast, async-first REST API framework (Django Ninja successor)
- [Pydantic v2](https://docs.pydantic.dev/) — Data validation with strict typing
- [msgspec](https://jcristharif.com/msgspec/) — High-performance serialization (installed; used optionally)
- [Taskiq](https://taskiq-python.github.io/) — Modern task queue (Celery alternative)
- [Valkey](https://valkey.io/) — Redis-compatible datastore
- [Sentry](https://sentry.io/) — Error monitoring and performance tracking
- [Django Channels](https://channels.readthedocs.io/) — WebSocket support

## Project structure
```
api/
├── common/          # Shared DTOs, error handling (BaseAsyncController)
├── config/          # Split settings (split_settings)
├── user/            # User/Message/Photo models, DMR controllers, services, forms, views
│   ├── api.py       # REST controllers (token, users, messages, photos)
│   ├── views.py     # Chat page, REST send, SSE stream
│   ├── services/    # Async service layer (business logic)
│   ├── forms.py     # Django form for the chat
│   └── migrations/  # Includes demo users (0003_demo_users)
├── templates/       # Django templates (base, login, chat with partials)
└── web/             # Router, URLconf, ASGI/WSGI
```

## Quick Start

### 0. Run with Docker Compose (web + worker + Postgres + Valkey)
```bash
docker compose up -d        # build & start the full stack
curl http://127.0.0.1:8000/health/   # {"status":"ok"}
docker compose run --rm test # run the test suite against Postgres
docker compose down          # stop (add -v to also drop volumes)
```
`docker compose up` starts `web` (gunicorn + `uvicorn_worker`, auto-runs `migrate` +
`collectstatic`), `worker` (Taskiq consumer), `db` and `redis`. Static and media files
are served by Django itself via async ASGI handlers (`serve_static` / `serve_media`),
so no separate static server is needed in dev. `db` and `redis` are only reachable
inside the compose network — only `web` publishes port 8000, so nothing conflicts with
a local Postgres/Valkey. The `test` service has its own profile and runs on demand
(see above).

### 1. Create `.env`
```bash
cp .env.example .env
```

### 2. Install dependencies
With `uv` (recommended):
```bash
uv sync
```

Without `uv`:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

### 3. Run migrations
```bash
uv run python manage.py migrate
```
This also creates the demo users `demo1` and `demo2` (password: `demo12345`, override with `DJANGO_DEMO_PASSWORD`) and, if you set `DJANGO_ADMIN_USERNAME`/`DJANGO_ADMIN_PASSWORD`, the admin user.

### 4. Run the development server
```bash
uv run uvicorn api.web.asgi:application --host 0.0.0.0 --port 8000 --reload
# or
make run.server.local
```

## Main endpoints

| Endpoint | Description |
| --- | --- |
| `http://127.0.0.1:8000/api/docs` | Swagger UI / OpenAPI docs |
| `http://127.0.0.1:8000/admin/` | Django admin (`admin` / `admin` by default) |
| `http://127.0.0.1:8000/login/` | Login page (session auth) |
| `http://127.0.0.1:8000/chat/` | Real-time chat (SSE + REST, requires login) |
| `POST /api/user/token` | Obtain JWT access + refresh tokens |
| `POST /api/user/refresh` | Refresh the access token |
| `GET/POST /api/user/users` | List / create users |
| `GET/POST /api/user/messages` | List / create messages (JWT) |
| `GET/POST /api/user/photos` | List / upload photos (JWT, multipart) |

## Real-time chat

The chat page (`/chat/`) is a classic Django form + template page authenticated via the session:

- **Send** — `POST /chat/send/` (REST): validates `MessageForm`, creates the message, returns JSON `{id, content, sender, timestamp}`.
- **Receive** — `GET /chat/stream/` (SSE): streams new messages as `text/event-stream`. Events carry an `id` (message PK) so the browser resumes correctly after reconnects (`Last-Event-ID`).
- **Rendering** — the message markup is a **Django 6.1 template partial** (`{% partialdef message-item %}` in `api/templates/chat/chat.html`), used both for the initial page render and for SSE-injected HTML — a single source of truth.

### Try it
1. Log in as `demo1` / `demo12345` in one browser and `demo2` / `demo12345` in another.
2. Send a message from either user — it appears live in both chats via SSE.

## Testing
```bash
USE_REDIS_FOR_CACHE=false TASKIQ_IN_MEMORY=true DJANGO_SETTINGS_MODULE=api.config.settings uv run pytest tests/ -q
```

## CI (GitHub Actions)
`.github/workflows/ci.yml` runs on every push to `main` and on pull requests:
- **Lint** — `ruff check .` + `flake8 .` (wemake-python-styleguide) + `black --check` + `ty check`.
- **Tests (sqlite)** — full pytest suite on SQLite.
- **Tests (postgres)** — full pytest suite against a Postgres 15 service container, mirroring production database behavior.

## Linting
Configured in `.flake8` (wemake-python-styleguide) and `pyproject.toml` (ruff/black):
- **ruff** — `uv run ruff check .`
- **black** — `uv run black --check api tasks tests main.py manage.py`
- **wemake-python-styleguide (flake8)** — `uv run flake8 .` (uses `.flake8`)
  - Excluded: `tests`, `migrations`, `api/config` (Django settings — `WPS407` false positives), `bot`.
  - Allowed exceptions: `WPS110` (domain names), `WPS115` (Django class constants), `WPS201`/`WPS202`/`WPS235` (module import sizes), `WPS226` (string over-use), `WPS432` (magic numbers for `max_length`/HTTP statuses), `WPS476` (serial async retry loops).
- **ty** — `uv run ty check api tasks main.py manage.py` (uses `django-stubs` `.pyi` from the venv; no mypy plugin).
- **mypy** — `uv run mypy api/` (`django-stubs` plugin for ORM: `Model.objects`, `AUTH_USER_MODEL`).

## Performance benefits
- Async Django — non-blocking I/O operations
- Connection pooling — efficient database connections
- Caching — Redis-based caching with cacheops
- Background tasks — non-blocking task processing (dispatched after commit)
- N+1 guard — `select_related` / `prefetch_related` everywhere

## Services
- Valkey: `redis://localhost:6379`
- PostgreSQL: `postgres://localhost:5432`
- Sentry: `https://sentry.io/`

## Acknowledgments
- [Django Community](https://www.djangoproject.com/) — For the amazing framework
- [django-modern-rest](https://github.com/django-modern-rest/django-modern-rest) — The async REST framework used here
- [MaksimZayats (aiogram-django-template)](https://github.com/MaksimZayats) — For inspiration
- [Suor (django-cacheops)](https://github.com/Suor) — For the useful django-cacheops project
- [Taskiq Team](https://taskiq-python.github.io/) — Modern task queue solution

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).
Dependencies and their licenses:
- Django: [BSD License](https://opensource.org/licenses/BSD-3-Clause)
- django-modern-rest: [MIT License](https://github.com/django-modern-rest/django-modern-rest/blob/master/LICENSE)
- Taskiq: [BSD License](https://github.com/taskiq-python/taskiq/blob/master/LICENSE)
- Valkey: [BSD 3-Clause License](https://github.com/valkey-io/valkey/blob/unstable/COPYING)
- Sentry: [BSD License](https://github.com/getsentry/sentry/blob/master/LICENSE)