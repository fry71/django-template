# api/web/routing.py
from django.urls import re_path
from api.user import consumers
from ninja import NinjaAPI, Swagger
from api.user.api import router as user_router

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<token>[^/]+)/$", consumers.ChatConsumer.as_asgi()),
]

api = NinjaAPI(
    title="Django Gateway API",
    version="0.1.0",
    description="High performance Django API with async capabilities",
)

api.add_router("/user/", user_router, tags=["user"])
