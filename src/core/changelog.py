"""Bundled release changelogs for offline display."""

from __future__ import annotations

from core.constants import APP_VERSION

CHANGELOG: dict[str, str] = {
    "1.0.0": """### FFmpeg 1.0.0 — Initial Release
- **Full FFmpeg 8 Media Engine**: Powered by PyAV on-device with zero cloud dependencies.
- **Convert & Transcode**: Support for MP4, MKV, MOV, WEBM, AVI, MP3, AAC, FLAC, Opus, and more.
- **Video Compressor**: Destination presets (WhatsApp, Telegram, Discord, Email) or custom target size.
- **Trim & Cut**: Fast stream-copy cuts or frame-accurate re-encoding with visual time scrubbers.
- **Audio Studio**: Two-pass loudness normalization (YouTube -14, Podcast -16, Broadcast -23 LUFS), channel mixing, and resampling.
- **Extractors**: High-quality audio extraction, frame capture to JPG/PNG, and palette-optimized GIF generation.
- **Filter Stack**: Speed adjustment, volume boosting, rotation/flip, and resolution scaling.
- **Media Dossier**: Detailed codec, stream, bitrate, and metadata inspection.
- **On-Device Storage**: Private, sandboxed processing with instant Share sheet and Downloads saving.
""",
}


def notes_for(version: str) -> str:
    """Return markdown notes for a given version, falling back to latest."""
    return CHANGELOG.get(version, CHANGELOG.get(APP_VERSION, "Release notes unavailable."))
