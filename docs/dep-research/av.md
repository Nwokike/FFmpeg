# av (PyAV) 18.1.0 — Complete API Reference

> Package purpose: Pythonic Cython bindings for the FFmpeg libraries (libavformat / libavcodec / libavfilter / libavdevice / libavutil / libswscale / libswresample). Containers, streams, packets, codecs, frames, filters. Version under test: **18.1.0**, built against **FFmpeg 8.1.2**. Binary wheel bundles FFmpeg — zero runtime Python dependencies.
> Measured on this machine: 557 codecs, 468 filters, 414 formats, 49 bitstream filters in this wheel. `av.time_base == 1000000`.
> Rule for the rewrite: if the `ffmpeg` CLI does the job, prefer it; use PyAV only where frame-level control is required.

---

## Files

Package dir (read-only): `<repo>\.venv\Lib\site-packages\av`

- 111 `.py`/`.pyi` files total (excluding `__pycache__`/`*.pyc`).
- Every extension module follows the same triplet pattern:
  - `X.py` — Cython source shipped in the wheel (readable; this is the ground truth for behavior, docstrings, defaults). Almost every `.py` is `import cython` + `cython.cimports.libav` code: readable but not plain Python.
  - `X.pyd` — compiled C extension actually imported at runtime (30 `.pyd` files).
  - `X.pyi` — type stub documenting the compiled public API (34 `.pyi` files; `py.typed` present so type-checkers use them).
  - `X.pxd` — Cython declaration file (not a runtime API; skip unless writing Cython against PyAV).
- Where an API exists only in `.pyd`, this report derives signatures from the matching `.pyi` **plus** the `.py` source (which shows defaults, control flow, and side effects).

### Complete file list (grouped)

- Top level: `__init__.py`, `__init__.pxd`, `__main__.py` (`pyav` CLI), `_core.py/.pyd/.pyi/.pxd`, `about.py` (`__version__`), `datasets.py` (test-data downloader, irrelevant to app), `device.py/.pyd/.pyi`, `dictionary.py/.pyd/.pyi`, `error.py/.pyd/.pyi`, `format.py/.pyd/.pyi`, `frame.py/.pyd/.pyi`, `index.py/.pyd/.pyi`, `logging.py/.pyd/.pyi`, `opaque.py`, `packet.py/.pyd/.pyi`, `plane.py/.pyd/.pyi`, `rational.py/.pyd/.pyi`, `buffer.py/.pyd/.pyi`, `bitstream.py/.pyd/.pyi`, `utils.py/.pxd` (+ `.pyd`), `py.typed`
- `audio/`: `__init__.py/.pyi/.pxd`, `codeccontext.py/.pyd/.pyi/.pxd`, `fifo.py/.pyd/.pyi/.pxd`, `format.py/.pyd/.pyi/.pxd`, `frame.py/.pyd/.pyi/.pxd`, `layout.py/.pyd/.pyi/.pxd`, `plane.py/.pyd/.pyi/.pxd`, `resampler.py/.pyd/.pyi/.pxd`, `stream.py/.pyd/.pyi/.pxd`
- `video/`: `__init__.py/.pyi/.pxd`, `codeccontext.py/.pyd/.pyi/.pxd`, `format.py/.pyd/.pyi/.pxd`, `frame.py/.pyd/.pyi/.pxd`, `plane.py/.pyd/.pyi/.pxd`, `reformatter.py/.pyd/.pyi/.pxd`, `stream.py/.pyd/.pyi/.pxd`
- `codec/`: `__init__.py`, `codec.py/.pyd/.pyi/.pxd`, `context.py/.pyd/.pyi/.pxd`, `hwaccel.py/.pyd/.pyi/.pxd`
- `container/`: `__init__.py/.pyi/.pxd`, `core.py/.pyd/.pyi/.pxd`, `input.py/.pyd/.pyi/.pxd`, `output.py/.pyd/.pyi/.pxd`, `streams.py/.pyd/.pyi/.pxd`, `pyio.py/.pyd/.pxd` (no `.pyi` — internal custom-IO bridge)
- `filter/`: `__init__.py/.pyi/.pxd`, `context.py/.pyd/.pyi/.pxd`, `filter.py/.pyd/.pyi/.pxd`, `graph.py/.pyd/.pyi/.pxd`, `link.py/.pyd/.pyi/.pxd`, `loudnorm.py/.pyd/.pyi/.pxd`, `loudnorm_impl.c/.h`
- `sidedata/`: `__init__.py`, `sidedata.py/.pyd/.pyi/.pxd`, `motionvectors.py/.pyd/.pyi/.pxd`, `encparams.py/.pyd/.pyi/.pxd`
- `subtitles/`: `__init__.py/.pyi/.pxd`, `codeccontext.py/.pyd/.pyi/.pxd`, `stream.py/.pyd/.pyi/.pxd`, `subtitle.py/.pyd/.pyi/.pxd`
- `filter/__init__.py` re-exports `Filter`, `filters_available`, `Graph`, `stats`; `codec/__init__.py` re-exports `Codec`, `CodecContext`, `Capabilities`, `Properties`, `PixFmtLoss`, `codecs_available`, `find_best_pix_fmt_of_list`; `audio/__init__.py` and `video/__init__.py` re-export only Frame+Stream (codec names live in `av.audio._AudioCodecName` / `av.video._VideoCodecName` Literals in the `.pyi`).

### Compiled libs (inventory only — never read binaries)

`<repo>\.venv\Lib\site-packages\av.libs` (24 DLLs, delvewheel-bundled): `avcodec-62-*`, `avdevice-62-*`, `avfilter-11-*`, `avformat-62-*`, `avutil-60-*`, `swresample-6-*`, `swscale-9-*`, plus `libx264-165-*`, `libx265-*`, `libvpx-1-*`, `libopus-0-*`, `libmp3lame-0-*`, `libSvtAv1Enc-*`, `libdav1d-*`, `libwebp`, `libwebpmux`, `libsharpyuv`, `libvpl`, `libopencore-amrnb/wb`, `libiconv-2`, `zlib1`, `libgcc_s_seh-1`, `libstdc++-6`, `libwinpthread-1`. Loaded via the delvewheel patch at the top of `av/__init__.py` (`os.add_dll_directory`). Audio encoders present per wheel: `libmp3lame`, `libopus`, `libopencore_amrnb`, AAC native. No `libfdk_aac`. HW device types reported at runtime: `cuda, dxva2, qsv, d3d11va, d3d12va, amf`.

