"""Generic media-job model — one builder for every FFmpeg operation.

The ten hand-written ops in services/engine_service.py become *presets* over
these specs: a Job describes WHAT to produce (inputs, streams, chains,
output); run_job implements HOW once. av owns timestamps, muxing and
draining — the builder only fixes up what the muxer genuinely requires.

Nothing here hardcodes capabilities: codec names arrive resolved by
engine_probe/engine_service, and filter chains are either explicit nodes
(validated by FFmpeg at runtime) or builder callables sized on the first
decoded frame (crop/watermark need the frame's dimensions).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class InputSpec:
    """One input file/URL/stream."""

    path: str
    format: str | None = None
    options: dict = field(default_factory=lambda: {"fflags": "+discardcorrupt"})
    timeout: tuple[float, float] = (5.0, 15.0)
    hwaccel: str | None = None
    # Seconds into the input; converted with the video stream's time base.
    seek_s: float | None = None
    # Seconds into the input; the builder converts with the video stream's
    # time base and tolerates containers whose index refuses the seek.
    seek_s: float | None = None


@dataclass
class StreamSpec:
    """One output stream (video or audio) to create from an input stream."""

    kind: str  # "video" | "audio"
    selector: int | str = "best"  # "best" or the input stream index
    codec: str = "libx264"  # encoder name; resolved against the wheel
    bit_rate: int | None = None  # bits/s (compress); None -> encoder default
    fps: float | None = None  # None -> the source's exact average rate
    speed: float = 1.0  # playback speed (graph setpts + declared rate change)
    cap_fps: bool = True  # clamp declared fps to 1..60 (phone-safe presets)
    pix_fmt: str | None = None  # None -> fitted to the encoder by the builder
    fine_time_base: bool = False  # use 1/90000 when a graph re-times frames
    scale_width: int | None = None
    scale_height: int | None = None
    crop_aspect: str | None = None  # "original" or a W:H aspect string
    rotation: int = 0  # right-angle display rotation through transpose
    even_align: bool = True  # round output dimensions down to even (yuv420p)
    layout: str | None = None  # audio layout override ("stereo"/"mono")
    channels: int | None = None
    sample_rate: int | None = None  # None -> source rate (opus preset may force 48k)
    # Encoder options merged after resolution: crf/preset/bf/threads/profile...
    encoder_options: dict = field(default_factory=dict)
    # Timestamp policy: "monotonic" (builder floors) | "encoder" (pts=None).
    pts_policy: str = "monotonic"
    # Fixed-frame audio encoders need AudioFifo batching (AAC/MP3/FLAC).
    audio_fifo: bool = False
    # Bridge rate/layout with soxr (swr fallback) before the encoder.
    audio_resample: bool = True


@dataclass
class FilterChain:
    """An ordered filter graph for one stream.

    ``nodes`` are static (name, args-dict) pairs; ``build`` is used when the
    chain must be sized on the first frame (crop aspect, watermark overlay)
    or gated on this build's available filters. run_job uses whichever the
    preset provides, preferring ``build``.
    """

    nodes: list[tuple[str, dict]] = field(default_factory=list)
    build: Callable[[object], object] | None = None
    # Audio chains may need frame-size batching through an AudioFifo; the
    # builder enables it when the chain sets fifo=True.
    fifo: bool = False


@dataclass
class OutputSpec:
    """The output container."""

    container: str | None = None  # None -> guessed from output_path extension
    options: dict = field(default_factory=dict)
    metadata: bool = True
    chapters: bool = True


@dataclass
class Job:
    """One media job: inputs -> streams/chains -> output."""

    output_path: str
    inputs: list[InputSpec] = field(default_factory=list)
    streams: list[StreamSpec] = field(default_factory=list)
    output: OutputSpec = field(default_factory=OutputSpec)
    video_chain: FilterChain | None = None
    audio_chain: FilterChain | None = None
    # Time window applied after decoding (seconds); None = whole input.
    window: tuple[float | None, float | None] | None = None
    # Progress copy per op family (builder messages otherwise say Processing/Complete).
    progress_label: str = "Processing"
    complete_label: str = "Complete"
    cancel_message: str = "Transcoding was cancelled"
    # Time window applied after decoding (seconds); None = whole input.
    window: tuple[float | None, float | None] | None = None
    # Progress copy per op family.
    progress_label: str = "Processing"
    complete_label: str = "Complete"
    cancel_message: str = "Transcoding was cancelled"
    # Multi-input transitions (concat): added in the timeline step.
    transition: str | None = None  # None | "cut" | "crossfade"
    fade_s: float = 0.5
