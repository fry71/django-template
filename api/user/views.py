# api/user/views.py
from __future__ import annotations

import asyncio
import itertools
import json
from typing import TYPE_CHECKING

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from api.user.forms import MessageForm
from api.user.models import Message

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_MESSAGE_PARTIAL = "chat/chat.html#message-item"
_MESSAGE_POLL_SECONDS = 1.0
_RECENT_MESSAGE_LIMIT = 50


def _message_payload(message: Message) -> dict[str, str | int]:
    """Serialize a message for the REST and SSE transports."""
    return {
        "id": message.id,
        "content": message.content,
        "sender": message.sender.username,
        "timestamp": message.timestamp.isoformat(),
    }


@login_required
def chat_view(request: HttpRequest) -> HttpResponse:
    """Render the chat page with the message form and recent messages."""
    recent_messages = Message.objects.select_related("sender").order_by("-id")
    messages = list(
        reversed(list(itertools.islice(recent_messages, _RECENT_MESSAGE_LIMIT))),
    )
    form = MessageForm()
    return render(request, "chat/chat.html", {"form": form, "messages": messages})


@require_POST
@login_required
def send_message(request: HttpRequest) -> JsonResponse:
    """Create a message over REST and return its JSON representation."""
    form = MessageForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    message = Message.objects.create(
        sender_id=request.user.id,
        content=form.cleaned_data["content"],
    )
    return JsonResponse(_message_payload(message), status=201)


async def _message_events(request: HttpRequest) -> AsyncIterator[str]:
    """Yield new chat messages as Server-Sent Events for a client."""
    last_id = int(
        request.META.get("HTTP_LAST_EVENT_ID") or request.GET.get("last_id") or 0,
    )
    while True:
        fresh = [
            message
            async for message in Message.objects.filter(id__gt=last_id)
            .select_related("sender")
            .order_by("id")
        ]
        for message in fresh:
            html = render(
                request,
                _MESSAGE_PARTIAL,
                {"message": message},
            ).content.decode("utf-8")
            payload = json.dumps({"id": message.id, "html": html})
            yield f"id: {message.id}\nevent: message\ndata: {payload}\n\n"
            last_id = message.id
        yield ": keep-alive\n\n"
        await asyncio.sleep(_MESSAGE_POLL_SECONDS)


@require_GET
@login_required
def message_stream(request: HttpRequest) -> StreamingHttpResponse:
    """Stream new chat messages to the client over Server-Sent Events."""
    return StreamingHttpResponse(
        _message_events(request),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