---

## Metadata

From `av-18.1.0.dist-info/METADATA` (+ `WHEEL`, `entry_points.txt`, `top_level.txt`, `RECORD`):

- `Name: av`, `Version: 18.1.0`, `Summary: Pythonic bindings for FFmpeg's libraries.`, `License-Expression: BSD-3-Clause`, `Requires-Python: >=3.11` (classifiers list 3.11–3.14).
- **Dependency pins: none.** METADATA contains zero `Requires-Dist` entries — PyAV has no runtime Python dependencies (numpy/Pillow are optional, used only by `to_ndarray`/`from_ndarray`/`to_image`/`from_image` code paths).
- Source builds target **FFmpeg 8.x** (`pip install av --no-binary av` needs FFmpeg dev files + pkg-config). This wheel reports `ffmpeg_version_info == 8.1.2`.
- `av._core.library_versions` (measured): libavutil (60,26,102), libavcodec (62,28,102), libavformat (62,12,102), libavdevice (62,3,102), libavfilter (11,14,102), libswscale (9,5,102), libswresample (6,3,102). `av._core.library_meta` adds per-lib `configuration`/`license` strings.
- Console script: `pyav = av.__main__:main` with flags `--codecs`, `--hwdevices`, `--hwconfigs`, `--version` (`av/__main__.py`). `top_level.txt` is just `av`.
- Top-level exports (`av/__init__.py::__all__`, 22 names): `__version__`, `time_base`, `ffmpeg_version_info`, `library_versions`, `AudioCodecContext`, `AudioFifo`, `AudioFormat`, `AudioFrame`, `AudioLayout`, `AudioResampler`, `AudioStream`, `BitStreamFilterContext`, `bitstream_filters_available`, `Codec`, `codecs_available`, `CodecContext`, `open`, `DeviceInfo`, `enumerate_input_devices`, `enumerate_output_devices`, `ContainerFormat`, `formats_available`, `Packet`, `VideoCodecContext`, `VideoFormat`, `VideoFrame`, `VideoStream`. Note: `av.stream`, `av.filter`, `av.codec` submodules are NOT imported by `__init__` — they resolve only as a side effect of other imports (see Gotchas).

---

## Module-by-module API

### `av.open()` / `av.container` (`container/core.py`, `input.py`, `output.py`, `streams.py`, `pyio.py`)

```python
av.open(
    file, mode=None,            # "r" | "w" (None -> file.mode or "r")
    format=None,                # e.g. "mp4", "matroska", "gif", "avfoundation"; "name:acodec" split supported on input
    options=None,               # dict[str,str] -> container AND every stream
    container_options=None,     # dict[str,str] -> container only
    stream_options=None,        # list per-stream dicts (input only; output raises ValueError — use add_stream(options=...))
    metadata_encoding="utf-8", metadata_errors="strict",
    buffer_size=32768,          # honored only for file-like objects
    timeout=None,               # float | (open_timeout, read_timeout); interrupt callback
    io_open=None,               # callable(url, flags, options) -> file-like (DASH/custom IO)
    hwaccel=None,               # HWAccel for hardware decode
) -> InputContainer | OutputContainer
```

- `file`: path `str`/`Path` or any file-like object (needs `read` for input, `write` for output; `seek`+`tell` make it seekable; bridged via `container/pyio.py`, buffer of `buffer_size`). DASH + custom IO needs a `customprotocol://` prefix on `file`.
- Side effects: input runs `avformat_open_input` + `avformat_find_stream_info` eagerly in `__cinit__`; wraps every stream with a decoder `CodecContext` (or `None` when no decoder exists — check before use). Output only allocates the format context; the header is written lazily by `start_encoding()` (auto-called on first `mux`).
- `Container` base: `name`, `file`, `format: ContainerFormat`, `options`, `container_options`, `stream_options`, `streams: StreamContainer`, `metadata` (dict; lazily `{}` on output, populated on input), `open_timeout`/`read_timeout`, `flags: int`, `video_codec_id`, `buffer_size`, `io_open`, `open_files`; `input_was_opened` prop; `close()`; context-manager support (`__enter__`/`__exit__` → `close()`); `chapters() -> list[Chapter{id,start,end,time_base(Fraction|None),metadata}]`; `set_chapters(chapters)`; `dumps_format() -> str` (ffmpeg `-i` style dump via log capture); `flags`/`video_codec_id` get/set after `_assert_open()`.
- `Flags` (input, `container/core.py`): `gen_pts ign_idx non_block ign_dts no_fillin no_parse no_buffer custom_io discard_corrupt flush_packets bitexact sort_dts fast_seek shortest auto_bsf`. `AudioCodec` IntEnum lists PCM codec ids for the `format:"acodec"` split.
- Exceptions: `FileNotFoundError`, `DemuxerNotFoundError`/`MuxerNotFoundError`, `ArgumentError` (EINVAL), `TimeoutError` (when `timeout` fires), `HTTPError` subclasses for network URLs, `ProtocolNotFoundError`.

`InputContainer` (`container/input.py`):

```python
.start_time: int | None            # AV_TIME_BASE units
.start_time_realtime: int | None   # wall-clock us since epoch (RTSP/RTCP only)
.duration: int | None              # AV_TIME_BASE units
.bit_rate: int; .size: int         # avio_size(pb)
.demux(*args, **kwargs) -> Iterator[Packet]   # args filtered via StreamContainer.get; ends with one dummy flush Packet per included stream
.decode(*args, **kwargs) -> Iterator[VideoFrame | AudioFrame | SubtitleSet]  # demux + packet.decode()
.seek(offset: int, *, backward=True, any_frame=False, stream=None,
      unsupported_frame_offset=False, unsupported_byte_offset=False) -> None
.flush_buffers() -> None           # flush every stream codec context (called by seek)
.close() -> None
```

