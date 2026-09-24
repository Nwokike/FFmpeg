# rich 15.0.0 — Complete API Reference

> Package purpose: terminal rendering — rich text, tables, progress bars,
> syntax highlighting, Markdown, tracebacks, and more, for CLIs and
> developer tooling. By Will McGugan / Textualize. This app's dependency is
> **transitive only** (see Metadata); no app module imports it directly.

---

## Files

Package dir (read-only ground truth):
`<repo>\.venv\Lib\site-packages\rich`
— **77 top-level `.py` files** (~26,600 lines total, incl. the 3,610-line
`_emoji_codes.py` data table), plus one subpackage dir `_unicode_data/`
and `py.typed` (the distribution ships type hints). No `context.py` and no
`pixels.py` exist in 15.0.0 — those two names from the assignment brief are
**absent** (there is also no `rich.pixels` / `rich.context` importable
module; anything referencing them would `ImportError`).

Largest files by lines: `console.py` 2698 · `progress.py` 1716 ·
`text.py` 1363 · `pretty.py` 1016 · `table.py` 1015 · `syntax.py` 988 ·
`traceback.py` 924 · `markdown.py` 802 · `style.py` 796 · `segment.py` 780 ·
`_win32_console.py` 661 · `color.py` 621 · `_spinners.py` 482 ·
`box.py` 474 · `layout.py` 442 · `live.py` 404 · `prompt.py` 400 ·
`cells.py` 352 · `align.py` 320 · `panel.py` 317 · `logging.py` 305.

Full module list (`__pycache__` excluded): `__init__`, `__main__`,
`_emoji_codes`, `_emoji_replace`, `_export_format`, `_extension`, `_fileno`,
`_inspect`, `_log_render`, `_loop`, `_null_file`, `_palettes`, `_pick`,
`_ratio`, `_spinners`, `_stack`, `_timer`, `_win32_console`, `_windows`,
`_windows_renderer`, `_wrap`, `abc`, `align`, `ansi`, `bar`, `box`, `cells`,
`color`, `color_triplet`, `columns`, `console`, `constrain`, `containers`,
`control`, `default_styles`, `diagnose`, `emoji`, `errors`, `file_proxy`,
`filesize`, `highlighter`, `json`, `jupyter`, `layout`, `live`,
`live_render`, `logging`, `markdown`, `markup`, `measure`, `padding`,
`pager`, `palette`, `panel`, `pretty`, `progress`, `progress_bar`,
`prompt`, `protocol`, `region`, `repr`, `rule`, `scope`, `screen`,
`segment`, `spinner`, `status`, `style`, `styled`, `syntax`, `table`,
`terminal_theme`, `text`, `theme`, `themes`, `traceback`, `tree`
(77 files; `_unicode_data/` holds versioned unicode width tables).

`__main__.py` (245 lines) powers `python -m rich` (self-demo: tables,
progress, markdown, syntax, tracebacks) and `python -m rich.spinner`
(spinner gallery), plus a `print`/`inspect` CLI shim.

## Metadata

From `rich-15.0.0.dist-info/METADATA` (installer: `uv`, wheel built by
`poetry-core 2.3.1`, tag `py3-none-any`, `Root-Is-Purelib: true`):

| Field | Value |
|---|---|
| Name / Version | `rich` / `15.0.0` |
| Summary | Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal |
| License | **MIT** (`licenses/LICENSE`; `License-File: LICENSE`) |
| Author | Will McGugan <willmcgugan@gmail.com> |
| Requires-Python | `>=3.9.0` (classifiers list 3.9–3.14; this env runs 3.14.7) |
| Requires-Dist (mandatory) | `markdown-it-py (>=2.2.0)`, `pygments (>=2.13.0,<3.0.0)` — **unpinned upper bound on markdown-it-py** |
| Requires-Dist (extra) | `ipywidgets (>=7.5.1,<9)` for `extra == "jupyter"` only |
| Status | Development Status 5 — Production/Stable; `Typing: Typed` |

Dist-info contains: `INSTALLER` (`uv`), `METADATA`, `RECORD`, `REQUESTED`
(empty — not a directly requested dep), `WHEEL`, `licenses/`. **No
`entry_points.txt`** — rich installs no console scripts.

Dependency position in *this* project (from `uv.lock` + `pyproject.toml`):

