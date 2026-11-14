"""Convert / compress / cut operations."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event

from services.engine_service.builders import probe_media, run_copy_job, run_encode_job
from services.engine_service.graphs import (
    _build_audio_filter_graph,
    _build_video_filter_graph,
)
from services.engine_service.logs import _INPUT_TIMEOUT
from services.engine_service.options import (
    _hardware_decode,
    _optional_encoder_knobs,
    _pick_video_encoder,
    _supported_encoder_options,
)
from services.engine_service.resolve import _resolve_or_raw
from services.job_model import FilterChain, InputSpec, Job, OutputSpec, StreamSpec

# Target-size compression math (shared shape with the Compress screen's estimate).
CONTAINER_HEADROOM = 0.92  # 8% muxer/container safety margin
AUDIO_BITRATE_CAP = 128_000
AUDIO_BITRATE_FLOOR = 64_000
AUDIO_BITRATE_SHARE = 0.15  # audio takes 15% of the total budget
VIDEO_BITRATE_FLOOR = 100_000
RESOLUTION_LADDER = ((400_000, 854), (1_000_000, 1280))  # (bitrate cap, width)


def convert(
    input_path: str,
    output_path: str,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 23,
    preset: str = "medium",
    scale_width: int | None = None,
    scale_height: int | None = None,
    fps: int | None = None,
    speed: float = 1.0,
    volume_pct: int = 100,
    rotation: int = 0,
    crop_aspect: str | None = None,
    eq: dict | None = None,
    denoise: str | None = None,
    sharpen: int | None = None,
    watermark: dict | None = None,
    hardware_accel: bool = False,
    gop_size: int | None = None,
    max_b_frames: int | None = None,
    qmin: int | None = None,
    qmax: int | None = None,
    thread_count: int | None = None,
    profile: str | None = None,
    level: str | None = None,
    pix_fmt: str | None = None,
    video_stream: int | None = None,
    audio_stream: int | None = None,
    video_filter: list | None = None,
    audio_filter: list | None = None,
    container: str | None = None,
    bit_rate: int | None = None,
    encoder_options: dict | None = None,
    audio_encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Transcode video/audio with quality, scaling, filters, and transforms.

    Preset over the generic encode builder (run_encode_job): the fixed knobs
    and ``encoder_options`` merge into one option set that passes through
    :func:`_supported_encoder_options`, so a key this wheel's encoder lacks
    drops with an info line instead of failing the job. ``audio_encoder_options``
    do the same for the audio stream (a separate encoder, so a separate dict).
    ``container_options`` go to the muxer through ``OutputSpec.options``
    (``av.open(options=...)``). ``container`` names the muxer explicitly when
    the output path's extension is not enough (the Terminal's ``-f``);
    ``video_stream``/``audio_stream`` are absolute input stream indices (the
    ``-map 0:v:1`` shape); ``pix_fmt`` overrides the encoder-fitted pixel format.
    """
    hwaccel = _hardware_decode(hardware_accel)
    need_vfilter = (
        rotation % 360 != 0
        or abs(speed - 1.0) > 1e-6
        or bool(crop_aspect and crop_aspect != "original")
        or bool(eq)
        or bool(denoise and denoise != "off")
        or bool(sharpen)
        or bool(watermark)
        or bool(video_filter)
    )
    need_afilter = volume_pct != 100 or abs(speed - 1.0) > 1e-6

    chosen_vcodec = _resolve_or_raw(video_codec, "video")
    # A caller-supplied filter chain (the Terminal's -vf/-af passthrough) is
    # the real chain; the built-in graph below only runs when no nodes came
    # in. Nodes are (filter, args-string) pairs handed to FFmpeg untouched.
    video_chain = (
        FilterChain(nodes=[(str(n), str(a)) for n, a in video_filter])
        if video_filter
        else (
            FilterChain(
                build=lambda frame: _build_video_filter_graph(
                    frame,
                    rotation,
                    speed,
                    crop_aspect=crop_aspect,
                    eq=eq,
                    denoise=denoise,
                    sharpen=sharpen,
                    watermark=watermark,
                )
            )
            if need_vfilter
            else None
        )
    )
    audio_chain = (
        FilterChain(nodes=[(str(n), str(a)) for n, a in audio_filter])
        if audio_filter
        else (
            FilterChain(build=lambda frame: _build_audio_filter_graph(frame, volume_pct, speed))
            if need_afilter
            else None
        )
    )

    job = Job(
        output_path=output_path,
        inputs=[
            InputSpec(
                path=input_path,
                options={},
                timeout=_INPUT_TIMEOUT,
                hwaccel=hwaccel,
            )
        ],
        streams=(
            [
                StreamSpec(
                    kind="video",
                    selector=video_stream if video_stream is not None else "best",
                    codec=chosen_vcodec,
                    fps=fps,
                    speed=speed,
                    fine_time_base=need_vfilter,
                    scale_width=scale_width,
                    scale_height=scale_height,
                    crop_aspect=crop_aspect,
                    rotation=rotation,
                    pix_fmt=pix_fmt,
                    bit_rate=bit_rate,
                    encoder_options=_supported_encoder_options(
                        chosen_vcodec,
                        {"crf": str(crf), "preset": preset}
                        | ({"bf": "0"} if need_vfilter else {})
                        | _optional_encoder_knobs(
                            gop_size=gop_size,
                            max_b_frames=max_b_frames,
                            qmin=qmin,
                            qmax=qmax,
                            thread_count=thread_count,
                            profile=profile,
                            level=level,
                        )
                        | dict(encoder_options or {}),  # user options last: they win
                    ),
                ),
            ]
            + (
                [
                    StreamSpec(
                        kind="audio",
                        selector=audio_stream if audio_stream is not None else "best",
                        codec=_resolve_or_raw(audio_codec, "audio"),
                        encoder_options=_supported_encoder_options(
                            _resolve_or_raw(audio_codec, "audio"),
                            dict(audio_encoder_options or {}),
                        ),
                    ),
                ]
                if audio_codec
                else []  # audio_codec=None: the Terminal's -an
            )
        ),
        output=OutputSpec(container=container, options=dict(container_options or {})),
        video_chain=video_chain,
        audio_chain=audio_chain,
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)


