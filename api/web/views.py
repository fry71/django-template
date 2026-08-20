# api/web/views.py
from __future__ import annotations

from django.http import HttpRequest, JsonResponse


def health(_request: HttpRequest) -> JsonResponse:
    """Return a lightweight liveness response for the orchestrator.

    Deliberately touches no DB or external services so it reflects the
    process liveness rather than dependency health.
    """
    return JsonResponse({"status": "ok"})
