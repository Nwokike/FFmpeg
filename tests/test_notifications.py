"""Job notification / foreground-service contract.

Pins the pieces the phone depends on: Android-only gating, progress +
Cancel/Exit actions, in-place updates, cancel wiring into the queue, the
manifest/resource declarations, and the soft-fail rule (a missing package or
a denied permission must never break a job).
"""

from __future__ import annotations

import asyncio
import sys
import tomllib
import types
from pathlib import Path

import flet as ft
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from services.job_queue import JobQueue  # noqa: E402
from services.notification_service import (  # noqa: E402
    CHANNEL,
    FGS_ID,
    JobNotificationService,
)


class _FakeNotifications:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, dict]] = []
        self.on_action = None
        self.on_tap = None

    async def request_permissions(self, **_kwargs) -> bool:
        return True

    async def start_foreground_service(self, **kwargs) -> None:
        self.calls.append(("start", kwargs))

    async def show(self, **kwargs) -> None:
        self.calls.append(("show", kwargs))

    async def stop_foreground_service(self) -> None:
        self.calls.append(("stop", {}))

    async def cancel(self, *_args, **_kwargs) -> None:
        self.calls.append(("cancel", {}))


def _fake_ftn() -> types.ModuleType:
    mod = types.ModuleType("flet_notifications")
    mod.Notifications = _FakeNotifications
    for name in (
        "AndroidOptions",
        "NotificationChannel",
        "AndroidProgress",
        "NotificationAction",
    ):
        setattr(mod, name, (lambda label: lambda **kw: {"type": label, **kw})(name))
    mod.AndroidImportance = types.SimpleNamespace(LOW="LOW")
    mod.AndroidServiceStartType = types.SimpleNamespace(STICKY="STICKY")
    mod.AndroidForegroundServiceType = types.SimpleNamespace(SPECIAL_USE="SPECIAL_USE")
    return mod


class _FakePage:
    def __init__(self, platform=ft.PagePlatform.ANDROID):
        self.platform = platform
        self.web = False
        self.services: list = []
        self.tasks: list = []

    def run_task(self, fn, *args) -> None:
        self.tasks.append(fn(*args))


@pytest.fixture
def ftn(monkeypatch):
    mod = _fake_ftn()
    monkeypatch.setitem(sys.modules, "flet_notifications", mod)
    return mod


def test_no_package_is_a_logged_noop(monkeypatch):
    monkeypatch.setitem(sys.modules, "flet_notifications", None)  # breaks the import
    page = _FakePage()
    svc = JobNotificationService(page)
    svc.mount()
    assert svc._svc is None
    asyncio.run(svc.update("anything", 10.0))  # must not raise
    asyncio.run(svc.finished(types.SimpleNamespace(status="completed"), 0))


def test_progress_update_posts_cancel_and_exit_actions(ftn):
    page = _FakePage()
    svc = JobNotificationService(page)
    svc.mount()
    assert svc._svc in page.services
    asyncio.run(svc.update("Converting: a.mp4 — 42%", 42.0))
    kind, kwargs = svc._svc.calls[0]
    assert kind == "start" and kwargs["id"] == FGS_ID
    assert kwargs["service_types"] == ["SPECIAL_USE"]
    assert [a["id"] for a in kwargs["actions"]] == ["cancel", "exit"]
    assert kwargs["options"]["progress"]["value"] == 42
    assert kwargs["options"]["channel"]["id"] == CHANNEL


def test_second_update_reuses_the_service_in_place(ftn):
    page = _FakePage()
    svc = JobNotificationService(page)
    svc.mount()
    asyncio.run(svc.update("a", 10.0, force=True))
    asyncio.run(svc.update("b", 55.0, force=True))
    assert [kind for kind, _ in svc._svc.calls] == ["start", "show"]
    assert svc._svc.calls[1][1]["options"]["progress"]["value"] == 55


def test_off_android_is_a_noop(ftn):
    page = _FakePage(platform=ft.PagePlatform.LINUX)
    svc = JobNotificationService(page)
    svc.mount()
    asyncio.run(svc.update("x", 10.0))
    assert svc._svc.calls == []


def test_cancel_action_runs_the_cancel_callback(ftn):
    page = _FakePage()
    called: list[bool] = []

    async def cancel_active():
        called.append(True)

    svc = JobNotificationService(page, cancel_active=cancel_active)
    svc.mount()
    svc._on_action(types.SimpleNamespace(action_id="cancel"))
    for coro in page.tasks:
        asyncio.run(coro)
    assert called == [True]


def test_finished_job_stops_the_service_and_posts_a_result(ftn):
    page = _FakePage()
    svc = JobNotificationService(page)
    svc.mount()
    asyncio.run(svc.update("running", 10.0, force=True))
    job = types.SimpleNamespace(id="j1", status="completed", output_path="/tmp/out.mp4")
    asyncio.run(svc.finished(job, queued=0))
    assert [kind for kind, _ in svc._svc.calls][-2:] == ["stop", "show"]
    done = svc._svc.calls[-1][1]
    assert done["payload"] == "job:j1" and "out.mp4" in done["body"]


def test_finished_hands_the_service_to_the_next_job(ftn):
    page = _FakePage()
    svc = JobNotificationService(page)
    svc.mount()
    asyncio.run(svc.update("running", 10.0, force=True))
    job = types.SimpleNamespace(id="j1", status="completed", output_path="/tmp/o.mp4")
    asyncio.run(svc.finished(job, queued=2))
    assert [kind for kind, _ in svc._svc.calls] == ["start"]  # no stop, no alert


def test_queue_cancel_active_targets_the_running_job():
    queue = JobQueue(runner=lambda job, evt: None)
    queue._current = types.SimpleNamespace(id="job-1")
    seen: list[str] = []
    queue.cancel = lambda job_id: seen.append(job_id) or True
    assert queue.cancel_active() is True
    assert seen == ["job-1"]
    queue._current = None
    assert queue.cancel_active() is False


def test_android_declarations_and_icons_are_present():
    doc = tomllib.loads((ROOT / "pyproject.toml").read_text())
    android = doc["tool"]["flet"]["android"]
    assert android["res_dir"] == "android_res"
    perms = android["permission"]
    for perm in (
        "android.permission.WAKE_LOCK",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.FOREGROUND_SERVICE",
        "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
    ):
        assert perms.get(perm) is True, perm
    service = android["service"]["com.dexterous.flutterlocalnotifications.ForegroundService"]
    assert service["foregroundServiceType"] == "specialUse"
    assert service["property"]["android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"]
    for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        icon = ROOT / "android_res" / f"drawable-{density}" / "ic_stat_ffmpegav.png"
        assert icon.is_file() and icon.stat().st_size > 0, icon
    deps = doc["project"]["dependencies"]
    assert any(d.startswith("flet-notifications") for d in deps)
