"""Adaptive navigation chrome (the Asase pattern, three window classes).

- Compact  (< 600 px): bottom NavigationBar (phones).
- Medium   (600-839 px): icon + label NavigationRail.
- Expanded (>= 840 px): collapsible labelled sidebar (264 px <-> 72 px rail),
  collapse state persisted through StorageService.

Only chrome lives here; the tab state machine stays in the shell. Flet 1.1.2
APIs used: NavigationRail / NavigationRailDestination, page.width +
page.on_resize, Container(on_click/ink), ft.Animation.
"""

from __future__ import annotations

import flet as ft

from core.theme import (
    BORDER_DARK,
    BORDER_LIGHT,
    KIRI_DARK_2,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
)
from core.tokens import (
    ANIM_NORMAL,
    FONT_SM,
    ICON_MD,
    RADIUS_MD,
    SIDEBAR_EXPANDED_WIDTH,
    SIDEBAR_RAIL_WIDTH,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
    WINDOW_COMPACT_MAX,
    WINDOW_MEDIUM_MAX,
)

# (tab index, label, icon, selected icon)
NAV_ITEMS: tuple[tuple[int, str, ft.IconData, ft.IconData], ...] = (
    (0, "Home", ft.Icons.HOME_OUTLINED, ft.Icons.HOME_ROUNDED),
    (1, "Jobs", ft.Icons.WORK_HISTORY_OUTLINED, ft.Icons.WORK_HISTORY_ROUNDED),
    (2, "Settings", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS_ROUNDED),
)


def window_class(width: float | None) -> str:
    """M3 window-size class for a viewport width (unknown -> compact)."""
    if width is None:
        return "compact"
    if width <= WINDOW_COMPACT_MAX:
        return "compact"
    if width <= WINDOW_MEDIUM_MAX:
        return "medium"
    return "expanded"


def build_navigation_rail(active_tab: int, on_select) -> ft.NavigationRail:
    """Medium chrome: labelled icon rail."""
    return ft.NavigationRail(
        destinations=[
            ft.NavigationRailDestination(icon=icon, selected_icon=selected, label=label)
            for _, label, icon, selected in NAV_ITEMS
        ],
        selected_index=active_tab,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=SIDEBAR_RAIL_WIDTH,
        group_alignment=-0.9,
        indicator_color=ft.Colors.with_opacity(0.2, PRIMARY),
        on_change=on_select,
    )


def build_sidebar(
    active_tab: int,
    on_select,
    collapsed: bool,
    on_toggle_collapse,
    *,
    is_dark: bool = True,
    footer: ft.Control | None = None,
) -> ft.Container:
    """Expanded chrome: full labelled sidebar <-> collapsed rail."""
    border = BORDER_DARK if is_dark else BORDER_LIGHT
    bg = KIRI_DARK_2 if is_dark else "#FFFFFF"
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    rows: list[ft.Control] = []
    for idx, label, icon, selected in NAV_ITEMS:
        active = idx == active_tab
        rows.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            selected if active else icon,
                            size=ICON_MD,
                            color=PRIMARY if active else muted,
                        ),
                        *(
                            [
                                ft.Text(
                                    label,
                                    size=FONT_SM,
                                    weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_500,
                                    color=PRIMARY if active else None,
                                )
                            ]
                            if not collapsed
                            else []
                        ),
                    ],
                    spacing=SPACE_MD,
                    tight=True,
                ),
                padding=ft.Padding(SPACE_MD, SPACE_SM, SPACE_MD, SPACE_SM),
                border_radius=RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(0.12, PRIMARY) if active else None,
                ink=True,
                on_click=lambda _, i=idx: on_select(i),
            )
        )

    body = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.MENU_OPEN_ROUNDED if not collapsed else ft.Icons.MENU_ROUNDED,
                        tooltip="Collapse sidebar" if not collapsed else "Expand sidebar",
                        icon_color=muted,
                        on_click=lambda _e: on_toggle_collapse(),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER if collapsed else ft.MainAxisAlignment.START,
            ),
            *rows,
            ft.Container(expand=True),
            *([footer] if footer is not None else []),
        ],
        spacing=SPACE_XS,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
    return ft.Container(
        content=body,
        width=SIDEBAR_RAIL_WIDTH if collapsed else SIDEBAR_EXPANDED_WIDTH,
        bgcolor=bg,
        border=ft.Border(right=ft.BorderSide(1, border)),
        padding=ft.Padding.symmetric(horizontal=SPACE_SM, vertical=SPACE_SM),
        animate=ft.Animation(ANIM_NORMAL, ft.AnimationCurve.EASE_OUT),
    )
