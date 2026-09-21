"""Update and release notes dialog rendering GITHUB_WEB markdown."""

from __future__ import annotations

from typing import Any

import flet as ft

from core.changelog import notes_for
from core.constants import APP_NAME, APP_VERSION, GITHUB_RELEASE_URL, PLAYSTORE_URL
from core.tokens import RADIUS_LG


def build_update_dialog(
    page: ft.Page,
    update_data: dict | None = None,
    on_dismiss: Any = None,
) -> ft.AlertDialog:
    """Build modal dialog displaying changelog and download buttons."""
    is_update = update_data is not None
    version_title = (
        update_data.get("title", f"{APP_NAME} {APP_VERSION}")
        if update_data
        else f"{APP_NAME} {APP_VERSION}"
    )
    notes = (
        update_data.get("release_notes", notes_for(APP_VERSION))
        if update_data
        else notes_for(APP_VERSION)
    )
    is_mandatory = bool(update_data.get("mandatory", False)) if update_data else False

    def _open_download(_):
        url = PLAYSTORE_URL if (page.platform and page.platform.is_mobile()) else GITHUB_RELEASE_URL
        page.launch_url(url)

    actions = [
        ft.FilledButton(
            "Download Update" if is_update else "View on GitHub", on_click=_open_download
        ),
    ]
    if not is_mandatory:
        actions.append(ft.TextButton("Close", on_click=lambda _: page.pop_dialog()))

    return ft.AlertDialog(
        modal=is_mandatory,
        title=ft.Text(version_title, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Markdown(
                        notes,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: page.launch_url(e.data),
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
            width=400,
            height=300,
        ),
        actions=actions,
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=RADIUS_LG),
    )
