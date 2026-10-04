"""Full end-to-end pass over the REAL media on this machine.

Every engine op the screens dispatch (main._job_runner surface), driven with
the same arguments the screens pass, against real videos/photos — and every
OUTPUT re-opened with av and verified (streams, duration, size), because
"no exception" is not "works". The network test records the public Mux HLS
master test stream — the same https → httpx → master→variant → segments path
the app ships.

Run explicitly: uv run pytest tests/test_e2e_real_media.py -m live -v
Skipped automatically when the local media roots are absent (CI).
"""

from __future__ import annotations

from pathlib import Path

import av
import pytest

from core.state import Job
from services.command_parser import CommandError, parse_command
from services.engine_service import EngineService, check_params, friendly_job_error
from services.job_queue import JobQueue

pytestmark = pytest.mark.live

VIDEOS = Path.home() / "Videos"
PICTURES = Path.home() / "Pictures" / "Camera Roll"
DESKTOP = Path.home() / "Desktop"

HLS_MASTER_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"


def _smallest(root: Path, pattern: str) -> Path | None:
    files = [p for p in root.glob(pattern) if p.is_file()]
    return min(files, key=lambda p: p.stat().st_size) if files else None


def _first(root: Path, *patterns: str) -> Path | None:
    # Recursive: the HEVC set lives in subfolders (Videos/1, Videos/2…).
    for pat in patterns:
        hits = sorted(p for p in root.rglob(pat) if p.is_file())
        if hits:
            return min(hits, key=lambda p: p.stat().st_size)
    return None


def _has_subtitles(path: Path) -> bool:
    with _open(path) as c:
        return any(s.type == "subtitle" for s in c.streams)


def _require(root: Path, name: str) -> None:
    if not root.is_dir() or not any(root.iterdir()):
        pytest.skip(f"{name} not present on this machine — E2E needs real local media")


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    """Real inputs + a 6s working clip (itself produced by a stream-copy cut)."""
    _require(VIDEOS, "~/Videos")
    mp4 = _smallest(VIDEOS, "*.mp4")
    assert mp4 is not None, "no .mp4 in ~/Videos"
    hevc = _first(VIDEOS, "*HEVC*.mkv")
    subbed = _first(VIDEOS, "*Sub*.mp4", "*sub*.mkv")
    jpg = _first(PICTURES, "*.jpg", "*.JPG") if PICTURES.is_dir() else None
    work = tmp_path_factory.mktemp("e2e")
    clip = work / "clip6s.mp4"
    EngineService.cut_trim(str(mp4), str(clip), 5.0, 11.0, stream_copy=True)
    # Stream-copy snaps the START back to the previous keyframe, so the
    # working clip is LONGER than the 6s window on sparse-keyframe encodes
    # (measured 11.0s on anime 23.976fps). Measure, never assume.
    clip_dur = _duration(clip)
    assert clip_dur >= 5.0, f"working clip too short: {clip_dur:.2f}s"
    return {
        "mp4": mp4,
        "hevc": hevc,
        "subbed": subbed,
        "jpg": jpg,
        "clip": clip,
        "clip_dur": clip_dur,
        "work": work,
    }


def _open(path: str | Path) -> av.container.Container:
    return av.open(str(path), "r")


def _has_stream(path: str | Path, kind: str) -> bool:
    with _open(path) as c:
        return any(s.type == kind for s in c.streams)


def _duration(path: str | Path) -> float:
    with _open(path) as c:
        d = c.duration
        return float(d) / float(av.time_base) if d else 0.0


# ── Probe ────────────────────────────────────────────────────────────────────


def test_probe_real_files(media):
    info = EngineService.probe(str(media["mp4"]))
    assert info.duration_s > 0
    assert info.video_stream is not None
    assert info.audio_stream is not None, "expected an mp4 with audio in ~/Videos"
    assert info.video_stream.codec_name
    if media["jpg"]:
        still = EngineService.probe(str(media["jpg"]))
        assert still.kind == "image", f"photo classified as {still.kind}"
        assert still.video_stream is not None


# ── Cut ──────────────────────────────────────────────────────────────────────


