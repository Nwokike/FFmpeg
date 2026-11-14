"""Remux, concat, crossfade."""

from __future__ import annotations

from collections.abc import Callable
from errno import EAGAIN
from fractions import Fraction
from threading import Event

import av
from av.error import FFmpegError

from core.state import MediaInfo
from services.engine_service.builders import (
    _discard_cancelled,
    _pause_hook,
    probe_media,
    run_copy_job,
    run_encode_job,
)
from services.engine_service.capability import _encoder_pix_fmt
from services.engine_service.logs import _INPUT_TIMEOUT, _decode_packet, logger
from services.engine_service.options import _pick_video_encoder, _supported_encoder_options
from services.engine_service.resolve import (
    _resolve_audio_codec,
    _resolve_or_raw,
    _resolve_video_codec,
)
from services.engine_service.safety import _close_container, _MuxClamp, _safe_seek
from services.job_model import CHAPTERS_SKIP, InputSpec, Job, OutputSpec, StreamSpec


def remux(
    input_path: str,
    output_path: str,
    drop_indices: list[int] | None = None,
    rotation: int | None = None,
    chapters: list[dict] | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Losslessly copy selected streams into a Matroska file (track picker).

    ``drop_indices`` are source stream indexes to EXCLUDE (e.g. an unwanted
    audio track). ``add_stream_from_template`` already carries codecpar,
    metadata (incl. language) and dispositions across — chapters are
    copied explicitly. Cancel follows the M1 pattern: remove + InterruptedError.

    ``rotation`` (90/180/270) rewrites the video display matrix WITHOUT
    re-encoding — orientation fix for phone footage with no encode wait.
    ``chapters``
    (list of {title, start_s, end_s}) replaces the chapter set; None keeps
    the source chapters. Chapter writes are matroska/mov-gated by the
    caller (other muxers ignore them).
    """
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_path)],
        output=OutputSpec(container="matroska", metadata=True, rotation=rotation),
        drop_indices=list(drop_indices or []),
        keep_attachments=True,
        chapters=chapters,
        progress_label="Copying streams",
        complete_label="Streams copied",
        cancel_message="Stream copy cancelled",
    )
    return run_copy_job(job, on_progress=on_progress, cancel_event=cancel_event)


def concat(
    paths: list[str],
    output_path: str,
    container_format: str | None = "mp4",
    transition: str = "cut",
    fade_s: float = 0.5,
    video_codec: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Join clips end-to-end. Identical streams → lossless stream-copy;
    anything else → uniform re-encode (scaled to the first clip's shape).

    ``video_codec`` is the screen's wheel-measured pick for any path that
    re-encodes (None = legacy auto). The resolver raises
    EngineCapabilityError for anything the wheel cannot encode.
    """
    if not paths or len(paths) < 2:
        raise ValueError("Pick at least two files to join")

    infos = [probe_media(p) for p in paths]

    if transition == "crossfade":
        gate_reason = _crossfade_gate(infos, fade_s)
        if gate_reason is None:
            return _concat_crossfade(
                paths,
                infos,
                output_path,
                container_format,
                fade_s,
                video_codec,
                on_progress,
                cancel_event,
            )
        logger.warning("Crossfade unavailable (%s) — falling back to lossless join", gate_reason)
    elif transition != "cut":
        raise ValueError(f"Unsupported transition: {transition}")

    if _concat_copyable(infos):
        return _concat_stream_copy(paths, output_path, container_format, on_progress, cancel_event)
    return _concat_reencode(
        paths, infos, output_path, container_format, video_codec, on_progress, cancel_event
    )


def _crossfade_gate(infos: list[MediaInfo], fade_s: float) -> str | None:
    """None when crossfade can run; otherwise a human-readable reason.

    Gates (all proven necessary by the window empirics): alphamerge +
    overlay (+ acrossfade when audio present) compiled in; every clip has
    video, matching fps, ≤1080p, and room for both windows; audio layouts
    match; fade snaps cleanly to the frame grid.
    """
    # Deferred through the facade: tests patch
    # services.engine_service.available_filters for this gate.
    from services.engine_service import available_filters

    avail = available_filters()
    needed = {"alphamerge", "overlay"}
    if any(s.audio_stream for s in infos):
        needed.add("acrossfade")
    missing = needed - avail
    if missing:
        return f"filters not in this build: {', '.join(sorted(missing))}"

    first = infos[0]
    fv = first.video_stream
    if fv is None:
        return "first file has no video"
    for other in infos:
        ov = other.video_stream
        if ov is None:
            return "a file has no video stream"
        # average_rate can jitter 0.01-0.06 between takes from the same
        # phone (encoder quantizes the rational differently per file), so a
        # strict 0.05 gate refuses identical-camera clips.  The concat paths
        # re-encode anyway (crossfade always does), so a frame-rate gate here
        # is a quality hint, not a hard muxer constraint — keep copyable
        # strict (0.05) but relax crossfade to 2 fps (~7% at 30p).
        if abs((ov.fps or 0) - (fv.fps or 0)) > 2.0:
            return "frame rates differ"
        if (ov.width or 0) > 1920 or (ov.height or 0) > 1080:
            return "sources above 1080p"
        if other.duration_s <= fade_s * 2 + 0.2:
            return f"{other.file_name} is too short for a {fade_s}s fade"
        oa, fa = other.audio_stream, first.audio_stream
        if (oa is None) != (fa is None):
            return "some clips have audio, others don't"
        if (
            oa is not None
            and fa is not None
            and (oa.sample_rate != fa.sample_rate or oa.channels != fa.channels)
        ):
            return "audio layouts differ"
    # fade grid: _concat_crossfade snaps it to round(fade*fps)/fps anyway,
    # so a pre-gate refusal for non-snapping fades is unnecessary — warn
    # at debug and let the re-encode path handle the rounding.
    return None


def _concat_copyable(infos: list[MediaInfo]) -> bool:
    """True when every clip shares stream layout + codec parameters."""
    first = infos[0]
    first_layout = [s.stream_type for s in first.streams]
    for other in infos[1:]:
        if [s.stream_type for s in other.streams] != first_layout:
            return False
        fv, ov = first.video_stream, other.video_stream
        if (fv is None) != (ov is None):
            return False
        if fv is not None and ov is not None:
            if fv.codec_name != ov.codec_name:
                return False
            if (fv.width, fv.height) != (ov.width, ov.height):
                return False
            if abs((fv.fps or 0) - (ov.fps or 0)) > 0.05:
                return False
        fa, oa = first.audio_stream, other.audio_stream
        if (fa is None) != (oa is None):
            return False
        if fa is not None and oa is not None:
            if fa.codec_name != oa.codec_name:
                return False
            if fa.channels != oa.channels or fa.sample_rate != oa.sample_rate:
                return False
    return True


def _concat_stream_copy(
    paths: list[str],
    output_path: str,
    container_format: str | None,
    on_progress: Callable[[float, str], None] | None,
    cancel_event: Event | None,
) -> str:
    """Lossless join: packets are rescaled onto the first clip's timeline."""
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=path) for path in paths],
        output=OutputSpec(container=container_format, metadata=False),
        chapters=CHAPTERS_SKIP,
        timeline_shift=True,
        progress_label="Joining",
        complete_label=f"Joined {len(paths)} clips",
        cancel_message="Join cancelled",
    )
    return run_copy_job(job, on_progress=on_progress, cancel_event=cancel_event)


