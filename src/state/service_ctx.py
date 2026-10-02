"""Service registry context for decoupled component access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flet as ft

#: Sentinel default: receiving THIS object means no provider is mounted.
_DEFAULT_SERVICES: Services | None = None  # set after the class definition


@dataclass(slots=True)
class Services:
    """Registered application services held with strong references.

    Locator-once by design: set once at the root (main mounts
    ``ServiceCtx(services, ...)``) and never swapped, so this plain
    dataclass is deliberately NOT observable — consumers do not re-render
    on service replacement because replacement never happens.
    """

    storage: Any = None
    engine: Any = None
    media_io: Any = None
    ads: Any = None
    update: Any = None
    url_launcher: Any = None
    clipboard: Any = None
    permission_handler: Any = None
    audio_recorder: Any = None
    queue: Any = None  # JobQueue: pause/cancel/queued reads for cards+banner


_DEFAULT_SERVICES = Services()

ServiceCtx = ft.create_context(_DEFAULT_SERVICES)


def use_services() -> Services:
    """Retrieve application services from context (render body only).

    Raises RuntimeError when no provider is mounted — a Services full of
    Nones failing far away as ``NoneType has no attribute`` is how missing
    providers used to surface, and it wasted hours.
    """
    services = ft.use_context(ServiceCtx)
    if services is _DEFAULT_SERVICES:
        raise RuntimeError(
            "ServiceCtx provider missing — mount ServiceCtx(services, ...) "
            "above this component (main does; tests must too)"
        )
    return services


__all__ = ["ServiceCtx", "Services", "use_services"]
