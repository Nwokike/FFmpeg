# FFmpeg app — 1:1 av wrap plan

Status: research complete. This is the plan to proceed. No implementation yet.

## The goal in one line

The app declares a flat dependency on `av`, a wrap pipeline ships the full
FFmpeg/av wheels to mobile, and the app exposes whatever the installed `av`
can do — every option, every codec, every filter — derived from the wheel at
runtime, with no hardcoded tables, no version branches, no platform forks, and
no workarounds.

Two workstreams:

- **A. The wrap pipeline** — build a full FFmpeg + matching `av` for Android,
  hand them to `flet build` through `PIP_FIND_LINKS`. The version pairing lives
  here, pinned like proot-distro's `_PINNED_SOURCES`, never in the app.
- **B. The 1:1 wrapper** — replace the hand-written engine and hardcoded
  screens with a capability schema + generic job model + generic controls that
  are generated from `av` at runtime.

---

# Part A — the wrap pipeline

## A1. What Flet ships today (evidence, verified from the wheels)

- `flet-libffmpeg 8.1.2` (pypi.flet.dev): bare LGPL build — configure line is
  `--disable-autodetect --disable-iconv --enable-zlib`, `DT_NEEDED` is only
  `libav*/libz/libm/libc`. No x264/x265/vpx/aom/mp3lame/opus/vorbis/ass/TLS.
- `av 18.1.0` (pypi.flet.dev): 49 Cython modules whose `DT_NEEDED` is the seven
  `libav*.so` by basename, resolved from `jniLibs/<abi>/`. Its
  `Requires-Dist: flet-libffmpeg (==8.1.2)` is the only pairing constraint.
- `pypi.flet.dev` has **no** `flet-libx264/x265/vpx/aom/svtav1`. So the "Lite"
  floor was a licensing choice, not a technical limit.
- The PyPI `av` wheel (desktop) bundles FFmpeg 9.0.2 with the full feature set
  (`libx264, libx265, libvpx, libSvtAv1Enc, libdav1d, libmp3lame, libopus,
  libvmaf, libvpl, libwebp, libgnutls…`). The canonical build config is
  `PyAV-Org/pyav-ffmpeg`.

## A2. Build the mobile wheels

1. **FFmpeg 9.0.2 for Android** (`arm64-v8a`, `armeabi-v7a`, `x86_64`) with the
   PyAV feature set. Two ways:
   - `ffmpeg-android-maker --source-tar=9.0.2 --enable-all-free --enable-all-gpl`
     (plus `libsvtav1`, `libass`, `libvorbis`; `mbedtls` or `openssl` for TLS).
     External libs are built static and folded into `libavcodec.so`, so the
     output is just the seven `libav*.so`, unversioned, 16 KB aligned, no text
     relocations.
   - Or repackage Termux's FFmpeg 9.0.2 debs (aarch64/arm/x86_64, GPL-3.0,
     16 KB aligned) with `elf_tools.py` soname rewrites — the proot pattern.
2. **Package as a wheel** in the `opt/lib` layout, exactly like `flet-libffmpeg`:
   `flet_libffmpeg-9.0.2-1-py3-none-android_24_<abi>.whl`. Script adapted from
   `proot-distro-flet/scripts/build_flet_proot_wheel.py`: sha256 pins, ELF
   alignment check, license texts, `THIRD-PARTY-SOURCES.md`.
3. **Build `av 19.0.2` for Android against it.** Fork mobile-forge's `av`
   recipe: version `19.0.2`, host dep `flet-libffmpeg ==9.0.2`. Build with
   `forge android av` for Python 3.14 per ABI (mobile-forge's CI has a
   `prebuild_recipes` input that seeds `dist/` for exactly this).
