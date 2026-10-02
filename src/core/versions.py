"""Live version strings — derived from the installed wheel, never hardcoded.

Screens used to say "PyAV 18" / "FFmpeg 8" as literals, which rot on the next
wheel bump. These helpers read the installed `av` package and fall back to the
last-known-good numerals when the wheel is unreachable, so the UI always names
the engine that is actually installed.
"""

from __future__ import annotations


def pyav_version() -> str:
    """Installed PyAV wrapper version (e.g. "18.1.0"); "18" when unreadable."""
    try:
        import av

        return str(av.__version__ or "18")
    except Exception:
        return "18"


def ffmpeg_version() -> str:
    """Linked FFmpeg version (e.g. "8.1.2"); "8" when unreadable.

    ``ffmpeg_version_info`` is a plain string attribute on the installed wheel,
    not a callable.
    """
    try:
        import av

        info = av.ffmpeg_version_info
        return str(info or "8")
    except Exception:
        return "8"


def pyav_major() -> str:
    """Major PyAV number for short labels ("PyAV 18 …")."""
    return pyav_version().split(".")[0] or "18"


__all__ = ["ffmpeg_version", "pyav_major", "pyav_version"]
