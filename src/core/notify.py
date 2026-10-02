"""Never-raising SnackBar helper.

All transient user feedback funnels through :func:`show_snack` so a failed
toast can never take down the interaction it is reporting on.

Contract: at most one live SnackBar per page (the same instance is
reused, so identical re-toasts replace instead of colliding on the
dialog stack's value-equality check). A toast never costs a real
dialog anything: the stack allows stacking, so a toast over an open
dialog is transient and harmless — and critically, nothing here ever
calls ``pop_dialog``, which is what used to destroy the user's dialog
before we even learned what it was. Returns True when the toast is on
screen, False only when the page itself could not show it.
"""

from __future__ import annotations

import logging

import flet as ft

logger = logging.getLogger(__name__)

# House semantic pair (reused verbatim across sibling apps)
SUCCESS = "#2E7D32"
ERROR = "#D32F2F"

_SNACK_ATTR = "_house_snack"


def show_snack(
    page: ft.Page,
    message: str,
    *,
    bgcolor: str | None = None,
    duration_ms: int = 3000,
    action: ft.SnackBarAction | None = None,
) -> bool:
    """Show a floating SnackBar; never raises.

    Returns True when the toast is on screen, False when the page itself
    could not show it. Fire-and-forget callers can ignore the return;
    critical messages should escalate on False. A toast is never shown
    at the expense of a real dialog — nothing here pops, closes, or
    replaces anything but the one reused SnackBar instance.
    """
    try:
        if not isinstance(duration_ms, int) or isinstance(duration_ms, bool):
            logger.warning("Snack duration must be an int of ms, got %r", duration_ms)
            duration_ms = 3000
        if duration_ms <= 0:
            logger.warning("Snack duration must be positive, got %r", duration_ms)
            duration_ms = 3000

        snack = getattr(page, _SNACK_ATTR, None)
        if not isinstance(snack, ft.SnackBar):
            snack = ft.SnackBar(
                content=ft.Text("", color=ft.Colors.WHITE),
                bgcolor=ft.Colors.BLACK,
                duration=ft.Duration(milliseconds=3000),
            )
            setattr(page, _SNACK_ATTR, snack)
        snack.content = ft.Text(message, color=ft.Colors.WHITE)
        snack.bgcolor = bgcolor or ft.Colors.BLACK
        snack.duration = ft.Duration(milliseconds=duration_ms)
        snack.action = action

        try:
            page.show_dialog(snack)
        except RuntimeError:
            # The only RuntimeError show_dialog raises is "Dialog is already
            # opened": this same snack instance is still on the dialog stack
            # (a previous toast that hasn't been dismissed yet). Re-showing
            # it would raise again — the content above is already mutated in
            # place, so flush the update to the live instance instead. This
            # path never touches any other dialog on the stack.
            try:
                page.update(snack)
            except Exception:
                logger.info("Snack suppressed: dialog stack busy")
                return False
        return True
    except Exception as exc:
        logger.warning("Snack failed: %s", exc)
        return False


__all__ = ["ERROR", "SUCCESS", "show_snack"]
