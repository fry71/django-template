# Production Deployment Guide

## 🚀 Быстрый старт для Production

### 1. Настройка переменных окружения

```bash
# Копируем файл с переменными
cp .env.example .env

# ОБЯЗАТЕЛЬНО измените эти ключи!
DJANGO_SECRET_KEY=your-super-secure-django-secret-key-256-chars
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-256-chars
```

### 2. Безопасность Production

```bash
# Включаем все security настройки
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000  # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
```

### 3. База данных с SSL

```bash
# Для production используйте PostgreSQL с SSL
DB_SSL_MODE=require
DB_SSL_CA=/path/to/ca-cert.pem
DB_SSL_CERT=/path/to/client-cert.pem
DB_SSL_KEY=/path/to/client-key.pem
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
```

### 4. Запуск в Production

```bash
# Установка зависимостей
uv sync

# Миграции
make migrate

# Создание суперпользователя
migrate createsuperuser

# Запуск с Gunicorn
migrate run.server.prod
```

## 🔒 Критические настройки безопасности

### SSL/HTTPS
```bash
# Обязательно для production!
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

### Content Security Policy
```python
# В settings.py добавьте
MIDDLEWARE += [
    'django.middleware.security.SecurityMiddleware',
]

# CSP настройки
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
```

### Rate Limiting
```bash
AXES_ENABLED=true
AXES_FAILURE_LIMIT=5
AXES_COOLOFF_TIME=1  # hour
```

## 📊 Мониторинг и логирование

### Sentry (ошибки)
```bash
USE_SENTRY=true
SENTRY_DSN=your-sentry-dsn
```

### Логирование
```bash
LOG_LEVEL=INFO
LOG_FILE=/var/log/app.log
```

### Мониторинг производительности
```bash
USE_SILK=true  # Включить Django Silk для профилирования
```

## 🗄️ Настройка базы данных

### PostgreSQL конфигурация
```python
# В database.py уже настроено:
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            'sslmode': 'require',
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}
```

### Оптимизация производительности
```sql
-- Настройки PostgreSQL для production
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 4MB
```

## 🔄 CI/CD Pipeline

### GitHub Actions пример
```yaml
name: Django CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Run migrations
      run: python manage.py migrate
      
    - name: Run tests
      run: |
        python manage.py test
        python manage.py check --deploy
```

## 📈 Масштабирование

### Horizontal scaling (несколько серверов)
```bash
# Используйте общую базу данных и Redis
REDIS_HOST=shared-redis-host
DATABASE_URL=postgresql://user:pass@shared-db:5432/dbname
```

### Load Balancer (Nginx)
```nginx
upstream django_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🛠️ Troubleshooting

### Проверка безопасности
```bash
# Запустите Django check с production флагами
python manage.py check --deploy

# Проверка SSL настроек
python manage.py check --deploy --settings=api.config.settings.production
```

### Логи ошибок
```bash
# Проверьте логи на наличие ошибок безопасности
grep -i "security\|warning\|error" /var/log/app.log
```

### Database подключение
```bash
# Проверьте подключение к БД
python manage.py dbshell
```

## ✅ Checklist перед продакшеном

- [ ] Изменить все дефолтные секретные ключи
- [ ] Настроить HTTPS/SSL сертификаты
- [ ] Включить SECURE_* настройки
- [ ] Настроить SSL для базы данных
- [ ] Настроить мониторинг (Sentry)
- [ ] Создать суперпользователя
- [ ] Провести security audit (`python manage.py check --deploy`)
- [ ] Настроить резервное копирование БД
- [ ] Настроить логирование
- [ ] Протестировать все API endpoints
- [ ] Настроить CI/CD pipeline

---

**Важно**: Никогда не запускайте приложение в production с дефолтными настройками безопасности!

Автор: MiniMax Agent