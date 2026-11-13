# Mobile FFmpeg capability gaps — status

The wrap's capability floor is the FFmpeg build we ship
(`scripts/build_ffmpeg_android.sh`). This tracks what the build includes, what
was added, and what is deliberately still open — updated whenever the build
changes.

## Closed in this pass (FFmpeg 9.0.2, API 24, 3 ABIs)

| Capability | How |
|---|---|
| H.264 encode | libx264 (GPL) |
| H.265/HEVC encode | libx265 (GPL) |
| VP8/VP9 encode | libvpx |
| AV1 encode | libaom + SVT-AV1 (**new** — overlay) |
| AV1 decode | libdav1d + libaom |
| MP3 encode | libmp3lame |
| AAC/Opus/FLAC/ALAC/PCM | FFmpeg native + libopus |
| **Vorbis encode (`.ogg`/`.oga`)** | **libogg + libvorbis (new — overlay)** |
| WebP encode | libwebp |
| Subtitles demux/decode | FFmpeg native + libxml2 |
| TLS (https/tls/hls-encrypted) | mbedtls |
| Bluray/DVD demux | libbluray/libdvdnav/libdvdread (fam free set) |
| 16 KB page alignment | `-Wl,-z,max-page-size=16384` |

### Overlay (this pass)

`scripts/ffmpeg-android-maker-ext/` adds three libraries the harness lacked,
each pinned by sha256:

- `libogg 1.3.5` — dependency of libvorbis, built first; FFmpeg has no
  `--enable-libogg`, so `apply.sh` wires it as build-only.
- `libvorbis 1.3.7` — Vorbis encoder (`--enable-libvorbis`).
- `SVT-AV1 v4.0.1` — AV1 encoder (`--enable-libsvtav1`).

`apply.sh` copies the recipes into the pinned ffmpeg-android-maker clone,
registers them in `parse-arguments.sh`, skips the `--enable-libogg` configure
flag, and puts the external pkg-config dir on the search path. The packager
gate (`REQUIRED_CONFIGURE_TOKENS`) now demands `libvorbis`/`libsvtav1` in the
built configure string, so a silently reduced build cannot ship.

## Still open (documented, not yet in the build)

| Gap | Why open | Path |
|---|---|---|
| **Subtitle burn-in (libass + `subtitles`/`ass` filters)** | libass needs a font stack: freetype + fribidi (already in fam) + **harfbuzz** + **fontconfig** (needs expat) — a 4-library dependency chain | Add `harfbuzz`, `fontconfig`(+expat), `libass` recipes to the overlay; enable `--enable-libass --enable-libfontconfig` |
| **rav1e (AV1 encoder)** | Rust toolchain in CI | Build with cargo/`--target` per ABI; AV1 encode already covered by libaom + SVT-AV1 |
| **OpenSSL** | Redundant: TLS is covered by mbedtls (fam free set); ffmpeg-android-maker has no openssl recipe | Not planned; mbedtls covers https/tls/hls-encrypted |
| **Hardware decode/encode (mediacodec, vulkan, opencl)** | `--disable-autodetect` drops them; mediacodec also needs a JavaVM handle that PyAV does not hold, so the codec would register but never initialize; vulkan/opencl are not drivable from PyAV on Android today | The app's hardware-decode setting keeps probe-gating to what the wheel actually supports (currently none); enabling mediacodec would only change the probe, not real capability — revisit with a JNI bridge |
| **libvmaf, libzimg, libzmq, libssh, libsrt, libv4l, libvidstab, libmysofa, libplacebo, libjxl, libopencore-amr, gme, rubberband, ocl-icd, xvidcore, libtheora** | Termux builds them; ffmpeg-android-maker lacks recipes | Add recipes as demand dictates; they extend filters/muxers, not core codecs |

## App-side gaps that follow from this

- `src/screens/engine_info_screen.py` header is derived from `av.ffmpeg_version_info`
  (no hardcoded "FFmpeg 8").
- The probe (`engine_probe.py`) now enumerates the full wheel — new encoders
  appear automatically in Engine Info, Convert and the format pickers; the
  display tables still need Phase 4's derived rendering for the long tail.
- HTTPS: the app still fetches HLS via httpx (Phase 5 deletes that once the
  native TLS path is the only one); plain `https://` via `av.open` now works.