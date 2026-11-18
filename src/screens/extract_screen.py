"""Media extraction screen for audio tracks, video frames, and animated GIFs."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.encoder_options import ContainerOptionRows, EncoderOptionPanel, OptionValues
from components.studio import chip_group, media_summary_card, screen_header
from components.tool_job_status import tool_job_row
from core.constants import (
    DEFAULT_EXTRACT_FORMAT,
    DEFAULT_SUBTITLE_FORMAT,
)
from core.engine_probe import can_encode_format
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import section_header
from core.theme import ACCENT_RED, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_SM, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller

# Mode names in display order — the derived-clamp fallback walks this.
_EXTRACT_MODES = ("audio", "frames", "gif", "subtitles")


def extract_mode_availability(info, probe_info=None) -> dict[str, bool]:
    """Engine-truth availability of each extract mode for probed media.

    Each mode names the stream it needs and the engine raises for a missing
    stream mid-job — offering Frames on an audio file (or Audio on muted
    video) used to pass the UI and fail inside the queue. A None info stays
    permissive: the load gate guarantees a probe before the screen opens.
    ``probe_info`` adds the wheel-level gates (GIF needs a gif encoder).
    """
    gif_ok = probe_info.gif_ok if probe_info is not None else True
    if info is None:
        return {"audio": True, "frames": True, "gif": gif_ok, "subtitles": False}
    has_audio = info.audio_stream is not None
    is_video = info.kind == "video"
    subs = any(s.stream_type == "subtitle" for s in info.streams)
    return {
        "audio": has_audio,
        "frames": is_video,
        "gif": is_video and gif_ok,
        "subtitles": subs,
    }


@ft.component
def ExtractScreen() -> ft.Control:
    """Extraction studio: Audio rip, frame grabber, and palette-optimized GIF maker."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    media_path = app_state.current_media_path
    info = app_state.current_media_info
    file_name = Path(media_path).name if media_path else "No file selected"
    has_audio = info.audio_stream is not None if info is not None else True
    duration_s = max(0.5, info.duration_s if info and info.duration_s else 10.0)

    mode, set_mode = ft.use_state("audio")  # "audio", "frames", "gif", "subtitles"
    audio_fmt, set_audio_fmt = ft.use_state(DEFAULT_EXTRACT_FORMAT)
    audio_kbps, set_audio_kbps = ft.use_state(192)
    frame_count, set_frame_count = ft.use_state(5)
    gif_fps, set_gif_fps = ft.use_state(15)
    gif_width, set_gif_width = ft.use_state(480)
    gif_duration, set_gif_duration = ft.use_state(min(5.0, duration_s))
    gif_start, set_gif_start = ft.use_state(0.0)
    gif_colors, set_gif_colors = ft.use_state(0)  # 0 = encoder default palette
    gif_dither, set_gif_dither = ft.use_state("")
    gif_loop, set_gif_loop = ft.use_state(0)  # 0 = loop forever
    sub_fmt, set_sub_fmt = ft.use_state(DEFAULT_SUBTITLE_FORMAT)
    sub_sel, set_sub_sel = ft.use_state(0)  # index into sub_streams
    muxer_rows, set_muxer_rows = ft.use_state([])
    # Touched encoder settings per codec (ref: mutated in place by the panel,
    # read once at Start — no re-render per keystroke).
    option_values = ft.use_ref({})

    # Live pipeline: derived from the queue, never a stuck local flag.
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    busy = running_job is not None

    # GIF window: lo=1.0 floor AND hi ceiling (sub-1s media used to build
    # max<min and render a broken slider); value pinned inside both.
    # The clamp only ever *lowered*, so it could never repair max<min.
    def _clamp_gif_duration() -> None:
        lo, hi = 1.0, max(1.0, min(8.0, duration_s))
        if gif_duration < lo:
            set_gif_duration(lo)
        elif gif_duration > hi:
            set_gif_duration(hi)

    ft.use_effect(_clamp_gif_duration, [duration_s])

    sub_streams = [s for s in (info.streams if info else []) if s.stream_type == "subtitle"]

    # Mode availability is engine truth (see extract_mode_availability): a
    # mode the file cannot support is disabled, never offered into a doomed
    # queue job.
    mode_ok = extract_mode_availability(info, app_state.probe_info)
    # Derived clamp (never written back): a mode the previous file allowed
    # shows as the first usable mode for THIS file instead of gating only at
    # Start.
    active_mode = (
        mode if mode_ok.get(mode) else next((m for m in _EXTRACT_MODES if mode_ok[m]), "audio")
    )

    def _clamp_sub_sel() -> None:
        if sub_sel >= len(sub_streams):
            set_sub_sel(0)

    ft.use_effect(_clamp_sub_sel, [len(sub_streams)])

    def _start_extraction(_):
        if not media_path or busy:
            return
        if not mode_ok.get(active_mode, True):
            return
        if active_mode == "audio" and not has_audio:
            return
        if active_mode == "subtitles" and not sub_streams:
            return

        stem = Path(media_path).stem
        if active_mode == "audio":
            out_name = unique_temp_name(f"{stem}_audio", chosen_audio_fmt)
            out_path = str(get_temp_dir() / out_name)
            job = Job(
                op="extract_audio",
                input_path=media_path,
                output_path=out_path,
                params={"format_name": chosen_audio_fmt, "bitrate_kbps": int(audio_kbps)},
                original_size_bytes=Path(media_path).stat().st_size
                if Path(media_path).exists()
                else 0,
            )
        elif active_mode == "subtitles":
            # Clamp for the engine, which indexes the subtitle SUBLIST
            # (inp.streams.subtitles) — the container-wide stream index made
            # it extract a different (or the first) track.
            stream_pos = sub_sel if sub_sel < len(sub_streams) else 0
            ext = "vtt" if sub_fmt == "webvtt" else sub_fmt
            out_name = unique_temp_name(stem, ext)
            out_path = str(get_temp_dir() / out_name)
            job = Job(
                op="extract_subtitles",
                input_path=media_path,
                output_path=out_path,
                params={
                    "stream_index": stream_pos,
                    "format_name": sub_fmt,
                },
                original_size_bytes=Path(media_path).stat().st_size
                if Path(media_path).exists()
                else 0,
            )
        elif active_mode == "frames":
            out_dir = str(get_temp_dir() / unique_temp_name(f"{stem}_frames", ""))
            job = Job(
                op="extract_frames",
                input_path=media_path,
                output_path=out_dir,
                params={"count": int(frame_count), "format_name": "jpg"},
                original_size_bytes=Path(media_path).stat().st_size
                if Path(media_path).exists()
                else 0,
            )
        else:  # gif (active_mode)
            out_name = unique_temp_name(f"{stem}_animated", ".gif")
            out_path = str(get_temp_dir() / out_name)
            job = Job(
                op="create_gif",
                input_path=media_path,
                output_path=out_path,
                params={
                    "fps": int(gif_fps),
                    "width": int(gif_width),
                    "start_s": float(gif_start),
                    "duration_s": float(gif_duration),
                    **({"colors": int(gif_colors)} if gif_colors else {}),
                    **({"dither": gif_dither} if gif_dither else {}),
                    "loop_count": int(gif_loop),
                },
                original_size_bytes=Path(media_path).stat().st_size
                if Path(media_path).exists()
                else 0,
            )

        # Generic option panels: only what the user actually touched, and only
        # for the modes that encode (audio / gif).
        encoder_opts = _values_for(mode_codec).as_dict() if mode_codec else {}
        if encoder_opts:
            job.params["encoder_options"] = encoder_opts
        muxer_opts = {str(row[0]): str(row[1]) for row in muxer_rows if str(row[0]).strip()}
        if muxer_opts:
            job.params["container_options"] = muxer_opts

        ctrl.start_job(job)

    # Audio formats — measured against the installed wheel, not assumed. The
    # Android LGPL build ships no MP3 encoder, so offering "mp3" produced an
    # UnknownCodecError after the user pressed Extract.
    audio_formats = [
        f for f in ("mp3", "aac", "m4a", "flac", "opus", "ogg", "wav") if can_encode_format(f)
    ]
    # Clamp onto something encodable so the first chip and the job agree.
    # DERIVED (not written back): the UI always shows the effective value.
    chosen_audio_fmt = (
        audio_fmt
        if audio_fmt in audio_formats
        else (audio_formats[0] if audio_formats else audio_fmt)
    )
    lossless_audio = chosen_audio_fmt in ("wav", "flac")

    start_blocked_reason: str | None = None
    if active_mode == "audio" and not audio_formats:
        start_blocked_reason = "This build has no audio encoders — extraction is unavailable."

    # Generic option panel data: the encoder each mode actually uses (audio is
    # derived from the chosen format; GIF is the wheel's gif encoder).
    from services.engine_service import audio_codec_for_format

    encoder_schemas = (
        app_state.probe_info.encoder_option_schema if app_state.probe_info else {}
    ) or {}
    common_options = list(
        app_state.probe_info.common_encoder_options if app_state.probe_info else []
    )
    mode_codec = (
        audio_codec_for_format(chosen_audio_fmt)
        if active_mode == "audio"
        else ("gif" if active_mode == "gif" else None)
    )

    def _values_for(codec: str | None) -> OptionValues:
        store = option_values.current
        if not codec:
            return OptionValues("")
        values = store.get(codec)
        if values is None:
            values = OptionValues(codec)
            store[codec] = values
        return values

    def _codec_panel() -> list:
        if not mode_codec:
            return []
        return [
            EncoderOptionPanel(
                mode_codec,
                encoder_schemas.get(mode_codec) or [],
                _values_for(mode_codec),
                common_options=common_options,
                is_dark=is_dark,
                title="Advanced encoder settings",
            )
        ]

    return ft.ListView(
        controls=[
            screen_header(
                "Extract",
                subtitle=file_name,
                on_back=lambda: ctrl.navigate("dashboard"),
                is_dark=is_dark,
            ),
            media_summary_card(
                media_path,
                info,
                is_dark=is_dark,
                on_change=lambda: ctrl.pick_media_for("extract"),
            ),
            # Live pipeline status (derived, never stuck)
            *([tool_job_row(running_job, ctrl, is_dark=is_dark)] if running_job else []),
            # Mode Switcher (capability-gated per file)
            section_header("Extraction Target", "Choose what to extract", is_dark=is_dark),
            chip_group(
                [
                    (label, key)
                    for key, label, _tip in (
                        ("audio", "Audio Track", "This file has no audio track"),
                        ("frames", "Video Frames", "Video frames need a video file"),
                        ("gif", "Animated GIF", "GIFs need a video file"),
                        ("subtitles", "Subtitles", "This file carries no subtitle streams"),
                    )
                ],
                value=mode,
                on_change=set_mode,
                disabled_values=[k for k in ("audio", "frames", "gif", "subtitles") if not mode_ok[k]],
                tips={
                    "audio": "This file has no audio track",
                    "frames": "Video frames need a video file",
                    "gif": "GIFs need a video file",
                    "subtitles": "This file carries no subtitle streams",
                },
            ),
            # Conditional settings based on mode
            *(
                [
                    section_header("Audio Format", "Select target sound format", is_dark=is_dark),
                    chip_group(
                        [(fmt.upper(), fmt) for fmt in audio_formats],
                        value=chosen_audio_fmt,
                        on_change=set_audio_fmt,
                    ),
                    # Bitrate is a target/ceiling for lossy, meaningless for
                    # WAV and advisory for FLAC — hidden for lossless.
                    *(
                        [
                            section_header(
                                "Audio Bitrate",
                                f"{audio_kbps} kbps target",
                                is_dark=is_dark,
                            ),
                            ft.Slider(
                                value=float(audio_kbps),
                                min=96,
                                max=320,
                                divisions=14,
                                on_change=lambda e: set_audio_kbps(round(float(e.control.value))),
                            ),
                        ]
                        if not lossless_audio
                        else []
                    ),
                ]
                if active_mode == "audio"
                else []
            ),
            *(
                [
                    section_header(
                        "Number of Frames", f"{frame_count} frames across duration", is_dark=is_dark
                    ),
                    ft.Slider(
                        value=float(frame_count),
                        min=1,
                        max=20,
                        divisions=19,
                        on_change=lambda e: set_frame_count(int(e.control.value)),
                    ),
                ]
                if active_mode == "frames"
                else []
            ),
            *(
                [
                    section_header(
                        "Subtitle Track",
                        (
                            f"{len(sub_streams)} track(s) found"
                            if sub_streams
                            else "No subtitle streams in this file"
                        ),
                        is_dark=is_dark,
                    ),
                    *(
                        [
                            ft.Row(
                                controls=[
                                    ft.Chip(
                                        label=ft.Text(
                                            f"Track {s.index}"
                                            + (f" • {s.language}" if s.language else "")
                                        ),
                                        selected=sub_sel == i,
                                        on_click=lambda _, idx=i: set_sub_sel(idx),
                                    )
                                    for i, s in enumerate(sub_streams)
                                ],
                                wrap=True,
                                spacing=SPACE_SM,
                            )
                        ]
                        if sub_streams
                        else []
                    ),
                    *(
                        [
                            ft.Row(
                                controls=[
                                    ft.Chip(
                                        label=ft.Text(fmt.upper() if fmt != "webvtt" else "VTT"),
                                        selected=sub_fmt == fmt,
                                        on_click=lambda _, f=fmt: set_sub_fmt(f),
                                    )
                                    for fmt in ("srt", "ass", "webvtt")
                                ],
                                spacing=SPACE_SM,
                            )
                        ]
                        if sub_streams
                        else []
                    ),
                ]
                if active_mode == "subtitles"
                else []
            ),
            *(
                [
                    section_header(
                        "GIF Framerate & Resolution",
                        f"{gif_fps} fps • {gif_width}px wide",
                        is_dark=is_dark,
                    ),
                    # Phone CPUs stall on the single-pass palette graph past
                    # ~20fps/640px/8s (hundreds of full-res frames through
                    # palettegen+paletteuse on the serial worker) — the caps
                    # keep the worst case responsive, with the reason on screen.
                    ft.Slider(
                        value=float(gif_fps),
                        min=10,
                        max=20,
                        divisions=10,
                        on_change=lambda e: set_gif_fps(int(e.control.value)),
                    ),
                    section_header("GIF Width", f"{gif_width}px wide", is_dark=is_dark),
                    ft.Slider(
                        value=float(gif_width),
                        min=160,
                        max=640,
                        divisions=12,
                        on_change=lambda e: set_gif_width(int(e.control.value)),
                    ),
                    section_header("GIF Duration", f"{gif_duration:.1f} seconds", is_dark=is_dark),
                    ft.Slider(
                        value=float(gif_duration),
                        min=1.0,
                        max=max(1.0, float(min(8.0, duration_s))),
                        divisions=14,
                        on_change=lambda e: set_gif_duration(round(float(e.control.value), 1)),
                    ),
                    section_header(
                        "GIF Start",
                        f"Begins at {gif_start:.1f}s — the in-point of the clip",
                        is_dark=is_dark,
                    ),
                    ft.Slider(
                        value=float(min(gif_start, max(0.0, duration_s - gif_duration))),
                        min=0.0,
                        max=max(0.1, float(duration_s - gif_duration)),
                        divisions=max(1, int(min(60, duration_s))),
                        on_change=lambda e: set_gif_start(round(float(e.control.value), 1)),
                    ),
                    section_header("GIF Palette", "Colours, dithering and looping", is_dark=is_dark),
                    chip_group(
                        [("Auto", 0), ("64 colours", 64), ("128 colours", 128), ("256 colours", 256)],
                        value=gif_colors,
                        on_change=set_gif_colors,
                    ),
                    chip_group(
                        [("No dither", ""), ("Bayer", "bayer"), ("Sierra", "sierra2_4a")],
                        value=gif_dither,
                        on_change=set_gif_dither,
                    ),
                    chip_group(
                        [("Loop forever", 0), ("Play once", 1), ("3 loops", 3)],
                        value=gif_loop,
                        on_change=set_gif_loop,
                    ),
                    ft.Text(
                        "GIFs cap at 20 fps, 640px wide and 8s — the palette "
                        "pass on a phone CPU stalls past that. Tall portrait "
                        "sources scale height proportionally.",
                        size=FONT_SM,
                        color=muted,
                    ),
                ]
                if active_mode == "gif"
                else []
            ),
            # Every encoder setting this build exposes for the mode's codec
            # (audio: the derived format encoder; gif: the gif encoder).
            *_codec_panel(),
            ContainerOptionRows(muxer_rows, set_muxer_rows, is_dark=is_dark),
            *(
                [ft.Text(start_blocked_reason, size=FONT_SM, color=ACCENT_RED)]
                if start_blocked_reason
                else []
            ),
            # Action button
            ft.FilledButton(
                f"Extract {active_mode.title()}",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                height=48,
                disabled=not media_path
                or busy
                or not mode_ok.get(active_mode, True)
                or (active_mode == "subtitles" and not sub_streams)
                or start_blocked_reason is not None,
                on_click=_start_extraction,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
