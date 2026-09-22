"""Controller methods context for decoupled component actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from core.state import Job


@dataclass
class ControllerMethods:
    """Methods exposed by AppController to UI components."""

    navigate: Callable[[str], None] = lambda view: None
    select_tab: Callable[[int], None] = lambda tab: None
    pick_media_for: Callable[[str], Any] = lambda target: None
    start_job: Callable[[Job], Any] = lambda job: None
    cancel_job: Callable[[str], Any] = lambda job_id: None
    toggle_pause_job: Callable[[], None] = lambda: None
    delete_job: Callable[[str], None] = lambda job_id: None
    restore_job: Callable[[Job], None] = lambda job: None
    retry_job: Callable[[Job], Any] = lambda job: None
    finish_onboarding: Callable[[], None] = lambda: None
    share_result: Callable[[Job], Any] = lambda job: None
    save_result: Callable[[Job], Any] = lambda job: None
    clear_history: Callable[[], None] = lambda: None
    check_update: Callable[[], Any] = lambda: None
    show_update_dialog: Callable[[], None] = lambda: None
    toggle_theme: Callable[[], None] = lambda: None


ControllerMethodsCtx = ft.create_context(ControllerMethods())


def use_controller() -> ControllerMethods:
    """Retrieve the nearest controller methods from context."""
    return ft.use_context(ControllerMethodsCtx)


__all__ = ["ControllerMethods", "ControllerMethodsCtx", "use_controller"]
