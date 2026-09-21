"""Service registry context for decoupled component access."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft


@dataclass
class Services:
    """Registered application services held with strong references."""

    storage: Any = None
    engine: Any = None
    media_io: Any = None
    ads: Any = None
    update: Any = None


_context = ft.create_context(Services())


def use_services() -> Services:
    """Retrieve application services from context."""
    return ft.use_context(_context)


@ft.component
def ServiceCtx(services: Services, content: Callable[[], ft.Control]):
    """Inject services into the widget tree."""
    return ft.ContextProvider(_context, services, content=content())
