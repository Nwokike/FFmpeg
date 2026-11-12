# Third-Party Sources — FFmpeg AV

This application incorporates third-party software components licensed under free and
open-source software licenses, including the GNU General Public License (GPL).

## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))

The complete machine-readable Corresponding Source for the GPL-licensed components
and for this application is available at:
https://github.com/Nwokike/FFmpeg
and via GitHub Releases at: https://github.com/Nwokike/FFmpeg/releases/latest

This offer is valid for at least three (3) years from the date of release to any third
party for no charge other than the cost of physically performing source distribution.
To request source code via durable physical medium, contact: contact@kiri.ng

## Native Payload (Packaged in flet-libffmpeg)

FFmpeg 9.0.2 and its statically-linked external codec libraries are
cross-built for Android at API level 24 with 16 KiB PT_LOAD alignment.

- FFmpeg 9.0.2: [https://www.ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz](https://www.ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz)
- SHA-256: `8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e`
- Cross-build harness: [https://github.com/Javernaut/ffmpeg-android-maker](https://github.com/Javernaut/ffmpeg-android-maker) at commit `dd72b161ae5c759fd25a5cab971a3ff710f0bdba`
  (each external library's exact download URL and hash is pinned in that
  commit's `scripts/<library>/download.sh`; verification runs at build time
  and the built payload's configure string is checked for every encoder)

| Component | License | Upstream |
|---|---|---|
| `FFmpeg` | GPL-3.0-or-later | [FFmpeg](https://ffmpeg.org) |
| `x264` | GPL-2.0-or-later | [x264](https://code.videolan.org/videolan/x264) |
| `x265` | GPL-2.0-or-later | [x265](https://bitbucket.org/multicoreware/x265_git) |
| `libvpx` | BSD-3-Clause | [libvpx](https://chromium.googlesource.com/webm/libvpx) |
| `libaom` | BSD-3-Clause | [libaom](https://aomedia.googlesource.com/aom) |
| `libdav1d` | BSD-2-Clause | [libdav1d](https://code.videolan.org/videolan/dav1d) |
| `libmp3lame` | LGPL-2.0-or-later | [libmp3lame](https://lame.sourceforge.net) |
| `libopus` | BSD-3-Clause | [libopus](https://opus-codec.org) |
| `libspeex` | BSD-3-Clause | [libspeex](https://speex.org) |
| `libtwolame` | LGPL-2.1-or-later | [libtwolame](https://www.twolame.org) |
| `libwebp` | BSD-3-Clause | [libwebp](https://developers.google.com/speed/webp) |
| `libfreetype` | FTL / GPL-2.0-or-later | [libfreetype](https://freetype.org) |
| `libfribidi` | LGPL-2.1-or-later | [libfribidi](https://github.com/fribidi/fribidi) |
| `mbedtls` | Apache-2.0 / GPL-2.0-or-later | [mbedtls](https://www.trustedfirmware.org/projects/mbed-tls) |
| `libbluray` | LGPL-2.1-or-later | [libbluray](https://www.videolan.org/developers/libbluray.html) |
| `libxml2` | MIT | [libxml2](https://gitlab.gnome.org/GNOME/libxml2) |

## Python Dependencies

| Package | License | Upstream |
|---|---|---|
| `av` (PyAV) | LGPL-2.1-or-later (binding) / GPL-3.0-or-later (combined payload) | https://github.com/PyAV-Org/PyAV |
| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-audio` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-audio-recorder` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-camera` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-permission-handler` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-video` | Apache-2.0 | https://github.com/flet-dev/flet |
| `httpx` | BSD-3-Clause | https://github.com/encode/httpx |

## License Texts

Complete license texts for all included software components are provided in the
`LICENSES/` directory and within the app under Settings → Open-Source Licenses.

