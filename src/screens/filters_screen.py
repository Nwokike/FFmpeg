"""Video and audio filter stack screen (speed, volume, rotate, crop, EQ, denoise, watermark).

Every presence-sensitive control is gated on this build's compiled-in filters
(loaded once via ``available_filters()``): a missing filter degrades to a note
naming it instead of failing mid-job.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import flet as ft

from components.tool_job_status import tool_job_row
from core.notify import ERROR, show_snack
from core.state import Job, use_app_state
from core.storage_paths import cache_bytes, format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header
from core.theme import ACCENT_PURPLE, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from services.engine_service import available_filters
from services.media_io import picker_files
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)

_CROP_ASPECTS = ("original", "16:9", "1:1", "4:5")
_DENOISE_LEVELS = ("off", "low", "high")
_WM_POSITIONS = ("br", "bl", "tl", "tr", "center")


@ft.component
def FiltersScreen() -> ft.Control:
    """Filter adjustments: speed/tempo, gain, rotation, crop, EQ, denoise, watermark."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
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

    speed_val, set_speed_val = ft.use_state(1.0)
    volume_pct, set_volume_pct = ft.use_state(100)
    rotation_deg, set_rotation_deg = ft.use_state(0)
    crop, set_crop = ft.use_state("original")
    scale, set_scale = ft.use_state("original")  # original | 480p | 720p
    brightness, set_brightness = ft.use_state(0.0)
    contrast, set_contrast = ft.use_state(1.0)
    saturation, set_saturation = ft.use_state(1.0)
    denoise, set_denoise = ft.use_state("off")
    sharpen, set_sharpen = ft.use_state(0)
    wm_path, set_wm_path = ft.use_state(None)
    wm_pos, set_wm_pos = ft.use_state("br")
    wm_pct, set_wm_pct = ft.use_state(20)
    # Tri-state: None = loading (skeleton), set() = loaded, _LOAD_FAILED =
    # enumeration threw (conservative gating + warning banner). The old
    # empty-set start rendered every gate OPEN, so EQ flashed then collapsed
    # on every visit — and a load failure left everything silently no-op.
    avail, set_avail = ft.use_state(None)
    _LOAD_FAILED = "load-failed"

    speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    rotations = [(0, "Normal"), (90, "90° CW"), (180, "180°"), (270, "270° CW")]

    async def _load_avail() -> None:
        try:
            names = await asyncio.to_thread(available_filters)
            set_avail(frozenset(names))
        except Exception as exc:
            logger.warning("Filter availability load failed: %s", exc)
            set_avail(frozenset({_LOAD_FAILED}))

    ft.use_effect(lambda: page.run_task(_load_avail), [])

    def _missing(*names: str) -> bool:
        """True when a named filter is absent. Loading → False ONLY after a
        successful load; a failed enumeration gates everything (conservative)
        instead of rendering controls that silently do nothing."""
        if avail is None:
            return False
        if _LOAD_FAILED in avail:
            return True
        return any(n not in avail for n in names)

    def _denoise_backend() -> str:
        if avail is None:
            return "checking…"
        for candidate in ("hqdn3d", "nlmeans", "atadenoise"):
            if candidate in avail:
                return candidate
        return "unavailable"

    def _note(filter_label: str) -> ft.Control:
        return ft.Text(
            f"“{filter_label}” isn't compiled into this FFmpeg build — feature hidden.",
            size=FONT_XS,
            color=muted,
        )

    async def _pick_wm(_=None) -> None:
        try:
            res = await services.media_io.file_picker.pick_files(
                dialog_title="Choose watermark image",
                file_type=ft.FilePickerFileType.IMAGE,
                allow_multiple=False,
                with_data=True,
            )
            files = picker_files(res)
            if not files:
                return
            picked = files[0]
            if picked.path and Path(picked.path).exists():  # noqa: ASYNC240 — trivial stat/exists check
                set_wm_path(picked.path)
            elif picked.bytes:
                dest = cache_bytes(picked.name, picked.bytes)
                set_wm_path(str(dest))
            else:
                show_snack(page, "Couldn't read that image", bgcolor=ERROR)
        except Exception as exc:
            logger.warning("Watermark pick failed: %s", exc)
            show_snack(page, f"Image pick failed: {exc}", bgcolor=ERROR)

    def _scale_dims() -> tuple[int | None, int | None]:
        if scale == "original" or info is None or info.video_stream is None:
            return None, None
        vw = info.video_stream.width or 0
        vh = info.video_stream.height or 0
        if not vw or not vh:
            return None, None
        target_h = 480 if scale == "480p" else 720
        if vh <= target_h:
            return None, None
        w = int(vw * target_h / vh)
        return (w // 2) * 2, (target_h // 2) * 2

    # Live pipeline: derived from the queue, never a stuck local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    busy = running_job is not None

    def _start_filters(_):
        if not media_path or busy:
            return

        stem = Path(media_path).stem
        ext = Path(media_path).suffix or ".mp4"
        out_name = unique_temp_name(f"{stem}_filtered", ext)
        out_path = str(get_temp_dir() / out_name)
        scale_w, scale_h = _scale_dims()

        # Prune gated-off params before building the Job: the engine silently
        # ignores a missing filter's params, so an unpruned job SUCCEEDS but
        # does nothing — the history would lie about what ran.
        eq_params = (
            {
                "brightness": float(brightness),
                "contrast": float(contrast),
                "saturation": float(saturation),
            }
            if not _missing("eq")
            and (
                abs(brightness) > 1e-6 or abs(contrast - 1.0) > 1e-6 or abs(saturation - 1.0) > 1e-6
            )
            else None
        )
        denoise_value = (
            denoise
            if denoise == "off" or _denoise_backend() in ("hqdn3d", "nlmeans", "atadenoise")
            else "off"
        )
        sharpen_value = int(sharpen) if not _missing("unsharp") else 0
        watermark_value = (
            {"path": wm_path, "position": wm_pos, "width_pct": int(wm_pct)}
            if wm_path and not _missing("movie", "overlay")
            else None
        )

        try:
            file_bytes = Path(media_path).stat().st_size if Path(media_path).exists() else 0
        except OSError:
            file_bytes = 0
        job = Job(
            op="convert",
            input_path=media_path,
            output_path=out_path,
            params={
                "speed": float(speed_val),
                "volume_pct": int(volume_pct),
                "rotation": int(rotation_deg),
                "crop": crop if crop != "original" else None,
                "scale_width": scale_w,
                "scale_height": scale_h,
                "eq": eq_params,
                "denoise": denoise_value,
                "sharpen": sharpen_value,
                "watermark": watermark_value,
            },
            original_size_bytes=file_bytes,
        )
        try:
            ctrl.start_job(job)
        except Exception as exc:
            logger.warning("Filter job start failed: %s", exc)
            show_snack(page, f"Couldn't start: {exc}", bgcolor=ERROR)

    media_kind = info.kind if info is not None else "video"
    header = ft.Row(
        controls=[
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK_ROUNDED,
                on_click=lambda _: ctrl.navigate("dashboard"),
                tooltip="Back to Dashboard",
            ),
            ft.Text("Media Filter Stack", size=FONT_LG, weight=ft.FontWeight.BOLD),
        ],
        spacing=SPACE_SM,
    )
    file_card = card_container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.TUNE_ROUNDED, size=32, color=ACCENT_PURPLE),
                ft.Column(
                    controls=[
                        ft.Text(
                            file_name,
                            size=FONT_MD,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(f"Size: {file_size_str}", size=FONT_SM, color=muted),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.OutlinedButton("Change", on_click=lambda _: ctrl.pick_media_for("filters")),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=SPACE_MD,
        border_radius=RADIUS_LG,
        is_dark=is_dark,
    )

    if media_kind != "video":
        # Every control below is video-only (speed/rotation/scale/overlay).
        # Offering them for a still image or an audio file was the reported
        # bug — say so instead of rendering controls that do nothing.
        kind_label = {"image": "an image", "audio": "an audio file"}.get(media_kind, "this file")
        return ft.ListView(
            controls=[
                header,
                file_card,
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=28, color=muted),
                            ft.Text(
                                "Video filters aren't available here",
                                size=FONT_MD,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                f"{kind_label.capitalize()} has no playback speed, "
                                "rotation, crop or video denoise to change. "
                                "Use Audio Studio for audio, or Extract for still frames.",
                                size=FONT_SM,
                                color=muted,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=SPACE_SM,
                    ),
                    padding=SPACE_MD,
                    border_radius=RADIUS_LG,
                    is_dark=is_dark,
                ),
                ft.FilledButton(
                    "Pick a video instead",
                    icon=ft.Icons.VIDEO_LIBRARY_OUTLINED,
                    height=48,
                    on_click=lambda _: ctrl.pick_media_for("filters"),
                ),
            ],
            spacing=SPACE_MD,
            expand=True,
        )

    return ft.ListView(
        controls=[
            header,
            file_card,
            # Live pipeline status (derived, never stuck)
            *([tool_job_row(running_job, ctrl, is_dark=is_dark)] if running_job else []),
            # Availability warning (failed enumeration gates conservatively).
            *(
                [
                    card_container(
                        content=ft.Text(
                            "Filter list couldn't load — controls are gated off "
                            "until it does, so nothing renders a no-op job.",
                            size=FONT_XS,
                            color=muted,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_LG,
                        is_dark=is_dark,
                    )
                ]
                if avail is not None and _LOAD_FAILED in avail
                else []
            ),
            # Speed / Tempo
            section_header("Playback Speed", f"{speed_val}x playback multiplier", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(f"{s}x"),
                        selected=abs(speed_val - s) < 0.05,
                        on_select=lambda _, sp=s: set_speed_val(sp),
                    )
                    for s in speeds
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Volume Boost
            section_header(
                "Audio Volume Boost", f"{volume_pct}% (100% is normal volume)", is_dark=is_dark
            ),
            ft.Slider(
                value=float(volume_pct),
                min=0,
                max=250,
                divisions=25,
                on_change=lambda e: set_volume_pct(int(e.control.value)),
            ),
            # Orientation / Rotate
            section_header("Video Rotation", "Rotate video frame", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(lbl),
                        selected=rotation_deg == deg,
                        on_select=lambda _, d=deg: set_rotation_deg(d),
                    )
                    for deg, lbl in rotations
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Crop (gated: crop filter)
            section_header("Crop", "Center-crop to an aspect ratio", is_dark=is_dark),
            *(
                [
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text(a.upper() if a == "original" else a),
                                selected=crop == a,
                                on_select=lambda _, v=a: set_crop(v),
                            )
                            for a in _CROP_ASPECTS
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    )
                ]
                if not _missing("crop")
                else [_note("crop")]
            ),
            # Scale (reuses convert's reformat path — no filter needed)
            section_header("Scale Down", "Even-dimension downscale", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(label),
                        selected=scale == value,
                        on_select=lambda _, v=value: set_scale(v),
                    )
                    for value, label in (
                        ("original", "Original"),
                        ("480p", "480p"),
                        ("720p", "720p"),
                    )
                ],
                spacing=SPACE_SM,
            ),
            # EQ (gated: eq filter — compiled out of this build)
            section_header("Color EQ", "Brightness · contrast · saturation", is_dark=is_dark),
            *(
                [
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        width=90,
                                        content=ft.Text("Brightness", size=FONT_SM),
                                    ),
                                    ft.Slider(
                                        value=float(brightness),
                                        min=-0.5,
                                        max=0.5,
                                        divisions=20,
                                        expand=True,
                                        on_change=lambda e: set_brightness(
                                            round(float(e.control.value), 3)
                                        ),
                                    ),
                                ],
                                spacing=SPACE_SM,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        width=90, content=ft.Text("Contrast", size=FONT_SM)
                                    ),
                                    ft.Slider(
                                        value=float(contrast),
                                        min=0.5,
                                        max=1.5,
                                        divisions=20,
                                        expand=True,
                                        on_change=lambda e: set_contrast(
                                            round(float(e.control.value), 3)
                                        ),
                                    ),
                                ],
                                spacing=SPACE_SM,
                            ),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        width=90, content=ft.Text("Saturation", size=FONT_SM)
                                    ),
                                    ft.Slider(
                                        value=float(saturation),
                                        min=0.0,
                                        max=2.0,
                                        divisions=20,
                                        expand=True,
                                        on_change=lambda e: set_saturation(
                                            round(float(e.control.value), 3)
                                        ),
                                    ),
                                ],
                                spacing=SPACE_SM,
                            ),
                        ],
                        spacing=SPACE_SM,
                    )
                ]
                if not _missing("eq")
                else [_note("eq")]
            ),
            # Denoise (gated: hqdn3d > nlmeans > atadenoise)
            section_header(
                "Denoise",
                f"Backend: {_denoise_backend()}" if avail is not None else "Checking filters…",
                is_dark=is_dark,
            ),
            *(
                [
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text(level.title()),
                                selected=denoise == level,
                                on_select=lambda _, v=level: set_denoise(v),
                            )
                            for level in _DENOISE_LEVELS
                        ],
                        spacing=SPACE_SM,
                    )
                ]
                if avail is None or _denoise_backend() != "unavailable"
                else [_note("hqdn3d/nlmeans/atadenoise")]
            ),
            # Sharpen (gated: unsharp)
            section_header("Sharpen", f"Amount {sharpen}%" if sharpen else "Off", is_dark=is_dark),
            *(
                [
                    ft.Slider(
                        value=float(sharpen),
                        min=0,
                        max=100,
                        divisions=20,
                        on_change=lambda e: set_sharpen(int(e.control.value)),
                    )
                ]
                if not _missing("unsharp")
                else [_note("unsharp")]
            ),
            # Watermark (gated: movie + overlay)
            section_header("Watermark", "Overlay a PNG on every frame", is_dark=is_dark),
            *(
                [
                    card_container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.IMAGE_ROUNDED, size=24, color=ACCENT_PURPLE
                                        ),
                                        ft.Text(
                                            Path(wm_path).name if wm_path else "No image chosen",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                            expand=True,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.OutlinedButton(
                                            "Choose PNG",
                                            on_click=lambda _: page.run_task(_pick_wm),
                                        ),
                                        *(
                                            [
                                                ft.TextButton(
                                                    "Clear", on_click=lambda _: set_wm_path(None)
                                                )
                                            ]
                                            if wm_path
                                            else []
                                        ),
                                    ],
                                    spacing=SPACE_SM,
                                ),
                                *(
                                    [
                                        ft.Row(
                                            controls=[
                                                ft.Text("Position", size=FONT_SM),
                                                *[
                                                    ft.Chip(
                                                        label=ft.Text(
                                                            {
                                                                "br": "Bottom Right",
                                                                "bl": "Bottom Left",
                                                                "tl": "Top Left",
                                                                "tr": "Top Right",
                                                                "center": "Center",
                                                            }[p]
                                                        ),
                                                        selected=wm_pos == p,
                                                        on_select=lambda _, v=p: set_wm_pos(v),
                                                    )
                                                    for p in _WM_POSITIONS
                                                ],
                                            ],
                                            wrap=True,
                                            spacing=SPACE_SM,
                                        ),
                                        ft.Row(
                                            controls=[
                                                ft.Text(f"Width {wm_pct}%", size=FONT_SM),
                                                ft.Slider(
                                                    value=float(wm_pct),
                                                    min=5,
                                                    max=40,
                                                    divisions=7,
                                                    expand=True,
                                                    on_change=lambda e: set_wm_pct(
                                                        int(e.control.value)
                                                    ),
                                                ),
                                            ],
                                            spacing=SPACE_SM,
                                        ),
                                    ]
                                    if wm_path
                                    else []
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_LG,
                        is_dark=is_dark,
                    )
                ]
                if not _missing("movie", "overlay")
                else [_note("movie/overlay")]
            ),
            # Action button
            ft.FilledButton(
                "Apply Filters & Render",
                icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED,
                height=48,
                disabled=not media_path or busy or avail is None,
                on_click=_start_filters,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
