"""Streams screen — record HTTP/HTTPS/HLS/DASH live streams on-device.

Protocol availability comes from the engine probe (first runtime consumer of
engine_probe's PROTOCOLS check). Recording runs through the normal job queue:
Start enqueues a `record` job; the banner's cancel button acts as **Stop** and
KEEPS the recording (engine returns normally on cancel for this op).

Downloads are capped (Settings → max HLS download, default 2 GB): the screen
preflights HLS totals via HEAD and refuses past the cap with a per-download
"Download anyway" override — a multi-GB VOD must never silently fill the disk.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import flet as ft
import httpx

from core.engine_probe import _probe_protocol
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir
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
from services.engine_service import EngineService
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
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    url, set_url = ft.use_state("")
    fmt, set_fmt = ft.use_state("mp4")
    dur_label, set_dur_label = ft.use_state("Until I stop")
    proto_status, set_proto_status = ft.use_state("checking")  # checking|present|missing
    preflight, set_preflight = ft.use_state(None)  # None|checking|{total}|error str
    override_cap, set_override_cap = ft.use_state(False)
    starting, set_starting = ft.use_state(False)

    cap_mb = app_state.settings.get("max_hls_download_mb", 2048)

    def _check_protocols_sync() -> tuple[str, str]:
        results = []
        for scheme in ("https", "http"):
            try:
                results.append(_probe_protocol(scheme))
            except Exception as exc:
                logger.warning("Protocol probe %s failed: %s", scheme, exc)
                results.append("missing")
        if all(r == "present" for r in results):
            return "present", "present"
        if any(r == "present" for r in results):
            return "partial", "partial"
        return "missing", "missing"

    async def _load_protocols() -> None:
        try:
            _, status = await asyncio.to_thread(_check_protocols_sync)
            set_proto_status(status)
        except Exception as exc:
            logger.warning("Protocol check failed: %s", exc)
            set_proto_status("missing")

    ft.use_effect(lambda: page.run_task(_load_protocols), [])

    url_ok = url.strip().lower().startswith(("http://", "https://"))
    is_hls = ".m3u8" in url.strip().lower()

    async def _run_preflight(target: str, cap: float) -> None:
        set_preflight("checking")
        set_override_cap(False)
        try:

            def _sync() -> tuple[int | None, str | None]:
                with httpx.Client(follow_redirects=True) as client:
                    try:
                        _, total = EngineService.estimate_hls_segments(client, target)
                        return total, None
                    except ValueError as exc:
                        return None, str(exc)

            total, error = await asyncio.to_thread(_sync)
            if error is not None:
                set_preflight(error)
            else:
                set_preflight({"total": total, "cap": cap})
        except Exception as exc:
            logger.warning("HLS preflight failed for %s: %s", target, exc)
            set_preflight(f"Couldn't size the stream: {exc}")

    def _check_url(_=None) -> None:
        target = url.strip()
        if not target.lower().startswith(("http://", "https://")):
            return
        if ".m3u8" not in target.lower():
            set_preflight(None)
            return
        try:
            cap_val = float(cap_mb)
        except (TypeError, ValueError):
            cap_val = 2048
        page.run_task(_run_preflight, target, cap_val)

    def _proto_chip() -> ft.Control:
        if proto_status == "checking":
            label, color = "Checking protocols…", muted
        elif proto_status == "present":
            label, color = "HTTP/HTTPS available", PRIMARY
        elif proto_status == "partial":
            label, color = "Some protocols unavailable", ACCENT_AMBER
        else:
            label, color = "Network protocols unavailable", ACCENT_RED
        return ft.Chip(
            label=ft.Text(label, size=FONT_SM, color=color),
            # Flet 1.0 Chip has no `avatar` prop — `leading` is the icon slot
            # (avatar= raised TypeError at construction on every visit here).
            leading=ft.Icon(
                ft.Icons.CELL_TOWER_ROUNDED,
                size=16,
                color=color,
            ),
        )

    def _preflight_card() -> ft.Control | None:
        if preflight is None or not is_hls:
            return None
        if preflight == "checking":
            body = ft.Text("Sizing the stream…", size=FONT_SM, color=muted)
        elif isinstance(preflight, str):
            body = ft.Text(preflight, size=FONT_SM, color=ACCENT_RED)
        else:
            total = preflight["total"]
            cap = preflight["cap"]
            if total is None:
                body = ft.Column(
                    controls=[
                        ft.Text(
                            "Size unknown (server omits lengths) — the download "
                            f"aborts past {format_bytes(cap * 1024 * 1024)} unless overridden.",
                            size=FONT_SM,
                            color=muted,
                        ),
                        ft.Checkbox(
                            label="Download anyway (this stream)",
                            value=override_cap,
                            on_change=lambda e: set_override_cap(bool(e.control.value)),
                        ),
                    ],
                    spacing=SPACE_SM,
                )
            else:
                over = total > cap * 1024 * 1024
                body = ft.Column(
                    controls=[
                        ft.Text(
                            f"Stream total ≈ {format_bytes(total)}"
                            + (
                                f" — over the {format_bytes(cap * 1024 * 1024)} cap"
                                if over
                                else " — within the download cap"
                            ),
                            size=FONT_SM,
                            color=ACCENT_RED if over else muted,
                        ),
                        *(
                            [
                                ft.Checkbox(
                                    label="Download anyway (this stream)",
                                    value=override_cap,
                                    on_change=lambda e: set_override_cap(bool(e.control.value)),
                                )
                            ]
                            if over
                            else []
                        ),
                    ],
                    spacing=SPACE_SM,
                )
        return card_container(
            content=body,
            padding=SPACE_MD,
            border_radius=RADIUS_LG,
            is_dark=is_dark,
        )

    def _start(_):
        if not url_ok or starting:
            return
        if isinstance(preflight, dict):
            total = preflight["total"]
            cap = preflight["cap"]
            over = total is not None and total > cap * 1024 * 1024
            unknown = total is None
            if (over or unknown) and not override_cap:
                return
        ext, container_format = _FORMATS[fmt]
        duration = next((d for label, d in _DURATION_CHOICES if label == dur_label), None)
        # Millisecond stamp: two taps in one second must not share a path.
        ts = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        job = Job(
            op="record",
            input_path=url.strip(),
            output_path=str(get_temp_dir() / f"stream_{ts}.{ext}"),
            params={
                "url": url.strip(),
                "format": container_format,
                "duration_s": duration,
                "ignore_hls_cap": bool(override_cap),
            },
        )
        try:
            set_starting(True)
            ctrl.start_job(job)
        except Exception as exc:
            logger.warning("Record start failed: %s", exc)
            set_starting(False)

    preflight_card = _preflight_card()
    blocked_on_cap = (
        isinstance(preflight, dict)
        and (
            (preflight["total"] is not None and preflight["total"] > preflight["cap"] * 1024 * 1024)
            or preflight["total"] is None
        )
        and not override_cap
    )

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
                            on_submit=_check_url,
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
                                        on_select=lambda _, text=label_text: set_dur_label(text),
                                    )
                                    for label_text, _dur_value in _DURATION_CHOICES
                                ],
                            ],
                            spacing=SPACE_SM,
                            wrap=True,
                        ),
                        *(
                            [
                                ft.OutlinedButton(
                                    "Check size",
                                    icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
                                    on_click=_check_url,
                                )
                            ]
                            if is_hls and url_ok
                            else []
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            *([preflight_card] if preflight_card is not None else []),
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
                disabled=not url_ok or starting or blocked_on_cap,
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
