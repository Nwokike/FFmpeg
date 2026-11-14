"""The two generic builders: run_encode_job / run_copy_job + media probe."""

from __future__ import annotations

import contextlib
import logging
import shutil
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from threading import Event

import av
from av.error import FFmpegError
from av.video.reformatter import VideoReformatter

from core.state import ChapterInfo, MediaInfo, MediaStreamInfo
from services.engine_service.capability import _encoder_open_kwargs, _encoder_pix_fmt
from services.engine_service.graphs import _FINE_VIDEO_TB, _drain_graph, _push_pull, _rebase_pts
from services.engine_service.logs import (
    _INPUT_TIMEOUT,
    _av_rational,
    _decode_packet,
    _is_attached_picture,
    logger,
)
from services.engine_service.options import _exact_rate, _supported_encoder_options
from services.engine_service.resolve import _resolve_audio_codec, _resolve_video_codec
from services.engine_service.safety import (
    _close_container,
    _disposition_flag_names,
    _MuxClamp,
    _safe_seek,
)
from services.engine_service.sizing import (
    _chain_declared_size,
    _crop_dims,
    _graph_from_nodes,
    _select_stream,
)
from services.job_model import CHAPTERS_SKIP, Job


def _discard_cancelled(path: str, *, directory: bool = False) -> None:
    """Best-effort removal of a partial output left behind by a cancelled job."""
    try:
        if directory:
            shutil.rmtree(path, ignore_errors=True)
        elif Path(path).exists():
            Path(path).unlink()
    except OSError as exc:
        logger.warning("Failed to remove cancelled output %s: %s", path, exc)


ENGINE_PAUSE_EVENT: Event | None = None


def set_pause_event(evt: Event | None) -> None:
    """Install (or clear) the queue's pause event for the engine hooks."""
    global ENGINE_PAUSE_EVENT
    ENGINE_PAUSE_EVENT = evt


def _pause_hook(cancel_event: Event | None = None) -> None:
    """Block between packets while paused; a cancel always wins."""
    evt = ENGINE_PAUSE_EVENT
    if evt is None or not evt.is_set():
        return
    logger.info("Engine paused")
    while evt.is_set():
        if cancel_event is not None and cancel_event.is_set():
            return
        time.sleep(0.1)
    logger.info("Engine resumed")


