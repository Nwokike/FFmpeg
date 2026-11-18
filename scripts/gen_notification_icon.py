"""Generate the Android notification small icon from the app icon.

Android renders notification small icons as a white silhouette; the platform
tints them. This derives the silhouette from the icon's alpha channel and
writes the five drawable densities `flet build` copies from `res_dir`
(android_res/). Run once per icon change; the PNGs are committed.

Usage: uv run python scripts/gen_notification_icon.py
(Pillow comes with the dev toolchain — flet-cli depends on it.)
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover — dev-only helper
    raise SystemExit(
        "Pillow is required (uv run --group dev python scripts/gen_notification_icon.py)"
    ) from None

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "assets" / "icon.png"
OUT = ROOT / "android_res"
NAME = "ic_stat_ffmpegav.png"
SIZES = {"mdpi": 24, "hdpi": 36, "xhdpi": 48, "xxhdpi": 72, "xxxhdpi": 96}


def main() -> int:
    icon = Image.open(SRC).convert("RGBA")
    alpha = icon.getchannel("A")
    white = Image.new("RGBA", icon.size, (255, 255, 255, 255))
    transparent = Image.new("RGBA", icon.size, (0, 0, 0, 0))
    silhouette = Image.composite(white, transparent, alpha)
    for density, px in SIZES.items():
        target = OUT / f"drawable-{density}" / NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        silhouette.resize((px, px), Image.LANCZOS).save(target, optimize=True)
        print(f"> {target.relative_to(ROOT)} ({px}x{px})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
