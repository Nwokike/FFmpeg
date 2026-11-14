"""The capability gate: what this wheel can encode, and pair checks."""

from __future__ import annotations

from fractions import Fraction

import av

from core.engine_probe import codec_family, codec_label, muxers_for_container, probe
from services.engine_service.logs import _codec_supports_mode


class EngineCapabilityError(ValueError):
    """Requested operation is not supported by this device's FFmpeg build.

    Subclasses ValueError so the existing job-error path (and every
    ``pytest.raises(ValueError)`` contract) keeps working, while giving the UI
    a message that names the missing capability instead of leaking
    ``av.codec.UnknownCodecError: h264``.
    """


def _friendly_codec(requested: str, kind: str) -> str:
    """Derived display label for a codec name ('libx264' → 'H.264 (libx264)')."""

    return codec_label(requested)


def _encoder_pix_fmt(codec_name: str) -> str:
    """A pixel format the encoder actually accepts.

    Video transcodes default to yuv420p; still-image codecs (png = rgb24/rgba/
    pal8/gray only) reject it with av.error.ArgumentError at the first encode
    — real crash from the E2E pass. JPEG-family codecs want FULL-range YUV
    (yuvj420p): plain yuv420p fails avcodec_open2 with "Non full-range YUV is
    non-standard", which is why the corpus builder and the matrix skip it.
    Falls back to the encoder's first declared format when none match.
    """
    preferred = ("yuv420p", "yuvj420p", "rgb24", "rgba", "rgb8")
    try:
        codec = av.codec.Codec(codec_name, "w")
        declared = [f.name for f in codec.video_formats or []]
    except Exception:
        return "yuv420p"
    if not declared:
        return "yuv420p"
    # Full-range first for the JPEG family: their declared list carries both,
    # and only yuvj420p opens without strict-unofficial.
    if codec_name.startswith(("mjpeg", "ljpeg", "jpeg")):
        preferred = ("yuvj420p", "rgb24", *preferred)
    for name in preferred:
        if name in declared:
            return name
    return declared[0]


def _encoder_open_kwargs(codec_name: str) -> dict:
    """Extra ``add_stream`` kwargs an encoder needs to actually open.

    Some encoders are experimental on this FFmpeg build (vorbis; amv; snow —
    avcodec_open2 refuses them without ``strict=-2``), and the capability enum
    PyAV exposes does not carry the EXPERIMENTAL bit, so the answer is
    measured: open a throwaway context and catch the error. Callers that
    resolve user-chosen codecs must spread this — resolving is not opening
    (see the E2E vorbis crash).
    """
    try:
        if av.codec.Codec(codec_name, "w").experimental:
            return {"options": {"strict": "-2"}}
    except Exception:
        return {}
    return {}


def check_pair(container: str, video_codec: str | None, audio_codec: str | None) -> str | None:
    """None when (container, vcodec, acodec) muxes; else the refusal reason.

    Aliases resolve first (libx264↔h264 …), so an h264-only wheel still
    offers H.264 instead of hiding the chip. Unknown containers fail OPEN
    (None) — the matrix covers the wheel's muxers, not every FFmpeg build.
    """

    key = (container or "").lower().lstrip(".")
    matches = muxers_for_container(key)
    if not matches:
        # Unknown container: fail OPEN (None) — the matrix derives from the
        # wheel's muxers, not every FFmpeg build.
        return None
    video_family = set(codec_family(video_codec)) if video_codec else set()
    audio_family = set(codec_family(audio_codec)) if audio_codec else set()
    for match in matches:
        allowed_video = set(match.get("video", [])) | {
            v for v in (match.get("default_video"),) if v
        }
        allowed_audio = set(match.get("audio", [])) | {
            a for a in (match.get("default_audio"),) if a
        }
        if video_codec:
            encodable = {c for c in {video_codec, *video_family} if _codec_supports_mode(c, "w")}
            if not (encodable & allowed_video) and video_codec not in allowed_video:
                continue
        if audio_codec:
            encodable_audio = {
                c for c in {audio_codec, *audio_family} if _codec_supports_mode(c, "w")
            }
            if not (encodable_audio & allowed_audio) and audio_codec not in allowed_audio:
                continue
        return None  # one muxer for this container accepts the pair
    reason_codec = video_codec or audio_codec or ""
    return (
        f"{_friendly_codec(reason_codec, 'video' if video_codec else 'audio')} is not "
        f"muxable into .{key} on this build — pick another container"
    )


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
