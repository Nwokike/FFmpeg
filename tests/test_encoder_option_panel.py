"""The generic option surface: schema → controls → wire strings → encoder.

Phase 4 renders av's own `CodecOption` schema in the app. These tests pin the
contract at each boundary, and prove the options actually reach the encoder
(an option that renders but never applies is the bug this phase exists to fix).
"""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest
from flet.components.component import Component, Renderer
from flet.controls.context import _context_page

from components.encoder_options import (
    ContainerOptionRows,
    EncoderOptionPanel,
    OptionValues,
    coerce_option,
    flag_names,
    format_number,
    option_controls,
    option_type,
)
from core.engine_probe import probe
from screens.extract_screen import extract_mode_availability
from services.engine_service import (
    EngineService,
    _supported_encoder_options,
    audio_codec_for_format,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_SRC = (ROOT / "src" / "components" / "encoder_options.py").read_text(encoding="utf-8")


def _collect(root, controls: list, components: list, depth: int = 0) -> None:
    """Mount components as they are met (Flet builds a body on mount) and gather
    every terminal control. Components are unmounted afterwards so later state
    writes cannot notify dead subscribers."""
    if root is None or depth > 80:
        return
    if isinstance(root, Component):
        with contextlib.suppress(Exception):
            root.did_mount()
            root.update()
        components.append(root)
        _collect(getattr(root, "_b", None), controls, components, depth + 1)
        return
    if isinstance(root, (list, tuple)):
        for item in root:
            _collect(item, controls, components, depth + 1)
        return
    if isinstance(root, ft.Control):
        controls.append(root)
    for name in ("controls", "content", "leading", "trailing", "title", "subtitle"):
        child = getattr(root, name, None)
        if child is not None and child is not root:
            _collect(child, controls, components, depth + 1)


def _controls(control) -> list:
    controls: list = []
    components: list = []
    with _page_context():
        _collect(control, controls, components)
    for component in reversed(components):
        with contextlib.suppress(Exception):
            component.will_unmount()
    return controls


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


def _render(fn):
    with _page_context():
        return Renderer().render(fn)


def _schema_for(codec: str) -> list[dict]:
    return probe().encoder_option_schema.get(codec) or []


# ── schema shape (the probe's half of the contract) ─────────────────────────


def test_flags_choices_are_plain_names():
    """Choices must be selectable: a repr like "CodecOptionChoice(name='cgop'…"
    cannot be written to the encoder, and no picker can show it."""
    p = probe()
    flags_entries = [
        spec
        for schema in p.encoder_option_schema.values()
        for spec in schema
        if option_type(spec) == 1 and spec.get("choices")
    ]
    assert flags_entries, "this wheel declares no flags option — schema changed?"
    for spec in flags_entries[:20]:
        for choice in spec["choices"]:
            assert "(" not in choice and "=" not in choice, f"non-name choice {choice!r}"
        for name, help_text in (spec.get("choice_help") or {}).items():
            assert name in spec["choices"]
            assert isinstance(help_text, str) and help_text


def test_common_encoder_options_are_shared_by_every_encoder():
    p = probe()
    common = set(p.common_encoder_options)
    assert common, "generic option set not measured"
    assert "b" in common and "flags" in common
    for codec, schema in p.encoder_option_schema.items():
        names = {str(spec["name"]) for spec in schema}
        assert common <= names, f"{codec} does not declare the generic set"
    # Encoder-specific keys are the short list the panel opens on.
    assert "crf" not in common
    assert any(
        "crf" in {str(s["name"]) for s in schema} for schema in p.encoder_option_schema.values()
    )


# ── values are wire strings ─────────────────────────────────────────────────


def test_option_values_only_send_touched_options():
    values = OptionValues("libx264")
    assert values.as_dict() == {}
    values.set_raw("crf", "23")
    values.set_raw("preset", "slow")
    assert values.as_dict() == {"crf": "23", "preset": "slow"}
    assert values.is_set("crf") and not values.is_set("tune")
    assert len(values) == 2
    values.unset("crf")
    values.reset()
    assert values.as_dict() == {}


@pytest.mark.parametrize(
    ("type_id", "raw", "expected"),
    [
        (2, "23.0", "23"),  # int options must not carry a decimal point
        (2, 23, "23"),
        (3, "64", "64"),
        (5, "0.5", "0.5"),
        (4, 1, "1"),
        (18, True, "1"),
        (18, False, "0"),
        (18, "true", "1"),
        (1, "cgop+psnr", "cgop+psnr"),
        (1, "cgop, psnr", "cgop+psnr"),
        (1, ["cgop", "psnr"], "cgop+psnr"),
        (6, "film", "film"),
    ],
)
def test_coerce_option_matches_av_wire_format(type_id, raw, expected):
    assert coerce_option({"type": str(type_id)}, raw) == expected


def test_flag_names_ignore_bitfield_defaults():
    assert flag_names("cgop+psnr") == ["cgop", "psnr"]
    assert flag_names("0x80000000") == []
    assert flag_names("") == []
    assert format_number(23.0) == "23"
    assert format_number(0.5) == "0.5"


def test_av_rejects_non_string_option_values(tmp_path):
    """The reason every value is coerced: av's option dict is str → str."""
    import av

    container = av.open(str(tmp_path / "unused.mp4"), "w")
    try:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 64, 64, "yuv420p"
        stream.options = {"crf": 23}
        with pytest.raises(TypeError):
            stream.encode(av.VideoFrame(64, 64, "yuv420p"))
    finally:
        container.close()


# ── controls are type-appropriate ───────────────────────────────────────────


def test_every_option_renders_one_row():
    schema = _schema_for("libx264")
    values = OptionValues("libx264")
    rows = option_controls(schema, values)
    assert len(rows) == len(schema)
    # Every row must build under Flet 1.1.2: TextField/Dropdown have no
    # `tooltip` kwarg there, so a stray one raises TypeError at construction.
    assert all(isinstance(row, ft.Control) for row in rows)


def test_option_row_dispatches_by_option_type():
    def _first(control, cls):
        return next((c for c in _controls(control) if isinstance(c, cls)), None)

    bool_row = option_controls([{"name": "aud", "type": "18", "help": ""}], OptionValues("x"))[0]
    assert _first(bool_row, ft.Switch) is not None

    enum_row = option_controls(
        [{"name": "tune", "type": "6", "choices": ["film", "grain"], "choice_help": {}}],
        OptionValues("x"),
    )[0]
    dropdown = _first(enum_row, ft.Dropdown)
    assert dropdown is not None
    assert {option.key for option in dropdown.options} == {"film", "grain"}

    bounded = option_controls(
        [{"name": "qmin", "type": "2", "min": 0, "max": 69, "default": "0", "help": ""}],
        OptionValues("x"),
    )[0]
    slider = _first(bounded, ft.Slider)
    assert slider is not None and slider.min == 0 and slider.max == 69

    unbounded = option_controls(
        [{"name": "b", "type": "3", "min": 0, "max": 9.2e18, "default": "0", "help": ""}],
        OptionValues("x"),
    )[0]
    assert _first(unbounded, ft.Slider) is None
    assert _first(unbounded, ft.TextField) is not None

    flags = option_controls(
        [
            {
                "name": "flags",
                "type": "1",
                "choices": ["cgop", "psnr"],
                "choice_help": {"cgop": "closed GOP"},
                "default": "0",
                "help": "",
            }
        ],
        OptionValues("x"),
    )[0]
    boxes = [c for c in _controls(flags) if isinstance(c, ft.Checkbox)]
    assert {box.label for box in boxes} == {"cgop", "psnr"}


def _panel(codec: str, schema, values: OptionValues, common: list[str] | None = None):
    return _render(
        lambda: EncoderOptionPanel(
            codec,
            schema,
            values,
            common_options=common if common is not None else probe().common_encoder_options,
            is_dark=True,
        )
    )


def test_panel_shows_encoder_specific_options_first():
    p = probe()
    schema = _schema_for("libx264")
    specific = [spec for spec in schema if str(spec["name"]) not in set(p.common_encoder_options)]
    panel = _panel("libx264", schema, OptionValues("libx264"), p.common_encoder_options)
    controls = _controls(panel)
    assert any(isinstance(c, ft.TextField) for c in controls), "search field missing"
    assert any(isinstance(c, ft.SegmentedButton) for c in controls), "scope switch missing"
    # Default scope is the encoder-specific short list, not the full 157 rows.
    rows = next(
        c.controls
        for c in controls
        if isinstance(c, ft.Column) and str(getattr(c, "key", "")).startswith("encoder-options-")
    )
    assert len(rows) == len(specific)
    assert 0 < len(specific) < len(schema)


def test_panel_without_schema_says_so():
    panel = _panel("definitely-not-a-codec", [], OptionValues("x"))
    texts = [c.value for c in _controls(panel) if isinstance(c, ft.Text)]
    assert any("no option schema" in str(t) for t in texts)


def test_container_rows_add_and_remove():
    seen: list[list[list[str]]] = []

    def _on_change(rows):
        seen.append(rows)

    rows = _render(
        lambda: ContainerOptionRows([["movflags", "+faststart"]], _on_change, is_dark=True)
    )
    controls = _controls(rows)
    fields = [c for c in controls if isinstance(c, ft.TextField)]
    assert len(fields) == 2
    assert fields[0].value == "movflags" and fields[1].value == "+faststart"
    assert any(isinstance(c, ft.IconButton) for c in controls), "remove button missing"
    assert any(isinstance(c, ft.OutlinedButton) for c in controls), "add button missing"
    assert seen == []


# ── options actually reach the encoder ──────────────────────────────────────


def _render_screen(factory):
    """Render a screen component with the services/controller contexts it reads."""
    from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
    from state.service_ctx import ServiceCtx, Services

    services, methods = Services(), ControllerMethods()
    with _page_context():
        return Renderer().render(
            lambda: ServiceCtx(services, lambda: ControllerMethodsCtx(methods, factory))
        )


def test_screens_render_their_panels_against_the_live_wheel():
    """The screen harnesses run with probe_info=None; this is the pass that
    exercises the real schema inside each screen (a bad prop or an empty codec
    key only shows up here)."""
    from core.state import state
    from screens.audio_screen import AudioScreen
    from screens.compress_screen import CompressScreen
    from screens.convert_screen import ConvertScreen
    from screens.cut_screen import CutScreen
    from screens.extract_screen import ExtractScreen

    previous = state.probe_info
    state.probe_info = probe()
    try:
        # Cut defaults to stream copy: no encoder is configured, so its panel is
        # correctly absent until the user picks re-encode.
        for factory, expect_codec_panel in (
            (ConvertScreen, True),
            (CompressScreen, True),
            (CutScreen, False),
            (AudioScreen, True),
            (ExtractScreen, True),
        ):
            controls = _controls(_render_screen(factory))
            assert any(isinstance(c, ft.ExpansionTile) for c in controls), (
                f"{factory.__name__} lost its option panel"
            )
            texts = [str(c.value) for c in controls if isinstance(c, ft.Text)]
            has_codec_panel = any("settings for" in t for t in texts)
            assert has_codec_panel is expect_codec_panel, (
                f"{factory.__name__} codec panel: expected {expect_codec_panel}, got {has_codec_panel}"
            )
    finally:
        state.probe_info = previous


def test_supported_options_keep_generic_and_private():
    options = _supported_encoder_options(
        "libx264",
        {"crf": "23", "b": "1M", "g": "12", "flags": "+cgop", "definitely_not_an_option": "x"},
    )
    assert options == {"crf": "23", "b": "1M", "g": "12", "flags": "+cgop"}


def test_supported_options_coerce_to_strings():
    options = _supported_encoder_options("libx264", {"crf": 23, "qmin": 1})
    assert options == {"crf": "23", "qmin": "1"}


def _keyframe_count(path: str) -> tuple[int, int]:
    """(key frames, frames) in the output — an option-observable property."""
    import av

    with av.open(path) as container:
        stream = container.streams.video[0]
        keys = frames = 0
        for packet in container.demux(stream):
            if packet.size == 0:
                continue
            frames += 1
            if packet.is_keyframe:
                keys += 1
    return keys, frames


def test_convert_applies_a_generic_encoder_option(synthetic_media):
    """`g` is a generic AVOption, not an x264 private one: it must survive the
    filter AND change the encode (the old private-only filter dropped it).
    g=1 makes every frame a keyframe — directly observable in the output."""
    baseline = str(synthetic_media.dir / "baseline_generic.mp4")
    keyframed = str(synthetic_media.dir / "keyframed_generic.mp4")

    EngineService.convert(
        synthetic_media.path,
        baseline,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    EngineService.convert(
        synthetic_media.path,
        keyframed,
        encoder_options={"g": "1"},
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )

    base_keys, frames = _keyframe_count(baseline)
    capped_keys, capped_frames = _keyframe_count(keyframed)
    assert capped_frames == frames > 0
    assert capped_keys == capped_frames, "g=1 must make every frame a keyframe"
    assert base_keys < frames, "the baseline must not already be all-keyframe"


def test_convert_container_option_reaches_the_muxer(synthetic_media):
    """movflags +faststart moves the moov atom in front of mdat — proof the
    container option dict reaches av.open, not just the panel."""
    out = str(synthetic_media.dir / "faststart.mp4")
    EngineService.convert(
        synthetic_media.path,
        out,
        container_options={"movflags": "+faststart"},
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    data = Path(out).read_bytes()
    moov = data.find(b"moov")
    mdat = data.find(b"mdat")
    assert moov != -1 and mdat != -1
    assert moov < mdat, "faststart must place moov before mdat"


def test_extract_audio_applies_an_encoder_option(synthetic_media):
    if not probe().encoders or "libmp3lame" not in probe().encoders:
        pytest.skip("this wheel has no mp3 encoder")
    baseline = str(synthetic_media.dir / "plain.mp3")
    capped = str(synthetic_media.dir / "capped.mp3")

    EngineService.extract_audio(
        synthetic_media.path,
        baseline,
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    EngineService.extract_audio(
        synthetic_media.path,
        capped,
        encoder_options={"b": "32000"},
        on_progress=lambda p, m: None,
        cancel_event=threading.Event(),
    )
    assert Path(capped).stat().st_size < Path(baseline).stat().st_size


def test_audio_codec_for_format_matches_the_engine():
    assert audio_codec_for_format("m4a") == "aac"
    assert audio_codec_for_format("definitely-not-a-format") is None


# ── screen-level gate ───────────────────────────────────────────────────────


def test_gif_mode_follows_the_wheel():
    info = SimpleNamespace(audio_stream=None, kind="video", streams=[])
    without_gif = SimpleNamespace(gif_ok=False)
    with_gif = SimpleNamespace(gif_ok=True)
    assert extract_mode_availability(info, without_gif)["gif"] is False
    assert extract_mode_availability(info, with_gif)["gif"] is True
    # One-argument calls keep working (the info-only gate).
    assert extract_mode_availability(info)["gif"] is True
    assert extract_mode_availability(None, without_gif)["gif"] is False
