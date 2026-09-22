"""FFmpeg media engine service wrapping PyAV.

Provides robust, thread-isolated implementations for:
- Container & stream probing (MediaInfo / MediaStreamInfo)
- Transcoding & format conversion (with CRF, presets, resolution downscale)
- Target-size video compression
- Lossless stream-copy and frame-accurate trimming
- Audio extraction (MP3, AAC, FLAC, Opus, WAV)
- High-res frame extraction
- Palette-aware animated GIF generation
- Audio normalization & filter pipelines
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from collections.abc import Callable
from errno import EAGAIN
from fractions import Fraction
from pathlib import Path
from threading import Event

import av
from av.error import FFmpegError
from av.filter.loudnorm import stats as loudnorm_stats

from core.state import MediaInfo, MediaStreamInfo

logger = logging.getLogger("EngineService")

# Fine-grained time base for the video filter pipeline: setpts at speed≠1 on a
# coarse stream tb (e.g. 1/30) quantizes to duplicate pts → non-monotonic dts →
# mp4 muxer EINVAL. 1/90000 keeps sub-frame spacing exact. Audio graphs stay on
# their sample-based tb (already far finer than any atempo shift).
_FINE_VIDEO_TB = Fraction(1, 90000)


def _rebase_pts(frame: av.VideoFrame, dst_tb: Fraction) -> None:
    """Rescale a frame's pts into dst_tb (Frame.time_base setter does not rescale)."""
    if frame.time_base is None or dst_tb is None:
        frame.time_base = dst_tb
        return
    if frame.time_base == dst_tb:
        return
    if frame.pts is not None:
        frame.pts = int(Fraction(frame.pts) * frame.time_base / dst_tb)
    frame.time_base = dst_tb


def _atempo_factors(speed: float) -> list[float]:
    """Split a speed multiplier into atempo-legal factors (each within 0.5..2.0)."""
    factors: list[float] = []
    s = float(speed)
    if abs(s - 1.0) < 1e-6:
        return factors
    while s < 0.5:
        factors.append(0.5)
        s /= 0.5
    while s > 2.0:
        factors.append(2.0)
        s /= 2.0
    if abs(s - 1.0) > 1e-6:
        factors.append(round(s, 6))
    return factors


def _pull_ready(graph: av.filter.Graph) -> av.VideoFrame | av.AudioFrame | None:
    """Pull one frame from a (mostly) synchronous filter graph, tolerating transient EAGAIN."""
    for _ in range(8):
        try:
            return graph.pull()
        except EOFError:
            raise
        except FFmpegError as exc:
            if exc.errno == EAGAIN:
                continue
            raise
    return None


def _push_pull(graph: av.filter.Graph, frame: av.VideoFrame | av.AudioFrame) -> list:
    """Push one frame through a 1:1 graph and collect its output (may be empty if buffered)."""
    graph.push(frame)
    got = _pull_ready(graph)
    return [got] if got is not None else []


def _drain_graph(graph: av.filter.Graph) -> list:
    """Signal EOF to the graph and collect every remaining output frame."""
    graph.push(None)
    frames: list = []
    eagain_streak = 0
    while True:
        try:
            frames.append(graph.pull())
            eagain_streak = 0
        except EOFError:
            break
        except FFmpegError as exc:
            if exc.errno == EAGAIN:
                eagain_streak += 1
                if eagain_streak > 64:
                    logger.warning("Filter graph stopped producing frames before EOF")
                    break
                continue
            raise
    return frames


def _build_video_filter_graph(
    frame: av.VideoFrame, rotation: int, speed: float
) -> av.filter.Graph:
    """buffer → transpose? → setpts? → buffersink for the Filters screen transforms."""
    g = av.filter.Graph()
    nodes: list = [g.add_buffer(template=frame, time_base=_FINE_VIDEO_TB)]
    rot = rotation % 360
    if rot == 90:
        nodes.append(g.add("transpose", "clock"))
    elif rot == 180:
        nodes.append(g.add("transpose", "clock"))
        nodes.append(g.add("transpose", "clock"))
    elif rot == 270:
        nodes.append(g.add("transpose", "cclock"))
    if abs(speed - 1.0) > 1e-6:
        nodes.append(g.add("setpts", f"PTS/{speed}"))
    nodes.append(g.add("buffersink"))
    g.link_nodes(*nodes)
    g.configure()
    return g


