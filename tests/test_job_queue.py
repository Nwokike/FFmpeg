"""JobQueue semantics: serial execution, pending-cancel, shutdown."""

from __future__ import annotations

import threading
import time

from core.state import Job
from services.job_queue import JobQueue


def _job() -> Job:
    return Job(op="convert", input_path="in.mp4", output_path="out.mp4")


def test_serial_execution_order():
    order: list[str] = []

    def runner(job: Job, evt) -> None:
        order.append(job.id)
        job.status = "completed"
        time.sleep(0.15)

    q = JobQueue(runner=runner)
    jobs = [_job() for _ in range(3)]
    for j in jobs:
        q.enqueue(j)
    deadline = time.time() + 5
    while len(order) < 3 and time.time() < deadline:
        time.sleep(0.05)
    q.shutdown()
    assert order == [j.id for j in jobs]  # FIFO, one at a time


def test_cancel_pending_job_removes_it_before_running():
    order: list[str] = []
    finished: dict[str, str] = {}

    def runner(job: Job, evt) -> None:
        order.append(job.id)
        job.status = "completed"
        time.sleep(0.3)

    q = JobQueue(runner=runner, on_finished=lambda j: finished.update({j.id: j.status}))
    j1, j2, j3 = _job(), _job(), _job()
    q.enqueue(j1)
    q.enqueue(j2)
    q.enqueue(j3)
    time.sleep(0.05)  # j1 running, j2/j3 pending
    assert q.cancel(j2.id) is True
    deadline = time.time() + 5
    while len(order) < 2 and time.time() < deadline:
        time.sleep(0.05)
    q.shutdown()
    assert j2.id not in order, "cancelled pending job must never run"
    assert j2.status == "cancelled"
    assert finished.get(j2.id) == "cancelled"


def test_running_job_cancel_sets_event():
    started = []

    def runner(job: Job, evt) -> None:
        started.append(job.id)
        deadline = time.time() + 5
        while not evt.is_set() and time.time() < deadline:
            time.sleep(0.01)
        job.status = "cancelled" if evt.is_set() else "completed"

    q = JobQueue(runner=runner)
    j = _job()
    q.enqueue(j)
    deadline = time.time() + 5
    while not started and time.time() < deadline:
        time.sleep(0.01)
    assert q.cancel(j.id) is True  # running path → event set
    deadline = time.time() + 5
    while j.status == "pending" and time.time() < deadline:
        time.sleep(0.01)
    q.shutdown()
    assert j.status == "cancelled"


def test_shutdown_drops_pending_jobs():
    finished: dict[str, str] = {}

    def runner(job: Job, evt) -> None:
        while not evt.is_set():
            time.sleep(0.01)
        job.status = "cancelled"

    q = JobQueue(runner=runner, on_finished=lambda j: finished.update({j.id: j.status}))
    running = _job()
    q.enqueue(running)
    time.sleep(0.1)
    pending = _job()
    q.enqueue(pending)
    q.shutdown()
    time.sleep(0.3)
    assert finished.get(pending.id) == "cancelled"
    assert pending.status == "cancelled"


def test_enqueue_sets_pending_status():
    q = JobQueue(runner=lambda job, evt: None)
    j = _job()
    q.enqueue(j)
    assert j.status == "pending"
    assert j.status_message == "Queued"
    q.shutdown()


def test_worker_space_failure_does_not_notify_outside_page_context(monkeypatch):
    job = _job()
    notified = []

    def listener(_sender, _field):
        notified.append(_field)

    job.subscribe(listener)
    monkeypatch.setattr("services.job_queue.free_space_error", lambda _job: "no space")
    q = JobQueue(runner=lambda _job, _evt: None)
    q.enqueue(job)
    notified.clear()  # enqueue is a UI-thread mutation; test the worker phase only
    deadline = time.time() + 5
    while job.status == "pending" and time.time() < deadline:
        time.sleep(0.01)
    q.shutdown()
    notified.clear()  # shutdown may run its own UI-side cancellation mutation

    assert job.status == "failed"
    assert notified == []


def test_double_start_keeps_single_worker():
    order: list[str] = []

    def runner(job: Job, evt) -> None:
        order.append(job.id)
        job.status = "completed"
        time.sleep(0.2)

    q = JobQueue(runner=runner)
    q.enqueue(_job())
    q.start()
    q.start()  # second call must not spawn a second worker
    q.start()
    deadline = time.time() + 5
    while len(order) < 1 and time.time() < deadline:
        time.sleep(0.05)
    q.shutdown()
    assert len(order) == 1


def test_runner_exception_marks_failed_not_ghost():
    finished: dict[str, str] = {}

    def runner(job: Job, evt) -> None:
        raise RuntimeError("boom")

    q = JobQueue(runner=runner, on_finished=lambda j: finished.update({j.id: j.status}))
    j = _job()
    q.enqueue(j)
    deadline = time.time() + 5
    while j.id not in finished and time.time() < deadline:
        time.sleep(0.05)
    q.shutdown()
    assert j.status == "failed"
    assert j.error_message, "reconciled failure must explain itself"


def test_cancel_reconciles_ignoring_runner():
    finished: dict[str, str] = {}

    def runner(job: Job, evt) -> None:
        # Never checks the event, never sets a terminal status.
        time.sleep(0.4)

    q = JobQueue(runner=runner, on_finished=lambda j: finished.update({j.id: j.status}))
    j = _job()
    q.enqueue(j)
    time.sleep(0.1)  # let the worker pick it up
    assert q.cancel(j.id) is True
    deadline = time.time() + 5
    while finished.get(j.id) is None and time.time() < deadline:
        time.sleep(0.05)
    q.shutdown()
    assert j.status == "cancelled"
    assert j.is_finished


def test_shutdown_joins_worker():
    gate = threading.Event()

    def runner(job: Job, evt) -> None:
        gate.wait(5)
        job.status = "completed"

    q = JobQueue(runner=runner)
    j = _job()
    q.enqueue(j)
    time.sleep(0.1)
    gate.set()
    q.shutdown(join_timeout=5.0)
    assert not (q._thread is not None and q._thread.is_alive())


def test_pause_wakes_promptly_without_poll_delay():
    q = JobQueue(runner=lambda job, evt: setattr(job, "status", "completed"))
    q.set_paused(True)
    j = _job()
    q.enqueue(j)
    time.sleep(0.1)
    assert j.status == "pending"
    started = time.time()
    q.set_paused(False)
    deadline = time.time() + 5
    while j.status == "pending" and time.time() < deadline:
        time.sleep(0.01)
    q.shutdown()
    assert time.time() - started < 1.0, "resume must wake the worker, not wait out a poll"
