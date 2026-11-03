from __future__ import annotations

import logging
import sys
from os import getenv

from dmr.settings import Settings

logger = logging.getLogger(__name__)

# Secret keys — must be changed in production!
_default_secret_key = "your-super-secret-and-long-django-secret-key"
SECRET_KEY = getenv("DJANGO_SECRET_KEY", _default_secret_key)

_default_jwt_secret_key = "your-super-secret-and-long-jwt-secret-key-for-token-signing"
JWT_SECRET_KEY = getenv("JWT_SECRET_KEY", _default_jwt_secret_key)

# Warn if default keys are in use
if _default_secret_key == SECRET_KEY:
    logger.warning(
        "You are using a default Django secret key - CHANGE THIS IN PRODUCTION!",
    )

if _default_jwt_secret_key == JWT_SECRET_KEY:
    logger.warning("You are using a default JWT secret key - CHANGE THIS IN PRODUCTION!")

# JWT settings — required for production
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_LIFETIME = 5  # minutes
JWT_HEADER_PREFIX = "JWT"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = getenv("DJANGO_DEBUG", "false").lower() == "true"

# Production security settings
SECURE_SSL_REDIRECT = getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_HSTS_SECONDS = int(getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "false").lower() == "true"
)
SECURE_HSTS_PRELOAD = getenv("SECURE_HSTS_PRELOAD", "false").lower() == "true"

SESSION_COOKIE_SECURE = getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
CSRF_COOKIE_SECURE = getenv("CSRF_COOKIE_SECURE", "false").lower() == "true"

# Content Security Policy
SECURE_CONTENT_TYPE_NOSNIFF = (
    getenv("SECURE_CONTENT_TYPE_NOSNIFF", "true").lower() == "true"
)
SECURE_BROWSER_XSS_FILTER = getenv("SECURE_BROWSER_XSS_FILTER", "true").lower() == "true"
X_FRAME_OPTIONS = getenv("X_FRAME_OPTIONS", "DENY")

# Rate limiting
RATELIMIT_USE_CACHE = "default"

ALLOWED_HOSTS = [
    host.strip() for host in getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
]

AUTHENTICATION_BACKENDS = [
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

# dmr recommendation: keep response validation on in development (and tests)
# and disable it in production only —
# https://django-modern-rest.readthedocs.io/en/latest/pages/validation.html
#
# Validation is on by default, so this settings dict only has to switch it
# off for a real production run. Tests keep it on even when DJANGO_DEBUG is
# unset, because that is how CI runs, and validation is exactly what catches
# undescribed headers there.
_UNDER_PYTEST = "pytest" in sys.modules
_PRODUCTION = not DEBUG and not _UNDER_PYTEST

DMR_SETTINGS: dict[Settings, bool] = {}
if _PRODUCTION:
    DMR_SETTINGS[Settings.validate_responses] = False