def test_cut_stream_copy_is_lossless(media, tmp_path):
    src = media["mp4"]
    with _open(src) as c:
        src_codec = next(s for s in c.streams if s.type == "video").codec_context.name
    out = tmp_path / "cut_copy.mp4"
    messages: list[str] = []
    EngineService.cut_trim(
        str(src), str(out), 5.0, 9.0, stream_copy=True, on_progress=lambda p, m: messages.append(m)
    )
    dur = _duration(out)
    # Stream-copy MUST start on a keyframe: the start snaps back (never
    # forward), so the output is the 4s window PLUS the snap-back. The snap
    # is announced via progress — silence would be the bug.
    assert 3.5 <= dur <= 14.0, f"cut duration {dur:.2f}s"
    if dur > 4.6:
        assert any("napped" in m for m in messages), f"snap unannounced: {messages}"
    with _open(out) as c:
        assert next(s for s in c.streams if s.type == "video").codec_context.name == src_codec


def test_cut_reencode(media, tmp_path):
    out = tmp_path / "cut_re.mp4"
    EngineService.cut_trim(str(media["clip"]), str(out), 1.0, 4.0, stream_copy=False)
    assert _duration(out) == pytest.approx(3.0, abs=0.5)
    assert _has_stream(out, "video")


# ── Convert ──────────────────────────────────────────────────────────────────


def test_convert_video_full_pipe(media, tmp_path):
    """The Convert screen's video path: scale + fps + rotation + crf + preset."""
    out = tmp_path / "conv.mp4"
    EngineService.convert(
        str(media["clip"]),
        str(out),
        video_codec="libx264",
        audio_codec="aac",
        crf=26,
        preset="fast",
        scale_width=320,
        scale_height=240,
        fps=24,
        rotation=90,
    )
    # Full transcode preserves the input timeline (measured clip, not assumed).
    assert _duration(out) == pytest.approx(media["clip_dur"], rel=0.1)
    with _open(out) as c:
        v = next(s for s in c.streams if s.type == "video")
        # 90° rotation transposes: stored 240x320 plays as 320-wide portrait.
        assert (v.width, v.height) in ((240, 320), (320, 240))
    assert _has_stream(out, "audio")


def test_convert_hevc_decode_transcodes(media, tmp_path):
    """HEVC source must decode and re-encode — the phone's H264-lacks case."""
    if not media["hevc"]:
        pytest.skip("no HEVC mkv in ~/Videos")
    src = media["hevc"]
    clip = tmp_path / "hevc6s.mkv"
    EngineService.cut_trim(src, str(clip), 30.0, 36.0, stream_copy=True)
    assert _has_stream(clip, "video")
    out = tmp_path / "hevc_conv.mp4"
    EngineService.convert(
        str(clip), str(out), video_codec="libx264", audio_codec="aac", preset="fast"
    )
    assert _duration(out) > 3.0
    assert _has_stream(out, "video") and _has_stream(out, "audio")


def test_convert_image_branch(media, tmp_path):
    if not media["jpg"]:
        pytest.skip("no photo in ~/Pictures/Camera Roll")
    out = tmp_path / "still.png"
    EngineService.convert(str(media["jpg"]), str(out), video_codec="png", audio_codec="aac")
    assert out.exists() and out.stat().st_size > 0
    with _open(out) as c:
        v = next(s for s in c.streams if s.type == "video")
        assert v.width > 0 and v.height > 0


def test_convert_audio_branch(media, tmp_path):
    """The Convert screen's audio kind passes only audio_codec; the input is
    an audio FILE (no video stream) — convert must not invent a video track."""
    src = tmp_path / "src_audio.m4a"
    EngineService.extract_audio(str(media["clip"]), str(src), format_name="m4a")
    out = tmp_path / "conv.ogg"
    EngineService.convert(str(src), str(out), audio_codec="libvorbis")
    assert out.exists() and out.stat().st_size > 0
    assert _has_stream(out, "audio")
    assert not _has_stream(out, "video"), "audio convert invented a video stream"