4. **Wire it up.** The app's flat `av` requirement resolves to our wheel
   (19.0.2 > pypi.flet.dev's 18.1.0), whose metadata pulls
   `flet-libffmpeg==9.0.2` from find-links. CI:
   ```yaml
   PIP_FIND_LINKS: ${{ github.workspace }}/wheels
   ```
   Flet's documented mechanism for self-built wheels.

## A3. Maintenance

Upstream release → bump the wrap script's pin → rebuild wheels → `uv lock
--upgrade` → fix any API changes in the app. The app's dependency list never
changes.

---

# Part B — the 1:1 wrapper

## B1. What av actually exposes (measured, av 19.0.2)

Everything below is live from the installed wheel — this is the surface the
app must expose, not a hardcoded subset:

| Area | Surface |
|---|---|
| **Entry** | `av.open(file, mode, format, options, container_options, io_open, timeout, hwaccel)` |
| **Enumerations** | `codecs_available` (553), `filters_available` (455), `formats_available` (418), `bitstream_filters_available` (50), `library_versions`, `ffmpeg_version_info`, `enumerate_input_devices` / `enumerate_output_devices`, `hwdevices_available` |
| **Container** | `.format`, `.streams`, `.metadata`, `.options`, `.container_options`, `.flags`, `.chapters()` / `.set_chapters()`, `InputContainer.decode/demux/seek`, `OutputContainer.add_stream / add_stream_from_template / add_mux_stream / add_attachment / add_data_stream / mux / mux_one / start_encoding / default_*_codec / supported_codecs` |
| **Stream** | `.codec_context`, `.type`, `.time_base`, `.duration`, `.metadata`, `.disposition`, `.discard`, `.language`, `.profile(s)`, `.frames`, `.index_entries`; Video adds `.average_rate / base_rate / guessed_rate / sample_aspect_ratio / display_aspect_ratio / set_display_matrix / set_display_rotation` |
| **Codec** | `.name / long_name / type / mode / frame_rates / audio_rates / video_formats / audio_formats / hardware_configs / capabilities / properties / intra_only / lossless / lossy / experimental` |
| **CodecContext** | `.supported_options` (`generic` + `private`), `.options`, `.flags / flags2`, `.thread_count / thread_type`, `.time_base`, `.profile / level`, `.open(strict)`, `.encode / decode / encode_lazy / parse / flush_buffers`, `.is_hwaccel`; Video adds `width/height/pix_fmt/gop_size/max_b_frames/qmin/qmax/refs/framerate/color_* /sample_aspect_ratio`; Audio adds `rate/format/layout/frame_size/channels` |
| **Codec options** | `CodecOption(name, type, choices, default, min, max, help, flags, is_array)` — a ready-made option schema with per-option help text |
| **Frames** | Video: `.reformat / to_rgb / to_image / to_ndarray / from_ndarray / from_image / from_bytes / from_dlpack / save / make_writable / side_data / pict_type / color_* / rotation / interlaced_frame`; Audio: `.from/to_ndarray`, `.planes` |
| **Packets** | `.pts / dts / duration / time_base / is_keyframe / is_corrupt / rescale_ts / sidedata (33 types) / stream_index` |
| **Filters** | `Graph.add / add_buffer / add_abuffer / configure / link_nodes / push / pull / vpush / vpull / set_audio_frame_size`; `Filter.description / flags / inputs / outputs`; `FilterContext.init / link_to / process_command / push / pull` |
| **Resample/FIFO** | `AudioResampler(format, layout, rate, options, threads)`, `AudioFifo.write/read/read_many` |
| **Reformatter** | `VideoReformatter.reformat(...)` with interpolation/colorspace/range enums |
| **Subtitles** | `SubtitleSet(pts, rects, start/end_display_time, format, create)`, `AssSubtitle.ass/dialogue/text`, `BitmapSubtitle.planes/x/y/w/h` |
| **Sidedata** | 33 `Type`s incl. `DISPLAYMATRIX`, `MASTERING_DISPLAY_METADATA`, `DOVI_METADATA`, `MOTION_VECTORS`, `VIDEO_ENC_PARAMS` |
| **Devices** | `enumerate_input_devices / enumerate_output_devices` → `DeviceInfo` |
| **Logging** | `set_level / set_libav_level / get_level / set_skip_repeated / get_last_error / log / Capture` |
| **Errors** | 60+ typed exceptions (`DecoderNotFoundError`, `ProtocolNotFoundError`, `InvalidDataError`, `HTTP*Error`…) + `ErrorType` + `err_check` |
| **Formats** | `ContainerFormat(name, long_name, extensions, flags, is_input/is_output, no_file)`, per-muxer `default_video_codec` (mp4→h264/aac), `default_audio_codec` (mkv→ac3), `default_subtitle_codec` (mkv→ass/webvtt), `supported_codecs` (mkv→113, avi→245, mov→155) |
| **Bitstream** | `BitStreamFilterContext.filter / flush` |

## B2. The capability schema (replaces every hardcoded table)

One module builds a schema from the wheel, cached on the FFmpeg build identity
(the existing `_ffmpeg_build_identity()` cache key is the single best idea in
the current code — keep it):

- **codecs**: every `codecs_available` name split by `Codec(name,"w"/"r")` into
  encoder/decoder, with type, modes, rates, formats, hw configs, lossless/
  intra-only/experimental, and the full `CodecOption` list (name/type/choices/
  default/min/max/help/flags) for both generic and private options.
- **filters**: every `filters_available` name with description, flags, pads, and
  option schema.
- **muxers/demuxers**: every `formats_available` entry with `is_input/is_output`,
  extensions, default codecs, `supported_codecs`, and options.
- **protocols**: dead-port probe (the existing `_probe_protocol`) → present/
  missing.
- **devices, bitstream filters, pixel/sample formats, layouts, hw devices**.

Deletions this enables (all verified hardcoded today):

- `engine_probe.py:34-112` `REQUIRED_FILTERS / OPTIONAL_FILTERS /
  PREFERRED_VIDEO_ENCODERS / PREFERRED_AUDIO_ENCODERS / PROTOCOLS` — the probe
  currently measures a preference list instead of enumerating the wheel.
- `engine_probe.py:279-287` `AUDIO_FORMAT_ENCODERS`, `:476` the fixed muxer
  probe list.
- `engine_service.py:176-245` codec alias/label maps;
  `:294-346` `_CONTAINER_CODEC_MATRIX` (derive from `supported_codecs` +
  `default_*_codec`); `:262` preferred pix-fmt tuple; `:276-286` the vorbis
  `strict=-2` wheel workaround; `:566-570` the hw decoder preference list;
  `:728-748` `_DISPOSITION_FLAG_NAMES` (derive from `av.stream.Disposition`).
- The four duplicated `_VIDEO_LABELS` maps (`compress_screen.py:52`,
  `cut_screen.py:81`, `join_screen.py:57`, `engine_service.py:211`), the two
  `_WM_POSITIONS` maps, and the three extension-set tables.
- `convert_screen.py:26-165` container/codec/choice tables;
  `compress_screen.py:75-87` presets; `audio_screen.py:28-95` loudness/bitrate/
  rate lists; `extract_screen.py:187-414` formats and GIF caps;
  `join_screen.py:31-138` containers/fades/caps; `streams_screen.py:54-138`
  formats; `filters_screen.py:30-103` aspects/levels/positions/backend order;
  `probe_screen.py:38-58` disposition labels;
  `result_screen.py:35-370` extension sets; `home_screen.py:45-117` tool list;
  `main.py:497-506, 631-753` tool capabilities and dispatch defaults.

Labels are display-only concerns: a single label map (proper name → human
label) is acceptable, but option *keys* must come from the schema.

## B3. The generic engine (replaces the hand-written ops)

`engine_service.py` (4,265 lines) hand-builds filter graphs, mux loops,
timestamp rebasing, loudnorm two-pass, crossfade ramps, an HLS parser, subtitle
writers, and an MJPEG thumbnailer — four copies of the same monotonic-PTS loop,
a `_MuxClamp` for a muxer EINVAL, and per-op stream-copy rebasing. A 1:1 wrap
replaces all of it with a schema-driven job model:

```
Job = InputSpec        (path/URL, open options, seek, hwaccel, discard)
    + StreamSpec[]     (map/drop/attach per stream, codec, encoder options,
                       bit_rate, pix_fmt, rate, layout, disposition, metadata)
    + GraphSpec[]      (filter name + option dict per stream, or a chain)
    + OutputSpec       (muxer, container options, chapters, metadata, flags)
```

One builder maps `Job` → `av.open` + `add_stream` + `Graph` + `mux`. av owns
the timestamps; the app keeps only the minimum clock fixups the muxer genuinely
requires, implemented once instead of four times. Everything else is a
parameter in the schema.

Existing ops become presets over the same model: `compress` is
`bit_rate + scale`, `cut` is `seek + duration + stream_copy`, `extract_audio`
is `drop_video + codec`, `gif` is `fps/scale/palettegen-paletteuse`, `remux` is
`stream_copy + drop`, `concat` is multiple inputs + a transition descriptor.
None of them is a bespoke code path any more.

Additional engine-level decisions:

- **TLS**: once the wheel ships TLS, delete the httpx download path
  (`engine_service.py:3724-3836, 3948-4052`, `streams_screen.py:143-176`).
  Keep an optional fetch for HLS progress/cancel if wanted, but never as a
  silent substitute.
- **CLI emulation**: `command_parser.py` (800 lines, hardcoded flag/filter/
  codec/refusal tables) is an emulation layer over the app's own ops. A 1:1
  wrap either passes real FFmpeg option syntax to `av`'s option system or drops
  command mode.
- **Containment**: a native segfault cannot be caught in-process. Run jobs in a
  worker process so a bad input does not kill the app (the proot pattern:
  spawn + PTY + crash reporting).
- **Errors**: use av's typed exception hierarchy for job failure cards instead
  of string matching.

## B4. The generic UI

- One control factory renders any `CodecOption`/filter option: type 6
  (string with choices) → dropdown, 3/5 (int/float) → slider with min/max and
  default, 18 (bool) → switch, others → text field with help text.
- Codec pickers, container pickers, filter pickers, disposition badges, stream
  tables: all rendered from the schema. A new codec in the wheel appears
  without an app change — the same property DDGS gets from `ddgs.engines.ENGINES`.
- Validation at both boundaries (the DDGS pattern): saved specs filtered through
  the live schema on load, job params filtered at build time.
- Surface tests: assert the exposed option set **equals** the installed wheel's
  set (proot's `test_proot_surfaces.py` model), and an AST/source test that
  fails if a hardcoded codec/filter literal reappears in `src/`.

## B5. Platform layer

Platform branching stays out of the engine: file picking (SAF), saving,
sharing, capture (camera/mic), ads, and notifications are the host layer and
may branch. The engine must be platform-blind — the same `Job` runs on desktop
and Android. Storage tiers (`FLET_APP_STORAGE_*`) and the TLS/CA setup remain
platform-layer concerns.

---

# Part C — phases

Product decision: the app is renamed **FFmpeg Lite → FFmpeg AV**. The generic engine that Phase 3 builds is documented separately in [docs/engine-architecture.md](engine-architecture.md). The wrap is
1:1 against `av`; the name follows the wrapped library.

## Phase 1 — FFmpeg AV on the full mobile FFmpeg

Make the app run as FFmpeg AV on a full FFmpeg wheel:

- Rename product, boot message, description, changelog entry, README, App Store
  copy; decide whether the Android bundle id changes (Play identity) or stays.
- Fix the av-19 fallout (rational attributes → `av.AVRational`; `is None`
  checks) so the app runs on the latest `av`.
- Build the full FFmpeg 9.0.2 Android libs (`arm64-v8a`, `armeabi-v7a`,
  `x86_64`) and package `flet_libffmpeg-9.0.2` wheels.
- Build `av 19.0.2` Android wheels against them (mobile-forge recipe fork).
- CI: build wheels → `PIP_FIND_LINKS` → `flet build apk --split-per-abi`;
  verify ELF alignment and that the device probe reports the full encoder set.
- Deliverable: an FFmpeg AV APK whose engine reports libx264/libx265/libvpx/
  libaom/libmp3lame/libopus/libvorbis on device.

## Phase 2 — Capability schema

Replace the hardcoded tables with a schema generated from the wheel:

- Enumerate codecs (split encoder/decoder by mode), filters, muxers/demuxers,
  protocols, devices, bitstream filters, hw devices; cache on the FFmpeg build
  identity.
- `CodecOption(name, type, choices, default, min, max, help, flags)` becomes
  the app's option descriptor.
- Delete `engine_probe.py:34-112` preference lists, `:279-287`, `:476`;
  `engine_service.py:176-346` alias/label/matrix tables; the duplicated
  `_VIDEO_LABELS` / `_WM_POSITIONS` maps.
- Surface tests: exposed set == installed set.

## Phase 3 — Generic engine

- `Job = InputSpec + StreamSpec[] + GraphSpec[] + OutputSpec`; one builder maps
  it onto `av.open` / `add_stream` / `Graph` / `mux`.
- Port the ten ops onto it as presets; delete the four copies of the
  monotonic-PTS loop, `_MuxClamp`, per-op rebasing, the HLS parser, the
  subtitle writers, and the MJPEG thumbnailer.
- Run jobs in a worker process (native-crash containment).
- Typed error cards from av's exception hierarchy.

## Phase 4 — Generic UI

- One control factory renders any `CodecOption`/filter option. **(done)**
  `components/encoder_options.py`: `EncoderOptionPanel` renders every option the
  installed wheel declares for the chosen encoder — typed controls, help text,
  search, and a "this encoder / all options" switch; `ContainerOptionRows` is
  the free-form muxer key/value surface (av exposes no muxer option list).
- Option values are applied, not just displayed. **(done)** They reach the
  encoder through `_supported_encoder_options` (generic ∪ private, wire
  strings) and the muxer through `OutputSpec.options`; unsupported keys drop
  with one info line. Measured while building this: the old private-only filter
  silently dropped `b`/`g`/`bf`/`threads`/`qmin`, and av rejects non-`str`
  option values — both fixed.
- Panels wired into Convert (video + audio encoders, muxer), Compress, Cut
  (re-encode), Audio Studio and Extract (audio/gif). **(done)**
- Codec/container pickers render from the schema; `containers_for_kind()`
  replaces the convert screen's hardcoded container tables. **(done)**
- Validation at the storage-load and job-build boundaries. Filter pickers,
  disposition badges and stream tables are already probe-driven; what remains is
  a saved-spec re-validation pass on load (Phase 5).

## Phase 5 — Cleanup

- Delete `command_parser.py` (CLI emulation) or turn it into a real option
  passthrough.
- Delete the httpx HTTPS substitution once TLS is in the wheel.
- Delete version literals (`terminal_screen.py:165`, `changelog.py:9`,
  `versions.py` fallbacks, `README.md:165`).
- Final surface tests; docs reflect FFmpeg AV.

## Risks

| Risk | Note |
|---|---|
| GPL | x264/x265 make the shipped wheel GPL; source offer + license texts required (proot already ships GPL). LGPL+BSD alternative exists (OpenH264/libvpx/libaom) but loses HEVC encode. |
| av API churn | av 19 already changed rational types and removed `hwaccel`. The schema is read at runtime, so drift is visible immediately rather than silently. |
| Building av for Android | mobile-forge's recipe is the path; the FFmpeg build is the long pole (external libs per ABI). |
| Job-model rewrite | the ten ops must keep their current UX while moving onto the generic model; presets, not forking. |
| Subprocess containment | changes job plumbing; do it once, behind the queue. |
