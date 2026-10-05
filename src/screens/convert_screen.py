"""Media conversion screen for container, codec, and quality transcoding."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.tool_job_status import tool_job_row
from core.notify import ERROR, show_snack
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
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
from services.engine_service import check_pair
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

_AUDIO_CODEC_CHOICES = (
    ("aac", "AAC"),
    ("mp3", "MP3"),
    ("flac", "FLAC"),
    ("opus", "Opus"),
    ("vorbis", "Vorbis"),
    ("wav", "WAV"),
)

# Display codec → probe encoder names it may resolve to (engine aliases).
_AUDIO_CHOICE_ENCODERS: dict[str, tuple[str, ...]] = {
    "aac": ("aac",),
    "mp3": ("libmp3lame", "mp3"),
    "flac": ("flac",),
    "opus": ("libopus", "opus"),
    "vorbis": ("vorbis",),
    "wav": ("pcm_s16le", "pcm_s24le"),
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
    # Alias-aware: an h264-only wheel (no libx264 entry) still offers H.264 —
    # the engine resolves libx264↔h264 itself.
    probe_info = app_state.probe_info
    available_video = list(probe_info.video_encoder_picks or []) if probe_info else []
    # Wheel-measured audio encoders (the video list above is curated∩verified;
    # audio comes straight from the probe — the old static tuple never met the
    # wheel and let AAC-in-.mp3-class mismatches through to mux time).
    available_audio = list(probe_info.audio_encoder_picks or []) if probe_info else []

    def _video_visible(key: str) -> bool:
        if key in available_video:
            return True
        return any(
            alias in available_video
            for alias in ({"libx264": ("h264",), "h264": ("libx264",)}.get(key, ()))
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
    visible_video = [(key, label) for key, label in video_choices if _video_visible(key)]

    # What kind of file the user picked. Selecting a still image and seeing
    # "playback speed / H.264 / 4K resolution" was the reported bug — the
    # controls are now per media kind, not hardwired to video.
    media_kind = info.kind if info is not None else "video"

    # State variables
    container_fmt, set_container_fmt = ft.use_state("mp4")
    v_codec, set_v_codec = ft.use_state("libx264")
    a_codec, set_a_codec = ft.use_state("aac")
    crf_val, set_crf_val = ft.use_state(23)
    res_choice, set_res_choice = ft.use_state("original")

    default_container = {"image": "png", "audio": "m4a", "video": "mp4"}.get(media_kind, "mp4")
    allowed_containers = _containers_for(media_kind)
    chosen_container = container_fmt if container_fmt in allowed_containers else default_container
    # Clamp the selection onto something this build can actually encode — the
    # default (libx264) is meaningless on a wheel that only ships LGPL codecs.
    # The clamp is DERIVED (not written back): the UI always shows the
    # effective value, so stale state can never silently resurrect.
    # Wheel-measured audio shortlist, shared by every kind branch below.
    visible_audio = [
        key
        for key, encs in _AUDIO_CHOICE_ENCODERS.items()
        if any(e in available_audio for e in encs)
    ]

    def _pick_audio() -> str | None:
        # Wheel default for the container wins (opus-for-webm-class cases),
        # then the user's pick if the wheel encodes it, else first verified.
        wheel_default = (
            (probe_info.muxer_default_audio.get(chosen_container, "") or "") if probe_info else ""
        )
        default_choice = next(
            (key for key, encs in _AUDIO_CHOICE_ENCODERS.items() if wheel_default in encs),
            "aac",
        )
        if a_codec in visible_audio:
            return a_codec
        if default_choice in visible_audio:
            return default_choice
        return visible_audio[0] if visible_audio else a_codec

    if media_kind == "image":
        still_choices = [c for c in ("png", "mjpeg", "libwebp", "gif") if c in available_video]
        chosen_video = (
            v_codec
            if v_codec in still_choices
            else (still_choices[0] if still_choices else v_codec)
        )
        chosen_audio = None
    elif media_kind == "audio":
        chosen_video = None
        chosen_audio = _pick_audio()
    else:
        chosen_video = (
            v_codec
            if _video_visible(v_codec)
            else (visible_video[0][0] if visible_video else v_codec)
        )
        chosen_audio = _pick_audio()

    # Probe state: None until the boot capability probe lands.  Starting a
    # job before that means guessing the encoder — the phone log showed
    # H.264-encode jobs failing on the LGPL wheel for exactly this reason.
    probing = app_state.probe_info is None

    # Container↔codec matrix: pairs the wheel's muxers reject (vp9+mp4,
    # aac-in-.mp3…) refuse BEFORE Start, not after a full encode.
    # check_params validates pix_fmt/fps against declared encoder facts —
    # with the ENCODER-FITTED pix_fmt (mjpeg-family rejects yuv420p, and the
    # engine fits per encoder since the still-image fix).
    from services.engine_service import _encoder_pix_fmt as _fit_pix_fmt
    from services.engine_service import check_params as _check_params

    pair_reason = (
        check_pair(chosen_container, chosen_video, chosen_audio)
        if not probing and media_path
        else None
    )
    params_reason = (
        _check_params(video_codec=chosen_video, pix_fmt=_fit_pix_fmt(chosen_video))
        if not probing and media_path and media_kind == "video" and chosen_video
        else None
    )
    start_blocked_reason = pair_reason or params_reason

    # Live pipeline: derived from the queue, never a stuck local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    busy = running_job is not None

    def show_snack_needs_probe() -> None:
        show_snack(
            page,
            "Still probing engine capabilities — try again in a moment.",
            bgcolor=ERROR,
        )

    def _start_conversion(_):
        if not media_path:
            return
        if busy:
            return
        if probing or not available_video:
            show_snack_needs_probe()
            return
        if start_blocked_reason is not None:
            show_snack(page, start_blocked_reason, bgcolor=ERROR)
            return

        # Aspect-correct scale: width-only scaling squished 3840x2160 into
        # 1920x2160. Both dims derive from the source aspect (portrait-safe).
        scale_w = None
        scale_h = None
        src_w = info.video_stream.width if info and info.video_stream else None
        src_h = info.video_stream.height if info and info.video_stream else None
        if res_choice != "original" and src_w and src_h:
            target_w = {"1080p": 1920, "720p": 1280, "480p": 854}[res_choice]
            if src_w > target_w:
                scale_w = target_w
                scale_h = max(2, (round(target_w * src_h / src_w) // 2) * 2)

        out_name = unique_temp_name(f"{Path(media_path).stem}_converted", chosen_container)
        out_path = str(get_temp_dir() / out_name)

        params: dict = {"container": chosen_container}
        if media_kind == "video":
            params.update(
                {
                    "video_codec": chosen_video,
                    "audio_codec": chosen_audio,
                    "crf": int(crf_val),
                    "scale_width": scale_w,
                    "scale_height": scale_h,
                }
            )
        elif media_kind == "audio":
            params.update({"audio_codec": chosen_audio})
        else:
            # Still image: the still encoder carries the transcode; no
            # video bitrate/scale params apply.
            params.update({"video_codec": chosen_video})

        job = Job(
            op="convert",
            input_path=media_path,
            output_path=out_path,
            params=params,
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

    audio_options = [
        ft.DropdownOption(key=key, text=label)
        for key, label in _AUDIO_CODEC_CHOICES
        if key in visible_audio
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
            # Live pipeline status (derived, never stuck)
            *([tool_job_row(running_job, ctrl, is_dark=is_dark)] if running_job else []),
            # Target Format Section
            section_header("Output Format", "Select destination container", is_dark=is_dark),
            ft.Dropdown(
                value=chosen_container,
                options=container_options,
                on_select=lambda e: set_container_fmt(e.control.value),
            ),
            # Audio codec picker (was hardcoded aac — AAC-in-.mp3 mismatched).
            *(
                [
                    section_header("Audio Codec", "Encoding algorithm", is_dark=is_dark),
                    ft.Dropdown(
                        value=chosen_audio,
                        options=audio_options,
                        on_select=lambda e: set_a_codec(e.control.value),
                    ),
                ]
                if media_kind in ("video", "audio")
                else []
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
                                        on_click=lambda _, code=key: set_v_codec(code),
                                    )
                                    for key, label in (
                                        visible_video
                                        if media_kind == "video"
                                        else [
                                            (still_key, still_label)
                                            for still_key, still_label in (
                                                ("png", "PNG"),
                                                ("mjpeg", "JPEG"),
                                                ("libwebp", "WebP"),
                                                ("gif", "GIF"),
                                            )
                                            if still_key in available_video
                                        ]
                                    )
                                ],
                                wrap=True,
                                spacing=SPACE_SM,
                            )
                        ]
                        if (visible_video if media_kind == "video" else True)
                        else [
                            card_container(
                                content=ft.Text(
                                    "This device's FFmpeg build has no still-image encoders.",
                                    size=FONT_SM,
                                    color=muted,
                                ),
                                padding=SPACE_MD,
                                border_radius=RADIUS_LG,
                                is_dark=is_dark,
                            )
                        ]
                    ),
                    # Quality & CRF (lossy codecs only — vacuous for
                    # lossless prores/ffv1/mjpeg, so hidden there).
                    *(
                        [
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
                        ]
                        if media_kind == "video"
                        and chosen_video not in ("prores", "ffv1", "mjpeg", "png", "gif", "libwebp")
                        else []
                    ),
                    # Resolution
                    *(
                        [
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
                ]
                if media_kind in ("video", "image")
                else []
            ),
            # Pair-matrix / param refusal (before Start, not after an encode).
            *(
                [
                    ft.Text(
                        start_blocked_reason,
                        size=FONT_SM,
                        color="#EF4444",
                    )
                ]
                if start_blocked_reason is not None
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
                disabled=not media_path
                or busy
                or probing
                or not available_video
                or start_blocked_reason is not None,
                on_click=_start_conversion,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
