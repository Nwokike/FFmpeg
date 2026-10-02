"""show_snack: reuse, no destructive pop, suppression bool + logger race."""

from __future__ import annotations

import logging
import threading

import flet as ft

from core.logger_handler import MemoryLogHandler
from core.notify import show_snack


class _FakeDialogs:
    def __init__(self):
        self.controls: list = []


class _FakePage:
    """Minimal show_dialog/pop_dialog twin of BasePage semantics."""

    def __init__(self):
        self._dialogs = _FakeDialogs()

    def show_dialog(self, dialog):
        if dialog in self._dialogs.controls:
            raise RuntimeError("Dialog is already opened")
        dialog.open = True
        self._dialogs.controls.append(dialog)

    def pop_dialog(self):
        for dlg in reversed(self._dialogs.controls):
            if getattr(dlg, "open", False):
                dlg.open = False
                return dlg
        return None

    def update(self, *args):
        pass


def test_identical_retoast_reuses_instead_of_raising():
    page = _FakePage()
    assert show_snack(page, "same message") is True
    # Same text twice: single reused instance, no RuntimeError path.
    assert show_snack(page, "same message") is True
    assert len(page._dialogs.controls) == 1


def test_real_dialog_is_never_popped():
    page = _FakePage()
    real = ft.AlertDialog(title=ft.Text("keep me"))
    page.show_dialog(real)
    assert show_snack(page, "background news") is True
    assert real.open is True, "toast must never destroy the user's dialog"
    # The toast still went out (stacked); nothing was popped.
    assert len(page._dialogs.controls) == 2


def test_suppression_bool_when_page_cannot_show():
    class _DeadPage(_FakePage):
        def show_dialog(self, dialog):
            raise RuntimeError("session gone")

        def update(self, *args):
            raise RuntimeError("session gone")

    assert show_snack(_DeadPage(), "critical") is False


def test_invalid_duration_falls_back_and_shows():
    page = _FakePage()
    assert show_snack(page, "hi", duration_ms=0) is True
    assert show_snack(page, "hi", duration_ms=-5) is True


def test_logger_race_log_while_read():
    handler = MemoryLogHandler(maxlen=500)
    log = logging.getLogger("m1.notify.race")
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer():
        i = 0
        while not stop.is_set():
            log.info("line %d", i)
            i += 1

    threads = [threading.Thread(target=writer, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    try:
        for _ in range(200):
            lines = MemoryLogHandler.get_logs(limit=50)
            assert len(lines) <= 50
    except BaseException as exc:
        errors.append(exc)
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=5)
        log.removeHandler(handler)
    assert not errors
    MemoryLogHandler.clear()