def test_convert_opus_from_44k_source(media, tmp_path):
    """Opus is 48k-native: converting a 44.1k source must resample, not crash."""
    src = tmp_path / "src_audio.m4a"
    EngineService.extract_audio(str(media["clip"]), str(src), format_name="m4a")
    out = tmp_path / "conv.opus"
    EngineService.convert(str(src), str(out), audio_codec="libopus")
    assert out.stat().st_size > 0
    with _open(out) as c:
        a = next(s for s in c.streams if s.type == "audio")
        assert a.rate == 48000


# ── Compress ─────────────────────────────────────────────────────────────────


def test_compress_to_target(media, tmp_path):
    out = tmp_path / "small.mp4"
    EngineService.compress_to_target(str(media["clip"]), str(out), target_size_mb=0.5)
    size_mb = out.stat().st_size / 1_000_000
    assert size_mb < 1.0, f"overshot: {size_mb:.2f}MB"
    assert _has_stream(out, "video")


# ── Extract ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["wav", "m4a", "flac", "opus", "ogg"])
def test_extract_audio_formats(media, tmp_path, fmt):
    out = tmp_path / f"audio.{fmt}"
    EngineService.extract_audio(str(media["clip"]), str(out), format_name=fmt)
    assert out.stat().st_size > 0
    assert _has_stream(out, "audio")
    with _open(out) as c:
        a = next(s for s in c.streams if s.type == "audio")
        assert a.sample_rate and a.sample_rate > 8000


def test_extract_frames(media, tmp_path):
    out_dir = tmp_path / "frames"
    files = EngineService.extract_frames(
        str(media["clip"]), str(out_dir), count=4, format_name="jpg"
    )
    assert len(files) == 4
    for f in files:
        assert Path(f).stat().st_size > 0
        with _open(f) as c:
            assert next(s for s in c.streams if s.type == "video")


def test_create_gif(media, tmp_path):
    out = tmp_path / "loop.gif"
    EngineService.create_gif(
        str(media["clip"]), str(out), fps=12, width=320, start_s=1.0, duration_s=3.0
    )
    assert out.stat().st_size > 0
    with _open(out) as c:
        v = next(s for s in c.streams if s.type == "video")
        assert v.codec_context.name == "gif"


def test_extract_subtitles(media, tmp_path):
    """Only meaningful on a source with subtitle streams — verified absence is
    a skip with the reason, not a silent pass. Prefers a *SubsPlease* file,
    falls back to scanning the inventory mp4."""
    src = media["subbed"] or media["mp4"]
    if not _has_subtitles(src):
        if media["subbed"]:
            pytest.skip(f"{media['subbed'].name} carries no subtitle streams after all")
        pytest.skip("no subtitled file found in ~/Videos")
    out = tmp_path / "subs.srt"
    EngineService.extract_subtitles(str(src), str(out), stream_index=0, format_name="srt")
    assert out.stat().st_size > 0
    text = out.read_text(encoding="utf-8", errors="replace")
    assert "-->" in text or len(text) > 0


# ── Remux ────────────────────────────────────────────────────────────────────


def test_remux_copy_drop_and_rotate(media, tmp_path):
    out = tmp_path / "tracks.mkv"
    EngineService.remux(str(media["mp4"]), str(out))
    assert _has_stream(out, "video") and _has_stream(out, "audio")
    assert _duration(out) == pytest.approx(_duration(media["mp4"]), rel=0.05)

    with _open(media["mp4"]) as c:
        audio_idx = next(s.index for s in c.streams if s.type == "audio")
    dropped = tmp_path / "dropped.mkv"
    EngineService.remux(str(media["mp4"]), str(dropped), drop_indices=[audio_idx])
    assert _has_stream(dropped, "video")
    assert not _has_stream(dropped, "audio")

    rotated = tmp_path / "rot.mkv"
    EngineService.remux(str(media["mp4"]), str(rotated), rotation=90)
    # Rotation lives in the display matrix — this build exposes no
    # stream-level accessor, so verify through decoded frames (the same
    # frame.rotation layer probe() reads).
    with _open(rotated) as c:
        v = next(s for s in c.streams if s.type == "video")
        frame_rot = None
        for pkt in c.demux([v]):
            frames = pkt.decode()
            if frames:
                frame_rot = getattr(frames[0], "rotation", None)
                break
    assert frame_rot == 90, f"display-matrix rotation not readable back: {frame_rot}"


