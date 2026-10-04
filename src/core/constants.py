"""Runtime constants — single source of truth for the app.

Identity, version, storage keys, and the update manifest URL live here so no
screen hardcodes them.
"""

from __future__ import annotations

import sys

APP_NAME = "FFmpeg Lite"
COMPANY = "Kiri Research Labs"
ORG = "ng.kiri"
BUNDLE_ID = "ng.kiri.ffmpeg"

# Read from pyproject.toml at import time so the update check compares
# against the real build (not a stale literal).
APP_VERSION = "1.0.0"
BUILD_NUMBER = 1


def _read_build_from_pyproject() -> tuple[str, int]:
    """Read [project] version and [tool.flet] build_number from pyproject.toml.

    Falls back to the module-level defaults if the file or keys are absent
    (the packaged app ships pyproject.toml at the app root).
    """
    version, build = APP_VERSION, BUILD_NUMBER
    try:
        import tomllib
        from pathlib import Path

        here = Path(__file__).resolve()
        for parent in here.parents:
            cand = parent / "pyproject.toml"
            if cand.is_file():
                with Path(cand).open("rb") as fh:
                    data = tomllib.load(fh)
                version = str(data.get("project", {}).get("version", version))
                build = int(data.get("tool", {}).get("flet", {}).get("build_number", build))
                break
    except Exception as exc:
        import logging as _log

        _log.getLogger(__name__).warning("pyproject read failed: %s", exc)
    return version, build


APP_VERSION, BUILD_NUMBER = _read_build_from_pyproject()

# Update manifest (raw version.json on the main branch of this repo).
UPDATE_CONFIG_URL = "https://raw.githubusercontent.com/Nwokike/FFmpeg/main/version.json"
GITHUB_RELEASE_URL = "https://github.com/Nwokike/FFmpeg/releases/latest"
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.ffmpeg"

# AdMob — Google test units (fallback only: AdService.USE_TEST_IDS is False
# and the PROD IDs below are filled, so test units are never served). The
# [tool.flet.android.meta_data] block in pyproject.toml must carry the
# matching production APPLICATION_ID — the CI AdMob guard fails tag builds
# while a test App ID is present there.
ADMOB_APP_ID_TEST = "ca-app-pub-3940256099942544~3347511713"
ADMOB_BANNER_UNIT_TEST = "ca-app-pub-3940256099942544/9214589741"
ADMOB_INTERSTITIAL_UNIT_TEST = "ca-app-pub-3940256099942544/1033173712"

# Production units (all filled = prod ads live; blank any to fall back to test IDs).
ADMOB_APP_ID_PROD = "ca-app-pub-5679949845754640~8554716742"
ADMOB_BANNER_UNIT_PROD = "ca-app-pub-5679949845754640/3222499013"
ADMOB_INTERSTITIAL_UNIT_PROD = "ca-app-pub-5679949845754640/5194056233"

# Storage-tier env vars set by the Flet mobile launcher (verified in 1.0 source).
STORAGE_DATA_ENV = "FLET_APP_STORAGE_DATA"
STORAGE_CACHE_ENV = "FLET_APP_STORAGE_CACHE"
STORAGE_TEMP_ENV = "FLET_APP_STORAGE_TEMP"

# Deep-link scheme/host (matches [tool.flet.android.deep_linking] — Android
# reads the ANDROID block only; a top-level [tool.flet.deep_linking] is ignored).
DEEP_LINK_SCHEME = "ffmpeg"
DEEP_LINK_HOST = "app"

# ── Brand palette (single source of truth; pyproject [tool.flet] keys mirror it)
# PRIMARY is the FFmpeg launcher glyph green — the app's primary color in both
# light and dark themes (brand hue constant across themes, only surfaces
# change). Dark surfaces = Kiri slate.
PRIMARY = "#3C8038"  # FFmpeg green (icon.svg glyph fill)
PRIMARY_DARK = "#2E6B2A"  # darker shade for light-mode glyph tinting
KIRI_DARK_BG = "#0F1114"  # launcher/splash dark background (icon_background)
KIRI_DARK_2 = "#1A1D22"
KIRI_LIGHT_BG = "#FAFAFA"

# ── Job op labels (single source of truth for cards, banners, snacks) ──
# "concat" is the real join op ("join" is a view name, never an op);
# "record" renders as a noun everywhere, not a verb in one place.
OP_LABELS: dict[str, str] = {
    "convert": "Convert",
    "compress": "Compress",
    "cut": "Trim",
    "extract_audio": "Extract Audio",
    "extract_frames": "Extract Frames",
    "extract_subtitles": "Extract Subtitles",
    "create_gif": "Create GIF",
    "filters": "Filters",
    "audio_studio": "Audio Studio",
    "audio": "Audio Studio",
    "concat": "Join",
    "join": "Join",
    "remux": "Remux",
    "record": "Recording",
}


def op_title(op: str | None) -> str:
    """Human label for a job op; never raises, never returns blanks."""
    key = (op or "").strip() or "convert"
    return OP_LABELS.get(key, key.replace("_", " ").title())


PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


# ── Per-tool media kinds (single source of truth for load-time gating) ──
# Derived from engine truth: which MediaInfo.kind each tool's op actually
# processes. The load gate (main._load_path_into, capture handoff) refuses a
# wrong-kind file BEFORE the screen opens — the Join screen's add-time
# reject, applied everywhere. None = kind-agnostic (the dossier's job).
TOOL_MEDIA_KINDS: dict[str, frozenset[str] | None] = {
    "convert": frozenset({"video", "audio", "image"}),
    "compress": frozenset({"video"}),
    "cut": frozenset({"video", "audio"}),
    "extract": frozenset({"video", "audio"}),
    "filters": frozenset({"video"}),
    "audio": frozenset({"video", "audio"}),
    "probe": None,  # dossier: any probed media
    "join": frozenset({"video"}),  # add-flow probe-then-skip keeps this
}

KIND_LABELS: dict[str, str] = {
    "video": "a video",
    "audio": "an audio file",
    "image": "an image",
    "unknown": "an unrecognized file",
}


def kind_allowed(target_view: str, kind: str) -> bool:
    """True when a tool accepts this media kind (None = kind-agnostic tool)."""
    allowed = TOOL_MEDIA_KINDS.get(target_view)
    return allowed is None or kind in allowed


def kind_refusal(target_view: str, kind: str) -> str:
    """Human message for a refused load; caller decides dialog vs snack."""
    allowed = TOOL_MEDIA_KINDS.get(target_view)
    want = ", ".join(sorted(allowed)) if allowed else "media"
    return (
        f"{op_title(target_view)} works on {want} — this file is "
        f"{KIND_LABELS.get(kind, kind)}. Pick a different file or a different tool."
    )
