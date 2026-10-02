"""Joiner screen — merge clips end-to-end: instant lossless, uniform re-encode,
or crossfade transitions (runtime-gated on the engine's blend window).

Owns its OWN local file list so the app-wide single-file `current_media`
assumption is untouched; multi-pick appends here only. Reordering is explicit
↑/↓ buttons (deterministic, no drag API gamble).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import flet as ft

from components.banner_ad import BannerAdView
from components.tool_job_status import tool_job_row
from core.notify import ERROR, show_snack
from core.state import Job, use_app_state
from core.storage_paths import format_bytes, get_temp_dir, unique_temp_name
from core.styles import card_container, section_header
from core.theme import TEXT_MUTED_DARK, TEXT_MUTED_LIGHT, is_dark_mode
from core.tokens import FONT_LG, FONT_SM, FONT_XS, RADIUS_LG, SPACE_MD, SPACE_SM
from services.engine_service import EngineService, available_filters
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)

_CONTAINERS = ("mp4", "mkv")
_FADES = (("Crossfade 0.5s", 0.5), ("Crossfade 1.0s", 1.0))


@ft.component
def JoinScreen() -> ft.Control:
    """Ordered multi-file picker + join controls (min two clips)."""
    page = ft.context.page
    ctrl = use_controller()
    services = use_services()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    entries, set_entries = ft.use_state([])  # [{path,name,size_s,dur_s,fps,w,h,kind,...}]
    container_fmt, set_container_fmt = ft.use_state("mp4")
    transition, set_transition = ft.use_state("cut")  # cut | crossfade
    fade_s, set_fade_s = ft.use_state(0.5)
    avail, set_avail = ft.use_state(frozenset())
    busy, set_busy = ft.use_state(False)

    # Live pipeline: derived from the queue (Start locks while it runs).
    running_job = (
        app_state.active_job if (app_state.active_job and app_state.active_job.is_running) else None
    )
    queue_busy = running_job is not None

    async def _load_avail() -> None:
        try:
            set_avail(frozenset(await asyncio.to_thread(available_filters)))
        except Exception as exc:
            logger.warning("Filter availability load failed: %s", exc)

    ft.use_effect(lambda: page.run_task(_load_avail), [])

    def _crossfade_reason() -> str | None:
        """None when crossfade can run for the current list; else why not."""
        if not entries:
            return "add at least two clips first"
        needed = {"alphamerge", "overlay"}
        if any(e.get("has_audio") for e in entries):
            needed.add("acrossfade")
        if avail:
            missing = needed - avail
            if missing:
                return f"not in this build: {', '.join(sorted(missing))}"
        first_fps = entries[0].get("fps") or 30.0
        for e in entries:
            if (e.get("kind") or "video") != "video":
                return f"{e['name']} is not a video clip"
            fps = e.get("fps") or 0.0
            if not fps:
                return f"{e['name']} has no video"
            if abs(fps - first_fps) > 2.0:
                return "frame rates differ"
            if (e.get("w") or 0) > 1920 or (e.get("h") or 0) > 1080:
                return "sources above 1080p"
            if e["dur_s"] <= fade_s * 2 + 0.2:
                return f"{e['name']} is too short for a {fade_s:g}s fade"
            if bool(e.get("has_audio")) != bool(entries[0].get("has_audio")):
                return "some clips have audio, others don't"
            if e.get("has_audio") and (
                e.get("sample_rate") != entries[0].get("sample_rate")
                or e.get("channels") != entries[0].get("channels")
            ):
                return "audio layouts differ"
        return None

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
                v = info.video_stream
                a = info.audio_stream
                return {
                    "path": p,
                    "name": Path(p).name,
                    "size_s": info.file_size_bytes,
                    "dur_s": info.duration_s,
                    "kind": info.kind,
                    "fps": v.fps if v else None,
                    "w": v.width if v else None,
                    "h": v.height if v else None,
                    "has_audio": a is not None,
                    "sample_rate": a.sample_rate if a else None,
                    "channels": a.channels if a else None,
                }

            new_entries = list(entries)
            failed = 0
            for p in added:
                try:
                    e = await asyncio.to_thread(_probe_sync, p)
                    if (e.get("kind") or "video") != "video":
                        show_snack(
                            page,
                            f"Skipped {e['name']}: joins need video clips",
                            bgcolor=ERROR,
                        )
                        continue
                    new_entries.append(e)
                except Exception as exc:
                    failed += 1
                    logger.warning("Skipping %s: %s", p, exc)
            set_entries(new_entries)
            if failed:
                show_snack(page, f"{failed} file(s) couldn't be read — skipped", bgcolor=ERROR)
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
        if queue_busy:
            return
        if transition == "crossfade":
            reason = _crossfade_reason()
            if reason is not None:
                show_snack(page, f"Crossfade unavailable: {reason}", bgcolor=ERROR)
                return
        ext = container_fmt
        out_name = unique_temp_name("joined", ext)
        out_path = str(get_temp_dir() / out_name)
        job = Job(
            op="concat",
            input_path=entries[0]["path"],
            output_path=out_path,
            params={
                "paths": [e["path"] for e in entries],
                "container": ("matroska" if ext == "mkv" else "mp4"),
                "transition": transition,
                "fade_s": fade_s,
            },
            original_size_bytes=sum(e["size_s"] for e in entries),
        )
        ctrl.start_job(job)

    total_dur = sum(e["dur_s"] for e in entries)
    total_size = sum(e["size_s"] for e in entries)
    gate_reason = _crossfade_reason()
    expected_dur = (
        total_dur - fade_s * (len(entries) - 1)
        if transition == "crossfade" and len(entries) >= 2
        else total_dur
    )

    entry_rows: list[ft.Control] = []
    for i, e in enumerate(entries):
        entry_rows.append(
            card_container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            width=24,
                            content=ft.Text(f"{i + 1}.", size=FONT_SM, weight=ft.FontWeight.W_600),
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
                                    selected=transition == "cut",
                                    on_select=lambda _: set_transition("cut"),
                                ),
                                *[
                                    ft.Chip(
                                        label=ft.Text(label),
                                        disabled=gate_reason is not None,
                                        selected=transition == "crossfade" and fade_s == value,
                                        on_select=lambda _, v=value: (
                                            set_transition("crossfade"),
                                            set_fade_s(v),
                                        ),
                                    )
                                    for label, value in _FADES
                                ],
                            ],
                            wrap=True,
                            spacing=SPACE_SM,
                        ),
                        ft.Text(
                            f"Crossfade unavailable: {gate_reason}"
                            if gate_reason is not None and entries
                            else (
                                f"Output ≈ {expected_dur:.1f}s — "
                                f"{len(entries) - 1} fade(s) of {fade_s:g}s overlap."
                                if transition == "crossfade" and len(entries) >= 2
                                else "Fade transitions blend each clip's end into "
                                "the next clip's start."
                            ),
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
            # Banner slot directly above the primary action — the natural
            # pause between reviewing the clip list and starting the join.
            BannerAdView(slot="join-action"),
            # Live pipeline status (derived, never stuck)
            *([tool_job_row(running_job, ctrl, is_dark=is_dark)] if running_job else []),
            ft.FilledButton(
                f"Join {len(entries) or ''} Clips".replace("  ", " "),
                icon=ft.Icons.MERGE_TYPE_ROUNDED,
                height=48,
                disabled=len(entries) < 2 or busy or queue_busy,
                on_click=_start_join,
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
