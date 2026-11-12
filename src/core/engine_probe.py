"""Engine capability schema — everything derived from the installed av wheel.

There are no preference lists here: the module enumerates every codec, filter,
format, protocol, device and bitstream filter the installed wheel actually
ships, and measures each encoder's full option schema (CodecOption: name, type,
choices, default, min/max, help). Whatever the wheel ships is exactly what the
app offers; a codec that is absent from a future wheel disappears from the UI
automatically.

Everything runs against the installed `av` wheel, so the SAME module answers
device-specific questions on a phone: `flet build apk` + the Engine Info screen
+ the Streams screen's protocol badge all call into it. Results are cached in
RAM and on disk keyed on the linked FFmpeg build identity (not the PyAV wrapper
version), so a rebuilt native library re-measures instead of serving stale
capabilities.

Two tiers:
- boot probe (`probe()`): codecs/filters/formats/protocols/devices + the
  common muxers' default codecs — seconds;
- muxer matrix (`muxer_matrix()`): EVERY output-capable format probed via a
  temp file for default/supported codecs — lazy, off-thread, disk-cached.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field, fields
from fractions import Fraction
from pathlib import Path

import av
import av.codec
import av.filter

try:
    from av.codec.hwaccel import hwdevices_available as _hwdevices_available
except Exception:  # pragma: no cover - build without hwaccel module
    _hwdevices_available = None

from core.storage_paths import get_cache_dir

logger = logging.getLogger(__name__)

# Protocols probed by default (dead-port open tells us whether the protocol
# handler is compiled in). HLS/DASH are demuxers, probed via `formats` instead.
PROTOCOLS = ["http", "https", "rtmp", "tcp", "udp"]

# Presentation-only ordering: which verified encoders are offered FIRST in
# pickers. Every verified encoder is offered; this only biases the default
# selection. It is not a capability gate.
_ENCODER_DISPLAY_ORDER = (
    "libx264",
    "libx265",
    "libsvtav1",
    "libaom-av1",
    "libvpx-vp9",
    "libvpx",
    "libopus",
    "libmp3lame",
    "libwebp",
    "pcm_s16le",
    "pcm_s24le",
)

_ALL_CODECS: set[str] = set()


@dataclass
class EngineProbe:
    """Measured capability schema for the installed av wheel."""

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
    # Full per-encoder option schema (generic + private AVOptions): encoder →
    # [{name, type, choices, default, min, max, help, flags, is_array}]. This is
    # what Phase 4's UI renders — every setting the engine actually has.
    encoder_option_schema: dict[str, list[dict]] = field(default_factory=dict)
    # Codec families keyed by AVCodecID (as str for JSON): same id = same codec
    # (h264 decoder, libx264 encoder, h264_nvenc...). Replaces alias maps.
    codec_families: dict[str, list[str]] = field(default_factory=dict)
    # Derived display labels for every constructible codec name.
    codec_labels: dict[str, str] = field(default_factory=dict)
    codec_long_names: dict[str, str] = field(default_factory=dict)
    # Per-format metadata: name → {is_input, is_output, extensions, flags}.
    format_meta: dict[str, dict] = field(default_factory=dict)
    # Per-muxer defaults from the wheel (boot tier: the common write targets).
    muxer_default_video: dict[str, str] = field(default_factory=dict)
    muxer_default_audio: dict[str, str] = field(default_factory=dict)
    muxer_default_subtitle: dict[str, str] = field(default_factory=dict)
    muxer_video_codecs: dict[str, list[str]] = field(default_factory=dict)
    muxer_audio_codecs: dict[str, list[str]] = field(default_factory=dict)
    encoder_frame_rates: dict[str, list[str]] = field(default_factory=dict)
    encoder_audio_rates: dict[str, list[int]] = field(default_factory=dict)
    encoder_audio_formats: dict[str, list[str]] = field(default_factory=dict)
    encoder_intra_only: list[str] = field(default_factory=list)
    encoder_lossless: list[str] = field(default_factory=list)
    library_versions: str = ""
    protocol_probe: dict[str, str] = field(default_factory=dict)
    video_encoder_picks: list[str] = field(default_factory=list)
    audio_encoder_picks: list[str] = field(default_factory=list)
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
        """MPEG-4 Part 2 — the FFmpeg-native video encoder always shipped."""
        return "mpeg4" in self.encoders

    @property
    def hls_ok(self) -> bool:
        """HLS is a DEMUXER (format), never a protocol."""
        return "hls" in self.formats

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
            f"codecs: {self.codec_count} total | encoders (verified): {len(self.encoders)}"
            f" | decoders (verified): {len(self.decoders)} | families: {len(self.codec_families)}",
            f"filters: {self.filter_count} | formats: {self.format_count}"
            f" | bitstream filters: {len(self.bitstream_filters)}",
            f"encoders with option schema: {len(self.encoder_option_schema)}",
            f"video encoders (verified): {', '.join(self.video_encoder_picks) or 'NONE'}",
            f"audio encoders (verified): {', '.join(self.audio_encoder_picks) or 'NONE'}",
            f"hw devices: {', '.join(sorted(self.hw_devices)) or 'none detected'}",
            f"hw configs: {len(self.hardware_configs)}",
            "protocol probe: " + ", ".join(f"{k}={v}" for k, v in self.protocol_probe.items()),
            f"HLS (demuxer): {'present' if self.hls_ok else 'missing'}",
            f"DASH (demuxer): {'present' if self.dash_ok else 'missing'}",
            f"GIF pipeline: {'OK' if self.gif_ok else 'MISSING'}",
        ]
        lines.extend(f"note: {note}" for note in self.notes)
        return "\n".join(lines)


# ── availability helpers ─────────────────────────────────────────────────────


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
    """Find a name-set on `root` or in the `av.format` module."""
    for name in names:
        obj = getattr(root, name, None)
        if obj is not None:
            return _as_name_set(obj)
        if "." in name:
            mod_name, _, attr = name.rpartition(".")
            try:
                import importlib

                mod = importlib.import_module(mod_name or name)
                obj = getattr(mod, attr or name, None)
            except Exception:
                continue
            if obj is not None:
                return _as_name_set(obj)
    return set()


def _constructible(name: str) -> av.codec.Codec | None:
    """Construct the codec in whichever mode it supports (None if neither)."""
    for mode in ("r", "w"):
        try:
            return av.codec.Codec(name, mode=mode)
        except Exception:
            continue
    return None


def _derive_label(family: list[str]) -> str:
    """Human label from the wheel: canonical long-name head + encoder name.

    The head comes from the family's decoder long_name (its first token when
    short); the parenthesised suffix names the family's display-preferred
    external encoder, so libx264 shows as "H.264 (libx264)". Keys derive from
    the wheel; nothing hand-written.
    """
    decoder = None
    for member in family:
        with contextlib.suppress(Exception):
            decoder = av.codec.Codec(member, "r")
            break
    ref = decoder or _constructible(family[0])
    if ref is None:
        return family[0]
    head = (ref.long_name or ref.name).strip()
    token = head.split(" ")[0]
    head = token if 0 < len(token) <= 10 else head

    encoders = [n for n in family if _codec_mode_available(n, "w")]
    ordered = _order_encoders(set(encoders))
    shown = ordered[0] if ordered else (encoders[0] if encoders else "")
    decoder_name = decoder.name if decoder is not None else None
    if shown and shown != decoder_name:
        return f"{head} ({shown})"
    return head or family[0]


# ── boot probe ───────────────────────────────────────────────────────────────


def _ffmpeg_build_identity() -> str:
    """Short hash of the linked FFmpeg build (NOT the PyAV wrapper version).

    ``av.__version__`` tracks the Python wrapper; a rebuilt FFmpeg under the
    same PyAV serves stale capabilities forever if the cache key ignores it.
    ``ffmpeg_version_info`` is a plain string attribute plus the per-library
    tuple map — both change exactly when the native build does.
    """
    try:
        version_info = av.ffmpeg_version_info
    except Exception:
        version_info = "unknown"
    try:
        libs = ",".join(
            f"{name}={'.'.join(str(v) for v in ver)}"
            for name, ver in sorted(av.library_versions.items())
        )
    except Exception:
        libs = "unknown"
    import hashlib

    return hashlib.sha256(f"{version_info}|{libs}".encode()).hexdigest()[:12]


def _probe_cache_path() -> Path:
    return get_cache_dir() / f"engine_probe_{av.__version__}_{_ffmpeg_build_identity()}_caps5.json"


def _load_cached() -> EngineProbe | None:
    """Disk tier: CACHE JSON keyed on the av wheel version (sets round-trip)."""
    try:
        path = _probe_cache_path()
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        valid = {f.name for f in fields(EngineProbe)}
        payload = {k: v for k, v in payload.items() if k in valid}
        for name in (
            "codecs",
            "encoders",
            "decoders",
            "filters",
            "formats",
            "hw_devices",
            "bitstream_filters",
        ):
            payload[name] = set(payload.get(name, []))
        return EngineProbe(**payload)
    except Exception as exc:
        logger.warning("Engine probe cache unreadable — re-measuring: %s", exc)
        return None


def _save_cached(p: EngineProbe) -> None:
    try:
        payload = asdict(p)
        for name in (
            "codecs",
            "encoders",
            "decoders",
            "filters",
            "formats",
            "hw_devices",
            "bitstream_filters",
        ):
            payload[name] = sorted(payload[name])
        _probe_cache_path().write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning("Engine probe cache write failed: %s", exc)


def probe() -> EngineProbe:
    """Full capability probe — measured once per wheel, then served from RAM
    and a CACHE JSON. The socket-level protocol pass is sequential (five
    dead-port opens, ~5s total) and cannot change within one installed wheel,
    so Settings/Engine Info/spike reuse it.
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


