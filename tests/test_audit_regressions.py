"""Regression pins for the screen-audit crash findings (2026-09-23).

Each test reproduces the exact expression that crashed on-device.
"""

from __future__ import annotations

import json
from pathlib import Path

import flet as ft
import pytest

from core.state import Job, state


def test_chip_leading_not_avatar():
    # Chip has no `avatar` prop in Flet 1.0 — constructor TypeError (this
    # fired on every visit to the Streams tab).
    with pytest.raises(TypeError):
        ft.Chip(label="x", avatar=ft.Icon(ft.Icons.ADD))
    chip = ft.Chip(label="x", leading=ft.Icon(ft.Icons.ADD))
    assert chip.leading is not None


def test_history_filter_survives_none_paths():
    # Typed into the search box with a JSON-null job in history:
    # Path(None) raised TypeError, None.lower() raised AttributeError.
    q = "x".lower()
    jobs = [
        Job(op=None, input_path=None, output_path=None),
        Job(op="cut", input_path="", output_path=""),
    ]
    out = [
        j
        for j in jobs
        if q in Path(j.input_path or "").name.lower()
        or q in (j.op or "").lower()
        or q in Path(j.output_path or "").name.lower()
    ]
    assert out == []  # no crash, nothing matches


def test_delete_snack_label_survives_none_output():
    job = Job(op=None, input_path="", output_path=None)
    label = f"Deleted {Path(job.output_path or '').name or (job.op or 'job')}"
    assert label == "Deleted job"


def test_progress_and_size_guards_survive_none():
    running = Job(op="cut", input_path="", output_path="", status="running", progress=None)
    assert max(0.0, min(running.progress or 0.0, 1.0)) == 0.0
    done = Job(
        op="cut",
        input_path="",
        output_path="",
        status="completed",
        original_size_bytes=None,
        output_size_bytes=None,
    )
    assert not ((done.original_size_bytes or 0) > 0 and (done.output_size_bytes or 0) > 0)


def test_rounded_rectangle_border_keyword():
    # Positional 12 bound to `side`, not `radius` (terminal screen button).
    bad = ft.RoundedRectangleBorder(12)
    assert bad.side == 12 and bad.radius == 0
    good = ft.RoundedRectangleBorder(radius=12)
    assert good.radius == 12 and not good.side


def test_restore_defaults_use_or_not_get(monkeypatch):
    # `d.get("input_path", "")` returns None for an explicit JSON null;
    # `or ""` is the guard the restore path needs.
    d = {"id": None, "op": None, "input_path": None, "output_path": None, "params": None}
    job = Job(
        id=d.get("id") or "fallback123",
        op=d.get("op") or "convert",
        input_path=d.get("input_path") or "",
        output_path=d.get("output_path") or "",
        params=d.get("params") or {},
    )
    assert job.input_path == "" and job.op == "convert" and job.id


def test_segmented_button_selected_is_list_not_set():
    # `selected={compare}` survived construction but crashed Flet's render
    # serializer (set has no __dict__) on every video result with an original.
    sb = ft.SegmentedButton(
        segments=[ft.Segment(value="output", label="Output")],
        selected=["output"],
    )
    assert isinstance(sb.selected, list)
    with pytest.raises(TypeError):
        json.dumps({"selected": {"output"}})  # what the old value did at render


def test_result_guard_rejects_empty_and_none_output():
    # Path("") is Path(".") and EXISTS — the old guard let an empty output
    # path render garbage stats; Path(None) raised outright.
    assert Path().exists() is True  # the trap: "" resolves to the CWD
    assert (not "x") or (not Path("x").exists())  # the correct first check wins
    for candidate in ("", None):
        guarded = not candidate or not Path(candidate).exists()
        assert guarded is True


def test_subtitle_stream_index_is_sublist_position():
    # extract_screen must pass the clamped sublist position (engine indexes
    # inp.streams.subtitles), not the container-wide stream index.
    sub_streams = [0, 1]  # positions within the subtitle sublist
    sub_sel = 1
    stream_pos = sub_sel if sub_sel < len(sub_streams) else 0
    assert stream_pos == 1
    assert stream_pos == sub_streams[sub_sel]


