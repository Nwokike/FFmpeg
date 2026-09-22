"""Joiner screen — merge clips end-to-end (instant lossless or uniform re-encode).

Owns its OWN local file list so the app-wide single-file `current_media`
assumption is untouched; multi-pick appends here only. Reordering is explicit
↑/↓ buttons (deterministic, no drag API gamble).
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import flet as ft

from core.notify import ERROR, show_snack
from core.state import Job
from core.storage_paths import format_bytes, get_temp_dir
from core.styles import card_container, section_header
from core.theme import TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from services.engine_service import EngineService
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)

_CONTAINERS = ("mp4", "mkv")


@ft.component
def JoinScreen() -> ft.Control:
    """Ordered multi-file picker + join controls (min two clips)."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    is_dark = is_dark_mode(page)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    entries, set_entries = ft.use_state([])  # [{path,name,size_s,dur_s}]
    container_fmt, set_container_fmt = ft.use_state("mp4")
    busy, set_busy = ft.use_state(False)

    async def _add_files(_=None) -> None:
        set_busy(True)
        try:
            picked = await services.media_io.pick_media_files()
            if not picked:
                return
            existing = {e["path"] for e in entries}
            added = [p for p in picked if p not in existing]
            if len(added) + len(existing) > 8:
                added = added[: max(0, 8 - len(existing))]
                show_snack(page, "Capped at 8 clips per join", bgcolor=ERROR)

            def _probe_sync(p: str) -> dict:
                info = EngineService.probe(p)
                return {
                    "path": p,
                    "name": Path(p).name,
                    "size_s": info.file_size_bytes,
                    "dur_s": info.duration_s,
                }

            new_entries = list(entries)
            for p in added:
                try:
                    e = await asyncio.to_thread(_probe_sync, p)
                    new_entries.append(e)
                except Exception as exc:  # noqa: BLE001 — skip unreadable files
                    logger.warning("Skipping %s: %s", p, exc)
            set_entries(new_entries)
            if added and len(new_entries) < 2:
                show_snack(page, "Add at least one more clip to join")
        finally:
            set_busy(False)

    def _remove(idx: int) -> None:
        set_entries([e for i, e in enumerate(entries) if i != idx])

    def _move(idx: int, delta: int) -> None:
        target = idx + delta
        if target < 0 or target >= len(entries):
            return
        reordered = list(entries)
        reordered[idx], reordered[target] = reordered[target], reordered[idx]
        set_entries(reordered)

    def _start_join(_):
        if len(entries) < 2:
            show_snack(page, "Pick at least two files to join", bgcolor=ERROR)
            return
        ext = container_fmt
        out_path = str(get_temp_dir() / f"joined_{int(time.time())}.{ext}")
        job = Job(
            op="concat",
            input_path=entries[0]["path"],
            output_path=out_path,
            params={
                "paths": [e["path"] for e in entries],
                "container": ("matroska" if ext == "mkv" else "mp4"),
                "transition": "cut",
            },
            original_size_bytes=sum(e["size_s"] for e in entries),
        )
        ctrl.start_job(job)

    total_dur = sum(e["dur_s"] for e in entries)
    total_size = sum(e["size_s"] for e in entries)

    entry_rows: list[ft.Control] = []
    for i, e in enumerate(entries):
        entry_rows.append(
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            width=24,
                            content=ft.Text(
                                f"{i + 1}.", size=FONT_SM, weight=ft.FontWeight.W_600
                            ),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    e["name"],
                                    size=FONT_SM,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"{e['dur_s']:.1f}s • {format_bytes(e['size_s'])}",
                                    size=FONT_XS,
                                    color=muted,
                                ),
                            ],
                            spacing=0,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                            icon_size=18,
                            tooltip="Move up",
                            disabled=i == 0,
                            on_click=lambda _, idx=i: _move(idx, -1),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                            icon_size=18,
                            tooltip="Move down",
                            disabled=i == len(entries) - 1,
                            on_click=lambda _, idx=i: _move(idx, 1),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_size=18,
                            tooltip="Remove",
                            on_click=lambda _, idx=i: _remove(idx),
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_SM,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            )
        )

    return ft.ListView(
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: ctrl.navigate("dashboard"),
                        tooltip="Back to Dashboard",
                    ),
                    ft.Text("Join Clips", size=FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=SPACE_SM,
            ),
            section_header(
                "Files to Join",
                "Ordered top to bottom — output plays in this order",
                is_dark=is_dark,
            ),
            ft.Row(
                controls=[
                    ft.FilledButton(
                        "Add Files",
                        icon=ft.Icons.PLAYLIST_ADD_ROUNDED,
                        disabled=busy,
                        on_click=lambda _: page.run_task(_add_files),
                    ),
                    *(
                        [
                            ft.Text(
                                f"{len(entries)} clips • {total_dur:.1f}s • "
                                f"{format_bytes(total_size)}",
                                size=FONT_SM,
                                color=muted,
                            )
                        ]
                        if entries
                        else []
                    ),
                ],
                spacing=SPACE_MD,
                wrap=True,
            ),
            *entry_rows,
            *(
                []
                if entries
                else [
                    ft.Text(
                        "Clips are joined end-to-end. Identical formats merge "
                        "losslessly (instant); mixed formats get a uniform re-encode.",
                        size=FONT_SM,
                        color=muted,
                    )
                ]
            ),
            section_header("Transition", "How clips meet", is_dark=is_dark),
            card_container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Chip(
                                    label=ft.Text("Instant (hard cut)"),
                                    selected=True,
                                    on_select=lambda _: None,
                                ),
                            ],
                            spacing=SPACE_SM,
                        ),
                        ft.Text(
                            "Crossfade lands in the next pass — instant join is "
                            "the M2 baseline.",
                            size=FONT_XS,
                            color=muted,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_MD,
                border_radius=RADIUS_LG,
                is_dark=is_dark,
            ),
            section_header("Output", "Target container", is_dark=is_dark),
            ft.Row(
                controls=[
                    ft.Chip(
                        label=ft.Text(ext.upper() if ext != "mkv" else "MKV"),
                        selected=container_fmt == ext,
                        on_select=lambda _, v=ext: set_container_fmt(v),
                    )
                    for ext in _CONTAINERS
                ],
                spacing=SPACE_SM,
            ),
            ft.FilledButton(
                f"Join {len(entries) or ''} Clips".replace("  ", " "),
                icon=ft.Icons.MERGE_TYPE_ROUNDED,
                height=48,
                disabled=len(entries) < 2 or busy,
                on_click=_start_join,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