_PROBE_MEM: EngineProbe | None = None

# Boot-tier muxers: registered muxer NAMES (not app container names — mkv's
# muxer is "matroska", m4a's is "ipod"; containers resolve to muxers via
# extensions through muxers_for_container). The lazy muxer_matrix() covers
# EVERY output format.
_BOOT_MUXERS = (
    "mp4",
    "mov",
    "matroska",
    "webm",
    "avi",
    "mp3",
    "ipod",
    "ogg",
    "opus",
    "flac",
    "wav",
)


def _probe_muxer(muxer: str, p: EngineProbe) -> None:
    """Measure one muxer's defaults + encodable codec sets (writes nothing)."""
    probe_file = Path(f"probe_probe.{muxer}")
    try:
        # format= is explicit: the muxer name must not be guessed from the
        # probe filename's extension (mkv's muxer is "matroska", "mpegts" has
        # no matching extension, ...).
        out = av.open(str(probe_file), "w", format=muxer)
    except Exception:
        return
    try:
        p.muxer_default_video[muxer] = str(getattr(out, "default_video_codec", "") or "")
        p.muxer_default_audio[muxer] = str(getattr(out, "default_audio_codec", "") or "")
        p.muxer_default_subtitle[muxer] = str(getattr(out, "default_subtitle_codec", "") or "")
        video_set: list[str] = []
        audio_set: list[str] = []
        for cand in {str(c) for c in (getattr(out, "supported_codecs", None) or set())}:
            if not _codec_mode_available(cand, "w"):
                continue
            try:
                kind = str(av.Codec(cand, "w").type or "")
            except Exception:
                continue
            if kind == "video":
                video_set.append(cand)
            elif kind == "audio":
                audio_set.append(cand)
        p.muxer_video_codecs[muxer] = sorted(video_set)
        p.muxer_audio_codecs[muxer] = sorted(audio_set)
    finally:
        with contextlib.suppress(Exception):
            out.close()
        with contextlib.suppress(OSError):
            probe_file.unlink(missing_ok=True)


