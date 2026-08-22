# Django Gateway — High Performance Django Template

A production-ready Django template showcasing modern web development: a fully **async REST API** built with **django-modern-rest**, **JWT** authentication, **WebSocket chat rooms**, an optional HTML/SSE demo, background jobs with Taskiq, and performance comparable to FastAPI — while keeping all Django batteries.

[![Python Version](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-6.1-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Features
- 🚀 **High Performance** — Async Django with performance comparable to FastAPI
- 🔧 **Async-first API** — django-modern-rest (DMR) controllers, fully async ORM (`aget`, `acreate`, `aiterator`)
- 📦 **All Django Batteries** — Admin, ORM, Auth, Forms, Templates
- 💬 **Chat Rooms (golden path)** — JWT REST for rooms/messages; membership-checked WebSocket `WS /ws/chat/<room_id>/` with first-frame `{"type":"auth","token":"<access JWT>"}` (token never in the URL)
- 🖥️ **HTML chat demo** — session login + Django form + SSE at `/chat/` (same `Message` model; not a second product)
- 🧩 **Django 6.1 Template Partials** — `{% partialdef %}` / `{% partial %}` for server-rendered chat messages
- 🔐 **JWT Authentication** — token-based auth for the API (`/api/user/token`, `/api/user/refresh`), refresh-token rotation with jti denylist; access TTL 5 minutes
- 🤖 **Telegram Bot** — aiogram 3 with routers/handlers (polling mode)
- 🎨 **WhiteNoise** — static files served with compression + manifests; media via nginx/S3
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
├── user/            # User/ChatRoom/RoomMembership/Message/Photo models, DMR controllers,
│                    # services, WS consumers, forms, views
│   ├── api.py       # REST controllers (token, users, rooms, messages, photos)
│   ├── consumers.py # WebSocket chat consumer (rooms, membership, rate limit)
│   ├── views.py     # Chat page, REST send, SSE stream
│   ├── services/    # Async service layer (user/room/message/photo)
│   └── migrations/  # Single fresh 0001_initial (regenerated on model change)
bot/
├── config/bot.py    # aiogram settings (token, running mode)
└── handlers/        # Routers: /start, /help, echo fallback
templates/           # Django templates (base, login, chat with partials)
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
`docker compose up` is **local only**: `DJANGO_DEBUG=true` and the compose
secret keys are not production values. It starts `web` (gunicorn + `uvicorn_worker`, auto-runs `migrate` +
`collectstatic`), `worker` (Taskiq consumer), `db` and `redis`. Static files are served
by **WhiteNoise** middleware; in production put nginx (or S3) in front for static and
media — the ASGI app itself never serves files. `db` and `redis` are only reachable
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
The template ships a single fresh `0001_initial` (no demo data). If you set
`DJANGO_ADMIN_USERNAME`/`DJANGO_ADMIN_PASSWORD`, a superuser can be created via
`manage.py createsuperuser`.

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
| `http://127.0.0.1:8000/chat/` | HTML demo: session chat via SSE (not the API golden path) |
| `POST /api/user/token` | Obtain JWT access + refresh tokens (throttled: 10 req/min; access TTL 5 min) |
| `POST /api/user/refresh` | Refresh the token pair (rotation, jti denylist; throttled) |
| `GET/POST /api/user/users` | List / create users |
| `GET/POST /api/user/rooms` | List / create chat rooms (JWT) |
| `POST /api/user/rooms/direct` | Get or create a 1:1 room with a peer (JWT) |
| `POST/DELETE /api/user/rooms/{id}/membership` | Join / leave a room (JWT, 204) |
| `GET/POST /api/user/messages?room_id=` | List / create messages per room (JWT) |
| `GET/POST /api/user/photos` | List / upload photos (JWT, multipart) |
| `WS /ws/chat/<room_id>/` | Room chat. First frame: `{"type":"auth","token":"<access JWT>"}` |

## Real-time chat

**Golden path (API / mobile / SPA):** JWT + REST rooms/messages + WebSocket
`/ws/chat/<room_id>/`. After the socket opens, send
`{"type": "auth", "token": "<access JWT>"}`. The server replies `{"type": "auth_ok"}`
then accepts `{"content": "..."}` messages. Membership is checked on auth;
rate limit 10 msg / 5 s.

**HTML demo only:** `/chat/` is a session-authenticated Django form + **SSE**
page that uses the same `Message` / `ChatRoom` models (shared `general` room).
Do not copy both stacks into a product — pick WebSockets for clients, or SSE
for server-rendered HTML.

The demo page:

- **Send** — `POST /chat/send/` (REST): validates `MessageForm`, creates the message, returns JSON `{id, content, sender, timestamp}`.
- **Receive** — `GET /chat/stream/` (SSE): streams new messages as `text/event-stream`. Events carry an `id` (message PK) so the browser resumes correctly after reconnects (`Last-Event-ID`).
- **Rendering** — the message markup is a **Django 6.1 template partial** (`{% partialdef message-item %}` in `api/templates/chat/chat.html`), used both for the initial page render and for SSE-injected HTML — a single source of truth.

### Try it
1. Create two users (`POST /api/user/users` or via admin), log in as each in a separate browser.
2. Send a message from either user — it appears live in both chats via SSE (messages land in the shared `general` room).

## Testing
```bash
uv run pytest tests/ -q
```
Tests are hermetic: under pytest the redis cache/cacheops is disabled automatically
and throttle counters are cleared between tests. No Redis required to run the suite.

## AI agents
`AGENTS.md` in the repo root contains ground rules for AI coding agents
(architecture, dmr conventions, security rules, testing/linting requirements).

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