"""Subtitle cue writers (SRT / WebVTT / ASS)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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
