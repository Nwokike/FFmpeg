"""Output sizing and stream selection."""

from __future__ import annotations

import av

from services.engine_service.logs import logger


def _crop_dims(width: int, height: int, aspect: str) -> tuple[int, int]:
    """Center-crop dimensions for an aspect chip ("16:9", "1:1", "4:5").

    Crops (never scales) so quality is untouched; even-aligned for yuv420p.
    """
    try:
        rw, rh = (int(p) for p in aspect.split(":", 1))
        target = rw / rh
    except (ValueError, ZeroDivisionError):
        logger.warning("Bad crop aspect %r — keeping %sx%s", aspect, width, height)
        return width, height
    current = width / height
    if current > target:
        cw, ch = int(height * target), height
    else:
        cw, ch = width, int(width / target)
    # Clamp first, THEN even-align: aligning before min() lets an odd source
    # dim (e.g. 853px) come back through min() still odd, and the crop filter
    # rejects odd dims for yuv420p.
    cw, ch = min(cw, width), min(ch, height)
    cw = max(2, (cw // 2) * 2)
    ch = max(2, (ch // 2) * 2)
    return cw, ch


def _chain_declared_size(nodes, base: tuple[int, int] | None = None) -> tuple[int, int] | None:
    """The frame size a linear filter chain declares, if it declares one.

    Walks the chain in order: ``scale``/``crop`` with literal integer arguments
    set the geometry, ``transpose`` swaps it. ``base`` is the input frame size —
    a chain that only rotates needs it, or a 90° transpose would look unknown
    and the encoder would be opened for the un-swapped input. Expressions
    (``-2``, ``iw/2``) and every other filter leave the geometry unknown (None)
    — the caller keeps the input's size.
    """
    if not nodes:
        return None
    size = base
    for node in nodes:
        name = str(node[0])
        args = str(node[1]) if len(node) > 1 else ""
        parts = [part.strip() for part in args.replace(";", ":").split(":") if part.strip()]
        if name in ("scale", "crop"):
            if len(parts) < 2:
                return None
            try:
                width, height = int(parts[0]), int(parts[1])
            except ValueError:
                return None
            if width <= 0 or height <= 0:
                return None
            size = (width, height)
        elif name == "transpose" and size is not None:
            # 90/270° transposes swap the axes; hflip/vflip keep them. Only the
            # axis swap changes the encoder's declared size.
            size = (size[1], size[0])
    return size


def _select_stream(container, spec, kind: str):
    """The input stream one StreamSpec maps from: ``selector`` or the best of kind.

    ``selector`` is ``"best"`` (default) or an absolute stream index — the
    ``-map 0:v:1`` shape. An index that is not there (or is the wrong type)
    falls back to the best of kind, so a hand-written job cannot crash on a
    stream that does not exist.
    """
    selector = getattr(spec, "selector", "best")
    if isinstance(selector, int) and not isinstance(selector, bool):
        try:
            stream = container.streams[selector]
        except (IndexError, ValueError):
            stream = None
        if stream is not None and (kind == "any" or stream.type == kind):
            return stream
    return container.streams.best(kind)


def _graph_from_nodes(nodes: list[tuple[str, dict]], first_frame) -> av.filter.Graph:
    """Static FilterChain nodes -> configured Graph (video or audio).

    Mirrors the bespoke builders' wiring: buffer/abuffer source, named nodes
    in order, buffersink/abuffersink sink, then configure().
    """
    g = av.filter.Graph()
    if isinstance(first_frame, av.AudioFrame):
        src = g.add_abuffer(
            sample_rate=first_frame.sample_rate,
            format=first_frame.format.name,
            layout=first_frame.layout.name,
        )
        sink = g.add("abuffersink")
    else:
        src = g.add_buffer(template=first_frame)
        sink = g.add("buffersink")
    chain: list = [src]
    for name, args in nodes:
        if isinstance(args, str):
            # FFmpeg's own filter-argument syntax ("4:3:6:4.5", "I=-16") —
            # handed to avfilter_init_str untouched, so every filter this build
            # ships accepts exactly what `ffmpeg -vf` accepts.
            chain.append(g.add(name, args) if args else g.add(name))
        else:
            chain.append(g.add(name, **(dict(args) if args else {})))
    chain.append(sink)
    g.link_nodes(*chain)
    g.configure()
    return g
