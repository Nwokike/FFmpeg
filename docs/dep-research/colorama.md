# colorama 0.4.6 — Complete API Reference

> Package: `colorama` 0.4.6 — cross-platform ANSI color support (Windows shim).
> Ground truth: `<repo>\.venv\Lib\site-packages\colorama` +
> `<repo>\.venv\Lib\site-packages\colorama-0.4.6.dist-info\`
> (METADATA, RECORD, WHEEL, INSTALLER, REQUESTED, licenses/LICENSE.txt).
> App: Flet 1.0 / Python 3.14 / uv venv at `<repo>`.

## Files

Skipping `__pycache__` (6 stale `cpython-314.pyc` files). Installed payload per RECORD (13 entries):

```text
colorama/__init__.py        (266 B, exports only)
colorama/ansi.py            (code generation: Fore/Back/Style/Cursor)
colorama/ansitowin32.py     (StreamWrapper + AnsiToWin32 conversion engine)
colorama/initialise.py      (init/deinit/reinit/just_fix_windows_console/colorama_text)
colorama/win32.py           (ctypes Win32 API bindings)
colorama/winterm.py         (WinTerm state machine + enable_vt_processing)
colorama/tests/__init__.py
colorama/tests/ansi_test.py
colorama/tests/ansitowin32_test.py
colorama/tests/initialise_test.py
colorama/tests/isatty_test.py
colorama/tests/utils.py
colorama/tests/winterm_test.py
colorama-0.4.6.dist-info/{METADATA, RECORD, WHEEL, INSTALLER, REQUESTED, licenses/LICENSE.txt}
```

Notable naming: files are lowercase `ansitowin32.py` / `winterm.py` (no `ansi_to_win32.py`,
`win32vt.py`, `wheel.py`, `docs/` — the assignment's guesses do not exist on disk).
There is no `entry_points.txt`, no `top_level.txt`, no console script.

## Metadata

From `colorama-0.4.6.dist-info/METADATA` (Metadata-Version 2.1):

| Field | Value |
|---|---|
| Name / Version | `colorama` / `0.4.6` (matches `__init__.__version__ = '0.4.6'`) |
| Summary | Cross-platform colored terminal text |
| Home | https://github.com/tartley/colorama |
| License | BSD (classifier `License :: OSI Approved :: BSD License`; file `licenses/LICENSE.txt`, BSD 3-Clause, © Jonathan Hartley 2010, + Arnon Yaari per README) |
| Requires-Python | `!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,>=2.7` — **allows Python 3.14** (upper bound open; classifiers only list up to 3.10 + PyPy, README "tested on 2.7/3.7–3.10", so 3.14 is permitted but not in the package's own CI matrix) |
| Requires-Dist | **none** — zero runtime pins on any Python |
| Provides-Extra | **none** — there is **no `[win]` extra** |
| Entry points | **none** — no `entry_points.txt` in dist-info, therefore **no `pytest11` plugin**, no `colorama` console script. The "pytest plugin capturing output on Windows" hypothesis is **disproven by ground truth** |
| Keywords | ansi,color,colour,crossplatform,terminal,text,windows,xplatform |
| Wheel | `hatchling 1.11.1`, `Root-Is-Purelib: true`, tags `py2-none-any` + `py3-none-any` (single pure wheel) |
| Installer | `uv`; `REQUESTED` is empty (0 bytes) → **transitive, not a direct request** |
| uv.lock pin | `colorama 0.4.6`, sdist `sha256:08695f…201be6e44`, wheel `sha256:4f1d9991…fb285fc6` (Oct 2022 release) |

## Module-by-module API

### `colorama/__init__.py` — public surface

```python
from .initialise import init, deinit, reinit, colorama_text, just_fix_windows_console
from .ansi import Fore, Back, Style, Cursor
from .ansitowin32 import AnsiToWin32

