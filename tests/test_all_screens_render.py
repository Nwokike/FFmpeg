"""Step-0 body-executing render pass: every screen, one by one.

The owner hit crashes that never reached the terminal (Flet's update scheduler
is unguarded and page.on_error has zero dispatch sites in this build). These
tests run each of the 16 screen bodies in-process — Renderer().render executes
the component body — so any Python-side API error fails a test instead of
freezing a tab silently. State is populated so real code paths run, not the
empty-state happy path that hid the M2 badge/Row crashes.
"""

from __future__ import annotations

import pytest
from flet.components.component import Renderer

from core.state import Job, state
from screens.audio_screen import AudioScreen
from screens.capture_screen import CaptureScreen
from screens.compress_screen import CompressScreen
from screens.convert_screen import ConvertScreen
from screens.cut_screen import CutScreen
from screens.engine_info_screen import EngineInfoScreen
from screens.extract_screen import ExtractScreen
from screens.filters_screen import FiltersScreen
from screens.history_screen import HistoryScreen
from screens.home_screen import HomeScreen
from screens.join_screen import JoinScreen
from screens.onboarding_screen import OnboardingScreen
from screens.probe_screen import ProbeScreen
from screens.result_screen import ResultScreen
from screens.settings_screen import SettingsScreen
from screens.streams_screen import StreamsScreen
from screens.terminal_screen import TerminalScreen
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
from state.service_ctx import ServiceCtx, Services

pytestmark = pytest.mark.usefixtures("_isolated_state")

SCREENS = [
    HomeScreen,
    HistoryScreen,
    SettingsScreen,
    ConvertScreen,
    CompressScreen,
    CutScreen,
    ExtractScreen,
    FiltersScreen,
    AudioScreen,
    ProbeScreen,
    EngineInfoScreen,
    CaptureScreen,
    StreamsScreen,
    JoinScreen,
    ResultScreen,
    TerminalScreen,
    OnboardingScreen,
]


@pytest.fixture
def _isolated_state():
    """Snapshot/restore the state singleton so tests never bleed into each other."""
    snap = (
        list(state.jobs),
        list(state.history),
        state.has_accepted_terms,
        state.selected_tab,
        dict(state.settings),
    )
    # Populate the paths the M2 crashes hid behind: non-empty queue + history.
    state.jobs = [
        Job(op="convert", input_path="in.mp4", output_path="out.mkv", status="running"),
        Job(op="cut", input_path="a.mp4", output_path="b.mp4", status="failed"),
    ]
    state.history = [
        Job(op="convert", input_path="видео.mov", output_path="out.mp4", status="completed"),
        Job(op="record", input_path="", output_path="", status="cancelled"),
    ]
    yield
    state.jobs, state.history = snap[0], snap[1]
    state.has_accepted_terms, state.selected_tab = snap[2], snap[3]
    state.settings.clear()
    state.settings.update(snap[4])


def _render(fn):
    r = Renderer()
    services, methods = Services(), ControllerMethods()
    return r.render(lambda: ServiceCtx(services, lambda: ControllerMethodsCtx(methods, fn)))


@pytest.mark.parametrize("factory", SCREENS, ids=lambda f: f.__name__)
def test_screen_body_renders(factory):
    assert _render(factory) is not None