- `seek` offset units: `stream.time_base` if `stream` given else `av.time_base` (1µs). Must be `int` (TypeError otherwise). Defaults seek to a keyframe at-or-before offset; `any_frame=True` allows non-keyframes (inaccurate/slow). Always `flush_buffers()` after. Typical precise pattern: `seek(ts, backward=True)` then demux/decode forward to the target.
- `demux` selection overloads accept single streams, tuples, `video=`/`audio=`/`subtitles=`/`data=` kwargs, or nothing (= all streams). Raises `ValueError` on out-of-range index. `EOFError` terminates iteration internally (never surfaces).
- Example:

```python
with av.open(path, "r") as c:
    v = c.streams.video[0]
    c.seek(int(12.5 * av.time_base), backward=True)
    for pkt in c.demux([v]):
        for frame in pkt.decode():
            ...
```

`OutputContainer` (`container/output.py`):

```python
.add_stream(codec_name: str, rate=None, options=None, hwaccel=None, **kwargs) -> AudioStream | VideoStream | SubtitleStream
.add_mux_stream(codec_name: str, rate=None, **kwargs) -> Stream          # remux pre-encoded packets, NO CodecContext
.add_stream_from_template(template: Stream, opaque=None, **kwargs) -> Stream  # remux; opaque defaults True except video
.add_attachment(name: str, mimetype: str, data: bytes) -> AttachmentStream     # header-embedded (e.g. Matroska fonts/covers)
.add_data_stream(codec_name=None, options=None) -> DataStream
.start_encoding() -> None            # write header; opens all stream CodecContexts; warns on unused options
.mux(packets: Packet | Sequence[Packet]) -> None
.mux_one(packet: Packet) -> None     # buffers until in-band extradata resolved for GLOBALHEADER formats
.default_video_codec / .default_audio_codec / .default_subtitle_codec -> str
.supported_codecs -> set[str]
.close() -> None                      # writes trailer exactly once
```

