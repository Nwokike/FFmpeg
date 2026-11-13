"""Advanced encoder/muxer settings — every option the installed wheel exposes.

The probe measures, for every verified encoder, the complete AVOption list
(generic + private) with type, choices, default, min/max and help text
(`core.engine_probe.EngineProbe.encoder_option_schema`). This module turns that
schema into real controls, so every setting the wheel's encoders actually have
is findable and settable — whatever the wheel ships, whatever av version, with
no per-codec tables anywhere in the app.

Measured against the installed av wheel, and load-bearing for the design:

- Option values travel as **strings**. av rejects anything else
  (`TypeError: Argument 'value' has incorrect type`), so ``OptionValues`` stores
  wire strings and coerces at the control boundary.
- Only **touched** options are sent. The schema's declared default is shown in
  the UI but never pushed, so an untouched setting keeps FFmpeg's own default
  (which is not always the AVOption's nominal default).
- 109 of the option names in this wheel are declared by *every* encoder (the
  generic AVOptions). The panel opens on the encoder-specific short list and
  keeps the shared ones behind "All".
- Flet's TextField/Dropdown have no ``tooltip`` kwarg; help text rides on the
  option row instead (name + one-line help), which is what the design uses.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import flet as ft

from core.theme import PRIMARY, TEXT_MUTED_DARK, TEXT_MUTED_LIGHT
from core.tokens import FONT_SM, FONT_XS, RADIUS_SM, SPACE_SM, SPACE_XS

# AVOption type ids (av.codec.context.OptionType, as the probe stores them).
_TYPE_FLAGS = 1
_TYPE_INT = (2, 3, 10)
_TYPE_FLOAT = (4, 5)
_TYPE_STRING = 6
_TYPE_RATIONAL = 7
_TYPE_DICT = 9
_TYPE_PIXEL_FMT = 12
_TYPE_SAMPLE_FMT = 13
_TYPE_AUDIO_RATE = 14
_TYPE_VIDEO_RATE = 15
_TYPE_DURATION = 16
_TYPE_COLOR = 17
_TYPE_BOOL = 18
_TYPE_CHANNEL_LAYOUT = 19

# Above this many choices a flags option renders as a text field: a 60-checkbox
# wall is worse than typing "+cgop".
_MAX_FLAG_CHOICES = 24
# A slider only makes sense when the declared range is usable; the huge ranges
# FFmpeg uses for bitrates (0 … 9.2e18) stay text fields.
_MAX_SLIDER_SPAN = 1_000_000
_MAX_SLIDER_BOUND = 1e7
_SLIDER_DIVISIONS = 100
# Trailing control width: leaves the phone's label column room for the option
# name and its one-line help.
_CONTROL_WIDTH = 170


@dataclass
class OptionValues:
    """Touched option values for one codec, in av's wire format (str → str).

    The caller owns the instance (one per codec); the panel mutates it in place
    and the screen reads :meth:`as_dict` when the job starts.
    """

    codec: str
    values: dict[str, str] = field(default_factory=dict)

    def get(self, name: str, default: str = "") -> str:
        value = self.values.get(str(name))
        return default if value is None else str(value)

    def is_set(self, name: str) -> bool:
        return str(name) in self.values

    def set(self, name: str, value: Any) -> None:
        """Coerce and store one control value as the wire string av expects."""
        self.values[str(name)] = "" if value is None else coerce_option({}, value)

    def set_raw(self, name: str, wire: str) -> None:
        """Store an already-coerced wire string."""
        self.values[str(name)] = str(wire)

    def unset(self, name: str) -> None:
        self.values.pop(str(name), None)

    def as_dict(self) -> dict[str, str]:
        """The option dict for the engine: touched keys only."""
        return {str(k): str(v) for k, v in self.values.items() if str(v) != ""}

    def reset(self) -> None:
        self.values.clear()

    def __len__(self) -> int:
        return len(self.as_dict())


# ── coercion ─────────────────────────────────────────────────────────────────


def option_type(spec: dict) -> int | None:
    """The AVOption type id, or None when the schema entry has no usable type."""
    try:
        return int(spec.get("type"))
    except (TypeError, ValueError):
        return None


def format_number(value: float) -> str:
    """Compact readout for a numeric option: 23, 0.5, 1e+06."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return f"{number:g}"


def coerce_option(spec: dict, raw: Any) -> str:
    """Coerce one control value to the wire string av accepts.

    av's option dict wants ``str`` for every type; ints must not carry a decimal
    point (FFmpeg parses the whole token) and bools are ``1``/``0``.
    """
    if isinstance(raw, (list, tuple, set, frozenset)):
        return "+".join(str(item).lstrip("+-") for item in raw if str(item).strip())
    if isinstance(raw, bool):
        return "1" if raw else "0"
    type_id = option_type(spec)
    text = str(raw).strip()
    if type_id == _TYPE_BOOL:
        return "1" if text.lower() in ("1", "true", "yes", "on") else "0"
    if type_id in _TYPE_INT:
        try:
            return str(int(float(text)))
        except (TypeError, ValueError):
            return text
    if type_id in _TYPE_FLOAT:
        try:
            return f"{float(text):g}"
        except (TypeError, ValueError):
            return text
    if type_id == _TYPE_FLAGS:
        return "+".join(part.strip() for part in text.replace(",", "+").split("+") if part.strip())
    return text


def flag_names(value: Any) -> list[str]:
    """Selected flag names from a wire value (empty for a raw bitfield)."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(item).lstrip("+-") for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text or text.lstrip("+-").lower().startswith("0x"):
        return []
    return [part.strip() for part in text.replace(",", "+").split("+") if part.strip()]


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


__all__ = [
    "ContainerOptionRows",
    "EncoderOptionPanel",
    "OptionValues",
    "coerce_option",
    "flag_names",
    "format_number",
    "option_controls",
    "option_row",
    "option_type",
]