def _measure() -> EngineProbe:
    """Run the full capability probe against the installed av."""
    global _ALL_CODECS
    p = EngineProbe(av_version=av.__version__)

    # ── codecs: EVERY name, split by mode, grouped into families ────────────
    p.codecs = _as_name_set(getattr(av.codec, "codecs_available", None))
    _ALL_CODECS = p.codecs
    p.codec_count = len(p.codecs)

    families: dict[str, list[str]] = {}
    long_names: dict[str, str] = {}
    labels: dict[str, str] = {}
    encoders: set[str] = set()
    decoders: set[str] = set()
    for name in sorted(p.codecs):
        # A codec may support BOTH modes (aac, png, mpeg4...): attempt each
        # mode independently — never classify by first success.
        w_ok = r_ok = False
        ref = None
        w_canonical = ""
        with contextlib.suppress(Exception):
            ref = av.codec.Codec(name, "w")
            w_ok = True
            # The wheel resolves aliases itself: Codec("h264","w").name is
            # "libx264". Canonical names keep the encoder set free of duplicate
            # aliases ("h264" decodes, libx264 encodes — same codec).
            w_canonical = str(ref.name or name)
        with contextlib.suppress(Exception):
            ref = av.codec.Codec(name, "r")
            r_ok = True
        if not w_ok and not r_ok:
            continue
        if w_ok:
            encoders.add(w_canonical)
        if r_ok:
            decoders.add(name)
        try:
            key = str(ref.id)
            families.setdefault(key, []).append(name)
            long_names[name] = str(ref.long_name or "")
        except Exception:
            families.setdefault(name, []).append(name)
    p.encoders = encoders
    p.decoders = decoders
    p.encoder_count = len(encoders)
    p.decoder_count = len(decoders)
    p.codec_families = {k: sorted(v) for k, v in sorted(families.items())}

    # Labels derive from the wheel: canonical long-name head of the family's
    # decoder + the family's display-preferred encoder. No hand-written keys.
    for members in p.codec_families.values():
        label = _derive_label(members)
        for member in members:
            labels[member] = label
    p.codec_long_names = long_names
    p.codec_labels = labels

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

    # ── format metadata (input/output/extensions) ───────────────────────────
    for name in sorted(p.formats):
        try:
            fmt = av.ContainerFormat(name)
        except Exception:
            continue
        try:
            p.format_meta[name] = {
                "is_input": bool(getattr(fmt, "is_input", False)),
                "is_output": bool(getattr(fmt, "is_output", False)),
                "extensions": list(getattr(fmt, "extensions", None) or []),
                "flags": int(getattr(fmt, "flags", 0) or 0),
                "long_name": str(getattr(fmt, "long_name", "") or ""),
            }
        except Exception:
            continue

    # ── per-encoder metadata + FULL option schema ───────────────────────────
    # This is measured for every verified encoder, not a preference list.
    for name in sorted(encoders):
        try:
            codec = av.Codec(name, "w")
        except Exception:
            continue
        if codec.video_formats:
            p.video_codec_formats[name] = [str(fmt.name) for fmt in codec.video_formats]
        if codec.audio_formats:
            p.audio_codec_formats[name] = [str(fmt.name) for fmt in codec.audio_formats]
        for rates in getattr(codec, "frame_rates", None) or []:
            p.encoder_frame_rates.setdefault(name, []).append(str(rates))
        arates = getattr(codec, "audio_rates", None) or []
        if arates:
            p.encoder_audio_rates[name] = [int(r) for r in arates]
        aforms = getattr(codec, "audio_formats", None) or []
        if aforms:
            p.encoder_audio_formats[name] = [str(getattr(f, "name", f)) for f in aforms]
        with contextlib.suppress(Exception):
            if bool(getattr(codec, "intra_only", False)):
                p.encoder_intra_only.append(name)
            if bool(getattr(codec, "lossless", False)):
                p.encoder_lossless.append(name)
        for hw in codec.hardware_configs or []:
            device = getattr(hw, "device_type", "unknown")
            fmt = getattr(hw, "format", None)
            p.hardware_configs.append(f"{name}:{device}:{getattr(fmt, 'name', 'any')}")
        try:
            ctx = av.CodecContext.create(name, "w")
            options = list(ctx.supported_options.generic) + list(ctx.supported_options.private)
            p.encoder_options[name] = sorted({str(o.name) for o in options})
            schema: list[dict] = []
            for o in options:
                schema.append(
                    {
                        "name": str(o.name),
                        "type": str(getattr(o, "type", "")),
                        "choices": [str(c) for c in (getattr(o, "choices", None) or [])],
                        "default": str(getattr(o, "default", "") or ""),
                        "min": getattr(o, "min", None),
                        "max": getattr(o, "max", None),
                        "help": str(getattr(o, "help", "") or ""),
                        "is_array": bool(getattr(o, "is_array", False)),
                    }
                )
            if schema:
                p.encoder_option_schema[name] = schema
        except Exception as exc:
            logger.debug("Encoder option probe failed for %s: %s", name, exc)

    # ── boot-tier muxer defaults (the common write targets) ────────────────
    for muxer in _BOOT_MUXERS:
        _probe_muxer(muxer, p)

    # Keep FFmpeg's native diagnostics visible in the app log instead of the
    # wheel's default discard callback.
    try:
        av.logging.set_level(av.logging.WARNING)
    except Exception as exc:
        p.notes.append(f"av logging setup unavailable: {exc}")

    # Hardware accel (may be empty on the mobile build — that is a result, not
    # a failure).
    try:
        p.hw_devices = _as_name_set(_hwdevices_available()) if _hwdevices_available else set()
        if not p.hw_devices:
            p.notes.append("hw accel: no devices detected — query per-encoder hardware_configs")
    except Exception as exc:
        p.notes.append(f"hwdevices_available failed: {exc}")

    # *_picks are the FULL verified encoder sets in stable display order.
    p.video_encoder_picks = _order_encoders(
        {n for n in encoders if str(av.codec.Codec(n, "w").type or "") == "video"}
    )
    p.audio_encoder_picks = _order_encoders(
        {n for n in encoders if str(av.codec.Codec(n, "w").type or "") == "audio"}
    )

    # Protocol probe: opening a URL on a dead port tells us whether the
    # protocol handler itself is compiled in (connection-level error) vs
    # missing (ProtocolNotFound-style error).
    for proto in PROTOCOLS:
        p.protocol_probe[proto] = probe_protocol(proto)

    p.notes.append("capability schema measured from this wheel; UI adapts to what is listed")
    return p


