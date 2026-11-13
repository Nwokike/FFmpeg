"""Golden-command suite for the expert Terminal's ffmpeg → engine translator.

Command mode is a translator, not an emulation: every test pins a real-world
command line to the exact op + params the job dispatcher consumes, and every
refusal asserts on the MESSAGE (loud, never silent). The filter and option
cases assert the *measured* contract — a filter passes through as a node, an
option only lands where this build says it exists.
"""

from __future__ import annotations

import pytest

from services.command_parser import CommandError, help_text, parse_command, tokenize


@pytest.fixture
def media(tmp_path):
    p = tmp_path / "in.mp4"
    p.write_bytes(b"\x00")
    a = tmp_path / "second.mp4"
    a.write_bytes(b"\x00")
    return str(p), str(a)


# ── tokenizer ───────────────────────────────────────────────────────────


def test_tokenizer_keeps_backslash_paths_and_quotes():
    cmd = r'ffmpeg -i "C:\media\my video.mp4" -y C:\out\final.mp4'
    toks = tokenize(cmd)
    assert toks[0] == "ffmpeg"
    assert toks[2] == r"C:\media\my video.mp4"
    assert toks[-1] == r"C:\out\final.mp4"


def test_tokenizer_keeps_filter_arguments_together():
    # A quoted -vf chain is ONE token; splitting it would shred the graph.
    toks = tokenize('ffmpeg -i in.mp4 -vf "hqdn3d=4:3:6:4.5,unsharp=5:5:1.0" out.mp4')
    assert toks[4] == "hqdn3d=4:3:6:4.5,unsharp=5:5:1.0"


# ── routing by output extension ─────────────────────────────────────────


def test_plain_transcode_defaults(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} {tmp_path / 'out.mp4'}")
    assert plan.op == "convert"
    # Nothing guessed: no codec/crf/scale keys the user never typed.
    assert plan.params == {}


