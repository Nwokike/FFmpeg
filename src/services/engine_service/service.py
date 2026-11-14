"""The EngineService namespace: every operation is a staticmethod here."""

from __future__ import annotations

from services.engine_service.builders import (  # noqa: F401 — engine surface
    ENGINE_PAUSE_EVENT,
    _discard_cancelled,
    _pause_hook,
    _snap_start_to_keyframe,
    probe_media,
    run_copy_job,
    run_encode_job,
    set_pause_event,
)
from services.engine_service.capability import (  # noqa: F401 — engine surface
    EngineCapabilityError,
    _encoder_open_kwargs,
    _encoder_pix_fmt,
    _friendly_codec,
    available_audio_encoders,
    available_video_encoders,
    check_pair,
    check_params,
)
from services.engine_service.graphs import (  # noqa: F401 — engine surface
    _FILTER_DESCRIPTIONS,
    _FILTERS_AVAIL,
    _FINE_VIDEO_TB,
    _WM_POSITIONS,
    _atempo_factors,
    _build_audio_filter_graph,
    _build_video_filter_graph,
    _drain_graph,
    _mjpeg_bytes,
    _pull_ready,
    _push_pull,
    _rebase_pts,
    available_filters,
    filter_description,
)
from services.engine_service.logs import (  # noqa: F401 — engine surface
    _INPUT_OPTIONS,
    _INPUT_TIMEOUT,
    _av_rational,
    _codec_supports_mode,
    _decode_packet,
    _is_attached_picture,
    _native_log_scope,
    _with_native_logs,
    logger,
)
from services.engine_service.ops_audio import (
    _measure_loudnorm,
    extract_audio,
)
from services.engine_service.ops_container import (
    _acrossfade_window,
    _concat_copyable,
    _concat_crossfade,
    _concat_reencode,
    _concat_stream_copy,
    _crossfade_gate,
    _xfade_window,
    concat,
    remux,
)
from services.engine_service.ops_convert import (
    _cut_reencode,
    _cut_stream_copy,
    compress_to_target,
    convert,
    cut_trim,
)
from services.engine_service.ops_extract import (
    create_gif,
    extract_frames,
    extract_subtitles,
    keyframe_times,
    thumbnail_strip,
)
from services.engine_service.ops_network import (
    _HLS_SEGMENT_RETRIES,
    _HLS_TIMEOUT,
    _check_hls_cap,
    _download_hls_segments,
    _hls_cap_bytes,
    _hls_download_segment,
    _hls_download_segment_once,
    _hls_fetch_text,
    _open_https_via_httpx,
    _open_network_input,
    _parse_hls_playlist,
    _record_from,
    estimate_hls_segments,
    record,
)
from services.engine_service.options import (  # noqa: F401 — engine surface
    _NUMERIC_OPTION_TYPES,
    _NUMERIC_SUFFIXES,
    _TLS_OK,
    _exact_rate,
    _hardware_decode,
    _optional_encoder_knobs,
    _parse_option_number,
    _pick_video_encoder,
    _supported_encoder_options,
    _tls_available,
    _value_fits,
    _wire_option_value,
)
from services.engine_service.resolve import (  # noqa: F401 — engine surface
    _derive_audio_codec_for_format,
    _resolve_audio_codec,
    _resolve_codec,
    _resolve_or_raw,
    _resolve_video_codec,
    audio_codec_for_format,
    friendly_job_error,
)
from services.engine_service.safety import (  # noqa: F401 — engine surface
    _close_container,
    _disposition_flag_names,
    _MuxClamp,
    _safe_seek,
    _unknown_codec_error_type,
)
from services.engine_service.sizing import (  # noqa: F401 — engine surface
    _chain_declared_size,
    _crop_dims,
    _graph_from_nodes,
    _select_stream,
)
from services.engine_service.subtitles import (  # noqa: F401 — engine surface
    _ASS_HEADER,
    SubCue,
    _fmt_ass_time,
    _fmt_srt_time,
    _fmt_vtt_time,
    _write_ass,
    _write_srt,
    _write_vtt,
)


class EngineService:
    """Core media transformation engine powered by PyAV."""

    _acrossfade_window = staticmethod(_acrossfade_window)
    _check_hls_cap = staticmethod(_check_hls_cap)
    _concat_copyable = staticmethod(_concat_copyable)
    _concat_crossfade = staticmethod(_concat_crossfade)
    _concat_reencode = staticmethod(_concat_reencode)
    _concat_stream_copy = staticmethod(_concat_stream_copy)
    _crossfade_gate = staticmethod(_crossfade_gate)
    _cut_reencode = staticmethod(_cut_reencode)
    _cut_stream_copy = staticmethod(_cut_stream_copy)
    _download_hls_segments = staticmethod(_download_hls_segments)
    _hls_cap_bytes = staticmethod(_hls_cap_bytes)
    _hls_download_segment = staticmethod(_hls_download_segment)
    _hls_download_segment_once = staticmethod(_hls_download_segment_once)
    _hls_fetch_text = staticmethod(_hls_fetch_text)
    _measure_loudnorm = staticmethod(_measure_loudnorm)
    _open_https_via_httpx = staticmethod(_open_https_via_httpx)
    _open_network_input = staticmethod(_open_network_input)
    _parse_hls_playlist = staticmethod(_parse_hls_playlist)
    _record_from = staticmethod(_record_from)
    _HLS_TIMEOUT = _HLS_TIMEOUT
    _HLS_SEGMENT_RETRIES = _HLS_SEGMENT_RETRIES
    _snap_start_to_keyframe = staticmethod(_snap_start_to_keyframe)
    _xfade_window = staticmethod(_xfade_window)
    compress_to_target = staticmethod(compress_to_target)
    concat = staticmethod(concat)
    convert = staticmethod(convert)
    create_gif = staticmethod(create_gif)
    cut_trim = staticmethod(cut_trim)
    estimate_hls_segments = staticmethod(estimate_hls_segments)
    extract_audio = staticmethod(extract_audio)
    extract_frames = staticmethod(extract_frames)
    extract_subtitles = staticmethod(extract_subtitles)
    keyframe_times = staticmethod(keyframe_times)
    probe = staticmethod(probe_media)
    record = staticmethod(record)
    remux = staticmethod(remux)
    thumbnail_strip = staticmethod(thumbnail_strip)
