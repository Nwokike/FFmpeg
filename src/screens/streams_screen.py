"""Streams screen — watch and record HTTP/HTTPS/HLS/DASH live streams.

The stage IS the tool: a valid URL mounts a live ``flet_video`` player (KTV
Player's mechanics — autoplay, wakelock, mpv network timeout, loading/error
overlay, 20s watchdog) so the stream is VISIBLE from the first tap. Record
runs through the normal job queue BESIDE the player: a red REC pill and the
engine's "Recording… Ns • KB" progress sit over the video, and **Stop** is
the user's — screen-level Stop cancels the job, the engine keeps what was
captured, and completion lands on the result screen. Only an explicit
duration chip (default "Until I stop") auto-stops; a VOD ending at EOF
completes honestly, now observable on screen instead of a mystery banner.

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

try:
    import flet_video as ftv

    _HAS_VIDEO = True
except ImportError:  # pragma: no cover — package ships in the dev tree
    _HAS_VIDEO = False

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
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
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

# flet_video surfaces media_kit's native errors as free text; live HLS sits
# at the live edge where seek requests are EXPECTED to fail — those are
# noise, everything else ends the watch (KTV's same distinction).
_LIVE_SEEK_NOISE = ("cannot seek", "force-seekable")

_STAGE_HEIGHT = 280
_WATCHDOG_SECONDS = 20.0


@ft.component
def StreamsScreen() -> ft.Control:
    """Watch a stream live and record it until you stop."""
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

    # Live stage: which URL the player holds + its lifecycle flags.
    stage_url, set_stage_url = ft.use_state(None)  # None = no stage
    players_ready, set_players_ready = ft.use_state(False)
    watch_error, set_watch_error = ft.use_state(None)  # None | final message
    fullscreen, set_fullscreen = ft.use_state(False)
    video_ref = ft.use_ref(None)
    # Watchdog ownership: the effect's cleanup disarms whatever run it armed.
    watchdog_alive = ft.use_ref(False)

    cap_mb = app_state.settings.get("max_hls_download_mb", 2048)

    # The queue is the truth for what's recording — never a local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    record_running = running_job is not None and running_job.op == "record"

    # The old `starting` flag never cleared on the success path and locked
    # the button until remount. Any queue movement (job appears or the
    # active slot empties again) releases the lock.
    ft.use_effect(
        lambda: set_starting(False) if starting else None,
        [running_job.id if running_job else "", record_running],
    )

    # ── Protocol availability (engine probe) ─────────────────────────────

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

    # ── HLS preflight / cap ──────────────────────────────────────────────

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
            # Chip has no `avatar` prop — `leading` is the icon slot
            # (avatar= raises TypeError at construction).
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

    # ── Live player (KTV mechanics, result-screen lifecycle) ────────────

    def _is_mounted(control) -> bool:
        try:
            _ = control.page
            return True
        except (RuntimeError, AttributeError):
            return False

    def _safe_run_task(coro_fn, *args) -> None:
        try:
            page.run_task(coro_fn, *args)
        except Exception as exc:
            logger.debug("Stage task skipped (page gone): %s", exc)

    async def _watchdog(url_that_was_loading: str) -> None:
        watchdog_alive.current = True
        try:
            await asyncio.sleep(_WATCHDOG_SECONDS)
        except asyncio.CancelledError:  # pragma: no cover — page teardown
            return
        if not watchdog_alive.current:
            return
        if stage_url == url_that_was_loading and not players_ready:
            set_watch_error("Stream is not responding — check the URL and network.")

    async def _stop_video() -> None:
        watchdog_alive.current = False
        player, video_ref.current = video_ref.current, None
        if player is None or not _is_mounted(player):
            return
        try:
            await player.stop()
        except Exception as exc:
            logger.debug("Stage player stop skipped: %s", exc)

    def _mount_stage() -> None:
        """Build (or clear) the live player for the staged URL."""
        set_watch_error(None)
        watchdog_alive.current = False
        if not stage_url or not _HAS_VIDEO:
            set_players_ready(True)
            video_ref.current = None
            return None
        set_players_ready(False)

        def _on_load(_e=None) -> None:
            watchdog_alive.current = False
            set_players_ready(True)

        def _on_error(e=None) -> None:
            data = str(getattr(e, "data", e) or "")
            if any(noise in data.lower() for noise in _LIVE_SEEK_NOISE):
                logger.debug("Live-edge seek noise ignored: %s", data)
                return
            logger.warning("Stage player error: %s", data)
            watchdog_alive.current = False
            set_watch_error(data or "Unable to play this stream here.")

        try:
            video_ref.current = ftv.Video(
                playlist=[ftv.VideoMedia(stage_url)],
                autoplay=True,
                wakelock=True,
                expand=True,
                fit=ft.BoxFit.CONTAIN,
                fill_color=ft.Colors.BLACK,
                filter_quality=ft.FilterQuality.MEDIUM,
                playlist_mode=ftv.PlaylistMode.NONE,
                on_load=_on_load,
                on_error=_on_error,
                on_enter_fullscreen=lambda _: set_fullscreen(True),
                on_exit_fullscreen=lambda _: set_fullscreen(False),
            )
        except Exception as exc:
            logger.warning("Live player construction failed: %s", exc)
            video_ref.current = None
            set_players_ready(True)  # stage degrades; recording still works
        if video_ref.current is not None:
            _safe_run_task(_watchdog, stage_url)
        return None

    ft.use_effect(
        _mount_stage,
        [stage_url or ""],
        cleanup=lambda: (_stop_video(),),
    )

    def _watch(_=None) -> None:
        target = url.strip()
        if not target.lower().startswith(("http://", "https://")):
            return
        if stage_url == target:
            return
        set_stage_url(target)
        _check_url()

    # Paste-to-play: a complete URL stages itself — no Watch tap needed.
    # The field only writes state; the stage follows valid input, so typing
    # never mounts half a URL and recording stays an explicit action.
    def _follow_url() -> None:
        target = url.strip()
        if not target.lower().startswith(("http://", "https://")):
            return
        if stage_url != target:
            set_stage_url(target)
            _check_url()

    ft.use_effect(_follow_url, [url.strip() if isinstance(url, str) else ""])

    async def _retry_watch() -> None:
        target = stage_url
        if not target:
            return
        await _stop_video()
        set_stage_url(None)
        set_stage_url(target)

    # ── Record start / stop ──────────────────────────────────────────────

    def _start(_):
        if not url_ok or starting or record_running:
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
            # Watch the stream while it records — the stage stays up and the
            # queue keeps the truth. return_to keeps us HERE (the old flow
            # bounced to the dashboard, leaving the tool that knows how to
            # stop the recording).
            if stage_url != url.strip():
                set_stage_url(url.strip())
            ctrl.start_job(job, return_to="streams")
        except Exception as exc:
            logger.warning("Record start failed: %s", exc)
            set_starting(False)

    def _stop(_=None):
        if not record_running:
            return
        ctrl.cancel_job(running_job.id)

    preflight_card = _preflight_card()
    blocked_on_cap = (
        isinstance(preflight, dict)
        and (
            (preflight["total"] is not None and preflight["total"] > preflight["cap"] * 1024 * 1024)
            or preflight["total"] is None
        )
        and not override_cap
    )

    # ── Stage widgets ────────────────────────────────────────────────────

    def _rec_pill() -> ft.Control | None:
        if not record_running:
            return None
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text("REC", size=FONT_XS, color=ft.Colors.WHITE),
                    bgcolor=ACCENT_RED,
                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    border_radius=999,
                ),
                ft.Text(
                    running_job.status_message or "Recording…",
                    size=FONT_SM,
                    color=ft.Colors.WHITE,
                ),
            ],
            spacing=SPACE_SM,
            wrap=True,
        )

    def _stage_overlay() -> ft.Control | None:
        if watch_error is not None:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SIGNAL_WIFI_CONNECTED_NO_INTERNET_4, size=36, color=muted),
                        ft.Text(
                            watch_error,
                            size=FONT_SM,
                            color=ft.Colors.WHITE,
                            max_lines=3,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            controls=[
                                ft.OutlinedButton(
                                    "Retry", on_click=lambda _: page.run_task(_retry_watch)
                                ),
                                ft.TextButton("Dismiss", on_click=lambda _: set_stage_url(None)),
                            ],
                            spacing=SPACE_SM,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=SPACE_SM,
                ),
                bgcolor="#000000D9",
                alignment=ft.Alignment.CENTER,
                expand=True,
                padding=SPACE_MD,
            )
        if not players_ready and stage_url:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(width=36, height=36),
                        ft.Text("Loading stream…", size=FONT_SM, color=ft.Colors.WHITE),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=SPACE_SM,
                ),
                bgcolor="#00000099",
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        return None

    def _stage() -> ft.Control:
        if stage_url is None:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED, size=40, color=muted),
                        ft.Text(
                            "Paste a stream URL below — it plays here live",
                            size=FONT_SM,
                            color=muted,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=SPACE_SM,
                ),
                height=_STAGE_HEIGHT,
                alignment=ft.Alignment.CENTER,
                border_radius=RADIUS_LG,
                bgcolor=ft.Colors.BLACK,
            )
        player = video_ref.current
        body: ft.Control = (
            player
            if player is not None
            else ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE_OFF_OUTLINED, size=36, color=muted),
                        ft.Text(
                            "Live preview unavailable on this device — recording still works.",
                            size=FONT_SM,
                            color=muted,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=SPACE_SM,
                ),
                bgcolor=ft.Colors.BLACK,
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )
        overlay = _stage_overlay()
        pill = _rec_pill()
        return ft.Container(
            content=ft.Stack(
                controls=[
                    ft.Container(
                        content=body,
                        bgcolor=ft.Colors.BLACK,
                        border_radius=RADIUS_LG,
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        expand=True,
                    ),
                    *(
                        [
                            ft.Container(
                                content=overlay,
                                expand=True,
                            )
                        ]
                        if overlay is not None
                        else []
                    ),
                    *(
                        [
                            ft.Container(
                                content=pill,
                                alignment=ft.Alignment.BOTTOM_LEFT,
                                padding=SPACE_SM,
                            )
                        ]
                        if pill is not None
                        else []
                    ),
                ],
                expand=True,
            ),
            height=_STAGE_HEIGHT if not fullscreen else None,
            expand=bool(fullscreen),
            border_radius=RADIUS_LG,
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
            _stage(),
            # Recording controls live WITH the stage: stop is always the
            # user's decision, never the queue banner's to discover.
            *(
                [
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Stop & Keep Recording",
                                icon=ft.Icons.STOP_CIRCLE_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                bgcolor=ACCENT_RED,
                                height=48,
                                expand=True,
                                on_click=_stop,
                            ),
                        ]
                    )
                ]
                if record_running
                else [
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Start Recording",
                                icon=ft.Icons.FIBER_MANUAL_RECORD_ROUNDED,
                                height=48,
                                expand=True,
                                disabled=not url_ok or starting or blocked_on_cap,
                                on_click=_start,
                            ),
                            *(
                                [
                                    ft.OutlinedButton(
                                        "Reload",
                                        icon=ft.Icons.REFRESH_ROUNDED,
                                        height=48,
                                        disabled=not url_ok,
                                        tooltip="Reload the live stream",
                                        on_click=lambda _: page.run_task(_retry_watch),
                                    )
                                ]
                                if stage_url is not None
                                else []
                            ),
                        ],
                        spacing=SPACE_SM,
                    )
                ]
            ),
            section_header(
                "Stream Source",
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
                            on_submit=_watch,
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
                            "Watch plays the stream live. Start Recording keeps the "
                            "video rolling while it saves. Stop & Keep Recording is "
                            "yours to press — what was captured is kept and opens on "
                            "the result screen.",
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