@pytest.fixture(autouse=True)
def _clean_state():
    before = state.history
    state.history = []
    yield
    state.history = before


def test_disconnect_lifecycle_accepts_event_and_awaits_cleanup():
    source = (Path(__file__).resolve().parents[1] / "src" / "main.py").read_text(encoding="utf-8")
    lifecycle = source.split("# Wire lifecycle", 1)[1].split("# Background tasks", 1)[0]
    assert "async def _on_disconnect(_e)" in lifecycle
    assert "await close_client()" in lifecycle
    assert "page.run_task(close_client)" not in lifecycle


def test_restore_inserts_at_captured_index_whole_value():
    from core.state import state as _state

    before = list(_state.history)
    try:
        jobs = [
            Job(op="convert", input_path="a.mp4", output_path="a.mp4"),
            Job(op="convert", input_path="b.mp4", output_path="b.mp4"),
            Job(op="convert", input_path="c.mp4", output_path="c.mp4"),
        ]
        _state.history = list(jobs)
        removed = _state.history[1]
        items = [j for j in _state.history if j.id != removed.id]
        _state.history = items
        after_delete = list(_state.history)
        # Whole-value restore at index 1 (main.restore_job contract).
        restored = list(_state.history)
        restored.insert(1, removed)
        _state.history = restored
        assert [j.id for j in _state.history] == [jobs[0].id, removed.id, jobs[2].id]
        assert _state.history is not after_delete
    finally:
        _state.history = before


def test_job_card_none_status_renders():
    from flet.components.component import Renderer

    from components.job_card import clamped_progress, job_card_view
    from core.constants import op_title
    from state.controller_ctx import ControllerMethods, ControllerMethodsCtx
    from state.service_ctx import ServiceCtx, Services

    job = Job(op=None, input_path=None, output_path=None)
    job.status = None
    assert op_title(None) == "Convert"
    assert clamped_progress(None) == 0.0
    assert clamped_progress(float("nan")) == 0.0
    assert clamped_progress(1.5) == 1.0
    r = Renderer()
    comp = r.render(
        lambda: ServiceCtx(
            Services(),
            lambda: ControllerMethodsCtx(ControllerMethods(), lambda: job_card_view(job)),
        )
    )
    assert comp is not None


def test_op_titles_single_source():
    from core.constants import OP_LABELS, op_title

    assert op_title("concat") == "Join"
    assert op_title("join") == "Join"
    assert op_title("record") == "Recording"
    assert op_title("extract_audio") == "Extract Audio"
    assert op_title(None) == "Convert"
    assert op_title("") == "Convert"
    assert "concat" in OP_LABELS and "record" in OP_LABELS


def test_unique_temp_names_never_collide():
    from core.storage_paths import unique_temp_name

    names = {unique_temp_name("clip_converted", ".mp4") for _ in range(50)}
    assert len(names) == 50
    assert all(n.startswith("clip_converted_") and n.endswith(".mp4") for n in names)


def test_check_pair_matrix():
    from services.engine_service import check_pair

    assert check_pair("mp4", "mpeg4", "aac") is None
    assert check_pair("mp4", "vp9", "aac") is not None
    assert "muxable" in (check_pair("mp4", "vp9", "aac") or "")
    assert check_pair("webm", "libvpx-vp9", "opus") is None
    assert check_pair("unknowncontainer", "anything", "anything") is None


def test_controller_has_nav_and_indexed_restore():
    from state.controller_ctx import ControllerMethods

    methods = ControllerMethods()
    methods.go_home()
    methods.back()
    methods.show_view("dashboard")
    methods.restore_job(Job(op="convert", input_path="a", output_path="b"), 0)
    methods.restore_all([])
    methods.toggle_pause_job("some-id")


def test_service_ctx_missing_provider_raises():
    from flet.components.component import Renderer

    from state.service_ctx import use_services

    @ft.component
    def _probe():
        use_services()
        return ft.Text("never")

    with pytest.raises(RuntimeError, match="ServiceCtx provider missing"):
        Renderer().render(_probe).before_update()
