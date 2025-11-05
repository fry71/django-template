from __future__ import annotations

import logging
import os
from os import getenv

logger = logging.getLogger(__name__)

# Секретные ключи - обязательно измените в production!
_default_secret_key = "your-super-secret-and-long-django-secret-key"  # noqa: S105
SECRET_KEY = getenv("DJANGO_SECRET_KEY", _default_secret_key)

_default_jwt_secret_key = "your-super-secret-and-long-jwt-secret-key-for-token-signing"
JWT_SECRET_KEY = getenv("JWT_SECRET_KEY", _default_jwt_secret_key)

# Проверка на использование дефолтных ключей
if _default_secret_key == SECRET_KEY:
    logger.warning("You are using a default Django secret key - CHANGE THIS IN PRODUCTION!")

if _default_jwt_secret_key == JWT_SECRET_KEY:
    logger.warning("You are using a default JWT secret key - CHANGE THIS IN PRODUCTION!")

# Безопасность - обязательно для production
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_LIFETIME = 60  # 5 минут
JWT_HEADER_PREFIX = "JWT"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = getenv("DJANGO_DEBUG", "false").lower() == "true"

# Production security settings
SECURE_SSL_REDIRECT = getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
SECURE_HSTS_PRELOAD = getenv("SECURE_HSTS_PRELOAD", "false").lower() == "true"

SESSION_COOKIE_SECURE = getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = getenv("CSRF_COOKIE_SECURE", "false").lower() == "true"

# Content Security Policy
SECURE_CONTENT_TYPE_NOSNIFF = getenv("SECURE_CONTENT_TYPE_NOSNIFF", "true").lower() == "true"
SECURE_BROWSER_XSS_FILTER = getenv("SECURE_BROWSER_XSS_FILTER", "true").lower() == "true"
X_FRAME_OPTIONS = getenv("X_FRAME_OPTIONS", "DENY")

# Rate limiting
RATELIMIT_USE_CACHE = "default"
AXES_FAILURE_LIMIT = int(getenv("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = int(getenv("AXES_COOLOFF_TIME", "1"))  # hour

ALLOWED_HOSTS = [
    host.strip() for host in getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",
    "django.contrib.auth.backends.ModelBackend",
]

CSRF_TRUSTED_ORIGINS = [
    host.strip() for host in getenv("CSRF_TRUSTED_ORIGINS", "http://localhost").split(",")
]

CORS_ALLOW_ALL_ORIGINS = getenv("CORS_ALLOW_ALL_ORIGINS", "False").lower() == "true"
CORS_ALLOW_CREDENTIALS = getenv("CORS_ALLOW_CREDENTIALS", "False").lower() == "true"
CORS_ALLOWED_ORIGINS = getenv("CORS_ALLOWED_ORIGINS", "http://localhost").split(
    ",",
)

DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880
