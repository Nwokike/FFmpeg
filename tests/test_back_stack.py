"""Back-stack contract, pinned to Flet 1.0.1's Dart page.dart behavior.

Verified facts these tests guard:

* ``_handleSystemPopRoute`` returns early when ``views.length <= 1`` and lets
  the framework finish the activity without emitting ``view_pop`` — so the
  ``/blank`` underlay must exist (and be re-pinned after every Router
  re-render, which replaces ``page.views`` wholesale).
* ``_markViewAsPopped`` filters views by route via
  ``_pendingPoppedViewRoutes`` — restoring a view therefore means a route
  re-key whose pathname still matches the Router.
* ``Control`` has no ``_page`` attribute — mount probes must use the ``page``
  property (the old ``getattr(ctrl, "_page")`` probe was always False, which
  permanently disabled camera capture).
"""

from __future__ import annotations

import flet as ft
from flet.components.component import Renderer

from core.back_stack import (
    UNDERLAY_ROUTE,
    background_app,
    ensure_back_underlay,
    restore_top_view,
    top_content_view,
)
from screens.capture_screen import _is_mounted


class _Page:
    """Minimal page stand-in: a views list plus recorded single-patch updates."""

    def __init__(self) -> None:
        self.views: list = []
        self.patches: list = []

    def update(self, *controls) -> None:
        self.patches.append(controls)


def _underlay() -> ft.View:
    return ft.View(route=UNDERLAY_ROUTE, controls=[ft.Container(expand=True)])


def _page_with(*routes: str) -> _Page:
    page = _Page()
    page.views = [_underlay(), *(ft.View(route=r, controls=[]) for r in routes)]
    return page


# ── ensure_back_underlay ─────────────────────────────────────────────────


def test_underlay_inserts_at_index_zero():
    page = _Page()
    page.views = [ft.View(route="/", controls=[])]
    ensure_back_underlay(page)
    assert [v.route for v in page.views] == [UNDERLAY_ROUTE, "/"]


def test_underlay_is_idempotent():
    page = _Page()
    page.views = [ft.View(route="/", controls=[])]
    ensure_back_underlay(page)
    ensure_back_underlay(page)
    assert sum(1 for v in page.views if v.route == UNDERLAY_ROUTE) == 1
    assert len(page.views) == 2


def test_underlay_skipped_while_views_empty_pre_render():
    page = _Page()
    ensure_back_underlay(page)
    assert page.views == []


def test_underlay_reasserted_after_router_replaces_views():
    """The Router rebuilds page.views on every route change — re-pin."""
    page = _Page()
    page.views = [ft.View(route="/", controls=[])]
    ensure_back_underlay(page)
    page.views = [ft.View(route="/convert", controls=[])]  # Router wipe
    ensure_back_underlay(page)
    assert [v.route for v in page.views] == [UNDERLAY_ROUTE, "/convert"]


def test_underlay_boot_phase_lazy_component_never_indexed():
    """render_views assigns the lazy root Component — indexing it raw raised
    'Component' object is not subscriptable and killed main() at boot."""

    @ft.component
    def _root():
        return ft.View(route="/", controls=[])

    page = _Page()
    page.views = Renderer().render(_root)  # _b is None until the first flush
    ensure_back_underlay(page)  # must not raise
    assert top_content_view(page) is None
    assert restore_top_view(page) is False


def test_underlay_pins_into_component_body_once_executed():
    @ft.component
    def _root():
        return [ft.View(route="/", controls=[])]

    page = _Page()
    comp = Renderer().render(_root)
    page.views = comp
    comp._b = [ft.View(route="/", controls=[])]  # first flush executed the body
    ensure_back_underlay(page)
    assert [v.route for v in comp._b] == [UNDERLAY_ROUTE, "/"]


# ── restore_top_view ─────────────────────────────────────────────────────


def test_restore_rekeys_top_view_and_single_patches():
    page = _page_with("/convert")
    top = page.views[-1]
    assert restore_top_view(page) is True
    assert top.route.startswith("/convert?back=")
    assert top.route.split("?", 1)[0] == "/convert"  # Router still matches
    assert page.patches[-1] == (top,)  # single immediate patch


def test_restore_keys_are_unique_across_repeated_backs():
    page = _page_with("/")
    restore_top_view(page)
    first = page.views[-1].route
    restore_top_view(page)
    second = page.views[-1].route
    assert first != second
    assert first.split("?", 1)[0] == second.split("?", 1)[0] == "/"


def test_restore_skips_underlay_and_reports_false():
    page = _Page()
    page.views = [_underlay()]
    assert top_content_view(page) is None
    assert restore_top_view(page) is False
    assert page.patches == []


def test_restore_rekeys_already_restored_route_from_base():
    page = _page_with("/")
    restore_top_view(page)
    stale = page.views[-1].route  # /?back=xxxx
    restore_top_view(page)
    fresh = page.views[-1].route
    assert stale.split("?", 1)[0] == fresh.split("?", 1)[0] == "/"
    assert fresh != stale


# ── background_app ───────────────────────────────────────────────────────


def test_background_app_is_noop_without_jnius():
    """pyjnius is an Android-runtime dep only — desktop must not raise."""
    page = _page_with("/")
    assert background_app(page) is False


# ── _is_mounted mount probe ──────────────────────────────────────────────


def test_is_mounted_none_is_false():
    assert _is_mounted(None) is False


def test_is_mounted_probes_page_property_not_private_attr():
    """The old getattr(ctrl, "_page") probe returned False for every control."""

    class Mounted:
        @property
        def page(self):
            return object()

    class Unmounted:
        @property
        def page(self):
            raise RuntimeError("Control must be added to the page first")

    assert _is_mounted(Mounted()) is True
    assert _is_mounted(Unmounted()) is False


def test_is_mounted_false_for_bare_flet_control():
    """A real control has no _page — the canonical .page probe must be used."""
    assert getattr(ft.Text("x"), "_page", None) is None
    assert _is_mounted(ft.Text("x")) is False
