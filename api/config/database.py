from __future__ import annotations

import logging
from os import getenv

import dj_database_url

logger = logging.getLogger(__name__)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_default_db_url = "sqlite:///db.sqlite3"
DB_URL = getenv("DATABASE_URL", default=_default_db_url)

if _default_db_url == DB_URL:
    logger.warning("Using default database url: '%s'", DB_URL)

# Connection pooling settings
CONN_MAX_AGE = int(getenv("CONN_MAX_AGE", default="600"))

# SSL settings for PostgreSQL
DB_SSL_MODE = getenv(
    "DB_SSL_MODE",
    "prefer",
)  # disable, allow, prefer, require, verify-ca, verify-full
DB_SSL_CERT = getenv("DB_SSL_CERT")
DB_SSL_KEY = getenv("DB_SSL_KEY")
DB_SSL_CA = getenv("DB_SSL_CA")

# Database credentials
DB_NAME = getenv("POSTGRES_DB", "postgres")
DB_USER = getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = getenv("POSTGRES_PASSWORD")
DB_HOST = getenv("POSTGRES_HOST", "localhost")
DB_PORT = getenv("POSTGRES_PORT", "5432")

# Database timeout settings
DB_CONNECT_TIMEOUT = int(getenv("DB_CONNECT_TIMEOUT", default="10"))
DB_OPTIONS: dict[str, str | int] = {
    "connect_timeout": DB_CONNECT_TIMEOUT,
}

# SSL options for PostgreSQL
if DB_SSL_MODE != "disable":
    if DB_SSL_CA:
        DB_OPTIONS["sslmode"] = DB_SSL_MODE
        DB_OPTIONS["sslrootcert"] = DB_SSL_CA
        if DB_SSL_CERT and DB_SSL_KEY:
            DB_OPTIONS["sslcert"] = DB_SSL_CERT
            DB_OPTIONS["sslkey"] = DB_SSL_KEY
        logger.info("SSL mode: %s", DB_SSL_MODE)
    else:
        logger.warning("SSL mode set but no CA certificate provided")

DATABASES = {
    "default": dj_database_url.parse(DB_URL, conn_max_age=CONN_MAX_AGE),
}

# Extra PostgreSQL settings
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Extra PostgreSQL options
    DATABASES["default"].update(
        {
            "OPTIONS": DB_OPTIONS,
        },
    )
