"""Serial job queue — one media job at a time with cooperative cancellation.

Owns ordering and lifetime only: the app controller provides the engine `runner`
and the `on_started`/`on_finished` hooks that touch UI state. A single worker
thread drains the FIFO so two encodes never fight for CPU/RAM on a phone, and
cancelling a still-pending job removes it before it ever starts.
"""

from __future__ import annotations

import logging
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

from core.state import Job

logger = logging.getLogger("JobQueue")


def _set_worker_field(job: Job, name: str, value) -> None:
    """Update an observable Job from the worker without notifying Flet."""
    object.__setattr__(job, name, value)


# Pre-flight floor: muxer scratch, thumbnails and frame exports all land
# beside the output, and a disk that fills mid-encode loses the whole take.
_MIN_FREE_BYTES = 100 * 1024 * 1024


def free_space_error(job: Job) -> str | None:
    """None when the output's filesystem plausibly has room; else why not.

    Estimate = source size (outputs are usually smaller) with the floor for
    scratch. A failed probe returns None — the engine is the final authority.
    """
    try:
        target = Path(job.output_path)
        probe_dir = target.parent if str(target.parent) else Path.cwd()
        free = shutil.disk_usage(probe_dir).free
    except OSError as exc:
        logger.debug("Disk-space probe failed for %s: %s", job.output_path, exc)
        return None
    needed = max(job.original_size_bytes, _MIN_FREE_BYTES)
    if free < needed:
        return (
            f"Not enough free space ({free // (1024 * 1024)} MB free, "
            f"needs about {needed // (1024 * 1024)} MB)"
        )
    return None


class JobQueue:
    """FIFO queue executing at most one job at a time on a dedicated thread."""

    def __init__(
        self,
        runner: Callable[[Job, threading.Event], None],
        on_started: Callable[[Job], None] | None = None,
        on_finished: Callable[[Job], None] | None = None,
    ) -> None:
        self._runner = runner
        self._on_started = on_started
        self._on_finished = on_finished
        self._pending: list[Job] = []
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._shutdown = False
        self._current: Job | None = None
        self._thread: threading.Thread | None = None
        # Shared pause switch: the worker holds BEFORE pulling the next job and
        # the engine's pause hook (same Event) holds INSIDE the running one.
        self.pause_event = threading.Event()

    # ── Pause ──────────────────────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        return self.pause_event.is_set()

    def set_paused(self, value: bool) -> bool:
        """Pause (True) or resume (False) the queue; returns the new state."""
        if value:
            self.pause_event.set()
        else:
            self.pause_event.clear()
            self._wake.set()
        return value

    def toggle_pause(self) -> bool:
        return self.set_paused(not self.paused)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the worker thread (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._shutdown = False
        self._thread = threading.Thread(target=self._loop, name="job-queue", daemon=True)
        self._thread.start()

    def enqueue(self, job: Job) -> None:
        """Queue a job; the worker picks it up when the current job finishes."""
        with self._lock:
            if self._shutdown:
                logger.warning("Queue shut down; dropping job %s", job.id)
                job.status = "cancelled"
                job.status_message = "App is closing"
                self._notify_finished(job)
                return
            job.status = "pending"
            job.status_message = "Queued"
            self._pending.append(job)
        self._wake.set()
        self.start()

    def shutdown(self) -> None:
        """Stop accepting work, cancel whatever is running, drop pending jobs.

        Safe to call from disconnect/close handlers: finished callbacks are
        expected to be defensive (the page may already be gone).
        """
        with self._lock:
            self._shutdown = True
            pending = list(self._pending)
            self._pending.clear()
            running_evt = self._cancel_events.get(self._current.id) if self._current else None
            running = self._current
        for job in pending:
            job.status = "cancelled"
            job.status_message = "App is closing"
            self._notify_finished(job)
        if running_evt is not None:
            running_evt.set()
        if running is not None:
            running.status_message = "Cancelling..."
        self._wake.set()

    # ── Inspection ───────────────────────────────────────────────────────

    @property
    def current(self) -> Job | None:
        """The job currently executing, if any."""
        return self._current

    @property
    def queued_jobs(self) -> list[Job]:
        """Pending jobs in FIFO order (snapshot)."""
        with self._lock:
            return list(self._pending)

    def active_jobs(self) -> list[Job]:
        """Running job first, then pending — what the Jobs UI should render."""
        with self._lock:
            return ([self._current] if self._current else []) + list(self._pending)

    # ── Cancellation ─────────────────────────────────────────────────────

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job (removed immediately) or signal the running one.

        Returns True if the job was found and cancellation was initiated.
        """
        with self._lock:
            for job in self._pending:
                if job.id == job_id:
                    self._pending.remove(job)
                    job.status = "cancelled"
                    job.status_message = "Cancelled"
                    self._notify_finished(job)
                    return True
            evt = self._cancel_events.get(job_id)
        if evt is not None:
            evt.set()
            return True
        return False

    # ── Worker ───────────────────────────────────────────────────────────

    def _notify_finished(self, job: Job) -> None:
        if self._on_finished is None:
            return
        try:
            self._on_finished(job)
        except Exception:
            logger.exception("on_finished callback failed for job %s", job.id)

    def _loop(self) -> None:
        while not self._shutdown:
            # Hold here while paused — the running job's engine hook holds
            # inside itself; this gate catches the *next* job.
            while self.pause_event.is_set() and not self._shutdown:
                self._wake.wait(timeout=0.5)
                self._wake.clear()
            with self._lock:
                job = self._pending.pop(0) if self._pending else None
            if job is None:
                self._wake.wait(timeout=0.5)
                self._wake.clear()
                continue

            self._current = job
            cancel_evt = threading.Event()
            with self._lock:
                self._cancel_events[job.id] = cancel_evt

            try:
                space_err = free_space_error(job)
                if space_err is not None:
                    _set_worker_field(job, "status", "failed")
                    _set_worker_field(job, "status_message", space_err)
                    _set_worker_field(job, "error_message", space_err)
                    logger.warning(
                        "Pre-flight space check failed for job %s: %s", job.id, space_err
                    )
                else:
                    if self._on_started is not None:
                        self._on_started(job)
                    self._runner(job, cancel_evt)
            except Exception:
                logger.exception("Runner raised for job %s", job.id)  # belt & braces
            finally:
                with self._lock:
                    self._cancel_events.pop(job.id, None)
                self._current = None
                self._notify_finished(job)

        logger.info("Job queue worker stopped")


__all__ = ["JobQueue"]
