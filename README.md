# Django Gateway - High Performance Django Template

A production-ready template project showcasing the integration of modern web development technologies with Django, providing performance comparable to FastAPI while maintaining all Django benefits.

[![Python Version](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-6.0-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Features
- 🚀 **High Performance** - Async Django with performance comparable to FastAPI
- 🔧 **Full Async Support** - Django Ninja API with async/await
- 📦 **All Django Batteries** - Admin, ORM, Auth, and more
- 🔄 **Task Processing** - Taskiq for background tasks
- 🔐 **JWT Authentication** - Secure token-based auth
- 💬 **Real-time Chat** - WebSocket support with Channels
- 📚 **OpenAPI Documentation** - Auto-generated API docs
- 🐳 **Docker Ready** - Production-ready Docker setup
- 🛡️ **Security** - Built-in security best practices



## Technologies
- [Django 6.0](https://www.djangoproject.com/) - High-level Python web framework
- [Python 3.14](https://www.python.org/) - Modern Python runtime
- [Django Ninja](https://django-ninja.rest-framework.com/) - Fast Django REST API framework
- [Pydantic v2](https://docs.pydantic.dev/) - Data validation with strict typing
- [Taskiq](https://taskiq-python.github.io/) - Modern task queue (Celery alternative)
- [Valkey](https://valkey.io/) - Redis-compatible datastore
- [Sentry](https://sentry.io/) - Error monitoring and performance tracking
- [Django Channels](https://channels.readthedocs.io/) - WebSocket and async support
- [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) - Real-time communication

## Quick Start

## Create .env
```bash
cp .env.example .env
```

### With `uv` (recommended):
```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn api.web.asgi:application --host 0.0.0.0 --port 8000 --reload

#or
make run.server.local
```
### Without uv:
```bash
# Install uv and dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Run development server
uv run uvicorn api.web.asgi:application --host 0.0.0.0 --port 8000 --reload

#or
make run.server.local
```

## Main Endpoints 

    API Docs: http://127.0.0.1:8000/api/docs 
    Admin Panel: http://127.0.0.1:8000/admin/  (admin/admin)
    WebSocket Chat: http://127.0.0.1:8000/chat/ 
    User Profile: http://127.0.0.1:8000/profile/ 
     

# Performance Benefits 

## This template provides: 

    Async Django - Non-blocking I/O operations
    Connection Pooling - Efficient database connections
    Caching - Redis-based caching with cacheops
    Background Tasks - Non-blocking task processing
    WebSocket Support - Real-time communication
    Production Ready - Optimized for high load
     

## Services 

    Valkey: redis://localhost:6379
    PostgreSQL: postgres://localhost:5432
    Sentry: https://sentry.io/ 
     

## Acknowledgments 

   - [Django Community](https://www.djangoproject.com/) - For the amazing framework
   - [Vitalik (Django Ninja)](https://github.com/vitalik) – For creating the awesome Django Ninja framework.
   - [MaksimZayats (aiogram-django-template)](https://github.com/MaksimZayats) – For inspiration and the aiogram-django-template.
   - [Suor (django-cacheops)](https://github.com/Suor) – For the useful django-cacheops project.
   - [Taskiq Team](https://taskiq-python.github.io/) - Modern task queue solution
   - [Django Channels Team](https://github.com/django/channels)
     

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).  
Dependencies and their licenses:
- Django: [BSD License](https://opensource.org/licenses/BSD-3-Clause)
- Django Ninja: [MIT License](https://github.com/vitalik/django-ninja/blob/master/LICENSE)
- Taskiq: [BSD License](https://github.com/taskiq-python/taskiq/blob/master/LICENSE)
- Valkey: [BSD 3-Clause License](https://github.com/valkey-io/valkey/blob/unstable/COPYING)
- RabbitMQ: [Mozilla Public License 2.0](https://github.com/rabbitmq/rabbitmq-server/blob/main/LICENSE-MPL-RabbitMQ)
- Sentry: [BSD License](https://github.com/getsentry/sentry/blob/master/LICENSE)
- Django Channels: [BSD License](https://github.com/django/channels/blob/main/LICENSE)
- Turbo (Hotwired): [MIT License](https://github.com/hotwired/turbo/blob/main/LICENSE)


     