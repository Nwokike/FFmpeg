# markdown-it-py 4.2.0 — Complete API Reference

> CommonMark-compliant Markdown parser. Python port of
> [markdown-it](https://github.com/markdown-it/markdown-it) (JS v14.1.0,
> commit `0fe7ccb`, see `port.yaml`). Import name: `markdown_it`.
> Public surface is exactly one name: `from markdown_it import MarkdownIt`
> (`__init__.py` exports only `MarkdownIt`; `__version__ = "4.2.0"`).

---

## Files

Package dir (read-only): `.venv/Lib/site-packages/markdown_it/` — 45 `.py`
files (no `plugins/` package; no `rules_block/__init__`-style alias modules
beyond what is listed). Layout:

| Path | Role |
|---|---|
| `__init__.py` | `__all__ = ("MarkdownIt",)`, re-exports `main.MarkdownIt` |
| `main.py` | `MarkdownIt` class + `_PRESETS` registry |
| `parser_core.py` / `parser_block.py` / `parser_inline.py` | `ParserCore`, `ParserBlock`, `ParserInline` |
| `ruler.py` | `Ruler`, `Rule`, `StateBase`, `RuleOptionsType` |
| `renderer.py` | `RendererProtocol`, `RendererHTML` |
| `token.py` | `Token` dataclass (+ `convert_attrs`) |
| `tree.py` | `SyntaxTreeNode` (Python-only, not in upstream JS) |
| `utils.py` | `OptionsType`, `OptionsDict`, `PresetType`, `EnvType`, `read_fixture_file` |
| `rules_core/` | `normalize`, `block`, `inline`, `linkify`, `replacements` (`replace`), `smartquotes`, `text_join`, `state_core.StateCore` |
| `rules_block/` | `table`, `code`, `fence` (+`make_fence_rule`), `blockquote`, `hr`, `list` (exports `list_block`), `reference`, `html_block`, `heading`, `lheading`, `paragraph`, `state_block.StateBlock` |
| `rules_inline/` | `text`, `linkify`, `newline`, `escape`, `backticks` (exports `backtick`), `strikethrough`, `emphasis`, `link`, `image`, `autolink`, `html_inline`, `entity`, `balance_pairs` (exports `link_pairs`), `fragments_join`, `state_inline.StateInline` |
| `presets/` | `commonmark`, `default`, `zero` (+ aliases `js_default = default`, `gfm_like`, `gfm_like2` defined inline in `presets/__init__.py`) |
| `common/` | `normalize_url` (uses `mdurl`), `utils` (char/escape/entity helpers), `entities.py` (HTML entity table), `html_blocks.py`, `html_re.py` |
| `helpers/` | `parseLinkDestination`, `parseLinkLabel`, `parseLinkTitle` (link-syntax scanners) |
| `cli/parse.py` | `markdown-it` console script (`main`, `convert`, `convert_stdin`, `convert_file`, `interactive`, `parse_args`) |
| `port.yaml` | upstream port notes (diffs from JS: `Token.attrs` is a `dict`, `env` is a plain `dict`, render signature `func(self, tokens, idx, options, env)`, default preset is `"commonmark"` not `"default"`) |
| `_compat.py`, `_punycode.py`, `py.typed` | compat shims, IDNA encoder, PEP-561 marker |

Note: there is **no** `front_matter` / `strobe` / built-in plugin package —
plugins live in the separate `mdit-py-plugins` distribution (not installed).

## Metadata

From `markdown_it_py-4.2.0.dist-info/METADATA` (+ `RECORD`, `WHEEL`,
`entry_points.txt`, `licenses/{LICENSE,LICENSE.markdown-it}`):

- **Version** `4.2.0`, `Requires-Python: >=3.10`, status Production/Stable.
- **License**: MIT (`License-File: LICENSE`, `LICENSE.markdown-it`).
  Classifier `License :: OSI Approved :: MIT License`.
- **Runtime pin** (only one): `Requires-Dist: mdurl~=0.1`
  (installed: `mdurl 0.1.2`). Used by `common/normalize_url.py` for
  `normalizeLink` / `normalizeLinkText`.
- **No `typing_extensions` pin** in 4.2.0 metadata (`utils.py` imports
  `NotRequired` under `TYPE_CHECKING` only). `typing_extensions 4.16.0`
  happens to be installed but is not required by this package.
