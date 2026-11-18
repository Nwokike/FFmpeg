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

# Drawtext needs an explicit font file (no fontconfig in the lean build).
_FONT = Path(__file__).resolve().parent / "fonts" / "Roboto-Regular.ttf"
_DRAWTEXT_ESCAPES = (("\\", r"\\"), (":", r"\:"), ("'", r"\'"), ("%", r"\%"), (",", r"\,"))


def _drawtext_escaped(text: str) -> str:
    """One line of text as a drawtext argument value (newlines -> spaces)."""
    flat = " ".join(line.strip() for line in str(text).splitlines() if line.strip())
    for raw, escaped in _DRAWTEXT_ESCAPES:
        flat = flat.replace(raw, escaped)
    return flat


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
    fps: int | None = None,
    flip: str | None = None,
    crop_rect: tuple[int, int, int, int] | None = None,
    pad: tuple[int, int, str] | None = None,
    deinterlace: bool = False,
    gamma: float | None = None,
    drawtext: dict | None = None,
) -> av.filter.Graph | None:
    """buffer → crop?/eq?/denoise?/sharpen? → [overlay] → transpose?/setpts? → sink.

    Every presence-sensitive node is gated on this build's ``available_filters()``
    (e.g. eq/hqdn3d are compiled OUT here); returns None when no node applies so
    the caller keeps the plain reformat path.
    """
    avail = available_filters()

    middle: list = []
    base_w = frame.width  # post-crop width — sizes the watermark overlay

    if deinterlace and "yadif" in avail:
        middle.append(("yadif", None))

    if crop_rect and len(crop_rect) == 4 and "crop" in avail:
        cw, ch, cx, cy = (int(v) for v in crop_rect)
        if cw >= 2 and ch >= 2:
            middle.append(("crop", f"{cw}:{ch}:{cx}:{cy}"))
            base_w = cw

    if pad and len(pad) >= 2 and "pad" in avail:
        pw, ph = int(pad[0]), int(pad[1])
        color = str(pad[2]) if len(pad) > 2 and pad[2] else "black"
        if pw >= 2 and ph >= 2:
            middle.append(("pad", f"{pw}:{ph}:(ow-iw)/2:(oh-ih)/2:{color}"))
            base_w = pw

    if crop_aspect and crop_aspect != "original" and "crop" in avail:
        cw, ch = _crop_dims(frame.width, frame.height, crop_aspect)
        if (cw, ch) != (frame.width, frame.height):
            middle.append(("crop", f"{cw}:{ch}"))
            base_w = cw

    eq_bits: list[str] = []
    if eq:
        brightness = float(eq.get("brightness", 0.0) or 0.0)
        contrast = float(eq.get("contrast", 1.0) or 1.0)
        saturation = float(eq.get("saturation", 1.0) or 1.0)
        if abs(brightness) > 1e-6:
            eq_bits.append(f"brightness={brightness:+.3f}")
        if abs(contrast - 1.0) > 1e-6:
            eq_bits.append(f"contrast={contrast:.3f}")
        if abs(saturation - 1.0) > 1e-6:
            eq_bits.append(f"saturation={saturation:.3f}")
    if gamma is not None and abs(float(gamma) - 1.0) > 1e-6:
        eq_bits.append(f"gamma={float(gamma):.3f}")
    if eq_bits and "eq" in avail:
        middle.append(("eq", ":".join(eq_bits)))

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

    if flip:
        wanted = str(flip).lower()
        if "h" in wanted and "hflip" in avail:
            middle.append(("hflip", None))
        if "v" in wanted and "vflip" in avail:
            middle.append(("vflip", None))

    rot = rotation % 360
    tail: list = []
    if fps and "fps" in avail:
        # Real CFR conversion. Without this node the encoder is merely TOLD a
        # new rate and every frame is relabelled: a 30fps source "converted"
        # to 24fps came out 300/24 = 12.5s instead of 10s (measured on the
        # real-media pass). fps runs before transpose/setpts so the timing
        # change happens on the source timeline.
        tail.append(("fps", str(int(fps))))
    if rot == 90:
        tail.append(("transpose", "clock"))
    elif rot == 180:
        tail.append(("transpose", "clock"))
        tail.append(("transpose", "clock"))
    elif rot == 270:
        tail.append(("transpose", "cclock"))
    if drawtext:
        if "drawtext" in avail:
            text = _drawtext_escaped(str(drawtext.get("text") or ""))
            if text:
                size_pct = float(drawtext.get("size_pct", 0.05) or 0.05)
                color = str(drawtext.get("color") or "white")
                anchor = str(drawtext.get("position") or "bottom")
                y_expr = {
                    "top": "h*0.06",
                    "center": "(h-text_h)/2",
                }.get(anchor, "h-text_h-h*0.06")
                args = (
                    f"fontfile={_FONT}:text='{text}':fontsize=h*{size_pct:.4f}:"
                    f"fontcolor={color}:borderw=3:bordercolor=black:"
                    f"x=(w-text_w)/2:y={y_expr}"
                )
                window = drawtext.get("window")
                if window and len(window) == 2:
                    args += f":enable='between(t,{float(window[0]):.3f},{float(window[1]):.3f})'"
                tail.append(("drawtext", args))
        else:
            logger.info("Text overlay requested but this build has no drawtext filter")
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
