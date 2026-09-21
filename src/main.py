"""FFmpeg — on-device media studio. M0 scaffold entry point.

Minimal house bootstrap: logging ring handler + crash hook + engine probe
screen (the M0 device-spike UI). M1 replaces the body with the full
AppController + KTV mount (ServiceCtx → ControllerMethodsCtx → AppShell).
"""

from __future__ import annotations

import logging
import sys
from collections import deque

import flet as ft

from core.constants import APP_NAME, BUILD_NUMBER, PLAYSTORE_URL, UPDATE_CONFIG_URL
from core.engine_probe import EngineProbe, probe, synthetic_transcode

logger = logging.getLogger(__name__)


class _RingLogHandler(logging.Handler):
    """In-memory log ring backing the Settings 'Activity Terminal' tile."""

    def __init__(self, maxlen: int = 500):
        super().__init__()
        self.records: deque[logging.LogRecord] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def get_logs(self) -> list[str]:
        return [r.getMessage() for r in self.records]


def _bootstrap_logging() -> _RingLogHandler:
    ring = _RingLogHandler()
    logging.basicConfig(level=logging.INFO, force=True)
    logging.getLogger().addHandler(ring)
    return ring


def _crash_hook() -> None:
    def _hook(exc_type, exc, _tb):
        logger.critical("Uncaught exception: %s", exc)
        sys.__excepthook__(exc_type, exc, _tb)

    sys.excepthook = _hook


def _report_card(p: EngineProbe | None) -> ft.Control:
    if p is None:
        return ft.Text("Engine not probed yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    return ft.Container(
        content=ft.Column(
            [ft.Text(line, size=12, selectable=True) for line in p.to_text().splitlines()],
            tight=True,
        ),
        padding=12,
        border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
    )


async def main(page: ft.Page) -> None:
    _bootstrap_logging()  # ring handler attached to root; M1 wires the Activity Terminal to it
    _crash_hook()
    page.title = APP_NAME
    page.padding = 16

    probe_result: list[EngineProbe] = []
    status = ft.Text("Self-test not run yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    probe_btn = ft.FilledButton("Probe engine", icon=ft.Icons.SCIENCE)

    def _do_probe(_: ft.Control) -> None:
        p = probe()
        probe_result.append(p)
        logger.info("Probe complete:\n%s", p.to_text())
        root.controls[1] = _report_card(probe_result[-1])
        page.update()

    probe_btn.on_click = _do_probe

    def _do_selftest(e: ft.Control) -> None:
        btn: ft.FilledTonalButton = e.control
        btn.disabled = True
        page.update()

        def _worker() -> None:
            try:
                res = synthetic_transcode("ui-spike")
                msg = (
                    f"OK — {res['frames']}/{res['expected_frames']} frames, "
                    f"MP4 {res['mp4_bytes'] // 1024} KB, JPG {res['jpg_bytes'] // 1024} KB, "
                    f"{res['encode_s']}s encode"
                    if res.get("ok")
                    else f"FAILED — {res.get('error')}"
                )
            except Exception as exc:  # noqa: BLE001 - surface any engine failure verbatim
                msg = f"FAILED — {exc}"
            logger.info("Self-test: %s", msg)
            page.run_task(_publish, msg, btn)

        page.run_thread(_worker)

    async def _publish(msg: str, btn: ft.FilledTonalButton) -> None:
        btn.disabled = False
        status.value = msg
        status.color = ft.Colors.GREEN if msg.startswith("OK") else ft.Colors.RED
        page.update()

    selftest_btn = ft.FilledTonalButton(
        "Run transcode self-test",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        on_click=_do_selftest,
    )

    root = ft.Column(
        controls=[
            ft.Column(
                [
                    ft.Text(f"{APP_NAME} — M0 scaffold", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"build {BUILD_NUMBER} · engine self-test", size=12),
                    ft.Divider(),
                ],
                tight=True,
            ),
            _report_card(None),
            ft.Row([probe_btn, selftest_btn], spacing=12),
            status,
            ft.Divider(),
            ft.Text(
                f"update: {UPDATE_CONFIG_URL}\nplay: {PLAYSTORE_URL}",
                size=10,
                color=ft.Colors.ON_SURFACE_VARIANT,
                selectable=True,
            ),
        ],
        spacing=12,
        expand=True,
    )
    page.add(root)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