- **Extras**: `benchmarking` (psutil/pytest/pytest-benchmark),
  `compare` (commonmark/markdown/mistletoe/mistune/panflute/markdown-it-pyrs),
  **`linkify`** (`linkify-it-py>=1,<3`), **`plugins`**
  (`mdit-py-plugins>=0.5.0`), `profiling` (gprof2dot),
  `rtd` (sphinx stack + myst-parser + mdit-py-plugins), `testing`
  (coverage/pytest/pytest-cov/pytest-regressions/pytest-timeout/requests).
- **Extras installed in this venv: NONE.** No `linkify-it-py`, no
  `mdit-py-plugins`. Only `mdurl` is present.
- **Console script**: `markdown-it=markdown_it.cli.parse:main`
  (`Scripts/markdown-it.exe` in RECORD).
- Keywords: markdown, lexer, parser, commonmark, markdown-it.

## Module-by-module API

### `MarkdownIt` (`main.py`) — constructor

```python
MarkdownIt(
    config: str | PresetType = "commonmark",
    options_update: Mapping[str, Any] | None = None,
    *,
    renderer_cls: Callable[[MarkdownIt], RendererProtocol] = RendererHTML,
)
```

- `config`: preset name — `"commonmark"` (default), `"default"`,
  `"js-default"`, `"zero"`, `"gfm-like"`, `"gfm-like2"` — or a full
  `PresetType` dict (`{"options": {...}, "components": {...}}`).
- `options_update`: merged over the preset's `options`
  (e.g. `MarkdownIt("commonmark", {"html": False})`).
- `renderer_cls`: custom renderer class; instance stored as `self.renderer`.
- Sub-objects created in `__init__`: `self.inline: ParserInline`,
  `self.block: ParserBlock`, `self.core: ParserCore`,
  `self.linkify` (`linkify_it.LinkifyIt()` or `None` when not installed),
  plus `self.utils` / `self.helpers` module handles.
- Unknown preset raises `KeyError`; empty config raises `ValueError`.

### `MarkdownIt` — methods (all chainable where noted)

| Method | Signature | Notes |
|---|---|---|
| `set` | `set(options: OptionsType) -> None` | Replace options wholesale (discouraged on the fly — create separate instances). |
| `configure` | `configure(presets: str \| PresetType, options_update=None) -> MarkdownIt` | Apply preset `components` via `ruler.enableOnly(rules)` per chain. |
| `get_all_rules` | `-> dict[str, list[str]]` (`core`/`block`/`inline`/`inline2`) | Every registered rule. |
| `get_active_rules` | `-> dict[str, list[str]]` | Only enabled rules. |
| `enable` | `enable(names: str \| Iterable[str], ignoreInvalid=False) -> MarkdownIt` | Search core/block/inline/inline2 rulers. Raises `ValueError` on unknown unless `ignoreInvalid`. |
| `disable` | same | Same mechanics, disables. E.g. `.disable("html_inline")`. |
| `reset_rules` | `@contextmanager reset_rules() -> Generator[None,None,None]` | Snapshot active rules, `yield`, restore on exit (testing/sandboxing). |
| `add_render_rule` | `add_render_rule(name: str, function: Callable, fmt: str = "html") -> None` | Only applied when `renderer.__output__ == fmt`; binds as renderer method (`function.__get__(self.renderer)`). |
| `use` | `use(plugin: Callable[..., None], *params, **options) -> MarkdownIt` | Sugar for `plugin(md, *params, **options)`. |
| `parse` | `parse(src: str, env: EnvType \| None = None) -> list[Token]` | Block token stream; `env` must be a `MutableMapping` (default `{}`). |
| `render` | `render(src: str, env=None) -> Any` | `renderer.render(parse(src, env), options, env)` → HTML `str` with default renderer. |
| `parseInline` | `parseInline(src, env=None) -> list[Token]` | `inlineMode=True`; single `inline` token with `children`. |
| `renderInline` | `renderInline(src, env=None) -> Any` | No wrapping `<p>` tags. |
| `validateLink` | `validateLink(url: str) -> bool` | XSS guard: blocks `vbscript:`/`javascript:`/`file:`/`data:` except `data:image/(gif\|png\|jpeg\|webp)`. |
| `normalizeLink` | `normalizeLink(url: str) -> str` | mdurl-based URL normalization (punycode host). |
| `normalizeLinkText` | `normalizeLinkText(link: str) -> str` | Display-form normalization (unicode host). |
| `__getitem__` | `md["inline"\|"block"\|"core"\|"renderer"]` | Typed overloads for the four sub-objects. |