def run_encode_job(
    job: Job,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """The single generic encode loop: demux -> decode -> chain -> encode -> mux.

    One monotonic-pts policy, one drain/flush sequence, one cancel/reconcile
    path for every op that produces encoded output (convert, compress,
    cut-reencode, extract_audio, gif, concat-reencode...). av owns timestamps;
    this fixes only what the muxer genuinely requires. Multi-input jobs
    (concat) iterate inputs over the same output streams with per-file
    progress steps.
    """
    first_spec = job.inputs[0]
    first_inp = av.open(
        first_spec.path,
        "r",
        format=first_spec.format,
        timeout=first_spec.timeout,
        options=first_spec.options,
        hwaccel=first_spec.hwaccel,
    )
    try:
        out = av.open(job.output_path, "w", format=job.output.container, options=job.output.options)
    except Exception:
        first_inp.close()
        raise

    if first_spec.seek_s:
        # container.seek defaults to AV_TIME_BASE (microseconds) units.
        _safe_seek(first_inp, max(0, int(first_spec.seek_s * av.time_base)))

    try:
        if job.output.metadata and first_inp.metadata:
            out.metadata.update(first_inp.metadata)
        if job.output.chapters:
            try:
                out.set_chapters(first_inp.chapters())
            except Exception as exc:
                logger.debug("Chapter copy skipped: %s", exc)

        v_spec = next((s for s in job.streams if s.kind == "video"), None)
        a_spec = next((s for s in job.streams if s.kind == "audio"), None)
        in_video = _select_stream(first_inp, v_spec, "video") if v_spec else None
        in_audio = _select_stream(first_inp, a_spec, "audio") if a_spec else None

        out_video = None
        if v_spec is not None and in_video is not None:
            target_fps = v_spec.fps if v_spec.fps else _exact_rate(in_video.average_rate)
            if v_spec.cap_fps:
                target_fps = max(1, min(target_fps, 60))
            chosen_vcodec = _resolve_video_codec(v_spec.codec)
            need_vfilter = job.video_chain is not None
            # setpts changes the effective frame rate (30fps sped 1.5x arrives
            # as 45fps); declare it so the encoder's DTS model matches reality.
            eff_rate = (
                max(1, -(-round(target_fps * v_spec.speed * 1000) // 1000))
                if need_vfilter and v_spec.speed > 0
                else target_fps
            )
            out_video = out.add_stream(
                chosen_vcodec,
                rate=eff_rate,
                **_encoder_open_kwargs(chosen_vcodec),
            )
            # A caller-supplied filter chain can change the frame size (scale,
            # crop, transpose…). FFmpeg sizes the encoder from the chain's
            # output, and so must we: the codec context opens on the first
            # encode() of ANY stream, so the size has to be known up front.
            # A chain's scale/crop with literal arguments declares it (readable
            # without decoding); anything else keeps the input geometry and the
            # runtime check below refuses loudly rather than upscaling silently.
            caller_chain = bool(job.video_chain is not None and job.video_chain.nodes)
            graph_owns_size = caller_chain and not (v_spec.scale_width or v_spec.scale_height)
            declared = (
                _chain_declared_size(
                    job.video_chain.nodes,
                    (in_video.width or 640, in_video.height or 360),
                )
                if graph_owns_size
                else None
            )
            target_w = (
                v_spec.scale_width or (declared[0] if declared else 0) or in_video.width or 640
            )
            target_h = (
                v_spec.scale_height or (declared[1] if declared else 0) or in_video.height or 360
            )
            # Crop defines the final size when no explicit scale is set —
            # otherwise the post-graph reformat would upscale right back.
            if (
                v_spec.crop_aspect
                and v_spec.crop_aspect != "original"
                and v_spec.scale_width is None
                and v_spec.scale_height is None
            ):
                target_w, target_h = _crop_dims(
                    in_video.width or target_w,
                    in_video.height or target_h,
                    v_spec.crop_aspect,
                )
            if v_spec.rotation % 180 == 90 and declared is None:  # 90/270 transpose swaps w/h
                target_w, target_h = target_h, target_w
            if v_spec.even_align:
                target_w = (target_w // 2) * 2  # even dimensions for yuv420p
                target_h = (target_h // 2) * 2
            out_video.width = target_w
            out_video.height = target_h
            if v_spec.bit_rate:
                out_video.bit_rate = v_spec.bit_rate
            enc_pix_fmt = v_spec.pix_fmt or _encoder_pix_fmt(chosen_vcodec)
            out_video.pix_fmt = enc_pix_fmt
            out_video.time_base = (
                _FINE_VIDEO_TB if v_spec.fine_time_base else Fraction(1, round(target_fps))
            )
            # The graph runs on the encoder's clock (see the push site): a filter
            # that relabels a frame's time_base then cannot stretch the timeline.
            graph_tb = out_video.time_base
            out_video.options = _supported_encoder_options(
                chosen_vcodec,
                dict(v_spec.encoder_options),
            )

        out_audio = None
        if a_spec is not None and in_audio is not None:
            chosen_acodec = _resolve_audio_codec(a_spec.codec)
            # Opus is 48k-native; the stream resamples fed frames itself.
            if a_spec.sample_rate:
                a_rate = a_spec.sample_rate
            elif chosen_acodec in ("opus", "libopus"):
                a_rate = 48000
            else:
                a_rate = in_audio.rate or 44100
            out_audio = out.add_stream(
                chosen_acodec,
                rate=a_rate,
                **_encoder_open_kwargs(chosen_acodec),
            )
            if a_spec.bit_rate:
                out_audio.bit_rate = a_spec.bit_rate
            n_ch = (
                a_spec.channels if a_spec.channels is not None else min(2, in_audio.channels or 2)
            )
            layout = a_spec.layout or ("stereo" if n_ch >= 2 else "mono")
            out_audio.layout = layout
            # Audio encoder options ride the same validation as video: a key the
            # wheel's encoder lacks drops with an info line, never fails the job.
            # Merge, never replace: add_stream may have set open-time options
            # (vorbis needs strict=-2), and those must survive.
            audio_opts = _supported_encoder_options(chosen_acodec, dict(a_spec.encoder_options))
            if audio_opts:
                merged_opts = dict(getattr(out_audio, "options", None) or {})
                merged_opts.update(audio_opts)
                out_audio.options = merged_opts

        # Fixed-frame encoders (AAC/MP3/FLAC) need AudioFifo batching; the
        # encoder is pre-opened so its real frame_size is visible before the
        # first packet.
        audio_fifo = None
        if a_spec is not None and in_audio is not None and a_spec.audio_fifo:
            try:
                out.start_encoding()
            except Exception as exc:
                logger.debug("Audio encoder pre-open deferred: %s", exc)
            audio_fifo = av.AudioFifo() if out_audio.frame_size > 0 else None

        # soxr-quality rate/layout conversion when this build has libsoxr;
        # _encode_audio_frame falls back to plain swr on first use otherwise.
        resampler = None
        if a_spec is not None and in_audio is not None and a_spec.audio_resample:
            src_rate = in_audio.rate or (a_spec.sample_rate or 44100)
            src_layout = getattr(in_audio.layout, "name", None)
            dst_rate = out_audio.rate
            # Encoders without a declared layout report an empty (0-channel)
            # layout; stringifying it would feed "0 channels" into the
            # resampler and crash. The spec's own layout is what was asked for.
            dst_layout = getattr(out_audio.layout, "name", None)
            if not dst_layout or not getattr(out_audio.layout, "channels", 0):
                dst_layout = layout
            if src_rate != dst_rate or (src_layout and src_layout != dst_layout):
                resampler = av.AudioResampler(
                    layout=dst_layout,
                    rate=dst_rate,
                    options={"resampler": "soxr", "precision": "28"},
                )

        video_reformatter = VideoReformatter()
        last_video_pts = -1
        last_audio_pts = -1
        mux_clamp = _MuxClamp()

        def _mux_packet(container, pkt) -> None:
            mux_clamp.mux(container, pkt)

        def _stamp_video(frame: av.VideoFrame) -> None:
            if v_spec is not None and v_spec.pts_policy == "encoder":
                frame.pts = None
                return
            _monotonic_video_pts(frame)

        def _stamp_audio(frame: av.AudioFrame) -> None:
            if a_spec is not None and a_spec.pts_policy == "encoder":
                frame.pts = None
                return
            _monotonic_audio_pts(frame)

        def _encode_audio_frame(frame: av.AudioFrame) -> None:
            """FIFO-batched or direct encode of one decoded audio frame."""
            nonlocal audio_fifo, resampler
            if resampler is not None:
                try:
                    resampled = resampler.resample(frame)
                except FFmpegError as exc:
                    logger.warning("soxr resampler unavailable (%s); falling back to swr", exc)
                    resampler = av.AudioResampler(layout=dst_layout, rate=dst_rate)
                    resampled = resampler.resample(frame)
                for rf in resampled:
                    _push_audio(rf)
            else:
                _push_audio(frame)

        def _push_audio(frame: av.AudioFrame) -> None:
            nonlocal audio_fifo
            # Timestamp policy applied by _stamp_audio ("encoder" policy
            # leaves pts=None here; "monotonic" keeps the floored clock).
            if audio_fifo is not None:
                try:
                    audio_fifo.write(frame)
                    while audio_fifo.samples >= out_audio.frame_size:
                        full = audio_fifo.read(out_audio.frame_size, partial=False)
                        if full is None:
                            break
                        for enc_pkt in out_audio.encode(full):
                            _mux_packet(out, enc_pkt)
                    return
                except (TypeError, ValueError, av.error.FFmpegError) as exc:
                    logger.debug("AudioFifo fallback to encoder resampler: %s", exc)
                    audio_fifo = None
            for enc_pkt in out_audio.encode(frame):
                _mux_packet(out, enc_pkt)

        def _monotonic_video_pts(frame: av.VideoFrame) -> None:
            nonlocal last_video_pts
            out_tb = out_video.time_base or Fraction(1, 30)
            candidate = None
            if frame.pts is not None and frame.time_base:
                candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
            if candidate is None or candidate <= last_video_pts:
                candidate = last_video_pts + 1
            frame.pts = candidate
            frame.time_base = out_tb
            frame.pict_type = 0
            frame.key_frame = False
            last_video_pts = candidate

        def _monotonic_audio_pts(frame: av.AudioFrame) -> None:
            nonlocal last_audio_pts
            out_tb = out_audio.time_base or Fraction(1, out_audio.rate or 44100)
            candidate = None
            if frame.pts is not None and frame.time_base:
                candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
            if candidate is None or candidate <= last_audio_pts:
                candidate = last_audio_pts + max(1, frame.samples)
            frame.pts = candidate
            frame.time_base = out_tb
            last_audio_pts = candidate

        cancelled_any = False
        multi_input = len(job.inputs) > 1
        for fi, spec_i in enumerate(job.inputs):
            if (
                fi > 0
                and not job.record_mode
                and cancel_event is not None
                and cancel_event.is_set()
            ):
                cancelled_any = True
                break
            if fi == 0:
                inp = first_inp
            elif (
                job.input_containers
                and fi < len(job.input_containers)
                and job.input_containers[fi] is not None
            ):
                inp = job.input_containers[fi]
            else:
                inp = av.open(
                    spec_i.path,
                    "r",
                    format=spec_i.format,
                    timeout=spec_i.timeout,
                    options=spec_i.options,
                    hwaccel=spec_i.hwaccel,
                )
            try:
                in_video = _select_stream(inp, v_spec, "video") if v_spec else None
                in_audio = _select_stream(inp, a_spec, "audio") if a_spec else None
                total_duration = (
                    float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
                )
                last_report = 0.0
                processed_pts = 0.0

                streams_to_demux = [
                    s for s, spec in ((in_video, v_spec), (in_audio, a_spec)) if s and spec
                ]

                video_graph = None
                audio_graph = None
                for packet in inp.demux(streams_to_demux):
                    _pause_hook(cancel_event)
                    if cancel_event and cancel_event.is_set():
                        logger.info("Transcode cancelled by user.")
                        break

                    if packet.size == 0 or (packet.pts is None and packet.dts is None):
                        continue

                    win_start, win_end = job.window if job.window else (None, None)

                    if in_video and packet.stream == in_video:
                        for frame in _decode_packet(packet):
                            if cancel_event and cancel_event.is_set():
                                break
                            if win_start is not None or win_end is not None:
                                ft = frame.time
                                if ft is None or (win_start is not None and ft < win_start):
                                    continue
                                if win_end is not None and ft > win_end:
                                    break
                            if frame.time:
                                processed_pts = frame.time

                            if job.video_chain is not None:
                                # Rebase BEFORE building the graph: the buffer
                                # source takes its time base from the first
                                # frame, and the graph must be driven on the
                                # encoder's clock (a filter that relabels a
                                # frame's time_base — scale does — would
                                # otherwise stretch the timeline).
                                _rebase_pts(frame, graph_tb)
                                if video_graph is None:
                                    builder = job.video_chain.build
                                    if builder is not None:
                                        video_graph = builder(frame)
                                    elif job.video_chain.nodes:
                                        video_graph = _graph_from_nodes(
                                            job.video_chain.nodes, frame
                                        )
                                out_frames = (
                                    _push_pull(video_graph, frame)
                                    if video_graph is not None
                                    else [frame]
                                )
                                from_graph = video_graph is not None
                            else:
                                out_frames = [frame]
                                from_graph = False

                            for frame in out_frames:
                                if out_video and graph_owns_size and from_graph:
                                    # The chain's geometry was declared up front
                                    # (or the input's); a chain that produces
                                    # something else cannot be re-fitted now —
                                    # refuse instead of upscaling or crashing
                                    # inside av's "codec is open" guard.
                                    want_w = (
                                        (frame.width // 2) * 2 if v_spec.even_align else frame.width
                                    )
                                    want_h = (
                                        (frame.height // 2) * 2
                                        if v_spec.even_align
                                        else frame.height
                                    )
                                    if (want_w, want_h) != (out_video.width, out_video.height):
                                        raise ValueError(
                                            f"the filter chain produced {frame.width}x{frame.height} "
                                            f"but the encoder was opened for "
                                            f"{out_video.width}x{out_video.height} — end the chain "
                                            "with a literal scale=W:H (or pass an explicit size)"
                                        )
                                if out_video and (
                                    frame.width != out_video.width
                                    or frame.height != out_video.height
                                    or frame.format.name != enc_pix_fmt
                                ):
                                    frame = video_reformatter.reformat(
                                        frame,
                                        width=out_video.width,
                                        height=out_video.height,
                                        format=enc_pix_fmt,
                                    )
                                if out_video:
                                    _stamp_video(frame)
                                    for enc_pkt in out_video.encode(frame):
                                        _mux_packet(out, enc_pkt)

                    elif in_audio and packet.stream == in_audio:
                        for frame in _decode_packet(packet):
                            if cancel_event and cancel_event.is_set():
                                break
                            if win_start is not None or win_end is not None:
                                ft = getattr(frame, "time", None)
                                if ft is None or (win_start is not None and ft < win_start):
                                    continue
                                if win_end is not None and ft > win_end:
                                    break
                            if not out_audio:
                                continue
                            if job.audio_chain is not None and audio_graph is None:
                                builder = job.audio_chain.build
                                if builder is not None:
                                    audio_graph = builder(frame)
                                elif job.audio_chain.nodes:
                                    audio_graph = _graph_from_nodes(job.audio_chain.nodes, frame)
                            out_frames = [frame]
                            if audio_graph is not None:
                                out_frames = _push_pull(audio_graph, frame)
                            for frame in out_frames:
                                _stamp_audio(frame)
                                _encode_audio_frame(frame)

                    now = time.monotonic()
                    if on_progress and not multi_input and (now - last_report >= 0.25):
                        last_report = now
                        progress = (
                            min(0.99, max(0.01, processed_pts / total_duration))
                            if total_duration > 0
                            else 0.5
                        )
                        on_progress(progress, f"{job.progress_label}... {int(progress * 100)}%")

                if multi_input and on_progress:
                    on_progress(
                        min(0.95, (fi + 1) / len(job.inputs) * 0.95),
                        f"Joining {Path(spec_i.path).name}… ({fi + 1}/{len(job.inputs)})",
                    )
            finally:
                if fi > 0:
                    _close_container(inp)

        cancelled = bool(cancel_event is not None and cancel_event.is_set()) or cancelled_any
        if not cancelled and video_graph is not None and out_video:
            for frame in _drain_graph(video_graph):
                if (
                    frame.width != out_video.width
                    or frame.height != out_video.height
                    or frame.format.name != out_video.pix_fmt
                ):
                    frame = video_reformatter.reformat(
                        frame,
                        width=out_video.width,
                        height=out_video.height,
                        format=out_video.pix_fmt,
                    )
                _stamp_video(frame)
                for enc_pkt in out_video.encode(frame):
                    _mux_packet(out, enc_pkt)
        if not cancelled and audio_graph is not None and out_audio:
            for frame in _drain_graph(audio_graph):
                _encode_audio_frame(frame)
        if not cancelled and resampler is not None:
            for rf in resampler.resample(None):
                _push_audio(rf)
        if not cancelled and audio_fifo is not None:
            tail = audio_fifo.read(partial=True)
            if tail is not None:
                for enc_pkt in out_audio.encode(tail):
                    _mux_packet(out, enc_pkt)
        if not cancelled and out_video:
            for enc_pkt in out_video.encode(None):
                _mux_packet(out, enc_pkt)
        if not cancelled and out_audio:
            for enc_pkt in out_audio.encode(None):
                _mux_packet(out, enc_pkt)

        if on_progress:
            on_progress(1.0, job.complete_label)

    finally:
        _close_container(first_inp)
        _close_container(out)

    if cancelled:
        if Path(job.output_path).exists():
            try:
                Path(job.output_path).unlink()
            except OSError as e:
                logging.getLogger(__name__).warning("Failed to remove cancelled output: %s", e)
        raise InterruptedError(job.cancel_message)

    return job.output_path


def run_copy_job(
    job: Job,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """The single generic packet-path builder: stream copy + mux (+ BSF).

    Used by remux (template streams), cut stream-copy (windowed zero-base),
    concat stream-copy (timeline shift) and record (zero-base + Annex-B BSF).
    av owns the muxing; this applies one rescale/rebase/repair policy per op.
    """
    kept_types = (
        ("video", "audio", "subtitle", "data")
        if job.keep_data_streams
        else ("video", "audio", "subtitle")
    )
    out = None
    mux_clamp = _MuxClamp()
    stream_map: dict = {}  # first input: src stream -> out stream
    out_by_pos: list = []
    tb_by_pos: list = []
    base_pts: dict = {}
    base_dts: dict = {}
    shift: dict = {}
    last_pts: dict = {}
    last_dts: dict = {}
    _timeline_state = {"fi": -1, "seen_pos": set()}
    bsfs: dict = {}
    win_start, win_end = job.window if job.window else (None, None)
    job_window_start = win_start
    start = time.monotonic()
    bytes_out = 0

    def _kept_streams(inp):
        return [
            s
            for s in inp.streams
            if s.type in kept_types
            and not _is_attached_picture(s)
            and s.index not in job.drop_indices
        ]

    cancelled_any = False
    try:
        for fi, spec_in in enumerate(job.inputs):
            if (
                fi > 0
                and not job.record_mode
                and cancel_event is not None
                and cancel_event.is_set()
            ):
                cancelled_any = True
                break
            preopened = (
                job.input_containers[fi]
                if job.input_containers and fi < len(job.input_containers)
                else None
            )
            if preopened is not None:
                inp = preopened
            else:
                inp = av.open(
                    spec_in.path,
                    "r",
                    format=spec_in.format,
                    timeout=spec_in.timeout,
                    options=spec_in.options,
                    hwaccel=spec_in.hwaccel,
                )
            try:
                if fi == 0:
                    in_video_early = inp.streams.best("video")
                    effective_seek_s = spec_in.seek_s or 0.0
                    if job.snap_to_keyframe and in_video_early is not None:
                        snapped = _snap_start_to_keyframe(in_video_early, effective_seek_s)
                        if snapped < effective_seek_s - 1e-6:
                            effective_seek_s = snapped
                            if on_progress:
                                on_progress(
                                    0.0,
                                    "Start snapped "
                                    f"{spec_in.seek_s:.2f}s → {snapped:.2f}s for stream-copy cut",
                                )
                        job_window_start = effective_seek_s
                    if effective_seek_s:
                        _safe_seek(inp, max(0, int(effective_seek_s * av.time_base)))
                    out = av.open(
                        job.output_path,
                        "w",
                        format=job.output.container or "matroska",
                        options=job.output.options,
                    )
                    if job.output.metadata and inp.metadata:
                        out.metadata.update(inp.metadata)

                    kept_attachments = False
                    if job.keep_attachments:
                        for attachment in inp.streams.attachments:
                            try:
                                out.add_attachment(
                                    attachment.name, attachment.mimetype, attachment.data
                                )
                                kept_attachments = True
                            except Exception as exc:
                                logger.debug(
                                    "Attachment copy skipped (%s): %s", attachment.name, exc
                                )

                    src_streams = _kept_streams(inp)
                    for s in src_streams:
                        try:
                            out_s = out.add_stream_from_template(s, opaque=True)
                        except ValueError as exc:
                            # MP4-family cannot carry SRT/data/cover-art codecs;
                            # keep the recordable tracks instead of failing.
                            logger.info("Record stream %s skipped: %s", s.index, exc)
                            continue
                        # add_stream_from_template is a NO-OP for metadata/
                        # disposition on this build — copy them explicitly.
                        out_s.metadata.update(s.metadata)
                        with contextlib.suppress(Exception):
                            out_s.disposition = int(s.disposition)
                        stream_map[s] = out_s
                        out_by_pos.append(out_s)
                        tb_by_pos.append(_av_rational(s.time_base or Fraction(1, 1000)))
                    if not stream_map and not kept_attachments:
                        raise ValueError("Nothing to keep — every stream was excluded")

                    rotation = job.output.rotation
                    if rotation in (90, 180, 270):
                        for s, out_s in stream_map.items():
                            if s.type == "video":
                                try:
                                    out_s.set_display_rotation(rotation)
                                except Exception as exc:
                                    logger.warning("Rotation write skipped: %s", exc)

                    if job.chapters is CHAPTERS_SKIP:
                        pass
                    elif job.chapters is not None:
                        try:
                            out.set_chapters(
                                [
                                    {
                                        "id": i,
                                        "start": int(c.get("start_s", 0) * 1000),
                                        "end": int(c.get("end_s", 0) * 1000),
                                        "time_base": Fraction(1, 1000),
                                        "metadata": {
                                            "title": str(c.get("title") or f"Chapter {i + 1}")
                                        },
                                    }
                                    for i, c in enumerate(job.chapters)
                                ]
                            )
                        except Exception as exc:
                            logger.warning("Chapter write skipped: %s", exc)
                    else:
                        try:
                            out.set_chapters(inp.chapters())
                        except Exception as exc:
                            logger.warning("Chapter copy skipped: %s", exc)

                    # Bitstream filters (record): MP4-family sources into an
                    # MPEG-TS/HLS muxer need Annex-B conversion; libavformat
                    # does NOT auto-insert it.
                    if job.bsf_codecs and out.format.name in ("mpegts", "hls"):
                        for s, out_s in stream_map.items():
                            if s.type != "video" or s.codec_context is None:
                                continue
                            cname = s.codec_context.name or ""
                            for prefix, bsf_name in job.bsf_codecs.items():
                                if cname.startswith(prefix):
                                    try:
                                        bsfs[s.index] = (
                                            av.BitStreamFilterContext(
                                                bsf_name, in_stream=s, out_stream=out_s
                                            ),
                                            out_s,
                                        )
                                    except Exception as exc:
                                        logger.warning("BSF %s unavailable: %s", bsf_name, exc)

                src_streams = _kept_streams(inp)
                if fi > 0:
                    # Later inputs map positionally onto the first clip's
                    # template streams; time bases stay the FIRST clip's
                    # (every input is rescaled onto that timeline in _emit).
                    stream_map_local = {s: out_by_pos[pos] for pos, s in enumerate(src_streams)}
                else:
                    stream_map_local = stream_map

                total_s = float(inp.duration or 0) / float(av.time_base) if inp.duration else 0.0
                last_report = 0.0

                def _emit(
                    packet,
                    _fi=fi,
                    _stream_map=stream_map_local,
                    _src_streams=src_streams,
                    _out=out,
                ) -> None:
                    nonlocal bytes_out
                    if _timeline_state["fi"] != _fi:
                        _timeline_state["fi"] = _fi
                        _timeline_state["seen_pos"].clear()
                    if packet.size == 0 or (packet.pts is None and packet.dts is None):
                        return
                    src_key = packet.stream.index if packet.stream is not None else -1
                    _out_s_pre = _stream_map.get(packet.stream)
                    if job.zero_base and src_key >= 0:
                        # Zero-base in the packet's OWN clock, then rescale.
                        # The out stream's time base changes when FFmpeg writes
                        # the header (template 1/12800 → mkv 1/1000), so a base
                        # captured on packet 1 (pre-rescale) applied to packet 2
                        # (post-rescale) mixed clocks: dts came out ~1 s too
                        # large and repair_pts_dts copied that into pts — a
                        # 1.2 s cut read as 2.1 s.
                        if src_key not in base_pts:
                            base_pts[src_key] = packet.pts if packet.pts is not None else 0
                        if src_key not in base_dts:
                            base_dts[src_key] = packet.dts if packet.dts is not None else 0
                        if packet.pts is not None:
                            packet.pts = max(0, packet.pts - base_pts[src_key])
                        if packet.dts is not None:
                            packet.dts = max(0, packet.dts - base_dts[src_key])
                        if (
                            job.repair_pts_dts
                            and packet.dts is not None
                            and packet.pts is not None
                            and packet.dts > packet.pts
                        ):
                            packet.pts = packet.dts
                    if (
                        _out_s_pre is not None
                        and _out_s_pre.time_base
                        and packet.time_base != _av_rational(_out_s_pre.time_base)
                    ):
                        packet.rescale_ts(_av_rational(_out_s_pre.time_base))
                    if job.timeline_shift:
                        pos = next(
                            (p for p, s in enumerate(_src_streams) if s.index == src_key),
                            None,
                        )
                        if pos is not None:
                            native_pts = packet.pts if packet.pts is not None else 0
                            native_dts = packet.dts if packet.dts is not None else native_pts
                            if pos not in _timeline_state["seen_pos"]:
                                # First packet of THIS input: land one tick past
                                # the previous input's final pts (continuity).
                                _timeline_state["seen_pos"].add(pos)
                                prev_pts = last_pts.get(pos)
                                prev_dts = last_dts.get(pos)
                                shift[pos] = max(
                                    prev_pts + 1 - native_pts if prev_pts is not None else 0,
                                    prev_dts + 1 - native_dts if prev_dts is not None else 0,
                                )
                            delta = shift.get(pos, 0)
                            if packet.pts is not None:
                                packet.pts = packet.pts + delta
                            if packet.dts is not None:
                                packet.dts = packet.dts + delta
                            previous_dts = last_dts.get(pos)
                            if previous_dts is not None and packet.dts <= previous_dts:
                                packet.dts = previous_dts + 1
                            previous_pts = last_pts.get(pos)
                            if previous_pts is not None and packet.pts <= previous_pts:
                                packet.pts = previous_pts + 1
                            if (
                                packet.dts is not None
                                and packet.pts is not None
                                and packet.dts > packet.pts
                            ):
                                packet.pts = packet.dts
                            last_pts[pos] = packet.pts
                            last_dts[pos] = packet.dts

                    out_s = _stream_map.get(packet.stream)
                    if out_s is None:
                        for src, mapped in _stream_map.items():
                            if src.index == src_key:
                                out_s = mapped
                                break
                    bsf_entry = bsfs.get(src_key)
                    candidates = bsf_entry[0].filter(packet) if bsf_entry else [packet]
                    for pkt in candidates:
                        pkt.stream = out_s
                        if job.timeline_shift:
                            # Timeline path self-manages monotonicity above.
                            _out.mux(pkt)
                        else:
                            mux_clamp.mux(_out, pkt)
                            bytes_out += max(0, pkt.size or 0)

                for packet in inp.demux(src_streams):
                    _pause_hook(cancel_event)
                    if cancel_event and cancel_event.is_set():
                        if job.record_mode:
                            logger.info(
                                "Recording stopped by user (%d bytes) — keeping output", bytes_out
                            )
                            break
                        break
                    if (
                        job.duration_cap_s is not None
                        and time.monotonic() - start >= job.duration_cap_s
                    ):
                        logger.info("Recording reached duration cap (%.1fs)", job.duration_cap_s)
                        break
                    # The window is judged on DTS, not PTS: B-frame streams
                    # arrive in dts order with pts jumping back and forth, and
                    # a pts-based window drops the keyframe (pts < start) plus
                    # every early B-frame — the mux clamp then repairs the
                    # resulting non-monotonicity by stretching the whole
                    # timeline (a 1.2 s cut read as 2.1 s).
                    ts = packet.dts if packet.dts is not None else packet.pts
                    if ts is None:
                        continue
                    pkt_time = float(ts * packet.stream.time_base)
                    if (
                        job.snap_to_keyframe
                        and packet.stream.type == "video"
                        and packet.is_keyframe
                        and job_window_start is not None
                        and pkt_time < job_window_start
                    ):
                        # The seek landed on this keyframe: a stream copy must
                        # begin on one, so adopt it as the window start even
                        # though it sits before the requested cut point.
                        job_window_start = pkt_time
                    if job_window_start is not None and pkt_time < job_window_start:
                        continue
                    if win_end is not None and pkt_time > win_end:
                        break
                    _emit(packet)
                    if not job.record_mode:
                        bytes_out += 0  # counted in _emit

                    now = time.monotonic()
                    if on_progress and (now - last_report >= 0.25):
                        last_report = now
                        if job.record_mode:
                            elapsed = now - start
                            prog = (
                                min(0.99, elapsed / job.duration_cap_s)
                                if job.duration_cap_s and job.duration_cap_s > 0
                                else 0.05
                            )
                            on_progress(
                                prog,
                                f"Recording… {elapsed:.0f}s • {bytes_out // 1024} KB",
                            )
                        else:
                            prog = min(0.99, max(0.01, pkt_time / total_s)) if total_s > 0 else 0.5
                            label = (
                                f"Joining {Path(spec_in.path).name}… ({fi + 1}/{len(job.inputs)})"
                                if job.timeline_shift
                                else f"{job.progress_label}... {int(prog * 100)}%"
                            )
                            on_progress(prog, label)

                if fi > 0 and on_progress and job.timeline_shift:
                    on_progress(
                        min(0.95, (fi + 1) / len(job.inputs) * 0.95),
                        f"Joining {Path(spec_in.path).name}… ({fi + 1}/{len(job.inputs)})",
                    )
            finally:
                _close_container(inp)

        if out is None:  # no inputs opened (defensive; presets always pass one)
            raise ValueError("No inputs in copy job")

        # Drain BSF-delayed packets (EOF marker).
        for bsf_ctx, out_s in bsfs.values():
            for pkt in bsf_ctx.filter(None):
                pkt.stream = out_s
                mux_clamp.mux(out, pkt)

        if on_progress:
            if job.record_mode:
                total = time.monotonic() - start
                on_progress(1.0, f"Recorded {total:.0f}s • {bytes_out // 1024} KB")
            else:
                on_progress(1.0, job.complete_label)
    finally:
        if out is not None:
            _close_container(out)

    if (cancelled_any or (cancel_event and cancel_event.is_set())) and not job.record_mode:
        _discard_cancelled(job.output_path)
        raise InterruptedError(job.cancel_message)
    if job.record_mode and not Path(job.output_path).exists():
        # Zero-packet stops never trigger the muxer's lazy header write.
        Path(job.output_path).touch(exist_ok=True)
    return job.output_path


def probe_media(file_path: str) -> MediaInfo:
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

    with av.open(file_path, "r", timeout=_INPUT_TIMEOUT) as container:
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
            s_bitrate = getattr(stream, "bit_rate", None) or (
                stream.codec_context.bit_rate if stream.codec_context else None
            )

            # DataStream/AttachmentStream have no bit_rate attribute —
            # files with chapter tracks used to crash the dossier here.
            disp_obj = getattr(stream, "disposition", None)
            disp_flags: dict[str, bool] = {}
            if disp_obj is not None:
                # Disposition is an IntFlag: attribute access returns the
                # CLASS member (always truthy) — test bits, not attributes.
                disp_bits = int(disp_obj)
                for flag_name in _disposition_flag_names():
                    flag_bit = int(getattr(av.stream.Disposition, flag_name, 0))
                    if flag_bit and disp_bits & flag_bit:
                        disp_flags[flag_name] = True

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
                disposition=disp_flags,
            )

            if stype == "video":
                v_ctx = stream.codec_context
                if v_ctx:
                    s_info.width = v_ctx.width
                    s_info.height = v_ctx.height
                    s_info.pix_fmt = getattr(v_ctx.pix_fmt, "name", str(v_ctx.pix_fmt))
                    # average_rate can jitter ±0.06 between takes from the
                    # same phone; keep it as the probe fps (crossfade gate
                    # now tolerates 2 fps), but do not average r_frame_rate
                    # in — it is noisier and would widen the jitter further.
                    if stream.average_rate:
                        s_info.fps = float(stream.average_rate)
            elif stype == "audio":
                a_ctx = stream.codec_context
                if a_ctx:
                    s_info.sample_rate = a_ctx.sample_rate
                    s_info.channels = a_ctx.channels
                    s_info.channel_layout = getattr(a_ctx.layout, "name", str(a_ctx.layout))

            streams_info.append(s_info)

        # Rotation lives in the display matrix — no stream-level accessor
        # exists on this build, so decode until the first non-empty frame
        # and read frame.rotation. The first packet can yield nothing
        # (decoder delay), so the loop — not a single break — is the fix.
        first_video = next((s for s in streams_info if s.stream_type == "video"), None)
        if first_video is not None and container.streams.video:
            try:
                for _pkt in container.demux([container.streams.best("video")]):
                    _frames = _pkt.decode()
                    if _frames:
                        first_video.rotation = int(getattr(_frames[0], "rotation", 0) or 0)
                        break
            except Exception as exc:
                logger.warning("Rotation probe failed: %s", exc)

        # Chapters (container dicts → ChapterInfo with seconds)
        chapters: list[ChapterInfo] = []
        try:
            for raw_ch in container.chapters() or []:
                tb = raw_ch.get("time_base") or Fraction(1, 1000)
                ch_meta = raw_ch.get("metadata") or {}
                ch_id = int(raw_ch.get("id", 0))
                chapters.append(
                    ChapterInfo(
                        id=ch_id,
                        title=str(ch_meta.get("title") or f"Chapter {ch_id + 1}"),
                        start_s=float(raw_ch.get("start", 0) * tb),
                        end_s=float(raw_ch.get("end", 0) * tb),
                    )
                )
        except Exception as exc:
            logger.warning("Chapter read failed: %s", exc)

        # Generate formatted overview text
        summary_lines = [
            f"File: {p.name} ({file_size // 1024} KB)",
            f"Format: {fmt_long} [{fmt_name}]",
            f"Duration: {duration_s:.2f}s | Bitrate: {bitrate // 1000} kbps",
            f"Streams ({len(streams_info)}):",
        ]
        for s in streams_info:
            if s.stream_type == "video":
                rot = f", rot {s.rotation}°" if s.rotation else ""
                summary_lines.append(
                    f"  #{s.index} Video: {s.codec_name} "
                    f"({s.width}x{s.height}, {s.fps or 0:.1f} fps, {s.pix_fmt}{rot})"
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
        chapters=chapters,
        raw_dump=raw_dump,
    )


def _snap_start_to_keyframe(video_stream, start_s: float) -> float:
    """Nearest keyframe at-or-before ``start_s`` (stream-copy must start on one).

    Returns ``start_s`` unchanged when the container has no usable index —
    the caller keeps today's behavior as the fallback.
    """
    try:
        entries = video_stream.index_entries
        if not entries:
            return start_s
        tb = float(video_stream.time_base)
        idx = entries.search_timestamp(int(start_s / tb), backward=True)
        if idx is None or idx < 0:
            return start_s
        snapped = float(entries[idx].timestamp * tb)
        if snapped < 0:
            return 0.0
        return min(snapped, start_s)
    except Exception as exc:
        logger.warning("Keyframe snap unavailable: %s", exc)
        return start_s