def _order_encoders(names: set[str]) -> list[str]:
    """Display order: preferred families first, then alphabetical."""
    ordered = [n for n in _ENCODER_DISPLAY_ORDER if n in names]
    ordered.extend(sorted(names - set(_ENCODER_DISPLAY_ORDER)))
    return ordered


def probe_protocol(proto: str) -> str:
    """'present' | 'missing' for one protocol handler (dead-port probe)."""
    port = "443" if proto == "https" else "9"
    url = f"{proto}://127.0.0.1:{port}/"
    # The dead-port open below ALWAYS emits native ERROR lines (connection
    # refused/timeout) on success paths too — that is the signal, not a
    # failure. Swallow them inside this probe window only (av.logging.Capture
    # verified empirically: native lines suppressed, exception still raised,
    # no global level change). Everything outside this function keeps full
    # native diagnostics.
    try:
        with av.logging.Capture():
            c = av.open(url, timeout=(1, 2))
            c.close()
        return "present"
    except Exception as exc:
        # Resolve the error names from the installed module instead of
        # assuming either spelling exists.
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
        return "present"  # network errors mean the protocol handler ran


# Back-compat alias: streams_screen imported the private name.
_probe_protocol = probe_protocol


def can_encode(name: str) -> bool:
    """True if the installed wheel can open ``name`` in encoder mode.

    Measures rather than assumes: ``_codec_mode_available`` constructs the
    Codec, which is the only check that distinguishes an encoder from a
    decoder-only name in ``codecs_available``.
    """
    probe()  # ensures _ALL_CODECS is populated for the mode check
    return _codec_mode_available(name, "w")


