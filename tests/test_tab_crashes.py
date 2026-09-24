"""Regression: History/Settings tab freezes.

Two crashes froze the dashboard with NO visible error (Flet's update scheduler
has no try/except, and page.on_error has zero dispatch sites in this build —
a render exception kills all further updates silently):

1. `ft.Positioned` does not exist in Flet 1.0 — the M2 queue badge raised
   AttributeError whenever state.jobs was non-empty, poisoning every tab.
2. `ft.Row(padding=...)` is invalid — the Dismissible backgrounds raised
   TypeError whenever history was non-empty.

Standalone render tests only assert wrapper non-None on EMPTY state, which is
why both slipped through. These tests populate state so the real code paths run.
"""

from __future__ import annotations

import pytest
from flet.components.component import Renderer

from app_shell import _build_navigation_bar, _dashboard_view
from core.state import Job, state
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from state.service_ctx import ServiceCtx, Services

pytestmark = pytest.mark.usefixtures("_isolated_state")


@pytest.fixture
def _isolated_state():
    """Snapshot/restore the state singleton around each test."""
    snap = (
        list(state.jobs),
        list(state.history),
        state.has_accepted_terms,
        state.selected_tab,
    )
    yield
    state.jobs, state.history = snap[0], snap[1]
    state.has_accepted_terms, state.selected_tab = snap[2], snap[3]


def _render(fn):
    r = Renderer()
    services, methods = Services(), ControllerMethods()
    return r.render(lambda: ServiceCtx(services, lambda: ControllerMethodsCtx(methods, fn)))


def test_nav_bar_renders_with_nonempty_queue():
    """Was AttributeError: ft.Positioned missing — froze Home/History/Settings."""
    state.has_accepted_terms = True
    state.jobs = [Job(op="convert", input_path="in.mp4", output_path="out.mp4", status="running")]
    comp = _render(lambda: _build_navigation_bar(ControllerMethods()))
    assert comp is not None


def test_dashboard_view_renders_with_jobs_and_badge():
    """Full dashboard path: banner + badge Stack/Margin construction."""
    state.has_accepted_terms = True
    state.jobs = [
        Job(op="convert", input_path="a.mp4", output_path="b.mp4", status="running"),
        Job(op="cut", input_path="c.mp4", output_path="d.mp4", status="pending"),
    ]
    comp = _render(_dashboard_view)
    assert comp is not None


def test_history_screen_renders_with_entries():
    """Was TypeError: Row(padding=...) — froze the History tab."""
    state.has_accepted_terms = True
    state.history = [
        Job(
            op="convert", input_path="C:/media/видео.mov", output_path="out.mp4", status="completed"
        ),
        Job(op="cut", input_path="", output_path="", status="failed"),
        Job(
            op="extract_audio",
            input_path="a very long path/" + "x" * 300,
            output_path="",
            status="cancelled",
        ),
        Job(
            op="record",
            input_path="https://例え.jp/live.m3u8",
            output_path="out.ts",
            status="completed",
        ),
    ]
    comp = _render(_history_screen_component())
    assert comp is not None


def _history_screen_component():
    from screens.history_screen import HistoryScreen

    return HistoryScreen


def test_settings_screen_renders():
    """Settings tab render (its probe effect is fire-and-forget via run_task)."""
    state.has_accepted_terms = True
    from screens.settings_screen import SettingsScreen

    comp = _render(SettingsScreen)
    assert comp is not None
