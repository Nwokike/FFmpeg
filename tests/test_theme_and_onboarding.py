"""Theme propagation and post-onboarding view swap — regression pins for the
'needs a restart / needs an extra tap' bugs."""

from __future__ import annotations

from pathlib import Path

import flet as ft
import pytest

from core.state import state
from core.theme import is_dark_mode

_ROOT = Path(__file__).resolve().parents[1]


class _FakePage:
    """Minimal Page stand-in — is_dark_mode only reads platform_brightness."""

    def __init__(self, brightness=ft.Brightness.LIGHT) -> None:
        self.platform_brightness = brightness


@pytest.fixture(autouse=True)
def _restore_theme():
    before = (state.theme_mode, state.theme_revision)
    yield
    state.theme_mode, state.theme_revision = before


def test_dark_mode_tracks_state_theme_not_page():
    # state.theme_mode is the single truth both theme paths write
    state.theme_mode = ft.ThemeMode.DARK
    assert is_dark_mode(_FakePage()) is True
    state.theme_mode = ft.ThemeMode.LIGHT
    assert is_dark_mode(_FakePage()) is False
    state.theme_mode = ft.ThemeMode.DARK
    assert is_dark_mode(_FakePage(ft.Brightness.LIGHT)) is True


def test_system_mode_follows_platform_brightness():
    state.theme_mode = ft.ThemeMode.SYSTEM
    assert is_dark_mode(_FakePage(ft.Brightness.DARK)) is True
    assert is_dark_mode(_FakePage(ft.Brightness.LIGHT)) is False


def test_is_dark_mode_reads_theme_revision():
    # The observable read inside is_dark_mode is what subscribes rendering
    # components to flips — guard against someone "simplifying" it away.
    src = (_ROOT / "src" / "core" / "theme.py").read_text(encoding="utf-8")
    assert "state.theme_revision" in src, "is_dark_mode must read the observable"


def test_settings_theme_path_publishes_observable():
    # The Settings picker must mirror main.toggle_theme (state.theme_mode +
    # revision bump) or switching theme there leaves the UI stale.
    src = (_ROOT / "src" / "screens" / "settings_screen.py").read_text(encoding="utf-8")
    update = src.split("def _update_theme", 1)[1].split("\n    def ", 1)[0]
    assert "state.theme_mode" in update
    assert "state.theme_revision" in update


def test_finish_onboarding_uses_context_subscription():
    # The Router is mounted once.  Route components subscribe to AppStateCtx,
    # so accepting terms must not rebuild page.views and discard route state.
    src = (_ROOT / "src" / "main.py").read_text(encoding="utf-8")
    handler = src.split("def finish_onboarding", 1)[1].split("\n    def ", 1)[0]
    assert "AppStateCtx" in src
    assert "_mount_ui()" not in handler
    assert "def _mount_ui" in src


def test_app_state_context_actually_subscribes_component():
    from flet.components.component import Renderer

    from core.state import AppStateCtx, use_app_state

    @ft.component
    def _probe():
        current = use_app_state().selected_tab
        return ft.Text(str(current))

    rendered = Renderer().render(lambda: AppStateCtx(state, _probe))
    rendered.before_update()
    assert len(rendered._state.observable_subscriptions) == 1
