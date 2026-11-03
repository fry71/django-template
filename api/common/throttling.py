# api/common/throttling.py
"""Custom throttling cache keys for dmr."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from dmr.throttling.cache_keys import BaseThrottleCacheKey

if TYPE_CHECKING:
    from dmr.controller import Controller
    from dmr.endpoint import Endpoint
    from dmr.serializer import BaseSerializer


@dataclass(slots=True, frozen=True, kw_only=True)
class UsernameFromBody(BaseThrottleCacheKey):
    """Throttle by the ``username`` field of a JSON request body.

    Login endpoints cannot use ``UserPk`` (there is no authenticated user
    yet), and a plain IP key lets one attacker spread attempts over many
    addresses while hammering a single account. Keying the login throttle by
    the targeted username closes that gap; failures with cooloff are counted
    separately in ``api.common.lockout``.
    """

    runs_before_auth: bool = True
    name: str = "UsernameFromBody"

    def __call__(
        self,
        endpoint: Endpoint,
        controller: Controller[BaseSerializer],
    ) -> str | None:
        """Return a hash of the body's username, or None if unavailable."""
        raw_body = controller.request.body
        if not raw_body:
            return None
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError, UnicodeDecodeError:
            return None
        username = payload.get("username") if isinstance(payload, dict) else None
        if not isinstance(username, str) or not username.strip():
            return None
        # Cache keys never contain raw identifiers.
        return sha256(username.strip().lower().encode("utf-8")).hexdigest()
