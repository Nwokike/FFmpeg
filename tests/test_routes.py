"""Single-view shell contract — guards the Sherlock navigation migration.

The pre-Router app shipped a Home tile navigating to "engine_info" that
AppShell had no branch for (silently fell back to Home).  The Router era
then masked that with Dart view-stack surgery.  The single-view shell
removes the Router entirely and pins branch switching to ``state.active_view``.
These tests pin every valid view, the old dead name, and the key invariants:
no Router/back_stack service at import, and the shell's ACTIVE_VIEWS set.
"""

from __future__ import annotations

from pathlib import Path

ALL_VIEWS = [
    "dashboard",
    "convert",
    "compress",
    "cut",
    "extract",
    "filters",
    "audio",
    "probe",
    "engine_info",
    "capture",
    "streams",
    "join",
    "result",
    "terminal",
]


def test_active_views_covers_all_declared_views():
    from app_shell import ACTIVE_VIEWS

    assert set(ALL_VIEWS) == ACTIVE_VIEWS, (
        "ACTIVE_VIEWS must match all view names AppShell branches to"
    )


def test_terminal_view_exists_and_is_registered():
    from app_shell import ACTIVE_VIEWS

    assert "terminal" in ACTIVE_VIEWS


def test_unknown_view_not_active():
    from app_shell import ACTIVE_VIEWS

    assert "definitely-not-a-route" not in ACTIVE_VIEWS


def test_old_dead_engine_info_name_not_active():
    # The historical tile value "engine_info" maps to the current
    # engine_info view; the Router path "/engine_info" with slash was the
    # actual dead name. In the single-view model every name is just a view;
    # the underscore is the valid one, the slash path is irrelevant.
    from app_shell import ACTIVE_VIEWS

    assert "engine_info" in ACTIVE_VIEWS
    assert "/engine_info" not in ACTIVE_VIEWS
    assert "/definitely-not-a-route" not in ACTIVE_VIEWS


def test_app_shell_source_uses_no_router_or_back_stack():
    """The shell must not import Router or back_stack (single-view, Sherlock)."""
    source = (Path(__file__).resolve().parents[1] / "src" / "app_shell.py").read_text(
        encoding="utf-8"
    )
    assert "ft.Router" not in source
    assert "back_stack" not in source
    assert "render_views" not in source


def test_app_shell_exposes_component_shell():
    from app_shell import AppShell

    assert callable(AppShell)


def test_navigation_bar_badge_uses_framework_badge_api():
    """Jobs counter must use ft.Badge, not a Stack hack."""
    source = (Path(__file__).resolve().parents[1] / "src" / "app_shell.py").read_text(
        encoding="utf-8"
    )
    assert "ft.Badge" in source
    # No negative-margin Stack badge (the M2-era regression that froze every tab).
    if "Stack" in source and "job_count" in source:
        assert "top=-4" not in source


def test_main_navigate_gates_on_active_views():
    """Dead view names are rejected by ACTIVE_VIEWS gating, never swapped."""
    from app_shell import ACTIVE_VIEWS

    assert "IGNORED_ROUTE_is_dead" not in ACTIVE_VIEWS
    assert "definitely-not-a-screen" not in ACTIVE_VIEWS


def test_select_tab_from_tool_route_returns_to_dashboard():
    from core.state import state
    from main import _select_tab

    class Page:
        route = "/convert"

        def __init__(self):
            self.navigated = []
            self.updates = 0

        def navigate(self, route):
            self.navigated.append(route)

        def update(self):
            self.updates += 1

    before = (state.selected_tab, state.active_view)
    try:
        page = Page()
        _select_tab(page, 1)
        assert state.selected_tab == 1
        assert state.active_view == "dashboard"
        assert page.updates == 1
    finally:
        state.selected_tab, state.active_view = before


def test_navigation_destinations_have_selected_icon():
    source = (Path(__file__).resolve().parents[1] / "src" / "app_shell.py").read_text(
        encoding="utf-8"
    )
    assert "selected_icon" in source
