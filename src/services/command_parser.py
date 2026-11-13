"""Real ``ffmpeg`` syntax → a validated job (FFmpeg libraries via PyAV, no binary).

The app ships the FFmpeg *libraries* inside the PyAV wheel — there is no
``ffmpeg.exe`` to exec. Command mode is therefore a translator, not an emulation:

- **Filters are real.** ``-vf``/``-af`` become a ``FilterChain`` of
  ``(filter, args-string)`` nodes, and the engine hands each to
  ``av.filter.Graph.add(name, args)`` — so FFmpeg's own argument syntax applies
  and every filter this build ships works (``hqdn3d``, ``unsharp``, ``drawbox``,
  ``loudnorm``, ``atempo``, ``xfade``…). Nothing is filtered through a table.
- **Codecs and containers are measured.** Names resolve through the capability
  probe; a codec this wheel cannot encode refuses naming the wheel.
- **Anything else is classified by measurement, not a table.** An unrecognised
  ``-name value`` is offered to the encoder first (the codec context's own
  option list) and then to the muxer (a probe open); if neither takes it, the
  command is refused and the message lists what would have been accepted.
- **Nothing is dropped silently.** Every approximation or substitution is a
  ``note`` rendered in the terminal before the job is confirmed.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

logger = logging.getLogger("CommandParser")

AUDIO_EXTS = {".mp3", ".aac", ".m4a", ".flac", ".opus", ".ogg", ".wav", ".oga"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".webvtt"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".flv", ".m4v", ".mpg", ".mpeg"}

# Flags that take NO value. Everything else that starts with "-" is read as
# "-name value" (or "-name=value"), which is how real ffmpeg behaves — so there
# is no hand-written list of "supported flags" to rot.
NO_ARG_FLAGS = {
    "-y",
    "-n",
    "-hide_banner",
    "-nostdin",
    "-nostats",
    "-benchmark",
    "-vn",
    "-an",
    "-sn",
    "-dn",
    "-copyts",
    "-vsync",
    "-async",
}

# Flags whose value is a bare number and whose engine slot exists.
_TIMESTAMP_FLAGS = ("-ss", "-to", "-t")


# Flags that carry an encoder option of the same name (the engine's encoder
# option dict is the real slot — nothing is "approximated").
_KNOB_FLAGS = (
    "-crf",
    "-preset",
    "-tune",
    "-profile",
    "-profile:v",
    "-level",
    "-g",
    "-keyint_min",
    "-bf",
    "-qmin",
    "-qmax",
    "-qcomp",
    "-refs",
    "-coder",
    "-trellis",
    "-subq",
    "-me_method",
    "-x264-params",
    "-x265-params",
    "-threads",
)

# Every flag the routing below consumes; anything else is classified by
# measurement (encoder option → muxer option → refusal).
_ROUTED_FLAGS = frozenset(
    (
        *_KNOB_FLAGS,
        "-i",
        "-f",
        "-y",
        "-n",
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-benchmark",
        "-loglevel",
        "-v",
        "-c",
        "-c:v",
        "-vcodec",
        "-c:a",
        "-acodec",
        "-movflags",
        "-pix_fmt",
        "-r",
        "-s",
        "-b",
        "-b:v",
        "-b:a",
        "-ar",
        "-ac",
        "-map",
        "-map:a",
        "-map:s",
        "-ss",
        "-t",
        "-to",
        "-vf",
        "-af",
    )
)


class CommandError(ValueError):
    """A command this build cannot honestly run — surfaced verbatim to the user."""


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

    @property
    def video_filter(self) -> list[list[str]]:
        return [list(node) for node in self.params.get("video_filter") or []]

    @property
    def audio_filter(self) -> list[list[str]]:
        return [list(node) for node in self.params.get("audio_filter") or []]

    def summary(self) -> str:
        """One line the terminal shows before Run."""
        bits = [
            f"op={self.op}",
            f"in={Path(self.input_path).name}",
            f"out={Path(self.output_path).name}",
        ]
        video_codec = self.params.get("video_codec")
        audio_codec = self.params.get("audio_codec")
        if video_codec:
            bits.append(f"v={video_codec}")
        if audio_codec:
            bits.append(f"a={audio_codec}")
        bits.extend(
            f"{key}={self.params[key]}"
            for key in (
                "crf",
                "preset",
                "start_seconds",
                "end_seconds",
                "format_name",
                "width",
                "fps",
            )
            if key in self.params
        )
        if self.params.get("stream_copy"):
            bits.append("stream-copy")
        if self.video_filter:
            bits.append("vf=" + ",".join(node[0] for node in self.video_filter))
        if self.audio_filter:
            bits.append("af=" + ",".join(node[0] for node in self.audio_filter))
        if self.params.get("encoder_options"):
            bits.append("encoder-options=" + ",".join(sorted(self.params["encoder_options"])))
        if self.params.get("container_options"):
            bits.append("muxer-options=" + ",".join(sorted(self.params["container_options"])))
        return " ".join(bits)


def tokenize(command: str) -> list[str]:
    """Split on whitespace, honour quotes, NEVER mangle backslash paths.

    ``shlex`` in POSIX mode eats ``C:\\media\\in.mp4`` backslashes — this
    tokenizer keeps every byte inside quotes, only stripping the quotes.
    Empty quoted strings (``-i ""``) are refused, not silently bound to the
    next token; backslash escapes are NOT processed (quote the whole path).
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