__version__ = "0.4.6"
```

Everything else (`ansi.AnsiFore`, `winterm.WinTerm`, `win32.*`) is importable but not re-exported.

### `colorama/ansi.py` — ANSI code generation (pure, cross-platform, no Win32)

Constants: `CSI = '\033['`, `OSC = '\033]'`, `BEL = '\a'`.

```python
def code_to_chars(code: int) -> str      # CSI + str(code) + 'm', e.g. 31 -> '\x1b[31m'
def set_title(title: str) -> str         # OSC + '2;' + title + BEL
def clear_screen(mode: int = 2) -> str   # CSI + str(mode) + 'J'
def clear_line(mode: int = 2) -> str     # CSI + str(mode) + 'K'
```

`AnsiCodes`: on instantiation converts every public class-attr int into an instance-attr
escape string. `AnsiCursor` methods return raw sequences (never wrapped):

```python
Cursor.UP(n=1)  # '\x1b[{n}A'
Cursor.DOWN(n=1)  # '\x1b[{n}B'
Cursor.FORWARD(n=1)  # '\x1b[{n}C'
Cursor.BACK(n=1)  # '\x1b[{n}D'
Cursor.POS(x=1, y=1)  # '\x1b[{y};{x}H'  (note arg order x,y but emitted y;x)
```

Complete color tables (class attr = SGR number; singleton attr = escape string):

| Fore name | SGR | Back name | SGR | Style name | SGR |
|---|---|---|---|---|---|
| BLACK | 30 | BLACK | 40 | BRIGHT | 1 |
| RED | 31 | RED | 41 | DIM | 2 |
| GREEN | 32 | GREEN | 42 | NORMAL | 22 |
| YELLOW | 33 | YELLOW | 43 | RESET_ALL | 0 |
| BLUE | 34 | BLUE | 44 | | |
| MAGENTA | 35 | MAGENTA | 45 | | |
| CYAN | 36 | CYAN | 46 | | |
| WHITE | 37 | WHITE | 47 | | |
| RESET | 39 | RESET | 49 | | |
| LIGHTBLACK_EX | 90 | LIGHTBLACK_EX | 100 | | |
| LIGHTRED_EX | 91 | LIGHTRED_EX | 101 | | |
| LIGHTGREEN_EX | 92 | LIGHTGREEN_EX | 102 | | |
| LIGHTYELLOW_EX | 93 | LIGHTYELLOW_EX | 103 | | |
| LIGHTBLUE_EX | 94 | LIGHTBLUE_EX | 104 | | |
| LIGHTMAGENTA_EX | 95 | LIGHTMAGENTA_EX | 105 | | |
| LIGHTCYAN_EX | 96 | LIGHTCYAN_EX | 106 | | |
| LIGHTWHITE_EX | 97 | LIGHTWHITE_EX | 107 | | |

Singletons: `Fore = AnsiFore()`, `Back = AnsiBack()`, `Style = AnsiStyle()`, `Cursor = AnsiCursor()`.
Example:

```python
from colorama import Fore, Back, Style

