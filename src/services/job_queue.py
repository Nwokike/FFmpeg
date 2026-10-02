"""Serial job queue — one media job at a time with cooperative cancellation.

Owns ordering and lifetime only: the app controller provides the engine `runner`
and the `on_started`/`on_finished` hooks that touch UI state. A single worker
thread drains the FIFO so two encodes never fight for CPU/RAM on a phone, and
cancelling a still-pending job removes it before it ever starts.

Threading contract (read before touching this file):

- Every field below (`_pending`, `_current`, `_cancel_events`, `_shutdown`,
  `_thread`, `_generation`) is owned by ``self._cond``. Snapshot to locals
  under the condition, then act outside it.
- ``_notify_finished`` (which runs app callbacks that re-enter the queue via
  ``queued_jobs``/``cancel``/``enqueue``) is NEVER called while holding the
  condition. Violating this deadlocks.
- Worker-thread Job writes use :func:`_set_worker_field` (bypasses the Flet
  observable hook). UI-thread writes use plain assignment so subscribers
  update. The two must never be mixed up: notifying Flet from the worker or
  the close path races the render loop.
- The worker loop is generation-scoped: ``start()`` bumps ``_generation``
  whenever it spawns a thread, and a loop whose generation no longer matches
  exits. Restart-after-shutdown can never leave two workers alive.
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

_TERMINAL_STATUSES = ("completed", "failed", "cancelled")


def free_space_error(job: Job) -> str | None:
    """None when the output's filesystem plausibly has room; else why not.

    Estimate = source size (outputs are usually smaller) with the floor for
    scratch. A failed probe returns None — the engine is the final authority.
    """
    try:
        target = Path(job.output_path)
        probe_dir = target.parent
        free = shutil.disk_usage(probe_dir).free
    except OSError as exc:
        logger.debug("Disk-space probe failed for %s: %s", job.output_path, exc)
        return None
    needed = max(job.original_size_bytes or 0, _MIN_FREE_BYTES)
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
        self._cond = threading.Condition(threading.Lock())
        self._shutdown = False
        self._current: Job | None = None
        self._thread: threading.Thread | None = None
        self._generation = 0
        # Shared pause switch: the worker holds BEFORE pulling the next job and
        # the engine's pause hook (same Event) holds INSIDE the running one.
        # Mutated only under _cond so wait_for() can never miss a flip.
        self.pause_event = threading.Event()

    # ── Pause ──────────────────────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        return self.pause_event.is_set()

    def set_paused(self, value: bool) -> bool:
        """Pause (True) or resume (False) the queue; returns the new state."""
        with self._cond:
            if value:
                self.pause_event.set()
            else:
                self.pause_event.clear()
            # Wake under the same lock the worker waits on — no lost signal.
            self._cond.notify_all()
        return value

    def toggle_pause(self) -> bool:
        return self.set_paused(not self.paused)

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the worker thread (idempotent, generation-scoped)."""
        with self._cond:
            if self._thread is not None and self._thread.is_alive():
                return
            self._shutdown = False
            self._generation += 1
            generation = self._generation
            self._thread = threading.Thread(
                target=self._loop, args=(generation,), name="job-queue", daemon=True
            )
            self._thread.start()

    def enqueue(self, job: Job) -> None:
        """Queue a job; the worker picks it up when the current job finishes."""
        with self._cond:
            if self._shutdown:
                logger.warning("Queue shut down; dropping job %s", job.id)
                dropped = job
            else:
                job.status = "pending"
                job.status_message = "Queued"
                self._pending.append(job)
                dropped = None
                self._cond.notify_all()
        if dropped is not None:
            # Finish outside the lock: the callback may re-enter the queue.
            _set_worker_field(dropped, "status", "cancelled")
            _set_worker_field(dropped, "status_message", "App is closing")
            self._notify_finished(dropped)
            return
        self.start()

    def shutdown(self, join_timeout: float | None = 5.0) -> None:
        """Stop accepting work, cancel whatever is running, drop pending jobs.

        Safe to call from disconnect/close handlers: finished callbacks are
        expected to be defensive (the page may already be gone). Waits for the
        worker to exit (bounded by ``join_timeout``) so no encode keeps
        running into teardown.
        """
        with self._cond:
            self._shutdown = True
            pending = list(self._pending)
            self._pending.clear()
            running_evt = self._cancel_events.get(self._current.id) if self._current else None
            running = self._current
            # A paused worker must observe _shutdown, not sleep on the gate.
            self.pause_event.clear()
            self._cond.notify_all()
            thread = self._thread
        for job in pending:
            _set_worker_field(job, "status", "cancelled")
            _set_worker_field(job, "status_message", "App is closing")
            self._notify_finished(job)
        if running_evt is not None:
            running_evt.set()
        if running is not None and running.status not in _TERMINAL_STATUSES:
            # Worker-thread-safe write; the owning thread reconciles below.
            # Never overwrite a terminal status the worker already published.
            _set_worker_field(running, "status_message", "Cancelling...")
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=join_timeout)
            if thread.is_alive():
                logger.warning("Job queue worker did not stop within %ss", join_timeout)

    # ── Inspection ───────────────────────────────────────────────────────

    @property
    def current(self) -> Job | None:
        """The job currently executing, if any."""
        with self._cond:
            return self._current

    @property
    def queued_jobs(self) -> list[Job]:
        """Pending jobs in FIFO order (snapshot)."""
        with self._cond:
            return list(self._pending)

    def active_jobs(self) -> list[Job]:
        """Running job first, then pending — what the Jobs UI should render."""
        with self._cond:
            return ([self._current] if self._current else []) + list(self._pending)

    # ── Cancellation ─────────────────────────────────────────────────────

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job (removed immediately) or signal the running one.

        Returns True if the job was found and cancellation was initiated.
        """
        with self._cond:
            for job in self._pending:
                if job.id == job_id:
                    self._pending.remove(job)
                    break
            else:
                evt = self._cancel_events.get(job_id)
                if evt is not None:
                    evt.set()
                    return True
                return False
            # Matched entry removed while we held the condition — finish the
            # bookkeeping without holding it (finisher may re-enter the queue).
            removed = job
        _set_worker_field(removed, "status", "cancelled")
        _set_worker_field(removed, "status_message", "Cancelled")
        self._notify_finished(removed)
        return True

    # ── Worker ───────────────────────────────────────────────────────────

    def _notify_finished(self, job: Job) -> None:
        if self._on_finished is None:
            return
        try:
            self._on_finished(job)
        except Exception:
            logger.exception("on_finished callback failed for job %s", job.id)

    def _loop(self, generation: int) -> None:
        while True:
            with self._cond:
                self._cond.wait_for(
                    lambda: (
                        self._shutdown
                        or self._generation != generation
                        or (not self.pause_event.is_set() and bool(self._pending))
                    )
                )
                if self._shutdown or self._generation != generation:
                    break
                job = self._pending.pop(0)
                cancel_evt = threading.Event()
                self._cancel_events[job.id] = cancel_evt
                self._current = job

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
                    started_ok = True
                    if self._on_started is not None:
                        try:
                            self._on_started(job)
                        except Exception:
                            logger.exception("on_started raised for job %s", job.id)
                            started_ok = False
                    if started_ok:
                        try:
                            self._runner(job, cancel_evt)
                        except Exception:
                            logger.exception("Runner raised for job %s", job.id)
            finally:
                with self._cond:
                    self._cancel_events.pop(job.id, None)
                    if self._current is job:
                        self._current = None
                # Reconcile: a runner that returns (or raises) without leaving
                # a terminal status must not strand a ghost row. A set cancel
                # event means cancelled even if the runner ignored it.
                if job.status not in _TERMINAL_STATUSES:
                    if cancel_evt.is_set():
                        _set_worker_field(job, "status", "cancelled")
                        _set_worker_field(job, "status_message", "Cancelled")
                    else:
                        _set_worker_field(job, "status", "failed")
                        _set_worker_field(job, "status_message", "Processing failed")
                        if not job.error_message:
                            _set_worker_field(
                                job,
                                "error_message",
                                "The worker stopped without reporting a result.",
                            )
                self._notify_finished(job)

        logger.info("Job queue worker stopped")


__all__ = ["JobQueue"]
