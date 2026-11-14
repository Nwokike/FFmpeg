"""Frames, GIFs, subtitles, thumbnails, keyframes."""

from __future__ import annotations

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
from services.engine_service.graphs import _mjpeg_bytes
from services.engine_service.logs import _INPUT_OPTIONS, _INPUT_TIMEOUT, _decode_packet, logger
from services.engine_service.options import _supported_encoder_options
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
    encoder_options: dict | None = None,
    container_options: dict | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Generate a palette-optimized animated GIF from a video segment.

    ``encoder_options`` reach the gif encoder (lossy LZW/palette knobs);
    ``container_options`` reach the muxer.
    """
    info = probe_media(input_path)
    if info.video_stream is None:
        raise ValueError("No video stream found")
    vs = info.video_stream
    out_fps = max(1, min(int(fps), 30))
    out_w = int(width)
    out_h = max(1, int(out_w * ((vs.height or 1) / (vs.width or 1))))
    end_s = start_s + duration_s

    def _palette_chain_build(frame):
        g = av.filter.Graph()
        try:
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
            options=dict(container_options or {}),
        ),
        video_chain=FilterChain(build=_palette_chain_build),
        window=(start_s, end_s),
        progress_label="Creating GIF",
        complete_label="GIF Created",
        cancel_message="GIF creation cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)


def extract_subtitles(
    input_path: str,
    output_path: str,
    stream_index: int = 0,
    format_name: str = "srt",
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Extract a text subtitle stream to SRT/ASS/WebVTT via hand writers.

    Timing comes from SubtitleSet empirically verified on this build:
    ``pts`` is microseconds (AV_TIME_BASE), ``start_display_time`` is a
    millisecond offset, and ``end_display_time`` is a millisecond DURATION.
    Bitmap (image-based) subtitle tracks raise a clear error — OCR is out
    of scope. Writers are plain text, so no muxer availability gate.
    """
    writers = {"srt": _write_srt, "ass": _write_ass, "webvtt": _write_vtt, "vtt": _write_vtt}
    writer = writers.get(format_name.lower())
    if writer is None:
        raise ValueError(f"Unsupported subtitle format: {format_name}")

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
        cancelled = False
        for pkt in inp.demux([sub]):
            _pause_hook(cancel_event)
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
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

            if on_progress and len(cues) % 25 == 0:
                on_progress(0.5, f"Extracted {len(cues)} cues…")

        if cancelled:
            raise InterruptedError("Subtitle extraction cancelled")

        if not cues:
            raise ValueError("No text cues found in that subtitle stream")

        writer(output_path, cues)
        if on_progress:
            on_progress(1.0, f"Wrote {len(cues)} cues")
    finally:
        _close_container(inp)

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