def _concat_reencode(
    paths: list[str],
    infos: list[MediaInfo],
    output_path: str,
    container_format: str | None,
    video_codec: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Uniform re-encode join: one encoder pair for the whole chain.

    Multi-input preset over run_encode_job: clips with mismatched shapes
    are scaled to the first clip's size; sequential pts=None keeps the
    timeline continuous across boundaries.
    """
    first = infos[0]
    fv = first.video_stream
    fa = first.audio_stream
    if fv is None:
        raise ValueError("The first file has no video stream to join")

    out_fps = max(1, min(int(fv.fps or 30), 60))
    out_w = max(2, (fv.width or 640) // 2 * 2)
    out_h = max(2, (fv.height or 360) // 2 * 2)
    chosen_v = _resolve_or_raw(video_codec, "video") if video_codec else _pick_video_encoder()
    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=path) for path in paths],
        streams=[
            StreamSpec(
                kind="video",
                codec=chosen_v,
                fps=out_fps,
                scale_width=out_w,
                scale_height=out_h,
                pts_policy="encoder",
                encoder_options=_supported_encoder_options(
                    chosen_v, {"crf": "23", "preset": "fast"}
                ),
            ),
            StreamSpec(
                kind="audio",
                codec="aac",
                sample_rate=int(fa.sample_rate) if fa and fa.sample_rate else None,
                layout="stereo" if (fa and (fa.channels or 2) >= 2) else "mono",
                pts_policy="encoder",
            ),
        ],
        output=OutputSpec(container=container_format, metadata=False),
        chapters=CHAPTERS_SKIP,
        progress_label="Joining",
        complete_label=f"Joined {len(paths)} clips",
        cancel_message="Join cancelled",
    )
    return run_encode_job(job, on_progress=on_progress, cancel_event=cancel_event)


def _concat_crossfade(
    paths: list[str],
    infos: list[MediaInfo],
    output_path: str,
    container_format: str | None,
    fade_s: float,
    video_codec: str | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Uniform re-encode join with crossfades at every boundary.

    Video timeline is OUTPUT-INDEX based (pts = round(idx·90000/fps)) —
    immune to the per-clip pts-domain traps the xfade path fell into.
    Each boundary runs the empirically-verified window recipe:
    alphamerge(B + Python-generated alpha ramp) composited over A via
    overlay, with B shifted into A's native domain for framesync pairing;
    output frames are then re-stamped by index like the mid segments.
    Audio windows use acrossfade (native pts in, encode-time +cursor shift
    out — verified monotonic); mid audio is seconds-based (t - start + cursor).

    ``video_codec`` is the screen's wheel-measured pick (None = legacy).
    """
    first = infos[0]
    fps = first.video_stream.fps or 30.0
    fade_frames = max(1, round(fade_s * fps))
    fade = fade_frames / fps  # grid-snapped fade duration
    out_w = max(2, ((first.video_stream.width or 640) // 2) * 2)
    out_h = max(2, ((first.video_stream.height or 360) // 2) * 2)
    first_audio = first.audio_stream
    fine = Fraction(1, 90000)
    out_rate = int(first_audio.sample_rate) if first_audio else 0

    def vid_pts(idx: int) -> int:
        return round(idx * 90000.0 / fps)

    out = av.open(output_path, "w", format=container_format)
    cancelled = False
    try:
        chosen_v = _resolve_video_codec(video_codec) if video_codec else _pick_video_encoder()
        out_video = out.add_stream(chosen_v, rate=max(1, round(fps)))
        out_video.width = out_w
        out_video.height = out_h
        out_video.pix_fmt = _encoder_pix_fmt(chosen_v)
        out_video.time_base = fine
        out_video.options = _supported_encoder_options(
            chosen_v, {"crf": "23", "preset": "fast", "bf": "0"}
        )

        out_audio = None
        if first_audio is not None:
            out_audio = out.add_stream(_resolve_audio_codec("aac"), rate=out_rate)
            out_audio.layout = "stereo" if (first_audio.channels or 2) >= 2 else "mono"

        v_idx = 0  # output video frame index → the ONLY video timeline
        audio_pts_cursor = -1
        last_audio_packet_dts = -1
        last_audio_packet_pts = -1
        cursor = 0.0  # output seconds where the next segment begins
        mux_clamp = _MuxClamp()

        def enc_video(frame) -> None:
            nonlocal v_idx
            frame.time_base = fine
            frame.pts = vid_pts(v_idx)
            v_idx += 1
            for enc_pkt in out_video.encode(frame):
                mux_clamp.mux(out, enc_pkt)

        def enc_audio(frame, out_seconds: float) -> None:
            nonlocal audio_pts_cursor, last_audio_packet_dts, last_audio_packet_pts
            if out_audio is None:
                return
            frame.time_base = Fraction(1, out_rate)
            candidate = round(out_seconds * out_rate)
            if candidate <= audio_pts_cursor:
                candidate = audio_pts_cursor + max(1, frame.samples)
            frame.pts = candidate
            audio_pts_cursor = candidate
            for enc_pkt in out_audio.encode(frame):
                if enc_pkt.dts is None or enc_pkt.dts <= last_audio_packet_dts:
                    enc_pkt.dts = last_audio_packet_dts + 1
                if enc_pkt.pts is None or enc_pkt.pts <= last_audio_packet_pts:
                    enc_pkt.pts = last_audio_packet_pts + 1
                last_audio_packet_dts = enc_pkt.dts
                last_audio_packet_pts = enc_pkt.pts
                mux_clamp.mux(out, enc_pkt)

        def reformat_to_out(frame):
            if (
                frame.width != out_w
                or frame.height != out_h
                or frame.format.name != out_video.pix_fmt
            ):
                return frame.reformat(width=out_w, height=out_h, format=out_video.pix_fmt)
            return frame

        for i, path in enumerate(paths):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                break
            _pause_hook(cancel_event)
            info = infos[i]
            d_i = info.duration_s
            has_next = i < len(paths) - 1
            in_start = fade if i > 0 else 0.0
            in_end = (d_i - fade) if has_next else d_i

            inp = av.open(path, "r", timeout=_INPUT_TIMEOUT)
            try:
                in_video = inp.streams.best("video")
                if in_video is None:
                    raise ValueError(f"{info.file_name} has no video stream")

                # ── Video mid-segment (index-timeline: pts = out_idx·step)
                if in_start > 0:
                    _safe_seek(inp, int(max(0.0, in_start - 1.0) * av.time_base))
                mid_done = False
                for packet in inp.demux([in_video]):
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        break
                    _pause_hook(cancel_event)
                    for frame in _decode_packet(packet):
                        t = frame.time
                        if t is None or t < in_start:
                            continue
                        if t >= in_end:
                            mid_done = True
                            break
                        enc_video(reformat_to_out(frame))
                    if mid_done:
                        break
            finally:
                inp.close()

            # Cursor = output seconds where the segment's tail/window starts
            cursor += in_end - in_start

            # ── Audio mid (seconds-based: out = t - in_start + pre-mid cursor)
            if out_audio is not None and info.audio_stream is not None:
                mid_cursor = cursor - (in_end - in_start)
                a_inp = av.open(path, "r", timeout=_INPUT_TIMEOUT)
                try:
                    a_stream = a_inp.streams.best("audio")
                    if in_start > 0:
                        _safe_seek(a_inp, int(max(0.0, in_start - 1.0) * av.time_base))
                    a_mid_done = False
                    for packet in a_inp.demux([a_stream]):
                        if cancel_event and cancel_event.is_set():
                            cancelled = True
                            break
                        _pause_hook(cancel_event)
                        for frame in _decode_packet(packet):
                            t = frame.time
                            if t is None or t < in_start:
                                continue
                            if t >= in_end:
                                a_mid_done = True
                                break
                            enc_audio(frame, (t - in_start) + mid_cursor)
                        if a_mid_done:
                            break
                finally:
                    a_inp.close()

            # ── Boundary window AFTER cursor reflects the mid segment ──
            if has_next and not cancelled:
                _xfade_window(
                    source_path=path,
                    next_path=paths[i + 1],
                    out_w=out_w,
                    out_h=out_h,
                    window_start=in_end,
                    clip_end=d_i,
                    fade=fade,
                    enc_video=enc_video,
                    reformat=reformat_to_out,
                    cancel_event=cancel_event,
                )
                if out_audio is not None and info.audio_stream is not None:
                    _acrossfade_window(
                        path=path,
                        next_path=paths[i + 1],
                        tail_start=in_end,
                        clip_end=d_i,
                        cursor=cursor,
                        fade=fade,
                        out_rate=out_rate,
                        enc_audio=enc_audio,
                        cancel_event=cancel_event,
                    )
                cursor += fade

            if on_progress:
                on_progress(
                    min(0.95, (i + 1) / len(paths) * 0.95),
                    f"Joining with crossfade… ({i + 1}/{len(paths)})",
                )

        if not cancelled:
            if out_video:
                for enc_pkt in out_video.encode(None):
                    mux_clamp.mux(out, enc_pkt)
            if out_audio:
                for enc_pkt in out_audio.encode(None):
                    mux_clamp.mux(out, enc_pkt)
            if on_progress:
                on_progress(1.0, f"Joined {len(paths)} clips with crossfades")
    finally:
        _close_container(out)

    if cancelled or (cancel_event and cancel_event.is_set()):
        _discard_cancelled(output_path)
        raise InterruptedError("Join cancelled")
    return output_path


def _xfade_window(
    *,
    source_path: str,
    next_path: str,
    out_w: int,
    out_h: int,
    window_start: float,
    clip_end: float,
    fade: float,
    enc_video,
    reformat,
    cancel_event: Event | None,
) -> None:
    """Emit the fade window: A-tail blended with B-head via the
    alphamerge+overlay recipe (empirically verified: pairing works when B
    is shifted into A's tail domain; alpha ramp generated as constant-bytes
    gray frames — memset-cheap)."""
    inp_a = av.open(source_path, "r", timeout=_INPUT_TIMEOUT)
    try:
        inp_b = av.open(next_path, "r", timeout=_INPUT_TIMEOUT)
    except Exception:
        inp_a.close()
        raise
    try:
        va = inp_a.streams.best("video")
        vb = inp_b.streams.best("video")
        vtb = va.time_base
        # A-window native domain is [clip_end-fade, clip_end]; B's [0,fade)
        # must map onto it → shift = window START (empirics: T = durA - fade).
        shift_b = int((clip_end - fade) / vtb)

        # Collect both windows first (small: fade·fps frames each)
        a_win: list = []
        done = False
        _safe_seek(inp_a, int(max(0.0, window_start - 1.0) * av.time_base))
        for packet in inp_a.demux([va]):
            if cancel_event and cancel_event.is_set():
                return
            for frame in _decode_packet(packet):
                t = frame.time
                if t is None or t < window_start - 1e-6:
                    continue
                if t > clip_end + 1e-6:
                    done = True
                    break
                a_win.append(frame)
            if done:
                break

        b_win: list = []
        done = False
        for packet in inp_b.demux([vb]):
            if cancel_event and cancel_event.is_set():
                return
            for frame in _decode_packet(packet):
                t = frame.time
                if t is None or t < 0:
                    continue
                if t >= fade - 1e-6:
                    done = True
                    break
                if frame.pts is not None:
                    frame.pts = frame.pts + shift_b
                b_win.append(frame)
            if done:
                break

        n = min(len(a_win), len(b_win))
        if n == 0:
            logger.warning("Crossfade window empty — boundary becomes a hard cut")
            return

        g = av.filter.Graph()
        buf_a = g.add_buffer(template=va)  # 0 — background
        buf_b = g.add_buffer(template=vb)  # 1 — main into alphamerge
        buf_al = g.add_buffer(
            width=out_w, height=out_h, format="gray", time_base=vtb
        )  # 2 — alpha ramp
        am = g.add("alphamerge")
        ov = g.add("overlay", "format=auto")
        sink = g.add("buffersink")
        buf_b.link_to(am, 0, 0)
        buf_al.link_to(am, 0, 1)
        am.link_to(ov, 0, 1)
        buf_a.link_to(ov, 0, 0)
        ov.link_to(sink)
        g.configure()

        for k in range(n):
            if cancel_event and cancel_event.is_set():
                return
            alpha = av.VideoFrame(out_w, out_h, "gray")
            val = round(255 * k / max(1, n - 1))
            for pl in alpha.planes:
                pl.update(bytes([val]) * pl.buffer_size)
            alpha.pts = b_win[k].pts
            alpha.time_base = b_win[k].time_base
            g.push(alpha, at=2)
            g.push(b_win[k], at=1)
            g.push(a_win[k], at=0)
        g.push(None, at=2)
        g.push(None, at=1)
        g.push(None, at=0)

        while True:
            try:
                of = g.pull()
            except EOFError:
                break
            except FFmpegError as exc:
                if exc.errno == EAGAIN:
                    continue
                raise
            enc_video(reformat(of))
    finally:
        inp_a.close()
        inp_b.close()


def _acrossfade_window(
    *,
    path: str,
    next_path: str,
    tail_start: float,
    clip_end: float,
    cursor: float,
    fade: float,
    out_rate: int,
    enc_audio,
    cancel_event: Event | None,
) -> None:
    """Audio half of a boundary: A's tail [tail_start, clip_end] + B's head
    [0, fade] through acrossfade; output (normalized to ~0) is re-based onto
    the running cursor at encode time — verified monotonic by empirics."""
    inp_a = av.open(path, "r", timeout=_INPUT_TIMEOUT)
    try:
        inp_b = av.open(next_path, "r", timeout=_INPUT_TIMEOUT)
    except Exception:
        inp_a.close()
        raise
    try:
        sa = inp_a.streams.best("audio")
        sb = inp_b.streams.best("audio")

        a_tail: list = []
        if tail_start > 0:
            _safe_seek(inp_a, int(max(0.0, tail_start - 1.0) * av.time_base))
        done = False
        for packet in inp_a.demux([sa]):
            if cancel_event and cancel_event.is_set():
                return
            for frame in _decode_packet(packet):
                t = frame.time
                if t is None or t < tail_start - 1e-6:
                    continue
                if t > clip_end + 1e-6:
                    done = True
                    break
                a_tail.append(frame)
            if done:
                break

        b_head: list = []
        done = False
        for packet in inp_b.demux([sb]):
            if cancel_event and cancel_event.is_set():
                return
            for frame in _decode_packet(packet):
                t = frame.time
                if t is None or t < 0:
                    continue
                if t >= fade - 1e-6:
                    done = True
                    break
                b_head.append(frame)
            if done:
                break

        n = min(len(a_tail), len(b_head))
        if n == 0:
            logger.warning("Audio crossfade window empty — boundary becomes a hard cut")
            return

        g = av.filter.Graph()
        buf_a = g.add_abuffer(template=sa)
        buf_b = g.add_abuffer(template=sb)
        ac = g.add("acrossfade", f"d={fade}")
        sink = g.add("abuffersink")
        buf_a.link_to(ac, 0, 0)
        buf_b.link_to(ac, 0, 1)
        ac.link_to(sink)
        g.configure()

        for frame in a_tail:
            if cancel_event and cancel_event.is_set():
                return
            g.push(frame, at=0)
        g.push(None, at=0)
        for frame in b_head:
            if cancel_event and cancel_event.is_set():
                return
            g.push(frame, at=1)
        g.push(None, at=1)

        while True:
            try:
                of = g.pull()
            except EOFError:
                break
            except FFmpegError as exc:
                if exc.errno == EAGAIN:
                    continue
                raise
            # acrossfade normalizes output to ~0 — shift onto the cursor
            base = (of.pts / out_rate) if of.pts else 0.0
            enc_audio(of, cursor + base)
    finally:
        inp_a.close()
        inp_b.close()