# ── lazy muxer matrix: EVERY output format, disk-cached, off-boot ───────────

_MUXER_MEM: dict | None = None


def _muxer_cache_path() -> Path:
    return get_cache_dir() / f"engine_muxer_matrix_{av.__version__}_{_ffmpeg_build_identity()}.json"


def muxer_matrix() -> dict[str, dict]:
    """Full output-format matrix: muxer → {defaults, encodable video/audio sets}.

    Lazy tier: probed on first use (Convert/Join/Extract), off the UI thread,
    memoized in RAM and cached on disk keyed on the FFmpeg build identity.
    """
    global _MUXER_MEM
    if _MUXER_MEM is not None:
        return _MUXER_MEM
    p = probe()
    path = _muxer_cache_path()
    try:
        if path.is_file():
            _MUXER_MEM = json.loads(path.read_text(encoding="utf-8"))
            return _MUXER_MEM
    except Exception as exc:
        logger.warning("Muxer matrix cache unreadable — re-measuring: %s", exc)

    matrix: dict[str, dict] = {}
    for name in sorted(p.formats):
        meta = p.format_meta.get(name) or {}
        if not meta.get("is_output"):
            continue
        entry = {
            "default_video": p.muxer_default_video.get(name, ""),
            "default_audio": p.muxer_default_audio.get(name, ""),
            "default_subtitle": p.muxer_default_subtitle.get(name, ""),
            "video": p.muxer_video_codecs.get(name, []),
            "audio": p.muxer_audio_codecs.get(name, []),
            "extensions": meta.get("extensions", []),
            "long_name": meta.get("long_name", ""),
        }
        if entry["video"] or entry["default_video"]:
            matrix[name] = entry
        elif name not in p.muxer_default_video:
            # Not covered by the boot tier: probe it now (one temp file).
            sub = EngineProbe()
            _probe_muxer(name, sub)
            entry["default_video"] = sub.muxer_default_video.get(name, "")
            entry["default_audio"] = sub.muxer_default_audio.get(name, "")
            entry["default_subtitle"] = sub.muxer_default_subtitle.get(name, "")
            entry["video"] = sub.muxer_video_codecs.get(name, [])
            entry["audio"] = sub.muxer_audio_codecs.get(name, [])
            if entry["video"] or entry["default_video"]:
                matrix[name] = entry
    _MUXER_MEM = matrix
    try:
        path.write_text(json.dumps(matrix, indent=1), encoding="utf-8")
    except Exception as exc:
        logger.warning("Muxer matrix cache write failed: %s", exc)
    return matrix