- `pyproject.toml` `[project] dependencies` does **NOT** list rich. It is
  **transitive only**, pulled by three packages (`uv.lock` lines ~211,
  ~338, ~352 → §757): `flet-cli 1.0.0` (dev group), `flet-desktop 1.0.0`
  (dev group), and `cookiecutter 2.7.1` (flet-cli's own dep).
- Pinned in lock: `rich 15.0.0` sdist + `rich-15.0.0-py3-none-any.whl`
  (sha256 `33bd4ef7…`). Its locked transitive deps: `markdown-it-py`,
  `pygments` (plus `ipywidgets` only under the jupyter extra — not
  installed here).
- Consequence for v1.0: rich ships in the **dev/APK-build environment**
  (flet-cli renders its own CLI output with it) but is **not a runtime app
  dependency** — `import rich` inside `src/` would work on desktop today
  yet break the packaged mobile build unless rich is promoted to
  `[project] dependencies`. Any "adopt rich" recommendation below implies
  that one-line promotion.

## Module-by-module API

Conventions used below: `RenderableType` = `str | ConsoleRenderable |
RichCast`; `TextType` = `str | Text`; `StyleType` = `str | Style`.
Every renderable implements `__rich_console__(console, options)` and most
implement `__rich_measure__`; custom app renderables can do the same (see
`protocol.py`: `is_renderable(obj)`, `rich_cast(obj)`).

### `rich.__init__` — top-level shortcuts

`__all__ = ["get_console", "reconfigure", "print", "inspect",
"print_json"]`.

```python
def get_console() -> Console          # process-global lazy Console
def reconfigure(*args, **kwargs) -> None   # replace global console attrs
def print(*objects, sep=" ", end="\n",
          file: IO[str] | None = None, flush: bool = False) -> None
    # builtin-print-compatible; markup+emoji+highlighting ON; flush is a no-op
def print_json(json: str | None = None, *, data: Any = None,
               indent: int | str | None = 2, highlight: bool = True,
               skip_keys: bool = False, ensure_ascii: bool = False,
               check_circular: bool = True, allow_nan: bool = True,
               default: Callable | None = None, sort_keys: bool = False) -> None
def inspect(obj, *, console=None, title=None, help=False, methods=False,
            docs=True, private=False, dunder=False, sort=True,
            all=False, value=True) -> None
```

`print()` semantics: same signature as builtin `print`, but each object is
rendered through the global `Console` — so `"[bold]hi[/]"` markup,
`":thumbs_up:"` emoji, and automatic pretty-printing/highlighting of
containers apply. `file=` wraps that file in a throwaway `Console`.
Example: `from rich import print; print("[bold magenta]Hello[/]", {"a": 1})`.

### `rich.console.Console` — the core object

```python
Console(*, color_system: "auto"|"standard"|"256"|"truecolor"|"windows"|None = "auto",
        force_terminal=None, force_jupyter=None, force_interactive=None,
        soft_wrap=False, theme: Theme | None = None, stderr=False,
        file: IO[str] | None = None, quiet=False,
        width: int | None = None, height: int | None = None,
        style: StyleType | None = None, no_color: bool | None = None,
        tab_size=8, record=False, markup=True, emoji=True,
        emoji_variant: "emoji"|"text"|None = None, highlight=True,
        log_time=True, log_path=True, log_time_format="[%X]",
        highlighter: HighlighterType | None = ReprHighlighter(),
        legacy_windows=None, safe_box=True,
        get_datetime=None, get_time=None)   # -> Console
```

Key methods (full list incl. properties: `file`, `color_system`,
`encoding`, `is_terminal`, `is_dumb_terminal`, `options`, `size`,
`width`, `height`; `bell()`, `clear(home=True)`, `line(count=1)`,
`show_cursor(show=True)`, `set_alt_screen(enable=True)`,
`set_window_title(title)`, `control(*Control)`, `measure()`,
`render()`, `render_lines()`, `render_str()`, `get_style()`):

```python
console.print(*objects, sep=" ", end="\n", style=None, justify=None,
              overflow=None, no_wrap=None, emoji=None, markup=None,
              highlight=None, width=None, height=None, crop=True,
              soft_wrap=None, new_line_start=False) -> None
console.log(*objects, sep=" ", end="\n", style=None, justify=None,
            emoji=None, markup=None, highlight=None,
            log_locals=False) -> None   # print + time + caller file:line
console.rule(title="", *, characters="─", style="rule.line", align="center")
console.print_json(json=None, *, data=None, indent=2, highlight=True, ...) -> None
console.status(status, *, spinner="dots", spinner_style="status.spinner",
               speed=1.0, refresh_per_second=12.5) -> Status  # context manager
console.screen(hide_cursor=True, style=None) -> ScreenContext  # alt-screen
console.pager(pager=None, styles=False, links=False) -> PagerContext
console.capture() -> Capture          # with-block; .get() -> str
console.begin_capture() / console.end_capture() -> str
console.push_theme(theme, *, inherit=True) / pop_theme() / use_theme(theme) -> ThemeContext
console.export_text(*, clear=True, styles=False) -> str
console.save_text(path, *, clear=True, styles=False) -> None
console.export_html(*, theme=None, clear=True, ...) -> str   # needs record=True at construction for full history
console.save_html(path, ...) / console.export_svg(...) / console.save_svg(path, title="Rich", ...)
```

Helpers in module: `group(fit=True)` decorator → `Group`; `Capture`
(`.get()`); `ScreenContext.update(*renderables, style=None)`;
`RenderHook` ABC (`.process_renderables(renderables)`); thread-local theme
stack; `detect_legacy_windows()`.

### `rich.markup` — markup syntax

Tags are BBCode-like: `[bold]`, `[italic]`, `[underline]`, `[strike]`,
`[red]` / `[on blue]` / `[#ff0000]` / `[color(255,0,0)]`, `[link=URL]…[/]`,
`[/]` closes. Literal brackets need `rich.markup.escape(text)`.

```python
def escape(markup: str) -> str            # backslash-escape tags
def render(markup: str, style="", emoji=True, emoji_variant=None) -> Text
class Tag(NamedTuple): name: str | None; parameters: str | None  # .markup property
```

Gotcha that matters for this app: any user-typed or engine-emitted text
containing `[…]` (ffmpeg filtergraphs like `scale[w]`, stream specifiers
`0:v:0`) is parsed as markup by `console.print` and raises
`MarkupError` on bad tags — always `escape()` untrusted text or call
`print(..., markup=False)`.

### `rich.text.Text`

The styled-string workhorse (`Text.__init__(text="", style="",
justify=None, overflow=None, no_wrap=None, end="\n", tab_size=8)`).
Constructors: `Text.from_markup(str, style="", emoji=True, ...)`,
`Text.from_ansi(str, ...)`, `Text.styled(text, style)`,
`Text.assemble(*parts)` where parts are `str | Text | (str, style)`.
Mutation/query highlights: `.append(text, style=None)`,
`.append_text()`, `.stylize(style, start=0, end=None)`,
`.highlight_regex(pattern, style=None)`,
`.highlight_words(words, style)`, `.wrap(console, width, ...)`,
`.truncate(max_width, ...)`, `.pad/pad_left/pad_right()`,
`.align()`, `.split(separator)`, `.divide(offsets)`, `.blank_copy()`,
`.copy()`, `.join(lines)`, `.render(console, end="")`,
`.get_style_at_offset(console, offset)`, `.markup` property (re-emit as
markup string), `.cell_len`, `.detect_indentation()`,
`.with_indent_guides()`. `Span` NamedTuple: `.split(offset)`,
`.move(offset)`, `.right_crop(offset)`, `.extend(cells)`.

### `rich.style.Style` / `rich.color.Color` / themes

`Style(color=None, bgcolor=None, bold=None, dim=None, italic=None,
underline=None, blink=None, blink2=None, reverse=None, conceal=None,
strike=None, underline2=None, frame=None, encircle=None, overline=None,
link=None, meta=None)` — all-`None` = null style. Factories:
`Style.parse("bold red on black")`, `Style.combine(styles)`,
`Style.chain(*styles)`, `Style.from_color(color, bgcolor)`,
`Style.null()`, `.normalize()`, `.pick_first(*values)`; instance ops
`.copy()`, `.without_color()`, `.render(text, color_system=TRUECOLOR)`,
`.get_html_style(theme=None)`, `.test(text=None)` (prints a swatch),
`+` combines. `colorsys`: `Color.parse("red" | "#ff0000" |
"color(255)" | "rgb(1,2,3)")`, `Color.from_ansi(n)`,
`Color.from_triplet()`, `Color.from_rgb()`, `.get_ansi_codes()`,
`.downgrade(system)`, `.get_truecolor(theme)`; `ColorSystem`
(`STANDARD/EIGHT_BIT/TRUECOLOR/WINDOWS`), `ColorType`
(`DEFAULT/STANDARD/EIGHT_BIT/TRUECOLOR/WINDOWS`); helpers `parse_rgb_hex`,
`blend_rgb`. `default_styles.DEFAULT_STYLES` defines every themeable name
(`logging.level.*`, `rule.line`, `table.header`, `bar.*`,
`progress.*`, `repr.*`, `traceback.*`, …). `Theme(styles_dict,
inherit=True)` + `Theme.from_file()` / `Theme.read(path)` (INI config);
`themes.DEFAULT = Theme(DEFAULT_STYLES)`; `ThemeStack.push/pop_theme`.

### `rich.table.Table` and `rich.box` styles

```python
Table(*headers: Column|str, title=None, caption=None, width=None, min_width=None,
      box=HEAVY_HEAD, safe_box=None, padding=(0,1), collapse_padding=False,
      pad_edge=True, expand=False, show_header=True, show_footer=False,
      show_edge=True, show_lines=False, leading=0, style="none",
      row_styles=None, header_style="table.header", footer_style="table.footer",
      border_style=None, title_style=None, caption_style=None,
      title_justify="center", caption_justify="center", highlight=False)
table.add_column(header="", footer="", *, header_style=None, style=None,
                 justify="left", vertical="top", overflow="ellipsis",
                 width=None, min_width=None, max_width=None, ratio=None,
                 no_wrap=False, ...)
table.add_row(*renderables, style=None, end_section=False)
table.add_section()          # draws a mid rule between row groups
Table.grid(*headers, padding=0, collapse_padding=True, pad_edge=False, expand=False)  # classmethod, borderless layout grid
```

Any renderable (even nested Tables, Syntax, Markdown) can be a cell.
Box constants (`box.py`): `ASCII`, `ASCII2`, `ASCII_DOUBLE_HEAD`,
`SQUARE`, `SQUARE_DOUBLE_HEAD`, `MINIMAL`, `MINIMAL_HEAVY_HEAD`,
`MINIMAL_DOUBLE_HEAD`, `SIMPLE`, `SIMPLE_HEAD`, `SIMPLE_HEAVY`,
`HORIZONTALS`, `ROUNDED`, `HEAVY`, `HEAVY_EDGE`, `HEAVY_HEAD` (default),
`DOUBLE`, `DOUBLE_EDGE`, `MARKDOWN`. `Box.substitute(options, safe=True)`
auto-downgrades to ASCII on legacy Windows; `get_plain_headed_box()`.

### `rich.panel.Panel` / `rich.rule.Rule` / `rich.align.Align` / `rich.padding.Padding` / `rich.columns.Columns` / `rich.tree.Tree`

```python
Panel(renderable, box=ROUNDED, *, title=None, title_align="center",
      subtitle=None, subtitle_align="center", safe_box=None, expand=True,
      style="none", border_style="none", width=None, height=None,
      padding=(0,1), highlight=False)
Panel.fit(renderable, box=ROUNDED, *, ...)          # shrink-to-content
Rule(title="", *, characters="─", style="rule.line", end="\n", align="center")
Align(renderable, align="left", style=None, *, vertical=None, pad=True, width=None, height=None)
Align.left/center/right(renderable, style=None, *, vertical=None, pad=True, width=None, height=None)  # classmethods
VerticalCenter(renderable, style=None)
Padding(renderable, pad=(0,0,0,0), *, style="none", expand=True)
Padding.indent(renderable, level)                   # classmethod, 4 cols/level
Columns(renderables=None, padding=(0,1), *, width=None, expand=False, equal=False,
        column_first=False, right_to_left=False, align=None, title=None)  # + .add_renderable()
Tree(label, *, style="tree", guide_style="tree.line", expanded=True, highlight=False, hide_root=False)
tree.add(label, *, style=None, guide_style=None, expanded=True, highlight=False) -> Tree
```

### `rich.progress.Progress` / `track`

```python
def track(sequence, description="Working...", total=None, completed=0,
          auto_refresh=True, console=None, transient=False, get_time=None,
          refresh_per_second=10, style="bar.back", complete_style="bar.complete",
          finished_style="bar.finished", pulse_style="bar.pulse",
          update_period=0.1, disable=False, show_speed=True)  # one-liner iterator
Progress(*columns, console=None, auto_refresh=True, refresh_per_second=10,
         speed_estimate_period=30.0, transient=False,
         redirect_stdout=True, redirect_stderr=True, get_time=None,
         disable=False, expand=False)   # context manager or .start()/.stop()
Progress.get_default_columns()  # description, bar, percentage, remaining, time
task_id = progress.add_task(description, start=True, total=100.0, completed=0, visible=True, **fields)
progress.update(task_id, *, total=None, completed=None, advance=None, description=None, visible=None, refresh=False, **fields)
progress.advance(task_id, advance=1)
progress.reset(task_id, *, start=True, total=None, completed=0, visible=None, description=None, **fields)
progress.start_task(task_id) / progress.stop_task(task_id) / progress.remove_task(task_id)
progress.track(sequence, total=None, ...)   # bound version of track()
progress.wrap_file(file, total=None, ...) / progress.open(path, mode="rb", ...)  # file reader with bar
wrap_file(file, total, *, description="Reading...", ...) / open(...)  # module-level equivalents
```

Columns: `TextColumn("{task.description}")` (+`{task.fields[x]}`),
`BarColumn()`, `TaskProgressColumn()`, `TimeElapsedColumn()`,
`TimeRemainingColumn()`, `SpinnerColumn()`, `RenderableColumn(renderable)`,
`FileSizeColumn()`, `TotalFileSizeColumn()`, `DownloadColumn()`,
`TransferSpeedColumn()`, `MofNCompleteColumn()`. `expand=True` stretches
bars full width; `transient=True` erases on completion; `disable=True`
silences for non-TTY/CI. `ProgressBar(total=100.0, completed=0,
width=None, pulse=False, ...)` + `.update(completed, total=None)` for a
bare bar; `Bar(size, begin, end, width=None, color, bgcolor)` for
fractions. Thread-safety: `Progress` is thread-safe; `track()` spawns its
own `_TrackThread`.

### `rich.live.Live` / `rich.status.Status` / `rich.spinner.Spinner`

```python
Live(renderable=None, *, console=None, screen=False, auto_refresh=True,
     refresh_per_second=4, transient=False, redirect_stdout=True,
     redirect_stderr=True, vertical_overflow="ellipsis",
     get_renderable=None)     # context manager; .start(refresh=False)/.stop()
live.update(renderable, *, refresh=False)   # swap content any time
live.refresh() / live.renderable (property) / live.is_started
Status(status, *, console=None, spinner="dots", spinner_style="status.spinner",
       speed=1.0, refresh_per_second=12.5)  # context manager or start()/stop()
status.update(status=None, *, spinner=None, spinner_style=None, speed=None)
Spinner(name, text="", *, style=None, speed=1.0)  # .render(time), .update(...)
# spinner names live in _spinners.py; preview with: python -m rich.spinner
```

`console.status(...)` is the one-line spelling of `Status`.

### `rich.syntax.Syntax`

```python
Syntax(code, lexer: Lexer|str, *, theme=DEFAULT_THEME, dedent=False,
       line_numbers=False, start_line=1, line_range=None,
       highlight_lines=None, code_width=None, tab_size=4, word_wrap=False,
       background_color=None, indent_guides=False,
       padding: PaddingDimensions = 0)
Syntax.from_path(path, encoding="utf-8", lexer=None, theme=DEFAULT_THEME,
                 dedent=False, line_numbers=False, line_range=None,
                 start_line=1, highlight_lines=None, code_width=None,
                 tab_size=4, word_wrap=False, background_color=None,
                 indent_guides=False, padding=0)   # classmethod
Syntax.guess_lexer(path, code=None)               # classmethod
syntax.highlight(code, line_range=None)           # re-highlight in place
syntax.stylize_range(style, start, end, style_before=False)
```

Powered by Pygments (`theme` accepts any Pygments style name, e.g.
`"monokai"`); `ANSISyntaxTheme` exists for ANSI fallback. Markdown code
fences delegate here too.

### `rich.markdown.Markdown`

```python
Markdown(markup: str, code_theme="monokai", justify=None, style="none",
         hyperlinks=True, inline_code_lexer=None, inline_code_theme=None)
```

Parsed by `markdown-it-py` into `MarkdownElement` subclasses
(`Heading`, `Paragraph`, `CodeBlock`, `BlockQuote`, `HorizontalRule`,
`TableElement/TableHeader/TableBody/TableRow/TableData`, `ListElement`,
`ListItem`, `Link`, `ImageItem`) rendered in `MarkdownContext`.
Example: `console.print(Markdown(open("README.md").read()))`.

### `rich.json.JSON`

```python
JSON(json: str, indent=2, highlight=True, skip_keys=False, ensure_ascii=False,
     check_circular=True, allow_nan=True, default=None, sort_keys=False)
JSON.from_data(data, indent=2, ...)   # classmethod — encode then render
```

`console.print_json(json=..., data=...)` and top-level `rich.print_json`
are the shortcuts. `default=` handles non-encodable values like
`json.dumps`.

### `rich.pretty.Pretty` / `pprint` / `pretty_repr` / `install`

```python
Pretty(_object, highlighter=None, *, indent_size=4, justify=None, overflow=None,
       no_wrap=False, indent_guides=False, max_length=None, max_string=None,
       max_depth=None, expand_all=False, margin=0, insert_line=False)
pretty_repr(obj, *, max_width=80, indent_size=4, max_length=None, max_string=None,
            max_depth=None, expand_all=False) -> str
pprint(obj, *, console=None, indent_guides=True, max_length=None, max_string=None,
       max_depth=None, expand_all=False) -> None
traverse(obj, max_length=None, max_string=None, max_depth=None) -> Node
is_expandable(obj) -> bool
install(console=None, overflow="ignore", crop=False, indent_guides=False,
        max_length=None, max_string=None, max_depth=None, expand_all=False) -> None  # REPL display hook
```

Handles dataclasses, attrs, namedtuples, defaultdicts, deques, arrays;
`max_*` knobs bound output size for logging large engine dicts.

### `rich.traceback.Traceback` / `install`

```python
install(*, console=None, width=100, code_width=88, extra_lines=3, theme=None,
        word_wrap=False, show_locals=False, locals_max_length=10,
        locals_max_string=80, locals_max_depth=None, locals_hide_dunder=True,
        locals_hide_sunder=None, indent_guides=True, suppress=(),
        max_frames=100) -> previous_excepthook
Traceback(trace=None, *, width=100, code_width=88, extra_lines=3, theme=None,
          word_wrap=False, show_locals=False, ...same locals_* knobs...,
          suppress=(), max_frames=100)
Traceback.from_exception(exc_type, exc_value, traceback, *, ...)  # classmethod
Traceback.extract(exc_type, exc_value, traceback, *, show_locals=False, ...)  # -> Trace
```

`install()` swaps `sys.excepthook` (plus an IPython hook) so uncaught
exceptions render with source context + optional locals tables.
`suppress=(click, ...)` hides framework frames.

### `rich._inspect.Inspect` / `rich.inspect()` / `rich.scope`

Top-level `rich.inspect(obj, ...)` (signature in §`__init__`) builds
`Inspect(obj, *, title=None, help=False, methods=False, docs=True,
private=False, dunder=False, sort=True, all=False, value=True)` — a
renderable showing type, signature, attributes, and pretty value; the
`all=True` shortcut enables methods+private+dunder. `rich.scope.render_scope(scope, *, title=None, sort_keys=True, indent_guides=False, ...)` renders a
locals-dict panel (what `console.log(log_locals=True)` uses internally).

### `rich.prompt.Prompt` / `Confirm` / `IntPrompt` / `FloatPrompt`

```python
Prompt.ask(prompt="", *, console=None, password=False, choices=None,
           case_sensitive=True, show_default=True, show_choices=True,
           default=..., stream=None) -> str
Confirm.ask(prompt="", *, ..., default=...) -> bool     # yes/no, "[y/n]"
IntPrompt.ask(...) -> int / FloatPrompt.ask(...) -> float
PromptBase(prompt, *, password=False, default=..., show_default=True,
           show_choices=True, choices=None, ...)        # instantiable form
prompt_inst(prompt=..., default=..., stream=None)       # __call__
```

Subclass hooks: `.process_response(value)`, `.check_choice(value)`,
`.make_prompt(default)`, `.render_default(default)`,
`.get_input(console, prompt, password, stream)`,
`.on_validate_error(value, error)`, `.pre_prompt()`.
`PromptError` / `InvalidResponse(message)` exceptions.

### `rich.logging.RichHandler`

```python
RichHandler(level=NOTSET, console=None, *, show_time=True,
            omit_repeated_times=True, show_level=True, show_path=True,
            enable_link_path=True, highlighter=None, markup=False,
            rich_tracebacks=False, tracebacks_width=None,
            tracebacks_code_width=88, tracebacks_extra_lines=3,
            tracebacks_theme=None, tracebacks_word_wrap=True,
            tracebacks_show_locals=False, tracebacks_suppress=(),
            tracebacks_max_frames=100, locals_max_length=10,
            locals_max_string=80, log_time_format="[%x %X]",
            keywords=None)   # subclasses logging.Handler
```

Methods: `.emit(record)`, `.render(*, record, traceback,
message_renderable)`, `.render_message(record, message)`,
`.get_level_text(record)`. `keywords=[...]` highlights extra words;
`markup=True` enables `[...]` markup in log messages (off by default —
safer for ffmpeg output).

### Layout / screen / misc modules

- `rich.layout.Layout(renderable=None, *, name=None, size=None,
  minimum_size=1, ratio=1, visible=True)`: `.split/.split_row/.split_column/
  .add_split(*layouts)`, `.unsplit()`, `.update(renderable)`,
  `.get(name)`, `.map/.tree`, `.refresh_screen(console, layout_name)`;
  `RowSplitter`/`ColumnSplitter` divide regions.
- `rich.screen.Screen(*renderables, style=None, application_mode=False)` —
  full alt-screen renderable (pairs with `console.screen()`).
- `rich.live_render.LiveRender`, `rich.region.Region`,
  `rich.containers.Renderables/Lines` (`.justify(console, width, ...)`),
  `rich.constrain.Constrain(renderable, width=80)`,
  `rich.styled.Styled(renderable, style)`,
  `rich.control.Control` (`.bell/.home/.move(x,y)/.move_to/.clear/
  .show_cursor/.alt_screen/.title()` statics; `strip_control_codes`,
  `escape_control_codes`), `rich.ansi.AnsiDecoder` (`.decode()`/
  `.decode_line()` — renders ANSI-escaped engine output as Text),
  `rich.pager.Pager/SystemPager` (`.show(content)`),
  `rich.file_proxy.FileProxy` (redirects `sys.stdout` writes into a
  Console), `rich.emoji.Emoji(name, style="none")` + `:name:` codes +
  `Emoji.replace(text)` / `NoEmoji`, `rich.filesize.decimal(size,
  precision=1, separator=" ")`, `rich.palette.Palette(...).match(rgb)`,
  `rich._palettes` (256-color tables), `rich.cells` (width measurement),
  `rich.measure.Measurement` (`.span/.normalize/.with_maximum/
  .with_minimum/.clamp(min,max)` + `Measurement.get(console, options,
  renderable)`), `rich.segment.Segment` (the render atom:
  `Segment(text, style=None, control=None)` + `split_cells`,
  `split_lines`, `adjust_line_length`, `simplify`, `strip_styles/
  strip_links/remove_color`, `divide`, `align_top/bottom/middle`),
  `rich.protocol` (`is_renderable`, `rich_cast`), `rich.abc.RichRenderable`
  ABC, `rich.repr` (`@rich_repr`, `auto` decorators),
  `rich.color_triplet.ColorTriplet` (`.hex/.rgb/.normalized`),
  `rich.terminal_theme.TerminalTheme` (export themes),
  `rich.diagnose` (env report), `rich.jupyter.JupyterMixin`,
  `rich._log_render.LogRender`, `rich._timer`, `rich._ratio`,
  `rich._loop`, `rich._pick`, `rich._stack`, `rich._fileno`,
  `rich._null_file.NullFile`, `rich._windows*` (Win32 console plumbing),
  `rich._extension.load_ipython_extension`.
- `rich.errors`: `ConsoleError`, `StyleError`, `StyleSyntaxError`,
  `MissingStyle`, `StyleStackError`, `NotRenderableError`, `MarkupError`,
  `LiveError`, `NoAltScreen`.
- `rich.highlighter`: `Highlighter.__call__`, `NullHighlighter`,
  `RegexHighlighter`, `ReprHighlighter` (numbers/strings/URLs/IPs…),
  `JSONHighlighter`, `ISO8601Highlighter`.
- `rich.bar.Bar(size, begin, end, *, width=None, color="default",
  bgcolor="default")` — fractional range bar (different from ProgressBar).
- `rich.status`/`rich.spinner` — see Live section.

## App usage & correctness

**(a) Correct usage — there is none, and that is expected.** Zero `import
rich` / `from rich` statements exist anywhere under `src/`, `tests/`, or
`tools/`. The 25 grep hits for "rich" in `tests/test_remux_dossier.py` are
all the `rich.mp4` fixture filename / `rich_source` fixture — not the
library (verified lines 19–199). rich reaches the venv only as a transitive
dep of `flet-cli`, `flet-desktop`, and `cookiecutter`. Nothing to fix; no
misuse to report.

**(b) Misuse — none found** (no direct usage means no incorrect usage:
no unescaped-markup `print`, no `Live` left un-stopped, no blocking
`Prompt.ask` on a mobile UI thread).

**(c) Underuse — the real story.** The app hand-rolls in Flet/plain-stdlib
several things rich does better, but only in places where a terminal
actually exists (dev host, CI, desktop runs — **not** inside the phone UI,
where Flet widgets remain correct):

1. `src/main.py:47-99` `_bootstrap_logging()` — builds
   `StreamHandler(sys.stderr)` + `FileHandler` with a hand-written
   `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` formatter.
   `RichHandler` (with `rich_tracebacks=True`,
   `tracebacks_show_locals=True`) would give colorized levels, aligned
   paths, and pretty tracebacks on the dev console for free.
2. `src/main.py:102-129` `_crash_hook()` (+`_install_loop_handler`) —
   routes uncaught/thread/async exceptions through plain
   `logger.critical/error`. Wrapping the stderr console with
   `rich.traceback.install(show_locals=True,
   suppress=("flet", "asyncio"))` during desktop/CI runs would render
   source-context tracebacks instead of single-line log records.
3. `src/services/engine_service.py` (`on_progress` callbacks at
   :641/:802-809/:837-838/:855-965/:988-1095/:1112-1183/:1226-1372) —
   throttled `(float, str)` progress callbacks. On desktop/CI harnesses,
   `Progress.add_task/update/advance` or one-line `track()` renders these
   as flicker-free bars with ETA (`TimeRemainingColumn`,
   `TransferSpeedColumn`); today that progress is only visible inside the
   Flet job cards.
4. `tools/admob.py` (click-based: `click.echo/secho/confirm`,
   `ClickException`) — works, but `Table` (three-file ID alignment
   check), `Confirm.ask`, and `Rule` would make `check-ids`/`swap-ids`
   output scannable; `tools/make_icons.py:50-59` uses three bare
   `print()` calls that `rich.print`/`Console.log` would timestamp.
5. `src/screens/settings_screen.py:87-96,132-153` Activity Terminal —
   renders `MemoryLogHandler.get_logs()` as monochrome `monospace`
   `ft.Text`. Correct for on-device (rich cannot render into Flet), but
   the *content* could be pre-colored server-side with
   `console.export_text(styles=True)`… in practice keep as-is; noted only
   for completeness.
6. `tests/` (18 files) — bare `assert`s with no formatted failure context;
   `pytest --tb=short` + a `conftest.py` that installs
   `rich.traceback.install(show_locals=True)` for local runs, or
   `pretty_repr`/`print_json` in failure helpers, would shorten
   red-bar triage.

## Underused APIs to adopt

Ranked by value for this Flet-mobile + desktop-tooling codebase. All are
desktop/CI/CLI-side — none belong inside the phone UI render path.

| # | API | Concrete adoption |
|---|---|---|
| 1 | `rich.logging.RichHandler` | Add to `_bootstrap_logging` (`src/main.py:47`) when `sys.stderr.isatty()` / `--dev`: colorized levels, `rich_tracebacks=True`. One handler, zero call-site changes. |
| 2 | `rich.traceback.install` | `tests/conftest.py` + desktop dev entry: `install(show_locals=True, suppress=["flet"])`. Complements (not replaces) `_crash_hook` (`src/main.py:102`), which must stay plain-text for the on-device file log. |
| 3 | `rich.progress.track` / `Progress` | Wrap engine batch/CI scripts and any desktop harness driving `EngineService.remux/compress/cut` (`src/services/engine_service.py` progress sites above): `for f in track(files, "Transcoding…")`. `transient=True` + `disable=not sys.stderr.isatty()` for CI safety. |
| 4 | `rich.table.Table` + `box.ROUNDED/SIMPLE` | `tools/admob.py check-ids`: 3-file ID alignment as a table instead of 4 `click.echo` lines; also engine-probe dumps (`EngineService.probe` dicts) in debug tooling. |
| 5 | `rich.pretty.pprint` / `pretty_repr` | Log `probe()` result dicts and `OpPlan` objects (`src/services/command_parser.py`, `src/screens/terminal_screen.py:98` plan echo) with bounded `max_string/max_depth` instead of `repr`. |
| 6 | `rich.prompt.Confirm.ask` / `Prompt.ask(choices=...)` | Replace `click.confirm` in `tools/admob.py:109` for destructive `swap-ids --mode prod`; choices-validated prompts for future scaffolding CLIs. |
| 7 | `rich.syntax.Syntax` | Render generated ffmpeg command lines / `help_text()` (`src/services/command_parser.py`, `src/screens/terminal_screen.py:53`) with shell-lexer highlighting in desktop help output. |
| 8 | `rich.live.Live` / `console.status` | Long dev-only waits (model downloads, `update_service` fetches): `with console.status("[bold green]Fetching update…")`. Never on the UI thread. |
| 9 | `rich.json.JSON` / `print_json` | Pretty-print `probe()` JSON and dossier reports in diagnostics instead of raw `json.dumps`. |
| 10 | `rich.rule.Rule` / `Panel.fit` | Section dividers in CLI output (`Rule("probe")`, `Panel.fit(plan.summary())`) for `tools/*.py` readability. |
| 11 | `rich.ansi.AnsiDecoder` | If engine stderr (which contains ANSI color codes) is ever surfaced in desktop logs, decode to `Text` instead of showing raw escapes. |
| 12 | `rich.markdown.Markdown` | Render `src/core/changelog.py` / release notes to the desktop console at startup in dev builds. |

Precondition for all of the above: promote `rich>=15,<16` (or `>=15`) into
`pyproject.toml [project] dependencies` — today it is only guaranteed
present via dev-group packages, so any `src/` or `tools/` import is one
`uv sync --no-dev` away from breaking.

## Gotchas

1. **Transitive-only dep.** `import rich` works in this venv by accident
   (flet-cli/flet-desktop/cookiecutter). Do not import it from `src/` or
   `tools/` until it is a declared dependency — the packaged APK resolver
   only ships declared runtime deps.
2. **No `rich.context` / `rich.pixels`.** The brief named them; neither
   module exists in 15.0.0. (Upstream `rich.pixels`/` rich._win32_console`
   pixel experiments never shipped as public modules.)
3. **Markup vs ffmpeg syntax.** `console.print` interprets `[…]` — ffmpeg
   filtergraphs (`[0:v]scale=…[out]`), stream maps, and file paths with
   brackets will raise `MarkupError` or silently restyle. Always
   `escape()` engine/user text or pass `markup=False` when printing
   commands, plans, or probe output.
4. **`print()` flushes always; `Console(record=True)` buffers.** For the
   Activity Terminal file log, `export_text(clear=False)` semantics matter:
   `export_*` defaults `clear=True`, which drains the record buffer.
5. **Emoji on Windows/mobile logs.** Emoji codes (`:warning:`) render as
   unicode glyphs that look wrong in legacy consoles and the on-device
   monospace view — construct dev consoles with `emoji=False` when output
   feeds `MemoryLogHandler`.
6. **`Live`/`Progress` redirect stdout/stderr by default**
   (`redirect_stdout=True, redirect_stderr=True`) and spin refresh threads;
   never start them on the Flet UI thread or inside `page.run_task`
   coroutines — restrict to CLI tools and background threads, and always
   use them as context managers so the refresh thread stops.
7. **`Prompt.ask` blocks on stdin.** It has no place in the mobile app or
   async Flet handlers; CLI tools only.
8. **`traceback.install(show_locals=True)` can leak secrets** (tokens, AdMob
   IDs, paths) into console output — keep `show_locals=False` in any
   shared/CI log, and never route rich tracebacks into the on-device
   `app.log` file that users can export.
9. **Unpinned `markdown-it-py>=2.2.0`** upstream means future `uv lock`
   refreshes can move Markdown rendering behavior; if `Markdown` output is
   ever user-visible, pin it explicitly.
10. **`safe_box=True` (default) substitutes ASCII boxes on legacy Windows**
    — desktop CLI tables degrade gracefully, but snapshot tests asserting
    exact box-drawing characters will differ across platforms; set
    `safe_box=False` + fixed `width=` in tests that assert rendered output.
11. **`quiet=True` silences all output; `no_color` honors `NO_COLOR`.**
    Respect both in CI (`--quiet` flags should construct the shared
    console with `quiet=True` rather than sprinkling `if` checks).
12. **Threading.** `Console.print` is thread-safe (internal `RLock`), but
    interleaved `print` from engine worker threads still garbles *logical*
    grouping — use a single `Live`/`Progress` instance or a logging
    handler rather than raw prints from callbacks.
