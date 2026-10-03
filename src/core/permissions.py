"""Shared permission-gate helper (extracted from capture's inline flow).

One place for the get→ask→request→rationale sequence so save/share flows
can pre-check without duplicating it. Behavior is capture's contract:
ok→True, anything else→False after showing the rationale UI via callback.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def next_permission_action(status: Any, just_requested: bool = False) -> str:
    """Map a permission status to the next UI action.

    Returns one of: ``ok`` | ``ask`` | ``explain`` | ``settings`` |
    ``unavailable``. (Duplicated from capture_screen for import-light use —
    both must agree; the honesty test pins parity.)
    """
    val = str(getattr(status, "value", status) or "").lower()
    if val in ("granted", "limited", "provisional"):
        return "ok"
    if val in ("permanentlydenied",):
        return "settings"
    if val in ("restricted",):
        return "unavailable"
    if val in ("denied",):
        return "explain" if just_requested else "ask"
    return "explain" if just_requested else "ask"


async def check_permission(
    handler: Any,
    permission: Any,
    on_rationale=None,
) -> bool:
    """Run get→ask→request; True only on grant. Rationale via callback.

    ``handler``/``permission`` None (platform without the plugin) returns
    False — callers with a cheaper fallback (mic's AudioRecorder check)
    try that first instead.
    """
    if handler is None or permission is None:
        return False
    try:
        status = await handler.get_status(permission)
        action = next_permission_action(status, just_requested=False)
        if action == "ask":
            status = await handler.request(permission)
            action = next_permission_action(status, just_requested=True)
        if action == "ok":
            return True
        if on_rationale is not None:
            on_rationale(permission, action)
        return False
    except Exception:
        logger.exception("Permission flow failed")
        return False


__all__ = ["check_permission", "next_permission_action"]
