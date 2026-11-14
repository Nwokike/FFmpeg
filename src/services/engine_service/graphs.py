"""Filter graphs, previews, frame/packet re-timing."""

from __future__ import annotations

from errno import EAGAIN
from fractions import Fraction
from pathlib import Path

import av
from av.error import FFmpegError

from services.engine_service.logs import logger
from services.engine_service.sizing import _crop_dims


def _mjpeg_bytes(frame: av.VideoFrame, width: int) -> bytes:
    """Encode one frame as an in-memory JPEG (Cut screen thumbnail strip).

    Mirrors VideoFrame.save's encoder choice (mjpeg/yuvj420p) but targets
    bytes instead of a file — no disk round-trip.
    """
    w = max(2, int(width) // 2 * 2)
    h = max(2, int(frame.height * (w / frame.width)) // 2 * 2)
    rf = frame.reformat(width=w, height=h, format="yuvj420p")
    ctx = av.CodecContext.create("mjpeg", "w")
    ctx.width = w
    ctx.height = h
    ctx.pix_fmt = "yuvj420p"
    ctx.time_base = Fraction(1, 25)
    ctx.open()
    packets = list(ctx.encode(rf))
    packets.extend(ctx.encode(None))
    return b"".join(bytes(p) for p in packets)


_FINE_VIDEO_TB = Fraction(1, 90000)


def _rebase_pts(frame: av.VideoFrame, dst_tb: Fraction) -> None:
    """Rescale a frame's pts into dst_tb (Frame.time_base setter does not rescale)."""
    if not frame.time_base or dst_tb is None:
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
    frame: av.VideoFrame,
    rotation: int,
    speed: float,
    *,
    crop_aspect: str | None = None,
    eq: dict | None = None,
    denoise: str | None = None,
    sharpen: int | None = None,
    watermark: dict | None = None,
) -> av.filter.Graph | None:
    """buffer → crop?/eq?/denoise?/sharpen? → [overlay] → transpose?/setpts? → sink.

    Every presence-sensitive node is gated on this build's ``available_filters()``
    (e.g. eq/hqdn3d are compiled OUT here); returns None when no node applies so
    the caller keeps the plain reformat path.
    """
    avail = available_filters()

    middle: list = []
    base_w = frame.width  # post-crop width — sizes the watermark overlay

    if crop_aspect and crop_aspect != "original" and "crop" in avail:
        cw, ch = _crop_dims(frame.width, frame.height, crop_aspect)
        if (cw, ch) != (frame.width, frame.height):
            middle.append(("crop", f"{cw}:{ch}"))
            base_w = cw

    if eq and "eq" in avail:
        bits = []
        brightness = float(eq.get("brightness", 0.0) or 0.0)
        contrast = float(eq.get("contrast", 1.0) or 1.0)
        saturation = float(eq.get("saturation", 1.0) or 1.0)
        if abs(brightness) > 1e-6:
            bits.append(f"brightness={brightness:+.3f}")
        if abs(contrast - 1.0) > 1e-6:
            bits.append(f"contrast={contrast:.3f}")
        if abs(saturation - 1.0) > 1e-6:
            bits.append(f"saturation={saturation:.3f}")
        if bits:
            middle.append(("eq", ":".join(bits)))

    if denoise and denoise != "off":
        # hqdn3d is preferred but compiled out of this build; nlmeans and
        # atadenoise are the verified fallbacks.
        if "hqdn3d" in avail:
            middle.append(("hqdn3d", "3:2:6:4" if denoise == "low" else "6:4:12:8"))
        elif "nlmeans" in avail:
            middle.append(("nlmeans", f"s={'3' if denoise == 'low' else '7'}"))
        elif "atadenoise" in avail:
            middle.append(("atadenoise", None))
        else:
            logger.info("Denoise requested but no denoise filter is available")

    if sharpen and int(sharpen) > 0 and "unsharp" in avail:
        amount = 0.5 + (int(sharpen) / 100.0) * 1.5  # slider 0..100 → 0.5..2.0
        middle.append(("unsharp", f"5:5:{amount:.2f}:5:5:0"))

    rot = rotation % 360
    tail: list = []
    if rot == 90:
        tail.append(("transpose", "clock"))
    elif rot == 180:
        tail.append(("transpose", "clock"))
        tail.append(("transpose", "clock"))
    elif rot == 270:
        tail.append(("transpose", "cclock"))
    if abs(speed - 1.0) > 1e-6:
        tail.append(("setpts", f"PTS/{speed}"))

    # Watermark: movie (static PNG) → scale → overlay's second input.
    wm_ok = False
    wm_path = ""
    wm_w = 8
    position = "br"
    if watermark and "movie" in avail and "overlay" in avail:
        candidate = str(watermark.get("path") or "")
        if candidate and Path(candidate).exists():
            pct = max(2, min(60, int(watermark.get("width_pct", 20) or 20)))
            wm_path = candidate
            wm_w = max(2, (base_w * pct) // 100)
            position = str(watermark.get("position", "br"))
            wm_ok = True
        elif candidate:
            logger.warning("Watermark image missing: %s", candidate)

    if not middle and not tail and not wm_ok:
        return None  # everything gated off / all defaults — plain reformat path

    g = av.filter.Graph()
    src = g.add_buffer(template=frame, time_base=_FINE_VIDEO_TB)

    main_pre: list = [src]
    for name, args in middle:
        main_pre.append(g.add(name) if args is None else g.add(name, args))
    tail_nodes = [g.add(name) if args is None else g.add(name, args) for name, args in tail]
    sink = g.add("buffersink")

    if wm_ok:
        overlay = g.add("overlay", _WM_POSITIONS.get(position, _WM_POSITIONS["br"]))
        g.link_nodes(*main_pre, overlay)  # main path → overlay input 0
        movie = g.add("movie", filename=wm_path)
        wm_scale = g.add("scale", f"{wm_w}:-1")
        movie.link_to(wm_scale)
        wm_scale.link_to(overlay, input_idx=1)  # watermark → overlay input 1
        g.link_nodes(overlay, *tail_nodes, sink)
    else:
        g.link_nodes(*main_pre, *tail_nodes, sink)

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
    if frame.time_base:
        ab_kwargs["time_base"] = frame.time_base
    nodes: list = [g.add_abuffer(**ab_kwargs)]
    if volume_pct != 100:
        nodes.append(g.add("volume", f"{volume_pct / 100.0}"))
    nodes.extend(g.add("atempo", str(factor)) for factor in _atempo_factors(speed))
    if len(nodes) == 1:
        return None
    nodes.append(g.add("abuffersink"))
    g.link_nodes(*nodes)
    g.configure()
    return g


_FILTERS_AVAIL: set[str] | None = None


def available_filters() -> set[str]:
    """Names of every filter compiled into this FFmpeg build (cached)."""
    global _FILTERS_AVAIL
    if _FILTERS_AVAIL is None:
        try:
            _FILTERS_AVAIL = set(av.filter.filters_available or [])
        except Exception as exc:
            logger.warning("Filter enumeration failed: %s", exc)
            _FILTERS_AVAIL = set()
    return _FILTERS_AVAIL


_FILTER_DESCRIPTIONS: dict[str, str] = {}


def filter_description(name: str) -> str:
    """One-line purpose of a filter from the wheel itself ("" when absent).

    Powers in-UI help subtitles: the text comes from the installed build, so
    it can never describe a filter this wheel doesn't ship.
    """
    if name in _FILTER_DESCRIPTIONS:
        return _FILTER_DESCRIPTIONS[name]
    try:
        text = str(av.filter.Filter(name).description or "").strip().splitlines()[0]
    except Exception:
        text = ""
    _FILTER_DESCRIPTIONS[name] = text
    return text


_WM_POSITIONS = {
    "br": "main_w-overlay_w-10:main_h-overlay_h-10",
    "bl": "10:main_h-overlay_h-10",
    "tl": "10:10",
    "tr": "main_w-overlay_w-10:10",
    "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
}
