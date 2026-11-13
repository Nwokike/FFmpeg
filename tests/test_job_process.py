"""Worker-process containment: identical output, crash containment, cancel.

Isolation is POSIX-fork-only and default-off. These tests drive
`_execute_isolated` directly with the real engine. To crash/raise *inside the
child*, the dispatch builder is monkeypatched before the fork — fork inherits
the patch.
"""

from __future__ import annotations

import multiprocessing
import os
import threading
from fractions import Fraction
from pathlib import Path

import av
import pytest

import main as main_mod
from core.state import Job
from core.state import state as app_state
from services.engine_service import EngineService

FORK = multiprocessing.get_context("fork") if hasattr(os, "fork") else None
requires_fork = pytest.mark.skipif(FORK is None, reason="isolation requires POSIX fork")


def _clip(path: str, seconds: int = 2, fps: int = 30) -> None:
    with av.open(path, "w") as c:
        s = c.add_stream("mpeg4", rate=fps)
        s.width, s.height = 96, 64
        for i in range(seconds * fps):
            f = av.VideoFrame(96, 64, "yuv420p")
            f.pts = i
            f.time_base = Fraction(1, fps)
            for pk in s.encode(f):
                c.mux(pk)
        for pk in s.encode(None):
            c.mux(pk)


def _duration(path: str) -> float:
    with av.open(path) as r:
        return float(r.duration / av.time_base)


def _run_dispatch_in_thread(job: Job, evt: threading.Event) -> None:
    """Thread-mode reference: build and run the dispatch, apply fields."""
    dispatch = main_mod._build_job_dispatch(EngineService(), app_state, job, None, evt)
    main_mod._dispatch_job_op(dispatch, job)
    main_mod._apply_run_fields(job, evt)


@requires_fork
def test_process_mode_output_matches_thread_mode(tmp_path):
    src = str(tmp_path / "in.mp4")
    _clip(src)
    thread_out = str(tmp_path / "thread.mp4")
    proc_out = str(tmp_path / "process.mp4")

    job = Job(
        op="convert",
        input_path=src,
        output_path=thread_out,
        params={
            "video_codec": "mpeg4",
            "crf": 23,
            # Generic option panel values must survive both runners verbatim.
            "encoder_options": {"b": "400000"},
            "container_options": {"movflags": "+faststart"},
        },
    )
    _run_dispatch_in_thread(job, threading.Event())
    assert job.status == "completed", job.error_message

    job2 = Job(
        op="convert",
        input_path=src,
        output_path=proc_out,
        params={
            "video_codec": "mpeg4",
            "crf": 23,
            "encoder_options": {"b": "400000"},
            "container_options": {"movflags": "+faststart"},
        },
    )
    main_mod._execute_isolated(lambda j, e: None, job2, threading.Event())
    assert job2.status == "completed", job2.error_message
    assert abs(_duration(thread_out) - _duration(proc_out)) < 0.15


@requires_fork
def test_child_crash_reconciles_as_failed(tmp_path, monkeypatch):
    """A child that dies without a message reconciles as failed — never
    fake-complete."""

    def _crash_dispatch(engine, state, job, on_progress, cancel_evt):
        def _boom():
            import os as _os

            _os._exit(7)

        return {"convert": _boom}

    monkeypatch.setattr(main_mod, "_build_job_dispatch", _crash_dispatch)
    job = Job(
        op="convert", input_path=str(tmp_path / "in.mp4"), output_path=str(tmp_path / "o.mp4")
    )
    main_mod._execute_isolated(lambda j, e: None, job, threading.Event())
    assert job.status == "failed"
    assert "7" in (job.error_message or "")


@requires_fork
def test_child_exception_message_reaches_the_job(tmp_path, monkeypatch):
    def _raise_dispatch(engine, state, job, on_progress, cancel_evt):
        def _raise():
            raise ValueError("derived audio codec boom")

        return {"convert": _raise}

    monkeypatch.setattr(main_mod, "_build_job_dispatch", _raise_dispatch)
    job = Job(
        op="convert", input_path=str(tmp_path / "in.mp4"), output_path=str(tmp_path / "o.mp4")
    )
    main_mod._execute_isolated(lambda j, e: None, job, threading.Event())
    assert job.status == "failed"
    assert "boom" in (job.error_message or "")


@requires_fork
def test_cancel_mid_run_marks_cancelled_and_removes_output(tmp_path):
    src = str(tmp_path / "in.mp4")
    _clip(src, seconds=4)
    out = str(tmp_path / "out.mp4")

    job = Job(
        op="convert", input_path=src, output_path=out, params={"video_codec": "mpeg4", "crf": 23}
    )
    evt = threading.Event()

    # Deterministic mid-run cancel: fire on the first progress tick.
    def _cancel_on_first_progress() -> None:
        while not evt.is_set():
            try:
                item = main_mod._PROGRESS_QUEUE.get(timeout=0.05)
            except Exception:
                continue
            if item[0] is not None and item[0].id == job.id and item[1] > 0.02:
                evt.set()

    threading.Thread(target=_cancel_on_first_progress, daemon=True).start()
    main_mod._execute_isolated(lambda j, e: None, job, evt)
    assert job.status == "cancelled"
    assert not Path(out).exists()


@requires_fork
def test_progress_messages_reach_the_shared_queue(tmp_path):
    src = str(tmp_path / "in.mp4")
    _clip(src, seconds=2)
    out = str(tmp_path / "out.mp4")
    job = Job(
        op="convert", input_path=src, output_path=out, params={"video_codec": "mpeg4", "crf": 23}
    )

    seen: list[tuple[float, str]] = []
    stop = threading.Event()

    def _drain() -> None:
        while not stop.is_set() or not main_mod._PROGRESS_QUEUE.empty():
            try:
                item = main_mod._PROGRESS_QUEUE.get(timeout=0.05)
            except Exception:
                continue
            if item[0] is not None and item[0].id == job.id:
                seen.append((item[1], item[2]))

    t = threading.Thread(target=_drain)
    t.start()
    main_mod._execute_isolated(lambda j, e: None, job, threading.Event())
    stop.set()
    t.join(timeout=2)
    assert any(0 < p <= 1.0 for p, _m in seen), seen
