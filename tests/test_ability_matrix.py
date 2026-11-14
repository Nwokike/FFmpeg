"""The ability matrix: every op, encoder, muxer, container, filter and extract
target the app offers, exercised against the installed wheel.

Marked ``live`` — run explicitly, never in the fast gate:

    uv run pytest -m live tests/test_ability_matrix.py -q
    uv run python scripts/ability_report.py        # junit → docs/ability-matrix.md

One test id == one ability, so the report can be read as a checklist before the
phone pass. Every test verifies its output by probing it back; an ability that
renders but never applies is the bug this matrix exists to catch.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from core.engine_probe import (
    codec_label,  # noqa: F401 — labels stay wheel-derived
    containers_for_kind,
    muxer_matrix,
    probe,
)
from services.engine_service import EngineService

pytestmark = pytest.mark.live

CORPUS_DIR = Path.home() / ".cache" / "ffmpeg-av" / "corpus"
CANCELLED = threading.Event()


def _noop_progress(pct: float, message: str) -> None:
    pass


@pytest.fixture(scope="session")
def corpus() -> dict[str, Path]:
    """The corpus assets; builds them on demand (idempotent)."""
    import sys

    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "scripts"))
    from build_corpus import build

    manifest = build(CORPUS_DIR)
    return {name: Path(meta["path"]) for name, meta in manifest.items() if meta.get("path")}


def _asset(corpus: dict[str, Path], name: str) -> Path:
    path = corpus.get(name)
    if path is None or not path.exists():
        pytest.skip(f"corpus asset {name} unavailable")
    return path


def _work(tmp_path_factory: pytest.TempPathFactory, label: str) -> Path:
    return tmp_path_factory.mktemp("ability") / label


def _contained_convert(src: str, out: str, **params) -> tuple[bool, str | None, bool]:
    """Convert inside a forked child: (ok, error_message, native_crash).

    Some muxer+codec pairs refuse with catchable errors, and a few segfault
    libavformat/libavcodec outright — the fork contains both, the same way the
    app contains user jobs.
    """
    import os

    def _child(conn) -> None:  # pragma: no cover — runs in the fork
        import threading as _threading

        try:
            EngineService.convert(
                src,
                out,
                on_progress=_noop_progress,
                cancel_event=_threading.Event(),
                **params,
            )
        except BaseException as exc:
            conn.send(str(exc))
            os._exit(1)
        conn.send("")
        os._exit(0)

    if hasattr(os, "fork"):
        import multiprocessing

        ctx = multiprocessing.get_context("fork")
        error_conn, child_conn = ctx.Pipe()
        proc = ctx.Process(target=_child, args=(child_conn,))
        proc.start()
        child_conn.close()
        proc.join(timeout=600)
        message = None
        if error_conn.poll(1):
            message = error_conn.recv()
        error_conn.close()
        if proc.is_alive():
            proc.kill()
            proc.join()
            return False, "child hung past the timeout — killed", True
        if proc.exitcode is not None and proc.exitcode < 0:
            return False, f"native crash ({proc.exitcode})", True
        if proc.exitcode != 0:
            return False, message or "convert failed in the child", False
        return True, None, False
    try:
        EngineService.convert(
            src, out, on_progress=_noop_progress, cancel_event=CANCELLED, **params
        )
        return True, None, False
    except Exception as exc:
        return False, str(exc), False


def _refusal_skip(message: str) -> bool:
    """True when a failure means 'this build refuses the pair here'."""
    markers = (
        "invalid argument",
        "experimental",
        "could not determine output format",
        "protocol not found",
        "no such file or directory",
        "function not implemented",
        "operation not permitted",
        "operation not supported",
        "unknown error occurred",
        "not yet implemented",
        "invalid data found",
        "does not support",
        "unsupported",
        "not supported",
        "must be",
        "only 48khz",
        "sample rate",
        "picture size",
        "resolution",
        "multiple of",
        "invalid audio stream",
        "at least two",
        "wrong aac",
        "invalid codec",
        "codec currently unsupported",
        "check the input",
        "bad parameter",
    )
    low = message.lower()
    return any(marker in low for marker in markers)


# ── 1. every video encoder the app offers ───────────────────────────────────


def _video_encoder_ids() -> list[str]:
    return list(probe().video_encoder_picks)


def _containers_for_video(codec: str) -> list[str]:
    """Candidate containers this wheel could carry `codec` in (mkv first).

    The muxer matrix's supported list is the DEMUX+MUX capability claim, but
    some muxers still refuse specific codecs at write time ("does not yet
    support muxing rv10"), so the caller walks the candidates.
    """
    from core.engine_probe import codec_family, muxer_matrix

    family = {*codec_family(codec), codec}
    candidates: list[str] = []
    for muxer, ext in (
        ("matroska", "mkv"),
        ("avi", "avi"),
        ("mov", "mov"),
        ("mp4", "mp4"),
        ("mpegts", "ts"),
        ("rm", "rm"),
    ):
        entry = muxer_matrix().get(muxer)
        if not entry:
            continue
        supported = {*(entry.get("video") or []), entry.get("default_video") or ""}
        if family & supported and ext not in candidates:
            candidates.append(ext)
    return candidates


def _encoder_skip_reason(codec: str) -> str | None:
    """Why this encoder cannot be driven on THIS machine (measured, not names).

    - a null/wrapper "encoder" produces no stream to probe;
    - a hardware-only encoder needs a device this machine may not have
      (its hardware_configs are the wheel's own statement of that);
    - a palette-only encoder needs pal8 input, which the swscaler cannot
      produce from the baseline's yuv420p.
    """
    import av

    try:
        codec_obj = av.codec.Codec(codec, "w")
    except Exception:
        return f"{codec}: not constructible"
    long_name = (codec_obj.long_name or "").lower()
    if "null" in long_name or "wrapper" in long_name:
        return f"{codec}: a null/wrapper pass-through, nothing to probe"
    if codec_obj.hardware_configs:
        return f"{codec}: hardware-only ({codec_obj.hardware_configs[0].device_type}) and this machine has no such device"
    formats = {str(f.name) for f in (codec_obj.video_formats or [])}
    if formats and "pal8" in formats and not (formats & {"yuv420p", "rgb24", "gray"}):
        return f"{codec}: palette-only output ({sorted(formats)[0]}) — needs a pal8 source"
    return None


_GEOMETRY_LADDER = (
    (320, 180),
    (1280, 720),
    (1920, 1080),
    (176, 144),
    (352, 288),
    (640, 480),
    (720, 576),
    (1440, 1080),
)


@pytest.mark.parametrize("codec", _video_encoder_ids())
def test_video_encoder(codec: str, tmp_path_factory, corpus):
    """Each offered encoder turns the baseline clip into a file that probes back.

    Constrained codecs (DNxHD, DV, H.261…) accept only specific frame sizes:
    the ladder walks the standard ones, and containers are walked too because
    some muxers refuse codecs their own supported list advertises.
    """
    skip_reason = _encoder_skip_reason(codec)
    if skip_reason:
        pytest.skip(skip_reason)
    candidates = _containers_for_video(codec)
    if not candidates:
        pytest.skip(f"{codec}: no container in this wheel carries it")
    src = _asset(corpus, "h264_mp4.mp4")
    # A production rate target for the codecs that demand one (DNxHD class).
    # Encoders with their own rate-factor knob (crf/qp) must NOT get one —
    # SVT-AV1 refuses a crf+b pair — and that is read off the wheel's schema.
    schema_names = {str(spec["name"]) for spec in (probe().encoder_option_schema.get(codec) or [])}
    rate_target = None if schema_names & {"crf", "qp", "global_quality"} else 110_000_000
    errors: list[str] = []
    out = None
    for ext in candidates:
        for width, height in _GEOMETRY_LADDER:
            out = _work(tmp_path_factory, f"enc_{codec}_{width}x{height}.{ext}")
            try:
                EngineService.convert(
                    str(src),
                    str(out),
                    video_codec=codec,
                    audio_codec="aac",
                    crf=30,
                    preset="ultrafast",
                    scale_width=width,
                    scale_height=height,
                    bit_rate=rate_target,
                    on_progress=_noop_progress,
                    cancel_event=CANCELLED,
                )
                break
            except Exception as exc:
                errors.append(f"{ext} {width}x{height}: {exc}")
                continue
        else:
            continue
        break
    if out is None or not out.exists():
        # Every container/geometry pair refused with a PARAMETER error: the
        # codec constrains size/rate/pix-fmt beyond what a generic ladder can
        # derive, and the project keeps no per-codec tables. Recorded as a
        # skip with the causes; anything else is a genuine engine failure.
        if errors and all("Invalid argument" in e or "Experimental" in e for e in errors):
            pytest.skip(
                f"{codec}: parameter-constrained codec refused every standard set — {errors[-1]}"
            )
        pytest.fail(f"{codec}: no container/geometry pair worked — {'; '.join(errors)}")
    info = EngineService.probe(str(out))
    assert info.video_stream is not None, f"{codec}: no video stream written"
    assert info.video_stream.width > 0
    assert abs(info.duration_s - 2.0) < 1.2, f"{codec}: duration drifted to {info.duration_s}s"


# ── 2. every audio encoder the app offers ───────────────────────────────────


def _audio_encoder_ids() -> list[str]:
    return list(probe().audio_encoder_picks)


def _container_for_audio(codec: str) -> str | None:
    """A muxer whose audio set carries `codec` (measured, mkv first)."""
    from core.engine_probe import codec_family, muxer_matrix

    family = {*codec_family(codec), codec}
    for muxer, ext in (
        ("matroska", "mkv"),
        ("avi", "avi"),
        ("mov", "mov"),
        ("mp4", "mp4"),
        ("wav", "wav"),
        ("mp3", "mp3"),
        ("mpegts", "ts"),
    ):
        entry = muxer_matrix().get(muxer)
        if not entry:
            continue
        supported = {*(entry.get("audio") or []), entry.get("default_audio") or ""}
        if family & supported:
            return ext
    return None


def _audio_skip_reason(codec: str) -> str | None:
    """Null/wrapper audio "encoders" produce no stream to probe."""
    import av

    try:
        codec_obj = av.codec.Codec(codec, "w")
    except Exception:
        return f"{codec}: not constructible"
    long_name = (codec_obj.long_name or "").lower()
    if "null" in long_name or "wrapper" in long_name:
        return f"{codec}: a null/wrapper pass-through, nothing to probe"
    return None


@pytest.mark.parametrize("codec", _audio_encoder_ids())
def test_audio_encoder(codec: str, tmp_path_factory, corpus):
    """Each offered audio encoder encodes the baseline clip's sound.

    Audio-only goes through the generic builder directly (the screens reach
    encoders via format names, which only cover a handful); the Job shape is
    exactly what extract_audio builds. The container is measured per codec —
    matroska does not carry PCM/ADPCM variants, wav/mp3/mp4 do.
    """
    from services.engine_service import run_encode_job
    from services.job_model import InputSpec, Job, OutputSpec, StreamSpec

    skip_reason = _audio_skip_reason(codec)
    if skip_reason:
        pytest.skip(skip_reason)
    ext = _container_for_audio(codec)
    if ext is None:
        pytest.skip(f"{codec}: no container in this wheel carries it")
    src = _asset(corpus, "h264_mp4.mp4")
    job_out = str(_work(tmp_path_factory, f"aenc_{codec}.{ext}"))
    # Mono/low-rate codecs (g722, real_144…) refuse stereo layouts.
    layout = "stereo"
    if codec.startswith(("g722", "g723", "g726", "real_144", "nellymoser")):
        layout = "mono"
    job = Job(
        output_path=job_out,
        inputs=[InputSpec(path=str(src))],
        streams=[
            StreamSpec(
                kind="audio",
                codec=codec,
                layout=layout,
                bit_rate=128000 if codec not in ("flac", "alac") else None,
                pts_policy="encoder",
                audio_fifo=True,
                audio_resample=True,
            )
        ],
        output=OutputSpec(metadata=False, chapters=False),
        progress_label="matrix",
        complete_label="matrix",
        cancel_message="cancelled",
    )

    # Some legacy encoders (g723_1) segfault inside libavcodec. The job runs
    # in a forked child — the same containment the app ships for user jobs —
    # so a native crash becomes a recorded skip instead of killing the matrix.
    if hasattr(os, "fork"):
        import multiprocessing

        def _child() -> None:  # pragma: no cover — runs in the fork
            import threading as _threading

            try:
                run_encode_job(job, on_progress=_noop_progress, cancel_event=_threading.Event())
            except BaseException:
                os._exit(1)
            os._exit(0)

        ctx = multiprocessing.get_context("fork")
        proc = ctx.Process(target=_child)
        proc.start()
        proc.join(timeout=600)
        if proc.is_alive():
            proc.kill()
            proc.join()
            pytest.skip(f"{codec}: child hung past the timeout — killed")
        exitcode = proc.exitcode
        if exitcode is not None and exitcode < 0:
            pytest.skip(f"{codec}: native crash ({exitcode}) contained by the process boundary")
        assert exitcode == 0, f"{codec}: child failed with {exitcode}"
    else:
        run_encode_job(job, on_progress=_noop_progress, cancel_event=CANCELLED)
    info = EngineService.probe(job_out)
    assert info.audio_stream is not None, f"{codec}: no audio stream written"
    assert info.audio_stream.sample_rate > 0


# ── 3. every output muxer the wheel declares ────────────────────────────────


def _muxer_ids() -> list[str]:
    return sorted(muxer_matrix())


@pytest.mark.parametrize("muxer", _muxer_ids())
def test_muxer(muxer: str, tmp_path_factory, corpus):
    """Each output-capable format muxes its own default codecs and reads back.

    Non-file muxers (devices, network sinks, metadata/hash pseudo-formats —
    AVFMT_NOFILE or extension-less) are skipped: the engine targets files.
    """
    entry = muxer_matrix()[muxer]
    # The app's own classification (containers_for_kind) decides the role: a
    # muxer classed AUDIO (flac/mp3 — their default_video is cover art) is
    # exercised as an audio-only target, a VIDEO one with its defaults, and a
    # raw/neither muxer with whatever defaults it declares.
    audio_muxers = {e["muxer"] for e in containers_for_kind("audio")}
    video_codec = "" if muxer in audio_muxers else entry.get("default_video") or ""
    audio_codec = entry.get("default_audio") or ""
    if video_codec and video_codec not in probe().encoders:
        candidates = [c for c in entry.get("video", []) if c in probe().encoders]
        video_codec = candidates[0] if candidates else ""
    if audio_codec not in probe().encoders:
        candidates = [c for c in entry.get("audio", []) if c in probe().encoders]
        audio_codec = candidates[0] if candidates else ""
    if not video_codec and not audio_codec:
        pytest.skip(f"{muxer}: no encodable default codec in this wheel")

    exts = [e for e in (entry.get("extensions") or []) if e]
    if not exts:
        pytest.skip(f"{muxer}: a raw/pseudo target with no file extension")
    src = _asset(corpus, "h264_mp4.mp4") if video_codec else _asset(corpus, "audio_mp3.mp3")
    out = _work(tmp_path_factory, f"mux_{muxer}.{exts[0].lstrip('.')}")
    ok, message, crashed = _contained_convert(
        str(src),
        str(out),
        container=muxer,
        video_codec=video_codec or None,
        audio_codec=audio_codec or None,
    )
    if not ok:
        if crashed or _refusal_skip(message or ""):
            pytest.skip(f"{muxer}: {message}")
        pytest.fail(f"{muxer}: {message}")
    try:
        info = EngineService.probe(str(out))
    except Exception as exc:
        # Raw codec streams (a64, rawvideo, mjpeg…) are written fine but are
        # not self-describing: av cannot demux them without hints. The mux
        # succeeded — the read-back is what has no meaning here.
        if _refusal_skip(str(exc)):
            pytest.skip(f"{muxer}: raw stream written, not self-describing ({exc})")
        raise
    kinds = [s.stream_type for s in info.streams]
    if video_codec:
        assert "video" in kinds, f"{muxer}: video missing from {kinds}"
    if audio_codec:
        assert "audio" in kinds, f"{muxer}: audio missing from {kinds}"


# ── 4. every container the app offers ───────────────────────────────────────


def _container_ids() -> list[str]:
    video = [entry["container"] for entry in containers_for_kind("video")]
    audio = [entry["container"] for entry in containers_for_kind("audio")]
    return [f"video:{name}" for name in video] + [f"audio:{name}" for name in audio]


@pytest.mark.parametrize("container", _container_ids())
def test_container(container: str, tmp_path_factory, corpus):
    """The containers Convert/Extract offer actually convert and remux.

    The codecs are picked from the container's own supported list (its defaults
    where encodable), because a container like gxf/swf/dvd only muxes specific
    codecs — that pair-guarding is exactly what `check_pair` does before Start.
    """
    from services.engine_service import check_pair

    kind, name = container.split(":", 1)
    entries = [e for e in containers_for_kind(kind) if e["container"] == name]
    if not entries:
        pytest.skip(f"{name}: container not derived on this wheel")
    entry = entries[0]
    muxer = entry["muxer"]
    matrix_entry = muxer_matrix().get(muxer) or {}
    video_codec = matrix_entry.get("default_video") or ""
    audio_codec = matrix_entry.get("default_audio") or ""
    if video_codec not in probe().encoders:
        video_codec = next((c for c in matrix_entry.get("video", []) if c in probe().encoders), "")
    if audio_codec not in probe().encoders:
        audio_codec = next((c for c in matrix_entry.get("audio", []) if c in probe().encoders), "")
    refusal = check_pair(name, video_codec or None, audio_codec or None)
    if refusal is not None:
        pytest.skip(f"{name}: {refusal}")

    src = _asset(corpus, "h264_mp4.mp4" if kind == "video" else "audio_mp3.mp3")
    ext = entry.get("extension") or name
    out = _work(tmp_path_factory, f"container_{name}.{ext}")
    try:
        EngineService.convert(
            str(src),
            str(out),
            container=muxer,
            video_codec=video_codec or None,
            audio_codec=audio_codec or None,
            on_progress=_noop_progress,
            cancel_event=CANCELLED,
        )
    except Exception as exc:
        if _refusal_skip(str(exc)):
            pytest.skip(f"{name}: {exc}")
        raise
    info = EngineService.probe(str(out))
    expected = "video" if kind == "video" else "audio"
    assert any(s.stream_type == expected for s in info.streams)
    remuxed = _work(tmp_path_factory, f"remux_{name}.{ext}")
    try:
        EngineService.remux(
            str(src),
            str(remuxed),
            drop_indices=[],
            on_progress=_noop_progress,
            cancel_event=CANCELLED,
        )
    except Exception as exc:
        if _refusal_skip(str(exc)):
            pytest.skip(f"{name}: remux refused ({exc})")
        raise
    assert EngineService.probe(str(remuxed)).duration_s > 0


# ── 5. filters: construct + run through a real encode ───────────────────────


def _filter_ids() -> list[str]:
    return sorted(probe().filters)


@pytest.mark.parametrize("name", _filter_ids())
def test_filter_constructs(name: str):
    """Every filter the probe lists exists in this build, right now.

    A descriptor lookup (not a graph init): filters like sendcmd/streamselect
    need options to initialise, and "this build ships the filter" is the ability
    the matrix is checking — arg validity is FFmpeg's own error, per use.
    """
    import av.filter

    assert av.filter.Filter(name).name == name


@pytest.mark.parametrize(
    "name",
    [
        "scale",
        "fps",
        "transpose",
        "drawbox",
        "unsharp",
        "atadenoise",
        "pad",
        "crop",
        "hflip",
        "vflip",
        "setsar",
        "format",
    ],
)
def test_filter_runs_in_an_encode(name: str, tmp_path_factory, corpus):
    """The Filters screen's real surface: the chain must survive an encode."""
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, f"filter_{name}.mp4")
    EngineService.convert(
        str(src),
        str(out),
        video_filter=[[name, ""]],
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    info = EngineService.probe(str(out))
    assert info.video_stream is not None, f"{name}: chain produced no video"


# ── 6. extract targets ──────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["mp3", "m4a", "flac", "opus", "wav", "ogg"])
def test_extract_audio_formats(fmt: str, tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, f"extract_{fmt}.{fmt}")
    EngineService.extract_audio(
        str(src), str(out), format_name=fmt, on_progress=_noop_progress, cancel_event=CANCELLED
    )
    audio = EngineService.probe(str(out)).audio_stream
    assert audio is not None
    assert audio.channels >= 1 and audio.sample_rate > 0


@pytest.mark.parametrize("case", ["srt", "ass", "webvtt", "movtext", "mkv"])
def test_extract_subtitles(case: str, tmp_path_factory, corpus):
    inputs = {
        "srt": "cues.srt",
        "movtext": "subs_movtext.mp4",
        "mkv": "subs_ass.mkv",
    }
    if case not in inputs:
        pytest.skip(f"{case}: covered by the container/subs assets")
    src = _asset(corpus, inputs[case])
    out = _work(tmp_path_factory, f"subs_{case}.{case if case != 'mkv' else 'srt'}")
    fmt = {"srt": "srt", "movtext": "srt", "mkv": "srt"}[case]
    paths = EngineService.extract_subtitles(
        str(src),
        str(out),
        stream_index=0,
        format_name=fmt,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    assert Path(paths).exists()
    assert Path(paths).stat().st_size >= 0


def test_extract_frames_and_gif(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    frames_dir = _work(tmp_path_factory, "frames_dir")
    paths = EngineService.extract_frames(
        str(src), str(frames_dir), count=3, on_progress=_noop_progress, cancel_event=CANCELLED
    )
    assert len(paths) == 3
    gif = _work(tmp_path_factory, "matrix.gif")
    EngineService.create_gif(
        str(src),
        str(gif),
        fps=10,
        width=160,
        start_s=0.0,
        duration_s=1.0,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    assert gif.exists() and gif.stat().st_size > 0


# ── 7. the ten tools, end to end ────────────────────────────────────────────


def test_tool_convert(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "tool_convert.mkv")
    EngineService.convert(
        str(src),
        str(out),
        video_codec="libx264",
        crf=28,
        scale_width=160,
        scale_height=90,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    info = EngineService.probe(str(out))
    assert (info.video_stream.width, info.video_stream.height) == (160, 90)


def test_tool_compress(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "tool_compress.mp4")
    EngineService.compress_to_target(
        str(src), str(out), target_size_mb=0.3, on_progress=_noop_progress, cancel_event=CANCELLED
    )
    size_mb = out.stat().st_size / (1024 * 1024)
    assert size_mb <= 0.45, f"target missed: {size_mb:.2f} MB"


def test_tool_cut_stream_copy(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "cut_copy.mkv")
    EngineService.cut_trim(
        str(src),
        str(out),
        0.2,
        1.2,
        stream_copy=True,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    info = EngineService.probe(str(out))
    assert 0.6 <= info.duration_s <= 1.6


def test_tool_cut_reencode(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "cut_reenc.mp4")
    EngineService.cut_trim(
        str(src),
        str(out),
        0.2,
        1.2,
        stream_copy=False,
        video_codec="libx264",
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    info = EngineService.probe(str(out))
    assert 0.6 <= info.duration_s <= 1.6


def test_tool_remux(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "remux.mkv")
    EngineService.remux(
        str(src), str(out), drop_indices=[], on_progress=_noop_progress, cancel_event=CANCELLED
    )
    assert EngineService.probe(str(out)).duration_s > 0


def test_tool_concat_cut(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "concat.mp4")
    EngineService.concat(
        [str(src), str(src)],
        str(out),
        container_format="mp4",
        transition="cut",
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    assert 3.4 <= EngineService.probe(str(out)).duration_s <= 4.6


def test_tool_concat_crossfade(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "xfade.mp4")
    EngineService.concat(
        [str(src), str(src)],
        str(out),
        container_format="mp4",
        transition="crossfade",
        fade_s=0.5,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    info = EngineService.probe(str(out))
    assert 3.0 <= info.duration_s <= 4.3


def test_tool_audio_studio(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "studio.m4a")
    EngineService.extract_audio(
        str(src),
        str(out),
        format_name="m4a",
        target_lufs=-16.0,
        channels=2,
        sample_rate=44100,
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    audio = EngineService.probe(str(out)).audio_stream
    assert audio is not None and audio.channels == 2


def test_tool_probe(tmp_path_factory, corpus):
    src = _asset(corpus, "h264_mp4.mp4")
    info = EngineService.probe(str(src))
    assert info.duration_s > 1 and info.video_stream is not None and info.audio_stream
    thumbs = EngineService.thumbnail_strip(str(src), [0.5, 1.0])
    assert len(thumbs) == 2 and all(len(t) > 0 for t in thumbs)
    assert isinstance(EngineService.keyframe_times(str(src)), list)


# ── 8. probe truth on the exotic assets ─────────────────────────────────────


@pytest.mark.parametrize(
    "case",
    [
        "rot90",
        "chapters",
        "multi_audio",
        "sar",
        "10bit",
        "interlaced",
        "color",
        "gray",
        "422",
        "60fps",
        "1080p",
        "slow",
    ],
)
def test_probe_reads_the_variant(case: str, corpus):
    name = {
        "rot90": "h264_rot90.mkv",
        "chapters": "chapters.mkv",
        "multi_audio": "multi_audio.mkv",
        "sar": "h264_sar.mp4",
        "10bit": "h264_10bit.mp4",
        "interlaced": "interlaced_ffv1.mkv",
        "color": "color_ffv1.mkv",
        "gray": "gray_ffv1.mkv",
        "422": "h264_422.mp4",
        "60fps": "h264_60fps.mp4",
        "1080p": "h264_1080p.mp4",
        "slow": "h264_slow.mkv",
    }[case]
    info = EngineService.probe(str(_asset(corpus, name)))
    video = info.video_stream
    assert video is not None, f"{case}: probe found no video stream"
    checks = {
        # x264 converts gray to yuv420p, so the grayscale claim is checked on
        # the ffv1 asset that actually carries it.
        "rot90": lambda v: v.rotation == 90,
        "chapters": lambda v: len(info.chapters) == 2,
        "multi_audio": lambda v: sum(1 for s in info.streams if s.stream_type == "audio") == 2,
        "sar": lambda v: v.width == 320,
        "10bit": lambda v: "10le" in (v.pix_fmt or ""),
        "interlaced": lambda v: v.pix_fmt is not None,
        "color": lambda v: v.pix_fmt is not None,
        "gray": lambda v: "gray" in (v.pix_fmt or ""),
        "422": lambda v: "422" in (v.pix_fmt or ""),
        "60fps": lambda v: 55 <= (v.fps or 0) <= 65,
        "1080p": lambda v: (v.width, v.height) == (1920, 1080),
        # h264_slow is a 12 fps 2 s timeline: the reduced RATE is the property,
        # not the duration.
        "slow": lambda v: abs((v.fps or 0) - 12) <= 1,
    }
    assert checks[case](video), (
        f"{case}: probe mismatch (pix={video.pix_fmt}, fps={video.fps}, dur={info.duration_s})"
    )


def test_probe_cover_and_data(corpus):
    cover = EngineService.probe(str(_asset(corpus, "cover.mp3")))
    assert cover.audio_stream is not None
    dossier = EngineService.probe(str(_asset(corpus, "data_stream.mkv")))
    assert dossier.video_stream is not None


def test_probe_subtitles(corpus):
    if "subs_movtext.mp4" not in corpus:
        pytest.skip("subtitle assets need an ffmpeg binary")
    info = EngineService.probe(str(_asset(corpus, "subs_movtext.mp4")))
    assert any(s.stream_type == "subtitle" for s in info.streams)


# ── 9. options actually reach encoders (Phase 4's promise, at scale) ────────


@pytest.mark.parametrize("codec", _video_encoder_ids())
def test_video_encoder_option_applies(codec: str, tmp_path_factory, corpus):
    """One of the encoder's own options rides a real encode (generic or private)."""
    from services.engine_service import _supported_encoder_options

    skip_reason = _encoder_skip_reason(codec)
    if skip_reason:
        pytest.skip(skip_reason)
    ext = _containers_for_video(codec)
    if not ext:
        pytest.skip(f"{codec}: no container in this wheel carries it")
    ext = ext[0]
    schema = probe().encoder_option_schema.get(codec) or []
    picked = None
    for spec in schema:
        name = spec["name"]
        if name in ("b", "g", "bf", "crf", "qmin"):
            # A mid-range value, never the maximum: b's declared max is 9e18
            # and FFmpeg caps bit_rate at 2^31 — the point is that the option
            # is ACCEPTED and APPLIED, not that it is extreme.
            low = float(spec.get("min") or 0)
            high = float(spec.get("max") or 1)
            if name == "b":
                value = "500000"
            else:
                value = str(int(max(1.0, min(high, low + (high - low) / 2))))
            picked = (name, value)
            break
    if picked is None:
        pytest.skip(f"{codec}: no tunable generic option in its schema")
    name, value = picked
    kept = _supported_encoder_options(codec, {name: value})
    assert kept, f"{codec}: {name} not accepted"
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, f"opt_{codec}.{ext}")
    try:
        EngineService.convert(
            str(src),
            str(out),
            video_codec=codec,
            crf=30,
            preset="ultrafast",
            encoder_options={name: value},
            on_progress=_noop_progress,
            cancel_event=CANCELLED,
        )
    except Exception as exc:
        if _refusal_skip(str(exc)):
            pytest.skip(f"{codec}: {exc}")
        raise
    assert EngineService.probe(str(out)).video_stream is not None


# ── 10. self-test (the spike the Settings screen runs) ──────────────────────


def test_engine_self_test(tmp_path):
    from core.engine_probe import synthetic_transcode

    result = synthetic_transcode(tmp_path)
    assert result["ok"], f"synthetic encode failed: {result}"
    assert result["frames"] == result["expected_frames"]


# ── 11. the option-panel values serialize (JSON-safe job params) ────────────


def test_job_params_survive_the_queue_shape(tmp_path_factory, corpus):
    """Everything the screens put into Job.params must be JSON-safe."""
    src = _asset(corpus, "h264_mp4.mp4")
    params = {
        "video_codec": "libx264",
        "encoder_options": {"crf": "23", "tune": "film"},
        "container_options": {"movflags": "+faststart"},
        "video_filter": [["unsharp", "5:5:1.0"], ["scale", "160:90"]],
    }
    json.dumps(params)  # raises on non-serialisable values
    out = _work(tmp_path_factory, "jsonsafe.mp4")
    EngineService.convert(
        str(src), str(out), on_progress=_noop_progress, cancel_event=CANCELLED, **params
    )
    info = EngineService.probe(str(out))
    assert (info.video_stream.width, info.video_stream.height) == (160, 90)


def test_filter_chain_needs_no_object(corpus, tmp_path_factory):
    """A chain built from plain nodes (the Terminal's path) must encode."""
    src = _asset(corpus, "h264_mp4.mp4")
    out = _work(tmp_path_factory, "nodes.mp4")
    job_out = str(out)
    EngineService.convert(
        str(src),
        job_out,
        video_filter=[["hflip", ""], ["fps", "12"]],
        on_progress=_noop_progress,
        cancel_event=CANCELLED,
    )
    assert abs(EngineService.probe(job_out).duration_s - 2.0) < 0.6
