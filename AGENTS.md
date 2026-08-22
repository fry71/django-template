# AGENTS.md — django-template

Ground rules for AI agents working in this repository. Read fully before
making changes. Do not invent APIs — check the installed packages first.

## Stack

- Python 3.14, Django 6.x, **django-modern-rest (dmr)** for the REST API,
  Pydantic v2 for schemas, Taskiq for background jobs, Channels for WS.
- Valkey/Redis for cache + cacheops + throttling backend.
- WhiteNoise serves static files; media via nginx or S3 in production.

## Architecture

```
api/
├── common/       # ErrorModel mapping (DomainErrorMixin), pagination, shared schemas
├── config/       # split_settings: base, security, cache, storage, taskiq, ...
├── user/         # models, schema.py (Pydantic), services/, api.py (controllers),
│                 # consumers.py (WS chat), views.py (server-rendered chat), forms.py
bot/              # aiogram Telegram bot (config + handlers routers)
tasks/            # taskiq broker & helpers
tests/            # unit/, integration/, load/
```

- **Service layer** owns business logic; controllers/consumers stay thin.
  Services accept Pydantic DTOs, return domain types (`User | None`),
  never HTTP statuses. Errors are raised as `DomainError` subclasses from
  `api/common/exceptions.py` and mapped by `DomainErrorMixin`.
- **Async ORM only** in async code: `aget`, `acreate`, `asave`, `[obj async for ...]`.
- **Transactions**: single writes need no transaction. Multi-step writes use
  `@sync_to_async` + `@transaction.atomic` bridge (see `room_service.py`,
  `message_service.py`). Never put `transaction.atomic` around `async def` directly.
- **Taskiq**: dispatch `await task.kiq(...)` AFTER the DB commit, wrapped in
  try/except with logging (see `user_service.create_user`).

## dmr (django-modern-rest) conventions

Follow https://django-modern-rest.readthedocs.io/llms-full.txt. Key points:

- Component parameter names are fixed: `parsed_body`, `parsed_query`,
  `parsed_path`, `parsed_headers`, `parsed_cookies`, `parsed_file_metadata`.
- Return type annotation = response spec; no implicit conversions.
- Prefer "raw endpoints" (`@modify`) over `@validate`; declare error responses
  via `BaseAsyncController.responses` / `ERROR_RESPONSES`.
- Never return raw `HttpResponse` from endpoints — raise `DomainError`
  or use `to_response`/`to_error`.
- Auth endpoints MUST be throttled (`throttling = (_AUTH_THROTTLE,)`).
- Response validation stays ON in development and OFF in production
  (`DMR_SETTINGS` in `api/config/security.py`).

## Chat domain model

- `ChatRoom` (group | direct) + `RoomMembership` (M2M through) + `Message.room`.
- Direct rooms are found via deterministic `direct_room_key(a_id, b_id)`.
- **Golden path:** JWT REST + WebSocket `/ws/chat/<room_id>/`. First frame
  `{"type": "auth", "token": "<access JWT>"}` (never path or query). Then
  membership check; group `chat_<room_id>`; rate limit 10 msg / 5 s;
  content ≤ 4000 chars.
- `/chat/` SSE + session is an HTML demo of the same models, not a second API.

## Security rules

- JWT: access tokens only for WS/API auth; refresh tokens rotate — each jti
  is denylisted in `UsedRefreshToken` after use.
- Static files: WhiteNoise middleware (`CompressedManifestStaticFilesStorage`);
  media: nginx/S3 — never hand-rolled ASGI file serving.
- Secrets come from env (`DJANGO_SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`,
  `REDIS_URL`). Never commit secrets; `.env.example` documents them.
- Cacheops is opt-in per model (`CACHEOPS` in `cache.py`) — do NOT add
  `"*.*": {"ops": "all"}`.

## Testing

- `uv run pytest tests` — must pass before finishing any change.
- Tests run hermetically: under pytest the redis cache/cacheops is disabled
  automatically (`api/config/cache.py`) and throttle counters are cleared
  between tests (`tests/conftest.py`).
- Migrations: this template keeps a single fresh `0001_initial`. When models
  change, delete old migrations and regenerate (demo data lives in code).

## Linting (all must pass)

```bash
uv run flake8 . --select=WPS         # wemake-python-styleguide (see .flake8 excludes)
uv run ruff check .
uv run black --check --target-version py314 api tasks tests main.py manage.py
uv run ty check api tasks main.py manage.py
```

Notes:
- `flake8 --select=WPS` is **only** wemake-python-styleguide. pep8/bugbear/isort
  live in `ruff check` (`select = ["ALL"]`). The two tools do not duplicate
  pycodestyle.
- WPS exceptions policy lives in `.flake8` (tests, settings modules and
  bot excluded; magic numbers allowed for max_length/status codes).
- Python 3.14 allows `except A, B:` without parentheses (PEP 758) but we
  prefer explicit parentheses for clarity.