def _build_audio_filter_graph(
    frame: av.AudioFrame, volume_pct: int, speed: float
) -> av.filter.Graph | None:
    """abuffer → volume? → atempo chain? → abuffersink; None when no filter applies."""
    g = av.filter.Graph()
    ab_kwargs: dict = {
        "sample_rate": frame.sample_rate,
        "format": frame.format.name,
        "layout": frame.layout.name,
    }
    if frame.time_base is not None:
        ab_kwargs["time_base"] = frame.time_base
    nodes: list = [g.add_abuffer(**ab_kwargs)]
    if volume_pct != 100:
        nodes.append(g.add("volume", f"{volume_pct / 100.0}"))
    for factor in _atempo_factors(speed):
        nodes.append(g.add("atempo", str(factor)))
    if len(nodes) == 1:
        return None
    nodes.append(g.add("abuffersink"))
    g.link_nodes(*nodes)
    g.configure()
    return g


def _discard_cancelled(path: str, *, directory: bool = False) -> None:
    """Best-effort removal of a partial output left behind by a cancelled job."""
    try:
        if directory:
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Failed to remove cancelled output %s: %s", path, exc)


class EngineService:
    """Core media transformation engine powered by PyAV."""

    @staticmethod
    def probe(file_path: str) -> MediaInfo:
        """Inspect a media container and extract all metadata and stream details."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        file_size = p.stat().st_size
        streams_info: list[MediaStreamInfo] = []
        metadata: dict[str, str] = {}
        duration_s = 0.0
        bitrate = 0
        fmt_name = ""
        fmt_long = ""
        raw_dump = ""

        with av.open(file_path, "r") as container:
            fmt_name = container.format.name
            fmt_long = container.format.long_name or fmt_name
            if container.duration is not None:
                duration_s = float(container.duration) / float(av.time_base)
            if container.bit_rate is not None:
                bitrate = container.bit_rate
            elif duration_s > 0:
                bitrate = int((file_size * 8) / duration_s)

            if container.metadata:
                metadata = {str(k): str(v) for k, v in container.metadata.items()}

            for idx, stream in enumerate(container.streams):
                stype = stream.type or "unknown"
                cname = stream.codec_context.name if stream.codec_context else "unknown"
                clong = (
                    getattr(stream.codec_context.codec, "long_name", "")
                    if stream.codec_context and stream.codec_context.codec
                    else ""
                )
                s_dur = (
                    float(stream.duration * stream.time_base)
                    if stream.duration and stream.time_base
                    else None
                )
                s_bitrate = stream.bit_rate or (
                    stream.codec_context.bit_rate if stream.codec_context else None
                )

                s_info = MediaStreamInfo(
                    index=idx,
                    stream_type=stype,
                    codec_name=cname,
                    codec_long_name=clong,
                    profile=getattr(stream, "profile", None),
                    bitrate=s_bitrate,
                    duration_s=s_dur,
                    language=getattr(stream, "language", None),
                    metadata={str(k): str(v) for k, v in stream.metadata.items()}
                    if stream.metadata
                    else {},
                )

                if stype == "video":
                    v_ctx = stream.codec_context
                    if v_ctx:
                        s_info.width = v_ctx.width
                        s_info.height = v_ctx.height
                        s_info.pix_fmt = getattr(v_ctx.pix_fmt, "name", str(v_ctx.pix_fmt))
                        if stream.average_rate:
                            s_info.fps = float(stream.average_rate)
                elif stype == "audio":
                    a_ctx = stream.codec_context
                    if a_ctx:
                        s_info.sample_rate = a_ctx.sample_rate
                        s_info.channels = a_ctx.channels
                        s_info.channel_layout = getattr(a_ctx.layout, "name", str(a_ctx.layout))

                streams_info.append(s_info)

            # Generate formatted overview text
            summary_lines = [
                f"File: {p.name} ({file_size // 1024} KB)",
                f"Format: {fmt_long} [{fmt_name}]",
                f"Duration: {duration_s:.2f}s | Bitrate: {bitrate // 1000} kbps",
                f"Streams ({len(streams_info)}):",
            ]
            for s in streams_info:
                if s.stream_type == "video":
                    summary_lines.append(
                        f"  #{s.index} Video: {s.codec_name} ({s.width}x{s.height}, {s.fps:.1f} fps, {s.pix_fmt})"
                    )
                elif s.stream_type == "audio":
                    summary_lines.append(
                        f"  #{s.index} Audio: {s.codec_name} ({s.channels}ch, {s.sample_rate} Hz, {s.channel_layout})"
                    )
                else:
                    summary_lines.append(
                        f"  #{s.index} {s.stream_type.title()}: {s.codec_name} [{s.language or 'und'}]"
                    )
            raw_dump = "\n".join(summary_lines)

        return MediaInfo(
            file_path=str(p.resolve()),
            file_name=p.name,
            file_size_bytes=file_size,
            duration_s=duration_s,
            bitrate=bitrate,
            format_name=fmt_name,
            format_long_name=fmt_long,
            streams=streams_info,
            metadata=metadata,
            raw_dump=raw_dump,
        )

    @staticmethod
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
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Transcode video/audio with quality, scaling, speed, volume, and rotation controls."""
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            in_audio = inp.streams.audio[0] if inp.streams.audio else None

            need_vfilter = rotation % 360 != 0 or abs(speed - 1.0) > 1e-6
            need_afilter = volume_pct != 100 or abs(speed - 1.0) > 1e-6
            video_graph: av.filter.Graph | None = None
            audio_graph: av.filter.Graph | None = None

            out_video = None
            if in_video:
                # Video stream setup
                target_fps = fps or int(in_video.average_rate or 30)
                out_fps = max(1, min(target_fps, 60))

                # Fallback to h264 if libx264 is unavailable
                chosen_vcodec = video_codec
                if chosen_vcodec == "libx264" and "libx264" not in av.codec.codecs_available:
                    chosen_vcodec = "h264"

                # setpts changes the effective frame rate (30fps sped 1.5x arrives
                # as 45fps); declare it so the encoder's DTS model matches reality.
                eff_rate = (
                    max(1, -(-int(round(out_fps * speed * 1000)) // 1000))
                    if need_vfilter and speed > 0
                    else out_fps
                )
                out_video = out.add_stream(chosen_vcodec, rate=eff_rate)
                target_w = scale_width or in_video.width
                target_h = scale_height or in_video.height
                if rotation % 180 == 90:  # 90°/270° transposes swap width/height
                    target_w, target_h = target_h, target_w
                # Dimensions must be even
                target_w = (target_w // 2) * 2
                target_h = (target_h // 2) * 2

                out_video.width = target_w
                out_video.height = target_h
                out_video.pix_fmt = "yuv420p"
                # With the filter graph active, timestamps arrive on the fine
                # 1/90000 tb with speed-warped spacing; bf=0 makes dts==pts so the
                # muxer sees the same strict sequence the graph produced.
                out_video.time_base = (
                    _FINE_VIDEO_TB if need_vfilter else Fraction(1, out_fps)
                )
                out_video.options = {"crf": str(crf), "preset": preset}
                if need_vfilter:
                    out_video.options["bf"] = "0"

            out_audio = None
            if in_audio:
                chosen_acodec = audio_codec
                out_audio = out.add_stream(chosen_acodec, rate=in_audio.rate or 44100)
                # PyAV 18: channels is read-only; layout is the writable source of truth
                n_ch = min(2, in_audio.channels or 2)
                out_audio.layout = "stereo" if n_ch == 2 else "mono"

            total_duration = float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
            last_report = 0.0
            processed_pts = 0.0

            streams_to_demux = [s for s in (in_video, in_audio) if s]

            for packet in inp.demux(streams_to_demux):
                if cancel_event and cancel_event.is_set():
                    logger.info("Transcode cancelled by user.")
                    break

                if packet.dts is None:
                    continue

                if in_video and packet.stream == in_video:
                    for frame in packet.decode():
                        if cancel_event and cancel_event.is_set():
                            break

                        # Progress reads the INPUT timeline (before setpts re-times frames)
                        if frame.time:
                            processed_pts = frame.time

                        if need_vfilter and video_graph is None:
                            video_graph = _build_video_filter_graph(frame, rotation, speed)

                        out_frames = [frame]
                        if video_graph is not None:
                            _rebase_pts(frame, _FINE_VIDEO_TB)
                            out_frames = _push_pull(video_graph, frame)

                        for frame in out_frames:
                            # Scale if needed
                            if out_video and (
                                frame.width != out_video.width
                                or frame.height != out_video.height
                                or frame.format.name != "yuv420p"
                            ):
                                frame = frame.reformat(
                                    width=out_video.width,
                                    height=out_video.height,
                                    format="yuv420p",
                                )

                            if out_video:
                                if video_graph is None:
                                    frame.pts = None  # let encoder handle sequential pts
                                for enc_pkt in out_video.encode(frame):
                                    out.mux(enc_pkt)

                elif in_audio and packet.stream == in_audio:
                    for frame in packet.decode():
                        if cancel_event and cancel_event.is_set():
                            break
                        if not out_audio:
                            continue
                        if need_afilter and audio_graph is None:
                            audio_graph = _build_audio_filter_graph(frame, volume_pct, speed)
                        out_frames = [frame]
                        if audio_graph is not None:
                            out_frames = _push_pull(audio_graph, frame)
                        for frame in out_frames:
                            if audio_graph is None:
                                frame.pts = None
                            for enc_pkt in out_audio.encode(frame):
                                out.mux(enc_pkt)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    progress = (
                        min(0.99, max(0.01, processed_pts / total_duration))
                        if total_duration > 0
                        else 0.5
                    )
                    on_progress(progress, f"Processing... {int(progress * 100)}%")

            # Drain filter graphs (EOF), then flush encoders
            if video_graph is not None and out_video:
                for frame in _drain_graph(video_graph):
                    if (
                        frame.width != out_video.width
                        or frame.height != out_video.height
                        or frame.format.name != "yuv420p"
                    ):
                        frame = frame.reformat(
                            width=out_video.width,
                            height=out_video.height,
                            format="yuv420p",
                        )
                    for enc_pkt in out_video.encode(frame):
                        out.mux(enc_pkt)
            if audio_graph is not None and out_audio:
                for frame in _drain_graph(audio_graph):
                    for enc_pkt in out_audio.encode(frame):
                        out.mux(enc_pkt)
            if out_video:
                for enc_pkt in out_video.encode(None):
                    out.mux(enc_pkt)
            if out_audio:
                for enc_pkt in out_audio.encode(None):
                    out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "Complete")

        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError as e:
                    logging.getLogger(__name__).warning("Failed to remove cancelled output: %s", e)
            raise InterruptedError("Transcoding was cancelled")

        return output_path

    @staticmethod
    def compress_to_target(
        input_path: str,
        output_path: str,
        target_size_mb: float,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Compress video to stay under a specified target file size (e.g. WhatsApp 16MB)."""
        info = EngineService.probe(input_path)
        duration = max(1.0, info.duration_s)
        target_bits = target_size_mb * 8 * 1024 * 1024 * 0.92  # 8% safety headroom
        total_bitrate = int(target_bits / duration)

        audio_bitrate = min(128000, max(64000, int(total_bitrate * 0.15)))
        video_bitrate = max(100000, total_bitrate - audio_bitrate)

        # Choose appropriate resolution downscale for low target bitrates
        scale_w = None
        scale_h = None
        v_stream = info.video_stream
        if v_stream and v_stream.width and v_stream.height:
            if video_bitrate < 400000:  # < 400kbps -> 480p
                if v_stream.width > 854:
                    scale_w = 854
                    scale_h = int(854 * (v_stream.height / v_stream.width))
            elif video_bitrate < 1000000:  # < 1Mbps -> 720p
                if v_stream.width > 1280:
                    scale_w = 1280
                    scale_h = int(1280 * (v_stream.height / v_stream.width))

        # Perform 1-pass constrained transcode with target bitrate
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            in_audio = inp.streams.audio[0] if inp.streams.audio else None

            out_video = None
            if in_video:
                fps = int(in_video.average_rate or 30)
                out_video = out.add_stream(
                    "libx264" if "libx264" in av.codec.codecs_available else "h264", rate=fps
                )
                target_w = (scale_w or in_video.width or 640) // 2 * 2
                target_h = (scale_h or in_video.height or 360) // 2 * 2
                out_video.width = target_w
                out_video.height = target_h
                out_video.pix_fmt = "yuv420p"
                out_video.time_base = Fraction(1, fps)
                out_video.bit_rate = video_bitrate
                out_video.max_bit_rate = int(video_bitrate * 1.3)
                out_video.options = {"preset": "fast"}

            out_audio = None
            if in_audio:
                out_audio = out.add_stream("aac", rate=in_audio.rate or 44100)
                out_audio.bit_rate = audio_bitrate
                out_audio.layout = "stereo"

            last_report = 0.0
            processed_pts = 0.0

            for packet in inp.demux([s for s in (in_video, in_audio) if s]):
                if cancel_event and cancel_event.is_set():
                    break
                if packet.dts is None:
                    continue

                if in_video and packet.stream == in_video:
                    for frame in packet.decode():
                        if cancel_event and cancel_event.is_set():
                            break
                        if out_video:
                            if (
                                frame.width != out_video.width
                                or frame.height != out_video.height
                                or frame.format.name != "yuv420p"
                            ):
                                frame = frame.reformat(
                                    width=out_video.width, height=out_video.height, format="yuv420p"
                                )
                            frame.pts = None
                            for enc_pkt in out_video.encode(frame):
                                out.mux(enc_pkt)
                        if frame.time:
                            processed_pts = frame.time

                elif in_audio and packet.stream == in_audio:
                    for frame in packet.decode():
                        if cancel_event and cancel_event.is_set():
                            break
                        if out_audio:
                            frame.pts = None
                            for enc_pkt in out_audio.encode(frame):
                                out.mux(enc_pkt)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, processed_pts / duration))
                    on_progress(prog, f"Compressing... {int(prog * 100)}%")

            if out_video:
                for enc_pkt in out_video.encode(None):
                    out.mux(enc_pkt)
            if out_audio:
                for enc_pkt in out_audio.encode(None):
                    out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "Compressed")
        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError as e:
                    logging.getLogger(__name__).warning("Failed to remove cancelled output: %s", e)
            raise InterruptedError("Compression cancelled")

        return output_path

    @staticmethod
    def cut_trim(
        input_path: str,
        output_path: str,
        start_seconds: float,
        end_seconds: float,
        stream_copy: bool = True,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Trim/cut a segment from media. Supports instant lossless copy or frame-accurate re-encode."""
        if stream_copy:
            return EngineService._cut_stream_copy(
                input_path, output_path, start_seconds, end_seconds, on_progress, cancel_event
            )
        return EngineService._cut_reencode(
            input_path, output_path, start_seconds, end_seconds, on_progress, cancel_event
        )

    @staticmethod
    def _cut_stream_copy(
        input_path: str,
        output_path: str,
        start_s: float,
        end_s: float,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            stream_map = {}
            for s in inp.streams:
                if s.type in ("video", "audio", "subtitle"):
                    out_s = out.add_stream_from_template(s, opaque=True)
                    stream_map[s] = out_s

            # Seek to start timestamp
            seek_target = int(start_s * av.time_base)
            inp.seek(seek_target, backward=True)

            duration = max(0.1, end_s - start_s)
            last_report = 0.0
            start_pts_map: dict[int, int] = {}

            for packet in inp.demux(list(stream_map.keys())):
                if cancel_event and cancel_event.is_set():
                    break
                if packet.pts is None:
                    continue

                pkt_time = float(packet.pts * packet.stream.time_base)
                if pkt_time < start_s:
                    continue
                if pkt_time > end_s:
                    break

                out_s = stream_map[packet.stream]
                # Rebase PTS/DTS to start at 0
                if packet.stream.index not in start_pts_map:
                    start_pts_map[packet.stream.index] = packet.pts

                base = start_pts_map[packet.stream.index]
                packet.pts = packet.pts - base
                if packet.dts is not None:
                    packet.dts = packet.dts - base
                packet.stream = out_s
                out.mux(packet)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, (pkt_time - start_s) / duration))
                    on_progress(prog, f"Copying cut... {int(prog * 100)}%")

            if on_progress:
                on_progress(1.0, "Cut Complete")
        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Cut was cancelled")

        return output_path

    @staticmethod
    def _cut_reencode(
        input_path: str,
        output_path: str,
        start_s: float,
        end_s: float,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            in_audio = inp.streams.audio[0] if inp.streams.audio else None

            out_video = None
            if in_video:
                fps = int(in_video.average_rate or 30)
                out_video = out.add_stream(
                    "libx264" if "libx264" in av.codec.codecs_available else "h264", rate=fps
                )
                out_video.width = in_video.width
                out_video.height = in_video.height
                out_video.pix_fmt = "yuv420p"
                out_video.time_base = Fraction(1, fps)
                out_video.options = {"crf": "20", "preset": "fast"}

            out_audio = None
            if in_audio:
                out_audio = out.add_stream("aac", rate=in_audio.rate or 44100)
                out_audio.layout = "stereo"

            # Seek close to start
            inp.seek(int(max(0.0, start_s - 2.0) * av.time_base), backward=True)
            duration = max(0.1, end_s - start_s)
            last_report = 0.0

            for packet in inp.demux([s for s in (in_video, in_audio) if s]):
                if cancel_event and cancel_event.is_set():
                    break

                if in_video and packet.stream == in_video:
                    for frame in packet.decode():
                        if frame.time is None or frame.time < start_s:
                            continue
                        if frame.time > end_s:
                            break
                        if out_video:
                            frame.pts = None
                            for enc_pkt in out_video.encode(frame):
                                out.mux(enc_pkt)
                        now = time.monotonic()
                        if on_progress and (now - last_report >= 0.25):
                            last_report = now
                            prog = min(0.99, max(0.01, (frame.time - start_s) / duration))
                            on_progress(prog, f"Encoding cut... {int(prog * 100)}%")

                elif in_audio and packet.stream == in_audio:
                    for frame in packet.decode():
                        if frame.time is None or frame.time < start_s:
                            continue
                        if frame.time > end_s:
                            break
                        if out_audio:
                            frame.pts = None
                            for enc_pkt in out_audio.encode(frame):
                                out.mux(enc_pkt)

            if out_video:
                for enc_pkt in out_video.encode(None):
                    out.mux(enc_pkt)
            if out_audio:
                for enc_pkt in out_audio.encode(None):
                    out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "Cut Complete")
        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Cut was cancelled")

        return output_path

    @staticmethod
    def _measure_loudnorm(input_path: str, target_lufs: float) -> dict[str, str]:
        """Pass 1 of two-pass loudnorm: measure integrated loudness as JSON stats.

        NOTE: ``av.filter.loudnorm.stats`` takes ownership of the format context it
        is given (it NULLs the Python wrapper's handle before the C pass), so this
        container is intentionally never closed — closing would double-free.
        """
        stats_container = av.open(input_path, "r")
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
            logger.warning(
                "Loudnorm measurement failed, falling back to dynamic mode: %s", exc
            )
            return {}

    @staticmethod
    def extract_audio(
        input_path: str,
        output_path: str,
        format_name: str = "mp3",  # mp3, aac, m4a, flac, opus, wav
        bitrate_kbps: int = 192,
        target_lufs: float | None = None,
        channels: int | None = None,
        sample_rate: int | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Extract audio with optional LUFS mastering, channel mix, and soxr resampling."""
        codec_map = {
            "mp3": "libmp3lame" if "libmp3lame" in av.codec.codecs_available else "mp3",
            "aac": "aac",
            "m4a": "aac",
            "flac": "flac",
            "opus": "libopus" if "libopus" in av.codec.codecs_available else "opus",
            "wav": "pcm_s16le",
        }

        # Two-pass loudnorm needs a full measurement pass before encoding starts.
        measured = (
            EngineService._measure_loudnorm(input_path, float(target_lufs))
            if target_lufs is not None
            else None
        )

        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_audio = inp.streams.audio[0] if inp.streams.audio else None
            if not in_audio:
                raise ValueError("No audio stream found in source media")

            chosen_codec = codec_map.get(format_name.lower(), "libmp3lame")
            out_rate = int(sample_rate) if sample_rate else (in_audio.rate or 44100)
            if channels in (1, 2):
                target_layout = "mono" if channels == 1 else "stereo"
            else:
                n_ch = min(2, in_audio.channels or 2)
                target_layout = "stereo" if n_ch == 2 else "mono"

            out_audio = out.add_stream(chosen_codec, rate=out_rate)
            if chosen_codec != "pcm_s16le":
                out_audio.bit_rate = bitrate_kbps * 1000
            out_audio.layout = target_layout

            # soxr-quality rate/layout conversion when this FFmpeg build has
            # libsoxr; otherwise _emit falls back to plain swr on first use.
            # The encoder's own resampler then passes through (it only ever
            # converts sample FORMAT).
            resampler = None
            src_rate = in_audio.rate or out_rate
            src_layout = getattr(in_audio.layout, "name", None)
            if src_rate != out_rate or (src_layout and src_layout != target_layout):
                resampler = av.AudioResampler(
                    layout=target_layout,
                    rate=out_rate,
                    options={"resampler": "soxr", "precision": "28"},
                )

            loud_graph: av.filter.Graph | None = None
            loud_args: str | None = None
            if target_lufs is not None:
                keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
                bad = {"inf", "-inf", "nan", ""} if measured else set()
                if measured and all(
                    k in measured and str(measured[k]).lower() not in bad for k in keys
                ):
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

            total_dur = float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
            last_report = 0.0
            cur_pts = 0.0

            def _encode(f: av.AudioFrame) -> None:
                f.pts = None  # encoder assigns sequential sample positions
                for enc_pkt in out_audio.encode(f):
                    out.mux(enc_pkt)

            def _emit(frames_list: list) -> None:
                nonlocal resampler
                for f in frames_list:
                    if resampler is not None:
                        try:
                            resampled = resampler.resample(f)
                        except FFmpegError as exc:
                            logger.warning(
                                "soxr resampler unavailable (%s); falling back to swr", exc
                            )
                            resampler = av.AudioResampler(
                                layout=target_layout, rate=out_rate
                            )
                            resampled = resampler.resample(f)
                        for rf in resampled:
                            _encode(rf)
                    else:
                        _encode(f)

            for packet in inp.demux([in_audio]):
                if cancel_event and cancel_event.is_set():
                    break
                for frame in packet.decode():
                    if cancel_event and cancel_event.is_set():
                        break
                    if frame.time:
                        cur_pts = frame.time
                    if loud_args is not None and loud_graph is None:
                        lg = av.filter.Graph()
                        ab_kwargs: dict = {
                            "sample_rate": frame.sample_rate,
                            "format": frame.format.name,
                            "layout": frame.layout.name,
                        }
                        if frame.time_base is not None:
                            ab_kwargs["time_base"] = frame.time_base
                        src = lg.add_abuffer(**ab_kwargs)
                        ln = lg.add("loudnorm", loud_args)
                        sink = lg.add("abuffersink")
                        lg.link_nodes(src, ln, sink)
                        lg.configure()
                        loud_graph = lg
                    if loud_graph is not None:
                        _emit(_push_pull(loud_graph, frame))
                    else:
                        _emit([frame])

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, cur_pts / total_dur))
                    on_progress(prog, f"Extracting Audio... {int(prog * 100)}%")

            # Flush: loudnorm graph → soxr resampler → encoder
            if loud_graph is not None:
                for f in _drain_graph(loud_graph):
                    _emit([f])
            if resampler is not None:
                for rf in resampler.resample(None):
                    _encode(rf)
            for enc_pkt in out_audio.encode(None):
                out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "Audio Extracted")
        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Audio extraction cancelled")

        return output_path

    @staticmethod
    def extract_frames(
        input_path: str,
        output_dir: str,
        count: int = 5,
        format_name: str = "jpg",
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> list[str]:
        """Extract evenly-spaced frames in a single decode pass into an image directory."""
        info = EngineService.probe(input_path)
        duration = max(0.1, info.duration_s)
        count = max(1, count)
        timestamps = sorted(duration * (i + 1) / (count + 1) for i in range(count))
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        out_paths: list[str] = []
        total = len(timestamps)
        idx = 0

        inp = av.open(input_path, "r")
        try:
            v_stream = inp.streams.video[0] if inp.streams.video else None
            if not v_stream:
                raise ValueError("No video stream found in source media")

            # One seek to the first target, then decode forward through all of them
            inp.seek(int(timestamps[0] * av.time_base), backward=True)
            done = False
            for packet in inp.demux([v_stream]):
                if cancel_event and cancel_event.is_set():
                    break
                for frame in packet.decode():
                    t = frame.time
                    while idx < total and t is not None and t >= timestamps[idx]:
                        ts = timestamps[idx]
                        frame_path = str(
                            out_p / f"frame_{idx + 1:03d}_{int(ts)}s.{format_name}"
                        )
                        try:
                            frame.save(frame_path)
                        except Exception as save_err:
                            logger.debug(
                                "Direct save failed, reformatting for %s: %s",
                                frame_path,
                                save_err,
                            )
                            frame.reformat(format="bgr24").save(frame_path)
                        out_paths.append(frame_path)
                        idx += 1
                        if on_progress:
                            on_progress(idx / total, f"Extracted frame {idx} of {total}")
                        if idx >= total:
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
        finally:
            inp.close()

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_dir, directory=True)
            raise InterruptedError("Frame extraction cancelled")

        return out_paths

    @staticmethod
    def create_gif(
        input_path: str,
        output_path: str,
        fps: int = 15,
        width: int = 480,
        start_s: float = 0.0,
        duration_s: float = 5.0,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Generate a palette-optimized animated GIF from a video segment.

        Uses a single split graph (fps → scale → split → palettegen | paletteuse)
        so every frame is dithered against the segment-wide palette; falls back to
        a direct rgb8 encode if the palette filters are unavailable on this build.
        """
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w", format="gif")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            if not in_video:
                raise ValueError("No video stream found")

            out_fps = max(1, min(fps, 30))
            out_video = out.add_stream("gif", rate=out_fps)
            out_w = int(width)
            out_h = max(1, int(out_w * ((in_video.height or 1) / (in_video.width or 1))))
            out_video.width = out_w
            out_video.height = out_h
            out_video.pix_fmt = "rgb8"
            out_video.time_base = Fraction(1, out_fps)

            graph: av.filter.Graph | None = None
            palette_mode = True  # until the first frame proves otherwise
            pushed = 0
            last_report = 0.0

            def _direct_encode(frame: av.VideoFrame) -> None:
                rf = frame.reformat(width=out_w, height=out_h, format="rgb8")
                rf.pts = None
                for enc_pkt in out_video.encode(rf):
                    out.mux(enc_pkt)

            inp.seek(int(start_s * av.time_base), backward=True)
            end_s = start_s + duration_s

            for packet in inp.demux([in_video]):
                if cancel_event and cancel_event.is_set():
                    break
                segment_done = False
                for frame in packet.decode():
                    if frame.time is None or frame.time < start_s:
                        continue
                    if frame.time > end_s:
                        segment_done = True
                        break

                    if palette_mode and graph is None:
                        try:
                            g = av.filter.Graph()
                            src = g.add_buffer(template=frame)
                            fps_f = g.add("fps", str(out_fps))
                            scale_f = g.add("scale", f"{out_w}:{out_h}")
                            split_f = g.add("split")
                            pgen = g.add("palettegen")
                            puse = g.add("paletteuse")
                            sink = g.add("buffersink")
                            g.link_nodes(src, fps_f, scale_f, split_f)
                            split_f.link_to(pgen, output_idx=0, input_idx=0)
                            split_f.link_to(puse, output_idx=1, input_idx=0)
                            pgen.link_to(puse, output_idx=0, input_idx=1)
                            puse.link_to(sink, output_idx=0, input_idx=0)
                            g.configure()
                            graph = g
                        except Exception as exc:
                            logger.warning(
                                "Palette GIF graph unavailable (%s); "
                                "falling back to direct GIF encode",
                                exc,
                            )
                            palette_mode = False

                    if graph is not None:
                        graph.push(frame)
                        pushed += 1
                    else:
                        _direct_encode(frame)
                        pushed += 1

                    now = time.monotonic()
                    if on_progress and (now - last_report >= 0.25):
                        last_report = now
                        prog = min(0.85, 0.85 * (frame.time - start_s) / max(0.1, duration_s))
                        on_progress(prog, f"Creating GIF... {int(prog * 100)}%")
                if segment_done:
                    break

            if cancel_event and cancel_event.is_set():
                raise InterruptedError("cancelled")

            if graph is not None:
                drained = 0
                for rf in _drain_graph(graph):
                    if rf.width != out_w or rf.height != out_h or rf.format.name != "rgb8":
                        rf = rf.reformat(width=out_w, height=out_h, format="rgb8")
                    rf.pts = None
                    for enc_pkt in out_video.encode(rf):
                        out.mux(enc_pkt)
                    drained += 1
                    if on_progress:
                        frac = min(1.0, drained / max(1, pushed))
                        on_progress(
                            min(0.99, 0.85 + 0.14 * frac),
                            f"Creating GIF... {int(min(0.99, 0.85 + 0.14 * frac) * 100)}%",
                        )

            for enc_pkt in out_video.encode(None):
                out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "GIF Created")
        finally:
            inp.close()
            out.close()

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("GIF creation cancelled")

        return output_path
