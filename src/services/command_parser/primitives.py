"""Value parsing primitives: timestamps, sizes, chains, stream maps."""

from __future__ import annotations

import logging
import math
import re
from typing import NoReturn

logger = logging.getLogger(__name__)


class CommandError(ValueError):
    """A command this build cannot honestly run — surfaced verbatim to the user."""


def _refuse(msg: str) -> NoReturn:
    logger.warning("Command refused: %s", msg)
    raise CommandError(msg)


AUDIO_EXTS = {".mp3", ".aac", ".m4a", ".flac", ".opus", ".ogg", ".wav", ".oga"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".webvtt"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".flv", ".m4v", ".mpg", ".mpeg"}


def _parse_ts(value: str, flag: str) -> float:
    """``HH:MM:SS(.ms)`` | ``MM:SS`` | plain seconds → seconds."""
    bad = f"{flag} expects a timestamp (12, 1:02, or 00:01:02.5), got {value!r}"
    if ":" in value:
        parts = value.split(":")
        if len(parts) > 3:
            _refuse(bad)
        try:
            secs = 0.0
            for part in parts:
                secs = secs * 60 + float(part)
        except ValueError:
            _refuse(bad)
    else:
        try:
            secs = float(value)
        except ValueError:
            _refuse(bad)
    if not math.isfinite(secs) or secs < 0:
        _refuse(f"{flag} expects a finite timestamp >= 0, got {value!r}")
    return secs


def _parse_size(value: str, flag: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{2,5})x(\d{2,5})", value.strip())
    if not match:
        _refuse(f"{flag} expects WIDTHxHEIGHT (e.g. 1280x720), got {value!r}")
    return int(match.group(1)), int(match.group(2))


def _parse_bitrate(value: str, flag: str) -> int:
    """``128k`` / ``1M`` / ``128000`` → bits/s (what the engine's bit_rate wants)."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([kKmM])?", value.strip())
    if not match:
        _refuse(f"{flag} expects a bitrate like 128k or 1M, got {value!r}")
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    return int(number * {"k": 1_000, "m": 1_000_000, "": 1}[unit])


def _split_chain(value: str, flag: str) -> list[list[str]]:
    """``"hqdn3d=4:3:6:4.5,unsharp=5:5:1.0"`` → [(filter, args), …].

    Splits on top-level commas only (a comma inside quotes or a filter argument
    belongs to the filter), which is exactly FFmpeg's own graph syntax.
    """
    nodes: list[list[str]] = []
    depth = 0
    quote: str | None = None
    current: list[str] = []
    for ch in value:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
        elif ch == "[":
            depth += 1
            current.append(ch)
        elif ch == "]":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            nodes.append(_one_node("".join(current), flag))
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        nodes.append(_one_node("".join(current), flag))
    if not nodes:
        _refuse(f"{flag} is empty")
    return nodes


def _one_node(part: str, flag: str) -> list[str]:
    name, sep, args = part.strip().partition("=")
    name = name.strip()
    if not name:
        _refuse(f"{flag} has an empty filter name in {part!r}")
    _check_filter(name, flag)
    return [name, args.strip() if sep else ""]


def _check_filter(name: str, flag: str) -> None:
    """Refuse a filter this build does not have — measured, at plan time.

    The filter graph is only built at encode time, where a missing filter would
    surface as a raw job failure; asking av now turns it into a plan refusal
    that names the real cause.
    """
    import av.filter

    try:
        av.filter.Filter(name)
    except Exception:
        from core.engine_probe import probe

        count = probe().filter_count
        _refuse(
            f"{flag} filter {name!r} is not in this build ({count} filters are) — "
            "the Filters screen lists the ones this wheel has"
        )


def _map_spec(value: str, flag: str = "-map") -> tuple[str | None, int]:
    """``0:v:1`` → ("v", 1); ``0:a:0`` → ("a", 0); ``0:3`` → (None, 3).

    The kind is what the *value* says, never what the flag says — real ffmpeg
    reads the stream specifier.
    """
    text = value.strip()
    if text.startswith("0:"):
        text = text[2:]
    kind: str | None = None
    if ":" in text:
        head, _, tail = text.partition(":")
        if head in ("v", "a", "s", "d", "t"):
            kind, text = head, tail
    if not text.isdigit():
        _refuse(f"{flag} {value!r} needs a stream index (e.g. 0:v:1)")
    return kind, int(text)


def _codec_bits(value: str) -> str:
    """Drop a trailing ``(label)`` FFmpeg sometimes prints after a codec name."""
    return value.strip().split(" ")[0]


def _check_pix_fmt(codec: str, pix_fmt: str) -> None:
    """Refuse a pixel format this encoder does not declare (measured)."""
    import av

    try:
        formats = {str(fmt.name) for fmt in (av.Codec(codec, "w").video_formats or [])}
    except Exception:
        return
    if formats and pix_fmt not in formats:
        _refuse(
            f"{codec} cannot encode {pix_fmt!r} — it declares "
            f"{', '.join(sorted(formats)[:8])}{' …' if len(formats) > 8 else ''}"
        )


def _probe_encoder(codec: str) -> str:
    """Resolve an encoder name against the wheel (canonical name or refusal)."""
    from core.engine_probe import can_encode, probe

    probe()  # populates the codec set for can_encode
    if can_encode(codec):
        return codec
    # Family aliases: "h264" encodes through libx264 on this wheel.
    from core.engine_probe import codec_family

    for member in codec_family(codec):
        if can_encode(member):
            return member
    from core.engine_probe import codec_label

    _refuse(
        f"this build cannot encode {codec!r} ({codec_label(codec)}) — "
        "Engine Info lists the encoders it has"
    )
    return codec


def _encoder_takes_option(codec: str, name: str, value: str) -> bool:
    """Measured: does this encoder advertise this option?"""
    from services.engine_service import _supported_encoder_options

    return bool(_supported_encoder_options(codec, {name: value}))
