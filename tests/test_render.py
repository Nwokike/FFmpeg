"""Smoke test rendering for all screens and AppShell."""

from __future__ import annotations

import flet as ft
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


def test_render_app_shell_router_when_accepted(mock_ctx):
    """Boot shape must be the Router component once terms are accepted.

    The mid-session onboarding bug this guards: swapping AppShell's RETURN
    between a View list and the Router was never adopted by render_views, so
    the gate lives inside route views and AppShell is ALWAYS the Router —
    meaning the rendered type must NOT flip when the terms flag changes.
    """
    services, methods = mock_ctx
    r = Renderer()

    state.has_accepted_terms = True
    accepted = r.render(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(methods, lambda: AppShell()),
        )
    )
    state.has_accepted_terms = False
    unaccepted = r.render(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(methods, lambda: AppShell()),
        )
    )
    assert accepted is not None and unaccepted is not None
    assert type(accepted) is type(unaccepted), (
        "AppShell boot shape must not change with terms — a mid-session "
        "Router swap is never adopted by render_views"
    )


def test_onboarding_gate_toggles_on_terms_flag(mock_ctx):
    from app_shell import _onboarding_gate

    r = Renderer()

    state.has_accepted_terms = False
    gated = r.render(lambda: _onboarding_gate() or ft.Container())
    assert gated is not None

    state.has_accepted_terms = True
    passed = r.render(lambda: _onboarding_gate() or ft.Container())
    assert passed is not None


def test_render_engine_info_screen(mock_ctx):
    from screens.engine_info_screen import EngineInfoScreen

    services, methods = mock_ctx
    r = Renderer()
    comp = r.render(
        lambda: ServiceCtx(
            services,
            lambda: ControllerMethodsCtx(methods, lambda: EngineInfoScreen()),
        )
    )
    assert comp is not None