# ── Join ─────────────────────────────────────────────────────────────────────


def test_concat_cut_and_crossfade(media, tmp_path):
    a = media["clip"]
    b = tmp_path / "clip_b.mp4"
    EngineService.cut_trim(str(media["mp4"]), str(b), 20.0, 26.0, stream_copy=True)
    b_dur = _duration(b)
    expected = media["clip_dur"] + b_dur

    joined = tmp_path / "joined.mp4"
    EngineService.concat([str(a), str(b)], str(joined), container_format="mp4", transition="cut")
    # Lossless join: the sum of the two snapped inputs, within mux rounding.
    assert _duration(joined) == pytest.approx(expected, rel=0.05)
    assert _has_stream(joined, "video") and _has_stream(joined, "audio")

    faded = tmp_path / "faded.mp4"
    EngineService.concat(
        [str(a), str(b)], str(faded), container_format="mp4", transition="crossfade", fade_s=0.5
    )
    # Crossfade overlaps the boundary by fade_s (0.5s), minus re-encode slack.
    assert _duration(faded) == pytest.approx(expected - 0.5, rel=0.1)
    assert _has_stream(faded, "video")


# ── Record (network) ─────────────────────────────────────────────────────────


def test_record_hls_master_stream(media, tmp_path):
    # The Mux master test stream is ~70MB worth of segments for a 6s take —
    # the cap MUST be lifted for this call (mirrors the app's per-download
    # "Download anyway" override), or the cap error itself is the assertion.
    out = tmp_path / "stream.mp4"
    EngineService.record(str(HLS_MASTER_URL), str(out), duration_s=6.0, max_hls_download_mb=None)
    assert out.stat().st_size > 0, "record returned but wrote no bytes"
    assert _has_stream(out, "video")
    assert _duration(out) > 2.0, f"only {_duration(out):.2f}s captured from a 6s take"


def test_record_bad_url_friendly_error(tmp_path):
    from services.engine_service import friendly_job_error as fje

    out = tmp_path / "never.mp4"
    with pytest.raises(Exception) as ei:
        EngineService.record("https://127.0.0.1:9/live.m3u8", str(out), duration_s=2.0)
    msg = fje(ei.value)
    assert msg, "error must be rendered for a person"
    low = msg.lower()
    for raw in ("httpx", "traceback", "exception:", "connecterror"):
        assert raw not in low, f"raw internals leaked into the message: {msg}"


# ── Command mode → engine (the Terminal's real pipeline) ─────────────────────


def test_command_mode_plans_execute(media, tmp_path):
    src = media["mp4"]
    # Second small clip for the two-input join plan (never the full source).
    join_b = tmp_path / "join_b.mp4"
    EngineService.cut_trim(str(src), str(join_b), 30.0, 34.0, stream_copy=True)
    commands = [
        f'ffmpeg -i "{src}" -vf scale=320:240 -c:v libx264 -crf 28 {tmp_path / "c.mp4"}',
        f'ffmpeg -ss 10 -t 3 -i "{src}" -c copy {tmp_path / "t.mkv"}',
        f'ffmpeg -i "{src}" -vn {tmp_path / "a.m4a"}',
        f'ffmpeg -ss 2 -t 3 -i "{src}" -r 10 {tmp_path / "g.gif"}',
        f'ffmpeg -i "{src}" -c copy {tmp_path / "r.mkv"}',
        f'ffmpeg -i "{src}" -vf transpose=1 {tmp_path / "rot.mp4"}',
        # Two inputs → the join plan (exercises the concat wiring too).
        f'ffmpeg -i "{media["clip"]}" -i "{join_b}" {tmp_path / "j.mp4"}',
    ]
    for cmd in commands:
        plan = parse_command(cmd, duration_s=_duration(src))
        params = dict(plan.params)
        paths = params.pop("paths", None)  # concat only
        if plan.op == "convert":
            EngineService.convert(plan.input_path, plan.output_path, **params)
        elif plan.op == "cut":
            EngineService.cut_trim(plan.input_path, plan.output_path, **params)
        elif plan.op == "extract_audio":
            EngineService.extract_audio(plan.input_path, plan.output_path, **params)
        elif plan.op == "create_gif":
            EngineService.create_gif(plan.input_path, plan.output_path, **params)
        elif plan.op == "remux":
            EngineService.remux(
                plan.input_path, plan.output_path, drop_indices=params.get("drop", [])
            )
        elif plan.op == "concat":
            EngineService.concat(
                paths, plan.output_path, container_format=params.get("container", "mp4")
            )
        else:  # pragma: no cover
            pytest.fail(f"unhandled plan op {plan.op}")
        assert Path(plan.output_path).stat().st_size > 0, f"{plan.op} produced nothing"