- `add_stream` defaults: video `width=640 height=480 pix_fmt=yuv420p framerate=rate or 24 time_base` passthrough; audio `sample_rate=rate or 48000`, first supported sample_fmt, stereo layout, `bit_rate=0`. `rate`: int (audio Hz) or Fraction/int (video fps). Extra `kwargs` setattr onto the stream (`width`, `height`, `pix_fmt`, `bit_rate`, `time_base`, `layout`…). **Configure everything before first mux** — the header freezes structural props. `hwaccel` only affects video encodes (e.g. `h264_vaapi`; software frames auto-upload on encode).
- `add_stream_from_template`: copies codecpar + time_base; `opaque=True` reuses the template codec object; resets codec_tag; video gets a fresh encoder object by default. Data/attachment templates (no codec context) handled without codec.
- `mux_one` extradata buffering: on GLOBALHEADER formats the first packets per stream are held while an `extract_extradata` BSF sniffs in-band parameter sets; only the first packet per stream is waited on. `mux` accepts a single Packet or a sequence (matches `encode()`'s list return). Packets are rebased to stream time and `av_interleaved_write_frame` takes ownership of a ref — do not reuse a Packet after muxing it.
- `start_encoding` merges `self.options` into each unopened context (`setdefault`), applies `_finalize_for_output()` per stream, `avio_open`s the target, copies `self.metadata`, writes the header. Unused options → `logging.warning`.
- Example:

```python
out = av.open("o.mp4", "w")
vs = out.add_stream("libx264", rate=30, options={"crf": "23", "preset": "fast"})
vs.width, vs.height, vs.pix_fmt, vs.time_base = 1280, 720, "yuv420p", Fraction(1, 30)
out.metadata.update({"title": "x"})
for pkt in vs.encode(frame):
    out.mux(pkt)
for pkt in vs.encode(None):
    out.mux(pkt)  # flush
out.close()
```

`StreamContainer` (`container/streams.py`): tuple-like. `.video/.audio/.subtitles/.data/.attachments` tuples; `__len__/__iter__/__getitem__(int|slice)`; `get(*args, **kwargs) -> list[Stream]` (ints, Stream objects, lists/tuples, `{type: index|[indices]}` dicts, `video=/audio=/...` kwargs; empty selection = all); `best(type: "video"|"audio"|"subtitle"|"data"|"attachment", /, related=None) -> Stream | None` (wraps `av_find_best_stream`; `None` when no streams).

### `av.Codec` / `codecs_available` (`codec/codec.py`)

```python
Codec(name: str, mode: Literal["r","w"] = "r")
.is_encoder/.is_decoder -> bool; .mode -> "r"|"w"; .name; .canonical_name; .long_name
.type -> "video"|"audio"|"data"|"subtitle"|"attachment"|"unknown"; .id -> int
.frame_rates: list[AVRational] | None; .audio_rates: list[int] | None
.video_formats: list[VideoFormat] | None; .audio_formats: list[AudioFormat] | None
.hardware_configs: list[HWConfig]
.properties -> int; .intra_only/.lossy/.lossless/.reorder/.bitmap_sub/.text_sub -> bool
.capabilities -> int; .experimental/.delay -> bool
.create(kind: "video"|"audio"|"subtitle"|None = None) -> matching CodecContext
codecs_available: set[str]          # ALL codec/descriptor names (NOT encoder-only!)
dump_codecs() / dump_hwconfigs()   # print to stdout (pyav --codecs/--hwconfigs)
find_best_pix_fmt_of_list(pix_fmts, src_pix_fmt, has_alpha=False) -> (VideoFormat|None, PixFmtLoss)
```

- `mode` accepts ONLY `"r"`/`"w"` (anything else raises). Unknown name raises `UnknownCodecError(ValueError)`.
- `Properties` Flag: NONE INTRA_ONLY LOSSY LOSSLESS REORDER BITMAP_SUB TEXT_SUB. `Capabilities` IntEnum: draw_horiz_band dr1 hwaccel delay small_last_frame hwaccel_vdpau subframes experimental channel_conf neg_linesizes frame_threads slice_threads param_change auto_threads variable_frame_size avoid_probing hardware hybrid encoder_reordered_opaque encoder_flush encoder_recon_frame. `PixFmtLoss` IntFlag: NONE RESOLUTION DEPTH COLORSPACE ALPHA COLORQUANT CHROMA.
- Gotcha: `"libx264" in codecs_available` does NOT prove encodability — verify with `Codec(name, "w")` in try/except.

### `av.CodecContext` + video/audio/subtitle variants (`codec/context.py`, `video/codeccontext.py`, `audio/codeccontext.py`, `subtitles/codeccontext.py`)

```python
CodecContext.create(codec: str | Codec, mode: "r"|"w"|None = None, hwaccel: HWAccel|None = None)
# overloads resolve audio/video/subtitle names to Audio/Video/SubtitleCodecContext
.open(strict: bool = True) -> None      # strict=False tolerates experimental codecs
.parse(raw_input: bytes|bytearray|memoryview|None = None) -> list[Packet]
.flush_buffers() -> None
.is_open/.is_encoder/.is_decoder/.is_hwaccel -> bool; .codec -> Codec
.supported_options -> CodecOptionSet(generic, private: tuple[CodecOption,...])
.profiles -> list[str]; .profile: str|None; .level: int
.extradata: bytes|None; .extradata_size: int; .time_base: Fraction; .codec_tag: str
.global_quality: int; .bit_rate: int|None; .max_bit_rate: int|None; .bit_rate_tolerance: int
.thread_count: int (0=auto); .thread_type: ThreadType(NONE|FRAME|SLICE|AUTO, get/set accepts int|str|ThreadType)
.skip_frame: NONE|DEFAULT|NONREF|BIDIR|NONINTRA|NONKEY|ALL
.flags: int (Flags: unaligned qscale four_mv output_corrupt qpel recon_frame copy_opaque frame_duration pass1 pass2 loop_filter gray psnr interlaced_dct low_delay global_header bitexact ac_pred interlaced_me closed_gop)
.flags2: int; .qscale: bool; .copy_opaque: bool; .delay: bool
.options: dict[str,str]
VideoCodecContext += .format: VideoFormat|None; .sw_format (+setter); .width/.height/.coded_width/.coded_height;
  .pix_fmt: str|None; .framerate/.rate: Fraction; .gop_size; .sample_aspect_ratio/.display_aspect_ratio;
  .has_b_frames/.max_b_frames/.reorder_depth; .color_range/.color_primaries/.color_trc/.colorspace; .field_order; .qmin/.qmax
AudioCodecContext += .frame_size/.sample_rate/.rate: int; .format/.layout (accept str); .channels (read-only prop)
SubtitleCodecContext += .subtitle_header: bytes|None;
  .decode2(packet) -> SubtitleSet|None; .encode_subtitle(subtitle: SubtitleSet) -> Packet
```

- Encode/decode:

```python
VideoStream.encode(frame|None) -> list[Packet];  .encode_lazy(frame|None) -> Iterator[Packet]
VideoCodecContext.decode(packet|None) -> list[VideoFrame]   # None flushes; reordering note: pass packets from ONE stream
AudioCodecContext.encode/decode analogous (AudioFrame); SubtitleStream.decode(packet|None) -> list[AssSubtitle]|list[BitmapSubtitle]
```

- `encode(None)` / `decode(None)` flush; `encode_lazy` streams packets out (use for memory-sensitive loops). Encoders needing fixed `frame_size` (AAC etc.) return `[]` until buffered enough — pair with `AudioFifo` or buffer yourself. Setting structural attrs after `open()` raises / is ignored (`_assert_not_open`); `thread_count`/`thread_type` similar.
- `CodecOption` dataclass: name/help/type(`OptionType`: FLAGS INT INT64 DOUBLE FLOAT STRING RATIONAL BINARY DICT UINT64 CONST IMAGE_SIZE PIXEL_FMT SAMPLE_FMT VIDEO_RATE DURATION COLOR CHANNEL_LAYOUT BOOL UINT)/is_array/default/min/max/flags(`OptionFlags`: ENCODING/DECODING/AUDIO/VIDEO/SUBTITLE_PARAM EXPORT READONLY BITSTREAM_FILTER RUNTIME FILTERING DEPRECATED CHILD_CONSTS)/choices. Inspect `supported_options` before setting exotic `options` (e.g. validate `crf`/`preset`).

### `HWAccel` (`codec/hwaccel.py`)

```python
HWAccel(device_type: str|HWDeviceType, device: str|int|None = None,
         allow_software_fallback: bool = False, options: dict|None = None,
         flags: int|None = None, is_hw_owned: bool = False)
.options; .is_hw_owned; .device_id: int
.create(codec: Codec, for_encoding=False) -> HWAccel
hwdevices_available() -> list[str]     # e.g. ['cuda','dxva2','qsv','d3d11va','d3d12va','amf'] here
HWDeviceType: none vdpau cuda vaapi dxva2 qsv videotoolbox d3d11va drm opencl mediacodec vulkan d3d12va
HWConfig: .device_type/.format(VideoFormat|None)/.methods(HWConfigMethod)/.is_supported
```

- Pass to `av.open(..., hwaccel=HWAccel("d3d11va", allow_software_fallback=True))` for decode or `add_stream(..., hwaccel=...)` for encode. Input init raises `RuntimeError` when `allow_software_fallback=False` and no stream accelerates. `VideoFrame.sw_format` gives the software pixel format behind a hardware frame.

### `Stream` / `Packet` / `Frame`

`Stream` (`stream.py` + `video/stream.py`, `audio/stream.py`, `subtitles/stream.py`): `name`, `container`, `codec: Codec`, `codec_context` (may be `None` for mux-only/data/attachment streams — always guard), `metadata: dict`, `index_entries: IndexEntries`, `id`, `profiles`, `profile`, `index`, `options`, `time_base: Fraction|None`, `average_rate/base_rate/guessed_rate: Fraction|None`, `start_time/duration: int|None` (stream tb), `disposition: Disposition` (IntFlag: default dub original comment lyrics karaoke forced hearing_impaired visual_impaired clean_effects attached_pic timed_thumbnails non_diegetic captions descriptions metadata dependent still_image multilayer — test bits with `int()`, attribute access is always truthy), `discard: Discard` (settable: none default nonref bidir nonintra nonkey all), `frames: int`, `language: str|None` (parsed from metadata), `codec_tag: str`, `type` Literal. `DataStream`/`AttachmentStream`: `AttachmentStream.mimetype/.data`. `VideoStream`: `encode/encode_lazy/decode`, `set_display_matrix(Sequence[int]|None)`, `set_display_rotation(degrees, hflip=..., vflip=...)`, plus codec-context mirrors (`width/height/format/pix_fmt/framerate/rate/gop_size/...`). `AudioStream`: `encode/decode`, `frame_size/sample_rate/bit_rate/rate/channels/format/layout`. `SubtitleStream`: `decode`, `decode2(packet) -> SubtitleSet|None`.

`Packet` (`packet.py`, Buffer subclass): `Packet(input: int|bytes|None = None)`; `stream`, `stream_index: int`, `time_base: Fraction`, `pts/dts/pos/size/duration`, `opaque`, flags `is_keyframe/is_corrupt/is_discard/is_trusted/is_disposable`; `rescale_ts(time_base: AVRational) -> None`; `decode()` overloads per stream type; sidedata: `has_sidedata/get_sidedata/set_sidedata/iter_sidedata`, `PacketSideData.from_packet/to_packet`, `data_type/data_desc/data_size`, 60-entry `PktSideDataT` literal. `Buffer`: `buffer_size/buffer_ptr/update/__buffer__/__bytes__`. Never reuse a Packet after `mux()`.

`Frame` (`frame.py`): `dts/pts/duration`, `time_base: Fraction|None`, `side_data`, `opaque`, `.metadata`, `.time -> float|None` (pts·tb in seconds), `.is_corrupt`, `.key_frame`, `make_writable()`.

`VideoFrame` (`video/frame.py`): `VideoFrame(width=0, height=0, format="yuv420p")`; `.format: VideoFormat`, `.planes`, `.pict_type`, `.colorspace/.color_range/.color_trc/.color_primaries`, `.sw_format`, `.width/.height`, `.interlaced_frame`, `.rotation` (from display matrix — the only rotation accessor on this build); `reformat(width?, height?, format?, src_colorspace?, dst_colorspace?, interpolation?, src_color_range?, dst_color_range?, dst_color_trc?, dst_color_primaries?, threads?) -> VideoFrame`; `to_rgb/save(filepath)/to_image/to_ndarray(channel_last=False)/from_image/from_ndarray(array, format="rgb24", channel_last=False)/from_numpy_buffer/from_bytes(data,width,height,format="rgba",flip_*)/from_dlpack(...)`; `CudaContext`; `PictureType` IntEnum; `supported_np_pix_fmts: set[str]`. `save()` picks its own encoder (mjpeg/yuvj420p) — may need a `reformat(format="bgr24")` fallback for exotic pix_fmts.

`VideoFormat` (`video/format.py`): `VideoFormat(name, width=0, height=0)`; `name/bits_per_pixel/padded_bits_per_pixel/is_big_endian/has_palette/is_bit_stream/is_planar/width/height/components/is_rgb/is_bayer`; `chroma_width/chroma_height`; `VideoFormatComponent(plane/bits/is_alpha/is_luma/is_chroma/width/height)`. `VideoReformatter.reformat(frame, ...)` — reusable variant of `VideoFrame.reformat` with `Interpolation` flags (FAST_BILINEAR BILINEAR BICUBIC X POINT AREA BICUBLIN GAUSS SINC LANCZOS SPLINE …) and `Colorspace/ColorRange/ColorTrc/ColorPrimaries` enums.

`AudioFrame` (`audio/frame.py`): `AudioFrame(format="s16", layout="stereo", samples=0, align=1)`; `.planes/.samples/.sample_rate/.rate`, `.format/.layout` (accept str); `from_ndarray(array, format="s16", layout="stereo")`, `to_ndarray()`; `format_dtypes` map. Supported ndarray dtypes: float64/float32/int32/int16/uint8.

`AudioFormat` (`audio/format.py`): `AudioFormat(name)`; `name/bytes/bits/is_planar/is_packed/planar/packed/container_name`. `AudioLayout` (`audio/layout.py`): `AudioLayout("stereo")`; `name/nb_channels/channels: tuple[AudioChannel(name, description)]`.

`AudioResampler` (`audio/resampler.py`): `AudioResampler(format=None, layout=None, rate=None, frame_size=None, options=None)`; `.rate/.frame_size/.format/.layout/.options/.graph`; `resample(frame|None) -> list[AudioFrame]` (`None` flushes; first frame fixes the template — later frames with different format/layout/rate raise `ValueError`; passthrough short-circuits to `[frame]`). `options` go to an explicit `aresample` filter (e.g. `{"resampler":"soxr","precision":"28"}`); without options it builds `abuffer→aformat→abuffersink`.

`AudioFifo` (`audio/fifo.py`): `write(frame)`; `read(samples=0, partial=False) -> AudioFrame|None`; `read_many(samples, partial=False) -> list[AudioFrame]`; `.format/.layout/.sample_rate/.samples/.samples_written/.samples_read/.pts_per_sample`. For encoders with fixed `frame_size`.

### `av.filter` graph (`filter/graph.py`, `filter.py`, `context.py`, `link.py`, `loudnorm.py`)

```python
g = av.filter.Graph()
g.add(filter: str|Filter, args=None, **kwargs) -> FilterContext
g.add_buffer(template: VideoStream|None = None, width?, height?, format?, name?, time_base?) -> FilterContext
g.add_abuffer(template: AudioStream|None = None, sample_rate?, format?, layout?, channels?, name?, time_base?) -> FilterContext
g.set_audio_frame_size(n)          # after configure()
g.configure(auto_buffer=True, force=False)
g.link_nodes(*nodes: FilterContext) -> Graph     # linear chain
node.link_to(input_: FilterContext, output_idx=0, input_idx=0)  # fan-out/fan-in (split/overlay/alphamerge)
g.push(frame|None, at=-1) -> None  # None = EOF on that input; at = input pad index
g.pull() -> VideoFrame|AudioFrame   # raises EOFError at end, FFmpegError(EAGAIN) when starved
g.vpush/g.vpull (video-typed); .configured; .threads: int
Filter(name).name/.description/.flags; filters_available: set[str] (468 here)
FilterContext: .name/.graph; .init(args?, **kwargs); .push/.pull;
  .process_command(cmd, arg=None, res_len=1024, flags=0) -> str|None  # runtime filter tweaking
FilterLink: placeholder (no API)
loudnorm.stats(loudnorm_args: str, stream: AudioStream) -> bytes   # two-pass measurement JSON; TAKES OWNERSHIP of the container (see Gotchas)
```

- Push/pull protocol: feed inputs (optionally by pad with `at=`), `pull()` until `EOFError`; transient `EAGAIN` (`errno == EAGAIN`) means "need more input", not failure. EOF each input with `push(None, at=i)`.
- `add_buffer(template=frame)` seeds size/format from a live frame — always pass an explicit `time_base` (recommend `Fraction(1, 90000)` for video when `setpts`/speed is downstream; audio inherits sample tb).
- Example (palette GIF): `src→fps→scale→split→{palettegen→paletteuse, direct}→sink` with `split.link_to(pgen,0,0)`, `split.link_to(puse,1,0)`, `pgen.link_to(puse,0,1)`.

### `av.audio.format` / `av.video.format` — see Frame section above. `ContainerFormat` / `formats_available` (`format.py`): `ContainerFormat(name, mode=None)`; `.name/.long_name/.is_input/.is_output/.extensions/.flags/.no_file`; `Flags` (no_file need_number show_ids global_header no_timestamps generic_index ts_discont variable_fps no_dimensions no_streams no_bin_search no_gen_search no_byte_seek allow_flush ts_nonstrict ts_negative seek_to_pts); `formats_available: set[str]` (414).

### Devices, bitstream filters, logging, rational, index, sidedata, subtitles

- `av.device`: `DeviceInfo(name, description, is_default, media_types)`, `enumerate_input_devices(format_name)`, `enumerate_output_devices(format_name)` (e.g. `"avfoundation"`, `"dshow"`, `"gdigrab"`).
- `av.bitstream.BitStreamFilterContext(filter_description, in_stream: Stream|Codec|str|None = None, out_stream: Stream|None = None)`; `.filter(packet|None) -> list[Packet]` (`None` drains); `.flush()`; `bitstream_filters_available: set[str]` (49). Needed ops: `h264_mp4toannexb`/`hevc_mp4toannexb` (MP4→MPEG-TS/HLS), `aac_adtstoasc`, `extract_extradata` (auto-used by `mux_one`).
- `av.logging`: default callback DISCARDS everything (errors lose detail). `set_level(PANIC|FATAL|ERROR|WARNING|INFO|VERBOSE|DEBUG|TRACE|None)` (None = discard; dev should use VERBOSE), `get_level()`, `set_libav_level()`, `restore_default_callback()`, `set/get_skip_repeated()`, `get_last_error()`, `log()`, `Capture(local=True)` context manager (`.logs: list[(level,name,message)]`). `Container.dumps_format()` uses `Capture` internally.
- `av.rational.AVRational(num=0, den=1)`: full numeric protocol (`num/den/numerator/denominator`, comparisons, `+ - * /` with Rational/float).
- `IndexEntries` (`index.py`, via `stream.index_entries`): `len/iter/getitem`, `IndexEntry(pos/timestamp/flags/is_keyframe/is_discard/size/min_distance)`, `search_timestamp(ts, *, backward=True, any_frame=False) -> int` (index into entries, stream-tb units; used for keyframe snapping).
- Frame sidedata (`sidedata/`): `SideDataContainer` mapping on frames (`MOTION_VECTORS` etc.), `Type` enum (36 kinds), `MotionVectors→to_ndarray()/MotionVector(source/w/h/src_x/src_y/dst_x/dst_y/motion_x/motion_y/motion_scale)`, `VideoEncParams(qp/delta_qp/block_params/qp_map)`.
- `Dictionary` (`dictionary.py`): str→str mapping used for codec/format options plumbing.
- Subtitles (`subtitles/`): `SubtitleSet.create(text: bytes, start, end, pts=0, subtitle_format=1)`; `.format/.start_display_time(ms offset)/.end_display_time(ms DURATION)/.pts(µs, AV_TIME_BASE)/.rects`; `AssSubtitle.ass/dialogue/text (bytes)`, `BitmapSubtitle(type==b"bitmap", x/y/width/height/nb_colors/planes)`. Decode path: `SubtitleStream.decode(packet|None)` or `decode2(packet)`; encode path: `SubtitleCodecContext.encode_subtitle(SubtitleSet) -> Packet` (+ `subtitle_header`).
- `av.packet.PacketSideData`, `av.opaque`, `av.utils` (internal helpers), `av.datasets` (test-data downloader) — no app relevance.
- CLI: `pyav --version --codecs --hwdevices --hwconfigs`.

---

## App usage & correctness

Scope: `src/services/engine_service.py` (2721 lines, all PyAV ops), `src/core/engine_probe.py` (capability probe + synthetic self-test), `src/services/media_io.py` (no PyAV — Flet file picker/share only), `tests/` (synthetic `av.open`/`VideoFrame`/`AudioFrame` fixtures).

### (a) Correct usage (keep these patterns)

- `probe()` (`engine_service.py:463-620`): `with av.open(path,"r")`, `container.format.name/long_name`, `duration/time_base` bitrate fallback, `container.metadata`, per-stream `codec_context` guarded for `None`, `stream.duration*time_base`, `average_rate` for fps, `container.chapters()` with `Fraction` tb, `container.streams.video[0]` demux-one-frame rotation probe (`engine_service.py:556-564`), `Disposition` bit-testing via `int()` (`engine_service.py:510-519`).
- Filter graphs (`engine_service.py:239-373,2411-2452,2518-2550`): `add_buffer(template=frame, time_base=FINE_TB)`, `add_abuffer(sample_rate/format/layout)`, `link_nodes` + indexed `link_to` for split/overlay/alphamerge/acrossfade, `configure()`, push/pull with EAGAIN tolerance (`_pull_ready`, `_push_pull`, `_drain_graph`), EOF-drain with `push(None)`.
- Remux paths (`engine_service.py:1036-1040,1786-1800,1973-1985`): `add_stream_from_template(s, opaque=True)`, explicit metadata/disposition copy, `set_chapters`, `Packet.rescale_ts` + one-tick shift in concat-copy (`engine_service.py:1992-2021`), `BitStreamFilterContext(h264/hevc_mp4toannexb)` for MP4→TS/HLS (`engine_service.py:2622-2641`) with EOF drain (`engine_service.py:2706-2709`).
- Cut (`engine_service.py:1001-1104`): keyframe snap via `index_entries.search_timestamp(ts, backward=True)` (`engine_service.py:1007-1021`), `seek(int(s*av.time_base), backward=True)`, PTS-zero-basing per stream.
- Frame extraction (`engine_service.py:1385-1449,1680-1739`): single seek + forward decode to all targets; `frame.save` with `reformat(bgr24)` fallback; `_mjpeg_bytes` in-memory mjpeg (`engine_service.py:141-157`).
- `engine_probe.py`: measures `codecs_available/filters_available/formats_available` from the wheel, verifies encoders via `Codec(name, mode)`, socket-level protocol probe (`engine_probe.py:287-300`), `synthetic_transcode` round-trip (`engine_probe.py:303-376`).
- `record()` (`engine_service.py:2556-2591`): `av.open(url, "r", timeout=(10.0, 30.0))` with `ProtocolNotFoundError/TimeoutError/HTTPError/FFmpegError` → `ValueError` mapping. Only caller that passes `timeout`.

### (b) Misuse / bugs (file:line)

1. **Output container opened outside `try` — input leaks on failure.** `engine_service.py:645-646, 885-886, 1032-1033, 1115-1116` (and concat/record variants): `inp = av.open(...); out = av.open(...)` precede `try:`. If the second `open` raises, `inp` is never closed. Fix: open `out` inside `try` or use nested `with av.open(...) as ...`.
2. **`codecs_available` abused as an encoder check.** `engine_service.py:673, 896, 1126, 2066, 2179` (`"libx264" in av.codec.codecs_available`) and `engine_probe.py:328`: the set holds ALL 557 codec/descriptor names, decoder-only included. A name can be present yet un-encodable. Fix: `Codec(name, "w")` in try/except, or reuse `probe().encoders` / `video_encoder_picks`.
3. **Implicit submodule access via transitive imports.** `engine_service.py:517` (`av.stream.Disposition`), `av.filter.Graph`, `av.codec.codecs_available` etc. work only because `from av.filter.loudnorm import ...` / `av.audio.*` imports happen to load those subpackages — `av/__init__.py` never imports `av.stream`, `av.filter`, or `av.codec`. Fragile: add explicit `import av.stream, av.filter, av.codec` (or `from av.stream import Disposition`).
4. **`_mjpeg_bytes` encodes without `open()`.** `engine_service.py:150-156`: standalone `CodecContext.create("mjpeg","w")` + `encode()` relies on PyAV's implicit open-on-first-encode. Works today but undocumented; call `ctx.open()` after setting width/height/pix_fmt/time_base.
5. **Inconsistent packet filtering drops valid data.** `convert`/`compress`/`cut_reencode` skip `packet.dts is None` (`engine_service.py:736,922,1146`) while `remux`/`record` skip `size == 0 or pts is None` (`engine_service.py:1816,2652`). A packet can carry valid `pts` with `None` dts (and vice versa); pick one policy (recommend: skip only `size == 0 or (pts is None and dts is None)`).
6. **`_cut_stream_copy` never rescales timestamps.** `engine_service.py:1078-1086` subtracts the base pts directly, unlike `_concat_stream_copy` which calls `packet.rescale_ts(target_tb)` (`engine_service.py:2000-2001`). Safe only because template streams share time_bases today; add the same `rescale_ts` guard.
7. **Outputs lose container metadata + non-AV streams.** Only `remux()` copies `metadata`/`disposition`/`chapters` (`engine_service.py:1795-1807`); `convert`/`compress`/`cut`/`concat`/`extract_audio` never set `out.metadata`, and every op except `record` drops data/attachment streams (fonts, covers, chapter tracks). Fix: copy `inp.metadata`, `set_chapters`, template data/attachment streams where the target format allows.
8. **Docstring lies about Codec modes.** `engine_probe.py:152-160` docstring says mode `'e'`/`'d'`; the Cython API accepts only `"r"`/`"w"` (calls themselves are correct). Fix the docstring before someone "corrects" the calls.
9. **Probe self-test overstates encoder support.** `engine_probe.py:328-329` picks `libx264` from the full codec-name set instead of the verified `p.encoders` set.
10. **Loudnorm container intentionally leaked (documented, still a smell).** `engine_service.py:1196-1215`: `loudnorm.stats()` NULLs the wrapper handle, so the container is never closed by design. Correct per current C code, but pin a regression test: if a future wheel stops stealing the handle this becomes a real leak.

### (c) Underuse — covered in the next section.

---

## Underused APIs to adopt

Ranked by value to this app (all verified present in `av-18.1.0` + this wheel):

1. **`CodecContext.supported_options` / `profiles` / `Codec(...).video_formats/audio_formats`** — validate `crf`/`preset`/codec params BEFORE encoding instead of failing mid-job; drive encoder pickers from measured data.
2. **`HWAccel` + `hwaccel=` on `av.open` / `add_stream`** — this wheel reports `cuda/dxva2/qsv/d3d11va/d3d12va/amf`; decode/encode offload + `allow_software_fallback=True` is free performance on desktop.
3. **`timeout=` (open/read) on every `av.open`** — only `record()` uses it; local opens hang on bad media/SD cards the same way sockets do. `av.open(path, "r", timeout=(5.0, 15.0))`.
4. **`Container.metadata` write + `set_chapters()` on outputs** — outputs currently drop title/artist/chapters; one `out.metadata.update(inp.metadata)` + `set_chapters` per op.
5. **`StreamContainer.best()` / `.get()` selectors + `demux(video=..)`/`decode(stream)` overloads** — replaces every `[0]`-index assumption (`inp.streams.video[0]`) with best-stream resolution and filtered demux.
6. **`AudioFifo`** — encoders with fixed `frame_size` (AAC) currently rely on lucky frame sizes; `fifo.write/decode-sized read_many` guarantees full buffers and kills the `encode() -> []` underruns.
7. **`VideoReformatter` (reusable) over per-frame `VideoFrame.reformat`** — one configured reformatter for the whole transcode instead of renegotiating swscale per frame.
8. **`stream.discard` / `CodecContext.skip_frame` / `thread_count=AUTO`** — thumbnail/keyframe scans and 1080p+ decodes get faster with `discard=nonkey` windows, `skip_frame`, and explicit thread counts.
9. **`av.logging.set_level(VERBOSE)` in dev + `Capture` around jobs + `dumps_format()` in the dossier** — today FFmpeg logs are discarded, so every `FFmpegError` arrives context-free; capture makes errors diagnosable.
10. **`BitStreamFilterContext` beyond annex-B** — `aac_adtstoasc`, `extract_extradata`, `filter(None)` drains belong in every remux path, not just record; `add_mux_stream`/`add_data_stream`/`add_attachment` + `SubtitleCodecContext.encode_subtitle` close the loop (attachments, data tracks, real subtitle muxing instead of hand-written SRT only).
11. Also unused: `container_options/stream_options/options` + `flags` (`discard_corrupt`, `fast_seek`, `gen_pts`), `io_open` custom IO, `Packet` sidedata (`display_matrix`, rotation, HDR), `start_time_realtime` (RTSP clock alignment), `stream.index_entries` beyond cut (keyframe chips already use it — extend to preview seek), `Filter.process_command` (live filter tweaks), `CodecContext.parse` (raw-stream ingest), `enumerate_input/output_devices` (desktop capture).

---

## Gotchas

1. **`av.time_base` is 1,000,000.** Container `duration/start_time` and bare `seek(offset)` are microseconds. Stream `duration/start_time/timestamp` values are in `stream.time_base` units — convert with `float(x * stream.time_base)`. `Frame.time` is seconds (float) but `None` until `pts`+`time_base` exist.
2. **`Frame.time_base` setter does NOT rescale.** Assigning `frame.time_base = tb` reinterprets the existing `pts`. The app's `_rebase_pts` (`engine_service.py:167-176`) does it right (scale pts, then set tb) — copy that helper, don't inline.
3. **`seek()` lands on keyframes, backward by default.** It does NOT give frame accuracy: always demux/decode forward to the exact target. `any_frame=True` is slow/inaccurate; `unsupported_frame_offset/unsupported_byte_offset` are unsupported by every known format despite being in the signature.
4. **`demux()` ends with dummy flush packets** (one per included stream, zero-size). `packet.decode()` on them flushes decoder buffers — the app's `size == 0` skips in remux/record must NOT be copied into decode loops or frames get lost.
5. **Never reuse a Packet after `mux()`.** `av_interleaved_write_frame` takes ownership of a reference; mutating `packet.pts/dts/stream` after mux corrupts the muxer. Same for frames after `encode()` in hwaccel paths.
6. **Header freezes the output.** Set width/height/pix_fmt/rate/layout/options/metadata BEFORE the first `mux()`/`start_encoding()`. `start_encoding()` is idempotent; `close()` writes the trailer exactly once and `__del__` also closes — double-close is safe, never skip it (unclosed outputs are unplayable).
7. **`encode(None)` / `decode(None)` / `resample(None)` / `push(None)` flushes are mandatory.** Forgetting any one of them truncates tails (audio tails, B-frames, filter delay). Drain order: filter graph → resampler → encoder.
8. **`loudnorm.stats()` steals its container.** It NULLs the Python wrapper's handle (C-level); closing afterwards double-frees. The app's never-close in `_measure_loudnorm` is load-bearing — comment it and test it on every wheel bump.
9. **`Disposition` attribute access is always truthy.** It's an IntFlag class: `stream.disposition.forced` is the FLAG, not the state. Always `int(disposition) & int(Disposition.forced)`.
10. **`AudioResampler` locks its template on the first frame.** A later frame with different format/layout/rate raises `ValueError`. One resampler instance per homogeneous run; construct lazily from the first decoded frame (the app already does this — keep it).
11. **`pix_fmt` on contexts/streams is `str | None`, not `VideoFormat`.** `getattr(pix_fmt, "name", ...)`-style code is dead weight — compare strings directly. `VideoFrame.format` IS a `VideoFormat` (`.name` valid there).
12. **Errors are dual-hierarchy.** `av.error` maps FFmpeg codes onto `FFmpegError` + builtin mixins (`InvalidDataError(ValueError)`, `EOFError(EOFError)`, `TimeoutError`, `FileNotFoundError`, `HTTP*Error`, `Encoder/Decoder/Demuxer/Muxer/Protocol/Filter/OptionNotFoundError(LookupError)`…). Catch `av.error.FFmpegError` for everything, builtins for interop, and always compare `exc.errno == EAGAIN` (from `errno`) around `graph.pull()` — EAGAIN means "feed me", not failure.
13. **Logging is OFF by default — and that degrades errors.** With the discard callback, `err_check` has no last-log to attach. Dev builds must `av.logging.set_level(av.logging.VERBOSE)` + `logging.basicConfig()`; wrap risky calls in `av.logging.Capture`.
14. **`add_stream` picks lossy defaults silently.** Video defaults to `yuv420p/640x480/24fps`; audio to first sample_fmt/stereo/48kHz. Every structural attr must be assigned explicitly (the app does — keep it), and `options={"crf":..,"preset":..}` typos only warn via `logging` at `start_encoding`.
15. **`add_stream_from_template` does NOT copy metadata/disposition on this build** (app-verified) — the manual copy in `remux()` is required, not belt-and-braces. Re-verify per wheel.
16. **File-like IO needs `seek`+`tell` for seeking; `AVSEEK_SIZE` returns -1.** Non-seekable inputs (pipes, network without range) break `seek()` and index-based snapping — guard `keyframe_times`/snap fallbacks (the app does; keep the empty-list path).
