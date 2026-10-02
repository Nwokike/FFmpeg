"""Job item card for queue, in-progress tasks, and history lists."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import flet as ft

from core.constants import op_title
from core.notify import ERROR, show_snack
from core.state import Job
from core.storage_paths import format_bytes
from core.styles import card_container, status_badge
from core.theme import (
    ACCENT_AMBER,
    ACCENT_RED,
    PRIMARY,
    PRIMARY_CONTAINER_DARK,
    PRIMARY_CONTAINER_LIGHT,
    SURFACE_CARD_DARK,
    SURFACE_CARD_LIGHT,
    TEXT_MUTED_DARK,
    TEXT_MUTED_LIGHT,
)
from core.tokens import FONT_MD, FONT_SM, FONT_XS, ICON_MD, RADIUS_MD, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller
from state.service_ctx import use_services

logger = logging.getLogger(__name__)


def clamped_progress(progress: float | None) -> float:
    """One clamp for bar AND label (NaN/inf-safe) — they can never disagree."""
    try:
        value = float(progress or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(value, 1.0))


@ft.component
def job_card_view(job: Job, is_dark: bool = True) -> ft.Control:
    """Card displaying a media job with live-updating progress bar or result metadata."""
    ctrl = use_controller()
    services = use_services()
    muted = TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT

    status = job.status or "unknown"
    # Status color resolution
    if status == "completed":
        status_color = PRIMARY
        bg_status = PRIMARY_CONTAINER_DARK if is_dark else PRIMARY_CONTAINER_LIGHT
    elif status == "running":
        status_color = ACCENT_AMBER
        bg_status = "#3D2E0B" if is_dark else "#FEF3C7"
    elif status == "failed":
        status_color = ACCENT_RED
        bg_status = "#3E1C1C" if is_dark else "#FEE2E2"
    else:
        status_color = muted
        bg_status = SURFACE_CARD_DARK if is_dark else SURFACE_CARD_LIGHT

    title = op_title(job.op)
    # Old history can carry None paths — guard before Path() or .title().
    norm_op = (job.op or "").strip() or "convert"
    card_icon_hint = "audio" in norm_op

    in_name = Path(job.input_path).name if job.input_path else "Unknown"
    out_name = Path(job.output_path).name if job.output_path else ""

    queue = getattr(services, "queue", None)

    def _is_paused() -> bool:
        if queue is not None and hasattr(queue, "is_job_paused"):
            try:
                return bool(queue.is_job_paused(job.id))
            except Exception:
                pass
        return (job.status_message or "") == "Paused"

    busy_action, set_busy_action = ft.use_state(False)

    def _guarded(action_name: str, fn) -> None:
        """Fire a share/save once; ignore double-taps while one is in flight.

        The controller slots are fire-and-forget ``page.run_task`` wrappers
        (sync, not coroutines), so there is nothing to await — the guard is
        the duplicate-tap window plus a loud snack if scheduling itself fails.
        Page access is lazy: the card also renders in page-less contexts.
        """
        if busy_action:
            return
        try:
            page = ft.context.page
        except RuntimeError:
            logger.warning("Card %s ignored outside a page context", action_name)
            return
        set_busy_action(True)
        try:
            fn(job)
        except Exception as exc:
            logger.warning("Card %s failed for %s: %s", action_name, job.id, exc)
            show_snack(page, f"{action_name} failed: {exc}", bgcolor=ERROR)
            set_busy_action(False)
            return

        async def _release() -> None:
            import asyncio as _asyncio

            await _asyncio.sleep(2.0)
            set_busy_action(False)

        try:
            page.run_task(_release)
        except Exception:
            set_busy_action(False)

    # Action buttons
    action_btns: list[ft.Control] = []
    if job.is_running:
        paused = _is_paused()
        action_btns.append(
            ft.IconButton(
                icon=ft.Icons.PAUSE_ROUNDED if not paused else ft.Icons.PLAY_ARROW_ROUNDED,
                icon_color=PRIMARY,
                icon_size=ICON_MD,
                tooltip="Pause Job" if not paused else "Resume Job",
                on_click=lambda _: ctrl.toggle_pause_job(job.id),
            )
        )
        action_btns.append(
            ft.IconButton(
                icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                icon_color=ACCENT_RED,
                icon_size=ICON_MD,
                tooltip="Cancel Job",
                on_click=lambda _: ctrl.cancel_job(job.id),
            )
        )
    elif status == "pending":
        paused = _is_paused()
        if paused:
            action_btns.append(
                ft.IconButton(
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    icon_color=PRIMARY,
                    icon_size=ICON_MD,
                    tooltip="Resume Job",
                    on_click=lambda _: ctrl.toggle_pause_job(job.id),
                )
            )
        action_btns.append(
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_color=muted,
                icon_size=ICON_MD,
                tooltip="Remove from Queue",
                on_click=lambda _: ctrl.cancel_job(job.id),
            )
        )
    elif status == "completed":
        action_btns.extend(
            [
                ft.IconButton(
                    icon=ft.Icons.SHARE_OUTLINED,
                    icon_size=ICON_MD,
                    tooltip="Share",
                    disabled=busy_action,
                    on_click=lambda _: _guarded("Share", ctrl.share_result),
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD_OUTLINED,
                    icon_size=ICON_MD,
                    tooltip="Save to Device",
                    disabled=busy_action,
                    on_click=lambda _: _guarded("Save", ctrl.save_result),
                ),
                ft.TextButton(
                    "View result",
                    on_click=lambda _: _view_result(),
                ),
            ]
        )
    elif status in ("failed", "cancelled"):
        action_btns.extend(
            [
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_color=PRIMARY,
                    icon_size=ICON_MD,
                    tooltip="Retry",
                    on_click=lambda _: ctrl.retry_job(job),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=muted,
                    icon_size=ICON_MD,
                    tooltip="Remove",
                    on_click=lambda _: ctrl.delete_job(job.id),
                ),
            ]
        )

    def _view_result() -> None:
        from core.state import state

        state.last_completed_job = job
        ctrl.navigate("result")

    op_icons = {
        "extract_subtitles": ft.Icons.SUBTITLES_OUTLINED,
        "record": ft.Icons.VIDEOCAM_OUTLINED,
        "remux": ft.Icons.CONTENT_COPY_ROUNDED,
        "concat": ft.Icons.MERGE_TYPE_ROUNDED,
    }
    card_icon = op_icons.get(
        norm_op,
        ft.Icons.AUDIOTRACK_OUTLINED if card_icon_hint else ft.Icons.MOVIE_OUTLINED,
    )

    content_rows = [
        ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            card_icon,
                            size=ICON_MD,
                            color=PRIMARY,
                        ),
                        ft.Text(title, size=FONT_MD, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=SPACE_SM,
                    tight=True,
                ),
                ft.Row(
                    controls=[
                        status_badge(status.upper(), text_color=status_color, bg_color=bg_status),
                        *action_btns,
                    ],
                    spacing=SPACE_SM,
                    tight=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Text(
            f"Input: {in_name}",
            size=FONT_SM,
            color=muted,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
    ]

    if job.is_running:
        pct = clamped_progress(job.progress)
        content_rows.extend(
            [
                ft.ProgressBar(
                    value=pct,
                    color=PRIMARY,
                    bgcolor=bg_status,
                ),
                ft.Row(
                    controls=[
                        ft.Text(job.status_message or "", size=FONT_XS, color=muted),
                        ft.Text(
                            f"{int(pct * 100)}%",
                            size=FONT_XS,
                            weight=ft.FontWeight.W_600,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ]
        )
    elif status == "completed":
        size_info = ""
        if (job.original_size_bytes or 0) > 0 or (job.output_size_bytes or 0) > 0:
            size_info = (
                f"{format_bytes(job.original_size_bytes or 0)} → "
                f"{format_bytes(job.output_size_bytes or 0)}"
            )
        content_rows.append(
            ft.Row(
                controls=[
                    ft.Text(
                        f"Output: {out_name}",
                        size=FONT_SM,
                        weight=ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    *(
                        [
                            ft.Text(
                                size_info, size=FONT_XS, color=PRIMARY, weight=ft.FontWeight.W_600
                            )
                        ]
                        if size_info
                        else []
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )
    elif status == "failed" and job.error_message:
        content_rows.append(
            ft.Text(
                f"Error: {job.error_message}",
                size=FONT_XS,
                color=ACCENT_RED,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )

    # No whole-card on_click: the inner Share/Save buttons used to bubble up
    # to it and yank the user to Results mid-sheet. "View result" above is the
    # explicit navigation affordance.
    return card_container(
        content=ft.Column(controls=content_rows, spacing=SPACE_SM),
        padding=SPACE_MD,
        border_radius=RADIUS_MD,
        is_dark=is_dark,
    )
