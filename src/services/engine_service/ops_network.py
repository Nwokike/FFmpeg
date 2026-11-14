"""HLS parsing/download, https fallback, live recording."""

from __future__ import annotations

import contextlib
import math
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from urllib.parse import urljoin

import av
import httpx

from core.storage_paths import get_temp_dir
from services.engine_service.builders import _pause_hook, run_copy_job
from services.engine_service.logs import _INPUT_TIMEOUT, _is_attached_picture, logger
from services.engine_service.options import _tls_available
from services.engine_service.safety import _close_container, _MuxClamp
from services.job_model import CHAPTERS_SKIP, InputSpec, Job, OutputSpec

_HLS_TIMEOUT = (10.0, 30.0, 30.0, 10.0)

_HLS_SEGMENT_RETRIES = 3


def _parse_hls_playlist(text: str, base: str) -> tuple[list[str], bool, str | None]:
    """Split an HLS playlist into segment URLs.

    Returns ``(segments, is_master, key_error)``.  A master variant
    playlist (``#EXT-X-STREAM-INF``) resolves to the highest-BANDWIDTH
    media playlist URL as the single "segment" for the caller to recurse
    into; ``key_error`` names the cause when ``#EXT-X-KEY`` (encrypted
    segments) is present, which this offline-concat path cannot decrypt.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    key_error = None
    for ln in lines:
        if ln.startswith("#EXT-X-KEY"):
            key_error = f"encrypted segments are not supported ({ln[:80]})"
            break
    is_master = any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines)
    variants: list[tuple[int, str]] = []
    segs: list[str] = []
    pending_bw = 0
    for ln in lines:
        if ln.startswith("#EXT-X-STREAM-INF"):
            bw = 0
            for part in ln.split(":", 1)[1].split(","):
                if part.strip().upper().startswith("BANDWIDTH="):
                    try:
                        bw = int(part.split("=", 1)[1])
                    except ValueError:
                        bw = 0
            pending_bw = bw
            continue
        if not ln or ln.startswith("#"):
            continue
        url = urljoin(base, ln)
        if is_master:
            variants.append((pending_bw, url))
            pending_bw = 0
        else:
            segs.append(url)
    if variants:
        variants.sort(key=lambda v: v[0], reverse=True)
        return [variants[0][1]], True, key_error
    return segs, False, key_error


def _hls_fetch_text(client, url: str) -> str:
    """GET a playlist URL, raising a loud error on failure."""
    resp = client.get(url, timeout=_HLS_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _hls_download_segment(client, seg: str, chunk_size: int, on_cancel) -> bytes:
    """Download one media segment, rejecting HTML/text error pages.

    Transient network errors retry with backoff (bounded); error pages
    and HTTP statuses fail immediately — retrying a 403 is pointless.
    """
    import time as _time

    last_err: Exception | None = None
    for attempt in range(_HLS_SEGMENT_RETRIES):
        try:
            return _hls_download_segment_once(client, seg, chunk_size, on_cancel)
        except ValueError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_err = exc
            logger.warning(
                "Segment retry %d/%d for %s: %s",
                attempt + 1,
                _HLS_SEGMENT_RETRIES,
                seg[:80],
                exc,
            )
            on_cancel()
            _time.sleep(min(2.0**attempt, 4.0))
    raise ValueError(f"Segment failed after retries ({seg[:80]}…): {last_err}")


def _hls_download_segment_once(client, seg: str, chunk_size: int, on_cancel) -> bytes:
    """Single attempt of a segment download (see _hls_download_segment)."""
    parts: list[bytes] = []
    with client.stream("GET", seg, timeout=_HLS_TIMEOUT) as resp:
        resp.raise_for_status()
        first = True
        for chunk in resp.iter_bytes(chunk_size=chunk_size):
            on_cancel()
            if not chunk:
                continue
            if first:
                first = False
                # A segment that answers HTML/text is an error page, not
                # media — fail loud with the cause instead of a blind EOF
                # at av.open time.
                head = chunk[:512].lstrip().lower()
                if (
                    head.startswith((b"<!doctype", b"<html", b"<head", b"{", b"<"))
                    and b"#extm3u" not in chunk[:512].lower()
                ):
                    raise ValueError(
                        f"Segment is not media ({seg[:80]}…) — the server returned an error page"
                    )
            parts.append(chunk)
    return b"".join(parts)


def _hls_cap_bytes(max_hls_download_mb: float | None) -> int | None:
    """Cap in bytes, or None when the caller overrode it for this download."""
    if max_hls_download_mb is None:
        return None
    try:
        cap = float(max_hls_download_mb)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(cap) or cap <= 0:
        return None
    return int(cap * 1024 * 1024)


def _check_hls_cap(total: int, cap: int | None, url: str) -> None:
    if cap is not None and total > cap:
        raise ValueError(
            f"Stream is ~{total // (1024 * 1024)} MB but the download cap is "
            f"{cap // (1024 * 1024)} MB — raise Settings → max HLS download, "
            "or tick 'Download anyway' on this stream to override once"
        )


def estimate_hls_segments(client, url: str) -> tuple[list[str], int | None]:
    """Resolve the media playlist and HEAD each segment for its size.

    Returns (segment URLs, total bytes or None when any server omits
    Content-Length). Never downloads media — the streams screen calls this
    for the preflight line before the user commits.
    """
    playlist = _hls_fetch_text(client, url)
    base = urljoin(url, ".")
    segments, is_master, key_error = _parse_hls_playlist(playlist, base)
    if key_error is not None:
        raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
    if is_master:
        media_url = segments[0]
        playlist = _hls_fetch_text(client, media_url)
        base = urljoin(media_url, ".")
        segments, _, key_error = _parse_hls_playlist(playlist, base)
        if key_error is not None:
            raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
    if not segments:
        raise ValueError("HLS playlist contained no media segments")
    total: int | None = 0
    for seg in segments:
        try:
            head = client.head(seg, timeout=_HLS_TIMEOUT)
            head.raise_for_status()
            length = head.headers.get("content-length")
            if length is None:
                return segments, None
            assert isinstance(total, int)
            total += int(length)
        except Exception:
            return segments, None
    return segments, total


def _download_hls_segments(
    client,
    url: str,
    on_cancel,
    max_hls_download_mb: float | None = None,
) -> list[tuple[str, bytes]]:
    """Resolve master→media playlist and download every segment.

    Raises a loud, specific ValueError for encrypted streams, empty
    playlists, error-page segments, payloads too small to be media, or
    totals past the download cap (servers that lie about Content-Length
    are caught by the running total mid-download).
    """
    cap = _hls_cap_bytes(max_hls_download_mb)
    playlist = _hls_fetch_text(client, url)
    base = urljoin(url, ".")
    segments, is_master, key_error = _parse_hls_playlist(playlist, base)
    if key_error is not None:
        raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
    if is_master:
        # The master holds variant URLs, not media bytes — writing those
        # produced the EOF-on-.dat failure. Recurse into the top variant.
        media_url = segments[0]
        logger.info("HLS master playlist — using %s", media_url)
        playlist = _hls_fetch_text(client, media_url)
        base = urljoin(media_url, ".")
        segments, _, key_error = _parse_hls_playlist(playlist, base)
        if key_error is not None:
            raise ValueError(f"This stream is encrypted and can't be recorded offline: {key_error}")
    if not segments:
        raise ValueError("HLS playlist contained no media segments")
    out: list[tuple[str, bytes]] = []
    running = 0
    for seg in segments:
        on_cancel()
        data = _hls_download_segment(client, seg, 256 * 1024, on_cancel)
        running += len(data)
        _check_hls_cap(running, cap, seg)
        out.append((seg, data))
    total = sum(len(b) for _, b in out)
    if total < 32 * 1024:
        raise ValueError(
            f"Stream produced too little data to be media ({total} bytes) — "
            "check the URL and your network"
        )
    return out


def _open_https_via_httpx(
    url: str,
    cancel_event: Event | None = None,
    max_hls_download_mb: float | None = None,
):
    """Download an HTTPS (optionally HLS) stream into a local temp file.

    The fallback for a wheel built WITHOUT a TLS protocol handler (the stock
    flet-libffmpeg is bare LGPL): ``av.open`` cannot open HTTPS there, so the
    bytes are fetched with ``httpx`` on the app's own network stack. When the
    wheel's TLS probe says https works, :meth:`_open_network_input` never
    calls this — the native path is always preferred.
    HLS playlists are expanded segment-by-segment so the resulting file is a
    plain container PyAV can demux.

    Plain files stream in ONE GET (the old code sniffed 512B, discarded the
    response, and GET again from byte 0). HLS totals are capped at
    ``max_hls_download_mb`` (None = the caller overrode the cap for this
    download).

    Returns ``(container, cleanup_path)`` — PyAV containers are Cython
    objects without a ``__dict__``, so the caller cannot be handed the
    backing path as an attribute.
    """
    from uuid import uuid4

    temp_path = get_temp_dir() / f"https_dl_{uuid4().hex}.dat"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    total_written = 0
    chunk_size = 256 * 1024
    cap = _hls_cap_bytes(max_hls_download_mb)

    def _raise_if_cancelled() -> None:
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("Stream download cancelled")

    try:
        with httpx.Client(follow_redirects=True) as client:
            with client.stream("GET", url, timeout=_HLS_TIMEOUT) as first:
                first.raise_for_status()
                head = next(first.iter_bytes(chunk_size=512), b"")
                is_hls = ".m3u8" in url.lower() or head.lstrip().startswith(b"#EXTM3U")
                probe_len = getattr(first, "headers", {}).get("content-length")
                if not is_hls and probe_len is not None:
                    _check_hls_cap(int(probe_len), cap, url)
                if is_hls:
                    # HLS goes segment-by-segment through the playlist
                    # helpers; this sniff response is discarded.
                    pass
                else:
                    # Plain file: consume THIS response inline (single GET).
                    # The 512B peek is prepended; servers that lie about
                    # Content-Length are caught by the running total.
                    with temp_path.open("wb") as fh:
                        if head:
                            fh.write(head)
                            total_written += len(head)
                        for chunk in first.iter_bytes(chunk_size=chunk_size):
                            _raise_if_cancelled()
                            if chunk:
                                total_written += len(chunk)
                                _check_hls_cap(total_written, cap, url)
                                fh.write(chunk)

            if is_hls:
                with temp_path.open("wb") as fh:
                    segments = _download_hls_segments(
                        client, url, _raise_if_cancelled, max_hls_download_mb
                    )
                    for _seg, seg_bytes in segments:
                        _raise_if_cancelled()
                        fh.write(seg_bytes)
                        total_written += len(seg_bytes)
                    logger.info("HLS playlist: %d segment(s) to download", len(segments))

        if total_written == 0:
            # Raising inside the try is what triggers the unlink below.
            raise ValueError(  # noqa: TRY301
                "Stream produced no data — check the URL and your network"
            )

        container = av.open(str(temp_path), "r", timeout=_INPUT_TIMEOUT)
        return container, str(temp_path)
    except BaseException:
        # Any failure (HTTP error, cancel, FFmpeg reject) must not leave a
        # partial multi-GB download sitting in the temp tier.
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
        raise


def _open_network_input(
    input_url: str,
    cancel_event: Event | None = None,
    max_hls_download_mb: float | None = None,
):
    """Return ``(container, cleanup_path)`` for a URL.

    Every protocol this wheel handles natively goes straight to ``av.open``
    (no cleanup path) — including HTTPS when the wheel's TLS probe says the
    handler is compiled in. Only a wheel WITHOUT TLS falls back to
    :meth:`_open_https_via_httpx` (the app's own network stack), and that
    download's temp file must be removed after the mux closes.
    ``max_hls_download_mb=None`` overrides the cap for this download.
    """
    if input_url.lower().startswith("https://") and not _tls_available():
        # Deferred through the class: tests patch EngineService._open_https_via_httpx.
        from services.engine_service.service import EngineService

        return EngineService._open_https_via_httpx(input_url, cancel_event, max_hls_download_mb)
    return av.open(input_url, "r", timeout=(10.0, 30.0)), None


def record(
    input_url: str,
    output_path: str,
    container_format: str | None = None,
    duration_s: float | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
    max_hls_download_mb: float | None = 2048,
) -> str:
    """Record an HTTP/HTTPS/HLS/DASH stream to a local file.

    Cancellation semantics differ from every other op: pressing Stop KEEPS
    the recording (returns normally instead of raising InterruptedError) —
    a stopped stream is a successful partial capture. ``duration_s`` acts
    as an automatic clean stop.

    ``max_hls_download_mb`` caps one HTTPS/HLS download (default 2 GB —
    the app setting; None = the caller overrode it for this download).

    HTTPS goes through ``av.open`` whenever this wheel has a TLS handler
    (the wrap build does; so does the desktop wheel). A wheel without one
    (the stock bare-LGPL flet-libffmpeg) falls back to fetching the stream
    with ``httpx`` and handing PyAV a local file — measured per wheel, never
    assumed from the platform.
    """
    if not input_url or "://" not in input_url:
        raise ValueError("That doesn't look like a stream URL (need scheme://…)")
    cleanup_path: str | None = None
    try:
        inp, cleanup_path = _open_network_input(input_url, cancel_event, max_hls_download_mb)
    except av.error.ProtocolNotFoundError as exc:
        raise ValueError(f"This build can't open that protocol: {exc}") from exc
    except av.error.TimeoutError as exc:
        raise ValueError("Connection timed out — check the URL and your network.") from exc
    except av.error.HTTPError as exc:
        raise ValueError(f"The server refused the stream: {exc}") from exc
    except httpx.TimeoutException as exc:
        raise ValueError("Connection timed out — check the URL and your network.") from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"The server refused the stream: HTTP {exc.response.status_code}") from exc
    except httpx.NetworkError as exc:
        raise ValueError(f"Network failed mid-download — retry: {exc}") from exc
    except httpx.TooManyRedirects as exc:
        raise ValueError(f"Too many redirects — check the URL: {exc}") from exc
    except httpx.DecodingError as exc:
        raise ValueError(f"Response couldn't be decoded: {exc}") from exc
    except httpx.HTTPError as exc:
        raise ValueError(f"Couldn't download that stream: {exc}") from exc
    except av.error.FFmpegError as exc:
        raise ValueError(f"Couldn't read that stream: {exc}") from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"Couldn't open URL: {exc}") from exc

    job = Job(
        output_path=output_path,
        inputs=[InputSpec(path=input_url, format=container_format)],
        input_containers=[inp],
        output=OutputSpec(container=container_format, metadata=False),
        chapters=CHAPTERS_SKIP,
        zero_base=True,
        bsf_codecs={
            "h264": "h264_mp4toannexb",
            "hevc": "hevc_mp4toannexb",
        },
        record_mode=True,
        duration_cap_s=duration_s,
        keep_data_streams=True,
        progress_label="Recording",
        complete_label="Recorded",
        cancel_message="Recording stopped",
    )
    try:
        return run_copy_job(job, on_progress=on_progress, cancel_event=cancel_event)
    finally:
        inp.close()
        # https inputs are backed by a temp file this method created; the
        # output may be large, so release it as soon as the muxer closes.
        if cleanup_path:
            with contextlib.suppress(OSError):
                Path(cleanup_path).unlink(missing_ok=True)


def _record_from(
    inp,
    output_path: str,
    container_format: str | None = None,
    duration_s: float | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    cancel_event: Event | None = None,
) -> str:
    """Demux-copy every stream of an open container into output_path.

    Test seam: tests drive this directly with a local file container
    instead of a network URL. Timestamps are shifted so the first packet
    of each stream lands at 0 (live inputs often start far up the
    timeline, which would leave a gaping offset in MP4).
    """
    out = av.open(output_path, "w", format=container_format)
    try:
        stream_map = {}
        for s in inp.streams:
            if s.type not in ("video", "audio", "subtitle", "data"):
                continue
            if _is_attached_picture(s):
                continue
            try:
                stream_map[s] = out.add_stream_from_template(s, opaque=True)
            except ValueError as exc:
                # MP4 cannot carry SRT/data or cover-art codecs; keep the
                # recordable A/V tracks instead of failing the whole URL.
                logger.info("Record stream %s skipped: %s", s.index, exc)
        if not stream_map:
            raise ValueError("No recordable streams found in that URL")

        # MP4-family sources carry h264/hevc in AVCC (length-prefixed) form;
        # the MPEG-TS muxer needs Annex-B. FFmpeg's CLI auto-inserts
        # h264_mp4toannexb for this combo — libavformat does NOT, so muxing
        # raw raises InvalidData. Apply the BSF manually per video stream.
        out_format = out.format.name
        bsfs: dict[int, tuple] = {}  # source stream index -> (ctx, out_stream)
        if out_format in ("mpegts", "hls"):
            for s, out_s in stream_map.items():
                if s.type != "video" or s.codec_context is None:
                    continue
                cname = s.codec_context.name or ""
                bsf_name = None
                if cname.startswith(("h264", "libx264")):
                    bsf_name = "h264_mp4toannexb"
                elif cname.startswith(("hevc", "libx265")):
                    bsf_name = "hevc_mp4toannexb"
                if bsf_name:
                    try:
                        bsfs[s.index] = (
                            av.BitStreamFilterContext(bsf_name, in_stream=s, out_stream=out_s),
                            out_s,
                        )
                    except Exception as exc:
                        logger.warning("BSF %s unavailable: %s", bsf_name, exc)

        start = time.monotonic()
        base_pts: dict[int, int] = {}
        base_dts: dict[int, int] = {}
        bytes_out = 0
        last_report = 0.0
        mux_clamp = _MuxClamp()

        def _emit(packet) -> None:
            """Zero-base the timestamps, run the BSF if any, mux result(s)."""
            # Real-world sources carry junk: zero-byte flush artifacts with no
            # timestamps (the mpegts muxer rejects size<7 AAC outright).
            if packet.size == 0 or (packet.pts is None and packet.dts is None):
                logger.debug(
                    "Skipping empty/timestamp-less packet (stream %s)",
                    packet.stream.index if packet.stream is not None else "?",
                )
                return
            src_key = packet.stream.index if packet.stream is not None else -1
            if src_key >= 0:
                # Separate bases per clock: B-frame delay (dts<pts) drives
                # the first dts negative under a single base.
                if src_key not in base_pts:
                    base_pts[src_key] = packet.pts if packet.pts is not None else 0
                if src_key not in base_dts:
                    base_dts[src_key] = packet.dts if packet.dts is not None else 0
                if packet.pts is not None:
                    packet.pts = max(0, packet.pts - base_pts[src_key])
                if packet.dts is not None:
                    packet.dts = max(0, packet.dts - base_dts[src_key])
            out_s = stream_map.get(packet.stream) if src_key >= 0 else None
            # stream identity may already be consumed; resolve out_s via key
            if out_s is None:
                for src, mapped in stream_map.items():
                    if src.index == src_key:
                        out_s = mapped
                        break
            bsf_entry = bsfs.get(src_key)
            candidates = bsf_entry[0].filter(packet) if bsf_entry else [packet]
            for pkt in candidates:
                pkt.stream = out_s
                mux_clamp.mux(out, pkt)

        for packet in inp.demux(list(stream_map)):
            _pause_hook(cancel_event)
            if cancel_event and cancel_event.is_set():
                logger.info("Recording stopped by user (%d bytes) — keeping output", bytes_out)
                break
            elapsed = time.monotonic() - start
            if duration_s is not None and elapsed >= duration_s:
                logger.info("Recording reached duration cap (%.1fs)", duration_s)
                break

            _emit(packet)
            bytes_out += max(0, packet.size or 0)

            now = time.monotonic()
            if on_progress and (now - last_report >= 0.25):
                last_report = now
                # Live streams have no total: the banner shows activity.
                prog = min(0.99, elapsed / duration_s) if duration_s and duration_s > 0 else 0.05
                on_progress(
                    prog,
                    f"Recording… {elapsed:.0f}s • {bytes_out // 1024} KB",
                )

        # Drain BSF-delayed packets (EOF marker)
        for bsf_ctx, out_s in bsfs.values():
            for pkt in bsf_ctx.filter(None):
                pkt.stream = out_s
                mux_clamp.mux(out, pkt)

        if on_progress:
            total_s = time.monotonic() - start
            on_progress(1.0, f"Recorded {total_s:.0f}s • {bytes_out // 1024} KB")
    finally:
        _close_container(out)

    # Zero-packet stops never trigger the muxer's lazy header write — keep
    # the "output exists" contract so callers can rely on the path.
    Path(output_path).touch(exist_ok=True)
    return output_path
