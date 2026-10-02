"""Golden-command suite for the expert Terminal's ffmpeg → engine translator.

Every test pins a real-world command line to the exact op + params the job
dispatcher consumes — regressions here would silently mistranslate user
commands, so refusals assert on the MESSAGE (loud, never silent).
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


def test_plain_transcode_defaults(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} {tmp_path / 'out.mp4'}")
    assert plan.op == "convert"
    assert plan.params == {}  # engine defaults everywhere — nothing guessed


def test_tokenizer_keeps_backslash_paths_and_quotes():
    cmd = r'ffmpeg -i "C:\media\my video.mp4" -y C:\out\final.mp4'
    toks = tokenize(cmd)
    assert toks[0] == "ffmpeg"
    assert toks[2] == r"C:\media\my video.mp4"
    assert toks[-1] == r"C:\out\final.mp4"


def test_trim_stream_copy(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -ss 00:00:10 -t 5 -i {src} -c copy {tmp_path / 'clip.mkv'}")
    assert plan.op == "cut"
    assert plan.params == {
        "start_seconds": 10.0,
        "end_seconds": 15.0,
        "stream_copy": True,
    }
    assert any("stream copy" in n for n in plan.notes)


def test_trim_reencode_with_crf_flag(media, tmp_path):
    src, _ = media
    plan = parse_command(
        f"ffmpeg -i {src} -ss 10 -to 20 -c:v libx264 -crf 18 {tmp_path / 'out.mp4'}"
    )
    assert plan.op == "cut"
    assert plan.params["start_seconds"] == 10.0
    assert plan.params["end_seconds"] == 20.0
    assert plan.params["stream_copy"] is False
    assert plan.params["crf"] == 18, "a -crf that forces re-encode is carried, not dropped"


def test_trim_without_end_uses_probed_duration(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 30 {tmp_path / 'tail.mkv'}", duration_s=120.0)
    assert plan.params["end_seconds"] == 120.0


def test_trim_without_end_or_duration_refuses(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="duration"):
        parse_command(f"ffmpeg -i {src} -ss 30 {tmp_path / 'tail.mkv'}")


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


def test_join_two_inputs(media, tmp_path):
    _, second = media
    first = media[0]
    plan = parse_command(f"ffmpeg -i {first} -i {second} {tmp_path / 'joined.mp4'}")
    assert plan.op == "concat"
    assert plan.params["paths"] == [first, second]
    assert plan.params["container"] == "mp4"


def test_scale_and_codec_mapping(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -s 1280x720 -c:v libx264 -crf 23 {tmp_path / 'o.mp4'}")
    assert plan.op == "convert"
    assert plan.params["scale_width"] == 1280
    assert plan.params["scale_height"] == 720
    assert plan.params["video_codec"] == "libx264"
    assert plan.params["crf"] == 23


def test_vf_subset_maps_to_convert(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -vf "scale=1280:720,fps=30" {tmp_path / "o.mp4"}')
    assert plan.params["scale_width"] == 1280
    assert plan.params["fps"] == 30


def test_vf_atempo_refused_audio_filter_in_video_chain(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="-af atempo"):
        parse_command(f'ffmpeg -i {src} -vf "atempo=1.5,atempo=1.2" {tmp_path / "o.mp4"}')


def test_af_atempo_chain_multiplies(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -af "atempo=1.5,atempo=1.2" {tmp_path / "o.mp4"}')
    assert plan.params["speed"] == pytest.approx(1.8)


def test_af_loudnorm_sets_lufs(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -vn -af "loudnorm=I=-18:TP=-1.5" {tmp_path / "o.wav"}')
    assert plan.op == "extract_audio"
    assert plan.params["target_lufs"] == -18.0


def test_lossless_copy_to_mkv_is_remux(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c copy {tmp_path / 'o.mkv'}")
    assert plan.op == "remux"


def test_lossless_copy_to_mp4_refuses_with_suggestion(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match=r"\.mkv"):
        parse_command(f"ffmpeg -i {src} -c copy {tmp_path / 'o.mp4'}")


def test_gif_with_range_and_fps(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 2 -t 3 -r 12 {tmp_path / 'loop.gif'}")
    assert plan.op == "create_gif"
    assert plan.params == {
        "fps": 12,
        "width": 480,
        "start_s": 2.0,
        "duration_s": 3.0,
    }


def test_subtitle_extension(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} {tmp_path / 'subs.srt'}")
    assert plan.op == "extract_subtitles"
    assert plan.params["format_name"] == "srt"


def test_unknown_flag_refused_loudly(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="unsupported flag"):
        parse_command(f"ffmpeg -i {src} -quantizer x {tmp_path / 'o.mp4'}")


def test_filter_complex_refused_with_guidance(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="vf/-af"):
        parse_command(f'ffmpeg -i {src} -filter_complex "scale=1280:-2" {tmp_path / "o.mp4"}')


def test_hflip_refused_points_to_filters_screen(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="Filters screen"):
        parse_command(f"ffmpeg -i {src} -vf hflip {tmp_path / 'o.mp4'}")


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


def test_help_text_mentions_refusals():
    text = help_text()
    assert "-filter_complex" in text
    assert "PyAV" in text


def test_vn_to_video_output_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="name an audio output"):
        parse_command(f"ffmpeg -i {src} -vn {tmp_path / 'o.mp4'}")


def test_duplicate_flags_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="duplicate -ss"):
        parse_command(f"ffmpeg -i {src} -ss 10 -ss 20 -t 5 {tmp_path / 'o.mp4'}")
    with pytest.raises(CommandError, match="duplicate -crf"):
        parse_command(f"ffmpeg -i {src} -crf 20 -crf 23 {tmp_path / 'o.mp4'}")


def test_concat_with_encode_flags_refused(media, tmp_path):
    src, second = media
    with pytest.raises(CommandError, match="would be ignored"):
        parse_command(f"ffmpeg -i {src} -i {second} -crf 20 {tmp_path / 'o.mp4'}")


def test_c_v_copy_remuxes(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -c:v copy {tmp_path / 'o.mkv'}")
    assert plan.op == "remux"


def test_volume_linear_and_db(media, tmp_path):
    src, _ = media
    plan = parse_command(f'ffmpeg -i {src} -af "volume=1.5" {tmp_path / "o.mp4"}')
    assert plan.params["volume_pct"] == 150
    plan = parse_command(f'ffmpeg -i {src} -af "volume=6dB" {tmp_path / "o.mp4"}')
    assert plan.params["volume_pct"] == pytest.approx(200, abs=1)


def test_fps_rounds_not_truncates(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -r 29.97 {tmp_path / 'o.mp4'}")
    assert plan.params["fps"] == 30


def test_transpose_zero_is_ccw(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -vf transpose=0 {tmp_path / 'o.mp4'}")
    assert plan.params["rotation"] == 270
    plan = parse_command(f"ffmpeg -i {src} -vf transpose=1 {tmp_path / 'o.mp4'}")
    assert plan.params["rotation"] == 90
    plan = parse_command(f"ffmpeg -i {src} -vf transpose=clock {tmp_path / 'o.mp4'}")
    assert plan.params["rotation"] == 90


def test_gif_end_zero_is_valid(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 0 -to 0 {tmp_path / 'o.gif'}", duration_s=10.0)
    assert plan.op == "create_gif"
    assert plan.params["duration_s"] == pytest.approx(0.0)


def test_gif_open_range_honours_probed_duration(media, tmp_path):
    src, _ = media
    plan = parse_command(f"ffmpeg -i {src} -ss 2 {tmp_path / 'o.gif'}", duration_s=10.0)
    assert plan.params["duration_s"] == pytest.approx(8.0)


def test_extraction_with_time_range_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="cut first"):
        parse_command(f"ffmpeg -i {src} -ss 5 -t 5 {tmp_path / 'o.mp3'}")
    with pytest.raises(CommandError, match="cut first"):
        parse_command(f"ffmpeg -i {src} -ss 5 -t 5 {tmp_path / 'o.srt'}")


def test_extraction_with_shaping_refused(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match="shaping"):
        parse_command(f"ffmpeg -i {src} -vf scale=640:480 {tmp_path / 'o.mp3'}")


def test_input_equals_output_refused(media, tmp_path):
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


def test_sslide_names_dossier(media, tmp_path):
    src, _ = media
    with pytest.raises(CommandError, match=r"[Dd]ossier"):
        parse_command(f"ffmpeg -i {src} -sslide 2 {tmp_path / 'o.mp4'}")
