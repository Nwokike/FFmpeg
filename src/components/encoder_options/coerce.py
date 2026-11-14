"""AVOption wire-format coercion and per-codec value stores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
