# Pygments 2.21.0 — Complete API Reference

> Syntax highlighting engine (transitive dep via `rich 15.0.0`). No direct app usage today.
> Relevance for v1: Flet-native highlighting for the Expert Terminal command preview,
> Activity Terminal log pane, before/after param diffs, and crash-report snippets.

## Files

Package dir: `.venv/Lib/site-packages/pygments` — 365 files total (incl. `__pycache__`, skipped below).
Dist-info: `.venv/Lib/site-packages/pygments-2.21.0.dist-info/` (352 RECORD lines).

**Top-level modules** (all read):

| File | Contents |
|---|---|
| `__init__.py` | `__version__ = '2.21.0'`; `__all__ = ['lex', 'format', 'highlight']` |
| `__main__.py` | `python -m pygments` → `pygments.cmdline.main(sys.argv)` |
| `cmdline.py` | `pygmentize` CLI: `-l` lexer, `-f` formatter, `-O` options, `-F` filters, `-S` style defs, `-L` list, `-H` help, `-x` custom lexers/formatters, `-o` output file |
| `console.py` | Low-level ANSI helpers: `codes` dict, `colorize(color_key, text)`, `ansiformat(attr, text)` (`*bold*`, `_underline_`, `+blink+` markers), `reset_color()` |
| `filter.py` | `Filter` base (`__init__(**options)`, `filter(lexer, stream)`), `FunctionFilter`, `@simplefilter` decorator, `apply_filters(stream, filters, lexer)` |
| `filters/__init__.py` | 8 builtin filters + `get_filter_by_name` / `find_filter_class` / `get_all_filters` (see API) |
| `formatter.py` | `Formatter` base; options `style`/`full`/`title`/`encoding`/`outencoding`; `format(tokensource, outfile)`, `format_unencoded(tokensource, outfile)`, `get_style_defs(arg='')` |
| `lexer.py` | `Lexer`, `RegexLexer`, `ExtendedRegexLexer`, `DelegatingLexer`, `LexerContext`, helpers `include`/`inherit`/`combined`/`bygroups`/`using`/`this`/`default`/`words`/`line_re`, `do_insertions`, `ProfilingRegexLexer` |
| `lexers/` | 263 `.py` files, **602 mapping entries** in `_mapping.py` (500+ languages) |
| `formatters/` | 13 modules: `bbcode`, `groff`, `html`, `img` (+gif/jpg/bmp), `irc`, `latex`, `other` (null/raw/testcase), `pangomarkup`, `rtf`, `svg`, `terminal`, `terminal256` (256 + truecolor), `_mapping.py` (18 `FORMATTERS` entries) |
| `style.py` | `Style` + `StyleMeta`; `style_for_token()`, `list_styles()`, `styles_token()`; `ansicolors` set, `#ansi*` → new-name deprecation map |
| `styles/` | 52 files (`_mapping.py` lists **49 styles**); `get_style_by_name(name)`, `get_all_styles()` |
| `token.py` | `_TokenType`, full `Token` tree, `STANDARD_TYPES` (CSS short names), `string_to_tokentype()`, `is_token_subtype()` |
| `plugin.py` | Entry-point groups: `pygments.lexers` / `pygments.formatters` / `pygments.styles` / `pygments.filters` (+ `functools.cache`d `iter_entry_points`) |
| `util.py` | `ClassNotFound`, `OptionError`, `get_bool_opt` / `get_int_opt` / `get_list_opt` / `get_choice_opt`, `shebang_matches`, `doctype_matches`, `guess_decode`, `html_escape`, `Future` |
| `modeline.py` | `get_filetype_from_buffer` (vim modeline — tried first by `guess_lexer`) |
| `regexopt.py` | `regex_opt()` — builds optimized alternation regexes (used by `words()`) |
| `scanner.py` | `Scanner` — regex scanner helper for hand-written lexers |
| `sphinxext.py` | Sphinx extension (docs only, irrelevant to app) |
| `unistring.py` | Generated Unicode category tables (`Cc Cf Cn Co Cs Ll Lm Lo …`) for Unicode-aware lexers |

