"""System-back plumbing, verified against Flet 1.0.1's Dart ``page.dart``.

Flet's Android pop handler (``_handleSystemPopRoute``) returns early when the
view stack has length <= 1 and lets the framework finish the activity — no
``view_pop`` ever reaches Python. Our flat ``ft.Router`` emits exactly one
view per route, so system back closed the app from every screen. The KTV
Player pattern fixes that: keep an empty ``/blank`` underlay at ``views[0]``
so the stack is never length 1, intercept ``view_pop`` in Python — and when
the decision is NOT to pop (tab switch, onboarding gate, backgrounding),
re-key the top view's route so page.dart's pending-pop filter releases it.

Two details from the Dart source drive the design:

* ``_markViewAsPopped`` puts the popped route into ``_pendingPoppedViewRoutes``
  and ``_buildNavigator`` filters any view whose route is in that set. The
  entry is removed as soon as one build contains no view with that route, and
  is never re-added without a new pop — so one immediate route patch clears
  it permanently, even if a later component re-render re-stamps the original
  route.
* Navigator pages are keyed ``ValueKey(route)``; a fresh route value re-adds
  the page.

``page.update(view)`` maps to a direct ``session.patch_control`` — the single
immediate patch that wins over the coalescing component-update scheduler.
"""

from __future__ import annotations

import logging
import os
import uuid

import flet as ft

logger = logging.getLogger(__name__)

UNDERLAY_ROUTE = "/blank"

_activity = None


def _unwrap(control):
    try:
        from flet.components.public_utils import unwrap_component

        return unwrap_component(control)
    except Exception:
        return control


def ensure_back_underlay(page) -> None:
    """Pin an empty ``/blank`` view at ``views[0]`` (idempotent).

    The Router rebuilds ``page.views`` wholesale on every route change, so
    ``main.py`` re-runs this inside a ``page.update`` wrapper before every
    outgoing flush — boot, navigation, deep links and component re-renders
    all pass through it. Skipped while ``views`` is empty (pre-render).
    """
    views = page.views
    if not views:
        return
    if getattr(_unwrap(views[0]), "route", None) == UNDERLAY_ROUTE:
        return
    views.insert(0, ft.View(route=UNDERLAY_ROUTE, controls=[ft.Container(expand=True)]))


def top_content_view(page):
    """Top view excluding the /blank underlay, or None."""
    for view in reversed([_unwrap(v) for v in page.views]):
        if getattr(view, "route", None) != UNDERLAY_ROUTE:
            return view
    return None


def restore_top_view(page) -> bool:
    """Release page.dart's pending-pop filter for the top view.

    Re-keys the route with a unique query suffix (pathname unchanged, so the
    Router still matches it) and pushes it as a single immediate patch: the
    popped route leaves the view list, the pending entry clears permanently,
    and Navigator's ``ValueKey(route)`` re-adds the page.
    """
    view = top_content_view(page)
    if view is None:
        return False
    route = getattr(view, "route", None) or "/"
    base = route.split("?", 1)[0] or "/"
    view.route = f"{base}?back={uuid.uuid4().hex[:8]}"
    page.update(view)
    logger.debug("Restored popped view as %r", view.route)
    return True


def background_app(page) -> bool:
    """Send the Android task to background so in-flight jobs keep running.

    Flet's window close/hide APIs are Dart-guarded to desktop, so Android
    backgrounding goes through the activity directly — the same pyjnius
    resolution chain KTV Player uses. Best-effort: without pyjnius (desktop,
    tests) this logs at debug level and returns False. Deliberately no exit
    path: Android back never finishes the activity in this app.
    """
    activity = _get_activity()
    if activity is None:
        logger.debug("background_app unavailable (desktop or jnius missing)")
        return False
    try:
        activity.moveTaskToBack(True)
        return True
    except Exception as exc:
        logger.warning("background_app failed: %s", exc)
        return False


def _get_activity():
    """Resolve the live Android activity through jnius, KTV-style."""
    global _activity
    if _activity is not None:
        return _activity

    try:
        from jnius import autoclass
    except Exception:
        return None

    for cls_name in (
        os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
        "ng.kiri.ffmpeg.MainActivity",
        "net.flet.MainActivity",
        "com.flet.flet_android.MainActivity",
        "org.kivy.android.PythonActivity",
    ):
        if not cls_name:
            continue
        try:
            host = autoclass(cls_name)
            activity = getattr(host, "mActivity", None) or getattr(host, "mCurrentActivity", None)
            if activity:
                _activity = activity
                return activity
        except Exception as ex:
            logger.debug("Activity candidate %s unavailable: %s", cls_name, ex)
    return None
