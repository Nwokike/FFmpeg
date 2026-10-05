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

import contextlib
import hashlib
import json
import logging
import math
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from errno import EAGAIN
from fractions import Fraction
from pathlib import Path
from threading import Event
from urllib.parse import urljoin

import av
import av.codec
import av.codec.hwaccel
import av.filter
import av.stream
import httpx
from av.error import FFmpegError
from av.filter.loudnorm import stats as loudnorm_stats
from av.video.reformatter import VideoReformatter

from core.engine_probe import probe
from core.state import ChapterInfo, MediaInfo, MediaStreamInfo
from core.storage_paths import get_cache_dir, get_temp_dir

logger = logging.getLogger("EngineService")

# Local media opens get bounded open/read waits so a disconnected SAF URI or
# damaged SD card cannot freeze the serial worker indefinitely.
_INPUT_TIMEOUT = (5.0, 15.0)

# Corrupt packets are dropped at demux (same outcome as the _decode_packet
# InvalidDataError skip, less noise). Harmless when ignored by the build.
_INPUT_OPTIONS = {"fflags": "+discardcorrupt"}

# PyAV defaults to discarding native FFmpeg diagnostics. Keep warnings/errors
# flowing into the app's logging bridge so a failed encode explains itself.
try:
    av.logging.set_level(av.logging.WARNING)
except Exception:  # pragma: no cover - depends on the linked FFmpeg build
    logger.debug("PyAV native logging could not be configured", exc_info=True)


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
    import functools

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


class EngineCapabilityError(ValueError):
    """Requested operation is not supported by this device's FFmpeg build.

    Subclasses ValueError so the existing job-error path (and every
    ``pytest.raises(ValueError)`` contract) keeps working, while giving the UI
    a message that names the missing capability instead of leaking
    ``av.codec.UnknownCodecError: h264``.
    """


# FFmpeg exposes the same encoder under several names. Resolve the friendly
# name a screen/job asks for onto whichever alias this build actually ships.
_VIDEO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    "libx264": ("libx264", "h264"),
    "h264": ("h264", "libx264"),
    "libx265": ("libx265", "hevc", "x265"),
    "hevc": ("hevc", "libx265", "x265"),
    "x265": ("x265", "libx265", "hevc"),
    "libsvtav1": ("libsvtav1", "av1"),
    "av1": ("av1", "libsvtav1"),
    "vp9": ("vp9", "libvpx-vp9", "libvpx"),
    "libvpx-vp9": ("libvpx-vp9", "vp9", "libvpx"),
    "libvpx": ("libvpx", "vp9", "libvpx-vp9"),
    "mpeg4": ("mpeg4",),
    "mjpeg": ("mjpeg",),
    "prores": ("prores",),
    "ffv1": ("ffv1",),
    "libwebp": ("libwebp",),
    "png": ("png",),
    "gif": ("gif",),
}
_AUDIO_CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    "aac": ("aac",),
    "flac": ("flac",),
    "opus": ("libopus", "opus"),
    "libopus": ("libopus", "opus"),
    "mp3": ("libmp3lame", "mp3"),
    "libmp3lame": ("libmp3lame", "mp3"),
    "wav": ("pcm_s16le",),
    "pcm_s16le": ("pcm_s16le",),
    "pcm_s24le": ("pcm_s24le", "pcm_s16le"),
    "vorbis": ("vorbis", "libvorbis"),
    "libvorbis": ("libvorbis", "vorbis"),
    "ogg": ("vorbis", "libvorbis"),
    "alac": ("alac",),
    "m4a": ("aac",),
}
_VIDEO_CODEC_LABELS = {
    "libx264": "H.264",
    "h264": "H.264",
    "libx265": "HEVC",
    "hevc": "HEVC",
    "x265": "HEVC",
    "vp9": "VP9",
    "libvpx-vp9": "VP9",
    "libvpx": "VP9",
    "libsvtav1": "AV1",
    "av1": "AV1",
    "mpeg4": "MPEG-4",
    "mjpeg": "MJPEG",
    "prores": "ProRes",
    "ffv1": "FFV1",
    "libwebp": "WebP",
    "png": "PNG",
    "gif": "GIF",
}
_AUDIO_CODEC_LABELS = {
    "aac": "AAC",
    "flac": "FLAC",
    "opus": "Opus",
    "libopus": "Opus",
    "mp3": "MP3",
    "libmp3lame": "MP3",
    "wav": "WAV",
    "pcm_s16le": "WAV",
    "pcm_s24le": "WAV 24-bit",
    "vorbis": "Vorbis",
    "libvorbis": "Vorbis",
    "ogg": "Vorbis",
    "alac": "ALAC",
    "m4a": "AAC",
}


def _friendly_codec(requested: str, kind: str) -> str:
    """Map a codec name onto a name users recognise ('libx264' → 'H.264')."""
    labels = _VIDEO_CODEC_LABELS if kind == "video" else _AUDIO_CODEC_LABELS
    return labels.get(requested) or requested


def _encoder_pix_fmt(codec_name: str) -> str:
    """A pixel format the encoder actually accepts.

    Video transcodes default to yuv420p; still-image codecs (png = rgb24/rgba/
    pal8/gray only) reject it with av.error.ArgumentError at the first encode
    — real crash from the E2E pass. Falls back to the encoder's first declared
    format when none of the usual candidates match.
    """
    preferred = ("yuv420p", "yuvj420p", "rgb24", "rgba", "rgb8")
    try:
        codec = av.codec.Codec(codec_name, "w")
        declared = [f.name for f in codec.video_formats or []]
    except Exception:
        return "yuv420p"
    if not declared:
        return "yuv420p"
    for name in preferred:
        if name in declared:
            return name
    return declared[0]


def _encoder_open_kwargs(codec_name: str) -> dict:
    """Extra ``add_stream`` kwargs an audio encoder needs to actually open.

    Vorbis is an experimental encoder on this FFmpeg build (avcodec_open2
    refuses without strict -2); the terse ``{}`` in the native log is the
    fingerprint. Callers that resolve user-chosen audio codecs must spread
    this — resolving is not opening (see the E2E vorbis crash).
    """
    if codec_name == "vorbis":
        return {"options": {"strict": "-2"}}
    return {}


# Container ↔ codec pairs the wheel's muxers actually accept. Keyed by
# container extension (no dot); values are (video codecs, audio codecs)
# using RESOLVED encoder names as the engine emits them. Anything outside a
# cell fails at mux time AFTER a full encode — check_pair() exists so the UI
# refuses before Start instead of after minutes of work.
_CONTAINER_CODEC_MATRIX: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "mp4": (
        frozenset({"libx264", "h264", "libx265", "hevc", "mpeg4", "libsvtav1", "av1"}),
        frozenset({"aac", "libmp3lame", "mp3", "ac3"}),
    ),
    "mov": (
        frozenset(
            {
                "libx264",
                "h264",
                "libx265",
                "hevc",
                "mpeg4",
                "prores",
                "libsvtav1",
                "av1",
            }
        ),
        frozenset({"aac", "alac", "pcm_s16le", "pcm_s24le"}),
    ),
    "mkv": (
        frozenset(
            {
                "libx264",
                "h264",
                "libx265",
                "hevc",
                "mpeg4",
                "vp9",
                "libvpx-vp9",
                "libvpx",
                "libsvtav1",
                "av1",
                "ffv1",
            }
        ),
        frozenset({"aac", "flac", "libopus", "opus", "vorbis", "pcm_s16le", "pcm_s24le"}),
    ),
    "webm": (
        frozenset({"vp9", "libvpx-vp9", "libvpx", "libsvtav1", "av1"}),
        frozenset({"libopus", "opus", "vorbis"}),
    ),
    "avi": (
        frozenset({"mpeg4", "mjpeg"}),
        frozenset({"pcm_s16le", "pcm_s24le", "libmp3lame", "mp3"}),
    ),
    "m4a": (frozenset(), frozenset({"aac", "alac"})),
    "mp3": (frozenset(), frozenset({"libmp3lame", "mp3"})),
    "ogg": (frozenset(), frozenset({"vorbis", "libopus", "opus", "flac"})),
    "opus": (frozenset(), frozenset({"libopus", "opus"})),
    "flac": (frozenset(), frozenset({"flac"})),
    "wav": (frozenset(), frozenset({"pcm_s16le", "pcm_s24le"})),
}


def check_pair(container: str, video_codec: str | None, audio_codec: str | None) -> str | None:
    """None when (container, vcodec, acodec) muxes; else the refusal reason.

    Aliases resolve first (libx264↔h264 …), so an h264-only wheel still
    offers H.264 instead of hiding the chip. Unknown containers fail OPEN
    (None) — the matrix covers the wheel's muxers, not every FFmpeg build.
    """
    key = (container or "").lower().lstrip(".")
    cell = _CONTAINER_CODEC_MATRIX.get(key)
    if cell is None:
        return None
    allowed_video, allowed_audio = cell
    if video_codec:
        try:
            resolved = _resolve_video_codec(video_codec)
        except Exception:
            resolved = video_codec
        candidates = {video_codec, resolved}
        try:
            from core.engine_probe import can_encode as _can_encode

            encodable = {c for c in candidates if _can_encode(c)}
            if encodable:
                candidates = encodable
        except Exception:
            pass
        if not (candidates & allowed_video):
            return (
                f"{_friendly_codec(video_codec, 'video')} is not muxable into .{key} "
                f"on this build — pick {sorted(allowed_video)[0] if allowed_video else 'another container'}"
            )
    if audio_codec:
        try:
            resolved_audio = _resolve_audio_codec(audio_codec)
        except Exception:
            resolved_audio = audio_codec
        if resolved_audio not in allowed_audio and audio_codec not in allowed_audio:
            return (
                f"{_friendly_codec(audio_codec, 'audio')} is not muxable into .{key} on this build"
            )
    return None


def check_params(
    video_codec: str | None = None,
    fps: float | int | str | None = None,
    sample_rate: int | None = None,
    pix_fmt: str | None = None,
) -> str | None:
    """None when the encode params fit the wheel; else the refusal reason.

    Validates fps against the encoder's declared frame rates (when declared),
    sample_rate against audio rates, and pix_fmt against video formats — so a
    120fps request to a 30fps-max encoder refuses before Start, not mid-job.
    Undeclared capabilities fail OPEN (None): absence of data is not proof of
    absence of support.
    """
    from fractions import Fraction

    from core.engine_probe import probe as _probe

    try:
        caps = _probe()
    except Exception:
        return None
    if video_codec and fps:
        try:
            want = float(Fraction(str(fps)))
        except (TypeError, ValueError, ZeroDivisionError):
            return f"Frame rate {fps!r} is not a number"
        for cand in (video_codec,):
            rates = caps.encoder_frame_rates.get(cand, [])
            nums: list[float] = []
            for r in rates:
                try:
                    nums.append(float(Fraction(str(r))))
                except (TypeError, ValueError, ZeroDivisionError):
                    continue
            if nums and max(nums) > 0 and want > max(nums) * 1.01:
                return (
                    f"{want:g} fps exceeds what {video_codec} declares "
                    f"(max {max(nums):g} fps on this build)"
                )
    if sample_rate:
        try:
            want_rate = int(sample_rate)
        except (TypeError, ValueError):
            return f"Sample rate {sample_rate!r} is not a number"
        known_rates: set[int] = set()
        for rates in caps.encoder_audio_rates.values():
            known_rates.update(rates)
        if known_rates and want_rate not in known_rates:
            nearest = min(known_rates, key=lambda r: abs(r - want_rate))
            return f"{want_rate} Hz is unusual — nearest declared rate is {nearest} Hz"
    if video_codec and pix_fmt:
        forms = caps.video_codec_formats.get(video_codec, [])
        if forms and pix_fmt not in forms:
            return f"{pix_fmt} is not a declared pixel format for {video_codec}"
    return None


