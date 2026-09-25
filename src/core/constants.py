"""Runtime constants — single source of truth for the app.

Mirrors the house pattern (sibling apps read identity/version/storage keys and
the update manifest URL from here).
"""

from __future__ import annotations

import sys

APP_NAME = "FFmpeg Lite"
COMPANY = "Kiri Research Labs"
ORG = "ng.kiri"
BUNDLE_ID = "ng.kiri.ffmpeg"

# Read from pyproject.toml at import time (house pattern: DDGS/Sherlock read
# build_number this way so the update check compares against the real build).
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

# AdMob — Google test App ID (matches AdService USE_TEST_IDS=True). The
# [tool.flet.android.meta_data] block in pyproject.toml carries the matching
# APPLICATION_ID; swap all three files at release with:
#   uv run python tools/admob.py swap-ids --mode prod --app-id … --banner … --interstitial …
# (the CI AdMob guard fails tag builds while the test App ID is still present.)
ADMOB_APP_ID_TEST = "ca-app-pub-3940256099942544~3347511713"
ADMOB_BANNER_UNIT_TEST = "ca-app-pub-3940256099942544/9214589741"
ADMOB_INTERSTITIAL_UNIT_TEST = "ca-app-pub-3940256099942544/1033173712"

# Production units — filled by tools/admob.py swap-ids --mode prod (empty = unset;
# AdService falls back to the test IDs while these are blank).
ADMOB_APP_ID_PROD = "ca-app-pub-5679949845754640~8554716742"
ADMOB_BANNER_UNIT_PROD = "ca-app-pub-5679949845754640/3222499013"
ADMOB_INTERSTITIAL_UNIT_PROD = "ca-app-pub-5679949845754640/5194056233"

# Storage-tier env vars set by the Flet mobile launcher (verified in 1.0 source).
STORAGE_DATA_ENV = "FLET_APP_STORAGE_DATA"
STORAGE_CACHE_ENV = "FLET_APP_STORAGE_CACHE"
STORAGE_TEMP_ENV = "FLET_APP_STORAGE_TEMP"

# Deep-link scheme/host (matches [tool.flet.deep_linking]).
DEEP_LINK_SCHEME = "ffmpeg"
DEEP_LINK_HOST = "app"

# ── Brand palette (single source of truth; pyproject [tool.flet] keys mirror it)
# PRIMARY is the FFmpeg launcher glyph green — the app's primary color in both
# light and dark themes (house rule: brand hue constant across themes, only
# surfaces change — Sherlock/voicelm pattern). Dark surfaces = Kiri slate.
PRIMARY = "#3C8038"  # FFmpeg green (icon.svg glyph fill)
PRIMARY_DARK = "#2E6B2A"  # darker shade for light-mode glyph tinting
KIRI_DARK_BG = "#0F1114"  # launcher/splash dark background (icon_background)
KIRI_DARK_2 = "#1A1D22"
KIRI_LIGHT_BG = "#FAFAFA"

PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
