"""Local brand assets that work in Flet web, desktop, and packaged apps."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def load_asset_bytes(name: str) -> bytes:
    """Read a packaged app asset without relying on Flet's client URL resolver."""
    src_root = Path(__file__).resolve().parents[1]
    candidates = (
        src_root / "assets" / name,
        Path.cwd() / "assets" / name,
        Path.cwd() / "src" / "assets" / name,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_bytes()
    raise FileNotFoundError(f"App asset not found: {name}")


def app_icon_svg() -> bytes:
    """Return the brand SVG as bytes so `ft.Image` can tint it in dark mode."""
    return load_asset_bytes("icon.svg")
