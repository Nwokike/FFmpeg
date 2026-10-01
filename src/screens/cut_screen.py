"""Media trim and cut screen with stream-copy and re-encode modes."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import flet as ft

from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import ACCENT_AMBER, PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from services.engine_service import EngineService
from state.controller_ctx import use_controller

logger = logging.getLogger(__name__)

try:
    import flet_video as ftv

    _HAS_VIDEO = True
except ImportError:  # pragma: no cover
    _HAS_VIDEO = False


def _format_time_s(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 10)
    return f"{m:02d}:{s:02d}.{ms}"


@ft.component
def CutScreen() -> ft.Control:
    """Segment trimmer view supporting lossless copy and frame-accurate cutting."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = app_state.current_media_path
    info = app_state.current_media_info
    file_name = Path(media_path).name if media_path else "No file selected"
    file_size_str = (
        format_bytes(Path(media_path).stat().st_size)
        if media_path and Path(media_path).exists()
        else "0 B"
    )
    total_dur = max(1.0, info.duration_s if info and info.duration_s else 60.0)

    start_s, set_start_s = ft.use_state(0.0)
    end_s, set_end_s = ft.use_state(total_dur)

    # Keep the window clamped when the underlying media shrinks (file swap /
    # re-pick).  The observable write that feeds `info` rebuilds the whole
    # screen, so a stale `end_s > total_dur` would otherwise feed a
    # RangeSlider with `end_value > max` — a deterministic Dart range throw.
    def _clamp_window() -> None:
        cur = total_dur
        if start_s > cur:
            set_start_s(cur)
        if end_s > cur:
            set_end_s(cur)

    ft.use_effect(_clamp_window, [total_dur])
    stream_copy, set_stream_copy = ft.use_state(True)
    is_processing, set_is_processing = ft.use_state(False)
    thumbs, set_thumbs = ft.use_state([])
    keyframes, set_keyframes = ft.use_state([])
    strip_loaded, set_strip_loaded = ft.use_state(False)
    scrub_ready, set_scrub_ready = ft.use_state(False)
    scrub_ref = ft.use_ref(None)
    last_seek_ref = ft.use_ref(0.0)

    cut_duration = max(0.0, end_s - start_s)

    def _is_mounted(ctrl) -> bool:
        """True once Flet has attached the control to the page.

        The scrub Video is created inside a ``use_effect`` and rendered on the
        following pass, so seeking/pausing/stopping during that window raised
        ``Control must be added to the page first`` on every interaction. The
        gap is one frame, so the call is dropped rather than surfaced as an
        error — the next interaction lands on a mounted control.

        ``flet.controls.base_control.Control.page`` walks parents and **raises**
        RuntimeError instead of returning None, so ``getattr(ctrl, "page")``
        without an except RuntimeError still crashes the guard itself.
        """
        if ctrl is None:
            return False
        try:
            _ = ctrl.page  # type: ignore[attr-defined]
            return True
        except (RuntimeError, AttributeError):
            return False

    # ── Scrub preview: stable Video instance + throttled seeks ──────────────

    async def _seek_to(seconds: float) -> None:
        v = scrub_ref.current
        if not _is_mounted(v):
            return
        try:
            await v.seek(ft.Duration(milliseconds=int(seconds * 1000)))
        except Exception as exc:
            logger.warning("Scrub seek failed: %s", exc)

    def _scrub_to(seconds: float) -> None:
        now = time.monotonic()
        if now - last_seek_ref.current < 0.3:
            return
        last_seek_ref.current = now
        page.run_task(_seek_to, seconds)

    def _stop_scrub() -> None:
        v = scrub_ref.current
        scrub_ref.current = None  # media_path change must rebuild the scrubber
        if not _is_mounted(v):
            return

        async def _stop():
            try:
                await v.stop()
            except Exception as exc:
                logger.warning("Scrub stop failed: %s", exc)

        page.run_task(_stop)

    def _pause_scrub() -> None:
        v = scrub_ref.current
        if not _is_mounted(v):
            return

        async def _pause():
            try:
                await v.pause()
            except Exception as exc:
                logger.warning("Scrub pause failed: %s", exc)

        page.run_task(_pause)

    def _mount_scrub():
        if not media_path or not _HAS_VIDEO or scrub_ref.current is not None:
            return None
        try:
            scrub_ref.current = ftv.Video(
                playlist=[ftv.VideoMedia(media_path)],
                autoplay=False,
                # No chrome on a 160px scrubber — default controls cover the frame
                controls=None,
                filter_quality=ft.FilterQuality.MEDIUM,
                on_error=lambda e: logger.warning("Scrub preview error: %s", getattr(e, "data", e)),
            )
            set_scrub_ready(True)
        except Exception as exc:
            logger.warning("Scrub preview unavailable: %s", exc)
        return None

    async def _load_strip() -> None:
        try:
            times = [total_dur * (i + 1) / 7 for i in range(6)]
            imgs = await asyncio.to_thread(EngineService.thumbnail_strip, media_path, times)
            kfs = await asyncio.to_thread(EngineService.keyframe_times, media_path)
            set_thumbs(imgs)
            set_keyframes(kfs)
        except Exception as exc:
            logger.warning("Thumbnail strip failed: %s", exc)
        finally:
            set_strip_loaded(True)

    def _effect_strip():
        if not media_path:
            return None
        set_thumbs([])  # a new file must not keep showing the old file's frames
        set_keyframes([])
        set_strip_loaded(False)
        page.run_task(_load_strip)
        return None

    # media_path in deps: picking a new file tears down + rebuilds scrub & strip
    # (empty deps kept the previous file's player/frames forever)
    ft.use_effect(_mount_scrub, [media_path or ""], cleanup=_stop_scrub)
    ft.use_effect(_effect_strip, [media_path or ""])

    def _set_trim_range(lo: float, hi: float) -> None:
        """RangeSlider handler: keep an ordered, non-empty trim window."""
        a = max(0.0, min(lo, hi))
        b = min(float(total_dur), max(lo, hi))
        if b - a < 0.05:
            return
        set_start_s(a)
        set_end_s(b)
        _scrub_to(a)

    def _start_cut(_):
        if not media_path or cut_duration <= 0.05:
            return
        # Frame-accurate re-encode needs a verified encoder; stream-copy
        # needs none.  Gate only the re-encode path on the probe.
        if not stream_copy and app_state.probe_info is None:
            from core.notify import ERROR, show_snack

            show_snack(
                page,
                "Still probing engine capabilities — try again in a moment.",
                bgcolor=ERROR,
            )
            return
        set_is_processing(True)
        _pause_scrub()  # the encode needs the CPU the preview would otherwise burn

        ext = Path(media_path).suffix or ".mp4"
        out_name = f"{Path(media_path).stem}_trimmed{ext}"
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="cut",
            input_path=media_path,
            output_path=out_path,
            params={
                "start_seconds": float(start_s),
                "end_seconds": float(end_s),
                "stream_copy": bool(stream_copy),
            },
            original_size_bytes=Path(media_path).stat().st_size if Path(media_path).exists() else 0,
        )
        ctrl.start_job(job)

    return ft.ListView(
        controls=[
            # Header
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Trim & Cut Segment", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CONTENT_CUT_ROUNDED, size=32, color=ACCENT_AMBER),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"Total Duration: {_format_time_s(total_dur)} • {file_size_str}",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton("Change", on_click=lambda _: ctrl.pick_media_for("cut")),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Trim boundaries display
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "START TIME",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(start_s), size=FONT_LG, weight=ft.FontWeight.BOLD
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "CLIP LENGTH",
                                    size=FONT_XS,
                                    color=PRIMARY,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(cut_duration),
                                    size=FONT_LG,
                                    weight=ft.FontWeight.BOLD,
                                    color=PRIMARY,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=2,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "END TIME",
                                    size=FONT_XS,
                                    color=muted,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    _format_time_s(end_s), size=FONT_LG, weight=ft.FontWeight.BOLD
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                            spacing=2,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                is_dark=is_dark,
            ),
            # Live scrub preview of the source — seeks as the range moves
            ft.Container(
                content=(
                    scrub_ref.current
                    if scrub_ready and scrub_ref.current is not None
                    else ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.ProgressRing(width=20, height=20),
                                ft.Text(
                                    "Loading preview…"
                                    if _HAS_VIDEO
                                    else "Preview unavailable on this platform",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=SPACE_SM,
                        ),
                        alignment=ft.Alignment.CENTER,
                        expand=True,
                    )
                ),
                height=160,
                border_radius=RADIUS_LG,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#000000",
            ),
            # Trim range — one RangeSlider keeps start <= end by construction
            # (the old interlinked Slider pair misbehaved on sub-second clips)
            section_header(
                "Trim Range",
                f"{_format_time_s(start_s)} → {_format_time_s(end_s)}",
                is_dark=is_dark,
            ),
            ft.RangeSlider(
                min=0.0,
                max=float(max(total_dur, 0.5)),
                start_value=float(start_s),
                end_value=float(end_s),
                divisions=100,
                on_change=lambda e: _set_trim_range(
                    round(float(e.control.start_value), 2),
                    round(float(e.control.end_value), 2),
                ),
            ),
            # Thumbnail strip + instant-cut keyframe jumps
            section_header("Timeline", "Frames & instant-cut points", is_dark=is_dark),
            *(
                [
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Image(src=img, fit=ft.BoxFit.COVER),
                                height=52,
                                expand=True,
                                border_radius=6,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            )
                            for img in thumbs
                        ],
                        spacing=4,
                    )
                ]
                if thumbs
                else [
                    ft.Text(
                        "Building thumbnails…" if not strip_loaded else "Thumbnails unavailable",
                        size=FONT_SM,
                        color=muted,
                    )
                ]
            ),
            *(
                [
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text(_format_time_s(kf)),
                                selected=False,
                                on_select=lambda _, t=kf: _scrub_to(t),
                                tooltip="Preview this cut point",
                            )
                            for kf in (
                                keyframes
                                if len(keyframes) <= 12
                                else keyframes[:: (len(keyframes) + 11) // 12][:12]
                            )
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    ),
                    ft.Text(
                        f"◆ {len(keyframes)} keyframes — instant (stream-copy) cuts snap to these",
                        size=FONT_XS,
                        color=muted,
                    ),
                ]
                if keyframes
                else []
            ),
            # Mode toggle
            section_header("Processing Mode", "Cutting method", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text("Stream Copy (Instant Lossless)"),
                        selected=stream_copy,
                        on_select=lambda _: set_stream_copy(True),
                    ),
                    ft.Chip(
                        label=ft.Text("Re-encode (Frame-Accurate)"),
                        selected=not stream_copy,
                        on_select=lambda _: set_stream_copy(False),
                    ),
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Action button
            ft.FilledButton(
                f"Cut Segment ({_format_time_s(cut_duration)})",
                icon=ft.Icons.CONTENT_CUT_ROUNDED,
                height=48,
                disabled=not media_path
                or is_processing
                or cut_duration <= 0.05
                or (not stream_copy and app_state.probe_info is None),
                on_click=_start_cut,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
