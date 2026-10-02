"""AppShell — single-view top-level shell (Sherlock pattern).

One Flet ``View`` for the whole session; navigation is ``use_state``
branching (``active_view`` + ``active_tab``), never a Router view stack.
``page.views`` stays length 1 forever, so the Dart Navigator has nothing
to underflow and Android back maps to in-app navigation instead of pops.
Onboarding gates the single branch until terms are accepted.
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
_TAB_ICONS = (ft.Icons.HOME_OUTLINED, ft.Icons.WORK_HISTORY_OUTLINED, ft.Icons.SETTINGS_OUTLINED)
_TAB_SELECTED_ICONS = (
    ft.Icons.HOME_ROUNDED,
    ft.Icons.WORK_HISTORY_ROUNDED,
    ft.Icons.SETTINGS_ROUNDED,
)


def clamp_tab(idx: int) -> int:
    """Pin a tab index to the valid range — corruption renders Home, not Settings."""
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        return 0
    return max(0, min(idx, len(_TAB_NAMES) - 1))


# Every active_view the shell can branch to. Unknown names never render —
# main.navigate() rejects them before they reach here.
ACTIVE_VIEWS = frozenset(
    {
        "dashboard",
        "convert",
        "compress",
        "cut",
        "extract",
        "filters",
        "audio",
        "probe",
        "engine_info",
        "result",
        "capture",
        "streams",
        "join",
        "terminal",
    }
)


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
    """Dashboard NavigationBar — declared on the view, rebuilt on queue change."""
    if app_state is None:
        app_state = state

    def _on_tab_change(e):
        idx = clamp_tab(e.control.selected_index)
        if idx == app_state.selected_tab:
            return
        ctrl.select_tab(idx)

    job_count = len(app_state.jobs)

    destinations = []
    for i, (icon, selected_icon, label) in enumerate(
        zip(_TAB_ICONS, _TAB_SELECTED_ICONS, _TAB_NAMES, strict=True)
    ):
        if i == 1 and job_count > 0:
            # ft.Badge is the framework's badge API. The bar is rebuilt (not
            # mutated) whenever the count changes — see _sync_chrome — so the
            # badge label always matches the queue.
            icon_control = ft.Badge(
                label=ft.Text(
                    str(min(job_count, 99)),
                    size=9,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                bgcolor=ACCENT_RED,
            )
            destinations.append(
                ft.NavigationBarDestination(
                    icon=ft.Icon(icon),
                    selected_icon=ft.Icon(selected_icon),
                    label=label,
                    badge=icon_control,
                )
            )
        else:
            destinations.append(
                ft.NavigationBarDestination(
                    icon=ft.Icon(icon),
                    selected_icon=ft.Icon(selected_icon),
                    label=label,
                )
            )

    return ft.NavigationBar(
        destinations=destinations,
        selected_index=clamp_tab(app_state.selected_tab),
        on_change=_on_tab_change,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
    )


def _should_show_onboarding(app_state: AppState) -> bool:
    return not app_state.has_accepted_terms


@ft.component
def AppShell() -> ft.Control:
    """Top-level shell. Branches: onboarding, dashboard tabs, or a tool view.

    Single-view shell (Sherlock pattern): the one root view's content swaps
    by ``active_view``/``active_tab`` state. Tool views render full-screen
    (no nav bar); the dashboard renders the tabbed Home / Jobs / Settings
    with the nav bar synced onto the root view.
    """
    # Branch on GLOBAL state.active_view with a local mirror: the shell seeds
    # from global (so pre-mount navigate() survives first render) and syncs
    # local←global whenever main drives navigation externally. Local-only
    # writes were the re-entry stuck bug (global said "convert" while the
    # shell showed dashboard, and the next navigate() no-op'd).
    initial_view = state.active_view if state.active_view in ACTIVE_VIEWS else "dashboard"
    active_view, set_active_view = ft.use_state(initial_view)

    controller = use_controller()
    app_state = use_app_state()

    def _adopt_global_view() -> None:
        if state.active_view in ACTIVE_VIEWS and state.active_view != active_view:
            set_active_view(state.active_view)

    ft.use_effect(_adopt_global_view)

    # Single source of truth: global selected_tab (shared with main._select_tab
    # and handle_system_back).  A local active_tab drifted from global and
    # silently froze History/Settings (Sherlock never has a second tab state).
    active_tab = clamp_tab(app_state.selected_tab)

    def set_active_tab(idx: int) -> None:
        idx = clamp_tab(idx)
        app_state.selected_tab = idx
        state.selected_tab = idx  # keep both aliases in sync

    # Inject view-local closures into the controller methods instance
    # (Sherlock pattern — main.navigate() drives these). Both write GLOBAL
    # state.active_view AND the local mirror, so neither can strand the other.
    def _go_dashboard() -> None:
        state.active_view = "dashboard"
        set_active_view("dashboard")

    def _show_view(view: str) -> None:
        if view in ACTIVE_VIEWS:
            state.active_view = view
            set_active_view(view)

    controller.show_view = _show_view
    controller.go_home = _go_dashboard
    controller.back = _go_dashboard

    def _system_back():
        # System/back button must never kill the single-view app.
        # Map it onto in-app navigation: tool views → dashboard,
        # settings/history tabs → home tab, home root → swallowed.
        if _should_show_onboarding(app_state):
            return
        if active_view != "dashboard":
            controller.back()
        elif active_tab != 0:
            set_active_tab(0)

    controller.handle_system_back = _system_back

    # Last queue length the nav bar was built for. Destinations are immutable
    # once built, so the bar is rebuilt (not mutated) whenever the count
    # flips between zero/non-zero or the capped label changes.
    last_nav_job_count, set_last_nav_job_count = ft.use_state(-1)

    def _sync_chrome():
        """Sync the root view's navigation bar to the current branch."""
        page = ft.context.page
        if not page or not page.views:
            return
        try:
            if _should_show_onboarding(app_state) or active_view != "dashboard":
                page.views[0].navigation_bar = None
            else:
                job_count = len(app_state.jobs)
                current_nav = page.views[0].navigation_bar
                if not isinstance(current_nav, ft.NavigationBar) or (
                    job_count != last_nav_job_count
                ):
                    page.views[0].navigation_bar = _build_navigation_bar(controller, app_state)
                    set_last_nav_job_count(job_count)
                else:
                    current_nav.selected_index = active_tab
            page.update()
        except Exception as exc:
            import logging as _lg

            _lg.getLogger(__name__).warning("Nav chrome sync failed: %s", exc, exc_info=True)

    ft.use_effect(
        _sync_chrome,
        [active_tab, active_view, app_state.has_accepted_terms, len(app_state.jobs)],
    )

    # --- Branching (lazy: only the active screen is constructed) ---
    if _should_show_onboarding(app_state):
        screen = OnboardingScreen(key=ft.ValueKey("onboarding"))
        return ft.SafeArea(content=screen, expand=True)

    if active_view == "dashboard":
        if active_tab == 0:
            content = HomeScreen(key=ft.ValueKey("home"))
        elif active_tab == 1:
            content = HistoryScreen(key=ft.ValueKey("history"))
        else:
            content = SettingsScreen(key=ft.ValueKey("settings"))
        body = _shell_body(content, app_state, header=BrandHeader())
    elif active_view == "convert":
        body = _shell_body(ConvertScreen(key=ft.ValueKey("convert")), app_state)
    elif active_view == "compress":
        body = _shell_body(CompressScreen(key=ft.ValueKey("compress")), app_state)
    elif active_view == "cut":
        body = _shell_body(CutScreen(key=ft.ValueKey("cut")), app_state)
    elif active_view == "extract":
        body = _shell_body(ExtractScreen(key=ft.ValueKey("extract")), app_state)
    elif active_view == "filters":
        body = _shell_body(FiltersScreen(key=ft.ValueKey("filters")), app_state)
    elif active_view == "audio":
        body = _shell_body(AudioScreen(key=ft.ValueKey("audio")), app_state)
    elif active_view == "probe":
        body = _shell_body(ProbeScreen(key=ft.ValueKey("probe")), app_state)
    elif active_view == "engine_info":
        body = _shell_body(EngineInfoScreen(key=ft.ValueKey("engine-info")), app_state)
    elif active_view == "capture":
        body = _shell_body(CaptureScreen(key=ft.ValueKey("capture")), app_state)
    elif active_view == "streams":
        body = _shell_body(StreamsScreen(key=ft.ValueKey("streams")), app_state)
    elif active_view == "join":
        body = _shell_body(JoinScreen(key=ft.ValueKey("join")), app_state)
    elif active_view == "result":
        body = _shell_body(ResultScreen(key=ft.ValueKey("result")), app_state)
    elif active_view == "terminal":
        body = _shell_body(TerminalScreen(key=ft.ValueKey("terminal")), app_state)
    else:
        logger.error("Unknown active_view %r — resetting to dashboard", active_view)
        state.active_view = "dashboard"
        body = _shell_body(HomeScreen(key=ft.ValueKey("home")), app_state)

    return ft.SafeArea(content=body, expand=True)
