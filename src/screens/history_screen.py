"""Jobs and conversions history view with search, filter, and swipe-to-delete."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from components.empty_state import empty_state_view
from components.job_card import job_card_view
from core.notify import ERROR, show_snack
from core.state import state
from core.styles import section_header
from core.theme import ACCENT_RED, is_dark_mode
from core.tokens import RADIUS_MD, SPACE_LG, SPACE_MD, SPACE_SM
from state.controller_ctx import use_controller


@ft.component
def HistoryScreen() -> ft.Control:
    """Historical archive of media operations with Dismissible delete actions."""
    page = ft.context.page
    ctrl = use_controller()
    is_dark = is_dark_mode(page)

    search_query, set_search_query = ft.use_state("")
    history_items = state.history

    filtered_items = (
        [
            j
            for j in history_items
            if search_query.lower() in Path(j.input_path).name.lower()
            or search_query.lower() in j.op.lower()
            or search_query.lower() in Path(j.output_path).name.lower()
        ]
        if search_query
        else history_items
    )

    def _confirm_clear_all(_):
        def _clear(_):
            ctrl.clear_history()
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text("Clear All History?"),
            content=ft.Text(
                "This will remove all job records from your local history. Converted files on your disk will remain untouched."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton("Clear All", bgcolor=ACCENT_RED, on_click=_clear),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    def _build_dismissible_card(job):
        card = job_card_view(job, is_dark=is_dark)

        def _on_dismiss(_e):
            # Delete, then offer Undo — swipe used to be unrecoverable data loss.
            ctrl.delete_job(job.id)
            show_snack(
                page,
                f"Deleted {Path(job.output_path).name or job.op}",
                bgcolor=ERROR,
                duration_ms=5000,
                action=ft.SnackBarAction(
                    label="UNDO",
                    on_click=lambda _: ctrl.restore_job(job),
                ),
            )

        return ft.Dismissible(
            key=ft.ValueKey(job.id),
            content=card,
            background=ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color="#FFFFFF", size=24)],
                    alignment=ft.MainAxisAlignment.START,
                    padding=ft.Padding.only(left=SPACE_LG),
                ),
                bgcolor=ACCENT_RED,
                border_radius=RADIUS_MD,
                alignment=ft.Alignment.CENTER_LEFT,
            ),
            secondary_background=ft.Container(
                content=ft.Row(
                    [ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color="#FFFFFF", size=24)],
                    alignment=ft.MainAxisAlignment.END,
                    padding=ft.Padding.only(right=SPACE_LG),
                ),
                bgcolor=ACCENT_RED,
                border_radius=RADIUS_MD,
                alignment=ft.Alignment.CENTER_RIGHT,
            ),
            on_dismiss=_on_dismiss,
        )

    return ft.ListView(
        controls=[
            # Header
            section_header(
                "History & Jobs",
                subtitle=f"{len(history_items)} total recorded tasks",
                action=ft.OutlinedButton(
                    "Clear All", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=_confirm_clear_all
                )
                if history_items
                else None,
                is_dark=is_dark,
            ),
            # Search bar if there are history items
            *(
                [
                    ft.TextField(
                        value=search_query,
                        hint_text="Filter history by name or operation...",
                        prefix_icon=ft.Icons.SEARCH_ROUNDED,
                        dense=True,
                        on_change=lambda e: set_search_query(e.control.value),
                    )
                ]
                if len(history_items) > 2
                else []
            ),
            # Now Processing — the serial queue (running + pending jobs)
            *(
                [
                    section_header(
                        "Now Processing",
                        (
                            f"{len(state.jobs)} in queue"
                            if len(state.jobs) > 1
                            else ("1 running" if state.jobs else "")
                        ),
                        is_dark=is_dark,
                    ),
                    ft.Column(
                        controls=[
                            job_card_view(j, is_dark=is_dark) for j in state.jobs
                        ],
                        spacing=SPACE_SM,
                    ),
                ]
                if state.jobs
                else []
            ),
            # Items or empty state
            *(
                [
                    ft.Column(
                        controls=[_build_dismissible_card(j) for j in filtered_items],
                        spacing=SPACE_SM,
                    )
                ]
                if filtered_items
                else [
                    empty_state_view(
                        icon=ft.Icons.HISTORY_ROUNDED,
                        title="No History Found" if search_query else "No Conversions Yet",
                        subtitle="Your processed media tasks will appear here automatically with swipe-to-delete support.",
                        action=ft.FilledButton(
                            "Start New Conversion", on_click=lambda _: ctrl.select_tab(0)
                        )
                        if not search_query
                        else None,
                        is_dark=is_dark,
                    )
                ]
            ),
        ],
        spacing=SPACE_MD,
        expand=True,
    )