def available_video_encoders() -> list[str]:
    """Verified mode='w' video encoders this build ships, preference order."""
    return list(probe().video_encoder_picks)


def available_audio_encoders() -> list[str]:
    """Verified mode='w' audio encoders this build ships, preference order."""
    return list(probe().audio_encoder_picks)


def _resolve_codec(
    requested: str,
    aliases: dict[str, tuple[str, ...]],
    labels: dict[str, str],
    kind: str,
) -> str:
    """Return a verified encoder name for ``requested`` or raise a clear error.

    Constructing ``av.codec.Codec(name, mode='w')`` is the only honest check —
    ``codecs_available`` also lists decoders, which is exactly how the Android
    build reached ``add_stream('h264')`` and exploded with UnknownCodecError.
    """
    for candidate in aliases.get(requested, (requested,)):
        if _codec_supports_mode(candidate, "w"):
            if candidate != requested:
                logger.info(
                    "Resolved %s codec %r to available encoder %r",
                    kind,
                    requested,
                    candidate,
                )
            return candidate

    available = available_video_encoders() if kind == "video" else available_audio_encoders()
    label = _friendly_codec(requested, kind)
    if available:
        options = ", ".join(available)
        detail = f" This device can encode with: {options}."
    else:
        detail = f" This device's FFmpeg build ships no {kind} encoders at all."
    raise EngineCapabilityError(
        f"{label} encoding is not available in this device's FFmpeg build.{detail}"
    )


def _resolve_video_codec(requested: str) -> str:
    return _resolve_codec(requested, _VIDEO_CODEC_ALIASES, _VIDEO_CODEC_LABELS, "video")


def _resolve_audio_codec(requested: str) -> str:
    return _resolve_codec(requested, _AUDIO_CODEC_ALIASES, _AUDIO_CODEC_LABELS, "audio")


def friendly_job_error(exc: BaseException) -> str:
    """Render a job exception as a message a person can act on.

    PyAV's raw text (``av.codec.UnknownCodecError: h264``) is what the phone
    showed before. Anything we cannot translate is returned unchanged so real
    failures are never hidden behind a vague apology.
    """
    if isinstance(exc, EngineCapabilityError):
        return str(exc)

    # UnknownCodecError is a ValueError subclass, so catch it before the
    # generic ValueError branch below would swallow it. It lives at
    # av.codec.codec (no av.codec re-export) — see _unknown_codec_error_type.
    unknown_codec = _unknown_codec_error_type()
    if unknown_codec is not None and isinstance(exc, unknown_codec):
        return (
            "This device's FFmpeg build can't encode that format. "
            "Open Engine Info to see what it supports."
        )

    protocol_errors = tuple(
        error_type
        for name in ("ProtocolNotFound", "ProtocolNotFoundError")
        if isinstance(error_type := getattr(av.error, name, None), type)
    )
    if protocol_errors and isinstance(exc, protocol_errors):
        return f"This device's FFmpeg build can't open that protocol: {exc}"

    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (28, 122):
        return "Not enough storage space to finish this job. Free some space and retry."

    if isinstance(exc, av.error.TimeoutError):
        return "Connection timed out — check the URL and your network."
    if isinstance(exc, av.error.InvalidDataError):
        return f"This file looks damaged or truncated: {exc}"
    http_errors = tuple(
        error_type
        for name in (
            "HTTPError",
            "HTTPClientError",
            "HTTPBadRequestError",
            "HTTPUnauthorizedError",
            "HTTPForbiddenError",
            "HTTPNotFoundError",
            "HTTPTooManyRequestsError",
            "HTTPServerError",
        )
        if isinstance(error_type := getattr(av.error, name, None), type)
    )
    if http_errors and isinstance(exc, http_errors):
        return f"The server refused the stream: {exc}"

    native = getattr(exc, "_native_log", "")
    if native:
        return f"{exc} — native log: {native}"
    return str(exc)


def _hardware_decode(enabled: bool):
    """Return a safe PyAV hardware decoder, or None when unavailable."""
    if not enabled:
        return None
    try:
        devices = list(av.codec.hwaccel.hwdevices_available())
        for preferred in ("d3d11va", "qsv", "cuda", "vaapi", "dxva2"):
            if preferred in devices:
                logger.info("Using PyAV hardware decoder: %s", preferred)
                return av.codec.hwaccel.HWAccel(preferred, allow_software_fallback=True)
        logger.info("Hardware acceleration requested but no supported decoder is available")
    except Exception as exc:
        logger.info("Hardware acceleration unavailable: %s", exc)
    return None


def _pick_video_encoder(preferred: str = "libx264", fallback: str = "h264") -> str:
    """Return a verified encoder, or raise a clear capability error.

    Both names are checked before returning; an unchecked fallback is what
    produced ``UnknownCodecError: h264`` on the Android LGPL wheel.
    """
    return _resolve_video_codec(fallback if not _codec_supports_mode(preferred, "w") else preferred)


def _exact_rate(value, default: int = 30):
    """Frame rate preserving fractional NTSC rates (30000/1001, not 29).

    ``int(average_rate)`` truncated 29.97→29, declaring the wrong encoder
    timeline. ``add_stream(rate=Fraction)`` keeps average_rate exact; ints
    pass through unchanged. Clamped to 1..120 downstream as before.
    """
    if value is None:
        return default
    try:
        rate = Fraction(value).limit_denominator(1001)
    except (TypeError, ValueError, ZeroDivisionError):
        return default
    if rate <= 0:
        return default
    return rate


def _supported_encoder_options(codec_name: str, requested: dict[str, str]) -> dict[str, str]:
    """Keep only options advertised by this wheel's encoder context."""
    try:
        ctx = av.CodecContext.create(codec_name, "w")
        valid = {str(option.name) for option in ctx.supported_options.private}
    except Exception as exc:
        logger.debug("Could not inspect options for %s: %s", codec_name, exc)
        return requested
    dropped = sorted(set(requested) - valid)
    if dropped:
        logger.info("Dropping unsupported %s encoder options: %s", codec_name, ", ".join(dropped))
    return {key: value for key, value in requested.items() if key in valid}


def _optional_encoder_knobs(
    *,
    gop_size: int | None = None,
    max_b_frames: int | None = None,
    qmin: int | None = None,
    qmax: int | None = None,
    thread_count: int | None = None,
    profile: str | None = None,
    level: str | None = None,
) -> dict[str, str]:
    """Translate optional knob params to encoder option dict (unset = absent).

    Values are validated to sane ranges here (positive ints, non-empty
    strings); unknown-to-the-wheel keys still drop later in
    :func:`_supported_encoder_options`, so a GPL-only key can never break an
    LGPL encode — it vanishes with an info line.
    """
    knobs: dict[str, str] = {}
    for key, value in (
        ("g", gop_size),
        ("bf", max_b_frames),
        ("qmin", qmin),
        ("qmax", qmax),
        ("threads", thread_count),
    ):
        if value is None:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            knobs[key] = str(number)
    for key, value in (("profile", profile), ("level", level)):
        if value:
            text = str(value).strip()
            if text:
                knobs[key] = text
    return knobs


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


# Stream disposition flags surfaced in the dossier (av.stream.Disposition names).
# Measured against the installed wheel (30 members incl. IntFlag helpers) —
# only real track flags are listed; helpers like bit_count/numerator are not.
_DISPOSITION_FLAG_NAMES = (
    "default",
    "dub",
    "original",
    "comment",
    "lyrics",
    "karaoke",
    "forced",
    "hearing_impaired",
    "visual_impaired",
    "clean_effects",
    "attached_pic",
    "timed_thumbnails",
    "non_diegetic",
    "captions",
    "descriptions",
    "metadata",
    "dependent",
    "still_image",
    "multilayer",
)


# ── Subtitle cue model + hand writers (no muxer dependency) ──────────────


@dataclass
class SubCue:
    """One extracted subtitle cue. Times in seconds; ``text`` uses real newlines."""

    start_s: float
    end_s: float
    text: str


