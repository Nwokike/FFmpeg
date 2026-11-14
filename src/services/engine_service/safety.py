"""Mux safety: clamping, closing, seeking, dispositions."""

from __future__ import annotations

import av

from services.engine_service.logs import logger


class _MuxClamp:
    """Per-container packet DTS/PTS floor.

    The encoder can emit two packets with identical DTS even when frame PTS
    is strictly monotonic (observed 12800 >= 12800 on the phone's wheel —
    coarse 1/out_fps time bases quantize two frames onto one tick). The MP4
    muxer rejects those, and with bf=0 dts==pts so PTS needs the same floor.
    One instance per output container; every re-encode path muxes through it.
    """

    def __init__(self) -> None:
        self.last_pts: dict[int, int] = {}
        self.last_dts: dict[int, int] = {}

    def mux(self, container, pkt) -> None:
        stream_idx = pkt.stream.index if pkt.stream is not None else -1
        if pkt.pts is not None:
            floor = self.last_pts.get(stream_idx)
            if floor is not None and pkt.pts <= floor:
                pkt.pts = floor + 1
            self.last_pts[stream_idx] = pkt.pts
        if pkt.dts is not None:
            floor = self.last_dts.get(stream_idx)
            if floor is not None and pkt.dts <= floor:
                pkt.dts = floor + 1
            self.last_dts[stream_idx] = pkt.dts
        container.mux(pkt)


def _close_container(container) -> None:
    """Close a container without masking the encode-loop traceback.

    Trailer writes can fail on a broken output; if the loop already raised,
    that original error is the one the user must see — never the close.
    """
    try:
        container.close()
    except Exception as exc:
        logger.warning("Container close failed (output may be incomplete): %s", exc)


def _unknown_codec_error_type() -> type | None:
    """UnknownCodecError lives at av.codec.codec, not av.codec (no re-export)."""
    try:
        from av.codec.codec import UnknownCodecError

        return UnknownCodecError
    except Exception:
        return getattr(av.codec, "UnknownCodecError", None)


def _safe_seek(container: av.container.InputContainer, ts: int, *, backward: bool = True) -> None:
    """Seek, or decode from the start when the container's index can't.

    Rebasing a stream-copy cut to 0 leaves some mp4s whose index refuses
    seeks before their first entry (``av.error.PermissionError`` /
    "Cannot find an index entry before timestamp: 0"). Every caller demuxes
    with a time filter afterwards, so skipping the seek changes speed, never
    output. The failure is logged, not silenced.
    """
    try:
        container.seek(ts, backward=backward)
    except av.error.FFmpegError as exc:
        logger.warning("Seek unavailable (%s) — decoding from start; output unaffected", exc)


def _disposition_flag_names() -> tuple[str, ...]:
    return tuple(name for name in av.stream.Disposition.__members__)
