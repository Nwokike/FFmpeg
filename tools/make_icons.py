"""Icon asset generator (dev-only Pillow — never shipped in the APK).

1. Square-pads src/assets/icon.png (currently 2048x1612) with transparency so
   flet-platform-assets stops auto-padding with a warning and Windows/Linux
   get a centered glyph.
2. Emits src/assets/icon_android.png — Android adaptive foreground with the
   glyph scaled to 64% of the canvas (inside the 66% circular safe zone).

Run: uv run python tools/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "assets"
CANVAS = 1024
SAFE_RATIO = 0.64  # glyph extent of canvas (adaptive safe zone ≈ 0.66)


def _pad_square(img: Image.Image) -> Image.Image:
    """Center the glyph on a transparent square canvas (no cropping)."""
    img = img.convert("RGBA")
    side = max(img.width, img.height)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


def _adaptive_foreground(img: Image.Image) -> Image.Image:
    """Scale the glyph into the adaptive-icon safe zone on a transparent square."""
    img = img.convert("RGBA")
    target = int(CANVAS * SAFE_RATIO)
    ratio = min(target / img.width, target / img.height)
    glyph = img.resize(
        (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.paste(glyph, ((CANVAS - glyph.width) // 2, (CANVAS - glyph.height) // 2), glyph)
    return canvas


def main() -> None:
    src = ASSETS / "icon.png"
    original = Image.open(src)
    print(f"source: {src.name} {original.size[0]}x{original.size[1]}")

    square = _pad_square(original)
    square.save(src, optimize=True)
    print(f"square master written: {src.name} {square.size[0]}x{square.size[1]}")

    android = _adaptive_foreground(original)
    out = ASSETS / "icon_android.png"
    android.save(out, optimize=True)
    print(f"adaptive foreground written: {out.name} {android.size[0]}x{android.size[1]}")


if __name__ == "__main__":
    main()
