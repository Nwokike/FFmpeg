"""Jobs and conversions history view with search, filter, and swipe-to-delete."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.empty_state import empty_state_view
from components.job_card import job_card_view
from core.constants import op_title
from core.notify import ERROR, show_snack
from core.state import use_app_state
from core.styles import section_header
from core.theme import ACCENT_RED, is_dark_mode
from core.tokens import RADIUS_MD, SPACE_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def HistoryScreen() -> ft.Control:
    """Historical archive of media operations with Dismissible delete actions."""
    page = ft.context.page
    ctrl = use_controller()
    app_state = use_app_state()
    is_dark = is_dark_mode(page, app_state)

    search_query, set_search_query = ft.use_state("")
    history_items = app_state.history

    query = search_query.strip().lower()
    filtered_items = (
        [
            j
            for j in history_items
            # Restored jobs can carry None paths/ops (explicit JSON null) —
            # Path(None) raised the moment the user typed a character.
            if query in Path(j.input_path or "").name.lower()
            or query in (j.op or "").lower()
            or query in Path(j.output_path or "").name.lower()
        ]
        if query
        else history_items
    )

    def _confirm_clear_all(_):
        shown = len(filtered_items)
        total = len(history_items)

        def _clear(_):
            snapshot = list(history_items)
            ctrl.clear_history()
            set_search_query("")
            page.pop_dialog()
            if snapshot:
                show_snack(
                    page,
                    f"Cleared {len(snapshot)} record(s)",
                    bgcolor=ERROR,
                    duration_ms=5000,
                    action=ft.SnackBarAction(
                        label="UNDO",
                        on_click=lambda _: ctrl.restore_all(snapshot),
                    ),
                )

        dlg = ft.AlertDialog(
            title=ft.Text("Clear All History?"),
            content=ft.Text(
                "This will remove all job records from your local history. Converted files on your disk will remain untouched."
                + (
                    f" ({shown} of {total} shown by the current filter — "
                    "this clears ALL records, not just the visible ones.)"
                    if query
                    else ""
                )
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton("Clear All", bgcolor=ACCENT_RED, on_click=_clear),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    def _build_dismissible_card(job, state_index: int):
        card = job_card_view(job, is_dark=is_dark)

        def _on_dismiss(_e):
            # Delete, then offer Undo — swipe used to be unrecoverable data loss.
            ctrl.delete_job(job.id)
            show_snack(
                page,
                f"Deleted {Path(job.output_path or '').name or op_title(job.op)}",
                bgcolor=ERROR,
                duration_ms=5000,
                action=ft.SnackBarAction(
                    label="UNDO",
                    on_click=lambda _: ctrl.restore_job(job, state_index),
                ),
            )

        return ft.Dismissible(
            key=ft.ValueKey(f"{job.id}-{job.created_at}"),
            content=card,
            background=ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color="#FFFFFF", size=24)],
                    alignment=ft.MainAxisAlignment.START,
                ),
                # padding lives on Container — ft.Row has NO padding kwarg
                # (pre-existing TypeError that froze the History tab).
                padding=ft.Padding.only(left=SPACE_LG),
                bgcolor=ACCENT_RED,
                border_radius=RADIUS_MD,
                alignment=ft.Alignment.CENTER_LEFT,
            ),
            secondary_background=ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color="#FFFFFF", size=24)],
                    alignment=ft.MainAxisAlignment.END,
                ),
                padding=ft.Padding.only(right=SPACE_LG),
                bgcolor=ACCENT_RED,
                border_radius=RADIUS_MD,
                alignment=ft.Alignment.CENTER_RIGHT,
            ),
            dismiss_direction=ft.DismissDirection.HORIZONTAL,
            on_dismiss=_on_dismiss,
        )

    # State index per card (NOT the filtered-view index — filtered position
    # and history position differ whenever a query is active, and undo must
    # restore the true position).
    state_index_of = {id(j): i for i, j in enumerate(history_items)}

    queue_count = len(app_state.jobs)
    running_count = sum(1 for j in app_state.jobs if j.is_running)

    return ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            # Header
            section_header(
                "History & Jobs",
                subtitle=(
                    f"{len(history_items)} in history"
                    + (f" · {queue_count} active" if queue_count else "")
                ),
                action=ft.OutlinedButton(
                    "Clear All", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=_confirm_clear_all
                )
                if history_items
                else None,
                is_dark=is_dark,
            ),
            # Search bar whenever there is anything to filter
            *(
                [
                    ft.TextField(
                        value=search_query,
                        hint_text="Filter history by name or operation...",
                        prefix_icon=ft.Icons.SEARCH_ROUNDED,
                        suffix_icon=ft.Icons.CLEAR_ROUNDED if search_query else None,
                        dense=True,
                        on_change=lambda e: set_search_query(e.control.value or ""),
                    )
                ]
                if history_items
                else []
            ),
            # Now Processing — the serial queue (running + pending jobs)
            *(
                [
                    section_header(
                        "Now Processing",
                        (
                            f"{queue_count} in queue"
                            if queue_count > 1
                            else (
                                "1 running"
                                if running_count
                                else ("1 queued" if queue_count else "")
                            )
                        ),
                        is_dark=is_dark,
                    ),
                    ft.Column(
                        controls=[job_card_view(j, is_dark=is_dark) for j in app_state.jobs],
                        spacing=SPACE_SM,
                    ),
                ]
                if app_state.jobs
                else []
            ),
            # Items or empty state
            *(
                [
                    ft.Column(
                        controls=[
                            _build_dismissible_card(j, state_index_of[id(j)])
                            for j in filtered_items
                        ],
                        spacing=SPACE_SM,
                    )
                ]
                if filtered_items
                else [
                    empty_state_view(
                        icon=ft.Icons.HISTORY_ROUNDED,
                        title=(
                            f'No matches for "{search_query.strip()}"'
                            if query
                            else "No Conversions Yet"
                        ),
                        subtitle=(
                            "Try a different filter — your tasks are still here."
                            if query
                            else "Your processed media tasks will appear here automatically with swipe-to-delete support."
                        ),
                        action=(
                            ft.OutlinedButton(
                                "Clear search", on_click=lambda _: set_search_query("")
                            )
                            if query
                            else ft.FilledButton(
                                "Start New Conversion", on_click=lambda _: ctrl.select_tab(0)
                            )
                        ),
                        is_dark=is_dark,
                    )
                ]
            ),
            # Nav-bar clearance INSIDE the scroll (sibling pattern — the shell's
            # fixed outer inset is gone; without this the last card sat under
            # the NavigationBar on gesture-nav phones).
            ft.Container(height=88),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
