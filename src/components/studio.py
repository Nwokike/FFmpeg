"""Shared UI components introduced in the studio pass.

Small, composed pieces every screen reuses instead of hand-rolling:
- chip_group: one-select chip row (the pattern every tool screen copied)
- screen_header: back arrow + title (+ subtitle, actions)
- adaptive_sheet: BottomSheet on phones, AlertDialog on desktop
- media_summary_card: thumbnail + name + facts for the loaded file
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import flet as ft

from core.theme import (
    BORDER_DARK,
    BORDER_LIGHT,
    KIRI_DARK_2,
    PRIMARY,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
)
from core.tokens import (
    FONT_SM,
    FONT_XS,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_2XS,
    SPACE_SM,
    SPACE_XS,
)

_PHONE_BREAKPOINT = 600  # Material compact width
_THUMB_CACHE: dict[tuple[str, float], bytes | None] = {}


def _muted(is_dark: bool) -> str:
    return TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT


def _fmt_size(num: float | None) -> str:
    if not num:
        return ""
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GB"


def _fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chip_group(
    options: Iterable[Any],
    *,
    value: Any,
    on_change: Callable[[Any], None],
    is_dark: bool = True,
    wrap: bool = True,
    key: str | None = None,
) -> ft.Control:
    """A single-select chip row. ``options`` may be strings or (label, value) pairs."""
    chips: list[ft.Control] = []
    for option in options:
        label, option_value = option if isinstance(option, tuple) else (option, option)
        selected = option_value == value
        chips.append(
            ft.Chip(
                label=ft.Text(str(label), size=FONT_SM),
                selected=selected,
                show_checkmark=selected,
                on_select=lambda _e, v=option_value: on_change(v),
            )
        )
    return ft.Row(
        controls=chips,
        wrap=wrap,
        spacing=SPACE_XS,
        run_spacing=SPACE_2XS,
        key=key,
    )


def screen_header(
    title: str,
    *,
    subtitle: str | None = None,
    on_back: Callable[[], None] | None = None,
    actions: list[ft.Control] | None = None,
    is_dark: bool = True,
) -> ft.Control:
    """Back arrow + title block + optional trailing actions."""
    leading = (
        [
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                icon_size=20,
                tooltip="Back",
                on_click=lambda _e: on_back(),
            )
        ]
        if on_back
        else []
    )
    title_col = ft.Column(
        controls=[
            ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
            *(
                [ft.Text(subtitle, size=FONT_XS, color=_muted(is_dark), no_wrap=True)]
                if subtitle
                else []
            ),
        ],
        spacing=0,
        expand=True,
    )
    return ft.Container(
        content=ft.Row(
            controls=[*leading, title_col, *(actions or [])],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACE_SM,
        ),
        padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=SPACE_SM),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_DARK if is_dark else BORDER_LIGHT)),
    )


def adaptive_sheet(
    page: ft.Page,
    content: ft.Control,
    *,
    title: str | None = None,
    on_close: Callable[[], None] | None = None,
) -> None:
    """Show a bottom sheet on phones and a centered dialog on wider screens."""
    width = getattr(page, "width", None) or 0
    if width and width >= _PHONE_BREAKPOINT:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(title) if title else None,
                content=ft.Container(content=content, width=480, height=420),
                on_dismiss=lambda _e: on_close() if on_close else None,
            )
        )
    else:
        page.show_dialog(
            ft.BottomSheet(
                content=ft.Container(
                    content=content,
                    padding=ft.Padding.only(left=SPACE_SM, right=SPACE_SM, top=SPACE_SM),
                ),
                show_drag_handle=True,
                on_dismiss=lambda _e: on_close() if on_close else None,
            )
        )


def poster_bytes(path: str | None, *, at_s: float = 0.5) -> bytes | None:
    """One cached JPEG thumbnail for a media path (best effort, never raises)."""
    if not path:
        return None
    try:
        key = (str(path), Path(path).stat().st_mtime)
    except OSError:
        return None
    if key in _THUMB_CACHE:
        return _THUMB_CACHE[key]
    blob: bytes | None = None
    try:
        from services.engine_service import EngineService

        frames = EngineService.thumbnail_strip(str(path), times=[at_s], width=160)
        blob = frames[0] if frames else None
    except Exception:
        blob = None
    _THUMB_CACHE[key] = blob
    return blob


def media_summary_card(
    path: str | None,
    info: Any = None,
    *,
    is_dark: bool = True,
    on_change: Callable[[], None] | None = None,
    extra_chips: Iterable[str] = (),
    key: str | None = None,
) -> ft.Control:
    """The loaded file at a glance: poster, name, duration/size/codec chips."""
    bg = KIRI_DARK_2 if is_dark else "#FFFFFF"
    border = BORDER_DARK if is_dark else BORDER_LIGHT
    name = Path(path).name if path else "No media selected"
    chips: list[ft.Control] = []
    if info is not None:
        duration = _fmt_duration(getattr(info, "duration_s", None))
        if duration:
            chips.append(_fact_chip(duration))
        with contextlib.suppress(OSError, TypeError):
            chips.append(_fact_chip(_fmt_size(Path(path).stat().st_size)))
        video = getattr(info, "video_stream", None)
        audio = getattr(info, "audio_stream", None)
        if video is not None:
            codec = getattr(video, "codec_name", "") or ""
            dims = ""
            if getattr(video, "width", None) and getattr(video, "height", None):
                dims = f"{video.width}x{video.height}"
            chips.append(_fact_chip(" ".join(part for part in (codec, dims) if part)))
        elif audio is not None:
            chips.append(
                _fact_chip(
                    f"{getattr(audio, 'codec_name', '') or 'audio'} · "
                    f"{getattr(audio, 'channels', '') or 2}ch"
                )
            )
    chips.extend(_fact_chip(text) for text in extra_chips if text)

    poster = poster_bytes(path)
    thumb: ft.Control = (
        ft.Image(src=poster, width=96, height=54, fit=ft.BoxFit.COVER, border_radius=RADIUS_SM)
        if poster
        else ft.Container(
            width=96,
            height=54,
            border_radius=RADIUS_SM,
            bgcolor=PRIMARY + "22",
            content=ft.Icon(ft.Icons.PERM_MEDIA, size=24, color=PRIMARY),
            alignment=ft.Alignment.CENTER,
        )
    )
    return ft.Container(
        key=key,
        bgcolor=bg,
        border=ft.Border.all(1, border),
        border_radius=RADIUS_MD,
        padding=SPACE_SM,
        content=ft.Row(
            controls=[
                thumb,
                ft.Column(
                    controls=[
                        ft.Text(name, size=FONT_SM, weight=ft.FontWeight.W_600, no_wrap=True),
                        ft.Row(controls=chips, wrap=True, spacing=SPACE_2XS),
                    ],
                    spacing=SPACE_2XS,
                    expand=True,
                ),
                *(
                    [
                        ft.IconButton(
                            icon=ft.Icons.SWAP_HORIZ,
                            tooltip="Change media",
                            on_click=lambda _e: on_change(),
                        )
                    ]
                    if on_change
                    else []
                ),
            ],
            spacing=SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _fact_chip(text: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(text, size=FONT_XS, color=PRIMARY),
        padding=ft.Padding.symmetric(horizontal=SPACE_XS, vertical=2),
        border_radius=RADIUS_SM,
        bgcolor=PRIMARY + "22",
    )
