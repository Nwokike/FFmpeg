"""Classic ``ffmpeg`` command lines onto the engine's existing ops (no binary).

The app ships the FFmpeg *libraries* inside the PyAV wheel — there is no
``ffmpeg.exe`` to exec. This module translates the CLI surface people actually
type (``-i``, ``-ss/-t/-to``, ``-c:v/-crf/-preset``, ``-vn``, ``-vf`` subset…)
into the exact ``op + params`` shape ``main._job_runner`` dispatches. Anything
unmappable is REFUSED loudly (``CommandError`` + ``logger.warning``) — command
mode never silently drops a flag. Approximations that do map imperfectly are
returned in ``notes`` and shown in the terminal before the job is confirmed.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

logger = logging.getLogger("CommandParser")

AUDIO_EXTS = {".mp3", ".aac", ".m4a", ".flac", ".opus", ".ogg", ".wav"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".flv", ".m4v", ".gif"}
# Flags taking no value — matched EXACTLY before any prefix scan, so -vn can
# never be misread as "-v n" (the attached-value fallback below is prefix-based
# and "-vn" startswith "-v").
NO_ARG_FLAGS = {"-y", "-hide_banner", "-nostdin", "-vn", "-an", "-sn"}
# Display-only / ignored-with-note flags: value consumed, behavior unchanged.
VALUE_FLAGS = {
    "-i",
    "-ss",
    "-t",
    "-to",
    "-c",
    "-c:v",
    "-vcodec",
    "-c:a",
    "-acodec",
    "-b:v",
    "-b:a",
    "-ar",
    "-ac",
    "-r",
    "-s",
    "-f",
    "-vf",
    "-af",
    "-crf",
    "-preset",
    "-pix_fmt",
    "-loglevel",
    "-v",
}
# Recognised but deliberately unsupported — refused with a specific message.
REFUSED_FLAGS = {
    "-filter_complex": "build the chain with -vf/-af instead",
    "-map": "stream selection is the Dossier/Remux screen's job",
    "-metadata": "metadata editing is not available in command mode",
    "-sslide": "subtitle stream selection is not available in command mode — the Dossier screen lists tracks",
}
ENCODER_PRESETS = {
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
}


class CommandError(ValueError):
    """A command the engine cannot honestly run — surfaced verbatim to the user."""


def _refuse(msg: str) -> NoReturn:
    logger.warning("Command refused: %s", msg)
    raise CommandError(msg)


@dataclass
class OpPlan:
    """A validated job waiting for confirmation in the terminal UI."""

    op: str
    input_path: str
    output_path: str
    params: dict
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        kv = ", ".join(f"{k}={v!r}" for k, v in sorted(self.params.items()))
        return f"op={self.op} in={self.input_path} out={self.output_path}" + (
            f" [{kv}]" if kv else ""
        )


def tokenize(command: str) -> list[str]:
    """Split on whitespace, honour quotes, NEVER mangle backslash paths.

    ``shlex`` in POSIX mode eats ``C:\\media\\in.mp4`` backslashes — this
    tokenizer keeps every byte inside quotes, only stripping the quotes.
    Empty quoted strings (``-i ""``) are refused, not silently bound to the
    next token; backslash escapes are NOT processed (documented: quote the
    whole path instead of escaping characters).
    """
    tokens: list[str] = []
    buf: list[str] = []
    buf_has_content = False
    quote: str | None = None
    for ch in command.strip():
        if quote:
            if ch == quote:
                quote = None
                buf_has_content = True
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if buf or buf_has_content:
                if not buf and buf_has_content:
                    _refuse("empty quoted string is not a valid path or value")
                tokens.append("".join(buf))
                buf = []
                buf_has_content = False
        else:
            buf.append(ch)
    if quote:
        _refuse(f"unterminated {quote} quote in command")
    if buf or buf_has_content:
        if not buf and buf_has_content:
            _refuse("empty quoted string is not a valid path or value")
        tokens.append("".join(buf))
    return tokens


def _parse_ts(value: str, flag: str) -> float:
    """``HH:MM:SS(.ms)`` | ``MM:SS`` | plain seconds → seconds."""
    bad = f"{flag} expects a timestamp (12, 1:02, or 00:01:02.5), got {value!r}"
    secs: float | None = None
    if ":" in value:
        parts = value.split(":")
        if len(parts) > 3:
            _refuse(bad)
        try:
            secs = 0.0
            for p in parts:
                secs = secs * 60 + float(p)
        except ValueError:
            _refuse(bad)
    else:
        try:
            secs = float(value)
        except ValueError:
            _refuse(bad)
    assert secs is not None  # _refuse always raises on every failure above
    if not math.isfinite(secs) or secs < 0:
        _refuse(f"{flag} expects a finite timestamp >= 0, got {value!r}")
    return secs


def _parse_size(value: str, flag: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{2,5})x(\d{2,5})", value)
    if not m:
        _refuse(f"{flag} expects WIDTHxHEIGHT (e.g. 1280x720), got {value!r}")
    return int(m.group(1)), int(m.group(2))


def _parse_bitrate_kbps(value: str, flag: str) -> int:
    m = re.fullmatch(r"(\d+)([kKmM])?", value)
    if not m:
        _refuse(f"{flag} expects a bitrate like 128k, got {value!r}")
    n = int(m.group(1))
    unit = (m.group(2) or "").lower()
    return n * 1000 if unit == "m" else n


def _parse_vf(vf: str, params: dict, notes: list[str]) -> None:
    """Verified filter subset → convert params; anything else is refused."""
    for part in vf.split(","):
        part = part.strip()
        if not part:
            continue
        name, _, args = part.partition("=")
        name = name.strip()
        arg_list = [a.strip() for a in args.split(":")] if args else []
        if name == "scale":
            m_scale = re.fullmatch(r"(\d{2,5}):(\d{2,5})", args)
            if not m_scale:
                _refuse(f"-vf scale expects W:H (e.g. 1280:720), got {part!r}")
            params["scale_width"] = int(m_scale[1])
            params["scale_height"] = int(m_scale[2])
        elif name == "fps":
            try:
                params["fps"] = round(float(arg_list[0]))
            except (ValueError, IndexError):
                _refuse(f"-vf fps expects a number, got {part!r}")
        elif name == "crop":
            # ffmpeg's crop is a PIXEL-REGION cut; the engine's crop is an
            # ASPECT crop (different semantics). Refuse rather than lie.
            _refuse(
                "-vf crop extracts a pixel region — the engine crops by aspect "
                "instead; use the Filters screen or -vf scale=W:H"
            )
        elif name == "transpose":
            # ffmpeg transpose: 0 = 90deg CCW, 1 = 90deg CW, 2 = 90deg CCW + flip,
            # 3 = 90deg CW + flip; clock/cclock are the named equivalents. The
            # engine rotates by right angles only (flips need the Filters
            # screen), so 2/3 map to their rotation with an honest note.
            raw = (arg_list[0].split(";")[0] if arg_list else "").strip().lower()
            named = {"clock": 90, "cclock": 270}
            deg = named[raw] if raw in named else {"0": 270, "1": 90, "2": 270, "3": 90}.get(raw)
            if deg is None:
                _refuse(f"-vf transpose expects 0-3 (or clock/cclock), got {part!r}")
            params["rotation"] = (params.get("rotation", 0) + deg) % 360
            notes.append(
                "transpose approximated as rotation (flip component needs the Filters screen)"
            )
        elif name in ("hflip", "vflip"):
            _refuse(f"-vf {name} is not available in command mode — use the Filters screen")
        elif name == "atempo":
            _refuse(
                "-vf atempo is an AUDIO filter — real ffmpeg rejects it in -vf too; "
                "use -af atempo=FACTOR instead"
            )
        elif name == "eq":
            eq = params.setdefault("eq", {})
            for kv in arg_list:
                k, _, v = kv.partition("=")
                try:
                    eq[k.strip()] = float(v)
                except ValueError:
                    _refuse(f"-vf eq expects key=value numbers, got {kv!r}")
            notes.append("eq applied where the engine build supports the filter")
        elif name == "hqdn3d":
            # Engine levels: "off", "low" (gentle 3:2:6:4), anything else
            # strong — pick the gentle end, never overshoot silently.
            params["denoise"] = "low"
            notes.append("hqdn3d mapped to the engine's low denoise")
        elif name == "unsharp":
            params["sharpen"] = 1
            notes.append("unsharp mapped to engine sharpen")
        else:
            _refuse(f"-vf filter {name!r} is not available in command mode")


def _parse_af(af: str, params: dict, notes: list[str]) -> None:
    for part in af.split(","):
        part = part.strip()
        if not part:
            continue
        name, _, args = part.partition("=")
        name = name.strip()
        if name == "atempo":
            try:
                params["speed"] = round(params.get("speed", 1.0) * float(args), 4)
            except ValueError:
                _refuse(f"-af atempo expects a factor, got {part!r}")
        elif name == "loudnorm":
            m = re.search(r"I=(-?\d+(?:\.\d+)?)", args)
            params["target_lufs"] = float(m.group(1)) if m else -16.0
            notes.append("loudnorm run as the engine's two-pass master")
        elif name in ("volume",):
            # ffmpeg volume takes a linear factor (1.5 = 150%) or dB with a
            # dB suffix (6dB approx 2x). The engine wants percent: linear x 100,
            # dB to 10^(dB/20) x 100. rstrip("dB") would strip a CHARACTER SET, not
            # a suffix — strip exact suffixes only.
            raw_arg = args.strip()
            try:
                if raw_arg.lower().endswith("db"):
                    pct = (10 ** (float(raw_arg[:-2]) / 20.0)) * 100.0
                else:
                    pct = float(raw_arg) * 100.0
                params["volume_pct"] = max(1, min(400, round(pct)))
            except ValueError:
                _refuse(f"-af volume expects e.g. 1.5 (=150%) or 6dB, got {part!r}")
        else:
            _refuse(f"-af filter {name!r} is not available in command mode")


def _map_video_codec(raw: str, params: dict, notes: list[str]) -> None:
    if raw == "copy":
        notes.append("-c:v copy inside a transcode is not possible — video re-encoded")
        return
    codec = {"h264": "libx264", "x264": "libx264", "hevc": "libx265", "x265": "libx265"}.get(
        raw, raw
    )
    params["video_codec"] = codec


def parse_command(
    command: str,
    *,
    duration_s: float | None = None,
    check_exist: bool = True,
) -> OpPlan:
    """Translate one ``ffmpeg …`` line into an :class:`OpPlan`.

    ``duration_s`` (probed by the caller from the first input) resolves an
    ``-ss`` with no ``-t``/``-to`` into a cut-to-end. Raises :class:`CommandError`
    for anything the engine cannot honestly honour.
    """
    tokens = tokenize(command)
    if tokens and tokens[0].lower() in ("ffmpeg", "ffmpeg.exe"):
        tokens = tokens[1:]
    if not tokens:
        _refuse("empty command — type ffmpeg -i input output (see ffmpeg -h)")
    if tokens[0].lower() in ("ffprobe", "ffprobe.exe"):
        _refuse("ffprobe is not supported here — open the Dossier screen for probes")

    inputs: list[str] = []
    flags: dict[str, str] = {}
    stream_flags: set[str] = set()  # -vn/-an/-sn presence (no values to store)
    positionals: list[str] = []
    notes: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in NO_ARG_FLAGS:
            # -vn/-an/-sn must be VISIBLE downstream — skipping them here is
            # what made `drop_video` permanently False.
            if tok in ("-vn", "-an", "-sn"):
                stream_flags.add(tok)
            i += 1
            continue
        if tok.startswith("-"):
            name = tok
            if name in REFUSED_FLAGS:
                _refuse(f"{name} is not supported in command mode — {REFUSED_FLAGS[name]}")
            if name not in VALUE_FLAGS:
                # attached-value form: -crf23 / -presetfast. NO_ARG_FLAGS was
                # already exact-matched above, so -vn/-an/-sn never reach this
                # prefix scan (that was the "-vn parsed as -v n" bug).
                attached = next(
                    (
                        f
                        for f in sorted(VALUE_FLAGS, key=len, reverse=True)
                        if tok.startswith(f) and len(tok) > len(f)
                    ),
                    None,
                )
                if attached is None:
                    _refuse(
                        f"unsupported flag {name!r} — command mode covers the common "
                        "surface (see ffmpeg -h for what's listed)"
                    )
                name, value = attached, tok[len(attached) :]
            else:
                if i + 1 >= len(tokens):
                    _refuse(f"{name} expects a value")
                value = tokens[i + 1]
                i += 1
            if name == "-i":
                inputs.append(value)
            else:
                # Duplicates are refused, not last-wins: silently keeping the
                # last -ss/-vf/-crf while dropping the first violates the
                # never-silently-drops contract. (-i accumulates by design.)
                if name in flags:
                    _refuse(
                        f"duplicate {name} ({flags[name]!r}, then {value!r}) — "
                        "run one command per value instead"
                    )
                flags[name] = value
            i += 1
            continue
        positionals.append(tok)
        i += 1

    if not inputs:
        _refuse("no input — add -i <file>")
    if len(positionals) == 0:
        _refuse("no output file — the last argument must be the output path")
    if len(positionals) > 1:
        _refuse(f"multiple outputs are not supported (got {positionals[1:]})")
    output = positionals[0]

    if check_exist:
        missing = [p for p in inputs if not Path(p).exists()]
        if missing:
            _refuse("input file(s) not found: " + ", ".join(missing))

    # The engine would clobber the input — refuse before anything is opened.
    try:
        if any(Path(src).resolve() == Path(output).resolve() for src in inputs):
            _refuse(f"input and output are the same file ({output}) — pick another output name")
    except OSError:
        pass

    out_ext = Path(output).suffix.lower()

    # ── display-only acceptances ─────────────────────────────────────────
    for f in ("-loglevel", "-v", "-pix_fmt"):
        if f in flags:
            if f == "-pix_fmt" and flags[f] != "yuv420p":
                _refuse(f"-pix_fmt {flags[f]} is fixed by the engine's encoders")
            notes.append(f"{f} {flags[f]} accepted (display/engine-managed)")

    params: dict = {}

    # ── multi-input → concat ─────────────────────────────────────────────
    if len(inputs) > 1:
        # A join takes paths + container only. Anything else on the line
        # (-ss/-vf/-crf/-c…) would be silently discarded, so refuse loudly.
        shaping = sorted(
            name
            for name in flags
            if name
            not in (
                "-i",
                "-f",
                "-loglevel",
                "-v",
                "-pix_fmt",
                "-y",
                "-hide_banner",
                "-nostdin",
            )
        )
        if shaping:
            _refuse(
                f"joining {len(inputs)} inputs takes no per-clip flags — "
                f"these would be ignored: {', '.join(shaping)}"
            )
        return OpPlan(
            op="concat",
            input_path=inputs[0],
            output_path=output,
            params={
                "paths": inputs,
                "container": out_ext.lstrip(".") or "mp4",
                "transition": "cut",
            },
            notes=[*notes, f"joining {len(inputs)} inputs (lossless cut transition)"],
        )

    src = inputs[0]

    # ── filter flags → convert params ────────────────────────────────────
    if "-vf" in flags:
        _parse_vf(flags["-vf"], params, notes)
    if "-af" in flags:
        _parse_af(flags["-af"], params, notes)
    if "-crf" in flags:
        try:
            params["crf"] = max(0, min(51, int(flags["-crf"])))
        except ValueError:
            _refuse(f"-crf expects 0-51, got {flags['-crf']!r}")
    if "-preset" in flags:
        if flags["-preset"] not in ENCODER_PRESETS:
            _refuse(f"unknown -preset {flags['-preset']!r}")
        params["preset"] = flags["-preset"]
    if "-c:v" in flags or "-vcodec" in flags:
        _map_video_codec(flags.get("-c:v") or flags.get("-vcodec", ""), params, notes)
    if "-r" in flags:
        try:
            params["fps"] = round(float(flags["-r"]))
        except ValueError:
            _refuse(f"-r expects a frame rate (24, 25, 29.97…), got {flags['-r']!r}")
    if "-s" in flags:
        w, h = _parse_size(flags["-s"], "-s")
        params["scale_width"], params["scale_height"] = w, h
    if "-f" in flags:
        alias = {"matroska": "mkv", "ipod": "m4a"}
        want = flags["-f"].lstrip(".").lower()
        want = alias.get(want, want)
        if want != out_ext.lstrip("."):
            _refuse(f"-f {flags['-f']} conflicts with the output extension {out_ext or '(none)'}")
        notes.append(f"container {want} via output extension")
    if "-b:v" in flags:
        _parse_bitrate_kbps(flags["-b:v"], "-b:v")
        notes.append("average bitrate (-b:v) is approximated — the engine transcodes with CRF")

    # ── audio-extract shaping ────────────────────────────────────────────
    audio_params: dict = {}
    if "-b:a" in flags:
        audio_params["bitrate_kbps"] = _parse_bitrate_kbps(flags["-b:a"], "-b:a")
    if "-ar" in flags:
        try:
            audio_params["sample_rate"] = int(flags["-ar"])
        except ValueError:
            _refuse(f"-ar expects a sample rate (44100…), got {flags['-ar']!r}")
    if "-ac" in flags:
        try:
            audio_params["channels"] = int(flags["-ac"])
        except ValueError:
            _refuse(f"-ac expects a channel count, got {flags['-ac']!r}")
    audio_codec = flags.get("-c:a") or flags.get("-acodec", "")

    # ── time ranges → cut ────────────────────────────────────────────────
    start = _parse_ts(flags["-ss"], "-ss") if "-ss" in flags else None
    if "-t" in flags and "-to" in flags:
        notes.append("both -t and -to given — -t (duration) wins")
    if "-t" in flags:
        end = (start or 0.0) + _parse_ts(flags["-t"], "-t")
    elif "-to" in flags:
        end = _parse_ts(flags["-to"], "-to")
    else:
        end = None

    # Anything that forces pixels through the encoder — including the codec
    # itself, audio shaping, and every codec-carrying -vf node — means this
    # is a re-encode. Default is re-encode (like real ffmpeg); only an
    # explicit `-c copy` with NO encode flags takes the copy path.
    # NOTE: `-c:v copy` / `-c:a copy` request NO re-encode, so copy-valued
    # codec flags are excluded from the encode set (they gate remux below).
    def _codec_flag_requests_encode(name: str) -> bool:
        return name in ("-c:v", "-vcodec", "-c:a", "-acodec") and flags.get(name) != "copy"

    _ENCODE_VF_NODES = ("transpose", "eq", "hqdn3d", "unsharp")
    vf_text = flags.get("-vf", "")
    has_encode_flags = (
        any(k in params for k in ("crf", "preset", "fps", "video_codec"))
        or bool(params.get("scale_width"))
        or "-vf" in flags
        or "-af" in flags
        or any(k in params for k in ("speed", "volume_pct", "target_lufs"))
        or "-r" in flags
        or "-s" in flags
        or "-b:v" in flags
        or "-b:a" in flags
        or "-ar" in flags
        or "-ac" in flags
        or any(_codec_flag_requests_encode(name) for name in flags)
        or any(node in vf_text for node in _ENCODE_VF_NODES)
    )

    # Output-extension routing wins over time-range routing: a gif/subtitle/
    # audio TARGET with -ss still produces that artifact — cutting INTO .mp3/
    # .gif would hand the engine an impossible container/codec pair.
    if (start is not None or end is not None) and out_ext not in (
        SUBTITLE_EXTS | AUDIO_EXTS | {".gif"}
    ):
        if end is None:
            if duration_s is None:
                _refuse(
                    "-ss without -t/-to needs a probed duration — the terminal "
                    "probes the input first; if this reached you the probe failed"
                )
            end = duration_s
        if start is None:
            start = 0.0
        if end <= start:
            _refuse(f"empty range: start {start}s >= end {end}s")
        # Explicit `-c copy` with no encode flags: lossless trim. Everything
        # else re-encodes (real ffmpeg's default) — and a -crf/-preset that
        # forced the re-encode is CARRIED into params, never dropped.
        copy = flags.get("-c", "") == "copy" and not has_encode_flags
        if "-c" in flags and flags["-c"] != "copy":
            _map_video_codec(flags["-c"], params, notes)
            copy = False
        cut_params: dict = {
            "start_seconds": float(start),
            "end_seconds": float(end),
            "stream_copy": bool(copy),
        }
        if not copy:
            notes.append("frame-accurate re-encode trim")
            for key in ("crf", "preset"):
                if key in params:
                    cut_params[key] = params[key]
        else:
            notes.append("stream copy — lossless, bit-exact trim")
        return OpPlan(
            op="cut",
            input_path=src,
            output_path=output,
            params=cut_params,
            notes=notes,
        )

    # ── pure stream copy (no time range) → remux ─────────────────────────
    # `-c copy`, `-c:v copy`, and `-c:a copy` all mean "don't re-encode".
    copy_requested = (
        flags.get("-c") == "copy"
        or flags.get("-c:v") == "copy"
        or flags.get("-vcodec") == "copy"
        or flags.get("-c:a") == "copy"
        or flags.get("-acodec") == "copy"
    )
    if copy_requested and not has_encode_flags and out_ext not in AUDIO_EXTS:
        if out_ext != ".mkv":
            _refuse(
                "lossless -c copy remuxes to Matroska in this engine — "
                "name the output .mkv or drop -c copy to transcode"
            )
        return OpPlan(
            op="remux",
            input_path=src,
            output_path=output,
            params={"drop": []},
            notes=[*notes, "lossless stream copy into .mkv"],
        )

    # ── audio-only extraction ────────────────────────────────────────────
    drop_video = "-vn" in stream_flags
    if drop_video or out_ext in AUDIO_EXTS:
        fmt = out_ext.lstrip(".") or "mp3"
        if fmt not in ("mp3", "aac", "m4a", "flac", "opus", "ogg", "wav"):
            _refuse(
                f"-vn with {out_ext or 'no'} output extension — name an audio "
                "output (.mp3 .m4a .flac .opus .ogg .wav)"
            )
        merged = {"format_name": fmt, **audio_params}
        if "target_lufs" in params:
            merged["target_lufs"] = params.pop("target_lufs")
        # Every shaping key the extractor cannot consume must refuse — a
        # dropped -vf scale would hand back the full track while the user
        # believes it was shaped.
        shaping_keys = (
            "speed",
            "volume_pct",
            "scale_width",
            "scale_height",
            "fps",
            "rotation",
            "crf",
            "preset",
            "video_codec",
            "denoise",
            "sharpen",
            "eq",
        )
        dropped_shaping = sorted(k for k in shaping_keys if k in params)
        if dropped_shaping:
            _refuse(
                f"shaping ({', '.join(dropped_shaping)}) cannot ride an extraction — "
                "use a video output, or the Audio Studio screen for volume/speed/loudness"
            )
        if audio_codec and audio_codec != "copy":
            codec_fmt = {
                "libmp3lame": "mp3",
                "mp3": "mp3",
                "aac": "aac",
                "flac": "flac",
                "libopus": "opus",
                "opus": "opus",
                "vorbis": "ogg",
                "libvorbis": "ogg",
                "pcm_s16le": "wav",
                "pcm_s24le": "wav",
                "alac": "m4a",
            }.get(audio_codec)
            if codec_fmt:
                merged["format_name"] = codec_fmt
            else:
                _refuse(f"-c:a {audio_codec!r} is not an extractable audio format")
        elif audio_codec == "copy":
            _refuse("-c:a copy with -vn would need a container remux, not an extract")
        if start is not None or end is not None:
            _refuse(
                "time ranges need a cut first — extraction covers the full track; "
                "trim to a file, then extract from the trim"
            )
        return OpPlan(
            op="extract_audio",
            input_path=src,
            output_path=output,
            params=merged,
            notes=notes,
        )

    # ── subtitle extraction ──────────────────────────────────────────────
    if out_ext in SUBTITLE_EXTS:
        if start is not None or end is not None:
            _refuse(
                "time ranges need a cut first — subtitle extraction covers the full "
                "track; trim to a file, then extract from the trim"
            )
        return OpPlan(
            op="extract_subtitles",
            input_path=src,
            output_path=output,
            params={"format_name": out_ext.lstrip("."), "stream_index": 0},
            notes=notes,
        )

    # ── GIF ──────────────────────────────────────────────────────────────
    if out_ext == ".gif":
        gif_params = {
            "fps": params.get("fps", 15),
            "width": params.get("scale_width", 480),
            "start_s": float(start) if start is not None else 0.0,
            "duration_s": float(end - start)
            if (start is not None and end is not None)
            else (float(duration_s - (start or 0.0)) if duration_s else 5.0),
        }
        if start is None and end is None and not duration_s:
            notes.append("no range given — first 5s becomes the GIF (pass -ss/-t to choose)")
        return OpPlan(
            op="create_gif",
            input_path=src,
            output_path=output,
            params=gif_params,
            notes=notes,
        )

    # ── default: convert ─────────────────────────────────────────────────
    if audio_codec and audio_codec not in ("aac", "copy", "libmp3lame"):
        params["audio_codec"] = audio_codec
    elif audio_codec == "copy":
        notes.append("-c:a copy inside a transcode is not possible — audio re-encoded")
    if "target_lufs" in params:
        _refuse(
            "-af loudnorm targets mastered audio — use the Audio Studio screen "
            "(a video convert has no loudness slot to put it in)"
        )
    if "-c" in flags and flags["-c"] not in ("copy", ""):
        # A bare `-c <codec>` that survived the cut branch (no time range):
        # treat it as the video codec rather than dropping it.
        _map_video_codec(flags["-c"], params, notes)
    if drop_video and out_ext in VIDEO_EXTS:
        _refuse("-vn with a video output extension — name an audio extension instead")
    return OpPlan(
        op="convert",
        input_path=src,
        output_path=output,
        params=params,
        notes=notes,
    )


def help_text() -> str:
    """What command mode accepts — rendered as the terminal's ``ffmpeg -h``."""
    return "\n".join(
        [
            "ffmpeg command mode — FFmpeg libraries via PyAV (no binary)",
            "",
            "inputs     -i <file>            (2+ inputs → join, flags refused)",
            "trim       -ss <ts> [-t <dur> | -to <ts>]  (re-encodes; + -c copy = lossless)",
            "convert    -c:v libx264|libx265 -crf 0-51 -preset <name>",
            "audio out  -vn / .mp3 .m4a .flac .opus .ogg .wav out",
            "             -b:a 128k -ar 44100 -ac 2",
            "filters     -vf scale,fps,transpose,eq,hqdn3d,unsharp",
            "             -af atempo,loudnorm,volume",
            "lossless   -c copy out.mkv     (remux; -c:v/-c:a copy honoured)",
            "gif        out.gif  [-ss -t | -to] [-r]",
            "subs       out.srt|vtt|ass",
            "",
            "refused loudly (never silently): -filter_complex, -map, -metadata,",
            "-sslide, hflip/vflip, -vf crop/atempo, duplicates, shaping on",
            "extracts, time-boxed extracts, input==output. Probes via Dossier.",
        ]
    )
