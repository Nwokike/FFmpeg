"""Media Dossier inspection screen displaying stream, container, and codec specs."""

from __future__ import annotations

import logging
from pathlib import Path

import flet as ft

from core.notify import ERROR, show_snack
from core.state import Job, MediaInfo, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header, status_badge
from core.theme import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
    is_dark_mode,
)
from core.tokens import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    RADIUS_LG,
    RADIUS_MD,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
)
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)

_DISPOSITION_LABELS = {
    "default": "Default",
    "forced": "Forced",
    "hearing_impaired": "SDH",
    "visual_impaired": "VI",
    "original": "Original",
    "comment": "Comment",
    "attached_pic": "Cover",
    "captions": "Captions",
}


def _fmt_ct(sec: float) -> str:
    """Chapter time as h:mm:ss (or mm:ss under an hour)."""
    total = max(0, int(sec))
    h, total = divmod(total, 3600)
    m, s = divmod(total, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build_media_report(info: MediaInfo) -> str:
    """Markdown dossier for the share sheet (unit-tested)."""
    lines = [f"# {info.file_name}", "", "## Container"]
    lines.append(f"- Format: {info.format_long_name} [{info.format_name}]")
    lines.append(f"- Size: {format_bytes(info.file_size_bytes)}")
    lines.append(f"- Duration: {info.duration_s:.2f} s")
    lines.append(f"- Bitrate: {info.bitrate // 1000} kbps")
    if info.metadata:
        lines += ["", "## Metadata"]
        lines += [f"- {k}: {v}" for k, v in info.metadata.items()]
    lines += ["", "## Streams"]
    for s in info.streams:
        details: list[str] = []
        if s.stream_type == "video" and s.width:
            details.append(f"{s.width}x{s.height}")
            if s.fps:
                details.append(f"{s.fps:.1f} fps")
            if s.rotation:
                details.append(f"rot {s.rotation}°")
        if s.stream_type == "audio" and s.channels:
            details.append(f"{s.channels}ch {s.sample_rate} Hz")
        if s.language:
            details.append(f"lang {s.language}")
        if s.disposition:
            details.append("/".join(s.disposition))
        base = f"- #{s.index} {s.stream_type} `{s.codec_name}`"
        lines.append(base + (f" — {', '.join(details)}" if details else ""))
    if info.chapters:
        lines += ["", "## Chapters"]
        lines += [f"- {_fmt_ct(c.start_s)} → {_fmt_ct(c.end_s)}  {c.title}" for c in info.chapters]
    lines += ["", "_Generated on-device by FFmpeg — Media Dossier._"]
    return "\n".join(lines) + "\n"


@ft.component
def ProbeScreen() -> ft.Control:
    """Detailed media intelligence dossier showing streams, codecs, and metadata."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    # Hooks first (discipline): excluded-stream set survives info swaps.
    excluded, set_excluded = ft.use_state([])
    remuxing, set_remuxing = ft.use_state(False)

    info = app_state.current_media_info
    media_path = app_state.current_media_path

    if not info or not media_path or not Path(media_path).exists():
        return ft.ListView(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: ctrl.navigate("dashboard"),
                        ),
                        ft.Text("Media Dossier", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                ),
                card_container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=48, color=muted),
                            ft.Text(
                                "No Media File Selected", size=FONT_MD, weight=ft.FontWeight.BOLD
                            ),
                            ft.Text(
                                "Select any video or audio file to inspect its internal streams.",
                                size=FONT_SM,
                                color=muted,
                            ),
                            ft.FilledButton(
                                "Select Media",
                                icon=ft.Icons.FILE_OPEN_ROUNDED,
                                on_click=lambda _: ctrl.pick_media_for("probe"),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=SPACE_MD,
                    ),
                    padding=SPACE_LG,
                    is_dark=is_dark,
                ),
            ],
            spacing=SPACE_MD,
            expand=True,
        )

    file_size_str = format_bytes(info.file_size_bytes)
    dur_str = (
        f"{int(info.duration_s // 60)}m {int(info.duration_s % 60)}s"
        if info.duration_s > 0
        else "Unknown"
    )

    def _toggle_stream(idx: int) -> None:
        if idx in excluded:
            set_excluded([i for i in excluded if i != idx])
        else:
            set_excluded([*excluded, idx])

    stream_cards: list[ft.Control] = []
    for s in info.streams:
        props: list[ft.Control] = []
        if s.stream_type == "video":
            icon = ft.Icons.VIDEOCAM_OUTLINED
            color = PRIMARY
            props = [
                ft.Text(f"Resolution: {s.width}x{s.height}", size=FONT_SM),
                ft.Text(
                    f"Framerate: {s.fps:.1f} fps" if s.fps else "Framerate: Variable", size=FONT_SM
                ),
                ft.Text(f"Pixel Format: {s.pix_fmt}", size=FONT_SM),
            ]
            if s.rotation:
                props.append(ft.Text(f"Rotation: {s.rotation}°", size=FONT_SM, color=color))
        elif s.stream_type == "audio":
            icon = ft.Icons.AUDIOTRACK_OUTLINED
            color = ACCENT_BLUE
            props = [
                ft.Text(f"Sample Rate: {s.sample_rate} Hz", size=FONT_SM),
                ft.Text(f"Channels: {s.channels} ({s.channel_layout})", size=FONT_SM),
                ft.Text(f"Language: {s.language or 'Undetermined'}", size=FONT_SM),
            ]
        elif s.stream_type in ("data", "attachment"):
            # Fonts, covers and chapter tracks used to fall into the subtitle
            # branch below and wear the wrong icon.
            icon = ft.Icons.DATA_OBJECT_OUTLINED
            color = ACCENT_AMBER
            props = [ft.Text("Embedded data / attachment stream", size=FONT_SM)]
        else:
            icon = ft.Icons.SUBTITLES_OUTLINED
            color = muted
            props = [
                ft.Text(f"Language: {s.language or 'Undetermined'}", size=FONT_SM),
            ]

        if s.disposition:
            props.append(
                ft.Row(
                    controls=[
                        status_badge(
                            _DISPOSITION_LABELS.get(flag, flag.title()),
                            text_color=color,
                            bg_color=f"{color}22",
                        )
                        for flag in s.disposition
                    ],
                    spacing=SPACE_SM,
                    wrap=True,
                )
            )

        trailing: list[ft.Control] = []
        if len(info.streams) > 1:
            trailing.append(
                ft.Switch(
                    value=s.index not in excluded,
                    tooltip="Include this track when saving a streams copy",
                    on_change=lambda _e, i=s.index: _toggle_stream(i),
                )
            )

        stream_cards.append(
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Icon(icon, size=24, color=color),
                        ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Text(
                                            f"Stream #{s.index}: {s.stream_type.upper()}",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        status_badge(
                                            (s.codec_name or "unknown").upper(),
                                            text_color=color,
                                            bg_color=f"{color}22",
                                        ),
                                    ],
                                    spacing=SPACE_SM,
                                ),
                                *props,
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        *trailing,
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            )
        )

    def _start_remux(_):
        if remuxing:
            return
        if not media_path or not info.streams or len(excluded) >= len(info.streams):
            if info.streams and len(excluded) >= len(info.streams):
                show_snack(page, "Keep at least one track", bgcolor=ERROR)
            return
        stem = Path(media_path).stem
        out_path = str(get_temp_dir() / unique_temp_name(f"{stem}_tracks", ".mkv"))
        job = Job(
            op="remux",
            input_path=media_path,
            output_path=out_path,
            params={"drop": list(excluded)},
            original_size_bytes=info.file_size_bytes,
        )
        set_remuxing(True)
        try:
            ctrl.start_job(job)
        except Exception as exc:
            logger.warning("Remux start failed: %s", exc)
            set_remuxing(False)

    async def _share_report() -> None:
        try:
            report = build_media_report(info)
            out = get_temp_dir() / unique_temp_name(f"{Path(media_path).stem}_dossier", ".md")
            out.write_text(report, encoding="utf-8")
            ok = await services.media_io.share_file(str(out))
            if not ok:
                show_snack(page, "Couldn't open the share sheet", bgcolor=ERROR)
        except Exception as exc:
            logger.exception("Dossier report failed")
            show_snack(page, f"Report failed: {exc}", bgcolor=ERROR)

    return ft.ListView(
        controls=[
            # Header
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Media Dossier", size=FONT_LG, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.OutlinedButton("Change", on_click=lambda _: ctrl.pick_media_for("probe")),
                ],
                spacing=SPACE_SM,
            ),
            # General Specs Card
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    info.file_name,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                                status_badge(info.format_name.upper(), text_color=PRIMARY),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    [
                                        ft.Text("SIZE", size=FONT_XS, color=muted),
                                        ft.Text(
                                            file_size_str, size=FONT_SM, weight=ft.FontWeight.W_600
                                        ),
                                    ]
                                ),
                                ft.Column(
                                    [
                                        ft.Text("DURATION", size=FONT_XS, color=muted),
                                        ft.Text(dur_str, size=FONT_SM, weight=ft.FontWeight.W_600),
                                    ]
                                ),
                                ft.Column(
                                    [
                                        ft.Text("BITRATE", size=FONT_XS, color=muted),
                                        ft.Text(
                                            f"{info.bitrate // 1000} kbps",
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                    ]
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=SPACE_MD,
                ),
                padding=SPACE_LG,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            # Stream specifications
            section_header(
                f"Streams ({len(info.streams)})", "Track-by-track breakdown", is_dark=is_dark
            ),
            ft.Column(controls=stream_cards, spacing=SPACE_SM),
            # Chapters (when the container carries them)
            *(
                [
                    section_header(
                        f"Chapters ({len(info.chapters)})",
                        "Navigation points in this file",
                        is_dark=is_dark,
                    ),
                    card_container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(ft.Icons.FLAG_ROUNDED, size=16, color=PRIMARY),
                                        ft.Text(
                                            ch.title,
                                            size=FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                            expand=True,
                                        ),
                                        ft.Text(
                                            f"{_fmt_ct(ch.start_s)} → {_fmt_ct(ch.end_s)}",
                                            size=FONT_XS,
                                            color=muted,
                                        ),
                                    ],
                                    spacing=SPACE_SM,
                                )
                                for ch in info.chapters
                            ],
                            spacing=SPACE_SM,
                        ),
                        padding=SPACE_MD,
                        border_radius=RADIUS_MD,
                        is_dark=is_dark,
                    ),
                ]
                if info.chapters
                else []
            ),
            # Raw FFmpeg Overview
            section_header("Raw Diagnostics", "Direct container summary", is_dark=is_dark),
            card_container(
                content=ft.Text(
                    info.raw_dump, size=FONT_XS, font_family="monospace", selectable=True
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_MD,
                is_dark=is_dark,
            ),
            # Track picker + shareable report
            ft.Row(
                controls=[
                    ft.FilledButton(
                        "Save Streams Copy",
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        height=48,
                        expand=True,
                        disabled=(bool(info.streams) and len(excluded) >= len(info.streams))
                        or remuxing,
                        on_click=_start_remux,
                    ),
                    ft.OutlinedButton(
                        "Share Report",
                        icon=ft.Icons.SHARE_ROUNDED,
                        height=48,
                        on_click=lambda _: page.run_task(_share_report),
                    ),
                ],
                spacing=SPACE_MD,
            ),
            # Quick conversion action
            ft.FilledButton(
                "Convert This File",
                icon=ft.Icons.TRANSFORM_ROUNDED,
                height=48,
                on_click=lambda _: ctrl.navigate("convert"),
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
