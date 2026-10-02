"""Bundled release changelogs for offline display."""

from __future__ import annotations

from core.constants import APP_VERSION

CHANGELOG: dict[str, str] = {
    "1.0.0": """### FFmpeg 1.0.0 — Initial Release
- **Full FFmpeg 8 Media Engine**: Powered by PyAV on-device with zero cloud dependencies.
- **Convert & Transcode**: Support for MP4, MKV, MOV, WEBM, AVI, MP3, AAC, FLAC, Opus, and more.
- **Video Compressor**: Destination presets (WhatsApp, Telegram, Discord, Email) or custom target size.
- **Trim & Cut**: Keyframe-snapped stream-copy cuts or frame-accurate re-encoding, scrubbed on a live thumbnail strip with keyframe markers.
- **Audio Studio**: Two-pass loudness normalization (YouTube -14, Podcast -16, Broadcast -23 LUFS), channel mixing, and soxr resampling.
- **Extractors**: Audio extraction, frame capture to JPG/PNG, palette-optimized GIF generation, and SRT/ASS/WebVTT subtitle export.
- **Filter Stack**: Crop, speed, volume boosting, rotation/flip, denoise, sharpen, and PNG watermark — with every filter gated to what this device's build actually supports.
- **Capture**: In-app camera photo/video and microphone recording, straight into the conversion pipeline.
- **Live Streams**: Record HTTP/HTTPS/HLS/DASH streams on-device; Stop keeps the recording.
- **Join**: Merge clips end-to-end — lossless when formats match, uniform re-encode otherwise, with optional crossfade transitions.
- **Batch Queue**: Serial job queue with per-job progress, pause/resume, cancel, and a persistent jobs banner.
- **Previews**: Before/after A/B video comparison, an audio player on results, and a scrubbing preview with thumbnails in Cut.
- **Media Dossier**: Streams, codecs, bitrates, rotation, language and chapters — with a shareable markdown report and lossless track-picker copies.
- **On-Device Storage**: Private, sandboxed processing with instant Share sheet and Downloads saving.
""",  # keys + prose are history (literal forever): they describe what shipped THEN
}


def notes_for(version: str) -> str:
    """Return markdown notes for a given version, falling back to the installed version's notes."""
    return CHANGELOG.get(version, CHANGELOG.get(APP_VERSION, "Release notes unavailable."))