## Metadata

From `pygments-2.21.0.dist-info/METADATA`:

- **Name / Version:** Pygments 2.21.0 · **Requires-Python:** `>=3.9` (covers app's 3.14) · **Status:** 6 - Mature
- **License:** `BSD-2-Clause` (LICENSE file under `licenses/` in dist-info) — permissive, Play Store safe
- **Console script** (`entry_points.txt`): `pygmentize = pygments.cmdline:main`; also runnable as `python -m pygments`
- **Plugin groups** (`plugin.py`): `pygments.lexers`, `pygments.formatters`, `pygments.styles`, `pygments.filters`
  (this install ships **no third-party plugin entry points** — only builtins)
- **Extras:** `plugins`, `windows-terminal` (`colorama>=0.6` on Windows)
- **Dependency status: TRANSITIVE, not direct.** `pyproject.toml` does not list `pygments` or `rich`;
  both are in `uv.lock` / `.venv` (`rich 15.0.0`, `pillow 12.3.0` also present, so `ImageFormatter` would work).
  → If v1 adopts it, add `pygments>=2.21` to `dependencies` so a resolver prune can't drop it.

## API (lexers/formatters/styles/filters)

### Core pipeline

```python
from pygments import lex, format, highlight  # lex/format/highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import get_formatter_by_name

highlight(code, lexer_instance, formatter_instance, outfile=None)
# = format(lex(code, lexer), formatter, outfile)
# lex() REQUIRES an instance: get_lexer_by_name("bash"), NOT the class (TypeError otherwise).
# outfile=None → returns str (or bytes for binary formatters like RawToken/Image);
# pass a file object with .write() to stream into it.
```

### Lexers — `pygments.lexers`

Lookup (all accept `**options` forwarded to the lexer constructor):

```python
get_lexer_by_name(alias, **options)  # e.g. "bash", "diff", "pytb" — raises ClassNotFound
get_lexer_for_filename(filename, code=None, **options)
get_lexer_for_mimetype(mimetype, **options)
guess_lexer(text, **options)  # runs analyse_text() over ALL lexers — slow, last resort
guess_lexer_for_filename(filename, text, **options)  # scoped guess — prefer this
find_lexer_class(name)  # by full name, returns class (None if missing)
find_lexer_class_by_name(alias)  # by alias, returns class (raises ClassNotFound)
find_lexer_class_for_filename(fn, code=None)
load_lexer_from_file(path, lexername="CustomLexer", **options)  # exec() — untrusted input = RCE
get_all_lexers(plugins=True)  # yields (name, aliases, filenames, mimetypes)
```

Base `Lexer.__init__` options (every lexer): `stripnl=True` (strip leading/trailing newlines),
`stripall=False`, `ensurenl=True` (append trailing `\n` — linewise lexers need it),
`tabsize=0` (expand tabs if > 0), `encoding='guess'` (utf-8 → locale → latin-1) / `'chardet'` (needs chardet lib),
`inencoding` (overrides `encoding`), `filters=[...]` (filter names + options via `add_filter`).
`get_tokens(text, unfiltered=False)` yields `(tokentype, value)`; the 3-tuple variant is
`get_tokens_unprocessed(text)` → `(index, tokentype, value)`.

**Lexer coverage: 602 entries in `_mapping.py` across 263 files.** Mapping tables enumer
ate `(module, name, aliases, filenames, mimetypes)`; individual lexer files were sampled, not all read.
Key samples for this app (verified in `_mapping.py` / source):

| Lexer | Aliases | Filenames | Notes |
|---|---|---|---|
| `BashLexer` (`lexers/shell.py`) | `bash sh ksh zsh shell openrc` | `*.sh *.bash *.zsh …` + rc files | Best match for ffmpeg command lines (flags, quotes, `&&`, `$vars`) |
| `BashSessionLexer` | `console shell-session` | `*.sh-session` | For `$ ffmpeg …\n<output>` transcripts — prompt vs output tokens |
| `DiffLexer` (`lexers/diff.py`) | `diff udiff` | `*.diff *.patch` | `Generic.Deleted/Inserted/Heading` tokens — before/after param diffs |
| `JsonLexer` (`lexers/data.py`) | `json json-object` | `*.json *.jsonl` | ffprobe JSON output |
| `YamlLexer` (`lexers/data.py`) | `yaml yml` | `*.yaml *.yml` | Config/job-spec rendering |
| `PythonTracebackLexer` (`lexers/python.py`) | `pytb py3tb` | `*.pytb` | Crash-report snippets (`Generic.Traceback` token) |
| `PythonLexer` / `PythonConsoleLexer` | `python py …` / `pycon` | `*.py …` | Diagnostics tooling, doctest-style samples |
| `IniLexer`/`TOMLLexer`/`PropertiesLexer` (`lexers/configs.py`) | `ini` / `toml` / `properties` | `*.ini *.cfg` / `*.toml` / `*.properties` | Preset/config file preview |
| `TextLexer` (`lexers/special.py`) | `text` | `*.txt` | Safe fallback (never errors) |

**There is NO ffmpeg/ffprobe lexer.** Grep for `ffmpeg|ffdec|ffprobe|mplayer` across all of
`lexers/` returns zero hits — no dedicated CLI-grammar lexer exists upstream. `BashLexer` is the
correct stand-in (flags lex as `Name.Attribute`/`Operator`, paths as `String`/`Text`); for exact
per-flag coloring (e.g. `-crf` vs `-preset` vs paths) use `NameHighlightFilter` (below) on top.

### Formatters — `pygments.formatters` (18 entries in `_mapping.py`)

```python
get_formatter_by_name(alias, **options)  # e.g. "terminal256", "html" — raises ClassNotFound
get_formatter_for_filename(
    fn, **options
)  # *.html → HTML, *.tex → LaTeX, *.rtf, *.svg, *.png/gif/jpg/bmp, *.txt, *.raw
find_formatter_class(alias)  # class or None
load_formatter_from_file(
    path, formattername="CustomFormatter", **options
)  # exec() — same RCE caveat
get_all_formatters()  # yields classes (not tuples, unlike lexers)
```

Base options: `style='default'` (name or `Style` subclass), `full=False` (self-contained document),
`title=''`, `encoding=None` (str output) / set for bytes, `outencoding` (overrides `encoding`).

| Formatter | Aliases | Key options (all verified in source) |
|---|---|---|
| `TerminalFormatter` (`terminal.py`) | `terminal console` | `bg='light'│'dark'`, `colorscheme=dict│None`, `linenos=False`. **Ignores `style`** — hardcoded `TERMINAL_COLORS` (16 ANSI colors, `*bold*`/`_underline_` markers via `ansiformat`) |
| `Terminal256Formatter` (`terminal256.py`) | `terminal256 console256 256` | `style='default'`, `linenos=False`, `nobold`/`nounderline`/`noitalic` kill-switches. Converts style RGB → nearest xterm-256 (`38;5;N`/`48;5;N`); `#ansi*` style colors map to plain ANSI |
| `TerminalTrueColorFormatter` (same file) | `terminal16m console16m 16m` | Same options; emits `38;2;R;G;B` truecolor — pick by terminal capability |
| `HtmlFormatter` (`html.py`) | `html` | `nowrap`, `full`, `title`, `noclasses` (inline styles vs CSS classes), `classprefix`, `cssclass='highlight'`, `cssstyles`, `prestyles`, `cssfile`, `noclobber_cssfile`, `linenos=False│'table'│'inline'│True`, `hl_lines=[]`, `linenostart=1`, `linenostep`, `linenospecial`, `nobackground`, `lineseparator='\n'`, `lineanchors` (per-line `#id` anchors), `linespans`, `anchorlinenos`, `tagsfile` (ctags — needs `python-ctags`), `filename`, `debug_token_types`. `get_style_defs(arg)` → CSS |
| `ImageFormatter` + Gif/Jpg/Bmp (`img.py`) | `img IMG png` / `gif` / `jpg jpeg` / `bmp bitmap` | **Requires Pillow** (present: 12.3.0). `font_name` (default DejaVu Sans Mono / Courier New / Menlo per-OS), `font_size=14`, `image_format`, `image_pad=10`, `line_pad=2`, `line_numbers=True`, `line_number_fg/bg/chars/step/start/pad/separator`, `hl_lines`, `hl_color`. Raises `PilNotAvailable` / `FontNotFound` |
| `NullFormatter` (`other.py`) | `text null` | None — passthrough, keeps `stripnl/ensurenl` normalization |
| `RawTokenFormatter` (`other.py`) | `raw tokens` | `compress=''│'gz'│'bz2'`, `error_color`. Emits `repr(ttype)\t repr(value)` lines (**bytes**, needs binary outfile). Round-trips via `RawTokenLexer` |
| `TestcaseFormatter` (`other.py`) | `testcase` | None — emits a ready `testNeedsName` assertion block (handy for golden lexer tests) |
| `LatexFormatter` (`latex.py`) | `latex tex` | `nowrap`, `docclass='article'`, `preamble`, `linenos`, `linenostart/step`, `verboptions`, `nobackground`, `commandprefix='PY'`, `texcomments`, `mathescape`, `escapeinside`, `envname='Verbatim'` |
| `RtfFormatter` (`rtf.py`) | `rtf` | `fontface`, `fontsize`, `linenos`, `lineno_*`, `linenostart/step`, `hl_linenostart`, `hl_color`, `hl_lines` — copy/paste into Word |
| `SvgFormatter` (`svg.py`) | `svg` | `nowrap`, `fontfamily='monospace'`, `fontsize='14px'`, `xoffset`, `yoffset`, `ystep`, `spacehack=True`, `linenos`, `linenostart/step`, `linenowidth` — experimental (`<text>`+`<tspan>` per line) |
| `BBCodeFormatter` (`bbcode.py`) | `bbcode bb` | `codetag`, `monofont` — forum posts |
| `IRCFormatter` (`irc.py`) | `irc IRC` | `bg='light'│'dark'`, `colorscheme`, `linenos` — mIRC color codes |
| `GroffFormatter` (`groff.py`) | `groff troff roff` | `monospaced=True`, `linenos`, `wrap=0` — man pages |
| `PangoMarkupFormatter` | `pango pangomarkup` | Style-driven Pango markup (renders to SVG) |

No `json` formatter alias exists — token streams serialize via `RawTokenFormatter`, not JSON.

### Styles — `pygments.styles` (49 builtins)

`get_style_by_name(name)` (raises `ClassNotFound`), `get_all_styles()` (names incl. plugins).
Short names incl: `default bw emacs friendly fruity tango vim vs xcode monokai native dracula
github-dark gruvbox-dark gruvbox-light solarized-dark solarized-light nord nord-darker one-dark
night-owl material manni pastie borland autumn igor inkpot lovelace paraiso-dark/light stata-dark/light …`
(full list in `styles/_mapping.py`). Dark-background candidates for the app's dark panes:
`monokai` (bg `#272822`), `native` (`#202020`, vim-like), `dracula`, `github-dark`, `gruvbox-dark`,
`nord`, `one-dark`. Light panes: `default`, `vs`, `xcode`, `friendly`.

Custom style = subclass `Style` with `background_color`, `highlight_color`, `line_number_*`, and a
`styles = {Token: "…"}` dict; values are space-separated `bold nobold italic underline bg:#rrggbb
border:#rrggbb roman sans mono #rgb #rrggbb ansi*color noinherit transparent var(…)` (validated by
`StyleMeta`; bad values assert). Introspect per-token with `style_for_token(ttype)` →
`{color, bold, italic, underline, bgcolor, border, roman, sans, mono, ansicolor, bgansicolor}` —
this is the bridge for Flet `TextSpan` rendering (see below). Verified shape on `MonokaiStyle` /
`NativeStyle`.

### Tokens — `pygments.token`

`Token` root; main branches `Text(.Whitespace) Escape Error Other Keyword* Name* Literal(String Number)
Punctuation Operator Comment* Generic*`. `ttype in parent` tests membership (`is_token_subtype` is the
legacy alias); `string_to_tokentype('String.Double')` parses names. `STANDARD_TYPES` maps every standard
type to its CSS short class (`k kc kd kn … n na nb … s s2 se … m mi … c c1 cm … gd gi gh gp gs gt …` —
full table in `token.py`). Rule of thumb for span mapping: walk `ttype.split()` / `.parent` chain until a
styled ancestor is found (exactly what `TerminalFormatter._get_color` does).

### Filters — `pygments.filters` (8 builtins in `FILTERS`)

Attach via lexer option `filters=[...]` or `lexer.add_filter(name_or_instance, **opts)`:

| Name | Class | Options → use |
|---|---|---|
| `codetagify` | `CodeTagFilter` | `codetags=[XXX TODO FIXME BUG NOTE]` → re-emits hits as `Comment.Special` (log-pane TODO highlighting) |
| `highlight` | `NameHighlightFilter` | `names=[...]`, `tokentype=Name.Function` (or string) → recolor exact identifiers, e.g. ffmpeg flags `-crf -preset -vf -c:v` as `Keyword` |
| `keywordcase` | `KeywordCaseFilter` | `case='lower'│'upper'│'capitalize'` |
| `whitespace` | `VisibleWhitespaceFilter` | `spaces/tabs/newlines` (char or bool → `· » ¶`), `tabsize=8`, `wstokentype=True` |
| `gobble` | `GobbleFilter` | `n=int` — strip N leading chars per line (indented/prefixed logs) |
| `tokenmerge` | `TokenMergeFilter` | none — coalesce adjacent same-type tokens (fewer `TextSpan`s) |
| `raiseonerror` | `RaiseOnErrorTokenFilter` | `excclass=ErrorToken` — strict mode for parser tests |
| `symbols` | `SymbolFilter` | `lang='isabelle'│'latex'` — math escapes → unicode |

Plugin authors register more via the `pygments.filters` entry-point group.

## App usage & correctness

**(a) Dependency chain (verified).** `src/`, `tests/`, `tools/` contain **zero** `pygments` /
`pygmentize` references. The chain is indirect: `rich 15.0.0` is installed (transitive — not a direct
`pyproject` dep) and `rich/syntax.py` imports `pygments.lexer.Lexer`, `get_lexer_by_name`,
`guess_lexer_for_filename`, `get_style_by_name`, token types and `ClassNotFound` — i.e.
**`rich.Syntax` highlights through Pygments when a lexer/style is available, falling back
gracefully when not.** `pillow 12.3.0` is likewise present, so `ImageFormatter` is functional if ever
needed. Neither `rich.Syntax`/`Console` nor any Pygments API is currently exercised by the app.

**(b) Misuse: none** — there is no direct usage to misuse. Two adjacent correctness notes:
`src/screens/terminal_screen.py` (283 lines) renders the Expert Terminal transcript as plain `ft.Text`
rows with a fixed 6-entry `_LEVEL_COLORS` map (`err/note/plan/ok/in/info`) — level-colored, not
syntax-highlighted. `src/services/command_parser.py` ships its own quote-aware `tokenize()` (avoids
`shlex` eating `C:\…` backslashes) plus `parse_command()` → `OpPlan(summary/notes)` with loud
`CommandError` refusal — the parse/record path is sound; only presentation is unhighlighted.

**(c) Underuse ( haut-le-cœur gap).** The Activity Terminal (`src/core/logger_handler.py`:
`MemoryLogHandler`, 500-record ring) and the Expert Terminal output pane both render monochrome
`ft.Text`. Everything in the previous section is available but unused.

## Underused APIs to adopt

All suggestions are presentation-layer only (no parser/engine changes). Flet `ft.Text` ignores ANSI
escapes, so terminal formatters are for export/debug — **in-app highlighting must map the token
stream to `ft.TextSpan`s** (pattern below):

```python
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
import flet as ft

lexer = get_lexer_by_name("bash", stripall=True)  # ffmpeg command lines
style = get_style_by_name("monokai")  # or "native"/"dracula" for dark panes
spans = []
for ttype, value in lexer.get_tokens(cmd):
    fg = style.style_for_token(ttype)["color"]
    spans.append(
        ft.TextSpan(
            value,
            style=ft.TextStyle(
                color=f"#{fg}" if fg else None,
                weight=ft.FontWeight.BOLD if style.style_for_token(ttype)["bold"] else None,
            ),
        )
    )
ft.Text(spans=spans, font_family="Roboto Mono", selectable=True)
```

1. **Command preview** (`terminal_screen.py` input echo + `$ cmd` history): `BashLexer(stripall=True)`
   + `NameHighlightFilter(names=["-i","-ss","-t","-to","-c:v","-c:a","-crf","-preset","-vf","-af","-map"…],
   toktentype="Keyword")` so flags pop vs paths/values; append `tokenmerge` to keep span counts low on
   mobile. `BashSessionLexer` for `$ cmd` + output transcripts.
2. **Before/after param diffs:** `DiffLexer` — `Generic.Inserted/Deleted/Heading` already separate
   added/removed/context lines; map to SUCCESS/ERROR/muted spans.
3. **Crash-report snippets:** `PythonTracebackLexer` (`pytb`) — `Generic.Traceback` + `Name.Exception`
   tokens give file/line/exception structure for the result/error screens.
4. **ffprobe output:** `JsonLexer` for probe JSON panes (probe/dossier screens).
5. **Activity Terminal:** `codetagify` filter surfaces TODO/FIXME/BUG/NOTE in log comments; `gobble`
   strips fixed indent/prefixes from engine lines before display.
6. **Export/share:** `HtmlFormatter(noclasses=True, linenos="table", hl_lines=[…])` for a self-contained
   shareable command transcript; `Terminal256Formatter(style="monokai")` for desktop-CLI debug dumps
   (never feed its ANSI output into `ft.Text`).
7. **Testing:** `TestcaseFormatter` generates golden token-assertion blocks for command-tokenizer
   regression tests; `raiseonerror` filter makes parser-highlight tests strict.

## Gotchas

1. **No ffmpeg lexer exists** — confirmed by full `lexers/` grep. `BashLexer` is the stand-in; exact
   flag semantics still belong to `command_parser.py`, never to lexer output.
2. **`lex()`/`format()` take instances, not classes** — both raise a helpful `TypeError` if given one.
3. **`ft.Text` cannot render ANSI** — `Terminal*/IRCFormatter` output shows raw escapes in-app. Always
   convert via `style_for_token` → `TextSpan` for on-screen use.
4. **`TerminalFormatter` ignores `style=`** (hardcoded 16-color map + `bg` light/dark switch); only
   `Terminal256Formatter`/`TerminalTrueColorFormatter` honor styles. Match formatter to capability:
   16m on modern mobile terminals, 256 as fallback.
5. **`guess_lexer()` is O(all lexers)** and consults vim modelines first — prefer `get_lexer_by_name`
   with a fixed alias; never run guess per keystroke or per log line. Lexer instances are cheap but
   not documented thread-safe — create per call or cache per isolate.
6. **Defaults mutate text:** `stripnl=True, ensurenl=True` add/remove newlines — set
   `stripnl=False, ensurenl=False` when offsets must round-trip to the original string.
7. **`encoding='guess'` falls back to latin-1** (never fails, may mojibake); decode bytes yourself
   (UTF-8) before lexing engine output.
8. **`load_lexer_from_file` / `load_formatter_from_file` are `exec()`** — never load user-supplied
   paths (terminal input must never reach them).
9. **`ImageFormatter` needs Pillow + a real font** (`fc-list` lookup on Linux, registry on Windows);
   on Android the default-font probe can fail — bundle `font_name=` explicitly or avoid image export.
10. **Transitive-only dependency** — pin `pygments` directly before v1, or a future `rich` bump could
    drop it. BSD-2-Clause is permissive; `pygmentize` CLI is also available on dev machines for
    offline lexer/style experiments (`-L`, `-S monokai`, `-O style=native`).