def compress_to_target(
    input_path: str,
    output_path: str,
    target_size_mb: float,
    video_codec: str | None = None,
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Compress video to stay under a specified target file size (e.g. WhatsApp 16MB).

    ``video_codec`` is the screen's wheel-measured pick (the Compress UI
    offers only verified encoders, mpeg4-first on LGPL wheels). None keeps
    the legacy auto choice. The resolver raises EngineCapabilityError for
    anything the wheel cannot encode — a refuse-before-Start at the UI.
    ``encoder_options``/``container_options`` are the generic option-panel
    values: encoder keys merge last and pass through
    :func:`_supported_encoder_options`, container keys reach the muxer.
    """
    info = probe_media(input_path)
    duration = max(1.0, info.duration_s)
    target_bits = target_size_mb * 8 * 1024 * 1024 * CONTAINER_HEADROOM  # 8% safety headroom
    total_bitrate = int(target_bits / duration)

    audio_bitrate = min(
        AUDIO_BITRATE_CAP, max(AUDIO_BITRATE_FLOOR, int(total_bitrate * AUDIO_BITRATE_SHARE))
    )
    video_bitrate = max(VIDEO_BITRATE_FLOOR, total_bitrate - audio_bitrate)

    # Resolution downscale ladder for low target bitrates (derived from the
    # probed source dimensions, never written back to the caller).
    scale_w = None
    scale_h = None
    v_stream = info.video_stream
    if v_stream and v_stream.width and v_stream.height:
        if video_bitrate < 400000 and v_stream.width > 854:  # <400kbps -> 480p
            scale_w = 854
            scale_h = int(854 * (v_stream.height / v_stream.width))
        elif video_bitrate < 1000000 and v_stream.width > 1280:  # < 1Mbps -> 720p
            scale_w = 1280
            scale_h = int(1280 * (v_stream.height / v_stream.width))

    chosen_vcodec = _resolve_or_raw(video_codec, "video") if video_codec else _pick_video_encoder()
    fps = int(float(v_stream.fps or 30)) if v_stream else None

    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path)],
        streams=[
            StreamSpec(
                kind="video",
                codec=chosen_vcodec,
                bit_rate=video_bitrate,
                fps=fps,
                cap_fps=False,
                scale_width=scale_w,
                scale_height=scale_h,
                encoder_options=_supported_encoder_options(
                    chosen_vcodec, {"preset": "fast"} | dict(encoder_options or {})
                ),
            ),
            StreamSpec(
                kind="audio",
                codec="aac",
                bit_rate=audio_bitrate,
                layout="stereo",
            ),
        ],
        output=OutputSpec(chapters=False, options=dict(container_options or {})),
        progress_label="Compressing",
        complete_label="Compressed",
        cancel_message="Compression cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)

    return output_path


def cut_trim(
    input_path: str,
    output_path: str,
    start_seconds: float,
    end_seconds: float,
    stream_copy: bool = True,
    video_codec: str | None = None,
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Trim/cut a segment from media. Supports lossless stream copy or frame-accurate re-encode.

    ``video_codec`` is the screen's wheel-measured pick for the re-encode
    path (None = legacy auto). The resolver raises EngineCapabilityError
    for anything the wheel cannot encode. ``encoder_options`` apply to the
    re-encode path only (a stream copy has no encoder); ``container_options``
    reach the muxer on both.
    """
    if stream_copy:
        return _cut_stream_copy(
            input_path,
            output_path,
            start_seconds,
            end_seconds,
            container_options,
            on_progress,
            cancel_event,
        )
    return _cut_reencode(
        input_path,
        output_path,
        start_seconds,
        end_seconds,
        video_codec,
        encoder_options,
        container_options,
        on_progress,
        cancel_event,
    )


def _cut_stream_copy(
    input_path: str,
    output_path: str,
    start_s: float,
    end_s: float,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path, seek_s=start_s)],
        output=OutputSpec(metadata=True, options=dict(container_options or {})),
        snap_to_keyframe=True,
        zero_base=True,
        repair_pts_dts=True,
        window=(start_s, end_s),
        progress_label="Copying cut",
        complete_label="Cut Complete",
        cancel_message="Cut was cancelled",
    )
    return run_copy_job(job, on_progress=on_progress, cancel_event=cancel_event)


def _cut_reencode(
    input_path: str,
    output_path: str,
    start_s: float,
    end_s: float,
    video_codec: str | None = None,
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    chosen_vcodec = _resolve_or_raw(video_codec, "video") if video_codec else _pick_video_encoder()
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path, seek_s=max(0.0, start_s - 2.0))],
        streams=[
            StreamSpec(
                kind="video",
                codec=chosen_vcodec,
                cap_fps=False,
                encoder_options=_supported_encoder_options(
                    chosen_vcodec,
                    {"crf": "20", "preset": "fast"} | dict(encoder_options or {}),
                ),
            ),
            StreamSpec(kind="audio", codec="aac", layout="stereo"),
        ],
        output=OutputSpec(metadata=False, chapters=False, options=dict(container_options or {})),
        window=(start_s, end_s),
        progress_label="Encoding cut",
        complete_label="Cut Complete",
        cancel_message="Cut was cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)
