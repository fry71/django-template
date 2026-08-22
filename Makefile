PYTHON = uv run python
UVICORN = uv run uvicorn
GUNICORN = uv run gunicorn
TASKIQ = uv run taskiq

SRC = api tasks tests main.py manage.py

.PHONY: run.bot run.server.local run.server.prod run.bot.local run.bot.prod \
	run.taskiq.local run.taskiq.prod makemigrations migrate collectstatic \
	createsuperuser fmt lint black black-check ruff ruff-fix wps ty mypy \
	test test.report docker.build docker.update docker.up docker.down docker.rebuild

# Run bot and server
run.bot:
	$(PYTHON) -m bot

run.server.local:
	$(UVICORN) api.web.asgi:application \
		--host 0.0.0.0 \
		--port 8000 \
		--reload

run.server.prod:
	$(GUNICORN) api.web.asgi:application \
		-b 0.0.0.0:8000 \
		-w 4 \
		-k uvicorn_worker.UvicornWorker \
		--timeout 480

run.bot.local:
	$(PYTHON) -m bot

run.bot.prod:
	$(PYTHON) -m bot

run.taskiq.local:
	DJANGO_SETTINGS_MODULE=api.config.settings $(TASKIQ) worker tasks.broker:broker

run.taskiq.prod:
	$(TASKIQ) worker tasks.broker:broker --workers 2

# Django management
makemigrations:
	$(PYTHON) manage.py makemigrations

migrate:
	$(PYTHON) manage.py migrate

collectstatic:
	$(PYTHON) manage.py collectstatic --no-input

createsuperuser:
	$(PYTHON) manage.py createsuperuser --email "" --username admin

# Formatting, linting, and tests (same as CI / AGENTS.md)
fmt:
	make -k ruff-fix black

lint:
	make -k ruff wps black-check ty

black:
	uv run black --target-version py314 $(SRC)

black-check:
	uv run black --check --target-version py314 $(SRC)

ruff:
	uv run ruff check .

ruff-fix:
	uv run ruff check --fix --unsafe-fixes .

wps:
	uv run flake8 . --select=WPS

ty:
	uv run ty check api tasks main.py manage.py

mypy:
	uv run mypy api/

test:
	uv run pytest tests/ -q

test.report:
	uv run pytest tests/ -s -v --cov=api --cov=tasks --cov-report=term-missing --cov-fail-under=80

docker.build:
	docker compose build

docker.update:
	docker compose build web worker
	docker compose up -d --no-deps web worker

docker.up:
	docker compose up

docker.down:
	docker compose down -v

docker.rebuild:
	docker compose down -v
	docker compose build --no-cache
	docker compose up