def muxers_for_container(container: str) -> list[dict]:
    """Output-muxer entries matching a container name or file extension.

    Derived resolution: "mp4" matches the mp4 muxer by name, "mkv" matches
    matroska via its extensions, "m4a" matches ipod. Returns every match —
    callers fail closed when the list is empty.
    """
    want = container.lower().lstrip(".")
    matches: list[dict] = []
    for name, entry in muxer_matrix().items():
        if name.lower() == want:
            matches.append({"muxer": name, **entry})
            continue
        exts = {e.lower().lstrip(".") for e in entry.get("extensions", [])}
        if want in exts:
            matches.append({"muxer": name, **entry})
    # Ranking: exact name match first, then the most specific extension list
    # (the mov family muxers all list the whole family's extensions, but only
    # ipod is "the" m4a writer), then default-audio encodability.
    matches.sort(
        key=lambda m: (
            m["muxer"].lower() != want,
            len(m.get("extensions", [])),
        )
    )
    return matches


def can_encode_format(fmt: str) -> bool:
    """True if the installed wheel can produce this container/extension.

    Derived: the extension maps to output muxers via ContainerFormat
    extensions, and one of the muxer's audio codecs (default or supported)
    must be encodable.
    """
    p = probe()
    want = fmt.lower().lstrip(".")
    matrix = muxer_matrix()
    for name, entry in matrix.items():
        exts = {e.lower().lstrip(".") for e in entry.get("extensions", [])}
        if want not in exts and want != name.lower():
            continue
        candidates = [c for c in (entry.get("default_audio"), *entry.get("audio", [])) if c]
        if any(_codec_mode_available(c, "w") for c in candidates):
            return True
        # Video-only muxer whose default video codec is encodable also counts
        # for formats like gif.
        if any(_codec_mode_available(c, "w") for c in (entry.get("default_video"),) if c):
            return True
    return False


