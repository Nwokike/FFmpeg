# Engine architecture (Phase 3)

Status: the generic builders are in place (commits `f1cfc29`…`f57c2a1`); worker-process
containment is designed below and tracked as the final Phase 3 item.

## The problem this solves

Before Phase 3, `services/engine_service.py` hand-built every FFmpeg pipeline:
three copies of the monotonic-PTS helpers, four bespoke timestamp-rebase schemes
(cut copy, concat copy, concat reencode, crossfade timeline, record zero-base),
four bespoke filter-graph builders, hand-written subtitle writers, an HLS parser,
and ten per-op encode loops. av owns timestamps and muxing — that machinery was
pure duplication and the main source of timestamp regressions.

## The job model

`services/job_model.py`:

```
InputSpec(path, format, options, timeout, hwaccel, seek_s)
StreamSpec(kind, selector, codec, bit_rate, fps, speed, cap_fps, pix_fmt,
           fine_time_base, scale_width/height, crop_aspect, rotation,
           even_align, layout, channels, sample_rate, encoder_options,
           pts_policy ("monotonic" | "encoder"), audio_fifo, audio_resample)
FilterChain(nodes=[(name, args)] or build=callable(first_frame), fifo=bool)
OutputSpec(container, options, metadata, chapters, rotation)
Job(output_path, inputs, streams, output, video_chain, audio_chain,
    window, progress_label, complete_label, cancel_message,
    drop_indices, keep_attachments, chapters (None=copy, list=replace,
    CHAPTERS_SKIP=untouched), zero_base, repair_pts_dts, timeline_shift,
    bsf_codecs, record_mode, duration_cap_s, input_containers)
```

A Job describes WHAT to produce; two builders implement HOW.

## Encode builder — `run_encode_job()`

One loop for every op that produces encoded output:

```
open input(s) -> map/add output streams -> optional chains ->
demux -> decode -> [window filter] -> [chain push/pull] -> reformat ->
stamp (monotonic or encoder-assigned pts) -> encode -> clamp-mux ->
drain chains -> flush encoders
```

- Multi-input (concat): all inputs iterate over the SAME encoder pair; per-file
  progress steps; `pts_policy="encoder"` keeps the timeline continuous.
- Audio fixed-frame encoders (AAC/MP3/FLAC): `audio_fifo` batches decoder frames
  to the encoder's real `frame_size` (encoder pre-opened via `start_encoding`).
- Rate/layout conversion: soxr (`precision 28`) with swr fallback, per-stream.
- Timestamp policies: `monotonic` floors duplicates/backwards jumps the muxer
  rejects; `encoder` leaves `pts=None` where the encoder owns sequencing.
- One native-log capture (`@_with_native_logs`) covers every encode-path op.

## Packet builder — `run_copy_job()`

One loop for stream-copy ops:

```
per input: select template streams -> rescale_ts onto the target clock ->
window filter (cut) -> zero-base rebase (cut copy, record) or timeline
shift (concat: boundary delta + running cursors, rescaled to the first
clip's time base) -> optional BSF (record: h264/hevc -> Annex-B) -> clamp-mux
```

- Keyframe snap (`snap_to_keyframe`) lives in the builder; cut copy notices
  progress at 0% when the start snaps.
- Record semantics: live progress copy ("Recording… 12s • 340 KB"), duration
  cap, and cancel KEEPS the partial file (returns normally).
- Attachments/metadata/chapters: remux and cut copy copy them; concat/record
  skip (`CHAPTERS_SKIP`).

## Presets (op → Job)

| Op | Builder | Preset |
|---|---|---|
| convert | encode | both streams, optional chains, windows/rotation/crop/speed/scale, op labels |
| compress | encode | bitrate ladders, resolution ladder, chapters off |
| cut (re-encode) | encode | seek−2 s + window, no metadata/chapters |
| cut (stream copy) | copy | snap + zero-base + repair, window |
| extract_audio | encode | format→codec derivation, loudnorm graph as chain build, FIFO+resampler, `pts_policy=encoder` |
| create_gif | encode | palette chain, `rgb8`, encoder pts policy, window |
| remux | copy | drop indices, attachments, chapters copy/replace, display-matrix rotation |
| concat (cut/copy) | copy | timeline shift, positional stream mapping |
| concat (re-encode) | encode | multi-input, first clip's fps/size, crf 23/fast, no metadata |
| record | copy | pre-opened network container, zero-base, Annex-B BSF, record semantics |

## Dispatch — `JOB_DISPATCH`

`main._job_runner` builds one closure per op over `JOB_DISPATCH` (module-level in
`main.py`), looks it up by `job.op`, and fails loudly on unknown ops. Retry
clones params verbatim, so every op keeps its own param contract.

## Worker-process containment (designed; NOT yet implemented)

Native crashes (segfault in libavcodec on a corrupt file) kill the whole app in
thread mode. This is the remaining Phase 3 item. Design (refined while
consolidating the dispatch builder):

- **No job_queue changes.** Isolation lives entirely in `main.py`: the queue
  already receives a `runner(job, cancel_evt)` callable, so containment is a
  different runner, not a different queue. `JobQueue(runner=_isolated_runner)`
  vs `JobQueue(runner=_job_runner)`.
- **The child runs only `_dispatch_job_op`** (`_build_job_dispatch(...)[op]()`),
  never `_job_runner`, so no Flet/history/navigation calls happen off-main.
- **Progress**: `_post_progress` gains a module-level sink override
  (`_PROGRESS_SINK`); the child swaps in a pipe-backed sink that forwards
  `(pct, msg)` tuples, and the parent relays them into the real
  `_progress_events` queue so the existing drain loop/UI are unchanged.
- **Cancel/pause**: a shared `multiprocessing.Event` pair; the parent mirrors
  `queue.pause_event` and the per-job `cancel_evt` into the child each poll,
  and the child rebinds the engine service's module-level pause event.
- **Reconcile**: a child that dies (non-zero exit / EOF without cancel) raises
  `RuntimeError` in the parent, which flows through the same terminal-field
  application as any runner exception (job `failed` + `error_message`); a
  cancelled child follows today's cancelled path.
- **POSIX fork only** (`multiprocessing.get_context("fork")`); other platforms
  keep the in-thread runner, with a runtime fallback if fork fails at spawn.
- **Required regression net before enabling**: identical-output test (same clip
  through both runners), crash test (child `os._exit`), cancel test, progress
  delivery test. Default stays OFF until that net exists and the device smoke
  passes.
