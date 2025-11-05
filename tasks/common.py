# tasks/common.py
from __future__ import annotations
import logging
from django.core.mail import send_mail
from asgiref.sync import sync_to_async, async_to_sync
from django.contrib.auth import get_user_model
from django.conf import settings
from taskiq import TaskiqDepends


def get_broker():
    from .broker import broker

    return broker


User = get_user_model()

logger = logging.getLogger(__name__)


@get_broker().task
async def send_verification_email(email: str, code: str):
    try:
        if settings.DEBUG:
            logger.info(f"Sending verification email to {email} with code {code}")
        else:
            logger.info(f"Sending verification email to {email}")
        return True
        # await sync_to_async(send_mail, thread_sensitive=True)(
        #     subject="Vrification",
        #     message=f"Your verification code is {code}",
        #     from_email=settings.EMAIL_HOST_USER,
        #     recipient_list=[email],
        #     fail_silently=False,
        # )
    except Exception as e:
        logger.error(f"Error sending verification email: {e}")
