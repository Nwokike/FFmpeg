"""Real ffmpeg syntax → a validated job (FFmpeg libraries via PyAV, no binary)."""

from services.command_parser.plan import (
    OpPlan,
    help_text,
    parse_command,
)
from services.command_parser.primitives import CommandError
from services.command_parser.tokenize import tokenize

__all__ = ["CommandError", "OpPlan", "help_text", "parse_command", "tokenize"]
