# Dockerfile
FROM python:3.14-slim AS builder

WORKDIR /application

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install --no-cache-dir uv

# Копируем зависимости
COPY pyproject.toml .
COPY uv.lock .  

# Установка зависимостей
RUN uv sync --frozen

FROM python:3.14-slim

WORKDIR /application

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    make \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости из builder
COPY --from=builder /application/.venv /application/.venv

# Копируем uv из builder (используется в dev-compose командах)
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Копируем проект
COPY . .

# Установка переменных окружения
ENV PATH="/application/.venv/bin:$PATH"
ENV PYTHONPATH="/application"

# Создание директорий для static и media файлов
RUN mkdir -p staticfiles media

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

CMD ["gunicorn", "api.web.asgi:application", "--bind", "0.0.0.0:8000", "--worker-class", "uvicorn_worker.UvicornWorker"]