def codec_family(name: str) -> list[str]:
    """Every codec name sharing `name`'s AVCodecID (decoder + encoders)."""
    p = probe()
    for members in p.codec_families.values():
        if name in members:
            return members
    return [name]


def codec_label(name: str) -> str:
    """Derived display label (long-name head + external encoder name)."""
    p = probe()
    return p.codec_labels.get(name) or p.codec_long_names.get(name) or name


def format_is_lossless(fmt: str) -> bool:
    """True when the container's default audio codec encodes losslessly.

    Derived from the muxer matrix + Codec.lossless (wav -> pcm_s16le, flac ->
    flac; lossy containers like mp3/aac/opus are False).
    """
    p = probe()
    for entry in muxers_for_container(fmt):
        default = entry.get("default_audio") or ""
        if default and default in p.encoder_lossless:
            return True
        if default:
            return False
    return False


def containers_for_kind(kind: str) -> list[dict]:
    """Output containers classified by media kind, derived from the wheel.

    audio: no real default video codec (FFmpeg reports the placeholder
    "none"/"wrapped_avframe" on audio muxers) and an encodable default audio
    codec. video: a real, encodable default video codec. Still-image
    containers are NOT derivable — av does not tag still-image muxers and
    intra-only video codecs (dnxhd, dv) are not still images — so the image
    list stays the app's explicit trio.
    """
    still = _still_image_codecs()
    placeholders = {"", "none", "wrapped_avframe"}
    seen: dict[str, dict] = {}
    for name, entry in muxer_matrix().items():
        default_v = entry.get("default_video") or ""
        default_a = entry.get("default_audio") or ""
        video_ok = (
            bool(default_v)
            and default_v.lower() not in placeholders
            and (
                _codec_mode_available(default_v, "w")
                or any(_codec_mode_available(c, "w") for c in entry.get("video", []))
            )
        )
        audio_ok = bool(default_a) and _codec_mode_available(default_a, "w")
        if kind == "audio":
            if video_ok or not audio_ok:
                continue
        elif kind == "video":
            if not video_ok:
                continue
            if default_v in still:
                # Intra-only defaults (png/gif writers AND dnxhd/dv) are
                # handled by the explicit image trio / excluded here.
                continue
        else:
            continue
        exts = [e.lower() for e in entry.get("extensions", []) if e]
        key = name if name.lower() in exts else (exts[0] if exts else name)
        seen.setdefault(
            key,
            {
                "container": key,
                "muxer": name,
                "extensions": exts,
                "label": (entry.get("long_name") or name).split(" (")[0],
            },
        )
    return list(seen.values())


def _still_image_codecs() -> set[str]:
    """Encoders whose output is a still image: intra-only video encoders."""
    p = probe()
    return {n for n in p.encoder_intra_only}


def container_label(container: str) -> str:
    """Derived display label for a container/muxer name."""
    for entry in muxers_for_container(container):
        long = entry.get("long_name") or ""
        if long:
            return long.split(" (")[0]
        return entry["muxer"]
    return container


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

    encoder = "libx264" if _codec_mode_available("libx264", "w") else "mpeg4"
    if encoder == "mpeg4" and not _codec_mode_available("mpeg4", "w"):
        # Plain ValueError (not EngineCapabilityError — that lives in
        # engine_service, which imports this module): same contract, the
        # message names the missing capability instead of leaking
        # UnknownCodecError.
        raise ValueError("This FFmpeg build has no usable video encoder")
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
