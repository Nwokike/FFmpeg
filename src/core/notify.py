"""Never-raising SnackBar helper (Sherlock pattern).

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
    """Show a floating SnackBar; never raises, never pops a real dialog."""
    try:
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=bgcolor or ft.Colors.BLACK,
            duration=duration_ms,
        )
        if action is not None:
            snack.action = action
        try:
            page.show_dialog(snack)
        except RuntimeError:
            popped = page.pop_dialog()
            # Only re-show if we popped nothing (None) or a prior SnackBar.
            # Popping a real AlertDialog here would close the user's dialog —
            # never do that (Sherlock guard).
            if popped is None or isinstance(popped, ft.SnackBar):
                page.show_dialog(snack)
            else:
                logger.info(
                    "Snack suppressed: %r dialog was open",
                    type(popped).__name__,
                )
    except Exception as exc:
        logger.warning("Snack failed: %s", exc)


__all__ = ["ERROR", "SUCCESS", "show_snack"]
