"""Command-line tokenization (quotes, backslash paths)."""

from __future__ import annotations

from services.command_parser.plan import _refuse


def tokenize(command: str) -> list[str]:
    """Split on whitespace, honour quotes, NEVER mangle backslash paths.

    ``shlex`` in POSIX mode eats ``C:\\media\\in.mp4`` backslashes — this
    tokenizer keeps every byte inside quotes, only stripping the quotes.
    Empty quoted strings (``-i ""``) are refused, not silently bound to the
    next token; backslash escapes are NOT processed (quote the whole path).
    """
    tokens: list[str] = []
    buf: list[str] = []
    buf_has_content = False
    quote: str | None = None
    for ch in command.strip():
        if quote:
            if ch == quote:
                quote = None
                buf_has_content = True
            else:
                buf.append(ch)
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if buf or buf_has_content:
                if not buf and buf_has_content:
                    _refuse("empty quoted string is not a valid path or value")
                tokens.append("".join(buf))
                buf = []
                buf_has_content = False
        else:
            buf.append(ch)
    if quote:
        _refuse(f"unterminated {quote} quote in command")
    if buf or buf_has_content:
        if not buf and buf_has_content:
            _refuse("empty quoted string is not a valid path or value")
        tokens.append("".join(buf))
    return tokens

