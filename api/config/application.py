from __future__ import annotations

from os import getenv

from api.config.base import BASE_DIR
from api.config.silk import SILKY_MIDDLEWARE_CLASS, USE_SILK

PROJECT_NAME = getenv("PROJECT_NAME", "django_template")
PROJECT_VERBOSE_NAME = getenv("PROJECT_VERBOSE_NAME", "Django Template")

ENVIRONMENT = getenv("ENVIRONMENT", "local")
HOST = getenv("HOST", "localhost")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "axes",
    "silk",
    "api.user.apps.UserConfig",
    "ninja",
    "channels",
    "cacheops",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    SILKY_MIDDLEWARE_CLASS,
    "axes.middleware.AxesMiddleware",
]

if not USE_SILK:
    INSTALLED_APPS.remove("silk")
    MIDDLEWARE.remove(SILKY_MIDDLEWARE_CLASS)

ROOT_URLCONF = "api.web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "api/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "api.web.wsgi.application"
ASGI_APPLICATION = "api.web.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
LOGIN_URL = "/login/"


LANGUAGE_CODE = getenv("LANGUAGE_CODE", "en-us")

USE_TZ = True
TIME_ZONE = getenv("TIME_ZONE", "UTC")

USE_I18N = True
