"""Codec resolution and job-error rendering."""

from __future__ import annotations

import av

from core.engine_probe import codec_family, muxers_for_container
from services.engine_service.capability import (
    EngineCapabilityError,
    _friendly_codec,
    available_audio_encoders,
    available_video_encoders,
)
from services.engine_service.logs import _codec_supports_mode, logger
from services.engine_service.safety import _unknown_codec_error_type


def _resolve_codec(requested: str, kind: str) -> str:
    """Return a verified encoder name for ``requested`` or raise a clear error.

    Two derivation steps, both from the wheel: the name itself when it
    constructs in "w" mode, else the family's display-preferred encoder (same
    AVCodecID: h264 → libx264, mp3 → libmp3lame, hevc → libx265...).
    Constructing ``av.codec.Codec(name, mode='w')`` is the only honest check —
    ``codecs_available`` also lists decoders, which is exactly how the Android
    build reached ``add_stream('h264')`` and exploded with UnknownCodecError.
    """
    if _codec_supports_mode(requested, "w"):
        # The wheel resolves aliases itself: Codec("h264","w").name is
        # "libx264" on this build. Return the canonical encoder name.
        try:
            return av.codec.Codec(requested, "w").name or requested
        except Exception:
            return requested

    order = available_video_encoders() if kind == "video" else available_audio_encoders()
    family = set(codec_family(requested))
    for candidate in order:
        if candidate in family and _codec_supports_mode(candidate, "w"):
            logger.info(
                "Resolved %s codec %r to available encoder %r",
                kind,
                requested,
                candidate,
            )
            return candidate

    available = order
    label = _friendly_codec(requested, kind)
    if available:
        options = ", ".join(available)
        detail = f" This device can encode with: {options}."
    else:
        detail = f" This device's FFmpeg build ships no {kind} encoders at all."
    raise EngineCapabilityError(
        f"{label} encoding is not available in this device's FFmpeg build.{detail}"
    )


def _resolve_or_raw(requested: str, kind: str) -> str:
    """Resolve when the wheel can; otherwise pass the name through untouched.

    Codec-less files must not fail on a codec they never use: the builder
    resolves for real only when the stream exists (the old in-branch resolve).
    """
    try:
        return _resolve_codec(requested, kind)
    except EngineCapabilityError:
        return requested


def _resolve_video_codec(requested: str) -> str:
    return _resolve_codec(requested, "video")


def _resolve_audio_codec(requested: str) -> str:
    return _resolve_codec(requested, "audio")


def _derive_audio_codec_for_format(requested_format: str) -> str:
    """Display-ordered encodable audio codec for one output format.

    Derived from the muxer matrix (extension → muxers → default/supported
    audio codecs). Raises EngineCapabilityError when no muxer for the format
    has an encodable audio codec.
    """

    order = available_audio_encoders()
    matches = muxers_for_container(requested_format)
    # Only the muxer that will actually write the file (best match) constrains
    # the codec: mp4's supported list must not bless libopus into an ipod
    # container. FFmpeg's own default for the container wins (wav →
    # pcm_s16le, mp3 → the wheel's default); then the display-ordered set.
    default_codec = ""
    supported: list[str] = []
    for match in matches[:1]:
        default = match.get("default_audio") or ""
        if default and _codec_supports_mode(default, "w"):
            default_codec = default
        supported = [c for c in match.get("audio", []) if _codec_supports_mode(c, "w")]
    for candidate in [default_codec, *(c for c in order if c in supported)]:
        if candidate:
            logger.info("Derived audio codec %r for format %r", candidate, requested_format)
            return candidate
    if supported:
        return supported[0]
    raise EngineCapabilityError(
        f"Unknown output format {requested_format!r}. The installed FFmpeg "
        "build has no muxer for it with an encodable audio codec."
    )


def audio_codec_for_format(requested_format: str) -> str | None:
    """The encoder the engine will use for one audio format (None when it cannot).

    The screens need the same answer the engine derives, so the option panel
    shows the settings of the encoder that will actually run — not a guess.
    """
    try:
        return _derive_audio_codec_for_format(requested_format)
    except Exception:
        return None


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
