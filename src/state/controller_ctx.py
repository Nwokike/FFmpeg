"""Controller methods context for decoupled component actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import flet as ft

from core.state import Job

# Fire-and-forget through page.run_task: main wraps these async impls as
# `lambda *a: page.run_task(fn, *a)`, so callers get a scheduled task, not a
# coroutine to await. Declared sync here on purpose — awaiting them would hang.
FireAndForget = Callable[..., Any]


@dataclass
class ControllerMethods:
    """Methods exposed by AppController to UI components.

    Call ``use_controller()`` only inside an ``@ft.component`` render body —
    it reads the render-time context and raises outside one. Defaults are
    inert no-ops so bare test doubles render without a provider.
    """

    navigate: Callable[[str], None] = lambda view: None
    select_tab: Callable[[int], None] = lambda tab: None
    handle_system_back: Callable[[], None] = lambda: None
    # Injected by AppShell at mount: swapping the single view's branch
    # directly. Non-optional no-op so every caller path is one branch, not two.
    show_view: Callable[[str], None] = lambda view: None
    # Written by AppShell alongside show_view; both flip GLOBAL active_view
    # plus the shell's local mirror, so back can never strand navigation.
    go_home: Callable[[], None] = lambda: None
    back: Callable[[], None] = lambda: None
    pick_media_for: FireAndForget = lambda target: None
    # return_to keeps the caller on screen (live Streams watches while the
    # record job runs); everything else lands on the dashboard.
    start_job: Callable[[Job], None] = lambda job, return_to=None: None
    cancel_job: Callable[[str], None] = lambda job_id: None
    # Per-job pause (queue holds the id at head / engine hook holds inside).
    toggle_pause_job: Callable[[str], None] = lambda job_id: None
    delete_job: Callable[[str], None] = lambda job_id: None
    # Whole-value insert at the captured index (undo restores position).
    restore_job: Callable[[Job, int], None] = lambda job, index=-1: None
    # Clear-All undo: restores the pre-clear snapshot (deduped by id).
    restore_all: Callable[[list], None] = lambda jobs: None
    retry_job: Callable[[Job], None] = lambda job: None
    finish_onboarding: Callable[[], None] = lambda: None
    share_result: FireAndForget = lambda job: None
    save_result: FireAndForget = lambda job: None
    clear_history: Callable[[], None] = lambda: None
    check_update: FireAndForget = lambda: None
    show_update_dialog: Callable[[], None] = lambda: None
    toggle_theme: Callable[[], None] = lambda: None


ControllerMethodsCtx = ft.create_context(ControllerMethods())


def use_controller() -> ControllerMethods:
    """Retrieve the nearest controller methods from context (render body only)."""
    return ft.use_context(ControllerMethodsCtx)


__all__ = ["ControllerMethods", "ControllerMethodsCtx", "use_controller"]
