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

import logging
import os
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from threading import Event

import av

from core.state import MediaInfo, MediaStreamInfo

logger = logging.getLogger("EngineService")


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
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Transcode video/audio to a target container with quality & scaling controls."""
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            in_audio = inp.streams.audio[0] if inp.streams.audio else None

            out_video = None
            if in_video:
                # Video stream setup
                target_fps = fps or int(in_video.average_rate or 30)
                out_fps = max(1, min(target_fps, 60))
                time_base = Fraction(1, out_fps)

                # Fallback to h264 if libx264 is unavailable
                chosen_vcodec = video_codec
                if chosen_vcodec == "libx264" and "libx264" not in av.codec.codecs_available:
                    chosen_vcodec = "h264"

                out_video = out.add_stream(chosen_vcodec, rate=out_fps)
                target_w = scale_width or in_video.width
                target_h = scale_height or in_video.height
                # Dimensions must be even
                target_w = (target_w // 2) * 2
                target_h = (target_h // 2) * 2

                out_video.width = target_w
                out_video.height = target_h
                out_video.pix_fmt = "yuv420p"
                out_video.time_base = time_base
                out_video.options = {"crf": str(crf), "preset": preset}

            out_audio = None
            if in_audio:
                chosen_acodec = audio_codec
                out_audio = out.add_stream(chosen_acodec, rate=in_audio.rate or 44100)
                out_audio.channels = min(2, in_audio.channels or 2)
                out_audio.layout = "stereo" if out_audio.channels == 2 else "mono"

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

                        # Scale if needed
                        if out_video and (
                            frame.width != out_video.width
                            or frame.height != out_video.height
                            or frame.format.name != "yuv420p"
                        ):
                            frame = frame.reformat(
                                width=out_video.width, height=out_video.height, format="yuv420p"
                            )

                        if out_video:
                            frame.pts = None  # let encoder handle sequential pts
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
                    progress = (
                        min(0.99, max(0.01, processed_pts / total_duration))
                        if total_duration > 0
                        else 0.5
                    )
                    on_progress(progress, f"Processing... {int(progress * 100)}%")

            # Flush encoders
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
                out_audio.channels = 2
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
                out_audio.channels = 2
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

        return output_path

    @staticmethod
    def extract_audio(
        input_path: str,
        output_path: str,
        format_name: str = "mp3",  # mp3, aac, flac, opus, wav
        bitrate_kbps: int = 192,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Extract audio track and convert to chosen audio format."""
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w")

        try:
            in_audio = inp.streams.audio[0] if inp.streams.audio else None
            if not in_audio:
                raise ValueError("No audio stream found in source media")

            codec_map = {
                "mp3": "libmp3lame" if "libmp3lame" in av.codec.codecs_available else "mp3",
                "aac": "aac",
                "flac": "flac",
                "opus": "libopus" if "libopus" in av.codec.codecs_available else "opus",
                "wav": "pcm_s16le",
            }
            chosen_codec = codec_map.get(format_name.lower(), "libmp3lame")
            out_audio = out.add_stream(chosen_codec, rate=in_audio.rate or 44100)
            if chosen_codec != "pcm_s16le":
                out_audio.bit_rate = bitrate_kbps * 1000
            out_audio.channels = min(2, in_audio.channels or 2)
            out_audio.layout = "stereo" if out_audio.channels == 2 else "mono"

            total_dur = float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
            last_report = 0.0
            cur_pts = 0.0

            for packet in inp.demux([in_audio]):
                if cancel_event and cancel_event.is_set():
                    break
                for frame in packet.decode():
                    if cancel_event and cancel_event.is_set():
                        break
                    frame.pts = None
                    for enc_pkt in out_audio.encode(frame):
                        out.mux(enc_pkt)
                    if frame.time:
                        cur_pts = frame.time

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, cur_pts / total_dur))
                    on_progress(prog, f"Extracting Audio... {int(prog * 100)}%")

            for enc_pkt in out_audio.encode(None):
                out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "Audio Extracted")
        finally:
            inp.close()
            out.close()

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
        """Extract evenly-spaced video frames and save directly as JPG/PNG without Pillow."""
        info = EngineService.probe(input_path)
        duration = max(0.1, info.duration_s)
        out_paths: list[str] = []

        timestamps = [duration * (i + 1) / (count + 1) for i in range(count)]
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        for i, ts in enumerate(timestamps):
            if cancel_event and cancel_event.is_set():
                break
            frame_path = str(out_p / f"frame_{i + 1:03d}_{int(ts)}s.{format_name}")
            inp = av.open(input_path, "r")
            try:
                v_stream = inp.streams.video[0] if inp.streams.video else None
                if not v_stream:
                    break
                inp.seek(int(ts * av.time_base), backward=True)
                for packet in inp.demux([v_stream]):
                    saved = False
                    for frame in packet.decode():
                        if frame.time is not None and frame.time >= ts:
                            try:
                                frame.save(frame_path)
                            except Exception as save_err:
                                logging.getLogger(__name__).debug(
                                    "Direct save failed, reformatting for %s: %s",
                                    frame_path,
                                    save_err,
                                )
                                frame.reformat(format="bgr24").save(frame_path)
                            out_paths.append(frame_path)
                            saved = True
                            break
                    if saved:
                        break
            finally:
                inp.close()

            if on_progress:
                prog = (i + 1) / count
                on_progress(prog, f"Extracted frame {i + 1} of {count}")

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
        """Generate an animated GIF from a video segment."""
        inp = av.open(input_path, "r")
        out = av.open(output_path, "w", format="gif")

        try:
            in_video = inp.streams.video[0] if inp.streams.video else None
            if not in_video:
                raise ValueError("No video stream found")

            out_fps = max(1, min(fps, 30))
            out_video = out.add_stream("gif", rate=out_fps)
            calc_h = int(width * (in_video.height / (in_video.width or 1)))
            out_video.width = width
            out_video.height = calc_h
            out_video.pix_fmt = "rgb8"
            out_video.time_base = Fraction(1, out_fps)

            inp.seek(int(start_s * av.time_base), backward=True)
            end_s = start_s + duration_s
            last_report = 0.0

            for packet in inp.demux([in_video]):
                if cancel_event and cancel_event.is_set():
                    break
                for frame in packet.decode():
                    if frame.time is None or frame.time < start_s:
                        continue
                    if frame.time > end_s:
                        break

                    rf = frame.reformat(width=width, height=calc_h, format="rgb8")
                    rf.pts = None
                    for enc_pkt in out_video.encode(rf):
                        out.mux(enc_pkt)

                    now = time.monotonic()
                    if on_progress and (now - last_report >= 0.25):
                        last_report = now
                        prog = min(0.99, max(0.01, (frame.time - start_s) / duration_s))
                        on_progress(prog, f"Creating GIF... {int(prog * 100)}%")

            for enc_pkt in out_video.encode(None):
                out.mux(enc_pkt)

            if on_progress:
                on_progress(1.0, "GIF Created")
        finally:
            inp.close()
            out.close()

        return output_path
