"""Streams screen — record HTTP/HTTPS/HLS/DASH live streams on-device.

Protocol availability comes from the engine probe (first runtime consumer of
engine_probe's PROTOCOLS check). Recording runs through the normal job queue:
Start enqueues a `record` job; the banner's cancel button acts as **Stop** and
KEEPS the recording (engine returns normally on cancel for this op).
"""

from __future__ import annotations

import asyncio
import logging
import time

import flet as ft

from core.engine_probe import _probe_protocol
from core.state import Job
from core.storage_paths import get_temp_dir
from core.styles import card_container, section_header
from core.theme import (
    ACCENT_AMBER,
    ACCENT_RED,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller

logger = logging.getLogger(__name__)

# chip label → (extension, av output format or None to infer from extension)
_FORMATS = {
    "mp4": ("mp4", None),
    "ts": ("ts", "mpegts"),
    "mkv": ("mkv", "matroska"),
}
_DURATION_CHOICES = (("Until I stop", None), ("30 seconds", 30.0), ("2 minutes", 120.0))


@ft.component
def StreamsScreen() -> ft.Control:
    """URL entry + record controls with a live protocol-availability badge."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    url, set_url = ft.use_state("")
    fmt, set_fmt = ft.use_state("mp4")
    dur_label, set_dur_label = ft.use_state("Until I stop")
    proto_status, set_proto_status = ft.use_state("checking")  # checking|present|missing

    def _check_protocols_sync() -> tuple[str, str]:
        results = []
        for scheme in ("https", "http"):
            try:
                results.append(_probe_protocol(scheme))
            except Exception as exc:  # noqa: BLE001 — badge is informational
                logger.debug("Protocol probe %s failed: %s", scheme, exc)
                results.append("missing")
        if all(r == "present" for r in results):
            return "present", "present"
        if any(r == "present" for r in results):
            return "partial", "partial"
        return "missing", "missing"

    async def _load_protocols() -> None:
        _, status = await asyncio.to_thread(_check_protocols_sync)
        set_proto_status(status)

    ft.use_effect(lambda: page.run_task(_load_protocols), [])

    url_ok = url.strip().lower().startswith(("http://", "https://"))

    def _proto_chip() -> ft.Control:
        if proto_status == "checking":
            label, color = "Checking protocols…", muted
        elif proto_status == "present":
            label, color = "HTTP/HTTPS/HLS available", PRIMARY
        elif proto_status == "partial":
            label, color = "Some protocols unavailable", ACCENT_AMBER
        else:
            label, color = "Network protocols unavailable", ACCENT_RED
        return ft.Chip(
            label=ft.Text(label, size=FONT_SM, color=color),
            avatar=ft.Icon(
                ft.Icons.CELL_TOWER_ROUNDED,
                size=16,
                color=color,
            ),
        )

    def _start(_):
        if not url_ok:
            return
        ext, container_format = _FORMATS[fmt]
        duration = next(
            (d for label, d in _DURATION_CHOICES if label == dur_label), None
        )
        ts = int(time.time())
        job = Job(
            op="record",
            input_path=url.strip(),
            output_path=str(get_temp_dir() / f"stream_{ts}.{ext}"),
            params={
                "url": url.strip(),
                "format": container_format,
                "duration_s": duration,
            },
        )
        ctrl.start_job(job)

    return ft.ListView(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Live Streams", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            section_header(
                "Record a Stream",
                "HTTP, HTTPS, HLS (.m3u8) and DASH — saved on-device",
                is_dark=is_dark,
            ),
            _proto_chip(),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.TextField(
                            value=url,
                            label="Stream URL",
                            hint_text="https://example.com/live/index.m3u8",
                            prefix_icon=ft.Icons.LINK_ROUNDED,
                            dense=True,
                            on_change=lambda e: set_url(e.control.value or ""),
                        ),
                        ft.Row(
                            controls=[
                                ft.Text("Save as", size=FONT_SM, color=muted),
                                *[
                                    ft.Chip(
                                        label=ft.Text(ext.upper()),
                                        selected=fmt == ext,
                                        on_select=lambda _, f=ext: set_fmt(f),
                                    )
                                    for ext in _FORMATS
                                ],
                            ],
                            spacing=SPACE_SM,
                            wrap=True,
                        ),
                        ft.Row(
                            controls=[
                                ft.Text("Stop after", size=FONT_SM, color=muted),
                                *[
                                    ft.Chip(
                                        label=ft.Text(label_text),
                                        selected=dur_label == label_text,
                                        on_select=lambda _, text=label_text: set_dur_label(
                                            text
                                        ),
                                    )
                                    for label_text, _dur_value in _DURATION_CHOICES
                                ],
                            ],
                            spacing=SPACE_SM,
                            wrap=True,
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Text("How recording works", size=FONT_MD, weight=ft.FontWeight.W_600),
                        ft.Text(
                            "Start queues a record job — watch progress in the jobs banner. "
                            "Banner Stop KEEPS what was recorded so far; the result screen "
                            "offers Save/Share like any other job.",
                            size=FONT_SM,
                            color=muted,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            ft.FilledButton(
                "Start Recording",
                icon=ft.Icons.FIBER_MANUAL_RECORD_ROUNDED,
                height=48,
                disabled=not url_ok,
                on_click=_start,
            ),
            *(
                []
                if url_ok or not url.strip()
                else [
                    ft.Text(
                        "Enter an http:// or https:// URL to enable recording.",
                        size=FONT_SM,
                        color=ACCENT_RED,
                    )
                ]
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )


__all__ = ["StreamsScreen"]