def _fmt_srt_time(sec: float) -> str:
    """00:00:02,000 style (SRT)."""
    if sec < 0:
        sec = 0.0
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_vtt_time(sec: float) -> str:
    """00:00:02.000 style (WebVTT)."""
    if sec < 0:
        sec = 0.0
    ms = round(sec * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _fmt_ass_time(sec: float) -> str:
    """0:00:02.00 style (ASS, centiseconds)."""
    if sec < 0:
        sec = 0.0
    cs = round(sec * 100)
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


_ASS_HEADER = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "PlayResX: 384\n"
    "PlayResY: 288\n"
    "ScaledBorderAndShadow: yes\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,"
    "100,100,0,0,1,1,1,2,10,10,10,1\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def _write_srt(path: str, cues: list[SubCue]) -> None:
    blocks = [
        f"{i}\n{_fmt_srt_time(c.start_s)} --> {_fmt_srt_time(c.end_s)}\n{c.text}\n"
        for i, c in enumerate(cues, start=1)
    ]
    Path(path).write_text("\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def _write_vtt(path: str, cues: list[SubCue]) -> None:
    blocks = [f"{_fmt_vtt_time(c.start_s)} --> {_fmt_vtt_time(c.end_s)}\n{c.text}\n" for c in cues]
    Path(path).write_text(
        "WEBVTT\n\n" + "\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8"
    )


def _write_ass(path: str, cues: list[SubCue]) -> None:
    lines = [_ASS_HEADER]
    for c in cues:
        # ASS carries wraps as \N; styles from the source are intentionally dropped.
        text = c.text.replace("\r\n", "\n").replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{_fmt_ass_time(c.start_s)},{_fmt_ass_time(c.end_s)},"
            f"Default,,0,0,0,,{text}\n"
        )
    Path(path).write_text("".join(lines), encoding="utf-8")


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


# Fine-grained time base for the video filter pipeline: setpts at speed≠1 on a
# coarse stream tb (e.g. 1/30) quantizes to duplicate pts → non-monotonic dts →
# mp4 muxer EINVAL. 1/90000 keeps sub-frame spacing exact. Audio graphs stay on
# their sample-based tb (already far finer than any atempo shift).
_FINE_VIDEO_TB = Fraction(1, 90000)


def _rebase_pts(frame: av.VideoFrame, dst_tb: Fraction) -> None:
    """Rescale a frame's pts into dst_tb (Frame.time_base setter does not rescale)."""
    if frame.time_base is None or dst_tb is None:
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
    if frame.time_base is not None:
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


def _discard_cancelled(path: str, *, directory: bool = False) -> None:
    """Best-effort removal of a partial output left behind by a cancelled job."""
    try:
        if directory:
            shutil.rmtree(path, ignore_errors=True)
        elif Path(path).exists():
            Path(path).unlink()
    except OSError as exc:
        logger.warning("Failed to remove cancelled output %s: %s", path, exc)


# Queue-pause switch: wired once at startup to the JobQueue's Event (single
# worker thread, so a module-level hook beats threading a param through every
# operation). Checked at each operation's packet loop top.
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


# Filter availability — cached per process so the Filters screen can disable
# features (naming the missing filter) instead of failing mid-job.
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


_WM_POSITIONS = {
    "br": "main_w-overlay_w-10:main_h-overlay_h-10",
    "bl": "10:main_h-overlay_h-10",
    "tl": "10:10",
    "tr": "main_w-overlay_w-10:10",
    "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
}


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
                    for flag_name in _DISPOSITION_FLAG_NAMES:
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

    @staticmethod
    @_with_native_logs
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
        speed: float = 1.0,
        volume_pct: int = 100,
        rotation: int = 0,
        crop_aspect: str | None = None,
        eq: dict | None = None,
        denoise: str | None = None,
        sharpen: int | None = None,
        watermark: dict | None = None,
        hardware_accel: bool = False,
        gop_size: int | None = None,
        max_b_frames: int | None = None,
        qmin: int | None = None,
        qmax: int | None = None,
        thread_count: int | None = None,
        profile: str | None = None,
        level: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Transcode video/audio with quality, scaling, filters, and transforms.

        ``gop_size/max_b_frames/qmin/qmax/thread_count/profile/level`` are
        optional encoder knobs: each flows through
        :func:`_supported_encoder_options`, so keys the wheel's encoder lacks
        drop with an info line instead of failing the job.
        """
        hwaccel = _hardware_decode(hardware_accel)
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, hwaccel=hwaccel)
        try:
            out = av.open(output_path, "w")
        except Exception:
            inp.close()
            raise

        try:
            # Container metadata + chapters ride along — only remux used to keep them.
            if inp.metadata:
                out.metadata.update(inp.metadata)
            try:
                out.set_chapters(inp.chapters())
            except Exception as exc:
                logger.debug("Chapter copy skipped: %s", exc)

            in_video = inp.streams.best("video")
            in_audio = inp.streams.best("audio")

            need_vfilter = (
                rotation % 360 != 0
                or abs(speed - 1.0) > 1e-6
                or bool(crop_aspect and crop_aspect != "original")
                or bool(eq)
                or bool(denoise and denoise != "off")
                or bool(sharpen)
                or bool(watermark)
            )
            need_afilter = volume_pct != 100 or abs(speed - 1.0) > 1e-6
            video_graph: av.filter.Graph | None = None
            audio_graph: av.filter.Graph | None = None

            out_video = None
            if in_video:
                # Video stream setup (exact rate: 29.97 stays 30000/1001, not 29)
                target_fps = fps if fps else _exact_rate(in_video.average_rate)
                out_fps = max(1, min(target_fps, 60))

                # Resolve against the wheel's verified encoder set so a mobile
                # LGPL build reports a friendly error instead of crashing at
                # add_stream with an UnknownCodecError.
                chosen_vcodec = _resolve_video_codec(video_codec)

                # setpts changes the effective frame rate (30fps sped 1.5x arrives
                # as 45fps); declare it so the encoder's DTS model matches reality.
                eff_rate = (
                    max(1, -(-round(out_fps * speed * 1000) // 1000))
                    if need_vfilter and speed > 0
                    else out_fps
                )
                out_video = out.add_stream(chosen_vcodec, rate=eff_rate)
                target_w = scale_width or in_video.width
                target_h = scale_height or in_video.height
                # Crop defines the final size when no explicit scale is set —
                # otherwise the post-graph reformat would upscale right back.
                if (
                    crop_aspect
                    and crop_aspect != "original"
                    and scale_width is None
                    and scale_height is None
                ):
                    target_w, target_h = _crop_dims(
                        in_video.width or target_w,
                        in_video.height or target_h,
                        crop_aspect,
                    )
                if rotation % 180 == 90:  # 90°/270° transposes swap width/height
                    target_w, target_h = target_h, target_w
                # Dimensions must be even
                target_w = (target_w // 2) * 2
                target_h = (target_h // 2) * 2

                out_video.width = target_w
                out_video.height = target_h
                # Encoder-fitted pixel format: still codecs (png) reject yuv420p.
                enc_pix_fmt = _encoder_pix_fmt(chosen_vcodec)
                out_video.pix_fmt = enc_pix_fmt
                # With the filter graph active, timestamps arrive on the fine
                # 1/90000 tb with speed-warped spacing; bf=0 makes dts==pts so the
                # muxer sees the same strict sequence the graph produced.
                out_video.time_base = _FINE_VIDEO_TB if need_vfilter else Fraction(1, out_fps)
                out_video.options = _supported_encoder_options(
                    chosen_vcodec,
                    {"crf": str(crf), "preset": preset}
                    | ({"bf": "0"} if need_vfilter else {})
                    | _optional_encoder_knobs(
                        gop_size=gop_size,
                        max_b_frames=max_b_frames,
                        qmin=qmin,
                        qmax=qmax,
                        thread_count=thread_count,
                        profile=profile,
                        level=level,
                    ),
                )

            out_audio = None
            if in_audio:
                chosen_acodec = _resolve_audio_codec(audio_codec)
                # Opus is 48k-native; the stream resamples fed frames itself
                # (verified: 44.1k frames into a 48k stream encode cleanly).
                a_rate = 48000 if chosen_acodec in ("opus", "libopus") else (in_audio.rate or 44100)
                out_audio = out.add_stream(
                    chosen_acodec,
                    rate=a_rate,
                    **_encoder_open_kwargs(chosen_acodec),
                )
                # Installed wheel: channels is read-only; layout is the writable source of truth
                n_ch = min(2, in_audio.channels or 2)
                out_audio.layout = "stereo" if n_ch == 2 else "mono"

            video_reformatter = VideoReformatter()
            last_video_pts = -1
            # Packet-level DTS/PTS floor per output stream (see _MuxClamp):
            # the encoder can still emit identical stamps even when frame PTS
            # is strictly monotonic. Shared by all encode sites below.
            mux_clamp = _MuxClamp()

            def _mux_packet(container, pkt) -> None:
                mux_clamp.mux(container, pkt)

            def _monotonic_video_pts(frame: av.VideoFrame) -> None:
                """Rebase every output frame to the encoder time base.

                Hardware decoders and VFR sources can hand FFmpeg duplicate or
                backwards timestamps.  The MP4 muxer requires strict DTS
                monotonicity, so preserve timing when possible and advance by
                one tick when the source timestamp is not strictly increasing.
                """
                nonlocal last_video_pts
                out_tb = out_video.time_base or Fraction(1, out_fps)
                candidate = None
                if frame.pts is not None and frame.time_base is not None:
                    candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
                if candidate is None or candidate <= last_video_pts:
                    candidate = last_video_pts + 1
                frame.pts = candidate
                frame.time_base = out_tb
                # Decoder keyframe hints describe the source GOP, not the
                # output encoder's GOP; forwarding them makes libx264 force
                # extra I-frames (and can interact badly with hw decode).
                frame.pict_type = 0
                frame.key_frame = False
                last_video_pts = candidate

            last_audio_pts = -1

            def _monotonic_audio_pts(frame: av.AudioFrame) -> None:
                nonlocal last_audio_pts
                out_tb = out_audio.time_base or Fraction(1, out_audio.rate or 44100)
                candidate = None
                if frame.pts is not None and frame.time_base is not None:
                    candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
                if candidate is None or candidate <= last_audio_pts:
                    candidate = last_audio_pts + max(1, frame.samples)
                frame.pts = candidate
                frame.time_base = out_tb
                last_audio_pts = candidate

            total_duration = float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
            last_report = 0.0
            processed_pts = 0.0

            streams_to_demux = [s for s in (in_video, in_audio) if s]

            for packet in inp.demux(streams_to_demux):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    logger.info("Transcode cancelled by user.")
                    break

                if packet.size == 0 or (packet.pts is None and packet.dts is None):
                    continue

                if in_video and packet.stream == in_video:
                    for frame in _decode_packet(packet):
                        if cancel_event and cancel_event.is_set():
                            break

                        # Progress reads the INPUT timeline (before setpts re-times frames)
                        if frame.time:
                            processed_pts = frame.time

                        if need_vfilter and video_graph is None:
                            video_graph = _build_video_filter_graph(
                                frame,
                                rotation,
                                speed,
                                crop_aspect=crop_aspect,
                                eq=eq,
                                denoise=denoise,
                                sharpen=sharpen,
                                watermark=watermark,
                            )

                        out_frames = [frame]
                        if video_graph is not None:
                            _rebase_pts(frame, _FINE_VIDEO_TB)
                            out_frames = _push_pull(video_graph, frame)

                        for frame in out_frames:
                            # Scale if needed
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
                                _monotonic_video_pts(frame)
                                for enc_pkt in out_video.encode(frame):
                                    _mux_packet(out, enc_pkt)

                elif in_audio and packet.stream == in_audio:
                    for frame in _decode_packet(packet):
                        if cancel_event and cancel_event.is_set():
                            break
                        if not out_audio:
                            continue
                        if need_afilter and audio_graph is None:
                            audio_graph = _build_audio_filter_graph(frame, volume_pct, speed)
                        out_frames = [frame]
                        if audio_graph is not None:
                            out_frames = _push_pull(audio_graph, frame)
                        for frame in out_frames:
                            _monotonic_audio_pts(frame)
                            for enc_pkt in out_audio.encode(frame):
                                _mux_packet(out, enc_pkt)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    progress = (
                        min(0.99, max(0.01, processed_pts / total_duration))
                        if total_duration > 0
                        else 0.5
                    )
                    on_progress(progress, f"Processing... {int(progress * 100)}%")

            # Drain filter graphs (EOF), then flush encoders — skipped when
            # cancelled: drained packets would be muxed into a file that is
            # about to be deleted, wasting seconds on large jobs.
            cancelled = bool(cancel_event is not None and cancel_event.is_set())
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
                    _monotonic_video_pts(frame)
                    for enc_pkt in out_video.encode(frame):
                        _mux_packet(out, enc_pkt)
            if not cancelled and audio_graph is not None and out_audio:
                for frame in _drain_graph(audio_graph):
                    _monotonic_audio_pts(frame)
                    for enc_pkt in out_audio.encode(frame):
                        _mux_packet(out, enc_pkt)
            if not cancelled and out_video:
                for enc_pkt in out_video.encode(None):
                    _mux_packet(out, enc_pkt)
            if not cancelled and out_audio:
                for enc_pkt in out_audio.encode(None):
                    _mux_packet(out, enc_pkt)

            if on_progress:
                on_progress(1.0, "Complete")

        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                except OSError as e:
                    logging.getLogger(__name__).warning("Failed to remove cancelled output: %s", e)
            raise InterruptedError("Transcoding was cancelled")

        return output_path

    @staticmethod
    @_with_native_logs
    def compress_to_target(
        input_path: str,
        output_path: str,
        target_size_mb: float,
        video_codec: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Compress video to stay under a specified target file size (e.g. WhatsApp 16MB).

        ``video_codec`` is the screen's wheel-measured pick (the Compress UI
        offers only verified encoders, mpeg4-first on LGPL wheels). None keeps
        the legacy auto choice. The resolver raises EngineCapabilityError for
        anything the wheel cannot encode — a refuse-before-Start at the UI.
        """
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
            if video_bitrate < 400000 and v_stream.width > 854:  # <400kbps -> 480p
                scale_w = 854
                scale_h = int(854 * (v_stream.height / v_stream.width))
            elif video_bitrate < 1000000:  # < 1Mbps -> 720p
                if v_stream.width > 1280:
                    scale_w = 1280
                    scale_h = int(1280 * (v_stream.height / v_stream.width))

        # Perform 1-pass constrained transcode with target bitrate
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w")
        except Exception:
            inp.close()
            raise

        try:
            if inp.metadata:
                out.metadata.update(inp.metadata)

            in_video = inp.streams.best("video")
            in_audio = inp.streams.best("audio")

            out_video = None
            if in_video:
                fps = int(in_video.average_rate or 30)
                chosen_vcodec = (
                    _resolve_video_codec(video_codec) if video_codec else _pick_video_encoder()
                )
                out_video = out.add_stream(chosen_vcodec, rate=fps)
                target_w = (scale_w or in_video.width or 640) // 2 * 2
                target_h = (scale_h or in_video.height or 360) // 2 * 2
                out_video.width = target_w
                out_video.height = target_h
                out_video.pix_fmt = _encoder_pix_fmt(chosen_vcodec)
                out_video.time_base = Fraction(1, fps)
                out_video.bit_rate = video_bitrate
                out_video.options = _supported_encoder_options(chosen_vcodec, {"preset": "fast"})

            out_audio = None
            if in_audio:
                out_audio = out.add_stream(_resolve_audio_codec("aac"), rate=in_audio.rate or 44100)
                out_audio.bit_rate = audio_bitrate
                out_audio.layout = "stereo"

            last_video_pts = -1
            last_audio_pts = -1

            def _monotonic_video_pts(frame: av.VideoFrame) -> None:
                nonlocal last_video_pts
                out_tb = out_video.time_base or Fraction(1, 30)
                candidate = None
                if frame.pts is not None and frame.time_base is not None:
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
                if frame.pts is not None and frame.time_base is not None:
                    candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
                if candidate is None or candidate <= last_audio_pts:
                    candidate = last_audio_pts + max(1, frame.samples)
                frame.pts = candidate
                frame.time_base = out_tb
                last_audio_pts = candidate

            last_report = 0.0
            processed_pts = 0.0
            mux_clamp = _MuxClamp()

            for packet in inp.demux([s for s in (in_video, in_audio) if s]):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break
                if packet.size == 0 or (packet.pts is None and packet.dts is None):
                    continue

                if in_video and packet.stream == in_video:
                    for frame in _decode_packet(packet):
                        if cancel_event and cancel_event.is_set():
                            break
                        if out_video:
                            enc_fmt = out_video.pix_fmt
                            if (
                                frame.width != out_video.width
                                or frame.height != out_video.height
                                or frame.format.name != enc_fmt
                            ):
                                frame = frame.reformat(
                                    width=out_video.width, height=out_video.height, format=enc_fmt
                                )
                            _monotonic_video_pts(frame)
                            for enc_pkt in out_video.encode(frame):
                                mux_clamp.mux(out, enc_pkt)
                        if frame.time:
                            processed_pts = frame.time

                elif in_audio and packet.stream == in_audio:
                    for frame in _decode_packet(packet):
                        if cancel_event and cancel_event.is_set():
                            break
                        if out_audio:
                            _monotonic_audio_pts(frame)
                            for enc_pkt in out_audio.encode(frame):
                                mux_clamp.mux(out, enc_pkt)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, processed_pts / duration))
                    on_progress(prog, f"Compressing... {int(prog * 100)}%")

            cancelled = bool(cancel_event is not None and cancel_event.is_set())
            if not cancelled and out_video:
                for enc_pkt in out_video.encode(None):
                    mux_clamp.mux(out, enc_pkt)
            if not cancelled and out_audio:
                for enc_pkt in out_audio.encode(None):
                    mux_clamp.mux(out, enc_pkt)

            if on_progress:
                on_progress(1.0, "Compressed")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            if Path(output_path).exists():
                try:
                    Path(output_path).unlink()
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
        video_codec: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Trim/cut a segment from media. Supports lossless stream copy or frame-accurate re-encode.

        ``video_codec`` is the screen's wheel-measured pick for the re-encode
        path (None = legacy auto). The resolver raises EngineCapabilityError
        for anything the wheel cannot encode.
        """
        if stream_copy:
            return EngineService._cut_stream_copy(
                input_path, output_path, start_seconds, end_seconds, on_progress, cancel_event
            )
        return EngineService._cut_reencode(
            input_path,
            output_path,
            start_seconds,
            end_seconds,
            video_codec,
            on_progress,
            cancel_event,
        )

    @staticmethod
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

    @staticmethod
    def _cut_stream_copy(
        input_path: str,
        output_path: str,
        start_s: float,
        end_s: float,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w")
        except Exception:
            inp.close()
            raise

        try:
            stream_map = {}
            for s in inp.streams:
                if s.type in ("video", "audio", "subtitle") and not _is_attached_picture(s):
                    out_s = out.add_stream_from_template(s, opaque=True)
                    stream_map[s] = out_s
            if inp.metadata:
                out.metadata.update(inp.metadata)
            try:
                out.set_chapters(inp.chapters())
            except Exception as exc:
                logger.debug("Chapter copy skipped: %s", exc)

            # Seek to start timestamp
            # Stream-copy cuts must begin on a keyframe — snap and tell the user.
            actual_start = start_s
            video_src = inp.streams.best("video")
            if video_src is not None:
                snapped = EngineService._snap_start_to_keyframe(video_src, start_s)
                if snapped < start_s - 1e-6:
                    actual_start = snapped
                    if on_progress:
                        on_progress(
                            0.0,
                            f"Start snapped {start_s:.2f}s → {actual_start:.2f}s for stream-copy cut",
                        )

            seek_target = int(actual_start * av.time_base)
            _safe_seek(inp, seek_target)

            duration = max(0.1, end_s - actual_start)
            last_report = 0.0
            start_pts_map: dict[int, int] = {}
            start_dts_map: dict[int, int] = {}
            mux_clamp = _MuxClamp()

            for packet in inp.demux(list(stream_map.keys())):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break
                if packet.size == 0:
                    continue
                ts = packet.pts if packet.pts is not None else packet.dts
                if ts is None:
                    continue

                pkt_time = float(ts * packet.stream.time_base)
                if pkt_time < actual_start:
                    continue
                if pkt_time > end_s:
                    break

                out_s = stream_map[packet.stream]
                # Template streams normally share the input time base; rescale
                # when they don't. The installed wheel exposes stream bases as
                # Fraction but rescale_ts requires AVRational.
                if out_s.time_base is not None and packet.time_base != out_s.time_base:
                    packet.rescale_ts(_av_rational(out_s.time_base))

                # Rebase PTS/DTS to start at 0, in the OUTPUT time base.
                # Separate bases per clock: with B-frame delay dts < pts, and
                # a single base drives the first dts negative after rebase.
                stream_idx = packet.stream.index
                if stream_idx not in start_pts_map:
                    start_pts_map[stream_idx] = packet.pts if packet.pts is not None else packet.dts
                if stream_idx not in start_dts_map:
                    start_dts_map[stream_idx] = packet.dts if packet.dts is not None else packet.pts

                if packet.pts is not None:
                    packet.pts = max(0, packet.pts - start_pts_map[stream_idx])
                if packet.dts is not None:
                    packet.dts = max(0, packet.dts - start_dts_map[stream_idx])
                # Post-seek packets can carry an inverted pts/dts pair (the
                # per-clock rebase above preserves each clock but not their
                # relationship — measured pts(1) < dts(1001) on a real mp4).
                # Presentation can never precede decode — carry PTS up to DTS
                # (a sub-frame nudge, same rule as the concat-copy path).
                if packet.dts is not None and packet.pts is not None and packet.dts > packet.pts:
                    packet.pts = packet.dts
                packet.stream = out_s
                mux_clamp.mux(out, packet)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, (pkt_time - actual_start) / duration))
                    on_progress(prog, f"Copying cut... {int(prog * 100)}%")

            if on_progress:
                on_progress(1.0, "Cut Complete")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Cut was cancelled")

        return output_path

    @staticmethod
    @_with_native_logs
    def _cut_reencode(
        input_path: str,
        output_path: str,
        start_s: float,
        end_s: float,
        video_codec: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w")
        except Exception:
            inp.close()
            raise

        try:
            in_video = inp.streams.best("video")
            in_audio = inp.streams.best("audio")

            out_video = None
            if in_video:
                fps = int(in_video.average_rate or 30)
                chosen_vcodec = (
                    _resolve_video_codec(video_codec) if video_codec else _pick_video_encoder()
                )
                out_video = out.add_stream(chosen_vcodec, rate=fps)
                out_video.width = in_video.width
                out_video.height = in_video.height
                out_video.pix_fmt = _encoder_pix_fmt(chosen_vcodec)
                out_video.time_base = Fraction(1, fps)
                out_video.options = _supported_encoder_options(
                    chosen_vcodec, {"crf": "20", "preset": "fast"}
                )

            out_audio = None
            if in_audio:
                out_audio = out.add_stream(_resolve_audio_codec("aac"), rate=in_audio.rate or 44100)
                out_audio.layout = "stereo"

            last_video_pts = -1
            last_audio_pts = -1

            def _monotonic_video_pts(frame: av.VideoFrame) -> None:
                nonlocal last_video_pts
                out_tb = out_video.time_base or Fraction(1, 30)
                candidate = None
                if frame.pts is not None and frame.time_base is not None:
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
                if frame.pts is not None and frame.time_base is not None:
                    candidate = round(Fraction(frame.pts) * frame.time_base / out_tb)
                if candidate is None or candidate <= last_audio_pts:
                    candidate = last_audio_pts + max(1, frame.samples)
                frame.pts = candidate
                frame.time_base = out_tb
                last_audio_pts = candidate

            # Seek close to start
            _safe_seek(inp, int(max(0.0, start_s - 2.0) * av.time_base))
            duration = max(0.1, end_s - start_s)
            last_report = 0.0
            mux_clamp = _MuxClamp()

            for packet in inp.demux([s for s in (in_video, in_audio) if s]):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break

                if in_video and packet.stream == in_video:
                    for frame in _decode_packet(packet):
                        if frame.time is None or frame.time < start_s:
                            continue
                        if frame.time > end_s:
                            break
                        if out_video:
                            _monotonic_video_pts(frame)
                            for enc_pkt in out_video.encode(frame):
                                mux_clamp.mux(out, enc_pkt)
                        now = time.monotonic()
                        if on_progress and (now - last_report >= 0.25):
                            last_report = now
                            prog = min(0.99, max(0.01, (frame.time - start_s) / duration))
                            on_progress(prog, f"Encoding cut... {int(prog * 100)}%")

                elif in_audio and packet.stream == in_audio:
                    for frame in _decode_packet(packet):
                        if frame.time is None or frame.time < start_s:
                            continue
                        if frame.time > end_s:
                            break
                        if out_audio:
                            _monotonic_audio_pts(frame)
                            for enc_pkt in out_audio.encode(frame):
                                mux_clamp.mux(out, enc_pkt)

            cancelled = bool(cancel_event is not None and cancel_event.is_set())
            if not cancelled and out_video:
                for enc_pkt in out_video.encode(None):
                    mux_clamp.mux(out, enc_pkt)
            if not cancelled and out_audio:
                for enc_pkt in out_audio.encode(None):
                    mux_clamp.mux(out, enc_pkt)

            if on_progress:
                on_progress(1.0, "Cut Complete")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Cut was cancelled")

        return output_path

    @staticmethod
    def _measure_loudnorm(input_path: str, target_lufs: float) -> dict[str, str]:
        """Pass 1 of two-pass loudnorm: measure integrated loudness as JSON stats.

        NOTE: ``av.filter.loudnorm.stats`` takes ownership of the format context it
        is given (it NULLs the Python wrapper's handle before the C pass), so this
        container is intentionally never closed — closing would double-free.
        """
        stats_container = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        audio_streams = stats_container.streams.audio
        if not audio_streams:
            stats_container.close()
            raise ValueError("No audio stream found in source media")
        try:
            raw = loudnorm_stats(f"i={target_lufs}", audio_streams[0])
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            # Handle already NULLed on entry to stats(); do not close.
            logger.warning("Loudnorm measurement failed, falling back to dynamic mode: %s", exc)
            return {}

    @staticmethod
    @_with_native_logs
    def extract_audio(
        input_path: str,
        output_path: str,
        format_name: str = "mp3",  # mp3, aac, m4a, flac, opus, ogg, wav
        bitrate_kbps: int = 192,
        target_lufs: float | None = None,
        channels: int | None = None,
        sample_rate: int | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Extract audio with optional LUFS mastering, channel mix, and soxr resampling."""
        # Do not create a partial output while the serial queue is paused.
        _pause_hook(cancel_event)
        # Requested format → friendly codec name. The resolver decides whether
        # this build can encode it; the old `else "mp3"` / `else "opus"`
        # branches pointed at encoders FFmpeg does not ship, which is exactly
        # what raised UnknownCodecError on the Android wheel.
        codec_map = {
            "mp3": "mp3",
            "aac": "aac",
            "m4a": "aac",
            "flac": "flac",
            "opus": "opus",
            "ogg": "vorbis",
            "wav": "pcm_s16le",
        }
        requested_format = format_name.lower()
        if requested_format not in codec_map:
            raise EngineCapabilityError(
                f"Unknown output format {format_name!r}. Supported: " + ", ".join(sorted(codec_map))
            )
        chosen_codec = _resolve_audio_codec(codec_map[requested_format])

        # Two-pass loudnorm needs a full measurement pass before encoding starts.
        measured = (
            EngineService._measure_loudnorm(input_path, float(target_lufs))
            if target_lufs is not None
            else None
        )

        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w")
        except Exception:
            inp.close()
            raise

        try:
            in_audio = inp.streams.best("audio")
            if not in_audio:
                raise ValueError("No audio stream found in source media")

            # chosen_codec is resolved (and verified) before the output file is
            # opened, so an unsupported format fails with no partial file.
            out_rate = int(sample_rate) if sample_rate else (in_audio.rate or 44100)
            if channels in (1, 2):
                target_layout = "mono" if channels == 1 else "stereo"
            else:
                n_ch = min(2, in_audio.channels or 2)
                target_layout = "stereo" if n_ch == 2 else "mono"

            # Opus is 48k-native (44100 fails avcodec_open2) — the resampler
            # below already bridges any source rate. Vorbis strictness rides
            # in _encoder_open_kwargs (experimental encoder on this build).
            if chosen_codec in ("opus", "libopus"):
                out_rate = 48000
            out_audio = out.add_stream(
                chosen_codec, rate=out_rate, **_encoder_open_kwargs(chosen_codec)
            )
            if chosen_codec != "pcm_s16le":
                out_audio.bit_rate = bitrate_kbps * 1000
            out_audio.layout = target_layout

            # Open the encoder before the first packet so fixed-frame codecs
            # (AAC/MP3/FLAC) expose their real frame_size. AudioFifo then keeps
            # partial decoder frames instead of relying on lucky buffer sizes.
            try:
                out.start_encoding()
            except Exception as exc:
                logger.debug("Audio encoder pre-open deferred: %s", exc)
            audio_fifo = av.AudioFifo() if out_audio.frame_size > 0 else None

            # soxr-quality rate/layout conversion when this FFmpeg build has
            # libsoxr; otherwise _emit falls back to plain swr on first use.
            # The encoder's own resampler then passes through (it only ever
            # converts sample FORMAT).
            resampler = None
            src_rate = in_audio.rate or out_rate
            src_layout = getattr(in_audio.layout, "name", None)
            if src_rate != out_rate or (src_layout and src_layout != target_layout):
                resampler = av.AudioResampler(
                    layout=target_layout,
                    rate=out_rate,
                    options={"resampler": "soxr", "precision": "28"},
                )

            loud_graph: av.filter.Graph | None = None
            loud_args: str | None = None
            if target_lufs is not None:
                keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
                bad = {"inf", "-inf", "nan", ""} if measured else set()
                if measured and all(
                    k in measured and str(measured[k]).lower() not in bad for k in keys
                ):
                    loud_args = (
                        f"i={target_lufs}"
                        f":measured_I={measured['input_i']}"
                        f":measured_TP={measured['input_tp']}"
                        f":measured_LRA={measured['input_lra']}"
                        f":measured_thresh={measured['input_thresh']}"
                        f":offset={measured['target_offset']}"
                        ":linear=true"
                    )
                else:
                    loud_args = f"i={target_lufs}"  # dynamic single-pass fallback

            total_dur = float(inp.duration or 0) / float(av.time_base) if inp.duration else 1.0
            last_report = 0.0
            cur_pts = 0.0
            mux_clamp = _MuxClamp()

            def _encode(f: av.AudioFrame) -> None:
                nonlocal audio_fifo
                f.pts = None  # encoder assigns sequential sample positions
                if audio_fifo is not None:
                    try:
                        audio_fifo.write(f)
                        while audio_fifo.samples >= out_audio.frame_size:
                            full = audio_fifo.read(out_audio.frame_size, partial=False)
                            if full is None:
                                break
                            for enc_pkt in out_audio.encode(full):
                                mux_clamp.mux(out, enc_pkt)
                        return
                    except (TypeError, ValueError, av.error.FFmpegError) as exc:
                        # A decoder format that the FIFO cannot represent is
                        # still valid for the encoder's own resampler; fall
                        # back rather than dropping the take. FFmpegError is
                        # the actual mismatch error — without it this branch
                        # never triggered and the job crashed instead.
                        logger.debug("AudioFifo fallback to encoder resampler: %s", exc)
                        audio_fifo = None
                for enc_pkt in out_audio.encode(f):
                    mux_clamp.mux(out, enc_pkt)

            def _emit(frames_list: list) -> None:
                nonlocal resampler
                for f in frames_list:
                    if resampler is not None:
                        try:
                            resampled = resampler.resample(f)
                        except FFmpegError as exc:
                            logger.warning(
                                "soxr resampler unavailable (%s); falling back to swr", exc
                            )
                            resampler = av.AudioResampler(layout=target_layout, rate=out_rate)
                            resampled = resampler.resample(f)
                        for rf in resampled:
                            _encode(rf)
                    else:
                        _encode(f)

            for packet in inp.demux([in_audio]):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break
                for frame in _decode_packet(packet):
                    if cancel_event and cancel_event.is_set():
                        break
                    if frame.time:
                        cur_pts = frame.time
                    if loud_args is not None and loud_graph is None:
                        lg = av.filter.Graph()
                        ab_kwargs: dict = {
                            "sample_rate": frame.sample_rate,
                            "format": frame.format.name,
                            "layout": frame.layout.name,
                        }
                        if frame.time_base is not None:
                            ab_kwargs["time_base"] = frame.time_base
                        src = lg.add_abuffer(**ab_kwargs)
                        ln = lg.add("loudnorm", loud_args)
                        sink = lg.add("abuffersink")
                        lg.link_nodes(src, ln, sink)
                        lg.configure()
                        loud_graph = lg
                    if loud_graph is not None:
                        _emit(_push_pull(loud_graph, frame))
                    else:
                        _emit([frame])

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, cur_pts / total_dur))
                    on_progress(prog, f"Extracting Audio... {int(prog * 100)}%")

            # Flush: loudnorm graph → soxr resampler → encoder
            if loud_graph is not None:
                for f in _drain_graph(loud_graph):
                    _emit([f])
            if resampler is not None:
                for rf in resampler.resample(None):
                    _encode(rf)
            if audio_fifo is not None:
                tail = audio_fifo.read(partial=True)
                if tail is not None:
                    for enc_pkt in out_audio.encode(tail):
                        mux_clamp.mux(out, enc_pkt)
            for enc_pkt in out_audio.encode(None):
                mux_clamp.mux(out, enc_pkt)

            if on_progress:
                on_progress(1.0, "Audio Extracted")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Audio extraction cancelled")

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
        """Extract evenly-spaced frames in a single decode pass into an image directory."""
        info = EngineService.probe(input_path)
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

    @staticmethod
    @_with_native_logs
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
        """Generate a palette-optimized animated GIF from a video segment.

        Uses a single split graph (fps → scale → split → palettegen | paletteuse)
        so every frame is dithered against the segment-wide palette; falls back to
        a direct rgb8 encode if the palette filters are unavailable on this build.
        """
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w", format="gif")
        except Exception:
            inp.close()
            raise

        try:
            in_video = inp.streams.best("video")
            if not in_video:
                raise ValueError("No video stream found")

            out_fps = max(1, min(fps, 30))
            out_video = out.add_stream(_resolve_video_codec("gif"), rate=out_fps)
            out_w = int(width)
            out_h = max(1, int(out_w * ((in_video.height or 1) / (in_video.width or 1))))
            out_video.width = out_w
            out_video.height = out_h
            out_video.pix_fmt = "rgb8"
            out_video.time_base = Fraction(1, out_fps)

            graph: av.filter.Graph | None = None
            palette_mode = True  # until the first frame proves otherwise
            pushed = 0
            last_report = 0.0
            mux_clamp = _MuxClamp()

            def _direct_encode(frame: av.VideoFrame) -> None:
                rf = frame.reformat(width=out_w, height=out_h, format="rgb8")
                rf.pts = None
                for enc_pkt in out_video.encode(rf):
                    mux_clamp.mux(out, enc_pkt)

            _safe_seek(inp, int(start_s * av.time_base))
            end_s = start_s + duration_s

            for packet in inp.demux([in_video]):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break
                segment_done = False
                for frame in _decode_packet(packet):
                    if frame.time is None or frame.time < start_s:
                        continue
                    if frame.time > end_s:
                        segment_done = True
                        break

                    if palette_mode and graph is None:
                        try:
                            g = av.filter.Graph()
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
                            graph = g
                        except Exception as exc:
                            logger.warning(
                                "Palette GIF graph unavailable (%s); "
                                "falling back to direct GIF encode",
                                exc,
                            )
                            palette_mode = False

                    if graph is not None:
                        graph.push(frame)
                        pushed += 1
                    else:
                        _direct_encode(frame)
                        pushed += 1

                    now = time.monotonic()
                    if on_progress and (now - last_report >= 0.25):
                        last_report = now
                        prog = min(0.85, 0.85 * (frame.time - start_s) / max(0.1, duration_s))
                        on_progress(prog, f"Creating GIF... {int(prog * 100)}%")
                if segment_done:
                    break

            if cancel_event and cancel_event.is_set():
                raise InterruptedError("cancelled")

            if graph is not None:
                for drained, rf in enumerate(_drain_graph(graph), start=1):
                    if rf.width != out_w or rf.height != out_h or rf.format.name != "rgb8":
                        rf = rf.reformat(width=out_w, height=out_h, format="rgb8")
                    rf.pts = None
                    for enc_pkt in out_video.encode(rf):
                        mux_clamp.mux(out, enc_pkt)
                    if on_progress:
                        frac = min(1.0, drained / max(1, pushed))
                        on_progress(
                            min(0.99, 0.85 + 0.14 * frac),
                            f"Creating GIF... {int(min(0.99, 0.85 + 0.14 * frac) * 100)}%",
                        )

            if not (cancel_event and cancel_event.is_set()):
                for enc_pkt in out_video.encode(None):
                    mux_clamp.mux(out, enc_pkt)

            if on_progress:
                on_progress(1.0, "GIF Created")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("GIF creation cancelled")

        return output_path

    @staticmethod
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
                cues.append(
                    SubCue(start_s=start_s, end_s=start_s + dur_s, text="\n".join(text_parts))
                )

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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
        drop = set(drop_indices or [])
        inp = av.open(input_path, "r", timeout=_INPUT_TIMEOUT, options=_INPUT_OPTIONS)
        try:
            out = av.open(output_path, "w", format="matroska")
        except Exception:
            inp.close()
            raise
        try:
            if inp.metadata:
                out.metadata.update(inp.metadata)
            stream_map = {}
            kept_attachments = False
            for attachment in inp.streams.attachments:
                try:
                    out.add_attachment(
                        attachment.name,
                        attachment.mimetype,
                        attachment.data,
                    )
                    kept_attachments = True
                except Exception as exc:
                    logger.debug("Attachment copy skipped (%s): %s", attachment.name, exc)
            for s in inp.streams:
                if s.index in drop or s.type not in ("video", "audio", "subtitle"):
                    continue
                if _is_attached_picture(s):
                    continue
                try:
                    out_s = out.add_stream_from_template(s, opaque=True)
                except Exception as exc:
                    logger.debug("Data/stream copy skipped for %s: %s", s.index, exc)
                    continue
                # add_stream_from_template is a NO-OP for metadata/disposition
                # on this build (verified: both come across empty) — copy them
                # explicitly before the header is written. Disposition is an
                # IntFlag, so int() carries the exact bit set.
                out_s.metadata.update(s.metadata)
                try:
                    out_s.disposition = int(s.disposition)
                except Exception as exc:
                    logger.debug("Disposition copy skipped: %s", exc)
                stream_map[s] = out_s
            if not stream_map and not kept_attachments:
                raise ValueError("Nothing to keep — every stream was excluded")

            if rotation in (90, 180, 270):
                # Display-matrix rotation: players honor it, pixels untouched.
                for s, out_s in stream_map.items():
                    if s.type == "video":
                        try:
                            out_s.set_display_rotation(rotation)
                        except Exception as exc:
                            logger.warning("Rotation write skipped: %s", exc)

            if chapters is not None:
                try:
                    out.set_chapters(
                        [
                            {
                                "id": i,
                                "start": int(c.get("start_s", 0) * 1000),
                                "end": int(c.get("end_s", 0) * 1000),
                                "time_base": Fraction(1, 1000),
                                "metadata": {"title": str(c.get("title") or f"Chapter {i + 1}")},
                            }
                            for i, c in enumerate(chapters)
                        ]
                    )
                except Exception as exc:
                    logger.warning("Chapter write skipped: %s", exc)
            else:
                try:
                    out.set_chapters(inp.chapters())
                except Exception as exc:
                    logger.warning("Chapter copy skipped: %s", exc)

            total_s = (float(inp.duration or 0) / float(av.time_base)) if inp.duration else 0.0
            last_report = 0.0
            mux_clamp = _MuxClamp()

            for packet in inp.demux(list(stream_map)):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    break
                if packet.size == 0 or (packet.pts is None and packet.dts is None):
                    continue
                ts = packet.pts if packet.pts is not None else packet.dts
                pkt_time = float(ts * packet.stream.time_base)
                packet.stream = stream_map[packet.stream]
                mux_clamp.mux(out, packet)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    prog = min(0.99, max(0.01, pkt_time / total_s)) if total_s > 0 else 0.5
                    on_progress(prog, f"Copying streams... {int(prog * 100)}%")

            if on_progress:
                on_progress(1.0, "Streams copied")
        finally:
            _close_container(inp)
            _close_container(out)

        if cancel_event and cancel_event.is_set():
            _discard_cancelled(output_path)
            raise InterruptedError("Stream copy cancelled")

        return output_path

    @staticmethod
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

        infos = [EngineService.probe(p) for p in paths]

        if transition == "crossfade":
            gate_reason = EngineService._crossfade_gate(infos, fade_s)
            if gate_reason is None:
                return EngineService._concat_crossfade(
                    paths,
                    infos,
                    output_path,
                    container_format,
                    fade_s,
                    video_codec,
                    on_progress,
                    cancel_event,
                )
            logger.warning(
                "Crossfade unavailable (%s) — falling back to lossless join", gate_reason
            )
        elif transition != "cut":
            raise ValueError(f"Unsupported transition: {transition}")

        if EngineService._concat_copyable(infos):
            return EngineService._concat_stream_copy(
                paths, output_path, container_format, on_progress, cancel_event
            )
        return EngineService._concat_reencode(
            paths, infos, output_path, container_format, video_codec, on_progress, cancel_event
        )

    @staticmethod
    def _crossfade_gate(infos: list[MediaInfo], fade_s: float) -> str | None:
        """None when crossfade can run; otherwise a human-readable reason.

        Gates (all proven necessary by the window empirics): alphamerge +
        overlay (+ acrossfade when audio present) compiled in; every clip has
        video, matching fps, ≤1080p, and room for both windows; audio layouts
        match; fade snaps cleanly to the frame grid.
        """
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

    @staticmethod
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

    @staticmethod
    def _concat_stream_copy(
        paths: list[str],
        output_path: str,
        container_format: str | None,
        on_progress: Callable[[float, str], None] | None,
        cancel_event: Event | None,
    ) -> str:
        """Lossless join: packets are rescaled onto the first clip's timeline
        and shifted so each file starts exactly one tick after the previous
        file's last packet (no duration-rounding gaps or overlaps)."""
        out = av.open(output_path, "w", format=container_format)
        cancelled = False
        try:
            out_by_pos: list = []
            tb_by_pos: list = []
            last_pts: dict[int, int] = {}
            last_dts: dict[int, int] = {}

            for fi, path in enumerate(paths):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                inp = av.open(path, "r", timeout=_INPUT_TIMEOUT)
                try:
                    src_streams = [
                        s
                        for s in inp.streams
                        if s.type in ("video", "audio", "subtitle") and not _is_attached_picture(s)
                    ]
                    if fi == 0:
                        for s in src_streams:
                            out_by_pos.append(out.add_stream_from_template(s, opaque=True))
                            tb_by_pos.append(_av_rational(s.time_base or Fraction(1, 1000)))

                    # Boundary constant per stream: land one tick past the previous
                    # file's final pts (computed on the FIRST packet of this file).
                    shift: dict[int, int] = {}
                    first_native: dict[int, int] = {}

                    for packet in inp.demux(src_streams):
                        if cancel_event and cancel_event.is_set():
                            cancelled = True
                            break
                        if packet.size == 0 or (packet.pts is None and packet.dts is None):
                            continue
                        pos = src_streams.index(packet.stream)
                        target_tb = tb_by_pos[pos]
                        if packet.time_base != target_tb:
                            packet.rescale_ts(target_tb)

                        key = pos
                        native_pts = packet.pts if packet.pts is not None else 0
                        native_dts = packet.dts if packet.dts is not None else native_pts
                        if key not in first_native:
                            first_native[key] = native_pts
                            prev_pts = last_pts.get(key)
                            prev_dts = last_dts.get(key)
                            shift[key] = max(
                                prev_pts + 1 - native_pts if prev_pts is not None else 0,
                                prev_dts + 1 - native_dts if prev_dts is not None else 0,
                            )
                        delta = shift.get(key, 0)
                        if packet.pts is not None:
                            packet.pts = packet.pts + delta
                        if packet.dts is not None:
                            packet.dts = packet.dts + delta
                        if packet.pts is None:
                            packet.pts = native_pts + delta
                        if packet.dts is None:
                            packet.dts = native_dts + delta
                        previous_dts = last_dts.get(pos)
                        if previous_dts is not None and packet.dts <= previous_dts:
                            packet.dts = previous_dts + 1
                        previous_pts = last_pts.get(pos)
                        if previous_pts is not None and packet.pts <= previous_pts:
                            packet.pts = previous_pts + 1
                        # B-frame delay vs the DTS floor: a pushed-up DTS can
                        # overtake this packet's PTS (muxer: "pts < dts").
                        # Presentation can never precede decode — carry PTS up.
                        if (
                            packet.dts is not None
                            and packet.pts is not None
                            and packet.dts > packet.pts
                        ):
                            packet.pts = packet.dts
                        last_pts[pos] = packet.pts
                        last_dts[pos] = packet.dts

                        packet.stream = out_by_pos[pos]
                        # Manually clamped above (shift + last_pts/last_dts
                        # floors) — no _MuxClamp needed on this path.
                        out.mux(packet)

                    if on_progress:
                        on_progress(
                            min(0.95, (fi + 1) / len(paths) * 0.95),
                            f"Joining {Path(path).name}… ({fi + 1}/{len(paths)})",
                        )
                finally:
                    _close_container(inp)

            if not cancelled and on_progress:
                on_progress(1.0, f"Joined {len(paths)} clips")
        finally:
            _close_container(out)

        if cancelled or (cancel_event and cancel_event.is_set()):
            _discard_cancelled(output_path)
            raise InterruptedError("Join cancelled")
        return output_path

    @staticmethod
    @_with_native_logs
    def _concat_reencode(
        paths: list[str],
        infos: list[MediaInfo],
        output_path: str,
        container_format: str | None,
        video_codec: str | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Uniform re-encode join: one encoder pair for the whole chain;
        clips with mismatched shapes are scaled to the first clip's size.
        Sequential pts=None keeps the timeline continuous across boundaries."""
        first = infos[0]
        fv = first.video_stream
        fa = first.audio_stream
        if fv is None:
            raise ValueError("The first file has no video stream to join")

        out = av.open(output_path, "w", format=container_format)
        cancelled = False
        try:
            out_fps = max(1, min(int(fv.fps or 30), 60))
            out_w = max(2, (fv.width or 640 // 2 * 2) // 2 * 2)
            out_h = max(2, (fv.height or 360 // 2 * 2) // 2 * 2)
            out_video = None
            chosen_v = _resolve_video_codec(video_codec) if video_codec else _pick_video_encoder()
            out_video = out.add_stream(chosen_v, rate=out_fps)
            out_video.width = out_w
            out_video.height = out_h
            out_video.pix_fmt = _encoder_pix_fmt(chosen_v)
            out_video.time_base = Fraction(1, out_fps)
            out_video.options = _supported_encoder_options(
                chosen_v, {"crf": "23", "preset": "fast"}
            )

            out_audio = None
            if fa is not None:
                out_audio = out.add_stream(
                    _resolve_audio_codec("aac"), rate=fa.sample_rate or 44100
                )
                out_audio.layout = "stereo" if (fa.channels or 2) >= 2 else "mono"

            mux_clamp = _MuxClamp()

            for fi, path in enumerate(paths):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                inp = av.open(path, "r", timeout=_INPUT_TIMEOUT)
                try:
                    in_video = inp.streams.best("video")
                    in_audio = inp.streams.best("audio")
                    streams = [s for s in (in_video, in_audio) if s]

                    for packet in inp.demux(streams):
                        if cancel_event and cancel_event.is_set():
                            cancelled = True
                            break
                        _pause_hook(cancel_event)
                        if in_video and packet.stream == in_video:
                            for frame in _decode_packet(packet):
                                if out_video is None:
                                    break
                                if (
                                    frame.width != out_video.width
                                    or frame.height != out_video.height
                                    or frame.format.name != out_video.pix_fmt
                                ):
                                    frame = frame.reformat(
                                        width=out_video.width,
                                        height=out_video.height,
                                        format=out_video.pix_fmt,
                                    )
                                frame.pts = None  # sequential across the whole chain
                                for enc_pkt in out_video.encode(frame):
                                    mux_clamp.mux(out, enc_pkt)
                        elif in_audio and packet.stream == in_audio and out_audio is not None:
                            for frame in _decode_packet(packet):
                                frame.pts = None
                                for enc_pkt in out_audio.encode(frame):
                                    mux_clamp.mux(out, enc_pkt)

                    if on_progress:
                        on_progress(
                            min(0.95, (fi + 1) / len(paths) * 0.95),
                            f"Joining {Path(path).name}… ({fi + 1}/{len(paths)})",
                        )
                finally:
                    _close_container(inp)

            if not cancelled:
                if out_video:
                    for enc_pkt in out_video.encode(None):
                        mux_clamp.mux(out, enc_pkt)
                if out_audio:
                    for enc_pkt in out_audio.encode(None):
                        mux_clamp.mux(out, enc_pkt)
                if on_progress:
                    on_progress(1.0, f"Joined {len(paths)} clips")
        finally:
            _close_container(out)

        if cancelled or (cancel_event and cancel_event.is_set()):
            _discard_cancelled(output_path)
            raise InterruptedError("Join cancelled")
        return output_path

    @staticmethod
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
                    EngineService._xfade_window(
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
                        EngineService._acrossfade_window(
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _parse_hls_playlist(text: str, base: str) -> tuple[list[str], bool, str | None]:
        """Split an HLS playlist into segment URLs.

        Returns ``(segments, is_master, key_error)``.  A master variant
        playlist (``#EXT-X-STREAM-INF``) resolves to the highest-BANDWIDTH
        media playlist URL as the single "segment" for the caller to recurse
        into; ``key_error`` names the cause when ``#EXT-X-KEY`` (encrypted
        segments) is present, which this offline-concat path cannot decrypt.
        """
        lines = [ln.strip() for ln in text.splitlines()]
        key_error = None
        for ln in lines:
            if ln.startswith("#EXT-X-KEY"):
                key_error = f"encrypted segments are not supported ({ln[:80]})"
                break
        is_master = any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines)
        variants: list[tuple[int, str]] = []
        segs: list[str] = []
        pending_bw = 0
        for ln in lines:
            if ln.startswith("#EXT-X-STREAM-INF"):
                bw = 0
                for part in ln.split(":", 1)[1].split(","):
                    if part.strip().upper().startswith("BANDWIDTH="):
                        try:
                            bw = int(part.split("=", 1)[1])
                        except ValueError:
                            bw = 0
                pending_bw = bw
                continue
            if not ln or ln.startswith("#"):
                continue
            url = urljoin(base, ln)
            if is_master:
                variants.append((pending_bw, url))
                pending_bw = 0
            else:
                segs.append(url)
        if variants:
            variants.sort(key=lambda v: v[0], reverse=True)
            return [variants[0][1]], True, key_error
        return segs, False, key_error

    # Network timeouts: 4-phase like the update service (connect/read/write/
    # pool) instead of the old bare (connect, read) tuple that left write/pool
    # unbounded. Import httpx lazily is unnecessary — module already imports it.
    _HLS_TIMEOUT = (10.0, 30.0, 30.0, 10.0)

    # Per-segment retry: one transient ReadError must not abort a playlist.
    _HLS_SEGMENT_RETRIES = 3

    @staticmethod
    def _hls_fetch_text(client, url: str) -> str:
        """GET a playlist URL, raising a loud error on failure."""
        resp = client.get(url, timeout=EngineService._HLS_TIMEOUT)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _hls_download_segment(client, seg: str, chunk_size: int, on_cancel) -> bytes:
        """Download one media segment, rejecting HTML/text error pages.

        Transient network errors retry with backoff (bounded); error pages
        and HTTP statuses fail immediately — retrying a 403 is pointless.
        """
        import time as _time

        last_err: Exception | None = None
        for attempt in range(EngineService._HLS_SEGMENT_RETRIES):
            try:
                return EngineService._hls_download_segment_once(client, seg, chunk_size, on_cancel)
            except ValueError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_err = exc
                logger.warning(
                    "Segment retry %d/%d for %s: %s",
                    attempt + 1,
                    EngineService._HLS_SEGMENT_RETRIES,
                    seg[:80],
                    exc,
                )
                on_cancel()
                _time.sleep(min(2.0**attempt, 4.0))
        raise ValueError(f"Segment failed after retries ({seg[:80]}…): {last_err}")

    @staticmethod
    def _hls_download_segment_once(client, seg: str, chunk_size: int, on_cancel) -> bytes:
        """Single attempt of a segment download (see _hls_download_segment)."""
        parts: list[bytes] = []
        with client.stream("GET", seg, timeout=EngineService._HLS_TIMEOUT) as resp:
            resp.raise_for_status()
            first = True
            for chunk in resp.iter_bytes(chunk_size=chunk_size):
                on_cancel()
                if not chunk:
                    continue
                if first:
                    first = False
                    # A segment that answers HTML/text is an error page, not
                    # media — fail loud with the cause instead of a blind EOF
                    # at av.open time.
                    head = chunk[:512].lstrip().lower()
                    if (
                        head.startswith((b"<!doctype", b"<html", b"<head", b"{", b"<"))
                        and b"#extm3u" not in chunk[:512].lower()
                    ):
                        raise ValueError(
                            f"Segment is not media ({seg[:80]}…) — the server returned an error page"
                        )
                parts.append(chunk)
        return b"".join(parts)

    @staticmethod
    def _hls_cap_bytes(max_hls_download_mb: float | None) -> int | None:
        """Cap in bytes, or None when the caller overrode it for this download."""
        if max_hls_download_mb is None:
            return None
        try:
            cap = float(max_hls_download_mb)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(cap) or cap <= 0:
            return None
        return int(cap * 1024 * 1024)

    @staticmethod
    def _check_hls_cap(total: int, cap: int | None, url: str) -> None:
        if cap is not None and total > cap:
            raise ValueError(
                f"Stream is ~{total // (1024 * 1024)} MB but the download cap is "
                f"{cap // (1024 * 1024)} MB — raise Settings → max HLS download, "
                "or tick 'Download anyway' on this stream to override once"
            )

    @staticmethod
    def estimate_hls_segments(client, url: str) -> tuple[list[str], int | None]:
        """Resolve the media playlist and HEAD each segment for its size.

        Returns (segment URLs, total bytes or None when any server omits
        Content-Length). Never downloads media — the streams screen calls this
        for the preflight line before the user commits.
        """
        playlist = EngineService._hls_fetch_text(client, url)
        base = urljoin(url, ".")
        segments, is_master, key_error = EngineService._parse_hls_playlist(playlist, base)
        if key_error is not None:
            raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
        if is_master:
            media_url = segments[0]
            playlist = EngineService._hls_fetch_text(client, media_url)
            base = urljoin(media_url, ".")
            segments, _, key_error = EngineService._parse_hls_playlist(playlist, base)
            if key_error is not None:
                raise ValueError(
                    f"This stream is encrypted and can't be recorded offline: {key_error}"
                )
        if not segments:
            raise ValueError("HLS playlist contained no media segments")
        total: int | None = 0
        for seg in segments:
            try:
                head = client.head(seg, timeout=EngineService._HLS_TIMEOUT)
                head.raise_for_status()
                length = head.headers.get("content-length")
                if length is None:
                    return segments, None
                assert isinstance(total, int)
                total += int(length)
            except Exception:
                return segments, None
        return segments, total

    @staticmethod
    def _download_hls_segments(
        client,
        url: str,
        on_cancel,
        max_hls_download_mb: float | None = None,
    ) -> list[tuple[str, bytes]]:
        """Resolve master→media playlist and download every segment.

        Raises a loud, specific ValueError for encrypted streams, empty
        playlists, error-page segments, payloads too small to be media, or
        totals past the download cap (servers that lie about Content-Length
        are caught by the running total mid-download).
        """
        cap = EngineService._hls_cap_bytes(max_hls_download_mb)
        playlist = EngineService._hls_fetch_text(client, url)
        base = urljoin(url, ".")
        segments, is_master, key_error = EngineService._parse_hls_playlist(playlist, base)
        if key_error is not None:
            raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
        if is_master:
            # The master holds variant URLs, not media bytes — writing those
            # produced the EOF-on-.dat failure. Recurse into the top variant.
            media_url = segments[0]
            logger.info("HLS master playlist — using %s", media_url)
            playlist = EngineService._hls_fetch_text(client, media_url)
            base = urljoin(media_url, ".")
            segments, _, key_error = EngineService._parse_hls_playlist(playlist, base)
            if key_error is not None:
                raise ValueError(
                    f"This stream is encrypted and can't be recorded offline: {key_error}"
                )
        if not segments:
            raise ValueError("HLS playlist contained no media segments")
        out: list[tuple[str, bytes]] = []
        running = 0
        for seg in segments:
            on_cancel()
            data = EngineService._hls_download_segment(client, seg, 256 * 1024, on_cancel)
            running += len(data)
            EngineService._check_hls_cap(running, cap, seg)
            out.append((seg, data))
        total = sum(len(b) for _, b in out)
        if total < 32 * 1024:
            raise ValueError(
                f"Stream produced too little data to be media ({total} bytes) — "
                "check the URL and your network"
            )
        return out

    @staticmethod
    def _open_https_via_httpx(
        url: str,
        cancel_event: Event | None = None,
        max_hls_download_mb: float | None = None,
    ):
        """Download an HTTPS (optionally HLS) stream into a local temp file.

        The Android FFmpeg build has no TLS handler, so ``av.open`` cannot open
        HTTPS directly. Fetch the bytes with ``httpx`` instead, using the app's
        own network stack. HLS playlists are expanded segment-by-segment so the
        resulting file is a plain container PyAV can demux.

        Plain files stream in ONE GET (the old code sniffed 512B, discarded the
        response, and GET again from byte 0). HLS totals are capped at
        ``max_hls_download_mb`` (None = the caller overrode the cap for this
        download).

        Returns ``(container, cleanup_path)`` — PyAV containers are Cython
        objects without a ``__dict__``, so the caller cannot be handed the
        backing path as an attribute.
        """
        from uuid import uuid4

        temp_path = get_temp_dir() / f"https_dl_{uuid4().hex}.dat"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        total_written = 0
        chunk_size = 256 * 1024
        cap = EngineService._hls_cap_bytes(max_hls_download_mb)

        def _raise_if_cancelled() -> None:
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Stream download cancelled")

        try:
            with httpx.Client(follow_redirects=True) as client:
                with client.stream("GET", url, timeout=EngineService._HLS_TIMEOUT) as first:
                    first.raise_for_status()
                    head = next(first.iter_bytes(chunk_size=512), b"")
                    is_hls = ".m3u8" in url.lower() or head.lstrip().startswith(b"#EXTM3U")
                    probe_len = getattr(first, "headers", {}).get("content-length")
                    if not is_hls and probe_len is not None:
                        EngineService._check_hls_cap(int(probe_len), cap, url)
                    if is_hls:
                        # HLS goes segment-by-segment through the playlist
                        # helpers; this sniff response is discarded.
                        pass
                    else:
                        # Plain file: consume THIS response inline (single GET).
                        # The 512B peek is prepended; servers that lie about
                        # Content-Length are caught by the running total.
                        with temp_path.open("wb") as fh:
                            if head:
                                fh.write(head)
                                total_written += len(head)
                            for chunk in first.iter_bytes(chunk_size=chunk_size):
                                _raise_if_cancelled()
                                if chunk:
                                    total_written += len(chunk)
                                    EngineService._check_hls_cap(total_written, cap, url)
                                    fh.write(chunk)

                if is_hls:
                    with temp_path.open("wb") as fh:
                        segments = EngineService._download_hls_segments(
                            client, url, _raise_if_cancelled, max_hls_download_mb
                        )
                        for _seg, seg_bytes in segments:
                            _raise_if_cancelled()
                            fh.write(seg_bytes)
                            total_written += len(seg_bytes)
                        logger.info("HLS playlist: %d segment(s) to download", len(segments))

            if total_written == 0:
                # Raising inside the try is what triggers the unlink below.
                raise ValueError(  # noqa: TRY301
                    "Stream produced no data — check the URL and your network"
                )

            container = av.open(str(temp_path), "r", timeout=_INPUT_TIMEOUT)
            return container, str(temp_path)
        except BaseException:
            # Any failure (HTTP error, cancel, FFmpeg reject) must not leave a
            # partial multi-GB download sitting in the temp tier.
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _open_network_input(
        input_url: str,
        cancel_event: Event | None = None,
        max_hls_download_mb: float | None = None,
    ):
        """Return ``(container, cleanup_path)`` for a URL.

        HTTP and other protocols PyAV handles natively go straight to
        ``av.open`` (no cleanup path). HTTPS goes through
        :meth:`_open_https_via_httpx` because the Android FFmpeg build ships
        without TLS, and its temp file must be removed after the mux closes.
        ``max_hls_download_mb=None`` overrides the cap for this download.
        """
        if input_url.lower().startswith("https://"):
            return EngineService._open_https_via_httpx(input_url, cancel_event, max_hls_download_mb)
        return av.open(input_url, "r", timeout=(10.0, 30.0)), None

    @staticmethod
    def record(
        input_url: str,
        output_path: str,
        container_format: str | None = None,
        duration_s: float | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
        max_hls_download_mb: float | None = 2048,
    ) -> str:
        """Record an HTTP/HTTPS/HLS/DASH stream to a local file.

        Cancellation semantics differ from every other op: pressing Stop KEEPS
        the recording (returns normally instead of raising InterruptedError) —
        a stopped stream is a successful partial capture. ``duration_s`` acts
        as an automatic clean stop.

        ``max_hls_download_mb`` caps one HTTPS/HLS download (default 2 GB —
        the app setting; None = the caller overrode it for this download).

        Flet Mobile Forge's Android FFmpeg build has NO TLS protocol handler,
        so ``av.open('https://…')`` raises ProtocolNotFoundError on the phone
        even though the same call works on desktop. HTTPS is therefore fetched
        through ``httpx`` (which uses the app's own network stack) and handed
        to PyAV as a local file — the exact approach the Mobile Forge recipe
        documentation recommends.
        """
        if not input_url or "://" not in input_url:
            raise ValueError("That doesn't look like a stream URL (need scheme://…)")
        cleanup_path: str | None = None
        try:
            inp, cleanup_path = EngineService._open_network_input(
                input_url, cancel_event, max_hls_download_mb
            )
        except av.error.ProtocolNotFoundError as exc:
            raise ValueError(f"This build can't open that protocol: {exc}") from exc
        except av.error.TimeoutError as exc:
            raise ValueError("Connection timed out — check the URL and your network.") from exc
        except av.error.HTTPError as exc:
            raise ValueError(f"The server refused the stream: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ValueError("Connection timed out — check the URL and your network.") from exc
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"The server refused the stream: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.NetworkError as exc:
            raise ValueError(f"Network failed mid-download — retry: {exc}") from exc
        except httpx.TooManyRedirects as exc:
            raise ValueError(f"Too many redirects — check the URL: {exc}") from exc
        except httpx.DecodingError as exc:
            raise ValueError(f"Response couldn't be decoded: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ValueError(f"Couldn't download that stream: {exc}") from exc
        except av.error.FFmpegError as exc:
            raise ValueError(f"Couldn't read that stream: {exc}") from exc
        except (OSError, ValueError) as exc:
            raise ValueError(f"Couldn't open URL: {exc}") from exc

        try:
            return EngineService._record_from(
                inp, output_path, container_format, duration_s, on_progress, cancel_event
            )
        finally:
            inp.close()
            # https inputs are backed by a temp file this method created; the
            # output may be large, so release it as soon as the muxer closes.
            if cleanup_path:
                with contextlib.suppress(OSError):
                    Path(cleanup_path).unlink(missing_ok=True)

    @staticmethod
    def _record_from(
        inp,
        output_path: str,
        container_format: str | None = None,
        duration_s: float | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_event: Event | None = None,
    ) -> str:
        """Demux-copy every stream of an open container into output_path.

        Test seam: tests drive this directly with a local file container
        instead of a network URL. Timestamps are shifted so the first packet
        of each stream lands at 0 (live inputs often start far up the
        timeline, which would leave a gaping offset in MP4).
        """
        out = av.open(output_path, "w", format=container_format)
        try:
            stream_map = {}
            for s in inp.streams:
                if s.type not in ("video", "audio", "subtitle", "data"):
                    continue
                if _is_attached_picture(s):
                    continue
                try:
                    stream_map[s] = out.add_stream_from_template(s, opaque=True)
                except ValueError as exc:
                    # MP4 cannot carry SRT/data or cover-art codecs; keep the
                    # recordable A/V tracks instead of failing the whole URL.
                    logger.info("Record stream %s skipped: %s", s.index, exc)
            if not stream_map:
                raise ValueError("No recordable streams found in that URL")

            # MP4-family sources carry h264/hevc in AVCC (length-prefixed) form;
            # the MPEG-TS muxer needs Annex-B. FFmpeg's CLI auto-inserts
            # h264_mp4toannexb for this combo — libavformat does NOT, so muxing
            # raw raises InvalidData. Apply the BSF manually per video stream.
            out_format = out.format.name
            bsfs: dict[int, tuple] = {}  # source stream index -> (ctx, out_stream)
            if out_format in ("mpegts", "hls"):
                for s, out_s in stream_map.items():
                    if s.type != "video" or s.codec_context is None:
                        continue
                    cname = s.codec_context.name or ""
                    bsf_name = None
                    if cname.startswith(("h264", "libx264")):
                        bsf_name = "h264_mp4toannexb"
                    elif cname.startswith(("hevc", "libx265")):
                        bsf_name = "hevc_mp4toannexb"
                    if bsf_name:
                        try:
                            bsfs[s.index] = (
                                av.BitStreamFilterContext(bsf_name, in_stream=s, out_stream=out_s),
                                out_s,
                            )
                        except Exception as exc:
                            logger.warning("BSF %s unavailable: %s", bsf_name, exc)

            start = time.monotonic()
            base_pts: dict[int, int] = {}
            base_dts: dict[int, int] = {}
            bytes_out = 0
            last_report = 0.0
            mux_clamp = _MuxClamp()

            def _emit(packet) -> None:
                """Zero-base the timestamps, run the BSF if any, mux result(s)."""
                # Real-world sources carry junk: zero-byte flush artifacts with no
                # timestamps (the mpegts muxer rejects size<7 AAC outright).
                if packet.size == 0 or (packet.pts is None and packet.dts is None):
                    logger.debug(
                        "Skipping empty/timestamp-less packet (stream %s)",
                        packet.stream.index if packet.stream is not None else "?",
                    )
                    return
                src_key = packet.stream.index if packet.stream is not None else -1
                if src_key >= 0:
                    # Separate bases per clock: B-frame delay (dts<pts) drives
                    # the first dts negative under a single base.
                    if src_key not in base_pts:
                        base_pts[src_key] = packet.pts if packet.pts is not None else 0
                    if src_key not in base_dts:
                        base_dts[src_key] = packet.dts if packet.dts is not None else 0
                    if packet.pts is not None:
                        packet.pts = max(0, packet.pts - base_pts[src_key])
                    if packet.dts is not None:
                        packet.dts = max(0, packet.dts - base_dts[src_key])
                out_s = stream_map.get(packet.stream) if src_key >= 0 else None
                # stream identity may already be consumed; resolve out_s via key
                if out_s is None:
                    for src, mapped in stream_map.items():
                        if src.index == src_key:
                            out_s = mapped
                            break
                bsf_entry = bsfs.get(src_key)
                candidates = bsf_entry[0].filter(packet) if bsf_entry else [packet]
                for pkt in candidates:
                    pkt.stream = out_s
                    mux_clamp.mux(out, pkt)

            for packet in inp.demux(list(stream_map)):
                _pause_hook(cancel_event)
                if cancel_event and cancel_event.is_set():
                    logger.info("Recording stopped by user (%d bytes) — keeping output", bytes_out)
                    break
                elapsed = time.monotonic() - start
                if duration_s is not None and elapsed >= duration_s:
                    logger.info("Recording reached duration cap (%.1fs)", duration_s)
                    break

                _emit(packet)
                bytes_out += max(0, packet.size or 0)

                now = time.monotonic()
                if on_progress and (now - last_report >= 0.25):
                    last_report = now
                    if duration_s and duration_s > 0:
                        prog = min(0.99, elapsed / duration_s)
                    else:
                        prog = 0.05  # live: no total — banner shows activity msg
                    on_progress(
                        prog,
                        f"Recording… {elapsed:.0f}s • {bytes_out // 1024} KB",
                    )

            # Drain BSF-delayed packets (EOF marker)
            for bsf_ctx, out_s in bsfs.values():
                for pkt in bsf_ctx.filter(None):
                    pkt.stream = out_s
                    mux_clamp.mux(out, pkt)

            if on_progress:
                total_s = time.monotonic() - start
                on_progress(1.0, f"Recorded {total_s:.0f}s • {bytes_out // 1024} KB")
        finally:
            _close_container(out)

        # Zero-packet stops never trigger the muxer's lazy header write — keep
        # the "output exists" contract so callers can rely on the path.
        Path(output_path).touch(exist_ok=True)
        return output_path
