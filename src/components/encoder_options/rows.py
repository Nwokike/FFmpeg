"""The per-option settings rows: one control per AVOption type."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from typing import Any

import flet as ft

from components.encoder_options.coerce import (  # noqa: F401 — shared type ids
    _CONTROL_WIDTH,
    _MAX_FLAG_CHOICES,
    _MAX_SLIDER_BOUND,
    _MAX_SLIDER_SPAN,
    _SLIDER_DIVISIONS,
    _TYPE_AUDIO_RATE,
    _TYPE_BOOL,
    _TYPE_CHANNEL_LAYOUT,
    _TYPE_COLOR,
    _TYPE_DICT,
    _TYPE_DURATION,
    _TYPE_FLAGS,
    _TYPE_FLOAT,
    _TYPE_INT,
    _TYPE_PIXEL_FMT,
    _TYPE_RATIONAL,
    _TYPE_SAMPLE_FMT,
    _TYPE_STRING,
    _TYPE_VIDEO_RATE,
    OptionValues,
    coerce_option,
    flag_names,
    format_number,
    option_type,
)
from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT
from core.tokens import FONT_SM, FONT_XS, SPACE_SM, SPACE_XS


def _touch() -> None:
    """Push an out-of-band control update (a slider moving its readout)."""
    with contextlib.suppress(Exception):
        ft.context.page.update()


def _muted(is_dark: bool) -> str:
    return TEXT_MUTED_DARK if is_dark else TEXT_MUTED_LIGHT


def _setting_name(spec: dict, *, is_set: bool) -> ft.Control:
    """Option name, marked when the user set it."""
    return ft.Row(
        controls=[
            ft.Text(
                str(spec["name"]),
                size=FONT_SM,
                weight=ft.FontWeight.W_600,
                color=PRIMARY if is_set else None,
            ),
            *([ft.Icon(ft.Icons.EDIT, size=12, color=PRIMARY)] if is_set else []),
        ],
        spacing=SPACE_XS,
        tight=True,
    )


def _help_text(spec: dict, is_dark: bool) -> ft.Control | None:
    help_text = str(spec.get("help") or "").strip()
    if not help_text:
        return None
    return ft.Text(
        help_text,
        size=FONT_XS,
        color=_muted(is_dark),
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def _label_column(spec: dict, *, is_dark: bool, is_set: bool) -> ft.Control:
    help_control = _help_text(spec, is_dark)
    return ft.Column(
        controls=[
            _setting_name(spec, is_set=is_set),
            *([help_control] if help_control is not None else []),
        ],
        spacing=0,
        expand=True,
    )


def _reset_button(name: str, on_reset: Callable[[str], None]) -> ft.Control:
    return ft.IconButton(
        icon=ft.Icons.REFRESH,
        icon_size=16,
        icon_color=PRIMARY,
        tooltip="Reset to default",
        on_click=lambda _e: on_reset(name),
    )


def _bounded(spec: dict) -> tuple[float, float] | None:
    """Declared (min, max) when a slider is meaningful, else None."""
    low, high = spec.get("min"), spec.get("max")
    if low is None or high is None:
        return None
    try:
        lo, hi = float(low), float(high)
    except (TypeError, ValueError):
        return None
    if not hi > lo or hi >= _MAX_SLIDER_BOUND or (hi - lo) > _MAX_SLIDER_SPAN:
        return None
    return lo, hi


def _initial_number(spec: dict, value: str, lo: float, hi: float) -> float:
    raw = value if value not in ("", None) else str(spec.get("default") or "")
    try:
        number = float(raw)
    except (TypeError, ValueError):
        number = lo
    return max(lo, min(hi, number))


def _range_hint(spec: dict) -> str | None:
    low, high = spec.get("min"), spec.get("max")
    if low is None or high is None:
        return None
    try:
        return f"{format_number(float(low))} … {format_number(float(high))}"
    except (TypeError, ValueError):
        return None


def _slider_row(
    spec: dict,
    name: str,
    *,
    value: str,
    is_set: bool,
    is_dark: bool,
    on_change: Callable[[Any], None],
    on_reset: Callable[[str], None],
) -> ft.Control:
    bounds = _bounded(spec)
    if bounds is None:
        return _text_row(
            spec,
            name,
            value=value,
            is_set=is_set,
            is_dark=is_dark,
            on_change=on_change,
            on_reset=on_reset,
        )
    lo, hi = bounds
    start = _initial_number(spec, value, lo, hi)
    readout = ft.Text(
        format_number(start),
        size=FONT_SM,
        weight=ft.FontWeight.W_600,
        color=_muted(is_dark),
    )
    is_int = option_type(spec) in _TYPE_INT
    divisions = _SLIDER_DIVISIONS
    if is_int and (hi - lo) <= _SLIDER_DIVISIONS:
        divisions = max(1, int(hi - lo))

    def _slide(event: ft.ControlEvent) -> None:
        number = float(event.control.value)
        shown = int(number) if is_int else number
        readout.value = format_number(shown)
        on_change(shown)
        _touch()

    return ft.Column(
        controls=[
            ft.Row(
                controls=[
                    _label_column(spec, is_dark=is_dark, is_set=is_set),
                    readout,
                    *([_reset_button(name, on_reset)] if is_set else []),
                ],
                spacing=SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Slider(value=start, min=lo, max=hi, divisions=divisions, on_change=_slide),
        ],
        spacing=0,
    )


def _dropdown_row(
    spec: dict,
    name: str,
    *,
    value: str,
    is_set: bool,
    is_dark: bool,
    on_change: Callable[[Any], None],
    on_reset: Callable[[str], None],
) -> ft.Control:
    help_map = spec.get("choice_help") or {}
    options = [
        ft.DropdownOption(
            key=choice,
            text=f"{choice} — {help_map[choice]}" if help_map.get(choice) else choice,
        )
        for choice in (str(c) for c in (spec.get("choices") or []))
    ]
    return ft.Row(
        controls=[
            _label_column(spec, is_dark=is_dark, is_set=is_set),
            ft.Dropdown(
                value=value or None,
                options=options,
                width=_CONTROL_WIDTH,
                on_select=lambda event: on_change(str(event.control.value)),
            ),
            *([_reset_button(name, on_reset)] if is_set else []),
        ],
        spacing=SPACE_SM,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _text_row(
    spec: dict,
    name: str,
    *,
    value: str,
    is_set: bool,
    is_dark: bool,
    on_change: Callable[[Any], None],
    on_reset: Callable[[str], None],
    hint: str | None = None,
) -> ft.Control:
    type_id = option_type(spec)
    numeric = type_id in (*_TYPE_INT, *_TYPE_FLOAT, _TYPE_RATIONAL)
    return ft.Row(
        controls=[
            _label_column(spec, is_dark=is_dark, is_set=is_set),
            ft.TextField(
                value=value,
                hint_text=hint or (_range_hint(spec) if numeric else None),
                dense=True,
                width=_CONTROL_WIDTH,
                keyboard_type=ft.KeyboardType.NUMBER if numeric else ft.KeyboardType.TEXT,
                on_change=lambda event: on_change(str(event.control.value)),
            ),
            *([_reset_button(name, on_reset)] if is_set else []),
        ],
        spacing=SPACE_SM,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _flags_row(
    spec: dict,
    name: str,
    *,
    value: str,
    is_set: bool,
    is_dark: bool,
    on_change: Callable[[Any], None],
    on_reset: Callable[[str], None],
) -> ft.Control:
    choices = [str(choice) for choice in (spec.get("choices") or [])]
    if not choices or len(choices) > _MAX_FLAG_CHOICES:
        # Too many to tick: type the flag expression instead, with the valid
        # names as the hint ("+cgop+psnr").
        sample = ", ".join(choices[:5]) + (" …" if len(choices) > 5 else "")
        return _text_row(
            spec,
            name,
            value=value,
            is_set=is_set,
            is_dark=is_dark,
            on_change=on_change,
            on_reset=on_reset,
            hint=f"+flag+flag ({sample})" if choices else None,
        )
    selected = set(flag_names(value))
    # The checkbox group owns the current value between re-builds: toggling one
    # box must not lose the others, and on_change reports the whole set.
    local = {"wire": value}

    def _toggle(choice: str, checked: bool) -> None:
        names = set(flag_names(local["wire"]))
        names.discard(choice)
        if checked:
            names.add(choice)
        local["wire"] = "+".join(c for c in choices if c in names)
        on_change(local["wire"])

    return ft.Column(
        controls=[
            ft.Row(
                controls=[
                    _label_column(spec, is_dark=is_dark, is_set=is_set),
                    *([_reset_button(name, on_reset)] if is_set else []),
                ],
                spacing=SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                controls=[
                    ft.Checkbox(
                        label=choice,
                        value=choice in selected,
                        active_color=PRIMARY,
                        on_change=lambda event, choice=choice: _toggle(
                            choice, bool(event.control.value)
                        ),
                    )
                    for choice in choices
                ],
                wrap=True,
                spacing=SPACE_SM,
                run_spacing=SPACE_XS,
            ),
        ],
        spacing=SPACE_XS,
    )


def option_row(
    spec: dict,
    values: OptionValues,
    *,
    is_dark: bool = True,
    on_reset: Callable[[str], None] | None = None,
) -> ft.Control:
    """One settings row: name + help on the left, the right control for its type."""
    name = str(spec["name"])
    is_set = values.is_set(name)
    current = values.get(name)
    type_id = option_type(spec)

    def _changed(raw: Any) -> None:
        values.set_raw(name, coerce_option(spec, raw))

    def _reset(reset_name: str) -> None:
        values.unset(reset_name)
        if on_reset is not None:
            on_reset(reset_name)
        else:
            _touch()

    if type_id == _TYPE_BOOL:
        return ft.Row(
            controls=[
                _label_column(spec, is_dark=is_dark, is_set=is_set),
                ft.Switch(
                    value=current.strip().lower() in ("1", "true", "yes", "on"),
                    active_color=PRIMARY,
                    on_change=lambda event: _changed(bool(event.control.value)),
                ),
                *([_reset_button(name, _reset)] if is_set else []),
            ],
            spacing=SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    if type_id == _TYPE_STRING and (spec.get("choices") or []):
        return _dropdown_row(
            spec,
            name,
            value=current,
            is_set=is_set,
            is_dark=is_dark,
            on_change=_changed,
            on_reset=_reset,
        )

    if type_id == _TYPE_FLAGS:
        return _flags_row(
            spec,
            name,
            value=current,
            is_set=is_set,
            is_dark=is_dark,
            on_change=_changed,
            on_reset=_reset,
        )

    if type_id in (*_TYPE_INT, *_TYPE_FLOAT) and _bounded(spec) is not None:
        return _slider_row(
            spec,
            name,
            value=current,
            is_set=is_set,
            is_dark=is_dark,
            on_change=_changed,
            on_reset=_reset,
        )

    return _text_row(
        spec,
        name,
        value=current,
        is_set=is_set,
        is_dark=is_dark,
        on_change=_changed,
        on_reset=_reset,
    )


def option_controls(
    schema: Sequence[dict] | None,
    values: OptionValues,
    *,
    is_dark: bool = True,
    on_reset: Callable[[str], None] | None = None,
) -> list[ft.Control]:
    """Render one settings row per schema entry, in the order given."""
    return [option_row(spec, values, is_dark=is_dark, on_reset=on_reset) for spec in (schema or [])]


# ── the panel ────────────────────────────────────────────────────────────────

__all__ = ["option_controls", "option_row"]
