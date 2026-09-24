"""Never-raising SnackBar helper (house pattern from Sherlock core/notify.py).

All transient user feedback funnels through :func:`show_snack` so a failed
toast can never take down the interaction it is reporting on.
"""

from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)

# House semantic pair (reused verbatim across sibling apps)
SUCCESS = "#2E7D32"
ERROR = "#D32F2F"


def show_snack(
    page: ft.Page,
    message: str,
    *,
    bgcolor: str | None = None,
    duration_ms: int = 3000,
    action: ft.SnackBarAction | None = None,
) -> None:
    """Show a floating SnackBar; never raises, logs instead."""
    snack = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=duration_ms,
    )
    if bgcolor:
        snack.bgcolor = bgcolor
    if action is not None:
        snack.action = action
    try:
        page.show_dialog(snack)
    except RuntimeError:
        # A dialog is already open — pop it only if it is a SnackBar, then retry.
        try:
            popped = page.pop_dialog()
            if isinstance(popped, ft.SnackBar):
                page.show_dialog(snack)
            else:
                logger.info("Snack suppressed: %r dialog was open", type(popped).__name__)
        except Exception as exc:
            logger.warning("Snack suppressed after pop failure: %s", exc)
    except Exception as exc:
        logger.warning("Snack failed: %s", exc)


__all__ = ["ERROR", "SUCCESS", "show_snack"]
