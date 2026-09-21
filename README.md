<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="src/assets/icon_white.svg">
    <source media="(prefers-color-scheme: light)" srcset="src/assets/icon.svg">
    <img src="src/assets/icon.svg" alt="FFmpeg" width="320" />
  </picture>
</p>

<p align="center">
  On-device media studio — convert, transcode, compress, cut, extract and filter any video or audio with the full power of FFmpeg 8
</p>

<p align="center">
  <a href="https://play.google.com/store/apps/details?id=ng.kiri.ffmpeg"><img src="https://img.shields.io/badge/Google_Play-Android-3DDC84?style=for-the-badge&logo=google-play&logoColor=white" alt="Google Play Store" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download-APK-orange?style=for-the-badge&logo=android&logoColor=white" alt="Download APK" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download_Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download_Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" /></a>
  <img src="https://img.shields.io/badge/Built%20with-Flet%201.0-00B0FF?style=for-the-badge&logo=flutter&logoColor=white" alt="Flet" />
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
</p>

---

## Download

| Platform | Download | Notes |
| :---: | :---: | :--- |
| 🤖 **Android** | [![Play Store](https://img.shields.io/badge/Google_Play-414141?style=flat-square&logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=ng.kiri.ffmpeg) | Recommended for Android users |
| 🪟 **Windows** | [![Windows Release](https://img.shields.io/badge/Download_Windows_Release-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg_Setup.exe) | Automated standalone setup installer with desktop shortcut integration |
| 🐧 **Linux (Debian/Ubuntu)** | [![Linux DEB](https://img.shields.io/badge/Download_Linux_DEB-FCC624?style=flat-square&logo=linux&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg.deb) | Desktop package tailored for Ubuntu, Debian, Linux Mint & Pop!_OS |
| 🎩 **Linux (Fedora/RHEL)** | [![Linux RPM](https://img.shields.io/badge/Download_Linux_RPM-E91E63?style=flat-square&logo=redhat&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg.rpm) | Desktop package tailored for Fedora, openSUSE, RHEL & CentOS |
| 📦 **Linux (Universal Portable)** | [![Linux TAR.GZ](https://img.shields.io/badge/Download_Linux_TAR.GZ-9C27B0?style=flat-square&logo=linux&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg.tar.gz) | Universal standalone portable archive for Arch, Alpine, Steam Deck & all distros |

### Android Architecture Build Splits

| Variant | Download | Notes |
| :---: | :---: | :--- |
| 📱 **ARM64** (most phones) | [**ffmpeg-arm64-v8a.apk**](https://github.com/Nwokike/FFmpeg/releases/latest/download/ffmpeg-arm64-v8a.apk) | Modern 64-bit Android devices |
| 💻 **x86_64** (emulators) | [**ffmpeg-x86_64.apk**](https://github.com/Nwokike/FFmpeg/releases/latest/download/ffmpeg-x86_64.apk) | Chromebooks & Android emulators |

---

## Core Capabilities

| Capability | Description |
| :--- | :--- |
| **Full FFmpeg 8 Engine** | Every codec, container and filter of the bundled FFmpeg build — enumerated live at runtime and surfaced in the UI, so the app always shows exactly what this device can do. |
| **Convert, Transcode & Compress** | Any container to any container, quality presets or target file size ("small enough for WhatsApp/Telegram"), duration presets, bitrate/CRF advanced controls. |
| **Cut / Trim** | Instant stream-copy cuts (keyframe-accurate) or frame-accurate re-encode, scrubbed on a live thumbnail strip. |
| **Extract** | Audio (AAC/MP3/Opus/FLAC/WAV/PCM), frames, thumbnail grids, palette-optimized GIFs, SRT/ASS subtitles. |
| **Filters** | Crop, scale, rotate/flip, speed (atempo), volume, EQ, denoise, sharpen, image watermark overlay, concat. |
| **Audio Studio** | Loudness normalization (two-pass, use-case presets), resampling (incl. soxr), channel mixing, speed/pitch. |
| **Capture** | In-app camera video/still capture and microphone recording — straight into the conversion pipeline. |
| **Live Streams** | Record HTTP/HTTPS/HLS/DASH streams on-device (feature-gated on engine support). |
| **Batch Jobs** | Multi-file queue with per-job progress, cancel, pause and a jobs banner that survives tab switches. |
| **Media Dossier** | Probe any file: streams, codecs, bitrates, dimensions, rotation, language, chapters, full `dumps_format` report — shareable on-device. |
| **Share & Save** | Save to Downloads/Movies via the system picker, or push outputs to any app via the system share sheet. |

---

## Architecture

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | Flet 1.0 (Flutter engine) | Cross-platform UI — M3 themes, adaptive video controls, on-demand lists, reorderable filter stacks |
| **Media Engine** | `av` (PyAV 18, FFmpeg 8.1.2 bundled) | Decode/encode/mux/filter/resample — in-process, GIL-released C calls, cancel-aware |
| **Playback** | `flet-video` (mpv backend, hardware decode) + `flet-audio` | Live before/after preview of sources and outputs |
| **Capture** | `flet-camera` + `flet-audio-recorder` | In-app video/still/mic capture feeding the engine |
| **Permissions** | `flet-permission-handler` | Just-in-time Android permission flows with graceful degradation |
| **Local Storage** | `FLET_APP_STORAGE_*` tiers (data/cache/temp) | Debounced atomic JSON for settings + job history; regenerable caches |
| **Async Runtime** | `asyncio` + isolated worker threads | One `CodecContext` per thread, ~4 Hz progress publish, cooperative cancellation |

### Visual Flow

```mermaid
graph TB
    subgraph FFMPEG_CLIENT ["📱 FFmpeg CLIENT (On-Device Media Studio)"]
        UI["🎨 Flet 1.0 UI (Home | Convert | Compress | Cut | Extract | Filters | Audio | Batch | Streams | History | Settings)"]
        Engine["⚙️ PyAV Engine (FFmpeg 8.1.2)"]
        Jobs["🧵 Job Queue (isolated worker threads)"]
        Storage["💾 Local Storage (data / cache / temp tiers)"]
        UI --> Jobs --> Engine
        UI --> Storage
    end

    subgraph SOURCES ["📥 INPUTS"]
        Files["📁 Media Picker (SAF/MediaStore)"]
        Cam["📷 Camera + Mic Capture"]
        URL["🌐 Live Streams (HTTP/HLS/DASH)"]
    end

    subgraph OUTPUTS ["📤 OUTPUTS"]
        Save["💾 Save (system picker)"]
        Share["🔗 System Share Sheet"]
        Preview["▶️ Hardware-Decode Preview (flet-video / flet-audio)"]
    end

    Files --> Engine
    Cam --> Engine
    URL --> Engine
    Engine --> Save
    Engine --> Share
    Engine --> Preview
```

---

## Processing Guide

| Job | Typical Time | Notes |
| :--- | :---: | :--- |
| **Stream Copy (remux / cut-copy)** | Seconds | No re-encode — instantaneous, lossless |
| **1080p → 720p H.264** | ~1× duration | Software encode on most SoCs |
| **HEVC encode** | 2–5× slower | Availability depends on device build |
| **GIF (palette-optimized)** | ~10–20 s / 15 s clip | Two-pass `palettegen`/`paletteuse` |
| **Loudness normalize** | ~2× pass | Two-pass `loudnorm` measurement + application |

---

## Privacy & Security

1. **On-Device Processing** — media never leaves your phone; no cloud uploads, ever.
2. **Zero Telemetry** — the only network calls are update checks and stream capture when you explicitly provide a URL.
3. **Data Sovereignty** — outputs are written where you choose via the system picker or share sheet; nothing is auto-synced.
4. **Local-First Storage** — settings, history and caches live in the app's private storage tiers and are fully clearable.

---

## Legal Disclaimer

This app embeds FFmpeg libraries (LGPL/GPL components) via PyAV (BSD-3-Clause). You are solely responsible for ensuring your use of converted media complies with applicable copyright law and the terms of service of any platform you share content to. The authors take no responsibility for misuse of this tool.

---

## Credits

- **Media engine:** [PyAV](https://github.com/PyAV-Org/PyAV) (BSD-3) — Pythonic bindings for [FFmpeg](https://ffmpeg.org/)
- **UI:** [Flet](https://flet.dev) 1.0 (Flutter engine)
- **Mobile wheels:** Flet's binary index [pypi.flet.dev](https://pypi.flet.dev) (Mobile Forge)
