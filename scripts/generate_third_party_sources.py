#!/usr/bin/env python3
"""Generate THIRD-PARTY-SOURCES.md with exact provenance and source offer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from wrap_pins import (  # noqa: E402
    ANDROID_API_LEVEL,
    FAM_COMMIT,
    FAM_REPO,
    FFMPEG_SHA256,
    FFMPEG_URL,
    FFMPEG_VERSION,
    PAYLOAD_COMPONENTS,
)

OUTPUT_FILE = REPO_ROOT / "THIRD-PARTY-SOURCES.md"


def generate_markdown() -> str:
    lines = [
        "# Third-Party Sources — FFmpeg AV",
        "",
        "This application incorporates third-party software components licensed under free and",
        "open-source software licenses, including the GNU General Public License (GPL).",
        "",
        "## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))",
        "",
        "The complete machine-readable Corresponding Source for the GPL-licensed components",
        "and for this application is available at:",
        "https://github.com/Nwokike/FFmpeg",
        "and via GitHub Releases at: https://github.com/Nwokike/FFmpeg/releases/latest",
        "",
        "This offer is valid for at least three (3) years from the date of release to any third",
        "party for no charge other than the cost of physically performing source distribution.",
        "To request source code via durable physical medium, contact: contact@kiri.ng",
        "",
        "## Native Payload (Packaged in flet-libffmpeg)",
        "",
        f"FFmpeg {FFMPEG_VERSION} and its statically-linked external codec libraries are",
        f"cross-built for Android at API level {ANDROID_API_LEVEL} with 16 KiB PT_LOAD alignment.",
        "",
        f"- FFmpeg {FFMPEG_VERSION}: [{FFMPEG_URL}]({FFMPEG_URL})",
        f"- SHA-256: `{FFMPEG_SHA256}`",
        f"- Cross-build harness: [{FAM_REPO}]({FAM_REPO}) at commit `{FAM_COMMIT}`",
        "  (each external library's exact download URL and hash is pinned in that",
        "  commit's `scripts/<library>/download.sh`; verification runs at build time",
        "  and the built payload's configure string is checked for every encoder)",
        "",
        "| Component | License | Upstream |",
        "|---|---|---|",
    ]
    for name, (lic, url) in PAYLOAD_COMPONENTS.items():
        lines.append(f"| `{name}` | {lic} | [{name}]({url}) |")

    lines.extend(
        [
            "",
            "## Python Dependencies",
            "",
            "| Package | License | Upstream |",
            "|---|---|---|",
            "| `av` (PyAV) | LGPL-2.1-or-later (binding) / GPL-3.0-or-later (combined payload) | https://github.com/PyAV-Org/PyAV |",
            "| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-audio` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-audio-recorder` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-camera` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-permission-handler` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-video` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `httpx` | BSD-3-Clause | https://github.com/encode/httpx |",
            "",
            "## License Texts",
            "",
            "Complete license texts for all included software components are provided in the",
            "`LICENSES/` directory and within the app under Settings → Open-Source Licenses.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    OUTPUT_FILE.write_text(generate_markdown(), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
