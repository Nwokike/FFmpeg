"""Engine capability probe — codecs, filters, formats and protocols.

Everything here runs against the installed `av` wheel, so the SAME module
answers device-specific questions on a phone: `flet build apk` + the Engine
Info screen + the Streams screen's protocol badge all call into it. No
assumptions — every result is a measured value from this exact wheel.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field, fields
from fractions import Fraction
from pathlib import Path

import av
import av.codec
import av.filter

from core.storage_paths import get_cache_dir

logger = logging.getLogger(__name__)

# Filters the app's feature set depends on (verified present in the Windows
# wheel; each is re-checked per device build here).
REQUIRED_FILTERS = [
    "crop",
    "scale",
    "transpose",
    "hflip",
    "vflip",
    "rotate",
    "atempo",
    "asetpts",
    "setpts",
    "trim",
    "atrim",
    "volume",
    "equalizer",
    "highpass",
    "lowpass",
    "treble",
    "bass",
    "anlmdn",
    "firequalizer",
    "unsharp",
    "pan",
    "amix",
    "overlay",
    "concat",
    "fps",
    "thumbnail",
    "tile",
    "palettegen",
    "paletteuse",
    "loudnorm",
    "astats",
    "volumedetect",
    "silenceremove",
    "aresample",
    "aformat",
    "select",
]
# Optional filters whose absence degrades a feature, not the app.
OPTIONAL_FILTERS = ["drawbox", "drawtext", "subtitles", "ass", "afftfilt"]

# Encoders the app wants (first available wins per quality tier).
#
# The LGPL list matters: Flet Mobile Forge builds `flet-libffmpeg` WITHOUT
# --enable-gpl and with --disable-autodetect, so the Android wheel has none of
# the GPL/external encoders. Its real set is FFmpeg's own — mpeg4/mjpeg/png/
# gif/prores/ffv1 video and aac/opus/vorbis/flac/alac/pcm audio. Listing those
# here is what lets the capability report, the codec pickers and every
# friendly error tell the truth on device instead of reporting "NONE".
PREFERRED_VIDEO_ENCODERS = [
    "libx264",
    "libx265",
    "hevc",
    "libsvtav1",
    "libvpx-vp9",
    "vp9",
    "libvpx",
    "av1",
    "h264",
    "mpeg4",
    "mjpeg",
    "png",
    "gif",
    "prores",
    "ffv1",
    "libwebp",
]
PREFERRED_AUDIO_ENCODERS = [
    "aac",
    "libmp3lame",
    "mp3",
    "libopus",
    "flac",
    "opus",
    "vorbis",
    "alac",
    "pcm_s16le",
    "pcm_s24le",
]

# Network protocols to probe for live-stream support. HLS and DASH are
# DEMUXERS (formats), not protocol handlers — probing `hls://` always reports
# "missing" even on a full build, so they are probed via `formats` instead.
PROTOCOLS = ["http", "https", "rtmp", "tcp", "udp"]

_ALL_CODECS: set[str] = set()


@dataclass
class EngineProbe:
    """Measured capability report for the installed av wheel."""

    av_version: str = ""
    codec_count: int = 0
    encoder_count: int = 0
    decoder_count: int = 0
    filter_count: int = 0
    format_count: int = 0
    codecs: set[str] = field(default_factory=set)
    encoders: set[str] = field(default_factory=set)
    decoders: set[str] = field(default_factory=set)
    filters: set[str] = field(default_factory=set)
    formats: set[str] = field(default_factory=set)
    hw_devices: set[str] = field(default_factory=set)
    hardware_configs: list[str] = field(default_factory=list)
    bitstream_filters: set[str] = field(default_factory=set)
    video_codec_formats: dict[str, list[str]] = field(default_factory=dict)
    audio_codec_formats: dict[str, list[str]] = field(default_factory=dict)
    encoder_options: dict[str, list[str]] = field(default_factory=dict)
    library_versions: str = ""
    protocol_probe: dict[str, str] = field(default_factory=dict)
    video_encoder_picks: list[str] = field(default_factory=list)
    audio_encoder_picks: list[str] = field(default_factory=list)
    missing_required_filters: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # ── helpers ──────────────────────────────────────────────

    @property
    def gif_ok(self) -> bool:
        return "gif" in self.encoders or "gif" in self.codecs

    @property
    def h264_encode(self) -> bool:
        return "libx264" in self.encoders or "h264" in self.encoders

    @property
    def mpeg4_encode(self) -> bool:
        """MPEG-4 Part 2 — the LGPL fallback video encoder FFmpeg always ships."""
        return "mpeg4" in self.encoders

    @property
    def hls_ok(self) -> bool:
        """HLS is a DEMUXER (format), never a protocol — see PROTOCOLS."""
        return "hls" in self.formats or "hls" in self.codecs

    @property
    def dash_ok(self) -> bool:
        return "dash" in self.formats

    @property
    def https_ok(self) -> bool:
        return self.protocol_probe.get("https", "") == "present"

    @property
    def network_ok(self) -> bool:
        return (
            self.protocol_probe.get("http") == "present"
            or self.protocol_probe.get("https", "") == "present"
        )

    def to_text(self) -> str:
        """Human-readable report (Engine Info screen + spike log)."""
        lines = [
            f"av {self.av_version}",
            f"libraries: {self.library_versions or 'unavailable'}",
            f"codecs: {self.codec_count} total | decoders verified: {self.decoder_count}",
            f"filters: {self.filter_count} | formats: {self.format_count}",
            f"bitstream filters: {len(self.bitstream_filters)}",
            f"video encoders (verified): {', '.join(self.video_encoder_picks) or 'NONE'}",
            f"audio encoders (verified): {', '.join(self.audio_encoder_picks) or 'NONE'}",
            f"hw devices: {', '.join(sorted(self.hw_devices)) or 'none detected'}",
            f"hw configs: {len(self.hardware_configs)}",
            f"encoder option sets: {len(self.encoder_options)}",
            "protocol probe: " + ", ".join(f"{k}={v}" for k, v in self.protocol_probe.items()),
            f"HLS (demuxer): {'present' if self.hls_ok else 'missing'}",
            f"DASH (demuxer): {'present' if self.dash_ok else 'missing'}",
            f"GIF pipeline: {'OK' if self.gif_ok else 'MISSING'}",
        ]
        if self.missing_required_filters:
            lines.append("MISSING required filters: " + ", ".join(self.missing_required_filters))
        lines.extend(f"note: {note}" for note in self.notes)
        return "\n".join(lines)


# ── availability resolvers (defensive: probe several export paths) ──


def _as_name_set(obj) -> set[str]:
    if obj is None:
        return set()
    if callable(obj):
        try:
            obj = obj()
        except Exception as exc:
            logger.warning("Capability callable failed: %s", exc)
            return set()
    try:
        return {str(x) for x in obj}
    except TypeError:
        return set()


def _codec_mode_available(name: str, mode: str) -> bool:
    """True if `name` exists and supports `mode` ('w' or 'r')."""
    if name not in _ALL_CODECS:
        return False
    try:
        av.codec.Codec(name, mode=mode)
        return True
    except Exception:
        return False


def _find_attr(root, *names) -> set[str]:
    """Find a name-set on `root`, in the `av.format` module, or under `av.*`."""
    for name in names:
        obj = getattr(root, name, None)
        if obj is not None:
            return _as_name_set(obj)
        try:
            import importlib

            mod = importlib.import_module(name)
            obj = getattr(mod, "formats_available", None)
            if obj is not None:
                return _as_name_set(obj)
        except Exception:
            continue
    return set()


# Formats the Extract/Audio screens offer, and the encoder names each maps to.
# Screens ask `can_encode_format()` so an option the wheel cannot encode is
# never shown, instead of failing after the user has already hit Process.
# ogg/vorbis, m4a and 24-bit wav ride the installed wheel (verified mode="w").
AUDIO_FORMAT_ENCODERS = {
    "mp3": ("libmp3lame", "mp3"),
    "aac": ("aac",),
    "m4a": ("aac",),
    "flac": ("flac",),
    "opus": ("libopus", "opus"),
    "ogg": ("vorbis", "libvorbis"),
    "wav": ("pcm_s16le", "pcm_s24le"),
}


def can_encode(name: str) -> bool:
    """True if the installed wheel can open ``name`` in encoder mode.

    Measures rather than assumes: ``_codec_mode_available`` constructs the
    Codec, which is the only check that distinguishes an encoder from a
    decoder-only name in ``codecs_available``.
    """
    probe()  # ensures _ALL_CODECS is populated for the mode check
    return _codec_mode_available(name, "w")


def can_encode_format(fmt: str) -> bool:
    """True if the Extract/Audio screens can actually produce this format."""
    return any(can_encode(enc) for enc in AUDIO_FORMAT_ENCODERS.get(fmt.lower(), ()))


_PROBE_MEM: EngineProbe | None = None
_SET_FIELDS = (
    "codecs",
    "encoders",
    "decoders",
    "filters",
    "formats",
    "hw_devices",
    "bitstream_filters",
)


def _probe_cache_path() -> Path:
    # caps3: adds the LGPL encoder set + demuxer-based HLS/DASH probing, so
    # older caps2 files (which reported "no video encoders" on Android) are
    # deliberately ignored rather than trusted.
    return get_cache_dir() / f"engine_probe_{av.__version__}_caps3.json"


def _load_cached() -> EngineProbe | None:
    """Disk tier: CACHE JSON keyed on the av wheel version (sets round-trip)."""
    try:
        path = _probe_cache_path()
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        valid = {f.name for f in fields(EngineProbe)}
        payload = {k: v for k, v in payload.items() if k in valid}
        for name in _SET_FIELDS:
            payload[name] = set(payload.get(name, []))
        return EngineProbe(**payload)
    except Exception as exc:
        logger.warning("Engine probe cache unreadable — re-measuring: %s", exc)
        return None


def _save_cached(p: EngineProbe) -> None:
    try:
        payload = asdict(p)
        for name in _SET_FIELDS:
            payload[name] = sorted(payload[name])
        _probe_cache_path().write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning("Engine probe cache write failed: %s", exc)


def probe() -> EngineProbe:
    """Full capability probe — measured once per wheel, then served from RAM
    and a CACHE JSON. The socket-level protocol pass costs ~2s and cannot
    change within one installed wheel, so Settings/Engine Info/spike reuse it.
    """
    global _PROBE_MEM, _ALL_CODECS
    if _PROBE_MEM is None:
        cached = _load_cached()
        if cached is not None:
            _PROBE_MEM = cached
        else:
            _PROBE_MEM = _measure()
            _save_cached(_PROBE_MEM)
    _ALL_CODECS = _PROBE_MEM.codecs
    return _PROBE_MEM


def _measure() -> EngineProbe:
    """Run the full capability probe against the installed av."""
    global _ALL_CODECS
    p = EngineProbe(av_version=av.__version__)

    # Verified in installed source: av.codec.codecs_available and
    # av.filter.filters_available are module-level SETS (codec.py:369,
    # filter.py:67) — no per-mode split exists, so encoder/decoder support
    # is probed per preferred name via Codec(name, mode=...).
    p.codecs = _as_name_set(getattr(av.codec, "codecs_available", None))
    _ALL_CODECS = p.codecs
    p.codec_count = len(p.codecs)

    preferred = PREFERRED_VIDEO_ENCODERS + PREFERRED_AUDIO_ENCODERS

    # Verified empirically against the installed wheel: Codec(name, mode)
    # accepts mode="w" (encode) and mode="r" (decode) only.
    p.encoders = {n for n in preferred if _codec_mode_available(n, "w")}
    p.decoders = {n for n in preferred if _codec_mode_available(n, "r")}
    p.encoder_count = len(p.encoders)
    p.decoder_count = len(p.decoders)

    p.filters = _as_name_set(getattr(av.filter, "filters_available", None))
    p.filter_count = len(p.filters)
    p.formats = _find_attr(av, "formats_available", "av.format.formats_available")
    p.format_count = len(p.formats)
    p.bitstream_filters = _as_name_set(getattr(av, "bitstream_filters_available", ()))
    try:
        p.library_versions = ", ".join(
            f"{name} {version[0]}.{version[1]}.{version[2]}"
            for name, version in av.library_versions.items()
        )
    except Exception as exc:
        p.notes.append(f"library version report unavailable: {exc}")

    # Measure encoder metadata instead of exposing only a flat name list.
    # This powers honest codec/filter pickers and validates options before a
    # job can fail halfway through a long encode.
    for name in preferred:
        try:
            codec = av.Codec(name, "w")
        except Exception:
            continue
        if codec.video_formats:
            p.video_codec_formats[name] = [str(fmt.name) for fmt in codec.video_formats]
        if codec.audio_formats:
            p.audio_codec_formats[name] = [str(fmt.name) for fmt in codec.audio_formats]
        for hw in codec.hardware_configs or []:
            device = getattr(hw, "device_type", "unknown")
            fmt = getattr(hw, "format", None)
            p.hardware_configs.append(f"{name}:{device}:{getattr(fmt, 'name', 'any')}")
        try:
            ctx = av.CodecContext.create(name, "w")
            p.encoder_options[name] = sorted(
                {str(option.name) for option in ctx.supported_options.private}
            )
        except Exception as exc:
            logger.debug("Encoder option probe failed for %s: %s", name, exc)

    # Keep FFmpeg's native diagnostics visible in the app log instead of the
    # wheel's default discard callback.
    try:
        av.logging.set_level(av.logging.WARNING)
    except Exception as exc:
        p.notes.append(f"av logging setup unavailable: {exc}")

    # Hardware accel (may be empty on the mobile build — that is a result, not a failure).
    try:
        fns = getattr(av.codec, "hwdevices_available", None)
        p.hw_devices = _as_name_set(fns()) if fns else set()
        if not p.hw_devices:
            p.notes.append("hw accel: no devices detected — query per-encoder hardware_configs")
    except Exception as exc:
        p.notes.append(f"hwdevices_available failed: {exc}")

    # Encoder picks are the VERIFIED mode="w" set only (no fallback to the
    # full codec-name set — that would overstate encoder support).
    p.video_encoder_picks = [c for c in PREFERRED_VIDEO_ENCODERS if c in p.encoders]
    p.audio_encoder_picks = [c for c in PREFERRED_AUDIO_ENCODERS if c in p.encoders]
    p.missing_required_filters = [f for f in REQUIRED_FILTERS if p.filters and f not in p.filters]
    if not p.filters:
        p.notes.append("filters_available unresolved in this build — filter features gated off")

    # Protocol probe: opening a URL on a dead port tells us whether the
    # protocol handler itself is compiled in (connection-level error) vs
    # missing (ProtocolNotFound-style error).
    for proto in PROTOCOLS:
        p.protocol_probe[proto] = _probe_protocol(proto)

    p.notes.append("capability sets measured from this wheel; UI adapts to what is listed")
    return p


def _probe_protocol(proto: str) -> str:
    port = "443" if proto == "https" else "9"
    url = f"{proto}://127.0.0.1:{port}/"
    # The dead-port open below ALWAYS emits native ERROR lines (connection
    # refused/timeout) on success paths too — that is the signal, not a
    # failure.  Swallow them inside this probe window only (av.logging.Capture
    # verified empirically: native lines suppressed, exception still raised,
    # no global level change).  Everything outside this function keeps full
    # native diagnostics.
    try:
        with av.logging.Capture():
            c = av.open(url, timeout=(1, 2))
            c.close()
        return "present"
    except Exception as exc:
        # PyAV 18 exposes ProtocolNotFoundError; older wheels used
        # ProtocolNotFound.  Resolve the names from the installed module
        # instead of assuming either spelling exists.
        missing_types = tuple(
            error_type
            for name in ("ProtocolNotFound", "ProtocolNotFoundError")
            if isinstance(error_type := getattr(av.error, name, None), type)
        )
        if missing_types and isinstance(exc, missing_types):
            return "missing"
        err_str = str(exc).lower()
        if "protocol not found" in err_str or "unknown protocol" in err_str:
            return "missing"
        return "present"  # network errors (connection refused, timeout, etc.) mean the protocol handler ran


def synthetic_transcode(out_dir: str | Path) -> dict:
    """Self-test: generate 10 synthetic frames, encode H.264 → MP4, read back,
    extract a frame and write a JPG — proves the full loop without test media.

    Returns {frames, duration_s, mp4_bytes, jpg_bytes, elapsed_s} or raises.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / "spike_test.mp4"
    jpg_path = out_dir / "spike_test.jpg"

    w, h, fps, n_frames = 320, 180, 30, 10

    def _make_frame(i: int):
        frame = av.VideoFrame(w, h, "bgr24")
        rows = bytearray()
        for y in range(h):
            b0 = (i * 3 + y * 7) % 256
            row = bytearray()
            for x in range(w):
                row.extend(((x + i) % 256, (x + y + b0) % 256, b0))
            rows.extend(row)
        frame.planes[0].update(bytes(rows))
        return frame

    encoder = "libx264" if _codec_mode_available("libx264", "w") else "h264"
    tb = Fraction(1, fps)

    t0 = time.perf_counter()
    out = av.open(str(mp4_path), "w")
    vs = out.add_stream(encoder, rate=fps)
    vs.width, vs.height = w, h
    vs.pix_fmt = "yuv420p"
    vs.time_base = tb
    for i in range(n_frames):
        frame = _make_frame(i)
        frame.pts = i
        frame.time_base = tb
        for pkt in vs.encode(frame):
            out.mux(pkt)
    for pkt in vs.encode(None):  # flush
        out.mux(pkt)
    out.close()
    encode_s = time.perf_counter() - t0

    frames = 0
    duration_s = 0.0
    with av.open(str(mp4_path)) as inp:
        stream = inp.streams.video[0]
        first = None
        for frame in inp.decode(stream):
            frames += 1
            if first is None:
                first = frame
        if inp.duration:
            duration_s = float(inp.duration) / float(av.time_base)
        if first is not None:
            try:
                first.save(str(jpg_path))
            except Exception:
                first.reformat(format="bgr24").save(str(jpg_path))
    jpg_bytes = jpg_path.stat().st_size if jpg_path.exists() else 0

    return {
        "frames": frames,
        "expected_frames": n_frames,
        "duration_s": round(duration_s, 3),
        "mp4_bytes": mp4_path.stat().st_size,
        "jpg_bytes": jpg_bytes,
        "encoder": encoder,
        "encode_s": round(encode_s, 3),
        "ok": frames == n_frames and jpg_bytes > 0,
    }


def run() -> tuple[EngineProbe, dict]:
    """Probe + self-test, logging both. Returns (probe, transcode_result)."""
    p = probe()
    logger.info("Engine probe:\n%s", p.to_text())
    result: dict = {}
    try:
        result = synthetic_transcode(Path(__file__).resolve().parent.parent / "ui-spike")
        logger.info("Synthetic transcode self-test: %s", result)
    except Exception as exc:
        logger.exception("Synthetic transcode self-test failed")
        result = {"ok": False, "error": str(exc)}
    return p, result
