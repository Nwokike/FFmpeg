"""Audio Studio screen for loudness normalization, resampling, and channel mixing."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.tool_job_status import tool_job_row
from core.engine_probe import can_encode_format
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller

_LOUDNESS_CHOICES = (
    ("off", "Off (passthrough)", None),
    ("youtube", "YouTube / Music (-14 LUFS)", -14.0),
    ("podcast", "Podcast / Vocal (-16 LUFS)", -16.0),
    ("broadcast", "Broadcast (-23 LUFS)", -23.0),
)

_BITRATE_CHOICES = (
    ("Opus/AAC 128k", 128),
    ("Standard 192k", 192),
    ("High 256k", 256),
    ("Max 320k", 320),
)


@ft.component
def AudioScreen() -> ft.Control:
    """Audio post-production studio: loudness targets, bitrates, and acoustic routing."""
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
    # Audio Studio needs an audio timeline: images and muted video are
    # refused with an explanation (the engine raised ValueError in a
    # background job before).
    media_kind = info.kind if info is not None else "video"
    has_audio = info.audio_stream is not None if info is not None else True
    audio_ok = has_audio or media_kind == "video"

    loudness_key, set_loudness_key = ft.use_state("podcast")
    channel_layout, set_channel_layout = ft.use_state("stereo")
    sample_rate, set_sample_rate = ft.use_state(48000)
    audio_format, set_audio_format = ft.use_state("m4a")
    bitrate_key, set_bitrate_key = ft.use_state("Standard 192k")

    # Live pipeline: derived from the queue, never a stuck local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    busy = running_job is not None

    # Output formats are measured against the installed wheel. The Android
    # LGPL build has no MP3 encoder, so "mp3" used to fail only after the user
    # pressed Process & Master.
    audio_formats = [
        f for f in ("m4a", "mp3", "aac", "flac", "opus", "ogg", "wav") if can_encode_format(f)
    ]
    # DERIVED (not written back): the UI always shows the effective value.
    chosen_audio_format = (
        audio_format
        if audio_format in audio_formats
        else (audio_formats[0] if audio_formats else audio_format)
    )
    lossless_audio = chosen_audio_format in ("wav", "flac")
    lufs_target = next((v for k, _, v in _LOUDNESS_CHOICES if k == loudness_key), -16.0)
    bitrate_kbps = next((v for k, v in _BITRATE_CHOICES if k == bitrate_key), 192)

    rates = [48000, 44100, 32000]

    def _start_audio_studio(_):
        if not media_path or busy or not audio_ok:
            return

        stem = Path(media_path).stem
        out_name = unique_temp_name(f"{stem}_mastered", chosen_audio_format)
        out_path = str(get_temp_dir() / out_name)

        job = Job(
            op="extract_audio",
            input_path=media_path,
            output_path=out_path,
            params={
                "format_name": chosen_audio_format,
                "bitrate_kbps": int(bitrate_kbps),
                **({"target_lufs": float(lufs_target)} if lufs_target is not None else {}),
                "channels": 2 if channel_layout == "stereo" else 1,
                "sample_rate": int(sample_rate),
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
                    ft.Text("Audio Studio & Mastering", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            # Input file overview
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.GRAPHIC_EQ_ROUNDED, size=32, color=PRIMARY),
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
                        ft.OutlinedButton(
                            "Change", on_click=lambda _: ctrl.pick_media_for("audio")
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
            # Kind gate: no audio timeline, no mastering.
            *(
                [
                    card_container(
                        content=ft.Text(
                            "This file has no audio track — mastering needs sound. "
                            "Pick a video or audio file to continue.",
                            size=FONT_SM,
                            color=muted,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_LG,
                        is_dark=is_dark,
                    )
                ]
                if media_path and not audio_ok
                else []
            ),
            # Loudness Normalization Presets (Off = single-pass, no loudnorm
            # filter needed — every job used to pay the two-pass cost).
            section_header(
                "Loudness Normalization",
                "Target integrated loudness (Off skips the measure pass)",
                is_dark=is_dark,
            ),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(label),
                        selected=loudness_key == key,
                        on_click=lambda _, k=key: set_loudness_key(k),
                    )
                    for key, label, _ in _LOUDNESS_CHOICES
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Channel Routing
            section_header("Channel Routing", "Acoustic layout", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text("Stereo (2 Channels)"),
                        selected=channel_layout == "stereo",
                        on_click=lambda _: set_channel_layout("stereo"),
                    ),
                    ft.Chip(
                        label=ft.Text("Mono (1 Channel)"),
                        selected=channel_layout == "mono",
                        on_click=lambda _: set_channel_layout("mono"),
                    ),
                ],
                spacing=SPACE_SM,
            ),
            # Sample Rate
            section_header("Sample Rate", "Digital frequency", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(f"{r // 1000} kHz"),
                        selected=sample_rate == r,
                        on_click=lambda _, rate=r: set_sample_rate(rate),
                    )
                    for r in rates
                ],
                spacing=SPACE_SM,
            ),
            # Output Format
            section_header("Output Format", "Container / codec target", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(fmt.upper() if fmt != "m4a" else "M4A (AAC)"),
                        selected=chosen_audio_format == fmt,
                        on_click=lambda _, f=fmt: set_audio_format(f),
                    )
                    for fmt in audio_formats
                ],
                wrap=True,
                spacing=SPACE_SM,
            ),
            # Bitrate (lossy only — WAV ignores it, FLAC treats it as a hint).
            *(
                [
                    section_header("Bitrate", "Target for lossy codecs", is_dark=is_dark),
                    ft.Row(
                        controls=[
                            ft.Chip(
                                label=ft.Text(label),
                                selected=bitrate_key == label,
                                on_click=lambda _, name=label: set_bitrate_key(name),
                            )
                            for label, _ in _BITRATE_CHOICES
                        ],
                        wrap=True,
                        spacing=SPACE_SM,
                    ),
                ]
                if not lossless_audio
                else []
            ),
            # Action button
            ft.FilledButton(
                "Process & Master Audio",
                icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                height=48,
                disabled=not media_path or busy or not audio_ok or not audio_formats,
                on_click=_start_audio_studio,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
