# av 18.1.0 (PyAV, FFmpeg 8 bindings) — audit reference

Wheel root: `.venv/Lib/site-packages/av/`, `__version__ = "18.1.0"`.
Only 2 files import it: `core/engine_probe.py` (capability probe),
`services/engine_service.py` (sole engine).

## Full API surface (verified in wheel, not docs)

- **Core/meta**: `time_base`, `library_versions`, `ffmpeg_version_info`,
  `get_include()`, `python -m av --codecs/--hwdevices/--hwconfigs`,
  `utils` (`avdict_to_dict`, `avrational_to_fraction`), `datasets`
  (test-data helper).
- **Containers**: `open(file, mode, format, options, container_options,
  stream_options, timeout, io_open, hwaccel)`;
  `Container` (`.format/.streams/.metadata/.options/.flags/.chapters()/.set_chapters()/.close()`);
  `Flags` (gen_pts/ign_idx/non_block/ign_dts/no_fillin/no_parse/no_buffer/
  custom_io/discard_corrupt/flush_packets/bitexact/sort_dts/fast_seek/
  shortest/auto_bsf); `Chapter`; `InputContainer`
  (`.demux/.decode/.seek/.flush_buffers/.duration/.bit_rate/.size`);
  `OutputContainer` (`.add_stream/.add_mux_stream/.add_stream_from_template/
  .add_attachment/.add_data_stream/.start_encoding/.mux/.mux_one/
  .default_video/audio/subtitle_codec/.supported_codecs`);
  `StreamContainer` (`.video/.audio/.subtitles/.attachments/.data/.get/.best`);
  `PyIOFile` custom-IO bridge.
- **Streams**: full field set (`time_base/average_rate/base_rate/
  guessed_rate/start_time/duration/disposition/discard/frames/language/
  codec_tag/options/profiles`); `Disposition` IntFlag (28 values);
  `VideoStream` (`.encode/.encode_lazy/.decode/.set_display_matrix/
  .set_display_rotation`, gop/aspect/color/coded fields);
  `AudioStream`; `SubtitleStream` (`.decode/.decode2`); `DataStream`;
  `AttachmentStream` (`.mimetype/.data`).
- **Codecs**: `Codec(name,mode)` (frame_rates/audio_rates/video_formats/
  audio_formats/hardware_configs/properties/intra_only/lossy/lossless/
  reorder); `codecs_available` (557 here); `CodecContext`
  (`.supported_options{generic,private}/.profile/.level/.extradata/
  .time_base/.thread_count/.thread_type/.skip_frame/.flags/.qscale/
  .copy_opaque/.flags2`, `.open(strict)/.parse/.flush_buffers`);
  `HWAccel` + `HWConfig/HWDeviceType/HWConfigMethod` +
  `hwdevices_available()`; `dump_codecs/dump_hwconfigs/
  find_best_pix_fmt_of_list/PixFmtLoss`.
- **Video**: `VideoFrame` (`.reformat/.to_rgb/.save/.to_image/
  .to_ndarray/.from_ndarray/.from_bytes/.from_image/.from_dlpack`,
  pict_type/colorspace/color_range/trc/primaries/sw_format/rotation/
  interlaced_frame); `VideoCodecContext` (gop/max_b_frames/qmin/qmax/
  field_order/sample_aspect/coded_*); `VideoReformatter` + enums
  (Interpolation/Colorspace/ColorRange/ColorTrc/ColorPrimaries);
  `VideoFormat` (bits/components/is_rgb/chroma); `CudaContext`.
- **Audio**: `AudioFrame` (`.from/to_ndarray`, `format_dtypes`);
  `AudioFormat/AudioLayout/AudioChannel`; `AudioResampler`
  (`.resample(frame|None)`, frame_size/format/layout introspection);
  `AudioFifo` (`.write/.read(samples,partial)/.samples/...`).
- **Filters**: `Graph` (`.add/.add_buffer/.add_abuffer/.link_nodes/
  .configure/.push/.pull/.vpush/.vpull/.set_audio_frame_size/.threads`);
  `Filter` (`.description/.flags`); `filters_available` (468 here);
  `FilterContext.process_command`; `loudnorm.stats(stream)`.
- **Packets/frames**: `Packet` (`.rescale_ts(AVRational)`, flags
  is_keyframe/is_corrupt/is_discard/is_trusted/is_disposable,
  sidedata has/get/set/iter, 40 `PktSideDataT` types);
  `Frame` (`.make_writable/.metadata/.time/.is_corrupt`);
  `Buffer.update/__bytes__`; `Plane/line_size/buffer_size`.
