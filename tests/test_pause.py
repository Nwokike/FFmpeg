"""Pause semantics: queue gate, engine hook, and cancel precedence."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from core.state import Job
from services.engine_service import _pause_hook, set_pause_event
from services.job_queue import JobQueue


def _job() -> Job:
    return Job(op="convert", input_path="in.mp4", output_path="out.mp4")


# ── Queue-level gate ─────────────────────────────────────────────────────


def test_paused_queue_holds_pending_jobs():
    ran: list[str] = []

    def runner(job: Job, evt) -> None:
        ran.append(job.id)
        job.status = "completed"

    q = JobQueue(runner=runner)
    try:
        q.set_paused(True)
        assert q.paused is True
        q.enqueue(_job())
        time.sleep(0.3)
        assert ran == [], "paused queue must not pull jobs"

        q.set_paused(False)
        deadline = time.time() + 3
        while not ran and time.time() < deadline:
            time.sleep(0.02)
        assert len(ran) == 1, "resume must release the held job"
    finally:
        q.shutdown()


def test_toggle_pause_flips_state():
    q = JobQueue(runner=lambda job, evt: None)
    try:
        assert q.paused is False
        assert q.toggle_pause() is True
        assert q.paused is True
        assert q.toggle_pause() is False
        assert q.paused is False
    finally:
        q.shutdown()


# ── Engine hook ──────────────────────────────────────────────────────────


def test_engine_pause_hook_blocks_until_cleared():
    evt = threading.Event()
    set_pause_event(evt)
    try:
        evt.set()
        done = threading.Event()

        def work():
            _pause_hook(None)
            done.set()

        t = threading.Thread(target=work, daemon=True)
        t.start()
        time.sleep(0.25)
        assert not done.is_set(), "hook must block while paused"

        evt.clear()
        t.join(2.0)
        assert done.is_set(), "hook must release on resume"
    finally:
        set_pause_event(None)


def test_cancel_wins_over_pause():
    evt = threading.Event()
    set_pause_event(evt)
    try:
        evt.set()
        cancel = threading.Event()
        cancel.set()
        t = threading.Thread(target=_pause_hook, args=(cancel,), daemon=True)
        t.start()
        t.join(1.0)
        assert not t.is_alive(), "cancel must break the pause wait"
    finally:
        set_pause_event(None)


def test_engine_op_respects_pause_e2e(synthetic_media):
    """A paused engine holds mid-operation and completes after resume."""
    evt = threading.Event()
    set_pause_event(evt)
    out = str(synthetic_media.dir / "paused.wav")
    errors: list[BaseException] = []

    def work():
        try:
            from services.engine_service import EngineService

            EngineService.extract_audio(
                synthetic_media.path, out, format_name="wav", on_progress=lambda p, m: None
            )
        except BaseException as exc:
            errors.append(exc)

    try:
        evt.set()  # paused BEFORE the op starts
        t = threading.Thread(target=work, daemon=True)
        t.start()
        time.sleep(0.4)
        assert t.is_alive(), "paused engine must not finish"
        assert not Path(out).exists(), "no output while still paused"

        evt.clear()
        t.join(15.0)
        assert not t.is_alive(), "op must complete after resume"
        assert not errors, f"op raised: {errors[0]!r}"
        assert Path(out).exists() and Path(out).stat().st_size > 0
    finally:
        set_pause_event(None)