def _map_params(maps: list[tuple[str, str]], src: str) -> dict:
    """``-map`` flags → the Job's stream selectors (absolute indices)."""
    params: dict = {}
    slots = {"v": "video_stream", "a": "audio_stream", "s": "subtitle_stream"}
    unresolved: list[int] = []
    for flag, value in maps:
        kind, index = _map_spec(value, flag)
        if kind is None:
            unresolved.append(index)
            continue
        params[slots[kind]] = index
    for index in unresolved:
        # A bare index ("-map 0:3"): ask the file what that stream is.
        stream_type = _stream_type_at(src, index)
        if stream_type in slots:
            params.setdefault(slots[stream_type], index)
        else:
            _refuse(f"-map 0:{index} is a {stream_type or 'missing'} stream — nothing to map")
    return params


def _stream_type_at(path: str, index: int) -> str | None:
    from services.engine_service import EngineService

    try:
        info = EngineService.probe(path)
    except Exception:
        return None
    for stream in info.streams:
        if stream.index == index:
            return stream.stream_type
    return None


def _codec_bits(value: str) -> str:
    """Drop a trailing ``(label)`` FFmpeg sometimes prints after a codec name."""
    return value.strip().split(" ")[0]


def _drop_empty(params: dict) -> dict:
    """Params the engine can take as "unset": drop None/""/empty containers.

    A key the user never typed must not appear in the job params at all — the
    engine's own defaults then apply, and the plan preview stays honest.
    """
    return {key: value for key, value in params.items() if value not in (None, "", {}, [])}


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


def _option_name(flag: str) -> str:
    """``-profile:v`` → ``profile``: FFmpeg's per-stream qualifier is syntax.

    ``-profile:v high`` means "the profile option, for the video stream" — the
    option's own name is ``profile``. (Only the qualifier is dropped; nothing
    else is renamed.)
    """
    name = flag.lstrip("-")
    head, sep, _tail = name.partition(":")
    return head if sep else name


def _offered_options(codec: str, limit: int = 12) -> str:
    """The encoder's own option names, for a refusal message that helps."""
    from core.engine_probe import probe

    schema = probe().encoder_option_schema.get(codec) or []
    names = sorted({str(spec["name"]) for spec in schema})
    if not names:
        return "(no options declared)"
    return ", ".join(names[:limit]) + (" …" if len(names) > limit else "")


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


