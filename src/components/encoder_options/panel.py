"""The advanced-settings panel and muxer key/value rows."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import flet as ft

from components.encoder_options.coerce import OptionValues
from components.encoder_options.rows import _muted, option_controls
from core.theme import PRIMARY
from core.tokens import FONT_SM, FONT_XS, RADIUS_SM, SPACE_SM


@ft.component
def EncoderOptionPanel(
    codec: str,
    schema: Sequence[dict] | None,
    values: OptionValues,
    *,
    common_options: Sequence[str] = (),
    is_dark: bool = True,
    title: str = "Advanced settings",
    expanded: bool = False,
) -> ft.Control:
    """Every option this build exposes for ``codec``, searchable and grouped.

    Collapsed by default and ``maintain_state=False``: a 157-row tree is built
    on the Python side but only mounted when the user opens the panel.
    """
    muted = _muted(is_dark)
    entries = [spec for spec in (schema or []) if str(spec.get("name") or "")]
    common = {str(name) for name in (common_options or ())}
    specific = [spec for spec in entries if str(spec["name"]) not in common]

    query, set_query = ft.use_state("")
    scope, set_scope = ft.use_state("specific")
    reset_tick, set_reset_tick = ft.use_state(0)

    pool = specific if (scope == "specific" and specific) else entries
    needle = query.strip().lower()
    if needle:
        pool = [
            spec
            for spec in pool
            if needle in str(spec["name"]).lower() or needle in str(spec.get("help") or "").lower()
        ]
    ordered = sorted(pool, key=lambda spec: str(spec["name"]))
    rows = option_controls(
        ordered,
        values,
        is_dark=is_dark,
        on_reset=lambda _name: set_reset_tick(reset_tick + 1),
    )

    if not entries:
        body: list[ft.Control] = [
            ft.Text(f"This build exposes no option schema for {codec}.", size=FONT_SM, color=muted)
        ]
    else:
        set_count = len(values)
        body = [
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TUNE, size=18, color=PRIMARY),
                    ft.Text(
                        f"{set_count} of {len(entries)} set",
                        size=FONT_SM,
                        weight=ft.FontWeight.W_600,
                        expand=True,
                    ),
                    *(
                        [
                            ft.TextButton(
                                "Reset",
                                icon=ft.Icons.REFRESH,
                                on_click=lambda _e: _reset_all(values, set_reset_tick, reset_tick),
                            )
                        ]
                        if set_count
                        else []
                    ),
                ],
                spacing=SPACE_SM,
            ),
            ft.TextField(
                value=query,
                hint_text="Search by option name or help text",
                prefix_icon=ft.Icons.SEARCH,
                dense=True,
                on_change=lambda event: set_query(str(event.control.value)),
            ),
            ft.SegmentedButton(
                segments=[
                    ft.Segment(value="specific", label=f"This encoder ({len(specific)})"),
                    ft.Segment(value="all", label=f"All ({len(entries)})"),
                ],
                selected=[scope],
                allow_empty_selection=False,
                on_change=lambda event: set_scope((event.control.selected or ["specific"])[0]),
            ),
            *(
                [ft.Text(f"No setting matches “{query.strip()}”.", size=FONT_SM, color=muted)]
                if not ordered
                else []
            ),
            ft.Column(controls=rows, spacing=SPACE_SM, key=f"encoder-options-{reset_tick}"),
        ]

    return ft.ExpansionTile(
        title=ft.Text(title, size=FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            f"{len(entries)} settings for {codec} — only the ones you change are applied",
            size=FONT_XS,
            color=muted,
        ),
        expanded=expanded,
        maintain_state=False,
        controls=[
            ft.Container(content=ft.Column(controls=body, spacing=SPACE_SM), padding=SPACE_SM)
        ],
    )


def _reset_all(
    values: OptionValues, set_reset_tick: Callable[[int], None], reset_tick: int
) -> None:
    values.reset()
    set_reset_tick(reset_tick + 1)


# ── muxer (container) options ────────────────────────────────────────────────


@ft.component
def ContainerOptionRows(
    rows: Sequence[Sequence[str]] | None,
    on_change: Callable[[list[list[str]]], None],
    *,
    is_dark: bool = True,
    title: str = "Muxer settings",
) -> ft.Control:
    """Free-form key/value rows for the output muxer.

    av does not enumerate muxer AVOptions (an OutputContainer's ``options`` is
    only what you passed), so the honest surface is a key/value list; FFmpeg
    validates the pair at mux time and a bad one fails the job with its own
    message.
    """
    muted = _muted(is_dark)
    current = [[str(pair[0]), str(pair[1]) if len(pair) > 1 else ""] for pair in (rows or [])]

    def _commit(index: int, *, key: str | None = None, value: str | None = None) -> None:
        updated = [[row[0], row[1]] for row in current]
        if key is not None:
            updated[index][0] = key
        if value is not None:
            updated[index][1] = value
        on_change(updated)

    entries: list[ft.Control] = []
    for index, (key, value) in enumerate(current):
        entries.append(
            ft.Row(
                controls=[
                    ft.TextField(
                        value=key,
                        hint_text="key",
                        dense=True,
                        expand=True,
                        on_submit=lambda e, i=index: _commit(i, key=str(e.control.value)),
                        on_blur=lambda e, i=index: _commit(i, key=str(e.control.value)),
                    ),
                    ft.TextField(
                        value=value,
                        hint_text="value",
                        dense=True,
                        expand=True,
                        on_submit=lambda e, i=index: _commit(i, value=str(e.control.value)),
                        on_blur=lambda e, i=index: _commit(i, value=str(e.control.value)),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        icon_size=18,
                        icon_color=muted,
                        tooltip="Remove",
                        on_click=lambda _e, i=index: on_change(
                            [[row[0], row[1]] for j, row in enumerate(current) if j != i]
                        ),
                    ),
                ],
                spacing=SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    return ft.ExpansionTile(
        title=ft.Text(title, size=FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            "Passed to the muxer as-is" if current else "Optional muxer options",
            size=FONT_XS,
            color=muted,
        ),
        maintain_state=False,
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[
                        *entries,
                        ft.Row(
                            controls=[
                                ft.OutlinedButton(
                                    "Add setting",
                                    icon=ft.Icons.ADD,
                                    on_click=lambda _e: on_change(
                                        [[row[0], row[1]] for row in current] + [["", ""]]
                                    ),
                                ),
                                ft.Text(
                                    "FFmpeg rejects an unknown pair when the job starts.",
                                    size=FONT_XS,
                                    color=muted,
                                ),
                            ],
                            spacing=SPACE_SM,
                            wrap=True,
                        ),
                    ],
                    spacing=SPACE_SM,
                ),
                padding=SPACE_SM,
                border_radius=RADIUS_SM,
            )
        ],
    )