Examples:

```python
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark", {"html": False})
md.enable(["table", "strikethrough"]).disable("smartquotes")
html = md.render("# Hi **there**")  # '<h1>Hi <strong>there</strong></h1>\n'
inline = md.renderInline("a *b* c")  # 'a <em>b</em> c' (no <p>)
tokens = md.parse("hello", env := {})  # env gains {"references": {...}}
with md.reset_rules():  # temporary rule tweaks
    md.disable("link")
```

`copy()` does **not** exist in this version — create a second `MarkdownIt`
instance instead (the documented recommendation for multiple configs).

### Presets — rule lists

**`commonmark`** (the constructor default): `maxNesting 20`, `html True`,
`xhtmlOut True`, rest off. core `normalize/block/inline/text_join`;
block = `blockquote, code, fence, heading, hr, html_block, lheading, list,
reference, paragraph`; inline =
`autolink, backticks, emphasis, entity, escape, html_inline, image, link,
newline, text`; inline2 = `balance_pairs, emphasis, fragments_join`.

**`default`** (upstream JS default): `maxNesting 100`, everything off
(`html False`, `xhtmlOut False`), **empty `components`** (`{"core": {},
"block": {}, "inline": {}}`) — rules are whatever the parsers register,
untouched by `enableOnly`. Practically: the full built-in rule set.

**`zero`**: `maxNesting 20`, everything off; core same four; block =
`["paragraph"]` only; inline = `["text"]`, inline2 =
`["balance_pairs", "fragments_join"]`. Start here for minimal modes
(e.g. bold/italic only: `MarkdownIt("zero").enable(["emphasis"])`).

**`gfm-like`** = commonmark + core `linkify`, block `table`, inline
`strikethrough, linkify` + inline2 `strikethrough`; sets
`linkify True, html True`.
**`gfm-like2`** = gfm-like + options-only extensions processed inside
existing rules: `tasklists` (checkbox detection in `rules_block/list.py`;
`tasklists_editable` controls the `disabled` attr), `alerts`
(`> [!NOTE]` detection in `rules_block/blockquote.py`),
`strikethrough_single_tilde` (`rules_inline/strikethrough.py`).

### Option table (`utils.OptionsType` / `OptionsDict`)

| Option | Type | commonmark | default/zero | Used by |
|---|---|---|---|---|
| `maxNesting` | `int` | 20 | 100 / 20 | block tokenizer recursion guard |
| `html` | `bool` | True | False | shorthand for enabling `html_block`/`html_inline` rules |
| `linkify` | `bool` | False (True in gfm-like) | False | core `linkify` rule; needs `linkify-it-py` or raises `ModuleNotFoundError` |
| `typographer` | `bool` | False | False | enables core `replacements` + `smartquotes` |
| `quotes` | `str` | `"\u201c\u201d\u2018\u2019"` | same | smartquotes open/close pairs (locale-customizable) |
| `xhtmlOut` | `bool` | True | False | `<br />` vs `<br>`, ` /` on self-closing tags |
| `breaks` | `bool` | False | False | `\n` in paragraphs → `<br>` |
| `langPrefix` | `str` | `"language-"` | same | `class="language-<lang>"` on fenced code |
| `highlight` | `(str, str, str) -> str \| None` | None | None | `(content, langName, langAttrs)`; `""`/None → escape; return starting with `<pre` skips wrapper |
| `store_labels` | `bool` (opt) | — | — | store link/image label in `Token.meta["label"]` (round-trip parsing) |
| `tasklists` / `tasklists_editable` | `bool` (opt, gfm-like2) | — | — | `- [x]` checkboxes → `token.meta["checked"]`; editable omits `disabled` |
| `alerts` | `bool` (opt, gfm-like2) | — | — | `> [!NOTE]` → `alert_open/alert_title_open/...` token family |
| `strikethrough_single_tilde` | `bool` (opt, gfm-like2) | — | — | `~text~` in addition to `~~text~~` |

`OptionsDict` exposes the 9 core options as attribute properties
(`md.options.html`, `md.options.breaks`, …) plus full `MutableMapping`
behaviour.

