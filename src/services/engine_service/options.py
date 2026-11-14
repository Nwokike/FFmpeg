"""Encoder option plumbing: validation against the wheel's schema."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import av

from core.engine_probe import probe
from services.engine_service.logs import _codec_supports_mode, logger
from services.engine_service.resolve import _resolve_video_codec


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


def _tls_available() -> bool:
    """Does THIS wheel have a TLS protocol handler? (measured, cached)

    The stock flet-libffmpeg build is bare LGPL with no TLS, so https recording
    has to go through httpx there; our wrap build (mbedtls) opens https natively.
    The capability probe answers this — no platform or build literals.
    """
    global _TLS_OK
    if _TLS_OK is None:
        from core.engine_probe import probe

        try:
            _TLS_OK = probe().https_ok
        except Exception as exc:
            logger.warning("TLS capability probe failed: %s", exc)
            _TLS_OK = False
    return _TLS_OK


_TLS_OK: bool | None = None


def _wire_option_value(value: Any) -> str:
    """One encoder-option value in the form av accepts.

    av's option dict is ``dict[str, str]``: passing an int or float raises
    ``TypeError: Argument 'value' has incorrect type`` at add_stream time, so
    every caller funnels through here.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (list, tuple, set, frozenset)):
        return "+".join(str(item).lstrip("+-") for item in value if str(item).strip())
    return str(value)


def _supported_encoder_options(codec_name: str, requested: dict[str, Any]) -> dict[str, str]:
    """Keep only options this wheel's encoder accepts, with values that can apply.

    Both option sets are legal: the generic ones (b/g/bf/threads/qmin/flags) are
    the AVCodecContext class options every encoder shares, and av hands the dict
    to avcodec_open2, which applies generic and private alike. Keeping private
    only (the old filter) silently dropped most of what a UI can offer.

    Values are checked against the measured schema too: a numeric option that
    was handed text (SVT-AV1's ``preset`` is a number, x264's is a word), or a
    number outside the option's declared range, is dropped with one info line
    instead of crashing ``avcodec_open2`` — the same knob means different things
    per encoder, and the engine has to be the one that knows.
    """
    try:
        ctx = av.CodecContext.create(codec_name, "w")
        valid = {str(option.name) for option in ctx.supported_options.generic}
        valid |= {str(option.name) for option in ctx.supported_options.private}
    except Exception as exc:
        logger.debug("Could not inspect options for %s: %s", codec_name, exc)
        return {str(key): _wire_option_value(value) for key, value in requested.items()}

    schema = {
        str(spec["name"]): spec for spec in (probe().encoder_option_schema.get(codec_name) or [])
    }
    kept: dict[str, str] = {}
    dropped: list[str] = []
    for key, raw in requested.items():
        if key not in valid:
            dropped.append(str(key))
            continue
        value = _wire_option_value(raw)
        spec = schema.get(str(key))
        if spec is not None:
            verdict = _value_fits(spec, value)
            if verdict is not None:
                logger.info("Dropping %s option %s=%r: %s", codec_name, key, value, verdict)
                continue
        kept[str(key)] = value
    if dropped:
        logger.info("Dropping unsupported %s encoder options: %s", codec_name, ", ".join(dropped))
    return kept


_NUMERIC_OPTION_TYPES = frozenset({"2", "3", "10", "4", "5", "7"})

_NUMERIC_SUFFIXES = {"k": 1e3, "m": 1e6, "g": 1e9}


def _parse_option_number(value: str) -> float | None:
    """Parse a numeric option value the way FFmpeg does, or None.

    ``"30"``, ``"1M"``, ``"0.5k"`` parse; ``"ultrafast"`` does not — and on a
    numeric option FFmpeg would refuse it, so the caller drops it first.
    """
    text = value.strip()
    if not text:
        return None
    multiplier = 1.0
    if text[-1].lower() in _NUMERIC_SUFFIXES and not text[-1].isdigit():
        multiplier = _NUMERIC_SUFFIXES[text[-1].lower()]
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _value_fits(spec: dict, value: str) -> str | None:
    """Why a value cannot apply, or None when it can (measured schema only)."""
    option_type = str(spec.get("type") or "")
    low, high = spec.get("min"), spec.get("max")
    if option_type in _NUMERIC_OPTION_TYPES:
        number = _parse_option_number(value)
        if number is None:
            bounds = (
                f" ({low:g} … {high:g})"
                if low is not None and high is not None and high > low
                else ""
            )
            return f"this encoder's option is a number{bounds}"
        if (
            low is not None
            and high is not None
            and float(high) > float(low)
            and not (float(low) <= number <= float(high))
        ):
            return f"outside the declared range {low:g} … {high:g}"
    return None


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