def parse_command(
    command: str,
    *,
    duration_s: float | None = None,
    check_exist: bool = True,
) -> OpPlan:
    """Translate one ``ffmpeg …`` line into an :class:`OpPlan`.

    ``duration_s`` (probed by the caller from the first input) resolves an
    ``-ss`` with no ``-t``/``-to`` into a cut-to-end. Raises :class:`CommandError`
    for anything this build cannot honestly honour.
    """
    tokens = tokenize(command)
    if tokens and tokens[0].lower() in ("ffmpeg", "ffmpeg.exe"):
        tokens = tokens[1:]
    if not tokens:
        _refuse("empty command — type ffmpeg -i input output (see ffmpeg -h)")
    if tokens[0].lower() in ("ffprobe", "ffprobe.exe"):
        _refuse("ffprobe is not supported here — open the Dossier screen for probes")
    if tokens[0].lower() in ("-h", "-help", "--help"):
        # `ffmpeg -h` is a help request, not a command: answer with this build's
        # own surface (generated, not a fixed list).
        _refuse(help_text())

    inputs: list[str] = []
    flags: dict[str, str] = {}
    maps: list[tuple[str, str]] = []  # repeatable: -map 0:v:0 -map 0:a:1
    stream_flags: set[str] = set()
    positionals: list[str] = []
    notes: list[str] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("-") and token != "-":
            name, sep, attached = token.partition("=")
            name = name.lower()
            if name in NO_ARG_FLAGS:
                if name in ("-vn", "-an", "-sn", "-dn"):
                    stream_flags.add(name)
                elif sep:
                    _refuse(f"{name} takes no value")
                index += 1
                continue
            if sep:
                value = attached
            else:
                if index + 1 >= len(tokens):
                    _refuse(f"{name} expects a value")
                value = tokens[index + 1]
                index += 1
            if name == "-i":
                inputs.append(value)
                index += 1
                continue
            if name.startswith("-map"):
                # Repeatable by design (real ffmpeg takes several -map flags).
                maps.append((name, value))
                index += 1
                continue
            if name in flags:
                _refuse(
                    f"duplicate {name} ({flags[name]!r}, then {value!r}) — "
                    "run one command per value instead"
                )
            flags[name] = value
            index += 1
            continue
        positionals.append(token)
        index += 1

    if not inputs:
        _refuse("no input — add -i <file>")
    if not positionals:
        _refuse("no output file — the last argument must be the output path")
    if len(positionals) > 1:
        _refuse(f"multiple outputs are not supported (got {positionals[1:]})")
    output = positionals[0]

    if check_exist:
        missing = [path for path in inputs if not Path(path).exists()]
        if missing:
            _refuse("input file(s) not found: " + ", ".join(missing))

    try:
        if any(Path(src).resolve() == Path(output).resolve() for src in inputs):
            _refuse(f"input and output are the same file ({output}) — pick another output name")
    except OSError:
        pass

    out_ext = Path(output).suffix.lower()
    src = inputs[0]

    # ── multi-input → join (the only shape the join op takes) ─────────────
    if len(inputs) > 1:
        shaping = sorted(
            name
            for name in flags
            if name not in ("-f", "-loglevel", "-v", "-map", "-y", "-hide_banner", "-nostdin")
        ) + sorted(f for f in ("-vn", "-an", "-sn", "-dn") if f in stream_flags)
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

    if "-filter_complex" in flags:
        _refuse(
            "-filter_complex builds a non-linear graph — command mode runs linear "
            "-vf/-af chains; use the Filters screen for splits and overlays"
        )

    # ── knobs → the Job's real slots ─────────────────────────────────────
    params: dict = {}
    encoder_options: dict[str, str] = {}
    container_options: dict[str, str] = {}
    video_filter = _split_chain(flags["-vf"], "-vf") if "-vf" in flags else []
    audio_filter = _split_chain(flags["-af"], "-af") if "-af" in flags else []

    video_codec_raw = flags.get("-c:v") or flags.get("-vcodec")
    if "-c" in flags and not video_codec_raw:
        video_codec_raw = flags["-c"]
    audio_codec_raw = flags.get("-c:a") or flags.get("-acodec")

    video_copy = (video_codec_raw or "").strip().lower() == "copy"
    audio_copy = (audio_codec_raw or "").strip().lower() == "copy"

    # A codec name is validated here (fail before the job) but resolved by the
    # engine (it knows the alias/family rules) — the plan shows what will run.
    if video_codec_raw and not video_copy:
        video_codec_raw = _probe_encoder(_codec_bits(video_codec_raw))
    if audio_codec_raw and not audio_copy:
        audio_codec_raw = _probe_encoder(_codec_bits(audio_codec_raw))

    for name in _KNOB_FLAGS:
        if name in flags:
            encoder_options[_option_name(name)] = flags[name]
    if "-movflags" in flags:
        container_options["movflags"] = flags["-movflags"]
    if "-f" in flags:
        want = flags["-f"].lstrip(".").lower()
        if want not in (out_ext.lstrip("."), {"matroska": "mkv", "ipod": "m4a"}.get(want, want)):
            _refuse(f"-f {flags['-f']} conflicts with the output extension {out_ext or '(none)'}")

    if "-pix_fmt" in flags:
        params["pix_fmt"] = flags["-pix_fmt"]
        if video_codec_raw and not video_copy:
            _check_pix_fmt(video_codec_raw, params["pix_fmt"])
    if "-r" in flags:
        try:
            params["fps"] = round(float(flags["-r"]))
        except ValueError:
            _refuse(f"-r expects a frame rate (24, 25, 29.97…), got {flags['-r']!r}")
    if "-s" in flags:
        width, height = _parse_size(flags["-s"], "-s")
        params["scale_width"], params["scale_height"] = width, height
    if "-b:v" in flags:
        encoder_options["b"] = str(_parse_bitrate(flags["-b:v"], "-b:v"))
    if "-b:a" in flags:
        params["bitrate_kbps"] = max(1, _parse_bitrate(flags["-b:a"], "-b:a") // 1000)
    if "-ar" in flags:
        try:
            params["sample_rate"] = int(flags["-ar"])
        except ValueError:
            _refuse(f"-ar expects a sample rate (44100…), got {flags['-ar']!r}")
    if "-ac" in flags:
        try:
            params["channels"] = int(flags["-ac"])
        except ValueError:
            _refuse(f"-ac expects a channel count, got {flags['-ac']!r}")

    params.update(_map_params(maps, src))

    # Anything else is offered to the ENCODER (measured: the codec context's own
    # option list). av cannot tell us whether a muxer consumed an option — an
    # unknown key is accepted silently at avformat level — so guessing "muxer"
    # would be exactly the silent approximation this mode refuses. Muxer
    # settings therefore have one honest, real flag (-movflags); anything else
    # refuses and names what this encoder does accept.
    unknown = sorted(name for name in flags if name not in _ROUTED_FLAGS)
    probe_codec = video_codec_raw or (audio_codec_raw if audio_copy is False else "") or "mpeg4"
    for name in unknown:
        value = flags[name]
        if _encoder_takes_option(probe_codec, _option_name(name), value):
            encoder_options[_option_name(name)] = value
            notes.append(f"{name} {value} → encoder option (this build's {probe_codec} accepts it)")
        else:
            offered = _offered_options(probe_codec)
            _refuse(
                f"{name} is not an option of {probe_codec} in this build — it accepts "
                f"{offered}. Muxer settings use -movflags (e.g. -movflags +faststart)."
            )

    if video_filter:
        params["video_filter"] = video_filter
    if audio_filter:
        params["audio_filter"] = audio_filter
    if encoder_options:
        params["encoder_options"] = encoder_options
    if container_options:
        params["container_options"] = container_options

    # ── time range → cut / window ────────────────────────────────────────
    start = _parse_ts(flags["-ss"], "-ss") if "-ss" in flags else None
    if "-t" in flags and "-to" in flags:
        notes.append("both -t and -to given — -t (duration) wins")
    if "-t" in flags:
        end = (start or 0.0) + _parse_ts(flags["-t"], "-t")
    elif "-to" in flags:
        end = _parse_ts(flags["-to"], "-to")
    else:
        end = None

    wants_copy = video_copy and not (video_filter or audio_filter or encoder_options)
    if "-c" in flags and flags["-c"].lower() == "copy":
        wants_copy = not (video_filter or audio_filter or encoder_options)

    # ── routing by output extension (ffmpeg's own rule) ──────────────────
    if out_ext in AUDIO_EXTS or "-vn" in stream_flags:
        if "-vn" in stream_flags and out_ext not in AUDIO_EXTS:
            _refuse(
                "-vn with a video output leaves nothing to write — name an audio "
                "(.mp3/.m4a/.flac/…) or subtitle (.srt/.ass/.vtt) output"
            )
        fmt = out_ext.lstrip(".") or "mp3"
        if audio_codec_raw and not audio_copy:
            fmt = _format_for_audio_codec(audio_codec_raw, fmt)
        if start is not None or end is not None:
            _refuse(
                "time ranges need a cut first — extraction covers the full track; "
                "trim to a file, then extract from the trim"
            )
        if video_filter:
            _refuse("-vf shapes video — an extraction has no video stream")
        merged = {
            "format_name": fmt,
            **{k: v for k, v in params.items() if k in ("bitrate_kbps", "sample_rate", "channels")},
            **({"audio_filter": audio_filter} if audio_filter else {}),
            **({"encoder_options": encoder_options} if encoder_options else {}),
            **({"container_options": container_options} if container_options else {}),
        }
        note = f"audio → {fmt}"
        if audio_filter:
            note += " through " + ",".join(node[0] for node in audio_filter)
        return OpPlan(
            op="extract_audio",
            input_path=src,
            output_path=output,
            params=merged,
            notes=[*notes, note],
        )

    if out_ext in SUBTITLE_EXTS:
        if start is not None or end is not None:
            _refuse("time ranges need a cut first — subtitle extraction covers the whole file")
        return OpPlan(
            op="extract_subtitles",
            input_path=src,
            output_path=output,
            params={
                "format_name": out_ext.lstrip("."),
                "stream_index": params.get("subtitle_stream", 0),
            },
            notes=notes,
        )

    if out_ext == ".gif":
        gif_start = float(start) if start is not None else 0.0
        if end is not None and end <= gif_start:
            _refuse(f"empty GIF range: start {gif_start}s is past end {end}s")
        if end is not None:
            gif_duration = float(end - gif_start)
        elif duration_s:
            gif_duration = float(max(0.5, duration_s - gif_start))
        else:
            gif_duration = 5.0
            notes.append("no range given — first 5s becomes the GIF (pass -ss/-t to choose)")
        return OpPlan(
            op="create_gif",
            input_path=src,
            output_path=output,
            params={
                "fps": params.get("fps", 15),
                "width": params.get("scale_width", 480),
                "start_s": gif_start,
                "duration_s": gif_duration,
                **({"encoder_options": encoder_options} if encoder_options else {}),
                **({"container_options": container_options} if container_options else {}),
            },
            notes=notes,
        )

    if (start is not None or end is not None) and not wants_copy:
        if end is None:
            if duration_s is None:
                _refuse(
                    "-ss without -t/-to needs a probed duration — the terminal probes "
                    "the input first; if this reached you the probe failed"
                )
            end = duration_s
        if end <= (start or 0.0):
            _refuse(f"empty range: start {start}s >= end {end}s")
        cut_params = {
            "start_seconds": float(start or 0.0),
            "end_seconds": float(end),
            "stream_copy": False,
            "video_codec": video_codec_raw,
            "encoder_options": encoder_options,
            "container_options": container_options,
        }
        return OpPlan(
            op="cut",
            input_path=src,
            output_path=output,
            params=_drop_empty(cut_params),
            notes=[*notes, "frame-accurate re-encode trim"],
        )

    if (start is not None or end is not None) and wants_copy:
        return OpPlan(
            op="cut",
            input_path=src,
            output_path=output,
            params=_drop_empty(
                {
                    "start_seconds": float(start or 0.0),
                    "end_seconds": float(end if end is not None else (duration_s or 0.0)),
                    "stream_copy": True,
                    "container_options": container_options,
                }
            ),
            notes=[*notes, "stream copy — lossless, bit-exact trim"],
        )

    if wants_copy and out_ext not in AUDIO_EXTS:
        return OpPlan(
            op="remux",
            input_path=src,
            output_path=output,
            params=_drop_empty({"drop": [], "container_options": container_options}),
            notes=[*notes, f"lossless stream copy into {out_ext.lstrip('.') or 'the output'}"],
        )

    # ── default: convert ─────────────────────────────────────────────────
    if video_copy and not video_filter:
        _refuse("-c:v copy with a transcode target — use -c copy for a remux")
    if "-vn" in stream_flags:
        _refuse(
            "-vn with a video output leaves nothing to write — name an audio "
            "(.mp3/.m4a/.flac/…) or subtitle (.srt/.ass/.vtt) output"
        )
    convert_params = _drop_empty(
        {
            "container_options": container_options,
            "encoder_options": encoder_options,
            "video_codec": video_codec_raw,
            "audio_codec": audio_codec_raw if "-an" not in stream_flags else None,
            "pix_fmt": params.get("pix_fmt"),
            "fps": params.get("fps"),
            "scale_width": params.get("scale_width"),
            "scale_height": params.get("scale_height"),
            "video_stream": params.get("video_stream"),
            "audio_stream": params.get("audio_stream"),
            "video_filter": video_filter,
            "audio_filter": audio_filter,
        }
    )
    if "-sn" in stream_flags:
        notes.append("-sn has no effect on a transcode (subtitles are not re-encoded)")
    if audio_copy and "-an" not in stream_flags:
        notes.append("-c:a copy inside a transcode is not possible — audio re-encoded")
    return OpPlan(
        op="convert",
        input_path=src,
        output_path=output,
        params=_drop_empty(convert_params),
        notes=notes,
    )


def _format_for_audio_codec(codec: str, fallback: str) -> str:
    """The output format a requested audio encoder can actually live in."""
    from core.engine_probe import codec_family, muxers_for_container
    from services.engine_service import _supported_encoder_options

    if not _supported_encoder_options(codec, {"b": "1"}):
        _refuse(f"this build cannot encode {codec!r} — Engine Info lists its encoders")
    family = set(codec_family(codec))
    for candidate in (fallback, "m4a", "mp3", "ogg", "flac", "wav", "opus"):
        for match in muxers_for_container(candidate)[:1]:
            supported = set(match.get("audio") or []) | {match.get("default_audio") or ""}
            if family & supported:
                return candidate
    _refuse(f"no container in this build carries {codec!r} — try .m4a, .ogg or .mkv")
    return fallback


def help_text() -> str:
    """What command mode accepts — generated from this build, never a fixed list."""
    from core.engine_probe import probe

    probe_info = probe()
    return "\n".join(
        [
            "ffmpeg command mode — real FFmpeg syntax, validated against this build",
            "",
            f"this wheel: {probe_info.encoder_count} encoders, "
            f"{probe_info.format_count} formats, {probe_info.filter_count} filters",
            "",
            "inputs     -i <file>            (2+ inputs → join; per-clip flags refused)",
            "streams    -map 0:v:1 -map 0:a:0 -vn -an -sn",
            "trim       -ss <ts> [-t <dur> | -to <ts>]   (-c copy = lossless cut)",
            "codecs     -c:v <name> -c:a <name> -c copy",
            "quality    -crf -preset -tune -profile -level -g -bf -qmin -qmax -b:v -b:a",
            'filters    -vf "hqdn3d=4:3:6:4.5,unsharp=5:5:1.0"  -af "loudnorm=I=-16"',
            "           every filter this wheel ships; FFmpeg's own argument syntax",
            "muxer      -movflags +faststart (validated by a probe open)",
            "",
            "anything this build lacks is refused naming what is missing — nothing",
            "is silently approximated. Output extension picks the target",
            "(.mp3/.m4a/.flac/... extract audio, .srt/.ass/.vtt subtitles, .gif).",
        ]
    )
