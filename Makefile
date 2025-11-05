
PYTHON = uv run python
CELERY = uv run celery
UVICORN = uv run uvicorn
GUNICORN = uv run gunicorn
TASKIQ = uv run taskiq

# Запуск бота и сервера
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
	DJANGO_SETTINGS_MODULE=api.config.settings $(TASKIQ) worker tasks:broker -fsd

run.taskiq.prod:
	$(TASKIQ) worker tasks:broker --worker 2 --fs-discover

# Управление Django
makemigrations:
	$(PYTHON) manage.py makemigrations

migrate:
	$(PYTHON) manage.py migrate

collectstatic:
	$(PYTHON) manage.py collectstatic --no-input

createsuperuser:
	$(PYTHON) manage.py createsuperuser --email "" --username admin

# Форматирование, линтинг и тесты
fmt:
	make -k ruff-fmt black

lint:
	make -k ruff black-check mypy

black:
	uv run black .

black-check:
	uv run black --check .

ruff:
	uv run ruff .

ruff-fmt:
	uv run ruff --fix-only --unsafe-fixes .

test:
	uv run pytest

test.report:
	uv run pytest -s -v
	
mypy:
	uv run mypy .

docker.build:
	docker compose build

docker.update:
	docker compose build api bot celery celery-beat
	docker compose up -d --no-deps api bot celery celery-beat

docker.up:
	docker compose up

docker.down:
	docker compose down -v

docker.rebuild:
	docker compose down -v
	docker compose build --no-cache
	docker compose up