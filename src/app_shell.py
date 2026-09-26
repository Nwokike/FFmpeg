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

from components.brand_header import BrandHeader
from components.jobs_banner import jobs_banner_view
from components.offline_banner import offline_banner_view
from core.state import AppState, state, use_app_state
from core.theme import ACCENT_RED, is_dark_mode
from core.tokens import SPACE_MD
from screens.audio_screen import AudioScreen
from screens.capture_screen import CaptureScreen
from screens.compress_screen import CompressScreen
from screens.convert_screen import ConvertScreen
from screens.cut_screen import CutScreen
from screens.engine_info_screen import EngineInfoScreen
from screens.extract_screen import ExtractScreen
from screens.filters_screen import FiltersScreen
from screens.history_screen import HistoryScreen
from screens.home_screen import HomeScreen
from screens.join_screen import JoinScreen
from screens.onboarding_screen import OnboardingScreen
from screens.probe_screen import ProbeScreen
from screens.result_screen import ResultScreen
from screens.settings_screen import SettingsScreen
from screens.streams_screen import StreamsScreen
from screens.terminal_screen import TerminalScreen
from state.controller_ctx import use_controller

logger = logging.getLogger("AppShell")

_TAB_NAMES = ("Home", "Jobs", "Settings")
_TAB_ICONS = (ft.Icons.HOME_OUTLINED, ft.Icons.HISTORY_ROUNDED, ft.Icons.SETTINGS_OUTLINED)
_TAB_SELECTED_ICONS = (ft.Icons.HOME_ROUNDED, ft.Icons.HISTORY_ROUNDED, ft.Icons.SETTINGS_ROUNDED)


def _shell_body(
    content: ft.Control,
    app_state: AppState,
    *,
    header: ft.Control | None = None,
) -> ft.Container:
    """Banners run full-width; screen content gets the horizontal gutter.

    Nav-bar clearance lives INSIDE each dashboard screen's scroll (trailing
    spacer, sibling pattern). The top status-bar inset is handled by a top-only
    SafeArea wrapping the header on the dashboard, or a zero-height spacer on
    tool screens, ensuring the body container remains an Expanded child of
    View's column so Flutter scroll views receive valid flex constraints.
    """
    is_dark = is_dark_mode(ft.context.page, app_state)
    # SafeArea has no bottom/left/right fields — those names silently bind to
    # LayoutControl's absolute-position offsets (Optional[Number]), so passing
    # False there ships bools into Dart double? fields ("type 'bool' is not a
    # subtype of type 'double?'" storm). The avoid_intrusions_* flags are the
    # real API: top inset only, banners stay full-width.
    top_bar = (
        ft.SafeArea(
            content=header,
            avoid_intrusions_bottom=False,
            avoid_intrusions_left=False,
            avoid_intrusions_right=False,
        )
        if header is not None
        else ft.SafeArea(
            content=ft.Container(height=0),
            avoid_intrusions_bottom=False,
            avoid_intrusions_left=False,
            avoid_intrusions_right=False,
        )
    )
    return ft.Container(
        content=ft.Column(
            controls=[
                top_bar,
                offline_banner_view(app_state.is_online),
                jobs_banner_view(app_state.active_job, is_dark=is_dark),
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
    )


def _build_navigation_bar(ctrl, app_state: AppState | None = None) -> ft.NavigationBar:
    """Dashboard NavigationBar — declared on the view, never mutated post-hoc."""
    if app_state is None:
        app_state = state

    def _on_tab_change(e):
        idx = e.control.selected_index
        if idx == app_state.selected_tab:
            return
        ctrl.select_tab(idx)

    job_count = len(app_state.jobs)  # observable read → badge re-renders on queue change

    def _icon_with_badge(base: ft.IconData):
        if job_count <= 0:
            return base
        # Flet 1.0 has NO ft.Positioned (M2 regression that froze every tab) —
        # the counter rides the icon via negative/offset margins inside a Stack.
        return ft.Stack(
            controls=[
                ft.Icon(base),
                ft.Container(
                    width=16,
                    height=16,
                    border_radius=8,
                    bgcolor=ACCENT_RED,
                    alignment=ft.Alignment.CENTER,
                    margin=ft.Margin(left=16, top=-4, right=0, bottom=0),
                    content=ft.Text(
                        str(min(job_count, 99)),
                        size=9,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ),
            ],
        )

    destinations = []
    for i, (icon, label) in enumerate(zip(_TAB_ICONS, _TAB_NAMES, strict=True)):
        icon_control = _icon_with_badge(icon) if i == 1 else icon
        destinations.append(ft.NavigationBarDestination(icon=icon_control, label=label))

    return ft.NavigationBar(
        destinations=destinations,
        selected_index=app_state.selected_tab,
        on_change=_on_tab_change,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
    )


def _onboarding_gate(app_state: AppState | None = None) -> ft.View | None:
    """Onboarding view while terms are unaccepted.

    The gate lives inside each route view and reads the subscribed AppStateCtx.
    The Router is mounted once; accepting terms swaps the route content without
    rebuilding page.views or losing its back-stack/deep-link state.
    """
    if app_state is None:
        app_state = state
    if app_state.has_accepted_terms:  # observable read → re-render on flip
        return None
    return ft.View(route="/", controls=[OnboardingScreen(key=ft.ValueKey("onboarding"))])


@ft.component
def _dashboard_view() -> ft.View:
    """Index route: tabbed Home / Jobs (history) / Settings with the nav bar."""
    app_state = use_app_state()
    gate = _onboarding_gate(app_state)
    if gate is not None:
        return gate

    ctrl = use_controller()
    selected_tab = app_state.selected_tab  # observable read → re-renders on tab change

    if selected_tab == 0:
        content = HomeScreen(key=ft.ValueKey("home"))
    elif selected_tab == 1:
        content = HistoryScreen(key=ft.ValueKey("history"))
    else:
        content = SettingsScreen(key=ft.ValueKey("settings"))

    return ft.View(
        route="/",
        controls=[_shell_body(content, app_state, header=BrandHeader())],
        # ft.View defaults to Padding.all(10); _shell_body owns the gutters,
        # so the default would stack a second inset on every screen.
        padding=ft.Padding.all(0),
        navigation_bar=_build_navigation_bar(ctrl, app_state),
    )


def _tool_view(screen_factory, name: str):
    """Wrap a full-screen tool route: banners + gutters, no nav bar.

    Returning ft.View lets ft.Router manage the stack (system back, swipe-back,
    AppBar semantics) — pop navigates structurally to the parent route.
    """

    @ft.component
    def _route_view() -> ft.View:
        app_state = use_app_state()
        gate = _onboarding_gate(app_state)
        if gate is not None:
            return gate
        return ft.View(
            route=f"/{name}",
            controls=[_shell_body(screen_factory(key=ft.ValueKey(name)), app_state)],
            padding=ft.Padding.all(0),  # gutters come from _shell_body
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
    ft.Route(path="capture", component=_tool_view(CaptureScreen, "capture")),
    ft.Route(path="streams", component=_tool_view(StreamsScreen, "streams")),
    ft.Route(path="join", component=_tool_view(JoinScreen, "join")),
    ft.Route(path="result", component=_tool_view(ResultScreen, "result")),
    ft.Route(path="terminal", component=_tool_view(TerminalScreen, "terminal")),
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