### Token structure (`token.py`)

```python
@dataclass(slots=True)
class Token:
    type: str  # e.g. "paragraph_open", "inline", "fence"
    tag: str  # HTML tag, e.g. "p", "h1", ""
    nesting: Literal[-1, 0, 1]  # 1 open / 0 self-closing / -1 close
    attrs: dict[str, str | int | float] = {}  # NB: dict (upstream JS uses list-of-lists)
    map: list[int] | None = None  # [line_begin, line_end] source map
    level: int = 0
    children: list[Token] | None = None  # inline children / image alt tokens
    content: str = ""  # code/html/fence/text payload
    markup: str = ""  # e.g. "*" / "```" / "linkify"
    info: str = ""  # fence info string; "auto" for autolinks; list-item marker
    meta: dict[Any, Any] = {}  # plugin sandbox (tasklist "checked", labels…)
    block: bool = False
    hidden: bool = False  # tight-list paragraph suppression
```

Helpers: `attrGet/attrSet/attrPush/attrJoin(name, value)` (preferred API;
`attrIndex` warns — dict has no stable index),
`copy(**changes)`, `as_dict(children=True, as_upstream=True, …)` /
`from_dict` round-trip.

**Every emitted token type** (via `StateBlock.push`): `alert_open/_close,
alert_title_open/_close, blockquote_open/_close, bullet_list_open/_close,
code_block, code_inline, definition, hardbreak, heading_open/_close,
hr, html_block, html_inline, image, inline, link_open/_close,
list_item_open/_close, ordered_list_open/_close, paragraph_open/_close,
softbreak, table_open/_close, tbody_open/_close, td_open/_close,
text, text_special (pre-`text_join`), th_open/_close, thead_open/_close,
tr_open/_close, fence`. Heading levels ride on `tag` (`h1`–`h6`);
task-list state on `meta["checked"]`; image alt text in `children`.

### Renderer (`renderer.py`) — rules & custom hooks

- `RendererProtocol`: `__output__: ClassVar[str]` + `render(tokens, options,
  env)`. `RendererHTML.__output__ = "html"`.
- `RendererHTML.render(tokens, options, env)`: `inline` tokens recurse via
  `renderInline(children)`; known `type` → `self.rules[type]`; unknown →
  generic `renderToken` (tag + escaped attrs + `xhtmlOut` slash + block
  newline logic; returns `""` for `hidden` tokens).
- Per-type methods populating `self.rules` at `__init__` (anything not
  starting with `render`/`_`): `list_item_open` (task-list checkbox),
  `code_inline`, `code_block`, `fence` (info-string split + `highlight` +
  `langPrefix` injection), `image` (CommonMark `alt` via
  `renderInlineAsText`), `hardbreak`, `softbreak`, `text`,
  `html_block`, `html_inline`.
- Three custom-render hooks:
  1. `md.add_render_rule("fence", fn)` — `fn(renderer, tokens, idx,
     options, env) -> str` (note: bound-method signature, *not* the JS
     `(tokens, idx, options, env, self)` order).
  2. Subclass `RendererHTML` (override e.g. `strong_open`) and pass
     `renderer_cls=…` to the constructor.
  3. Fresh `RendererProtocol` with a different `__output__` for non-HTML
     targets (terminal/console text, Flet spans).
- `renderAttrs` / `renderInlineAsText` are reusable statics/instance helpers.

### Rules, Ruler, states, env

- **Core chain** (`parser_core._rules`, in order): `normalize` (newline/CR
  + NULL → `\uFFFD`), `block`, `inline`, `linkify` (no-op unless
  `options.linkify`), `replacements` (`(c)→©`, `(tm)→™`, `+-→±`, `...→…`,
  `---→—` em/en dashes, …), `smartquotes` (`'`/`"` → locale `quotes` pairs),
  `text_join` (`text_special` folding).
- **Block rules** (registration order): `table, code, fence, blockquote, hr,
  list, reference, html_block, heading, lheading, paragraph`.
- **Inline rules**: `text, linkify, newline, escape, backticks, strikethrough,
  emphasis, link, image, autolink, html_inline, entity`; **inline2**
  post-processing: `balance_pairs, strikethrough, emphasis, fragments_join`.
- `Ruler` API per chain (`md.block.ruler`, `md.inline.ruler`,
  `md.inline.ruler2`, `md.core.ruler`): `push / before / after / at /
  enable / disable / enableOnly / getRules(chain="") / get_all_rules /
  get_active_rules`.
