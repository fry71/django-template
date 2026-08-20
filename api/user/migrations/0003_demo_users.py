# Demo users for local development (demo1, demo2).
from os import getenv
from typing import TYPE_CHECKING, cast

from django.db import migrations


def create_demo_users(apps, schema_editor):
    User = cast("UserModel", apps.get_model("user", "User"))
    demo_password = getenv("DJANGO_DEMO_PASSWORD", "demo12345")

    for username in ("demo1", "demo2"):
        if not User.objects.filter(username=username).exists():
            User.objects.create_user(
                username=username,
                password=demo_password,
                email=f"{username}@example.com",
            )


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0002_createsuperuser"),
    ]

    operations = [
        migrations.RunPython(create_demo_users),
    ]
