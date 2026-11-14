"""Audio mastering and extraction."""

from __future__ import annotations

import json
from collections.abc import Callable
from threading import Event

import av
from av.filter.loudnorm import stats as loudnorm_stats

from services.engine_service.builders import _pause_hook, probe_media, run_encode_job
from services.engine_service.logs import _INPUT_OPTIONS, _INPUT_TIMEOUT, logger
from services.engine_service.options import _supported_encoder_options
from services.engine_service.resolve import _derive_audio_codec_for_format
from services.job_model import FilterChain, InputSpec, Job, OutputSpec, StreamSpec


def _measure_loudnorm(input_path: str, target_lufs: float) -> dict[str, str]:
    """Pass 1 of two-pass loudnorm: measure integrated loudness as JSON stats.

    NOTE: ``av.filter.loudnorm.stats`` takes ownership of the format context it
    is given (it NULLs the Python wrapper's handle before the C pass), so this
    container is intentionally never closed — closing would double-free.
    """
    stats_container = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    audio_streams = stats_container.streams.audio
    if not audio_streams:
        stats_container.close()
        raise ValueError("No audio stream found in source media")
    try:
        raw = loudnorm_stats(f"i={target_lufs}", audio_streams[0])
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        # Handle already NULLed on entry to stats(); do not close.
        logger.warning("Loudnorm measurement failed, falling back to dynamic mode: %s", exc)
        return {}


def extract_audio(
    input_path: str,
    output_path: str,
    format_name: str = "mp3",  # mp3, aac, m4a, flac, opus, ogg, wav
    bitrate_kbps: int = 192,
    target_lufs: float | None = None,
    channels: int | None = None,
    sample_rate: int | None = None,
    audio_filter: list | None = None,
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Extract audio with optional LUFS mastering, channel mix, and soxr resampling.

    ``audio_filter`` is a caller-supplied ``(filter, args)`` chain (the
    Terminal's ``-af``); ``encoder_options``/``container_options`` are the
    generic option-panel values: encoder keys merge last and pass through
    :func:`_supported_encoder_options`, container keys reach the muxer.
    """
    # Do not create a partial output while the serial queue is paused.
    _pause_hook(cancel_event)
    requested_format = format_name.lower()
    chosen_codec = _derive_audio_codec_for_format(requested_format)

    # Two-pass loudnorm needs a full measurement pass before encoding starts.
    measured = (
        _measure_loudnorm(input_path, float(target_lufs)) if target_lufs is not None else None
    )
    loud_args: str | None = None
    if target_lufs is not None:
        keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        bad = {"inf", "-inf", "nan", ""} if measured else set()
        if measured and all(k in measured and str(measured[k]).lower() not in bad for k in keys):
            loud_args = (
                f"i={target_lufs}"
                f":measured_I={measured['input_i']}"
                f":measured_TP={measured['input_tp']}"
                f":measured_LRA={measured['input_lra']}"
                f":measured_thresh={measured['input_thresh']}"
                f":offset={measured['target_offset']}"
                ":linear=true"
            )
        else:
            loud_args = f"i={target_lufs}"  # dynamic single-pass fallback

    info = probe_media(input_path)
    in_channels = getattr(info.audio_stream, "channels", None) if info.audio_stream else None
    if info.audio_stream is None:
        raise ValueError("No audio stream found in source media")
    if channels in (1, 2):
        target_layout = "mono" if channels == 1 else "stereo"
    else:
        n_ch = min(2, in_channels or 2)
        target_layout = "stereo" if n_ch == 2 else "mono"

    out_rate = int(sample_rate) if sample_rate else None
    loud_chain = None
    if loud_args is not None:

        def _loudnorm_build(frame) -> av.filter.Graph:
            lg = av.filter.Graph()
            ab_kwargs: dict = {
                "sample_rate": frame.sample_rate,
                "format": frame.format.name,
                "layout": frame.layout.name,
            }
            if frame.time_base:
                ab_kwargs["time_base"] = frame.time_base
            src = lg.add_abuffer(**ab_kwargs)
            ln = lg.add("loudnorm", loud_args)
            sink = lg.add("abuffersink")
            lg.link_nodes(src, ln, sink)
            lg.configure()
            return lg

        loud_chain = FilterChain(build=_loudnorm_build)
    elif audio_filter:
        # A caller-supplied chain (the Terminal's -af passthrough): the same
        # (filter, args-string) nodes the video path uses, so any filter this
        # build ships works here too.
        loud_chain = FilterChain(nodes=[(str(n), str(a)) for n, a in audio_filter])

    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path)],
        streams=[
            StreamSpec(
                kind="audio",
                codec=chosen_codec,
                sample_rate=out_rate,
                channels=channels,
                layout=target_layout,
                bit_rate=(bitrate_kbps * 1000) if chosen_codec != "pcm_s16le" else None,
                pts_policy="encoder",
                audio_fifo=True,
                audio_resample=True,
                encoder_options=_supported_encoder_options(
                    chosen_codec, dict(encoder_options or {})
                ),
            )
        ],
        output=OutputSpec(metadata=False, chapters=False, options=dict(container_options or {})),
        audio_chain=loud_chain,
        progress_label="Extracting Audio",
        complete_label="Audio Extracted",
        cancel_message="Audio extraction cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)
