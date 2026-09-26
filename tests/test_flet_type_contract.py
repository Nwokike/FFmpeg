"""Guard: no bool ever lands in a Flet Number/float-typed control property.

Python's ``bool`` subclasses ``int``, and Flet 1.0.1 only range-validates
numbers (``V.ge``/``V.le``/``V.between``) — no runtime type check — so
``True``/``False`` passes every Python-side guard, msgpack ships a real bool,
and the Dart client throws ``type 'bool' is not a subtype of type 'double?'``
against every ``double?`` field. The SafeArea(bottom=False) storm was exactly
this: kwargs that don't exist on the control silently bind to inherited
``LayoutControl`` offsets typed ``Optional[Number]``.

Three layers:

1. Runtime walk — execute real component bodies in-process (Flet 1.0.1
   renders lazily: ``Renderer().render`` only builds the wrapper, so bodies
   are driven via ``did_mount``/``update`` with a stub session) and fail on
   any bool found in a Number-typed field of any control in the tree.
2. Static AST scan of src/ — catches bool literals/expressions assigned to
   Number-typed kwargs anywhere, including files the runtime pass misses.
3. Explicit SafeArea field pin — the exact 2026-09-26 regression.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import importlib
import pathlib

import flet as ft
import pytest
from flet.components.component import Component, Renderer
from flet.controls.context import _context_page

from app_shell import ConvertScreen, _dashboard_view, _shell_body, _tool_view
from core.state import Job, state
from screens.audio_screen import AudioScreen
from screens.capture_screen import CaptureScreen
from screens.compress_screen import CompressScreen
from screens.convert_screen import ConvertScreen as _ConvertScreenCls
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

SCREENS = [
    HomeScreen,
    HistoryScreen,
    SettingsScreen,
    _ConvertScreenCls,
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
    state.has_accepted_terms = True
    state.jobs = [
        Job(op="convert", input_path="in.mp4", output_path="out.mkv", status="running"),
        Job(op="cut", input_path="a.mp4", output_path="b.mp4", status="failed"),
    ]
    state.history = [
        Job(op="convert", input_path="clip.mov", output_path="out.mp4", status="completed"),
        Job(op="record", input_path="", output_path="", status="cancelled"),
    ]
    yield
    state.jobs, state.history = snap[0], snap[1]
    state.has_accepted_terms, state.selected_tab = snap[2], snap[3]
    state.settings.clear()
    state.settings.update(snap[4])


# ── In-process body-execution harness (Flet 1.0.1 renders lazily) ────────


class _StubSession:
    def patch_control(self, *args, **kwargs):
        pass

    def schedule_effect(self, *args, **kwargs):
        pass

    def schedule_update(self, *args, **kwargs):
        pass


class _StubPage:
    route = "/"
    web = False
    width = 393
    height = 852
    platform = ft.PagePlatform.ANDROID
    platform_brightness = ft.Brightness.DARK
    session = _StubSession()

    def update(self, *args, **kwargs):
        pass

    def run_task(self, fn, *args, **kwargs):
        pass

    def show_dialog(self, *args, **kwargs):
        pass

    def pop_dialog(self, *args, **kwargs):
        pass


@contextlib.contextmanager
def _page_context():
    token = _context_page.set(_StubPage())
    try:
        yield
    finally:
        _context_page.reset(token)


def _collect_controls(root, out: list, seen: set, components: list, depth: int = 0) -> None:
    """Execute lazy component bodies and gather every terminal control."""
    if root is None or id(root) in seen or depth > 80:
        return
    seen.add(id(root))
    if isinstance(root, Component):
        root.did_mount()
        root.update()
        components.append(root)
        _collect_controls(root._b, out, seen, components, depth + 1)
        return
    if isinstance(root, ft.Control):
        out.append(root)
    if isinstance(root, (list, tuple)):
        for item in root:
            _collect_controls(item, out, seen, components, depth + 1)
        return
    if dataclasses.is_dataclass(root) and not isinstance(root, type):
        for field in dataclasses.fields(root):
            try:
                value = getattr(root, field.name)
            except Exception:
                continue
            if isinstance(value, (ft.Control, Component, list, tuple)) or (
                dataclasses.is_dataclass(value) and not isinstance(value, type)
            ):
                _collect_controls(value, out, seen, components, depth + 1)


def _render(fn):
    r = Renderer()
    services, methods = Services(), ControllerMethods()
    return r.render(lambda: ServiceCtx(services, lambda: ControllerMethodsCtx(methods, fn)))


def _bool_number_offenders(controls) -> list[str]:
    offenders = []
    for ctrl in controls:
        for field in dataclasses.fields(ctrl):
            annotation = str(field.type)
            if "Number" not in annotation and "float" not in annotation:
                continue
            value = getattr(ctrl, field.name, None)
            if isinstance(value, bool):
                offenders.append(f"{type(ctrl).__name__}.{field.name}={value!r}")
    return offenders


def _unmount_all(components) -> None:
    """Detach observable subscriptions from executed components (best-effort)."""
    for comp in reversed(components):
        with contextlib.suppress(Exception):
            comp.will_unmount()


def _execute_tree(fn) -> list:
    """Execute a tree in a stub page context and return its controls.

    Components read observable AppState fields during their bodies, which
    subscribes them to the singleton — every executed component is unmounted
    (will_unmount detaches those subscriptions) before the context is reset,
    or later fixture writes to state would notify dead components and raise
    "context is not associated with any page" from unrelated tests.
    """
    with _page_context():
        controls: list = []
        components: list = []
        _collect_controls(_render(fn), controls, set(), components)
        _unmount_all(components)
    return controls


def _execute_and_check(fn) -> None:
    controls = _execute_tree(fn)
    assert controls, "component body produced no controls — executor regression"
    assert _bool_number_offenders(controls) == []


# ── Runtime: executed trees ──────────────────────────────────────────────


def test_dashboard_tree_has_no_bool_in_number_fields():
    """Covers the header SafeArea branch, banners, job cards, nav bar."""
    _execute_and_check(_dashboard_view)


def test_tool_route_tree_has_no_bool_in_number_fields():
    """Covers the zero-height spacer SafeArea branch on every tool route."""
    _execute_and_check(_tool_view(ConvertScreen, "convert"))


def test_shell_body_both_branches_directly():
    with _page_context():
        # Renderer frame required: _shell_body constructs @ft.component
        # children (banners) which must build inside a render context.
        r = Renderer()
        trees = [
            r.render(
                lambda: _shell_body(ft.Container(content=ft.Text("x")), state, header=ft.Text("H"))
            ),
            r.render(lambda: _shell_body(ft.Container(content=ft.Text("x")), state)),
        ]
        controls: list = []
        components: list = []
        for tree in trees:
            _collect_controls(tree, controls, set(), components)
        _unmount_all(components)
    assert _bool_number_offenders(controls) == []


@pytest.mark.parametrize("factory", SCREENS, ids=lambda f: f.__name__)
def test_screen_tree_has_no_bool_in_number_fields(factory):
    _execute_and_check(factory)


# ── Static: AST scan of src/ ─────────────────────────────────────────────

# Import aliases used across src/ for Flet-family modules.
_FLET_ALIASES = {
    "ft": "flet",
    "flet": "flet",
    "ftc": "flet_camera",
    "fta": "flet_ads",
    "ftv": "flet_video",
}

_NUMBER_FIELDS_CACHE: dict[type, frozenset[str]] = {}


def _class_number_fields(cls) -> frozenset[str]:
    """Number/float-typed field names of a control class, MRO-inclusive.

    ``dataclasses.fields`` walks base classes, so SafeArea inherits
    LayoutControl's ``bottom``/``left``/``right`` — exactly the silent-bind
    surface that produced the SafeArea storm.
    """
    cached = _NUMBER_FIELDS_CACHE.get(cls)
    if cached is None:
        cached = frozenset(
            field.name
            for field in dataclasses.fields(cls)
            if "Number" in str(field.type) or "float" in str(field.type)
        )
        _NUMBER_FIELDS_CACHE[cls] = cached
    return cached


def _is_bool_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, bool)
    if isinstance(node, ast.Compare | ast.BoolOp):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return True
    if isinstance(node, ast.Name):
        return node.id in ("True", "False")
    return False


def test_src_never_assigns_bool_to_number_kwarg():
    """Per-class check: Switch.value is bool-typed, ProgressBar.value is
    Number-typed — a flat kwarg-name set would false-positive on the former,
    so resolve the called class and inspect ITS (MRO-inclusive) fields."""
    offenders = []
    for py in SRC.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as exc:
            offenders.append(f"{py}: SyntaxError {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
                continue
            pkg = _FLET_ALIASES.get(func.value.id)
            if pkg is None:
                continue
            cls = getattr(importlib.import_module(pkg), func.attr, None)
            if cls is None or not dataclasses.is_dataclass(cls):
                continue
            number_fields = _class_number_fields(cls)
            for kw in node.keywords:
                if kw.arg in number_fields and _is_bool_expr(kw.value):
                    rel = py.relative_to(ROOT)
                    offenders.append(f"{rel}:{node.lineno} {func.attr}({kw.arg}=bool)")
    assert offenders == [], "bool assigned to a Number-typed Flet property:\n" + "\n".join(
        offenders
    )


# ── Explicit pin: the 2026-09-26 SafeArea storm ─────────────────────────


def test_shell_body_safearea_uses_real_avoid_intrusions_fields():
    """SafeArea has no bottom/left/right of its own — those names silently
    bind to LayoutControl absolute offsets (double?). The header branch must
    express the top-only intent through avoid_intrusions_* and leave the
    offsets untouched (None, never a bool)."""
    with _page_context():
        controls: list = []
        components: list = []
        tree = Renderer().render(lambda: _shell_body(ft.Text("x"), state, header=ft.Text("H")))
        _collect_controls(tree, controls, set(), components)
        _unmount_all(components)
    safes = [c for c in controls if isinstance(c, ft.SafeArea)]
    assert safes, "header branch must contain a SafeArea"
    for sa in safes:
        assert sa.avoid_intrusions_top is True
        assert sa.avoid_intrusions_bottom is False
        assert sa.avoid_intrusions_left is False
        assert sa.avoid_intrusions_right is False
        assert sa.bottom is None
        assert sa.left is None
        assert sa.right is None
