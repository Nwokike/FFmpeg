"""Persistent job notification + Android foreground service.

Ported from the house pattern (proot-distro-flet's ``session_fgs`` and
CollabShell's ``session_notify``): while a media job runs, a sticky
foreground service keeps the process alive when the app is minimized and
shows an ongoing notification. Unlike those apps, this notification carries
**progress and a Cancel action**, plus the app-level Exit.

Facts this module is built on (verified against the installed
``flet_notifications`` 1.1.2 source):
- ``Notifications`` is an ``ft.Service`` that registers on construction.
- Re-posting ``show(id=...)`` updates a notification in place; combined with
  ``only_alert_once`` it advances a progress bar without re-alerting.
- ``start_foreground_service`` reuses the same id for subsequent updates and
  is Android-only; ``stop_foreground_service`` also removes the notification.
- Action taps arrive on ``on_action`` (``action_id``); Python does not run in
  the background isolate, so actions must use ``foreground=True`` to act
  immediately. Worker threads never touch the bridge — updates are pushed
  from the page's progress-drain coroutine.
- Every call degrades to a log line: a notification must never break a job.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from core.constants import OP_LABELS

logger = logging.getLogger("job_notify")

FGS_ID = 1  # nonzero: the plugin rejects id=0 for the foreground service
DONE_ID = 2
CHANNEL = "jobs"
CHANNEL_NAME = "Jobs"
ICON = "ic_stat_ffmpegav"
_MIN_INTERVAL = 0.5  # seconds between progress re-posts


def _is_android(page) -> bool:
    try:
        import flet as ft

        return not getattr(page, "web", False) and page.platform in (
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.ANDROID_TV,
        )
    except Exception:
        return False


class JobNotificationService:
    """One persistent, cancelable notification for the running job."""

    def __init__(self, page, *, cancel_active=None, open_jobs=None):
        self.page = page
        self._cancel_active = cancel_active
        self._open_jobs = open_jobs
        self._ftn = None
        self._svc = None
        self._fg = False
        self._last_at = 0.0
        self._last_body = ""

    # ── lifecycle of the service itself ─────────────────────────────────
    def mount(self) -> None:
        try:
            import flet_notifications as ftn
        except ImportError:
            logger.info("flet_notifications not installed; notifications off")
            return
        self._ftn = ftn
        try:
            self._svc = ftn.Notifications(android_default_icon=ICON)
            self._svc.on_action = self._on_action
            self._svc.on_tap = self._on_tap
            if self._svc not in self.page.services:
                self.page.services.append(self._svc)
        except Exception as exc:
            logger.warning("notification service unavailable: %s", exc)
            self._svc = None

    async def request_permission(self) -> None:
        if self._svc is None:
            return
        try:
            await self._svc.request_permissions()
        except Exception as exc:
            logger.debug("notification permission request failed: %s", exc)

    def _options(self, progress=None):
        ftn = self._ftn
        return ftn.AndroidOptions(
            channel=ftn.NotificationChannel(
                id=CHANNEL, name=CHANNEL_NAME, importance=ftn.AndroidImportance.LOW
            ),
            silent=True,
            only_alert_once=True,
            ongoing=True,
            progress=progress,
        )

    def _actions(self):
        ftn = self._ftn
        return [
            ftn.NotificationAction(
                id="cancel", title="Cancel", cancel_notification=True, foreground=True
            ),
            ftn.NotificationAction(
                id="exit", title="Exit", cancel_notification=True, foreground=True
            ),
        ]

    # ── updates ─────────────────────────────────────────────────────────
    async def update(self, body: str, percent: float | None, *, force: bool = False) -> None:
        """Post or advance the running-job notification (throttled)."""
        if self._svc is None or not _is_android(self.page):
            return
        now = time.monotonic()
        if not force and self._fg and now - self._last_at < _MIN_INTERVAL:
            return
        self._last_at = now
        self._last_body = body
        progress = (
            None
            if percent is None
            else self._ftn.AndroidProgress(value=max(0, min(100, int(percent))), max=100)
        )
        try:
            if self._fg:
                await self._svc.show(
                    id=FGS_ID,
                    title="FFmpeg AV",
                    body=body,
                    actions=self._actions(),
                    options=self._options(progress=progress),
                )
            else:
                await self.request_permission()
                await self._svc.start_foreground_service(
                    id=FGS_ID,
                    title="FFmpeg AV",
                    body=body,
                    start_type=self._ftn.AndroidServiceStartType.STICKY,
                    service_types=[self._ftn.AndroidForegroundServiceType.SPECIAL_USE],
                    actions=self._actions(),
                    options=self._options(progress=progress),
                )
                self._fg = True
        except Exception as exc:
            logger.warning("notification update failed: %s", exc)

    async def update_job(self, job, queued: int = 0) -> None:
        """Mirror one Job's progress: 'Converting clip.mp4 — 42% · 1 queued'."""
        op = OP_LABELS.get(getattr(job, "op", ""), getattr(job, "op", "Working"))
        name = Path(getattr(job, "input_path", "") or "").name or "media"
        pct = float(getattr(job, "progress", 0.0) or 0.0) * 100.0
        body = f"{op}: {name} — {pct:.0f}%"
        if queued > 0:
            body += f" · {queued} queued"
        await self.update(body, pct)

    async def finished(self, job, queued: int = 0) -> None:
        """End the foreground service; leave a tap-to-result completion alert."""
        if self._svc is None or not _is_android(self.page):
            return
        if queued > 0:
            return  # the next job's progress reuses the running service
        try:
            ok = getattr(job, "status", "") == "completed"
            name = Path(getattr(job, "output_path", "") or "").name or "output"
            body = f"Done: {name}" if ok else f"Failed: {getattr(job, 'error_message', '') or name}"
            if self._fg:
                await self._svc.stop_foreground_service()
                self._fg = False
            await self._svc.show(
                id=DONE_ID,
                title="FFmpeg AV",
                body=body,
                payload=f"job:{getattr(job, 'id', '')}",
                options=self._ftn.AndroidOptions(channel=CHANNEL, auto_cancel=True),
            )
        except Exception as exc:
            logger.debug("completion notification failed: %s", exc)

    async def stop(self) -> None:
        if self._svc is None:
            return
        try:
            if self._fg:
                await self._svc.stop_foreground_service()
                self._fg = False
            await self._svc.cancel(DONE_ID)
        except Exception as exc:
            logger.debug("notification stop failed: %s", exc)

    async def are_enabled(self) -> bool:
        """Whether the OS allows this app's notifications (Settings row)."""
        if self._svc is None:
            return False
        try:
            return bool(await self._svc.are_notifications_enabled())
        except Exception:
            return False

    async def open_settings(self) -> None:
        """Open the OS notification settings screen (Android/iOS/macOS)."""
        if self._svc is None:
            return
        try:
            await self._svc.open_settings()
        except Exception as exc:
            logger.debug("notification settings unavailable: %s", exc)

    # ── actions / taps ──────────────────────────────────────────────────
    def _on_action(self, e) -> None:
        action = getattr(e, "action_id", "")
        if action == "cancel":
            self.page.run_task(self._cancel_and_report)
        elif action == "exit":
            self.page.run_task(self._exit_app)

    async def _cancel_and_report(self) -> None:
        await self._cancel_running()
        await self.update("Cancelling…", None, force=True)

    async def _exit_app(self) -> None:
        await self._cancel_running()
        await self.stop()
        try:
            from jnius import autoclass  # type: ignore

            proc = autoclass("android.os.Process")
            proc.killProcess(proc.myPid())
            return
        except Exception:
            pass
        import os

        os._exit(0)

    async def _cancel_running(self) -> None:
        if self._cancel_active is None:
            return
        try:
            await self._cancel_active()
        except Exception as exc:
            logger.warning("cancel from notification failed: %s", exc)

    def _on_tap(self, e) -> None:
        if self._open_jobs is not None:
            try:
                self._open_jobs()
            except Exception as exc:
                logger.debug("notification tap handler failed: %s", exc)