- Rule signatures: core `(StateCore) -> None`; block
  `(StateBlock, startLine, endLine, silent) -> bool`; inline
  `(StateInline, silent) -> bool`; inline2 `(StateInline) -> None`.
- `env` keys written by built-ins: `env["references"]` (`{label: {href,
  title, map, …}}`) + `env["duplicate_refs"]` (reference rule); everything
  else is plugin/user space. `env` **must be a `MutableMapping`** —
  passing anything else raises `TypeError`.
- `SyntaxTreeNode(tokens)` (in `tree.py`): root/nested tree over the flat
  stream; `node.type` (with `_open` stripped), `.children`, `.walk()`,
  `.pretty(indent, show_text)`, `.to_tokens()`, token-passthrough
  properties (`.tag/.attrs/.map/.content/.markup/.info/.meta/…`).
- `helpers`: `parseLinkDestination(str, pos, max)`,
  `parseLinkLabel(state, start, disableNested=False)`,
  `parseLinkTitle(...)` — building blocks for custom link-like syntax.
- `make_fence_rule(*, markers=("~","`"), token_type="fence",
  exact_match=False, disallow_marker_in_info=("`",), min_markers=3)` —
  factory for custom fenced constructs (e.g. `colon_fence`).
- CLI: `markdown-it [--stdin] [files…]` → HTML on stdout; interactive REPL
  with no args.

### Plugins & ecosystem — installed?

| Piece | Status in this venv |
|---|---|
| `mdit_py_plugins` (front_matter, footnote, tasklists, colon_fence, deflist, texmath, …) | **NOT installed** (`plugins` extra unmet) |
| `linkify-it-py` (auto-URL linking; option `linkify`) | **NOT installed** (`linkify` extra unmet); enabling raises `ModuleNotFoundError("Linkify enabled but not installed.")` |
| `mdurl~=0.1` | installed `0.1.2` — hard requirement, present |
| `pygments 2.21.0` | installed (directly, not via markdown-it) — usable as `highlight=` backend |

## App usage & correctness

(a) **Dependency chain** (verified in `uv.lock` + source greps over
`src/`, `tests/`, `tools/`):

- `pyproject.toml` does **not** list `markdown-it-py` as a direct
  dependency. It arrives **transitively**.
- `rich 15.0.0` is present in the venv and **does** use it:
  `rich/markdown.py` does `from markdown_it import MarkdownIt` and builds
  `MarkdownIt().enable("strikethrough").enable("table")` for
  `rich.Markdown`. **BUT** — `rich` itself is **dev-only** in this project:
  required by `flet-cli`, `flet-desktop` (dependency group `dev`), and
  `cookiecutter` — not by the shipped `flet 1.0.0` runtime, which depends
  only on `httpx/msgpack/oauthlib/repath`. **No file under `src/`,
  `tests/`, or `tools/` imports `rich` or `markdown_it`** (grep confirms
  zero hits).
- So the true chain is: `markdown-it-py` ← `rich` ← (`flet-cli` /
  `flet-desktop` dev tooling). The **shipped app never parses Markdown with
  it today**.

(b) **Misuse**: none — it is not called at all, so nothing is misused.
Closest risks to avoid when adopting: enabling `linkify` without adding
`linkify-it-py` (runtime `ModuleNotFoundError`); enabling `html: True`
then injecting rendered HTML anywhere raw (XSS — prefer `validateLink` +
  `html: False` still allows `html_block` only if the rule is enabled… in
  the `commonmark` preset HTML passes through, so never put `md.render()`
  output into an unescaped sink).

(c) **Markdown flows in the app that currently bypass markdown-it-py**:

- `src/core/changelog.py` — `CHANGELOG` dict of Markdown strings +
  `notes_for(version)`.
- `version.json` — `release_notes` (plain-text bullets today).
- `src/components/update_dialog.py` — renders those notes with
  `ft.Markdown(notes, extension_set=GITHUB_WEB, on_tap_link=…)` inside an
  `AlertDialog`. Flet's `Markdown` is a **native/Flutter-side renderer** —
  it does not call markdown-it-py; compatibility is at the syntax level.
- `src/screens/probe_screen.py::build_media_report` — builds a Markdown
  dossier string (`#`, `##`, backticked codecs, chapters) for the share
  sheet; asserted in `tests/test_remux_dossier.py` (starts with `#`,
  contains `## Streams`, backticks, `## Chapters`).

