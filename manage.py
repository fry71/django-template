#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

from __future__ import annotations

import os
import sys

from django.core.management import execute_from_command_line

from api.config.base import BASE_DIR

_APPS_DIR = BASE_DIR / "api"
_TEMPLATE_DIR = BASE_DIR / "api" / "config" / "__app_template__"

type _AppName = str
type _AppDirectory = str


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.config.settings")

    _modify_startapp_args()
    execute_from_command_line(sys.argv)


def _modify_startapp_args() -> None:
    if "startapp" not in sys.argv:
        return

    _add_app_directory_if_not_provided()
    _add_template_if_not_provided()


def _add_template_if_not_provided() -> None:
    if "--no-template" in sys.argv:
        sys.argv.remove("--no-template")
    elif "--template" not in sys.argv:
        sys.argv.extend(("--template", str(_TEMPLATE_DIR)))


def _add_app_directory_if_not_provided() -> None:
    app_name, provided_directory = _get_app_parameters()
    if provided_directory:
        return

    app_directory = _APPS_DIR / app_name
    app_directory.mkdir(parents=True, exist_ok=True)

    position = sys.argv.index(app_name) + 1
    sys.argv.insert(position, str(app_directory))


def _get_app_parameters() -> tuple[_AppName, _AppDirectory]:
    arguments = _positional_arguments()
    app_name = ""
    app_directory = ""
    for argument in arguments:
        if not app_name:
            app_name = argument
        elif not app_directory:
            app_directory = argument
        else:
            msg = "Too many positional arguments for startapp command."
            raise ValueError(msg)
    return app_name, app_directory


def _positional_arguments() -> list[str]:
    arguments = sys.argv[sys.argv.index("startapp") + 1 :]
    positional = []
    for index, argument in enumerate(arguments):
        if _is_skipped(arguments, index):
            continue
        positional.append(argument)
    return positional


def _is_skipped(arguments: list[str], index: int) -> bool:
    previous = arguments[index - 1] if index > 0 else ""
    return previous.startswith("-") or arguments[index].startswith("-")


if __name__ == "__main__":
    main()
