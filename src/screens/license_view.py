"""Open-source license notices and bundled license texts.

Adapted from the proot-distro pattern: a GPL §6(b) source offer, the native
payload components (FFmpeg + its statically-linked codec libraries), the Python
dependencies read live from importlib.metadata, and the full license texts from
src/LICENSES/.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path

import flet as ft

from core.constants import APP_NAME, APP_VERSION
from core.theme import TEXT_MUTED_DARK, TEXT_MUTED_LIGHT
from core.tokens import FONT_MD, FONT_SM, FONT_XS, SPACE_SM

_LICENSES_DIR = Path(__file__).resolve().parent.parent / "LICENSES"
_REPO_URL = "https://github.com/Nwokike/FFmpeg"

# Native payload components (FFmpeg + the external codec libraries statically
# folded into libavcodec.so). Kept in step with scripts/wrap_pins.py.
_NATIVE_LICENSES = {
    "FFmpeg": "GPL-3.0-or-later",
    "x264 (H.264 encoder)": "GPL-2.0-or-later",
    "x265 (HEVC encoder)": "GPL-2.0-or-later",
    "libvpx (VP8/VP9)": "BSD-3-Clause",
    "libaom (AV1)": "BSD-3-Clause",
    "libdav1d (AV1 decoder)": "BSD-2-Clause",
    "libmp3lame (MP3 encoder)": "LGPL-2.0-or-later",
    "libopus": "BSD-3-Clause",
    "libspeex": "BSD-3-Clause",
    "libtwolame": "LGPL-2.1-or-later",
    "libwebp": "BSD-3-Clause",
    "libfreetype": "FTL / GPL-2.0-or-later",
    "libfribidi": "LGPL-2.1-or-later",
    "mbedtls (TLS)": "Apache-2.0 / GPL-2.0-or-later",
    "libbluray": "LGPL-2.1-or-later",
    "libxml2": "MIT",
}

_PY_DISTS = (
    "av",
    "flet",
    "flet-ads",
    "flet-audio",
    "flet-audio-recorder",
    "flet-camera",
    "flet-permission-handler",
    "flet-video",
    "httpx",
    "httpcore",
    "h11",
    "idna",
    "certifi",
    "typing-extensions",
    "anyio",
    "msgpack",
    "oauthlib",
    "repath",
    "six",
)

_TEXT_FILES = (
    ("GPL-3.0.txt", "GPL-3.0"),
    ("GPL-2.0.txt", "GPL-2.0"),
    ("LGPL-2.1.txt", "LGPL-2.1"),
    ("IJG.txt", "IJG"),
    ("BSD-3-Clause.txt", "BSD-3-Clause"),
    ("MIT.txt", "MIT"),
    ("ISC.txt", "ISC"),
    ("Apache-2.0.txt", "Apache-2.0"),
    ("MPL-2.0.txt", "MPL-2.0"),
    ("PSF-2.0.txt", "PSF-2.0"),
)


def _dist_license(dist: str) -> tuple[str, str]:
    try:
        meta = importlib_metadata.metadata(dist)
    except Exception:
        return ("", "")
    version = meta.get("Version", "")
    lic = meta.get("License-Expression") or meta.get("License") or ""
    return (version, lic)


def licenses_view(is_dark: bool) -> ft.Control:
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT
    rows: list[ft.Control] = [
        ft.Text(
            f"{APP_NAME} v{APP_VERSION} incorporates open-source components "
            "licensed under free and copyleft licenses.",
            size=FONT_SM,
        ),
        ft.Divider(),
        ft.Text("GPL §6(b) Source Code Offer", size=FONT_MD, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)). The complete "
            "machine-readable Corresponding Source for the GPL-licensed "
            "components — FFmpeg, x264, x265 and this application — is "
            f"available at {_REPO_URL} and will remain available for at least "
            "three (3) years from the date of each release. Upstream: "
            "ffmpeg.org, code.videolan.org/videolan/x264, "
            "bitbucket.org/multicoreware/x265_git, github.com/PyAV-Org/PyAV, "
            "github.com/Javernaut/ffmpeg-android-maker (build recipes).",
            size=FONT_XS,
            color=muted,
            selectable=True,
        ),
        ft.Divider(),
        ft.Text(
            "FFmpeg is a trademark of the FFmpeg project. This application is "
            "not affiliated with, endorsed by, or sponsored by the FFmpeg "
            "project.",
            size=FONT_XS,
            color=muted,
        ),
        ft.Divider(),
        ft.Text("Native Payload Components", size=FONT_MD, weight=ft.FontWeight.BOLD),
    ]
    for pkg, lic in _NATIVE_LICENSES.items():
        rows.append(
            ft.ListTile(
                title=ft.Text(pkg, size=FONT_SM, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"License: {lic}", size=FONT_XS, color=muted),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("Python Dependencies", size=FONT_MD, weight=ft.FontWeight.BOLD))
    for dist in _PY_DISTS:
        ver, lic = _dist_license(dist)
        rows.append(
            ft.ListTile(
                title=ft.Text(f"{dist} {ver}".strip(), size=FONT_SM, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(
                    f"License: {lic or 'See license text'}",
                    size=FONT_XS,
                    color=muted,
                ),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("License Texts", size=FONT_MD, weight=ft.FontWeight.BOLD))
    for fname, label in _TEXT_FILES:
        path = _LICENSES_DIR / fname
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else "(text missing)"
        )
        rows.append(
            ft.ExpansionTile(
                title=ft.Text(label, size=FONT_SM, weight=ft.FontWeight.BOLD),
                controls=[
                    ft.Container(
                        content=ft.Text(text, size=FONT_XS, font_family="monospace"),
                        padding=SPACE_SM,
                    )
                ],
            )
        )
    return ft.Column(controls=rows, scroll=ft.ScrollMode.AUTO, expand=True)
