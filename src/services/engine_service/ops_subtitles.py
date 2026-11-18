"""Subtitle muxing and burn-in for a build without libass.

The lean FFmpeg wheel has no libass, so the styled ``subtitles``/``ass``
filters do not exist. What it does have: the subtitle codecs (subrip/ass/
mov_text for reading and packet copy), and ``drawtext`` (freetype + fribidi).
So:

- ``mux_subtitles`` adds an external sidecar as a real subtitle track by
  packet copy — valid for Matroska/WebM text tracks. MP4 needs mov_text
  re-encoding, which this PyAV surface cannot encode; that case is refused
  loudly instead of producing a broken file.
- ``burn_subtitles`` renders every cue with a ``drawtext`` node gated to its
  own time window. Styling is our own (font size/color/position), not ASS
  styling — honest about the capability difference.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event

import av

from services.engine_service.builders import run_encode_job
from services.engine_service.capability import EngineCapabilityError
from services.engine_service.graphs import _FONT, _drawtext_escaped, available_filters
from services.engine_service.logs import _INPUT_OPTIONS, _INPUT_TIMEOUT
from services.engine_service.ops_extract import read_cues
from services.engine_service.options import _pick_video_encoder
from services.engine_service.resolve import _resolve_or_raw
from services.engine_service.safety import _close_container
from services.job_model import FilterChain, InputSpec, Job, OutputSpec, StreamSpec

logger = logging.getLogger(__name__)

_TEXT_CONTAINERS = ("matroska", "webm")
_escaped = _drawtext_escaped  # the shared escaping lives next to the graph code


def mux_subtitles(
    input_path: str,
    sidecar_path: str,
    output_path: str,
    container: str | None = None,
    language: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Add a text sidecar to a media file as a subtitle track (packet copy)."""
    target = container
    if target is None:
        suffix = Path(output_path).suffix.lower()
        target = "matroska" if suffix in (".mkv", ".mka") else "webm" if suffix == ".webm" else None
    if target not in _TEXT_CONTAINERS:
        raise ValueError(
            "External subtitle tracks need a Matroska (.mkv) or WebM output — "
            "MP4 needs mov_text re-encoding, which this build cannot encode"
        )

    inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    side = av.open(sidecar_path, "r")
    out = av.open(output_path, "w", format=target)
    try:
        stream_map: dict = {}
        for src in inp.streams:
            if src.type not in ("video", "audio", "subtitle", "attachment", "data"):
                continue
            try:
                stream_map[src] = out.add_stream_from_template(src, opaque=True)
            except ValueError as exc:
                logger.info("Stream %s not carried into %s: %s", src.index, target, exc)

        side_src = side.streams[0]
        side_out = out.add_stream_from_template(side_src, opaque=True)
        if language:
            side_out.metadata["language"] = language

        for pkt in inp.demux():
            if pkt.size == 0 or (pkt.pts is None and pkt.dts is None):
                continue
            out_s = stream_map.get(pkt.stream)
            if out_s is None:
                continue
            pkt.stream = out_s
            out.mux(pkt)

        copied = 0
        for pkt in side.demux([side_src]):
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Subtitle muxing cancelled")
            if pkt.size == 0:
                continue
            pkt.stream = side_out
            out.mux(pkt)
            copied += 1
        if on_progress:
            on_progress(1.0, f"Added {copied} subtitle packets")
    finally:
        _close_container(out)
        _close_container(side)
        _close_container(inp)
    return output_path


def burn_subtitles(
    input_path: str,
    output_path: str,
    *,
    sidecar_path: str | None = None,
    stream_index: int = 0,
    font_size_pct: float = 0.05,
    color: str = "white",
    position: str = "bottom",
    video_codec: str | None = None,
    audio_codec: str = "aac",
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Render every cue into the video frames (drawtext, no libass needed)."""
    if "drawtext" not in available_filters():
        raise EngineCapabilityError(
            "Burning subtitles needs the drawtext filter, which this FFmpeg build "
            "does not include — mux the subtitles as a track instead"
        )
    if not _FONT.is_file():
        raise ValueError(f"Burned-in subtitles need the bundled font at {_FONT}")
    cues = read_cues(sidecar_path or input_path, stream_index, cancel_event)
    if not cues:
        raise ValueError("No text cues to burn in")

    if position == "top":
        y_expr = "h*0.06"
    elif position == "center":
        y_expr = "(h-text_h)/2"
    else:
        y_expr = "h-text_h-h*0.06"

    nodes = [
        (
            "drawtext",
            f"fontfile={_FONT}:text='{_escaped(cue.text)}':"
            f"fontsize=h*{font_size_pct:.4f}:fontcolor={color}:"
            f"borderw=3:bordercolor=black:x=(w-text_w)/2:y={y_expr}:"
            f"enable='between(t,{cue.start_s:.3f},{cue.end_s:.3f})'",
        )
        for cue in cues
    ]

    chosen = _resolve_or_raw(video_codec, "video") if video_codec else _pick_video_encoder()
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path)],
        streams=[
            StreamSpec(kind="video", codec=chosen, cap_fps=False),
            StreamSpec(kind="audio", codec=_resolve_or_raw(audio_codec, "audio")),
        ],
        output=OutputSpec(options=dict(container_options or {})),
        video_chain=FilterChain(nodes=nodes),
        progress_label="Burning subtitles",
        complete_label="Subtitles burned",
        cancel_message="Subtitle burn-in cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)
