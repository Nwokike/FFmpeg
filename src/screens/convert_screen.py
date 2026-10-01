"""Media conversion screen for container, codec, and quality transcoding."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from core.notify import ERROR, show_snack
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    RADIUS_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller

_VIDEO_CONTAINERS = ("mp4", "mkv", "mov", "webm", "avi")
_AUDIO_CONTAINERS = ("mp3", "m4a", "flac", "wav")
_IMAGE_CONTAINERS = ("jpg", "png", "webp")


def _containers_for(kind: str) -> tuple[str, ...]:
    """Output containers that make sense for the kind of file being converted."""
    return {
        "image": _IMAGE_CONTAINERS,
        "audio": _AUDIO_CONTAINERS,
        "video": _VIDEO_CONTAINERS,
    }.get(kind, _VIDEO_CONTAINERS)


_CONTAINER_LABELS = {
    "mp4": "MP4 (Universal standard)",
    "mkv": "MKV (Matroska container)",
    "mov": "MOV (QuickTime / Apple)",
    "webm": "WebM (Open web video)",
    "avi": "AVI (Legacy container)",
    "mp3": "MP3 (Audio only)",
    "m4a": "M4A (AAC Audio)",
    "flac": "FLAC (Lossless audio)",
    "wav": "WAV (PCM audio)",
    "jpg": "JPEG (Lossy image)",
    "png": "PNG (Lossless image)",
    "webp": "WebP (Modern image)",
}


@ft.component
def ConvertScreen() -> ft.Control:
    """Format and codec conversion view with interactive presets and settings."""
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

    # Codec choices are shown only when the INSTALLED wheel verified them as a
    # mode='w' encoder. Hardcoding libx264/libx265/vp9 is what let a tap reach
    # add_stream() and crash on Android's LGPL build with UnknownCodecError.
    available_video = (
        list(app_state.probe_info.video_encoder_picks or []) if app_state.probe_info else []
    )
    video_choices = [
        ("libx264", "H.264 (libx264)"),
        ("libx265", "H.265 (HEVC)"),
        ("libsvtav1", "AV1 (SVT)"),
        ("vp9", "VP9"),
        ("mpeg4", "MPEG-4"),
        ("mjpeg", "MJPEG"),
        ("prores", "ProRes"),
        ("ffv1", "FFV1 (lossless)"),
    ]
    visible_video = [(key, label) for key, label in video_choices if key in available_video]

    # What kind of file the user picked. Selecting a still image and seeing
    # "playback speed / H.264 / 4K resolution" was the reported bug — the
    # controls are now per media kind, not hardwired to video.
    media_kind = info.kind if info is not None else "video"

    # State variables
    container_fmt, set_container_fmt = ft.use_state("mp4")
    v_codec, set_v_codec = ft.use_state("libx264")
    a_codec, _set_a_codec = ft.use_state("aac")
    crf_val, set_crf_val = ft.use_state(23)
    res_choice, set_res_choice = ft.use_state("original")
    is_processing, set_is_processing = ft.use_state(False)

    # Clamp the selection onto something this build can actually encode — the
    # default (libx264) is meaningless on a wheel that only ships LGPL codecs.
    chosen_video = (
        v_codec
        if v_codec in available_video
        else (available_video[0] if available_video else v_codec)
    )
    default_container = {"image": "png", "audio": "m4a", "video": "mp4"}.get(media_kind, "mp4")
    allowed_containers = _containers_for(media_kind)
    chosen_container = container_fmt if container_fmt in allowed_containers else default_container

    # Probe state: None until the boot capability probe lands.  Starting a
    # job before that means guessing the encoder — the phone log showed
    # H.264-encode jobs failing on the LGPL wheel for exactly this reason.
    probing = app_state.probe_info is None

    def show_snack_needs_probe() -> None:
        show_snack(
            page,
            "Still probing engine capabilities — try again in a moment.",
            bgcolor=ERROR,
        )

    def _start_conversion(_):
        if not media_path:
            return
        if probing or not available_video:
            show_snack_needs_probe()
            return
        set_is_processing(True)

        scale_w = None
        scale_h = None
        if res_choice == "1080p":
            scale_w = 1920
        elif res_choice == "720p":
            scale_w = 1280
        elif res_choice == "480p":
            scale_w = 854

        out_name = f"{Path(media_path).stem}_converted.{chosen_container}"
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="convert",
            input_path=media_path,
            output_path=out_path,
            params={
                "container": chosen_container,
                "video_codec": chosen_video,
                "audio_codec": a_codec,
                "crf": int(crf_val),
                "scale_width": scale_w,
                "scale_height": scale_h,
            },
            original_size_bytes=Path(media_path).stat().st_size if Path(media_path).exists() else 0,
        )
        ctrl.start_job(job)

    # Resolution mapping
    res_options = [
        ft.DropdownOption(key="original", text="Original Resolution"),
        ft.DropdownOption(key="1080p", text="1080p Full HD (1920x1080)"),
        ft.DropdownOption(key="720p", text="720p HD (1280x720)"),
        ft.DropdownOption(key="480p", text="480p SD (854x480)"),
    ]

    container_options = [
        ft.DropdownOption(key=key, text=_CONTAINER_LABELS.get(key, key.upper()))
        for key in allowed_containers
    ]

    return ft.ListView(
        controls=[
            # Header with back button
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Convert Media", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview card
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.VIDEO_FILE_ROUNDED, size=32, color=PRIMARY),
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
                                    f"Size: {file_size_str} • {info.duration_s:.1f}s"
                                    if info
                                    else f"Size: {file_size_str}",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            "Change", on_click=lambda _: ctrl.pick_media_for("convert")
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Target Format Section
            section_header("Output Format", "Select destination container", is_dark=is_dark),
            ft.Dropdown(
                value=chosen_container,
                options=container_options,
                on_select=lambda e: set_container_fmt(e.control.value),
            ),
            # Video-only sections — never shown for a still image or a pure
            # audio file (reported bug: an image showed H.264/4K controls).
            *(
                [
                    # Video Codec Chips — populated from the measured encoder set.
                    section_header("Video Codec", "Encoding algorithm", is_dark=is_dark),
                    *(
                        [
                            ft.Row(
                                controls=[
                                    ft.Chip(
                                        label=ft.Text(label),
                                        selected=chosen_video == key,
                                        on_select=lambda _, k=key: set_v_codec(k),
                                    )
                                    for key, label in visible_video
                                ],
                                wrap=True,
                                spacing=SPACE_SM,
                            )
                        ]
                        if visible_video
                        else [
                            card_container(
                                content=ft.Text(
                                    "This device's FFmpeg build has no video encoders, "
                                    "so it can copy media but cannot re-encode it.",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                                padding=SPACE_MD,
                                border_radius=RADIUS_LG,
                                is_dark=is_dark,
                            )
                        ]
                    ),
                    # Quality & CRF
                    section_header(
                        "Compression Quality",
                        f"Constant Rate Factor: {crf_val} (Lower is higher quality)",
                        is_dark=is_dark,
                    ),
                    ft.Slider(
                        value=float(crf_val),
                        min=15,
                        max=35,
                        divisions=20,
                        on_change=lambda e: set_crf_val(int(e.control.value)),
                    ),
                    # Resolution
                    section_header(
                        "Output Resolution", "Optionally downscale video", is_dark=is_dark
                    ),
                    ft.Dropdown(
                        value=res_choice,
                        options=res_options,
                        on_select=lambda e: set_res_choice(e.control.value),
                    ),
                ]
                if media_kind == "video"
                else []
            ),
            # Action Button — gated on the probe so Start can never fire with
            # a guessed (possibly unencodable) default codec.
            *(
                [
                    ft.Row(
                        controls=[
                            ft.ProgressRing(width=22, height=22),
                            ft.Text(
                                "Probing engine capabilities…",
                                size=FONT_SM,
                                color=muted,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=SPACE_SM,
                    )
                ]
                if probing
                else []
            ),
            ft.FilledButton(
                "Start Conversion",
                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                height=48,
                disabled=not media_path or is_processing or probing or not available_video,
                on_click=_start_conversion,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