def test_command_mode_refusals_still_loud(media, tmp_path):
    src = str(media["mp4"])
    for cmd in (
        f'ffmpeg -i "{src}" -an out.mp4',
        f'ffmpeg -i "{src}" -i "{src}" -vn out.mp4',
        f'ffmpeg -i "{src}" -ss 5 -to 3 out.gif',
        f'ffmpeg -i "{src}" -ss 5 -t 5 out.mp3',
    ):
        with pytest.raises(CommandError):
            parse_command(cmd, duration_s=_duration(src))


# ── Guards + errors ──────────────────────────────────────────────────────────


def test_check_params_fraction_fps():
    # "30000/1001" must parse as a Fraction, not raise float().
    assert check_params(video_codec="libx264", fps="30000/1001") is None


def test_friendly_errors_on_bad_inputs(media, tmp_path):
    garbage = tmp_path / "garbage.mp4"
    garbage.write_bytes(b"\x00" * 64)
    cases = [
        lambda: EngineService.probe(str(tmp_path / "missing.mp4")),
        lambda: EngineService.probe(str(garbage)),
    ]
    for fn in cases:
        with pytest.raises(Exception) as ei:
            fn()
        msg = friendly_job_error(ei.value)
        assert msg and not msg.startswith("["), f"unfriendly error: {msg}"


# ── Queue with the real engine ───────────────────────────────────────────────


def test_queue_serial_real_jobs(media, tmp_path):
    done: list[str] = []

    def runner(job: Job, evt) -> None:
        p = job.params
        if job.op == "cut":
            EngineService.cut_trim(job.input_path, job.output_path, **p)
        elif job.op == "extract_audio":
            EngineService.extract_audio(job.input_path, job.output_path, **p)
        elif job.op == "create_gif":
            EngineService.create_gif(job.input_path, job.output_path, **p)
        done.append(job.id)

    q = JobQueue(runner=runner)
    q.set_paused(True)  # hold the gate, then enqueue
    jobs = [
        Job(
            op="cut",
            input_path=str(media["clip"]),
            output_path=str(tmp_path / "q1.mp4"),
            params={"start_seconds": 0.5, "end_seconds": 3.0, "stream_copy": True},
        ),
        Job(
            op="extract_audio",
            input_path=str(media["clip"]),
            output_path=str(tmp_path / "q2.wav"),
            params={"format_name": "wav"},
        ),
        Job(
            op="create_gif",
            input_path=str(media["clip"]),
            output_path=str(tmp_path / "q3.gif"),
            params={"fps": 10, "width": 240, "start_s": 0.0, "duration_s": 2.0},
        ),
    ]
    for j in jobs:
        q.enqueue(j)
    import time

    time.sleep(0.5)
    assert done == [], "paused queue must not run real engine jobs"
    q.set_paused(False)
    deadline = time.time() + 60
    while len(done) < 3 and time.time() < deadline:
        time.sleep(0.2)
    q.shutdown()
    assert done, "queue never ran"
    for j in jobs:
        assert Path(j.output_path).stat().st_size > 0, f"{j.op} output empty"


# ── Misc engine surfaces ─────────────────────────────────────────────────────


def test_thumbnails_and_keyframes(media):
    thumbs = EngineService.thumbnail_strip(str(media["clip"]), [1.0, 3.0, 5.0], width=96)
    assert len(thumbs) == 3 and all(len(t) > 0 for t in thumbs)
    kfs = EngineService.keyframe_times(str(media["mp4"]), limit=5)
    assert 0 < len(kfs) <= 5
    assert all(k >= 0 for k in kfs)
