"""Root application shell coordinating navigation, tab switches, and view routing."""

from __future__ import annotations

import flet as ft

from components.jobs_banner import jobs_banner_view
from components.offline_banner import offline_banner_view
from core.constants import APP_NAME
from core.state import state
from core.theme import PRIMARY, PRIMARY_DARK, is_dark_mode
from core.tokens import FONT_LG, FONT_XS, RADIUS_MD, SPACE_MD, SPACE_SM
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


@ft.component
def AppShell() -> ft.Control:
    """Master presentation layout containing appbar, active view, and navigation."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)

    # Gate: show onboarding deck until accepted
    if not state.has_accepted_terms:
        # Hide navigation bar on onboarding
        page.navigation_bar = None
        page.appbar = None
        return OnboardingScreen()

    active_view = state.active_view
    is_dashboard = active_view == "dashboard"

    # Synchronize bottom navigation bar
    nav_bar = ft.NavigationBar(
        selected_index=state.selected_tab,
        on_change=lambda e: ctrl.select_tab(e.control.selected_index),
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME_ROUNDED,
                label="Home",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_ROUNDED,
                selected_icon=ft.Icons.HISTORY_ROUNDED,
                label="Jobs",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS_ROUNDED,
                label="Settings",
            ),
        ],
    )

    # Attach or detach nav bar based on active view
    page.navigation_bar = nav_bar if is_dashboard else None

    # App bar with SVG logo tinted to white in dark mode or primary-dark in light mode
    logo_color = ft.Colors.WHITE if is_dark else PRIMARY_DARK
    logo_widget = ft.Image(
        src="icon.svg",
        width=28,
        height=28,
        fit=ft.BoxFit.CONTAIN,
        color=logo_color,
        color_blend_mode=ft.BlendMode.SRC_IN,
    )

    page.appbar = (
        ft.AppBar(
            leading=ft.Container(content=logo_widget, padding=ft.Padding.only(left=SPACE_MD)),
            title=ft.Text(APP_NAME, size=FONT_LG, weight=ft.FontWeight.BOLD),
            actions=[
                *(
                    [
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.SYSTEM_UPDATE_ROUNDED, size=14, color=PRIMARY),
                                    ft.Text(
                                        "UPDATE",
                                        size=FONT_XS,
                                        weight=ft.FontWeight.BOLD,
                                        color=PRIMARY,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=4),
                            border_radius=RADIUS_MD,
                            bgcolor="#1E3E1C" if is_dark else "#E2F4E0",
                            on_click=lambda _: ctrl.show_update_dialog(),
                            margin=ft.Margin.only(right=SPACE_MD),
                        )
                    ]
                    if state.update_available
                    else []
                )
            ],
            center_title=False,
        )
        if is_dashboard
        else None
    )

    # Resolve active view content
    view_content: ft.Control
    if is_dashboard:
        if state.selected_tab == 0:
            view_content = HomeScreen()
        elif state.selected_tab == 1:
            view_content = HistoryScreen()
        else:
            view_content = SettingsScreen()
    elif active_view == "convert":
        view_content = ConvertScreen()
    elif active_view == "compress":
        view_content = CompressScreen()
    elif active_view == "cut":
        view_content = CutScreen()
    elif active_view == "extract":
        view_content = ExtractScreen()
    elif active_view == "filters":
        view_content = FiltersScreen()
    elif active_view == "audio":
        view_content = AudioScreen()
    elif active_view == "probe":
        view_content = ProbeScreen()
    elif active_view == "result":
        view_content = ResultScreen()
    else:
        view_content = HomeScreen()

    return ft.Column(
        controls=[
            offline_banner_view(state.is_online),
            jobs_banner_view(state.active_job, is_dark=is_dark),
            ft.Container(
                content=view_content, expand=True, padding=ft.Padding.symmetric(horizontal=SPACE_MD)
            ),
        ],
        spacing=0,
        expand=True,
    )
