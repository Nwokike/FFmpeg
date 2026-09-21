"""Smoke test rendering for all screens and AppShell."""

from __future__ import annotations

import pytest
from flet.components.component import Renderer

from app_shell import AppShell
from core.state import state
from screens.audio_screen import AudioScreen
from screens.compress_screen import CompressScreen
from screens.convert_screen import ConvertScreen
from screens.cut_screen import CutScreen
from screens.extract_screen import ExtractScreen
from screens.filters_screen import FiltersScreen
from screens.history_screen import HistoryScreen
from screens.home_screen import HomeScreen
from screens.onboarding_screen import OnboardingScreen
from screens.probe_screen import ProbeScreen
from screens.result_screen import ResultScreen
from screens.settings_screen import SettingsScreen
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from state.service_ctx import ServiceCtx, Services


@pytest.fixture
def mock_ctx():
    services = Services()
    methods = ControllerMethods()
    return services, methods


def test_render_onboarding(mock_ctx):
    services, methods = mock_ctx
    r = Renderer()
    comp = r.render(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(methods, lambda: OnboardingScreen()),
        )
    )
    assert comp is not None


def test_render_all_screens(mock_ctx):
    services, methods = mock_ctx
    r = Renderer()

    screens = [
        HomeScreen,
        ConvertScreen,
        CompressScreen,
        CutScreen,
        ExtractScreen,
        FiltersScreen,
        AudioScreen,
        ProbeScreen,
        ResultScreen,
        HistoryScreen,
        SettingsScreen,
    ]

    for screen_cls in screens:
        comp = r.render(
            lambda s=screen_cls: ServiceCtx(
                services,
                lambda: ControllerMethodsCtx(methods, lambda: s()),
            )
        )
        assert comp is not None


def test_render_app_shell_onboarding(mock_ctx):
    services, methods = mock_ctx
    state.has_accepted_terms = False
    r = Renderer()
    comp = r.render(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(methods, lambda: AppShell()),
        )
    )
    assert comp is not None
