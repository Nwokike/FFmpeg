"""Route template matching — guards against dead-route regressions.

The pre-Router app shipped a Home tile navigating to "engine_info" that
AppShell had no branch for (silently fell back to Home). These tests pin
every route including /engine-info and the old dead name.
"""

from __future__ import annotations

from pathlib import Path

from flet.components.router import _match_routes, _normalize_path

from app_shell import _ROUTES

ALL_ROUTES = [
    "/",
    "/convert",
    "/compress",
    "/cut",
    "/extract",
    "/filters",
    "/audio",
    "/probe",
    "/engine-info",
    "/capture",
    "/streams",
    "/join",
    "/result",
]


def test_every_declared_route_matches():
    for path in ALL_ROUTES:
        chain = _match_routes(_ROUTES, _normalize_path(path))
        assert chain is not None, f"{path} must match a route"


def test_unknown_route_does_not_match():
    assert _match_routes(_ROUTES, _normalize_path("/definitely-not-a-route")) is None


def test_old_dead_engine_info_name_is_not_a_route():
    # The historical tile value "engine_info" maps to /engine-info in
    # main.navigate; the underscore form itself must 404, not silently match.
    assert _match_routes(_ROUTES, _normalize_path("/engine_info")) is None


def test_index_route_matches_root_only():
    chain = _match_routes(_ROUTES, _normalize_path("/"))
    assert chain is not None
    assert chain[-1].route.index is True


def test_tool_routes_resolve_to_leaf_path():
    chain = _match_routes(_ROUTES, _normalize_path("/engine-info"))
    assert chain is not None
    assert chain[-1].route.path == "engine-info"


def test_router_views_declare_explicit_routes():
    source = (Path(__file__).resolve().parents[1] / "src" / "app_shell.py").read_text(
        encoding="utf-8"
    )
    assert 'route="/"' in source
    assert 'route=f"/{name}"' in source


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
        assert page.navigated == ["/"]
        assert page.updates == 0
    finally:
        state.selected_tab, state.active_view = before
