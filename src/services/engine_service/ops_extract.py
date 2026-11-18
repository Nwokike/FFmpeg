"""Frames, GIFs, subtitles, thumbnails, keyframes."""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Callable
from pathlib import Path
from threading import Event

import av

from core.storage_paths import get_cache_dir
from services.engine_service.builders import (
    _discard_cancelled,
    _pause_hook,
    probe_media,
    run_encode_job,
)
from services.engine_service.graphs import _mjpeg_bytes, available_filters
from services.engine_service.logs import _INPUT_OPTIONS, _INPUT_TIMEOUT, _decode_packet, logger
from services.engine_service.options import _pick_video_encoder, _supported_encoder_options
from services.engine_service.resolve import _resolve_or_raw
from services.engine_service.safety import _close_container, _safe_seek
from services.engine_service.subtitles import SubCue, _write_ass, _write_srt, _write_vtt
from services.job_model import FilterChain, InputSpec, Job, OutputSpec, StreamSpec


def extract_frames(
    input_path: str,
    output_dir: str,
    count: int = 5,
    format_name: str = "jpg",
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> list[str]:
    """Extract evenly-spaced frames in a single decode pass into an image directory."""
    info = probe_media(input_path)
    duration = max(0.1, info.duration_s)
    count = max(1, count)
    timestamps = sorted(duration * (i + 1) / (count + 1) for i in range(count))
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    out_paths: list[str] = []
    total = len(timestamps)
    idx = 0

    inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    try:
        v_stream = inp.streams.best("video")
        if not v_stream:
            raise ValueError("No video stream found in source media")

        # One seek to the first target, then decode forward through all of them
        _safe_seek(inp, int(timestamps[0] * av.time_base))
        done = False
        for packet in inp.demux([v_stream]):
            _pause_hook(cancel_event)
            if cancel_event and cancel_event.is_set():
                break
            for frame in _decode_packet(packet):
                t = frame.time
                while idx < total and t is not None and t >= timestamps[idx]:
                    ts = timestamps[idx]
                    frame_path = str(out_p / f"frame_{idx + 1:03d}_{int(ts)}s.{format_name}")
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
        _close_container(inp)

    if cancel_event and cancel_event.is_set():
        _discard_cancelled(output_dir, directory=True)
        raise InterruptedError("Frame extraction cancelled")

    return out_paths


def create_gif(
    input_path: str,
    output_path: str,
    fps: int = 15,
    width: int = 480,
    start_s: float = 0.0,
    duration_s: float = 5.0,
    colors: int | None = None,
    dither: str | None = None,
    loop_count: int | None = None,
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Generate a palette-optimized animated GIF from a video segment.

    ``colors`` caps the palette (2-256), ``dither`` selects paletteuse's
    dithering (e.g. "bayer", "none"), ``loop_count`` sets the GIF loop count
    (0 = forever). ``encoder_options`` reach the gif encoder (lossy LZW/
    palette knobs); ``container_options`` reach the muxer.
    """
    info = probe_media(input_path)
    if info.video_stream is None:
        raise ValueError("No video stream found")
    vs = info.video_stream
    out_fps = max(1, min(int(fps), 30))
    out_w = int(width)
    out_h = max(1, int(out_w * ((vs.height or 1) / (vs.width or 1))))
    end_s = start_s + duration_s

    palette_args = None
    if colors:
        palette_args = f"max_colors={max(2, min(int(colors), 256))}"
    use_args = None
    if dither:
        use_args = f"dither={dither}"
    mux_options = dict(container_options or {})
    if loop_count is not None:
        mux_options.setdefault("loop", str(int(loop_count)))

    def _palette_chain_build(frame):
        g = av.filter.Graph()
        try:
            src = g.add_buffer(template=frame)
            fps_f = g.add("fps", str(out_fps))
            scale_f = g.add("scale", f"{out_w}:{out_h}")
            split_f = g.add("split")
            pgen = g.add("palettegen", palette_args) if palette_args else g.add("palettegen")
            puse = g.add("paletteuse", use_args) if use_args else g.add("paletteuse")
            sink = g.add("buffersink")
            g.link_nodes(src, fps_f, scale_f, split_f)
            split_f.link_to(pgen, output_idx=0, input_idx=0)
            split_f.link_to(puse, output_idx=1, input_idx=0)
            pgen.link_to(puse, output_idx=0, input_idx=1)
            puse.link_to(sink, output_idx=0, input_idx=0)
            g.configure()
            return g
        except Exception as exc:
            logger.warning(
                "Palette GIF graph unavailable (%s); falling back to direct GIF encode",
                exc,
            )
            return None

    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path, seek_s=start_s)],
        streams=[
            StreamSpec(
                kind="video",
                codec="gif",
                fps=out_fps,
                cap_fps=False,
                pix_fmt="rgb8",
                scale_width=out_w,
                scale_height=out_h,
                even_align=False,
                pts_policy="encoder",
                encoder_options=_supported_encoder_options("gif", dict(encoder_options or {})),
            )
        ],
        output=OutputSpec(
            container="gif",
            metadata=False,
            chapters=False,
            options=mux_options,
        ),
        video_chain=FilterChain(build=_palette_chain_build),
        window=(start_s, end_s),
        progress_label="Creating GIF",
        complete_label="GIF Created",
        cancel_message="GIF creation cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)


_SEQUENCE_CODECS = {
    "png": ("png", "rgb24"),
    "jpg": ("mjpeg", "yuvj420p"),
    "jpeg": ("mjpeg", "yuvj420p"),
}


def export_sequence(
    input_path: str,
    output_dir: str,
    *,
    fmt: str = "png",
    every_n: int = 1,
    start_s: float = 0.0,
    end_s: float | None = None,
    width: int | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Export decoded frames as a numbered image sequence (image2 muxer).

    ``every_n`` keeps one frame out of every N decoded frames; ``width``
    scales (aspect preserved). Returns the pattern the files were written to.
    """
    codec_map = _SEQUENCE_CODECS.get(fmt.lower())
    if codec_map is None:
        raise ValueError(f"Unsupported sequence format: {fmt} (use png or jpg)")
    codec, pix_fmt = codec_map
    if codec not in av.codecs_available:
        raise ValueError(f"This build cannot encode {fmt}")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if codec == "mjpeg" else "png"
    pattern = str(out_dir / f"frame_%05d.{ext}")

    info = probe_media(input_path)
    if info.video_stream is None:
        raise ValueError("No video stream found")
    vs = info.video_stream
    duration = info.duration_s or 0.0
    stop = min(end_s, duration) if end_s is not None else duration
    every_n = max(1, int(every_n))

    inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    out = av.open(pattern, "w", format="image2")
    try:
        src = inp.streams.video[0]
        stream = out.add_stream(codec)
        stream.pix_fmt = pix_fmt
        if width:
            stream.width = int(width)
            stream.height = max(1, round(int(width) * (vs.height or 1) / (vs.width or 1)))
        else:
            stream.width = src.codec_context.width
            stream.height = src.codec_context.height
        if start_s > 0:
            _safe_seek(inp, int(start_s * av.time_base))
        kept = 0
        seen = 0
        for frame in inp.decode(src):
            _pause_hook(cancel_event)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Sequence export cancelled")
            t = float(frame.time or 0.0)
            if t < start_s - 0.05:
                continue
            if stop and t > stop:
                break
            seen += 1
            if (seen - 1) % every_n:
                continue
            if width:
                frame = frame.reformat(width=stream.width, height=stream.height)
            frame.pts = None
            for pkt in stream.encode(frame):
                out.mux(pkt)
            kept += 1
            if on_progress and kept % 10 == 0:
                total = max(1, int(((stop or duration) - start_s) * (vs.fps or 25) / every_n))
                on_progress(min(0.99, kept / total), f"Exported {kept} frames…")
        for pkt in stream.encode(None):
            out.mux(pkt)
    finally:
        _close_container(out)
        _close_container(inp)
    if on_progress:
        on_progress(1.0, f"Exported {kept} frames")
    return pattern


def sequence_to_video(
    pattern: str,
    output_path: str,
    *,
    fps: int = 25,
    video_codec: str | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Encode an image sequence (``frame_%05d.png``) into a video."""
    if not any(ch in pattern for ch in "%"):
        raise ValueError("The sequence needs a numbered pattern such as frame_%05d.png")
    fps = max(1, min(int(fps), 120))
    chosen = _resolve_or_raw(video_codec, "video") if video_codec else _pick_video_encoder()
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=pattern, format="image2", options={"framerate": str(fps)})],
        streams=[StreamSpec(kind="video", codec=chosen, fps=fps, cap_fps=False)],
        output=OutputSpec(options=dict(container_options or {})),
        progress_label="Encoding sequence",
        complete_label="Sequence encoded",
        cancel_message="Sequence encode cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)


def thumbnail_sheet(
    input_path: str,
    output_path: str,
    *,
    cols: int = 4,
    rows: int = 3,
    width: int = 160,
    start_s: float | None = None,
    end_s: float | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Compose a contact sheet (cols x rows thumbnails) into one image.

    Uses the ``tile`` filter: an fps sampler picks exactly cols*rows frames
    across the window, each is scaled to ``width``, and tile assembles them.
    """
    if "tile" not in available_filters():
        raise ValueError("This build has no tile filter — contact sheets are unavailable")
    if "png" not in av.codecs_available:
        raise ValueError("This build cannot encode the PNG sheet")
    info = probe_media(input_path)
    if info.video_stream is None:
        raise ValueError("No video stream found")
    duration = info.duration_s or 0.0
    start = 0.0 if start_s is None else max(0.0, float(start_s))
    end = min(end_s, duration) if end_s is not None else duration
    span = max(0.5, end - start)
    count = max(1, int(cols) * int(rows))
    thumb_w = int(width)
    vs = info.video_stream
    thumb_h = max(1, round(thumb_w * (vs.height or 1) / (vs.width or 1)))
    nodes = [
        ("fps", f"{count / span:.6f}"),
        ("scale", f"{thumb_w}:{thumb_h}"),
        ("tile", f"{int(cols)}x{int(rows)}"),
    ]
    # image2 requires a numbered pattern (a plain filename fails write_header),
    # and a rounding surplus can emit an extra grid. Write to an internal
    # pattern, then keep the first sheet under the caller's exact path.
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix or ".png"
    pattern = str(out_path.with_name(f"{out_path.stem}_%03d{suffix}"))
    job = Job(
        output_path=pattern,
        inputs=[InputSpec(path=input_path)],
        streams=[
            StreamSpec(
                kind="video",
                codec="png",
                pix_fmt="rgb24",
                # The sheet is exactly the tile grid; declaring it lets the
                # encoder open at the final size instead of the input size.
                scale_width=thumb_w * int(cols),
                scale_height=thumb_h * int(rows),
                even_align=False,
                cap_fps=False,
            )
        ],
        output=OutputSpec(container="image2", metadata=False, chapters=False),
        video_chain=FilterChain(nodes=nodes),
        window=(start, end),
        progress_label="Building contact sheet",
        complete_label="Sheet ready",
        cancel_message="Sheet cancelled",
    )
    run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)
    sheets = sorted(out_path.parent.glob(f"{out_path.stem}_*{suffix}"))
    if not sheets:
        raise ValueError("The sheet produced no image")
    Path(sheets[0]).replace(out_path)
    for extra in sheets[1:]:
        with contextlib.suppress(OSError):
            Path(extra).unlink()
    return str(out_path)


def read_cues(
    input_path: str,
    stream_index: int = 0,
    cancel_event: Event | None = None,
) -> list[SubCue]:
    """Every text cue of a media file or subtitle sidecar (SRT/ASS/VTT).

    Works for embedded subtitle streams and for sidecar files alike: PyAV
    opens both and ``SubtitleSet`` decoding is identical. Bitmap tracks raise
    the same loud error extraction does (OCR is out of scope).
    """
    inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    try:
        subs = inp.streams.subtitles
        if not subs:
            raise ValueError("This file has no subtitle streams to extract")
        if stream_index < 0 or stream_index >= len(subs):
            logger.warning(
                "Subtitle stream index %d out of range (%d streams) — using first",
                stream_index,
                len(subs),
            )
            stream_index = 0
        sub = subs[stream_index]
        cues: list[SubCue] = []
        for pkt in inp.demux([sub]):
            _pause_hook(cancel_event)
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Subtitle read cancelled")
            if pkt.size == 0:
                continue
            ss = sub.codec_context.decode2(pkt)
            if ss is None:
                continue
            text_parts: list[str] = []
            for rect in ss.rects:
                if getattr(rect, "type", None) == b"bitmap":
                    raise ValueError(
                        "This track has image-based subtitles (PGS/VobSub) — "
                        "text extraction needs OCR, which isn't supported"
                    )
                dialogue = getattr(rect, "dialogue", None)
                if dialogue:
                    text_parts.append(
                        dialogue.decode("utf-8", errors="replace")
                        if isinstance(dialogue, bytes)
                        else str(dialogue)
                    )
            if not text_parts:
                continue
            start_s = (ss.pts or 0) / 1_000_000 + (ss.start_display_time or 0) / 1000
            dur_s = (ss.end_display_time or 0) / 1000
            if dur_s <= 0:
                logger.debug("Cue without duration at %.2fs — defaulting to 2s", start_s)
                dur_s = 2.0
            cues.append(SubCue(start_s=start_s, end_s=start_s + dur_s, text="\n".join(text_parts)))
        return cues
    finally:
        _close_container(inp)


def extract_subtitles(
    input_path: str,
    output_path: str,
    stream_index: int = 0,
    format_name: str = "srt",
    shift_s: float = 0.0,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Extract a text subtitle stream to SRT/ASS/WebVTT via hand writers.

    Timing comes from SubtitleSet empirically verified on this build:
    ``pts`` is microseconds (AV_TIME_BASE), ``start_display_time`` is a
    millisecond offset, and ``end_display_time`` is a millisecond DURATION.
    Bitmap (image-based) subtitle tracks raise a clear error — OCR is out
    of scope. Writers are plain text, so no muxer availability gate.
    ``shift_s`` moves every cue by that many seconds (negative = earlier,
    clamped at 0) — the app's subtitle-sync control.
    """
    writers = {"srt": _write_srt, "ass": _write_ass, "webvtt": _write_vtt, "vtt": _write_vtt}
    writer = writers.get(format_name.lower())
    if writer is None:
        raise ValueError(f"Unsupported subtitle format: {format_name}")

    cues = read_cues(input_path, stream_index, cancel_event)
    if shift_s:
        cues = [
            SubCue(
                start_s=max(0.0, c.start_s + shift_s),
                end_s=max(0.0, c.end_s + shift_s),
                text=c.text,
            )
            for c in cues
        ]
    if not cues:
        raise ValueError("No text cues found in that subtitle stream")

    writer(output_path, cues)
    if on_progress:
        on_progress(1.0, f"Wrote {len(cues)} cues")

    if cancel_event and cancel_event.is_set():
        _discard_cancelled(output_path)
        raise InterruptedError("Subtitle extraction cancelled")

    return output_path


def thumbnail_strip(input_path: str, times: list[float], width: int = 96) -> list[bytes]:
    """JPEG bytes for each timestamp — single decode pass, in-memory.

    Missing timestamps are skipped, so the result may be shorter than
    ``times``; order of successes follows the requested order.
    """
    if not times:
        return []
    # CACHE read-through: keyed on file identity (path + mtime_ns + size)
    # and the exact request — Cut-screen revisits load instantly; only a
    # complete strip is written back, so partial failures re-decode.
    cache_dir: Path | None = None
    try:
        st = Path(input_path).stat()
        sig = f"{input_path}|{st.st_mtime_ns}|{st.st_size}|{width}|{times}"
        key = hashlib.sha256(sig.encode()).hexdigest()[:16]
        cache_dir = get_cache_dir() / f"thumbs_{key}"
        hits = [cache_dir / f"{i:02d}.jpg" for i in range(len(times))]
        if all(f.is_file() for f in hits):
            return [f.read_bytes() for f in hits]
    except OSError as exc:
        logger.warning("Thumbnail cache read failed: %s", exc)
        cache_dir = None
    order = sorted(range(len(times)), key=lambda i: times[i])
    results: dict[int, bytes] = {}
    inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
    try:
        v = inp.streams.best("video")
        if not v:
            return []
        _safe_seek(inp, int(max(0.0, times[order[0]] - 1.0) * av.time_base))
        idx = 0
        done = False
        for packet in inp.demux([v]):
            for frame in _decode_packet(packet):
                t = frame.time
                while idx < len(order) and t is not None and t >= times[order[idx]]:
                    try:
                        results[order[idx]] = _mjpeg_bytes(frame, width)
                    except Exception as exc:
                        logger.warning("Thumb at %.2fs failed: %s", times[order[idx]], exc)
                    idx += 1
                    if idx >= len(order):
                        done = True
                        break
                if done:
                    break
            if done:
                break
    finally:
        _close_container(inp)
    ordered = [results[i] for i in range(len(times)) if i in results]
    if cache_dir is not None and len(ordered) == len(times):
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            for i, data in enumerate(ordered):
                (cache_dir / f"{i:02d}.jpg").write_bytes(data)
        except OSError as exc:
            logger.warning("Thumbnail cache write failed: %s", exc)
    return ordered


def keyframe_times(input_path: str, limit: int = 24) -> list[float]:
    """Keyframe timestamps in seconds (sampled to ``limit``), ascending.

    Drives the Cut screen's keyframe jump chips; empty list when the
    container has no usable index (MPEG-TS etc.) — UI degrades gracefully.
    Negative index entries (edit-list offsets, measured -0.08s on a real
    mp4) are floored at 0.0 — chips seek to a time the player can show.
    """
    try:
        with av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS) as inp:
            v = inp.streams.best("video")
            if v is None:
                return []
            entries = v.index_entries
            if not entries:
                return []
            keys = [e for e in entries if e.is_keyframe]
            if not keys:
                return []
            step = max(1, len(keys) // max(1, limit))
            sampled = keys[::step][:limit]
            tb = v.time_base
            return sorted(max(0.0, float(e.timestamp * tb)) for e in sampled)
    except Exception as exc:
        logger.warning("Keyframe index unavailable: %s", exc)
        return []
