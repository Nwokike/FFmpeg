"""Audio Studio screen for loudness normalization, resampling, and channel mixing."""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from components.tool_job_status import tool_job_row
from core.engine_probe import can_encode_format
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_MD, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller

try:
    from flet_audio import Audio

    _HAS_AUDIO_PLAYER = True
except ImportError:  # pragma: no cover — package is in the dev tree
    _HAS_AUDIO_PLAYER = False

logger = logging.getLogger(__name__)

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

    def _toggle_audition(_=None) -> None:
        player = audition_ref.current
        if player is None:
            return

        async def _t():
            try:
                if audition_playing:
                    await player.pause()
                else:
                    await player.play()
            except Exception as exc:
                logger.warning("Audition toggle failed: %s", exc)

        try:
            page.run_task(_t)
        except Exception as exc:
            logger.debug("Audition skipped (page gone): %s", exc)

    def _set_audition_rate(value: float) -> None:
        set_audition_rate(value)
        player = audition_ref.current
        if player is None:
            return

        async def _r():
            try:
                player.playback_rate = float(value)
            except Exception as exc:
                logger.warning("Audition rate failed: %s", exc)

        try:
            page.run_task(_r)
        except Exception as exc:
            logger.debug("Audition rate skipped: %s", exc)

    def _set_audition_pan(value: float) -> None:
        # -1 left-only … 0 center … 1 right-only. Auditioning one side tells
        # you whether the mono downmix will lose anything important.
        set_audition_pan_state(value)
        player = audition_ref.current
        if player is None:
            return

        async def _p():
            try:
                player.balance = float(value)
            except Exception as exc:
                logger.warning("Audition pan failed: %s", exc)

        try:
            page.run_task(_p)
        except Exception as exc:
            logger.debug("Audition pan skipped: %s", exc)

    # Audition player: hear pan/tempo WITHOUT re-encoding. Mounted on the
    # source file (service lifecycle like result: append on mount effect,
    # release on cleanup). Player-side only — zero wheel risk.
    audition_ref = ft.use_ref(None)
    audition_ready, set_audition_ready = ft.use_state(False)
    audition_playing, set_audition_playing = ft.use_state(False)
    audition_rate, set_audition_rate = ft.use_state(1.0)
    audition_pan, set_audition_pan_state = ft.use_state(0.0)

    def _mount_audition():
        if not _HAS_AUDIO_PLAYER or not media_path or audition_ref.current is not None:
            return None
        try:
            player = Audio(
                src=media_path,
                on_state_change=lambda e: set_audition_playing(
                    getattr(e, "state", None) is not None
                    and str(getattr(e.state, "value", e.state)) == "playing"
                ),
                on_loaded=lambda _: set_audition_ready(True),
                on_error=lambda e: logger.warning("Audition error: %s", getattr(e, "data", e)),
            )
            page.services.append(player)
            audition_ref.current = player
        except Exception as exc:
            logger.warning("Audition player unavailable: %s", exc)
        return None

    def _release_audition() -> None:
        player, audition_ref.current = audition_ref.current, None
        set_audition_playing(False)
        set_audition_ready(False)
        if player is None:
            return

        async def _release():
            try:
                await player.release()
            except Exception as exc:
                logger.debug("Audition release failed: %s", exc)
            finally:
                try:
                    if any(s is player for s in page.services):
                        page.services.remove(player)
                        page.update()
                except Exception as exc:
                    logger.debug("Audition removal skipped: %s", exc)

        try:
            page.run_task(_release)
        except Exception as exc:
            logger.debug("Audition teardown skipped: %s", exc)

    ft.use_effect(
        _mount_audition,
        [media_path or ""],
        cleanup=lambda: (_release_audition(),),
    )

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
            # Audition (preview pan/tempo without encoding).
            section_header(
                "Audition",
                "Hear the source before you encode (no re-encode)",
                is_dark=is_dark,
            ),
            *(
                [
                    card_container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.PLAY_ARROW_ROUNDED
                                            if not audition_playing
                                            else ft.Icons.PAUSE_ROUNDED,
                                            icon_size=32,
                                            tooltip="Preview source audio",
                                            on_click=lambda _: _toggle_audition(),
                                        ),
                                        ft.Column(
                                            controls=[
                                                ft.Text(
                                                    "Preview tempo",
                                                    size=FONT_SM,
                                                    color=muted,
                                                ),
                                                ft.Slider(
                                                    value=float(audition_rate),
                                                    min=0.5,
                                                    max=2.0,
                                                    divisions=15,
                                                    on_change=lambda e: _set_audition_rate(
                                                        round(float(e.control.value), 2)
                                                    ),
                                                ),
                                            ],
                                            expand=True,
                                            spacing=2,
                                        ),
                                        ft.Text(
                                            f"{audition_rate:.2f}x",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ],
                                    spacing=SPACE_SM,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Text(
                                    (
                                        "Pan one side to check what the mono downmix "
                                        "keeps; tempo previews without touching "
                                        "the encode below."
                                        if audition_ready
                                        else "Loading preview…"
                                    ),
                                    size=FONT_XS,
                                    color=muted,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.Text("Pan", size=FONT_SM, color=muted),
                                        *[
                                            ft.Chip(
                                                label=ft.Text(label),
                                                selected=audition_pan == value,
                                                on_click=lambda _, v=value: _set_audition_pan(v),
                                            )
                                            for label, value in (
                                                ("L", -1.0),
                                                ("C", 0.0),
                                                ("R", 1.0),
                                            )
                                        ],
                                    ],
                                    spacing=SPACE_SM,
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_LG,
                        is_dark=is_dark,
                    )
                ]
                if media_path and audio_ok and _HAS_AUDIO_PLAYER
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
