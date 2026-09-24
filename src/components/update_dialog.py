"""Update and release notes dialog rendering GITHUB_WEB markdown."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import flet as ft

from core.changelog import notes_for
from core.constants import APP_NAME, APP_VERSION, GITHUB_RELEASE_URL, PLAYSTORE_URL
from core.notify import ERROR, show_snack
from core.tokens import RADIUS_LG

logger = logging.getLogger(__name__)

# Release notes are REMOTE markdown — a tampered or hijacked manifest could
# otherwise hand the user any URL (market://, intent://, custom deep links) on
# a single tap. Only https links into the project's own domains may launch.
_ALLOWED_HOSTS = frozenset({"github.com", "raw.githubusercontent.com", "play.google.com"})


def is_allowed_launch_url(url: str) -> bool:
    """True for https URLs on the project's own domains (subdomains included)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    host = (parts.hostname or "").lower()
    return any(host == d or host.endswith(f".{d}") for d in _ALLOWED_HOSTS)


def build_update_dialog(
    page: ft.Page,
    update_data: dict | None = None,
    url_launcher: Any = None,
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

    def _launch(url: str) -> None:
        # Flet 1.0: URLs open via the registered UrlLauncher service (async),
        # never page.launch_url which no longer exists on Page.
        if not is_allowed_launch_url(url):
            logger.warning("Blocked non-allowlisted link: %r", url)
            show_snack(page, "That link isn't from an approved source", bgcolor=ERROR)
            return
        if url_launcher is None:
            logger.warning("UrlLauncher unavailable; cannot open %s", url)
            show_snack(page, "Couldn't open the link — no browser available", bgcolor=ERROR)
            return
        page.run_task(url_launcher.launch_url, url)

    def _open_download(_):
        url = PLAYSTORE_URL if (page.platform and page.platform.is_mobile()) else GITHUB_RELEASE_URL
        _launch(url)

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
                        on_tap_link=lambda e: _launch(e.data),
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