print(Fore.RED + "some red text")
print(Back.GREEN + "and with a green background")
print(Style.DIM + "and in dim text")
print(Style.RESET_ALL + "back to normal now")
print("\033[31m" + "same red, hand-rolled")
```

### `colorama/initialise.py` — init / deinit / just_fix_windows_console

```python
def init(autoreset=False, convert=None, strip=None, wrap=True) -> None
def deinit() -> None
def reinit() -> None
def just_fix_windows_console() -> None
@contextlib.contextmanager
def colorama_text(*args, **kwargs)  # init(*args, **kwargs); yield; deinit() in finally
def reset_all() -> None              # AnsiToWin32(orig_stdout).reset_all(), atexit-registered
def wrap_stream(stream, convert, strip, autoreset, wrap) -> stream
```

`init` kwargs — exactly when each applies:

- `autoreset=False`: if True, every `write()` ends with a reset (`reset_all()`). Applies on
  **all platforms** (it forces `should_wrap()` True even on Linux). Convenience so you don't
  re-emit `Style.RESET_ALL` after each print.
- `convert=None`: override "translate ANSI → Win32 calls". Default (`None`) resolves to
  `need_conversion and have_tty` where `need_conversion = conversion_supported and not
  system_has_native_ansi`. Practically: True only on **old Windows consoles without native VT**.
  On Win10+ with VT enabled, or on POSIX, default is False/None-effect.
- `strip=None`: override "delete ANSI sequences from output". Default resolves to
  `need_conversion or not have_tty` — i.e. strips when piped/redirected **or** on legacy
  Windows. This is the heuristic the docs warn is "not particularly clever".
- `wrap=True`: replace `sys.stdout`/`sys.stderr` with `AnsiToWin32(...).stream` proxies.
  `wrap=False` **plus any other arg True raises `ValueError('wrap=False conflicts with any
  other arg=True')`**. With `wrap=False`, stdout/stderr are untouched; do cross-platform
  output manually via `AnsiToWin32(sys.stderr).stream` (see METADATA Usage example).

Lifecycle details: `init` snapshots `sys.stdout/stderr` into `orig_stdout/orig_stderr`,
installs wrapped versions, registers `reset_all` with `atexit` once (`atexit_done` flag).
`deinit` restores originals. `reinit` re-installs the previously built wrappers (cheaper than
`init`). Calling `init` twice stacks wrappers — **not safe** (double conversion/stripping).

`just_fix_windows_console()` (added 0.4.6, **the recommended entry point**):

- No-op on non-Windows (`sys.platform != "win32"` → return).
- No-op if already fixed (`fixed_windows_console`) or if `init()` already wrapped something.
- Otherwise constructs `AnsiToWin32(sys.stdout/stderr, convert=None, strip=None,
  autoreset=False)`; the constructor **side-effects `enable_vt_processing(fd)`** (sets
  `ENABLE_VIRTUAL_TERMINAL_PROCESSING` on Win10+). Only replaces the stream if
  `new.convert` is truthy (legacy console). Everywhere else it just flips the VT flag
  and returns. Safe to call repeatedly, safe on POSIX, safe under redirection.

```python
from colorama import just_fix_windows_console

just_fix_windows_console()  # preferred one-liner at program top

from colorama import colorama_text, Fore

with colorama_text(autoreset=True):
    print(Fore.GREEN + "scoped color, auto-reset, unwrapped on exit")
```

### `colorama/ansitowin32.py` — the conversion engine

```python
class StreamWrapper:           # transparent proxy; only write() is intercepted
    def __init__(self, wrapped, converter)
    def write(self, text)      # delegates to converter.write
    def isatty(self)           # PYCHARM_HOSTED special-case; missing isatty -> False
    @property closed
    # __getattr__ proxies everything else; __enter__/__exit__ forwarded explicitly

class AnsiToWin32:
    ANSI_CSI_RE = re.compile('\001?\033\\[((?:\\d|;)*)([a-zA-Z])\002?')
    ANSI_OSC_RE = re.compile('\001?\033\\]([^\a]*)(\a)\002?')
    def __init__(self, wrapped, convert=None, strip=None, autoreset=False)
    def should_wrap(self) -> bool   # self.convert or self.strip or self.autoreset
    def get_win32_calls(self) -> dict
    def write(self, text) -> None
    def reset_all(self) -> None
    def write_and_convert(self, text) -> None
    def write_plain_text(self, text, start, end) -> None
    def convert_ansi(self, paramstring, command) -> None
    def extract_params(self, command, paramstring) -> tuple
    def call_win32(self, command, params) -> None
    def convert_osc(self, text) -> str
    def flush(self) -> None
```

Constructor resolution (the heart of the "when does colorama matter" question):

```python
on_windows = os.name == 'nt'
conversion_supported = on_windows and winapi_test()   # real console handles exist
fd = wrapped.fileno()  # except -> -1
system_has_native_ansi = not on_windows or enable_vt_processing(fd)
have_tty = not self.stream.closed and self.stream.isatty()
need_conversion = conversion_supported and not system_has_native_ansi
strip   = need_conversion or not have_tty   if strip is None
convert = need_conversion and have_tty      if convert is None
```

So on this project's typical environments: Git Bash / Windows Terminal / VS Code terminal
(VT-capable) → `convert=False`, `strip=False` on a tty → passthrough. Piped to a file or CI
log capture (not a tty) → `strip=True` → colors vanish unless you force `strip=False`.
Legacy `cmd.exe` without VT → `convert=True` → Win32 calls.

`write()`: if `strip or convert` → `write_and_convert` (regex-split CSI sequences, emit plain
text, dispatch SGR/cursor/erase via `call_win32`), else raw passthrough + flush; then
`reset_all()` if `autoreset`. `reset_all()`: in convert mode issues Win32 reset (`call_win32('m',
(0,))`); else if not stripping writes `Style.RESET_ALL` to the stream. `extract_params`
defaults: `J/K/m` → `(0,)`, `A/B/C/D` → `(1,)`, `H/f` → pad to 2 with 1s. `call_win32`
handles `m` (color/style via `win32_calls` map), `J` (erase_screen), `K` (erase_line),
`H/f` (set_cursor_position), `A/B/C/D` (cursor_adjust). `convert_osc` deletes OSC sequences
from text and forwards genuine `OSC 0/2;title BEL` to `winterm.set_title`. Recognized SGR set
is exactly the Fore/Back/Style table above plus cursor/erase; **all other `ESC[…<letter>`
forms are silently stripped on Windows**; non-CSI/OSC forms are ignored entirely.

### `colorama/win32.py` — ctypes bindings (Windows only, graceful elsewhere)

Import guard: `windll = LibraryLoader(ctypes.WinDLL)` else `windll = None` with no-op
`SetConsoleTextAttribute` / `winapi_test` lambdas. Constants `STDOUT = -11`, `STDERR = -12`,
`ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004`. Struct `CONSOLE_SCREEN_BUFFER_INFO`.
Functions (all no-ops off-Windows): `winapi_test()` (any of stdout/stderr handles valid),
`GetConsoleScreenBufferInfo(stream_id)`, `SetConsoleTextAttribute(stream_id, attrs)`,
`SetConsoleCursorPosition(stream_id, position, adjust=True)` (1-based ANSI → 0-based Win32 +
viewport scroll adjust), `FillConsoleOutputCharacter/Attribute`, `SetConsoleTitle`,
`GetConsoleMode/SetConsoleMode` (raise `ctypes.WinError` on failure).

### `colorama/winterm.py` — terminal state + VT enabler

```python
class WinColor:  BLACK=0 BLUE=1 GREEN=2 CYAN=3 RED=4 MAGENTA=5 YELLOW=6 GREY=7
class WinStyle:  NORMAL=0x00 BRIGHT=0x08 BRIGHT_BACKGROUND=0x80
class WinTerm:
    def __init__()                       # snapshots console attrs as defaults; _light=0
    def get_attrs / set_attrs(value)
    def reset_all(on_stderr=None)
    def fore(fore=None, light=False, on_stderr=False)
    def back(back=None, light=False, on_stderr=False)
    def style(style=None, on_stderr=False)
    def set_console(attrs=None, on_stderr=False)
    def get_position(handle)             # 0-based -> 1-based
    def set_cursor_position(position=None, on_stderr=False)
    def cursor_adjust(x, y, on_stderr=False)
    def erase_screen(mode=0, on_stderr=False)   # 0 cursor→end, 1 cursor→start, 2 all + home
    def erase_line(mode=0, on_stderr=False)     # 0 cursor→end, 1 cursor→start, 2 whole line
    def set_title(title)
def enable_vt_processing(fd) -> bool     # GetConsoleMode|ENABLE_VIRTUAL_TERMINAL_PROCESSING
```

Notes: `LIGHT_EX` colors are emulated by borrowing the `BRIGHT` bit, tracked separately in
`_light` so `Style.BRIGHT` and light colors don't clobber each other. `DIM` maps to
`WinStyle.NORMAL` — **dim renders as normal on old Windows** (documented screenshot caveat).

### Pytest plugin behavior

**None.** There is no `entry_points.txt`, no `pytest11` group, no hook. Colorama does not
capture, filter, or recolor pytest output by itself; pytest on Windows simply emits ANSI
(via pygments terminal formatting) and relies on the console (or an explicit
`just_fix_windows_console()` / `init()` call, or native VT) to render it. No interaction
with this suite's log capture beyond the generic tty heuristic: under `pytest -s`, captured
vs live streams change `isatty()`, which changes default `strip` if someone wraps streams.

## App usage & correctness

Direct usage: **zero**. `grep -rni "colorama|just_fix_windows|AnsiToWin32|Fore\.|Back\.|Style\."`
over `src/ tests/ tools/ pyproject.toml` returns no colorama import; the only `Fore.`-like
hits are English words ("fallback", "before") in engine_service/test files. Neither
`tools/admob.py` (click CLI) nor `tools/make_icons.py` (3 `print()` status lines) nor any
`src/` module touches colorama. `conftest.py` does not init/deinit it.

Why it is installed (transitive, Windows-conditional — chain):

1. `pytest 9.1.1` — `Requires-Dist: colorama>=0.4; sys_platform == "win32"`. `pyproject.toml`
   directly depends on `pytest>=9.1.1`, so on this Windows dev box uv installs colorama 0.4.6.
2. `qrcode 8.2` — `Requires-Dist: colorama; sys_platform == "win32"` (second installer; qrcode
   itself is a transitive dep in this venv, not a direct pyproject dep).
3. NOT rich: `rich 15.0.0` dist-info lists only `markdown-it-py`, `pygments`, jupyter extra —
   **no colorama requirement** (rich uses its own Windows console handling).
4. NOT click: `click 8.5.0` dist-info has **no colorama requirement** (the colorama pin existed
   only in click 7.x; click 8+ vendors its own ANSI handling).
5. NOT active: `pygments 2.21.0` offers `colorama>=0.4.6; extra == 'windows-terminal'`, which
   is not enabled here.

Correctness assessment: (a) chain is healthy — pinned 0.4.6 satisfies both `>=0.4` markers on
`sys_platform == 'win32'`; on Linux/macOS CI the markers exclude it entirely. (b) No misuse —
nothing to misuse since nothing imports it. (c) Pytest's own Windows coloring works without
any app-side init because modern Windows consoles have native VT; on legacy consoles pytest
users would need an explicit init, but that is outside this repo's code.

Git Bash / CI nuance: Git Bash (mintty) is not a Win32 console — `winapi_test()` fails, so
colorama defaults to passthrough and the terminal renders ANSI itself. Piped CI logs
(`isatty()` False) default to `strip=True` under `init()`, which is why CI logs sometimes
lose color while local runs keep it.

## Underused APIs to adopt

Recommendation for v1: **do not adopt raw colorama for app/tooling output — use `rich`
(already installed, v15.0.0) or `click.echo`/`click.secho`**. Reasons: richer API, no
`init`/`deinit` discipline, handles Windows VT itself, consistent with the existing
`tools/admob.py` click CLI. Concrete picks:

- `tools/admob.py check-ids` — today plain `click.echo`; colorize verdicts with
  `click.secho('IDs OK', fg='green')` / `fg='red'` instead of importing Fore. Zero new deps.
- `tools/make_icons.py` — 3 plain `print()` lines; either leave uncolored (correct for a
  rarely-run dev script) or switch to `rich.console.Console().print('[green]…[/]')`.
- Any future `print()` diagnostics in `tools/` — prefer `rich.print` over manual
  `Fore.RED + … + Style.RESET_ALL`, which leaks color on exceptions without autoreset.
- If a minimal stdlib-only script must emit ANSI without rich/click: call
  `just_fix_windows_console()` once at the top (idempotent, POSIX-safe) — never `init()`.
  Reserve `init(autoreset=True)` for legacy-console-only scripts, and `colorama_text()` for
  scoped coloring in tests/demos. `Cursor.POS` / `clear_screen` / `set_title` cover the only
  gaps rich doesn't already fill (cursor choreography, title setting).
- Test suite: no change needed. Do not wrap `sys.stdout` in `conftest.py`; pytest capture +
  colorama stripping heuristics interact badly (captured streams are not ttys).

## Gotchas

1. `init()` is not idempotent — double `init()` double-wraps stdout (nested
   `StreamWrapper`s, stripped twice, `deinit()` only peels one layer). `just_fix_windows_console()`
   is the safe one.
2. `init(wrap=False)` + any of `autoreset/convert/strip` truthy → immediate `ValueError`.
3. Default `strip` eats your colors when piped: any `init()`-wrapped run redirected to a file
   or captured by CI comes out monochrome. Force `init(strip=False)` only if you control the
   consumer.
4. `convert` only fires on legacy Windows tty without native VT. On Win10+, Git Bash, VS Code
   terminal, and all POSIX systems it is a passthrough — test Windows color bugs on a real
   legacy console or mock `winapi_test`/`enable_vt_processing`.
5. `DIM` == normal on old Windows; `LIGHT_EX` is faked with the BRIGHT bit. Don't rely on
   subtle brightness distinctions for error-vs-warning severity.
6. Unrecognized ANSI (256-color `38;5;…`, truecolor `38;2;…`, scroll regions, etc.) is
   **silently stripped** in convert/strip mode — rich/pygments output past the SGR table
   degrades on legacy consoles without warning.
7. `atexit.reset_all` touches console handles at interpreter exit; with closed/detached
   stdout it guards via `AnsiToWin32 is not None` + `stream.closed` checks, but expect no
   color reset if the interpreter dies hard.
8. `StreamWrapper` proxies attributes but `closed`/`isatty` have custom logic; code doing
   `isinstance(sys.stdout, io.TextIOBase)` or poking `.buffer` after `init()` can break —
   another reason to prefer `just_fix_windows_console()`.
9. `sys.stdout = None` (pythonw) is handled (wrappers stay None) — but most color code isn't.
10. Version age: 0.4.6 is Oct 2022. It works on 3.14 per `Requires-Python`, yet its own
    classifiers/CI stop at 3.10 — treat Windows-console behavior on 3.14 as
    community-tested, not vendor-tested. No security surface beyond console writes, but pin
    stays because pytest/qrcode markers demand it on Windows.
