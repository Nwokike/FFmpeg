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
| AV1 encode | libaom |
| AV1 decode | libdav1d + libaom |
| MP3 encode | libmp3lame |
| AAC/Opus/FLAC/ALAC/PCM | FFmpeg native + libopus |
| WebP encode | libwebp |
| drawtext + bidi text | libfreetype + libfribidi |
| Vorbis decode | FFmpeg native |
| TLS (https/tls/hls-encrypted) | mbedtls |
| 16 KB page alignment | `-Wl,-z,max-page-size=16384` |

### Component set (lean, no overlay)

`scripts/wrap_pins.py` (`FAM_ARGS`) enables exactly these external libraries
and no others; every one is built static and folded into the seven `libav*.so`,
so the wheels ship no companion `.so` closure:

- GPL: `libx264`, `libx265` (`--enable-all-gpl` also sets `--enable-gpl`)
- Free: `libaom`, `libdav1d`, `libmp3lame`, `libopus`, `libvpx`, `libwebp`,
  `libfreetype`, `libfribidi`, `mbedtls`

The packager gate (`REQUIRED_CONFIGURE_TOKENS`) demands exactly this set in the
built configure string, so a silently reduced build cannot ship.

Dropped on purpose (size, not capability-critical): `libvorbis`/`libogg`
(lossy audio encode is covered by AAC/Opus/MP3; Vorbis decode stays native),
`svt-av1` (AV1 encode covered by libaom), `libbluray`, `libxml2` (DASH/ISM —
the app handles HLS), `libtwolame`, `libspeex`.

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
- The probe (`engine_probe.py`) enumerates the full wheel — new encoders appear
  automatically in Engine Info, Convert and the format pickers. **Closed in
  Phase 4:** every encoder setting is reachable too — the advanced panel renders
  the measured AVOption schema (typed controls, per-option help, search) and the
  values are applied to the encoder and the muxer.
- Muxer options are the one surface av cannot enumerate (an `OutputContainer`'s
  `options` is only what you passed), so they are entered as key/value pairs and
  validated by FFmpeg at mux time — a gap in the library, not the app.
- HTTPS: the app still fetches HLS via httpx (Phase 5 deletes that once the
  native TLS path is the only one); plain `https://` via `av.open` now works.