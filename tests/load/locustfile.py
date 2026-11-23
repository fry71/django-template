# tests/load/locustfile.py
"""Load scenarios for the chat API (REST + auth).

Run against a live server without installing anything permanently:

    uv run python manage.py migrate --run-syncdb  # if needed
    uv run python manage.py runserver &  # or daphne/gunicorn behind it

    uvx locust -f tests/load/locustfile.py \
        --headless -u 20 -r 4 -t 30s --host http://127.0.0.1:8000

Scenarios:

- ``AnonymousUser``: health checks, the cheapest possible probe.
- ``ChatUser``: the full golden path — register, login (JWT), create a
  room, walk the cursor-paginated message feed.

Every ``ChatUser`` registers its own account, so the login throttle
(``_AUTH_THROTTLE``, 10 req/min per IP) and the per-account lockout are
part of what is being loaded — raise ``-r`` carefully.
"""

from __future__ import annotations

import uuid

from locust import HttpUser, between, task


class AnonymousUser(HttpUser):
    """Liveness probe: no DB, no auth."""

    wait_time = between(0.1, 0.5)

    @task
    def health(self) -> None:
        """Hit the orchestrator liveness endpoint."""
        self.client.get("/health/", name="/health")


class ChatUser(HttpUser):
    """The authenticated read-heavy chat client."""

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Register a fresh account and store its access token."""
        suffix = uuid.uuid4().hex[:12]
        self.credentials = {
            "username": f"load_{suffix}",
            "email": f"load_{suffix}@example.com",
            "password": "loadpass12345",
            "first_name": "Load",
            "last_name": "Test",
        }
        self.client.post(
            "/api/user/users",
            json=self.credentials,
            name="/api/user/users [register]",
        )
        resp = self.client.post(
            "/api/user/token",
            json={
                "username": self.credentials["username"],
                "password": self.credentials["password"],
            },
            name="/api/user/token",
        )
        token = resp.json().get("access_token", "")
        self.headers = {"Authorization": f"Bearer {token}"}

        room = self.client.post(
            "/api/user/rooms",
            json={"name": f"load-room-{suffix}"},
            headers=self.headers,
            name="/api/user/rooms",
        )
        self.room_id = room.json().get("id")

    @task(3)
    def walk_messages(self) -> None:
        """Follow the cursor feed to its end, then start over."""
        cursor = ""
        while cursor is not None:
            params = {"room_id": self.room_id, "limit": 10, "sort": "asc"}
            if cursor:
                params["cursor"] = cursor
            resp = self.client.get(
                "/api/user/messages",
                params=params,
                headers=self.headers,
                name="/api/user/messages",
            )
            cursor = resp.json().get("next_cursor")

    @task(1)
    def send_message(self) -> None:
        """Post one chat message (also 10 msg / 5 s is WS-only, REST is free)."""
        self.client.post(
            "/api/user/messages",
            json={"room_id": self.room_id, "content": "load test message"},
            headers=self.headers,
            name="/api/user/messages [post]",
        )

    @task(1)
    def list_rooms(self) -> None:
        """List the user's rooms."""
        self.client.get(
            "/api/user/rooms",
            params={"page": 1, "page_size": 10},
            headers=self.headers,
            name="/api/user/rooms [list]",
        )
