"""AppShell — top-level shell branching onboarding vs dashboard.

Follows the proven ktv-player / CollabShell / spaninsight architecture:
- @ft.component reading observable AppState and ControllerMethods
- Page-level NavigationBar attached to page.views[0].navigation_bar via use_effect
- Clean declarative screen switching with explicit ValueKeys
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


@ft.component
def AppShell() -> ft.Control:
    """Master presentation layout containing appbar, active view, and navigation."""
    ctrl = use_controller()
    is_dark = is_dark_mode(ft.context.page)

    # Local tab index — controller mutates this via ctrl.select_tab
    from flet import context

    selected_tab, set_selected_tab = ft.use_state(state.selected_tab)

    def _sync_navigation_bar():
        page = context.page
        if not page or not page.views:
            return

        # Gate: hide nav bar during onboarding
        if not state.has_accepted_terms:
            if page.views[0].navigation_bar is not None:
                page.views[0].navigation_bar = None
                try:
                    page.update()
                except Exception:
                    logger.exception("Failed to clear NavigationBar during onboarding")
            return

        # Build destinations
        def _on_tab_change(e):
            idx = e.control.selected_index
            if idx == selected_tab:
                return
            set_selected_tab(idx)
            ctrl.select_tab(idx)

        destinations = [
            ft.NavigationBarDestination(icon=icon, label=label)
            for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
        ]
        page.views[0].navigation_bar = ft.NavigationBar(
            destinations=destinations,
            selected_index=selected_tab,
            on_change=_on_tab_change,
            bgcolor=ft.Colors.SURFACE,
            indicator_color=ft.Colors.with_opacity(0.12, PRIMARY),
            label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        )
        try:
            page.update()
        except Exception:
            logger.exception("Failed to sync NavigationBar")

    ft.use_effect(_sync_navigation_bar, [selected_tab, state.has_accepted_terms])

    # Gate: show onboarding deck until accepted
    if not state.has_accepted_terms:
        return OnboardingScreen()

    active_view = state.active_view
    is_dashboard = active_view == "dashboard"

    # Resolve active view content
    view_content: ft.Control
    if is_dashboard:
        if selected_tab == 0:
            view_content = HomeScreen(key=ft.ValueKey("home"))
        elif selected_tab == 1:
            view_content = HistoryScreen(key=ft.ValueKey("history"))
        else:
            view_content = SettingsScreen(key=ft.ValueKey("settings"))
    elif active_view == "convert":
        view_content = ConvertScreen(key=ft.ValueKey("convert"))
    elif active_view == "compress":
        view_content = CompressScreen(key=ft.ValueKey("compress"))
    elif active_view == "cut":
        view_content = CutScreen(key=ft.ValueKey("cut"))
    elif active_view == "extract":
        view_content = ExtractScreen(key=ft.ValueKey("extract"))
    elif active_view == "filters":
        view_content = FiltersScreen(key=ft.ValueKey("filters"))
    elif active_view == "audio":
        view_content = AudioScreen(key=ft.ValueKey("audio"))
    elif active_view == "probe":
        view_content = ProbeScreen(key=ft.ValueKey("probe"))
    elif active_view == "result":
        view_content = ResultScreen(key=ft.ValueKey("result"))
    else:
        view_content = HomeScreen(key=ft.ValueKey("home"))

    return ft.Column(
        controls=[
            offline_banner_view(state.is_online),
            jobs_banner_view(state.active_job, is_dark=is_dark),
            ft.Container(
                content=view_content,
                expand=True,
                padding=ft.Padding.symmetric(horizontal=SPACE_MD),
            ),
        ],
        spacing=0,
        expand=True,
    )
