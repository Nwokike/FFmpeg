"""Native log capture, packet helpers, shared I/O constants."""

from __future__ import annotations

import contextlib
import functools
import logging

import av

logger = logging.getLogger(__name__)


logger = logging.getLogger("EngineService")

_INPUT_TIMEOUT = (5.0, 15.0)

_INPUT_OPTIONS = {"fflags": "+discardcorrupt"}


def _native_log_scope():
    """Capture native FFmpeg diagnostics for one job body.

    On exception, the last captured native line is attached as ``_native_log``
    (read by :func:`friendly_job_error`), so a failed encode carries the
    muxer/decoder's own words instead of only the Python traceback. Yields
    nothing; use as ``with _native_log_scope():`` around a job body.
    Thread-local by default, so concurrent jobs don't mix lines.
    """
    import contextlib as _contextlib

    @_contextlib.contextmanager
    def _scope():
        try:
            with av.logging.Capture() as logs:
                yield
        except BaseException as exc:
            if getattr(exc, "_native_log", "") == "":
                with contextlib.suppress(Exception):
                    lines = [str(getattr(entry, "message", entry)).strip() for entry in logs]
                    lines = [ln for ln in lines if ln]
                    if lines:
                        exc._native_log = lines[-1][:300]
            raise

    return _scope()


def _with_native_logs(fn):
    """Decorator: run a job body inside :func:`_native_log_scope`.

    Zero indentation churn vs wrapping every body by hand; the scope
    attaches the last native line to any escaping exception.
    """

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        with _native_log_scope():
            return fn(*args, **kwargs)

    return _wrapped


def _av_rational(value) -> av.AVRational:
    """Convert PyAV's Fraction time bases to the type rescale_ts requires."""
    if isinstance(value, av.AVRational):
        return value
    if value is None:
        return av.AVRational(1, 1000)
    return av.AVRational(value.numerator, value.denominator)


def _decode_packet(packet):
    """Yield decoded frames while isolating one malformed media packet.

    Real-world files occasionally contain a truncated AAC/H.264 packet. FFmpeg
    reports that packet as InvalidDataError; aborting an entire conversion for
    one bad packet is less useful than continuing with the surrounding frames.
    The warning is retained in the activity log so the output is not presented
    as silently lossless.
    """
    try:
        yield from packet.decode()
    except av.error.InvalidDataError as exc:
        stream = getattr(packet, "stream", None)
        logger.warning(
            "Skipping corrupt media packet (stream=%s pts=%s dts=%s): %s",
            getattr(stream, "index", "?"),
            getattr(packet, "pts", None),
            getattr(packet, "dts", None),
            exc,
        )


def _is_attached_picture(stream) -> bool:
    """Matroska copy paths must skip cover-art video streams."""
    try:
        return stream.type == "video" and bool(
            int(stream.disposition) & int(av.stream.Disposition.attached_pic)
        )
    except Exception:
        return False


def _codec_supports_mode(name: str, mode: str) -> bool:
    """True if ``name`` can be constructed in ``mode`` ('w' encoder, 'r' decoder).

    ``av.codec.codecs_available`` holds every descriptor name — decoders
    included — so membership is NOT proof an encoder exists; constructing the
    Codec in the target mode is the only honest check.
    """
    if name not in av.codec.codecs_available:
        return False
    try:
        av.codec.Codec(name, mode=mode)
        return True
    except Exception:
        return False
