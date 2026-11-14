"""The per-op engine dispatch: job params → engine calls.

Lives outside main.py so the controller stays wiring-only; the state
facade is passed in (tests import and call these directly)."""

from __future__ import annotations

from core.constants import (
    DEFAULT_AUDIO_CODEC,
    DEFAULT_CONTAINER,
    DEFAULT_EXTRACT_FORMAT,
    DEFAULT_GIF_FPS,
    DEFAULT_GIF_WIDTH,
    DEFAULT_JPEG_FORMAT,
    DEFAULT_SUBTITLE_FORMAT,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_PRESET,
)


def _build_job_dispatch(engine, state, job, _on_progress, cancel_evt):
    """Build the per-op engine call for one job.

    Module-level so a forked worker process can construct and run it
    without pickling closures.
    """
    p = job.params

    def _run_convert():
        engine.convert(
            input_path=job.input_path,
            output_path=job.output_path,
            video_codec=p.get("video_codec", DEFAULT_VIDEO_CODEC),
            audio_codec=p.get("audio_codec", DEFAULT_AUDIO_CODEC),
            crf=p.get("crf", 23),
            preset=p.get("preset", DEFAULT_VIDEO_PRESET),
            fps=p.get("fps"),
            scale_width=p.get("scale_width"),
            scale_height=p.get("scale_height"),
            speed=p.get("speed", 1.0),
            volume_pct=p.get("volume_pct", 100),
            rotation=p.get("rotation", 0),
            crop_aspect=p.get("crop"),
            eq=p.get("eq"),
            denoise=p.get("denoise"),
            sharpen=p.get("sharpen"),
            watermark=p.get("watermark"),
            hardware_accel=bool(
                p.get(
                    "hardware_accel",
                    state.settings.get("hardware_accel", True),
                )
            ),
            # Generic option panel (components/encoder_options.py): encoder keys
            # and muxer keys the user set. Both optional; absent = old behavior.
            # video_filter/audio_filter are the Terminal's -vf/-af chains.
            video_filter=p.get("video_filter"),
            audio_filter=p.get("audio_filter"),
            encoder_options=p.get("encoder_options"),
            audio_encoder_options=p.get("audio_encoder_options"),
            container_options=p.get("container_options"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_compress():
        engine.compress_to_target(
            input_path=job.input_path,
            output_path=job.output_path,
            target_size_mb=p.get("target_size_mb", 16.0),
            video_codec=p.get("video_codec"),
            encoder_options=p.get("encoder_options"),
            container_options=p.get("container_options"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_cut():
        engine.cut_trim(
            input_path=job.input_path,
            output_path=job.output_path,
            start_seconds=p.get("start_seconds", 0.0),
            end_seconds=p.get("end_seconds", 10.0),
            stream_copy=p.get("stream_copy", True),
            video_codec=p.get("video_codec"),
            encoder_options=p.get("encoder_options"),
            container_options=p.get("container_options"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_extract_audio():
        engine.extract_audio(
            input_path=job.input_path,
            output_path=job.output_path,
            format_name=p.get("format_name", DEFAULT_EXTRACT_FORMAT),
            bitrate_kbps=p.get("bitrate_kbps", 192),
            target_lufs=p.get("target_lufs"),
            channels=p.get("channels"),
            sample_rate=p.get("sample_rate"),
            audio_filter=p.get("audio_filter"),
            encoder_options=p.get("encoder_options"),
            container_options=p.get("container_options"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_extract_frames():
        engine.extract_frames(
            input_path=job.input_path,
            output_dir=job.output_path,
            count=p.get("count", 5),
            format_name=p.get("format_name", DEFAULT_JPEG_FORMAT),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_extract_subtitles():
        engine.extract_subtitles(
            input_path=job.input_path,
            output_path=job.output_path,
            stream_index=p.get("stream_index", 0),
            format_name=p.get("format_name", DEFAULT_SUBTITLE_FORMAT),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_record():
        # Per-download override (streams "Download anyway") is stored on
        # the job, not the setting: None lifts the cap for this take.
        cap_override = p.get("ignore_hls_cap", False)
        engine.record(
            input_url=p.get("url", job.input_path),
            output_path=job.output_path,
            container_format=p.get("format"),
            duration_s=p.get("duration_s"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
            max_hls_download_mb=(
                None if cap_override else state.settings.get("max_hls_download_mb", 2048)
            ),
        )

    def _run_concat():
        engine.concat(
            paths=p.get("paths", [job.input_path]),
            output_path=job.output_path,
            container_format=p.get("container", DEFAULT_CONTAINER),
            transition=p.get("transition", "cut"),
            fade_s=p.get("fade_s", 0.5),
            video_codec=p.get("video_codec"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_remux():
        engine.remux(
            input_path=job.input_path,
            output_path=job.output_path,
            drop_indices=p.get("drop", []),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    def _run_create_gif():
        engine.create_gif(
            input_path=job.input_path,
            output_path=job.output_path,
            fps=p.get("fps", DEFAULT_GIF_FPS),
            width=p.get("width", DEFAULT_GIF_WIDTH),
            start_s=p.get("start_s", 0.0),
            duration_s=p.get("duration_s", 5.0),
            encoder_options=p.get("encoder_options"),
            container_options=p.get("container_options"),
            on_progress=_on_progress,
            cancel_event=cancel_evt,
        )

    return {
        # name, retry clones params verbatim, and unknown ops fail loudly.
        "convert": _run_convert,
        "compress": _run_compress,
        "cut": _run_cut,
        "extract_audio": _run_extract_audio,
        "extract_frames": _run_extract_frames,
        "extract_subtitles": _run_extract_subtitles,
        "record": _run_record,
        "concat": _run_concat,
        "remux": _run_remux,
        "create_gif": _run_create_gif,
    }


def _dispatch_job_op(dispatch, job):
    """Run the adapter for ``job.op``; unknown ops fail loudly."""
    run = dispatch.get(job.op)
    if run is None:
        # Unknown op: fail LOUDLY naming the op. Falling through to
        # completed-doing-nothing once faked success for a typo'd op.
        raise ValueError(f"Unknown job op {job.op!r} — no engine path dispatches it")
    run()
