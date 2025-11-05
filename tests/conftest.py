# tests/conftest.py
import os
import django
import uuid
from django.conf import settings

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")
django.setup()

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user_data():
    """Фикстура с уникальными данными для создания пользователя"""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "username": f"testuser_{unique_id}",
        "email": f"test_{unique_id}@example.com",
        "password": "testpass123",
        "first_name": "Test",
        "last_name": "User",
    }



@pytest.fixture
def test_user(user_data):
    """Фикстура для создания тестового пользователя"""
    user = User.objects.create_user(**user_data)
    yield user
    # Пробуем удалить, но не падаем если уже удален
    try:
        user.delete()
    except:
        pass


@pytest.fixture
def authenticated_client(client, user_data):
    """Фикстура для аутентифицированного клиента"""
    import json

    # Создаем пользователя для аутентификации
    user = User.objects.create_user(**user_data)

    # Получение токена
    url = "/api/user/token"
    response = client.post(
        url,
        json.dumps(
            {"username": user_data["username"], "password": user_data["password"]}
        ),
        content_type="application/json",
    )

    if response.status_code == 200:
        token = response.json()["access_token"]
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    yield client

    # Очистка
    if "HTTP_AUTHORIZATION" in client.defaults:
        del client.defaults["HTTP_AUTHORIZATION"]

    # Удаляем пользователя
    try:
        user.delete()
    except:
        pass
