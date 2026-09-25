<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="src/assets/icon_white.svg">
    <source media="(prefers-color-scheme: light)" srcset="src/assets/icon.svg">
    <img src="src/assets/icon.svg" alt="FFmpeg Lite" width="320" />
  </picture>
</p>

<p align="center">
  FFmpeg Lite — on-device media studio built on FFmpeg 8. Cut, join, extract, remux and master audio on-device, with a UI that only offers what your device really supports.
</p>

<p align="center">
  <a href="https://play.google.com/store/apps/details?id=ng.kiri.ffmpeg"><img src="https://img.shields.io/badge/Google_Play-Android-3DDC84?style=for-the-badge&logo=google-play&logoColor=white" alt="Google Play Store" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download-APK-orange?style=for-the-badge&logo=android&logoColor=white" alt="Download APK" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download_Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" /></a>
  <a href="https://github.com/Nwokike/FFmpeg/releases/latest"><img src="https://img.shields.io/badge/Download_Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" /></a>
  <img src="https://img.shields.io/badge/Built%20with-Flet%201.0.1-00B0FF?style=for-the-badge&logo=flutter&logoColor=white" alt="Flet" />
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
</p>

---

## Download

| Platform | Download | Notes |
| :---: | :---: | :--- |
| 🤖 **Android** | [![Play Store](https://img.shields.io/badge/Google_Play-414141?style=flat-square&logo=google-play&logoColor=white)](https://play.google.com/store/apps/details?id=ng.kiri.ffmpeg) | Recommended for Android users |
| 🪟 **Windows** | [![Windows Release](https://img.shields.io/badge/Download_Windows_Release-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg_Lite.exe) | Automated standalone setup installer with desktop shortcut integration |
| 🐧 **Linux (Debian/Ubuntu)** | [![Linux DEB](https://img.shields.io/badge/Download_Linux_DEB-FCC624?style=flat-square&logo=linux&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg_Lite.deb) | Desktop package tailored for Ubuntu, Debian, Linux Mint & Pop!_OS |
| 🎩 **Linux (Fedora/RHEL)** | [![Linux RPM](https://img.shields.io/badge/Download_Linux_RPM-E91E63?style=flat-square&logo=redhat&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg_Lite.rpm) | Desktop package tailored for Fedora, openSUSE, RHEL & CentOS |
| 📦 **Linux (Universal Portable)** | [![Linux TAR.GZ](https://img.shields.io/badge/Download_Linux_TAR.GZ-9C27B0?style=flat-square&logo=linux&logoColor=white)](https://github.com/Nwokike/FFmpeg/releases/latest/download/FFmpeg_Lite.tar.gz) | Universal standalone portable archive for Arch, Alpine, Steam Deck & all distros |

### Android Architecture Build Splits

| Variant | Download | Notes |
| :---: | :---: | :--- |
| 📱 **ARM64** (most phones) | [**ffmpeg-arm64-v8a.apk**](https://github.com/Nwokike/FFmpeg/releases/latest/download/ffmpeg-arm64-v8a.apk) | Modern 64-bit Android devices |
| 💻 **x86_64** (emulators) | [**ffmpeg-x86_64.apk**](https://github.com/Nwokike/FFmpeg/releases/latest/download/ffmpeg-x86_64.apk) | Android emulators and Chromebooks |
| 📱 **ARMv7** (32-bit phones) | [**ffmpeg-armeabi-v7a.apk**](https://github.com/Nwokike/FFmpeg/releases/latest/download/ffmpeg-armeabi-v7a.apk) | Older 32-bit Android devices |

---

## Core Capabilities

Every option in the UI is gated on a **live capability probe** of the installed engine. On Android, Flet's official PyAV wheel is built LGPL-only, so the app offers FFmpeg's own LGPL encoders (MPEG-4, MJPEG, PNG, GIF, AAC, FLAC, PCM) plus lossless stream-copy — and it hides what that wheel cannot do instead of failing after you tap a button.

| Capability | Description |
| :--- | :--- |
| **Measured FFmpeg Engine** | Every codec, container, filter and protocol is enumerated from the installed build at runtime and surfaced in Engine Info — the UI never advertises a feature this device cannot run. |
| **Convert & Compress** | Container-to-container conversion with the encoders this build ships, target file size ("small enough for WhatsApp/Telegram"), bitrate/CRF controls. |
| **Cut / Trim & Join** | Instant keyframe-accurate stream-copy cuts, frame-accurate re-encode when the engine provides an encoder, lossless merge, and optional crossfade. |
| **Extract** | Audio in the formats this build can encode (AAC/M4A/FLAC/WAV), frame extraction, palette-optimized GIFs, and SRT/ASS/WebVTT subtitles. |
| **Filters** | Crop, scale, rotate/flip, speed (atempo), volume, denoise, sharpen, image watermark overlay — gated on the build's filter set. |
| **Audio Studio** | Loudness normalization (two-pass, use-case presets), resampling (incl. soxr), channel mixing, and playback-speed export. |
| **Capture** | In-app camera video/still capture and microphone recording — straight into the conversion pipeline. |
| **Live Streams** | HTTP stream recording on-device. HTTPS/HLS bytes are downloaded through the app's own network stack and handed to PyAV, because the mobile engine has no TLS protocol handler. |
| **Batch Jobs** | Multi-file queue with per-job progress, cancel, pause and a jobs banner that survives tab switches. |
| **Media Dossier** | Probe any file: streams, codecs, bitrates, dimensions, rotation, language, chapters — with a raw container summary and a shareable markdown report. Includes lossless track-picker copies (drop audio/subtitle tracks without re-encoding). |
| **Share & Save** | Save to Downloads/Movies via the system picker, or push outputs to any app via the system share sheet. |

---

## Architecture

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | Flet 1.0 (Flutter engine) | Cross-platform UI — Material 3 themes, adaptive video controls, on-demand lists, chip-and-slider filter stacks |
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
        UI["🎨 Flet 1.0 UI (Home | Capture | Convert | Compress | Cut | Extract | Filters | Audio | Join | Streams | Probe | Batch | History | Settings)"]
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

## Screenshots

The release screenshots are kept in [`screenshots/`](screenshots/) and should be refreshed whenever the main navigation or Settings surface changes.

![FFmpeg home in dark mode](screenshots/home_dark.png)

## Production release status

`v1.0.0` is prepared as a closed-testing release. It intentionally uses Google test AdMob units while the AdMob production account is being finalized. Test units are not a public-production configuration; swap all IDs with [`tools/admob.py`](tools/admob.py) before the Play production release.

The release workflow blocks test IDs on later production tags, runs the locked test suite, validates version/build identity, builds mobile wheels without hiding failures, and checks that development-only files do not enter Android artifacts.

## Development and release checks

```text
uv sync --frozen
uv run pytest -m "not live"
uv run ruff check .
uv run ruff format --check .
uv run python tools/check_release_consistency.py
uv run flet run -v
uv run --frozen flet build apk --python-version 3.14 --split-per-abi -v
```

The CLI engine audit outputs used during the v1.0.0 preparation are kept outside Git in `audit-output/` so they can be inspected and deleted without affecting the repository.

## Privacy & Security

1. **On-Device Processing** — media never leaves your phone; no cloud uploads, ever.
2. **Minimal Network Use** — the only network calls are update checks, in-app ads (AdMob, with startup UMP consent where required), and stream capture when you explicitly provide a URL. No analytics, no crash reporting, no media uploads.
3. **Data Sovereignty** — outputs are written where you choose via the system picker or share sheet; nothing is auto-synced.
4. **Local-First Storage** — settings, history and caches live in the app's private storage tiers and are fully clearable.

---

## Legal Disclaimer

This app embeds FFmpeg libraries (LGPL/GPL components) via PyAV (BSD-3-Clause). You are solely responsible for ensuring your use of converted media complies with applicable copyright law and the terms of service of any platform you share content to. The authors take no responsibility for misuse of this tool.

---

## License

MIT © 2025-2026 Nwokike. See [`LICENSE`](LICENSE).

## Credits

- **Media engine:** [PyAV](https://github.com/PyAV-Org/PyAV) (BSD-3) — Pythonic bindings for [FFmpeg](https://ffmpeg.org/)
- **UI:** [Flet](https://flet.dev) 1.0 (Flutter engine)
- **Mobile wheels:** Flet's binary index [pypi.flet.dev](https://pypi.flet.dev) (Mobile Forge)