## Underused APIs to adopt

For v1 (no app-source changes made — proposals only):

1. **Validate the changelog / release notes before display.**
   `update_dialog` feeds bundled strings + network `release_notes`
   straight into `ft.Markdown`. A 3-line guard with
   `MarkdownIt("commonmark").parse(notes)` catches unbalanced fences /
   broken tables before they hit the dialog, and `renderInline` can
   produce a plain-text fallback for notifications/snacks.
2. **Smoke-test `build_media_report` output.** `tests/test_remux_dossier.py`
   asserts substrings; adding `MarkdownIt("commonmark").render(report)`
   (must contain `<h1>`, `<table>`-free `<ul>`, no raw `[](...)` leftovers)
   guarantees the shared dossier renders everywhere it is pasted
   (GitHub, mail, chat).
3. **Normalize `version.json` release notes.** Server notes are `•`-bullet
   plain text while bundled notes are `#`/`-` Markdown. One shared
   `MarkdownIt("zero").enable(["emphasis","link","newline"])` pass (or a
   bullet-normalizer on the token stream) unifies both feeds into the same
   `ft.Markdown`-safe dialect.
4. **Syntax-highlight fenced code blocks.** `pygments 2.21.0` is already
   installed — wire it as `options.highlight` so any in-app "show as HTML"
   path (share sheet, dossier export) emits highlighted code instead of
   plain `<pre><code>`.
5. **GFM parity for the update dialog.** `ft.Markdown` uses
   `GITHUB_WEB`/`GITHUB_FLAVORED`; the authoring side should match:
   `MarkdownIt("gfm-like2")` gives tables + strikethrough + tasklists +
   alerts for linting content destined for that control.
6. **Token-stream linting via `SyntaxTreeNode`.** Walk the changelog/report
   trees in tests: assert heading hierarchy (`h1` once), no `html_block`
   tokens (store policy), every `link_open` passes `validateLink`.
7. **Terminal output.** If any dev tool (`tools/`, future CLI diagnostics)
   pretty-prints Markdown to the console, `rich.Markdown` (already in the
   dev closure, strikethrough+tables enabled) is the zero-cost path — no
   new dependency needed — or a tiny custom `RendererProtocol` for
   Flet-span/plain-text targets.

## Gotchas

- Default preset is `"commonmark"`, **not** `"default"` (differs from JS).
  `MarkdownIt()` ≠ `MarkdownIt("default")` (maxNesting 20 vs 100, html on).
- `options_update` requires the preset positionally first:
  `MarkdownIt("commonmark", {"html": False})` — `MarkdownIt({"html":
  False})` raises `TypeError` (guarded explicitly).
- `Token.attrs` is a **dict**, upstream is list-of-lists. `attrIndex` only
  warns; use `attrGet/Set/Push/Join`. `as_dict(as_upstream=True)` converts
  back for snapshots.
- `add_render_rule` binds `fn` as a renderer method: signature is
  `(self, tokens, idx, options, env)` after binding — the JS 5-arg order
  does not apply.
- `env` must be a `MutableMapping`; `parse`/`render` raise `TypeError`
  otherwise. Share one `env` between `parse` and a later `render` only if
  you re-pass the same object.
- `linkify=True` without `linkify-it-py` installed raises
  `ModuleNotFoundError` at parse time (not at construction).
- Plugin package is separate: no `front_matter`/`footnote`/… without
  installing `mdit-py-plugins>=0.5.0`.
- `fence` renderer trusts `options.highlight` output as raw HTML; a
  highlighter must escape itself (return `""`/None to fall back to
  `escapeHtml`).
- `validateLink` allowlists `data:image/(gif|png|jpeg|webp)` only — other
  `data:` URIs are dropped; `vbscript:/javascript:/file:` always dropped.
- `reset_rules` is a context manager, not a reset method — misuse as a
  plain call silently does nothing.
- Performance: don't mutate `md.options` per-render; keep one instance per
  config (documented in `set()`). `text_join`/`ParserInline` fast paths
  assume the default terminator set — `add_terminator_char` costs a recompile.
- No `MarkdownIt.copy()` in 4.2.0 — construct a new instance for variant
  configs.