def test_extract_audio_via_vn(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -vn -b:a 128k -ar 44100 -ac 2 {tmp_path / 'o.m4a'}")
    assert plan.op == "extract_audio"
    assert plan.params == {
        "format_name": "m4a",
        "bitrate_kbps": 128,
        "sample_rate": 44100,
        "channels": 2,
    }


def test_extract_audio_via_audio_extension(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} {tmp_path / 'song.flac'}")
    assert plan.op == "extract_audio"
    assert plan.params["format_name"] == "flac"


def test_vn_to_video_output_refused(media, tmp_path):
    """-vn with a video target leaves nothing to write — refuse, don't guess."""
    src, _ = media
    with pytest.raises(CommandError, match="leaves nothing to write"):
        parse_command(f"ffmpeg -i {src} -vn {tmp_path / 'o.mp4'}")


def test_subtitle_extension(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} {tmp_path / 'subs.srt'}")
    assert plan.op == "extract_subtitles"
    assert plan.params["format_name"] == "srt"


def test_gif_with_range_and_fps(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 2 -t 3 -r 12 {tmp_path / 'loop.gif'}")
    assert plan.op == "create_gif"
    assert plan.params == {"fps": 12, "width": 480, "start_s": 2.0, "duration_s": 3.0}


def test_gif_reversed_range_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="empty GIF range"):
        parse_command(f"ffmpeg -i {src} -ss 5 -to 3 {tmp_path / 'o.gif'}")


def test_gif_open_range_honours_probed_duration(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 2 {tmp_path / 'o.gif'}", duration_s=10.0)
    assert plan.params["duration_s"] == pytest.approx(8.0)


# ── cut / remux ─────────────────────────────────────────────────────────


def test_trim_stream_copy(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -ss 00:00:10 -t 5 -i {src} -c copy {tmp_path / 'clip.mkv'}")
    assert plan.op == "cut"
    assert plan.params == {"start_seconds": 10.0, "end_seconds": 15.0, "stream_copy": True}
    assert any("stream copy" in n for n in plan.notes)


def test_trim_reencode_with_crf_flag(media, tmp_path):
    src, _ = media
    plan = parse_command(
        f"ffmpeg -i {src} -ss 10 -to 20 -c:v libx264 -crf 18 {tmp_path / 'out.mp4'}"
    )
    assert plan.op == "cut"
    assert plan.params["stream_copy"] is False
    assert plan.params["encoder_options"] == {"crf": "18"}


def test_trim_without_end_uses_probed_duration(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 30 {tmp_path / 'tail.mkv'}", duration_s=120.0)
    assert plan.params["end_seconds"] == 120.0


def test_trim_without_end_or_duration_refuses(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="duration"):
        parse_command(f"ffmpeg -i {src} -ss 30 {tmp_path / 'tail.mkv'}")


def test_lossless_copy_is_remux(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c copy {tmp_path / 'o.mkv'}")
    assert plan.op == "remux"


def test_c_v_copy_remuxes(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c:v copy {tmp_path / 'o.mkv'}")
    assert plan.op == "remux"
    assert not any("re-encoded" in n for n in plan.notes)


def test_copy_v_inside_a_trim_stream_copies(media, tmp_path):
    """-c:v copy with a time range is a lossless (keyframe-snapped) cut."""
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 2 -t 2 -c:v copy {tmp_path / 'o.mp4'}")
    assert plan.op == "cut"
    assert plan.params["stream_copy"] is True
    assert any("stream copy" in n for n in plan.notes)


# ── filters are real passthroughs (no tables) ───────────────────────────


def test_vf_chain_becomes_nodes_with_ffmpeg_argument_syntax(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -vf "unsharp=5:5:1.0,scale=160:90" {tmp_path / "o.mp4"}')
    assert plan.video_filter == [
        ["unsharp", "5:5:1.0"],
        ["scale", "160:90"],
    ]


def test_vf_filter_the_build_has_passes_through(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -vf "drawbox=x=0:y=0:w=10:h=10" {tmp_path / "o.mp4"}')
    assert plan.video_filter == [["drawbox", "x=0:y=0:w=10:h=10"]]


def test_vf_filter_this_build_lacks_refuses_at_plan_time(media, tmp_path):
    """A missing filter must fail the plan (naming the cause), not the encode."""
    src, _ = media
    with pytest.raises(CommandError, match="is not in this build"):
        parse_command(f'ffmpeg -i {src} -vf "definitely_not_a_filter=1" {tmp_path / "o.mp4"}')


def test_af_chain_becomes_nodes(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -af "volume=1.5,atempo=1.2" {tmp_path / "o.mp4"}')
    assert plan.audio_filter == [["volume", "1.5"], ["atempo", "1.2"]]


def test_filter_complex_refused_with_guidance(media, tmp_path):
    """Non-linear graphs need the Filters screen — command mode is linear."""
    src, _ = media
    with pytest.raises(CommandError, match="vf/-af"):
        parse_command(f'ffmpeg -i {src} -filter_complex "scale=1280:-2" {tmp_path / "o.mp4"}')


def test_vf_on_an_extraction_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="extraction has no video stream"):
        parse_command(f"ffmpeg -i {src} -vf scale=640:480 {tmp_path / 'o.mp3'}")


def test_af_on_an_extraction_rides_the_filter_chain(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -af "volume=0.5" {tmp_path / "o.wav"}')
    assert plan.op == "extract_audio"
    assert plan.params["audio_filter"] == [["volume", "0.5"]]


# ── codecs, options and streams ─────────────────────────────────────────


def test_scale_and_codec_are_their_own_params(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -s 1280x720 -c:v libx264 {tmp_path / 'o.mp4'}")
    assert plan.op == "convert"
    assert plan.params["scale_width"] == 1280
    assert plan.params["scale_height"] == 720
    assert plan.params["video_codec"] == "libx264"


def test_pix_fmt_is_validated_against_the_named_encoder(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c:v libx264 -pix_fmt yuv420p {tmp_path / 'o.mp4'}")
    assert plan.params["pix_fmt"] == "yuv420p"
    # gif only encodes rgb8 — the wheel's own format list says so.
    with pytest.raises(CommandError, match="cannot encode"):
        parse_command(f"ffmpeg -i {src} -c:v gif -pix_fmt yuv420p {tmp_path / 'o.gif'}")


def test_unknown_encoder_refused_naming_the_wheel(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="cannot encode"):
        parse_command(f"ffmpeg -i {src} -c:v definitely_not_a_codec {tmp_path / 'o.mp4'}")


def test_encoder_knobs_become_encoder_options(media, tmp_path):
    src, _ = media
    plan = parse_command(
        f"ffmpeg -i {src} -c:v libx264 -tune film -profile:v high -level 4.1 {tmp_path / 'o.mp4'}"
    )
    assert plan.params["encoder_options"] == {
        "tune": "film",
        "profile": "high",
        "level": "4.1",
    }


def test_bitrate_flags_take_their_real_slots(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c:v libx264 -b:v 1M {tmp_path / 'o.mp4'}")
    assert plan.params["encoder_options"]["b"] == "1000000"
    plan = parse_command(f"ffmpeg -i {src} -vn -b:a 128k {tmp_path / 'o.mp3'}")
    assert plan.params["bitrate_kbps"] == 128


def test_unknown_flag_refused_with_what_this_encoder_accepts(media, tmp_path):
    """av accepts unknown muxer options silently — so we refuse instead of
    pretending a typo became a setting."""
    src, _ = media
    with pytest.raises(CommandError, match="not an option of"):
        parse_command(f"ffmpeg -i {src} -quantizer x {tmp_path / 'o.mp4'}")


def test_movflags_is_the_one_muxer_flag(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -movflags +faststart {tmp_path / 'o.mp4'}")
    assert plan.params["container_options"] == {"movflags": "+faststart"}


def test_map_selectors_use_the_absolute_stream_index(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -map 0:v:1 -map 0:a:0 {tmp_path / 'o.mp4'}")
    assert plan.params["video_stream"] == 1
    assert plan.params["audio_stream"] == 0


def test_an_drops_the_audio_stream(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -an {tmp_path / 'o.mp4'}")
    assert plan.op == "convert"
    assert "audio_codec" not in plan.params


def test_vn_extraction_uses_the_named_format(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -vn -c:a libmp3lame {tmp_path / 'o.mp3'}")
    assert plan.op == "extract_audio"
    assert plan.params["format_name"] == "mp3"


# ── joins ───────────────────────────────────────────────────────────────


def test_join_two_inputs(media, tmp_path):
    src, second = media
    plan = parse_command(f"ffmpeg -i {src} -i {second} {tmp_path / 'joined.mp4'}")
    assert plan.op == "concat"
    assert plan.params["paths"] == [src, second]
    assert plan.params["container"] == "mp4"


def test_concat_with_encode_flags_refused(media, tmp_path):
    src, second = media
    with pytest.raises(CommandError, match="would be ignored"):
        parse_command(f"ffmpeg -i {src} -i {second} -crf 20 {tmp_path / 'o.mp4'}")


def test_join_with_stream_flags_refused(media, tmp_path):
    src, second = media
    with pytest.raises(CommandError, match="-vn"):
        parse_command(f"ffmpeg -i {src} -i {second} -vn {tmp_path / 'o.mp4'}")


# ── refusals that must stay loud ────────────────────────────────────────


def test_missing_input_refused(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        parse_command(f"ffmpeg -i {tmp_path / 'ghost.mp4'} {tmp_path / 'o.mp4'}")


def test_no_output_refused(media):
    src, _ = media
    with pytest.raises(CommandError, match="no output"):
        parse_command(f"ffmpeg -i {src}")


def test_bare_invocation_lists_help():
    with pytest.raises(CommandError):
        parse_command("ffmpeg")


def test_help_flag_answers_with_the_builds_surface():
    with pytest.raises(CommandError, match="real FFmpeg syntax"):
        parse_command("ffmpeg -h")


def test_help_text_is_generated_from_this_build():
    text = help_text()
    assert "this wheel:" in text
    assert "encoders" in text and "filters" in text
    assert "movflags" in text


def test_duplicate_single_valued_flags_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="duplicate -ss"):
        parse_command(f"ffmpeg -i {src} -ss 10 -ss 20 -t 5 {tmp_path / 'o.mp4'}")
    with pytest.raises(CommandError, match="duplicate -crf"):
        parse_command(f"ffmpeg -i {src} -crf 20 -crf 23 {tmp_path / 'o.mp4'}")


def test_input_equals_output_refused(media):
    src, _ = media
    with pytest.raises(CommandError, match="same file"):
        parse_command(f"ffmpeg -i {src} {src}")


def test_empty_quotes_refused():
    with pytest.raises(CommandError, match="empty quoted"):
        parse_command('ffmpeg -i "" out.mp4', check_exist=False)


def test_bad_timestamps_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="timestamp"):
        parse_command(f"ffmpeg -i {src} -ss nan -t 5 {tmp_path / 'o.mp4'}")
    with pytest.raises(CommandError, match="timestamp"):
        parse_command(f"ffmpeg -i {src} -ss -5 -t 5 {tmp_path / 'o.mp4'}")


def test_extraction_with_time_range_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="cut first"):
        parse_command(f"ffmpeg -i {src} -ss 5 -t 5 {tmp_path / 'o.mp3'}")
    with pytest.raises(CommandError, match="cut first"):
        parse_command(f"ffmpeg -i {src} -ss 5 -t 5 {tmp_path / 'o.srt'}")
