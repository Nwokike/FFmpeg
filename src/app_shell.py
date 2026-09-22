"""AppShell — Router-based top-level shell.

Flet 1.0 ft.Router (manage_views=True) owns the view stack: each route
component returns a ft.View, so Android back/swipe-back walk the real
navigation history instead of dumping to the dashboard. The dashboard route
carries the NavigationBar; tool routes are full-screen with their own back
rows. Onboarding sits above the Router as a single-view tree until accepted.
"""

from __future__ import annotations

import logging

import flet as ft

from components.jobs_banner import jobs_banner_view
from components.offline_banner import offline_banner_view
from core.state import state
from core.theme import PRIMARY, is_dark_mode
from core.tokens import SPACE_MD
from screens.audio_screen import AudioScreen
from screens.compress_screen import CompressScreen
from screens.convert_screen import ConvertScreen
from screens.cut_screen import CutScreen
from screens.engine_info_screen import EngineInfoScreen
from screens.extract_screen import ExtractScreen
from screens.filters_screen import FiltersScreen
from screens.history_screen import HistoryScreen
from screens.home_screen import HomeScreen
from screens.onboarding_screen import OnboardingScreen
from screens.probe_screen import ProbeScreen
from screens.result_screen import ResultScreen
from screens.settings_screen import SettingsScreen
from state.controller_ctx import use_controller

logger = logging.getLogger("AppShell")

_TAB_NAMES = ("Home", "Jobs", "Settings")
_TAB_ICONS = (ft.Icons.HOME_OUTLINED, ft.Icons.HISTORY_ROUNDED, ft.Icons.SETTINGS_OUTLINED)
_TAB_SELECTED_ICONS = (ft.Icons.HOME_ROUNDED, ft.Icons.HISTORY_ROUNDED, ft.Icons.SETTINGS_ROUNDED)


def _shell_body(content: ft.Control, *, bottom_inset: bool) -> ft.Container:
    """Banners run full-width; tool content gets the horizontal gutter.

    ``bottom_inset`` keeps dashboard content clear of the NavigationBar —
    tool routes are full-screen and need none.
    """
    is_dark = is_dark_mode(ft.context.page)
    return ft.Container(
        content=ft.Column(
            controls=[
                offline_banner_view(state.is_online),
                jobs_banner_view(state.active_job, is_dark=is_dark),
                ft.Container(
                    content=content,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=SPACE_MD),
                ),
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
        padding=ft.Padding.only(bottom=88) if bottom_inset else 0,
    )


def _build_navigation_bar(ctrl) -> ft.NavigationBar:
    """Dashboard NavigationBar — declared on the view, never mutated post-hoc."""

    def _on_tab_change(e):
        idx = e.control.selected_index
        if idx == state.selected_tab:
            return
        ctrl.select_tab(idx)

    return ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=icon, label=label)
            for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
        ],
        selected_index=state.selected_tab,
        on_change=_on_tab_change,
        bgcolor=ft.Colors.SURFACE,
        indicator_color=ft.Colors.with_opacity(0.12, PRIMARY),
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
    )


def _onboarding_gate() -> ft.View | None:
    """Onboarding view while terms are unaccepted.

    The gate lives INSIDE the route views rather than above the Router: the
    view list from render_views is established at boot, so a Router mounted
    mid-session (after "Get Started") would never be adopted. Swapping view
    CONTENT on the observable flip is the same control-swap pattern Sherlock
    uses under single-view render.
    """
    if state.has_accepted_terms:  # observable read → re-render on flip
        return None
    return ft.View(controls=[OnboardingScreen(key=ft.ValueKey("onboarding"))])


@ft.component
def _dashboard_view() -> ft.View:
    """Index route: tabbed Home / Jobs (history) / Settings with the nav bar."""
    gate = _onboarding_gate()
    if gate is not None:
        return gate

    ctrl = use_controller()
    selected_tab = state.selected_tab  # observable read → re-renders on tab change

    if selected_tab == 0:
        content = HomeScreen(key=ft.ValueKey("home"))
    elif selected_tab == 1:
        content = HistoryScreen(key=ft.ValueKey("history"))
    else:
        content = SettingsScreen(key=ft.ValueKey("settings"))

    return ft.View(
        controls=[_shell_body(content, bottom_inset=True)],
        navigation_bar=_build_navigation_bar(ctrl),
    )


def _tool_view(screen_factory, name: str):
    """Wrap a full-screen tool route: banners + gutters, no nav bar.

    Returning ft.View lets ft.Router manage the stack (system back, swipe-back,
    AppBar semantics) — pop navigates structurally to the parent route.
    """

    @ft.component
    def _route_view() -> ft.View:
        gate = _onboarding_gate()
        if gate is not None:
            return gate
        return ft.View(
            controls=[
                _shell_body(
                    screen_factory(key=ft.ValueKey(name)), bottom_inset=False
                )
            ]
        )

    return _route_view


_ROUTES = [
    ft.Route(index=True, component=_dashboard_view),
    ft.Route(path="convert", component=_tool_view(ConvertScreen, "convert")),
    ft.Route(path="compress", component=_tool_view(CompressScreen, "compress")),
    ft.Route(path="cut", component=_tool_view(CutScreen, "cut")),
    ft.Route(path="extract", component=_tool_view(ExtractScreen, "extract")),
    ft.Route(path="filters", component=_tool_view(FiltersScreen, "filters")),
    ft.Route(path="audio", component=_tool_view(AudioScreen, "audio")),
    ft.Route(path="probe", component=_tool_view(ProbeScreen, "probe")),
    ft.Route(path="engine-info", component=_tool_view(EngineInfoScreen, "engine-info")),
    ft.Route(path="result", component=_tool_view(ResultScreen, "result")),
]


@ft.component
def AppShell() -> ft.Control:
    """Master shell — always the Router; onboarding gates INSIDE route views.

    manage_views=True → Router emits ft.View per route level, consumed by
    page.render_views (see main.py). Mounting the Router unconditionally at
    boot keeps the view-list structure stable for the whole session; deep
    links (ffmpeg://app/...) land in page.route and match these templates.
    """
    return ft.Router(_ROUTES, not_found=HomeScreen, manage_views=True)