- **Side data**: `SideDataContainer/Type` (28), `MotionVectors.to_ndarray`,
  `VideoEncParams` (qp_map/block_params).
- **Subtitles**: `SubtitleSet.create`, `AssSubtitle.text/dialogue/ass`,
  `BitmapSubtitle`, `SubtitleCodecContext.encode_subtitle/subtitle_header`.
- **Formats**: `ContainerFormat/Flags/no_file/extensions` (414 here);
  `AVRational` full arithmetic; `Dictionary`; `IndexEntry/
  IndexEntries.search_timestamp`.
- **Errors** (60+): `FFmpegError` + Lookup/HTTP-family/Bug/Experimental/
  InputChanged/OutputChanged/builtin-mapped (EOF/FileNotFound/Timeout/
  …); `code_to_tag/tag_to_code/err_check`. Note: only
  `ProtocolNotFoundError` exists (no `ProtocolNotFound` spelling);
  `UnknownCodecError` lives at `av.codec.codec`, NOT `av.codec`.
- **Logging**: levels + `set_level/set_libav_level/get_last_error/log/
  adapt_level/set_skip_repeated/get_level`; `Capture(local)`.
- **Devices**: `enumerate_input/output_devices`, `DeviceInfo`.

## Used by app

Probe: version, codecs/filters/formats/bitstream sets, library
versions, `Codec(name,"w")` + hardware_configs +
`supported_options.private`, `CodecContext.create`,
`logging.set_level/Capture`, `av.open(url,timeout)` protocol probe,
`VideoFrame` smoke frame, mp4 round-trip, `time_base` math.
Engine: containers/streams open + metadata/chapters/disposition loop +
`streams.best("video"/"audio")` (only ever best — never subtitle/
attachment pickers), demux/decode/encode/mux, `seek`, `VideoReformatter`,
`frame.save` thumbnails, graph add/buffer/link/configure/push/pull,
`AudioFifo`, `AudioResampler`, `loudnorm_stats`,
`BitStreamFilterContext`, attachment add, `HWAccel(preferred,
allow_software_fallback=True)` (decode only).

## Unused opportunities (each: one-line use case)

Device enumeration → real camera/mic names. `io_open`/PyIO →
in-memory uploads without temp files. `add_data_stream` → telemetry
tracks. `add_mux_stream` → mux-only remux. `mux_one` → per-packet
isolation. `default_*_codec/supported_codecs` → dropdown defaults from
wheel. `Codec.create/frame_rates/formats/properties` → preflight
validation + intra-only badges. `dump_codecs/find_best_pix_fmt` →
diagnostics + quantified fallback. HW encode path (NVENC/QSV/AMF/VAAPI)
— app only hardware-decodes. ndarray frame access → numpy
thumbnails/waveforms. `pict_type/interlaced` → GOP view + deinterlace
flag. colorspace enums → HDR-aware convert. `set_display_matrix` →
rotation without re-encode. gop/b-frames/qmin/qmax/thread/skip_frame →
keyframe + preview-speed controls. profile/level/extradata/global_quality
→ device-compat presets. `parse/flush_buffers` → raw-stream probe +
resets. `encode_lazy` → per-packet progress. `InputContainer.decode`
→ simpler transcodes. `Filter.description/process_command` → in-UI
help + live retune. `vpush/vpull/set_audio_frame_size` → typed
plumbing + AAC frame sizing. Audio ndarray/Format/Layout → silence
synth + fmt validation. Resampler introspection → exact FIFO reads.
Packet sidedata (40 types) → HDR/3D preservation. `make_writable/
metadata/is_corrupt` → safe edits + quarantine counts. Motion-vector/
QP maps → quality viz. Subtitle encode/`SubtitleSet.create`/ASS →
SRT→ASS/WebVTT + styled burn-in. `Stream.discard` → demux-level skip.
`streams.get/subtitles/attachments/data` → track pickers.
`AttachmentStream.data` → font/cover extraction. rate/start/id/tag/
options → VFR + tag diagnostics. `search_timestamp` → keyframe seek.
`Container.Flags` → corrupt recovery + fast preview. `ContainerFormat`
direct → muxer validation. timeout/buffer/stream-options → finer
network control. `AVRational` math → exact fps. `logging` beyond
set/Capture → per-job native logs. error subclasses → precise failure
cards. `Dictionary` → low-level option interop. `datasets` + `python -m
av` → fixtures + bug-report dumps. `Disposition` beyond attached_pic →
full track badges. `set_chapters` authoring (app only copies).
