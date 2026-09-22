"""Service registry context for decoupled component access."""

from __future__ import annotations

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
    url_launcher: Any = None
    clipboard: Any = None
    permission_handler: Any = None
    audio_recorder: Any = None


ServiceCtx = ft.create_context(Services())


def use_services() -> Services:
    """Retrieve application services from context."""
    return ft.use_context(ServiceCtx)


__all__ = ["ServiceCtx", "Services", "use_services"]
