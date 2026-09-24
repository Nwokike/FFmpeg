# Jinja2 3.1.6 — Complete API Reference

> Fast, expressive, extensible template engine (pure Python, Pallets). Templates compile to optimized Python code JIT and cache. Used in this repo **only transitively**: `flet-cli` (dev dep) → `cookiecutter 2.7.1` → `jinja2 3.1.6`, for `flet create`/`flet build` project-template rendering. No app code imports it today.

## Files

Package dir: `.venv/Lib/site-packages/jinja2` — 25 `.py` files, ~14,425 lines total (excl. `__pycache__`). Note: the real layout differs slightly from older docs — loaders live in `loaders.py` (not `loader.py`), async helpers in `async_utils.py` (not `asyncutils.py`), and there is **no** `template.py` (`Template`, `TemplateModule`, `TemplateStream`, `TemplateExpression` all live in `environment.py`).

| File | Lines | Contents |
|---|---|---|
| `__init__.py` | 38 | Public re-exports, `__version__ = "3.1.6"` |
| `_identifier.py` | 6 | Identifier-validity regex |
| `async_utils.py` | 99 | `async_variant`, `auto_await`, `auto_aiter`, `auto_to_list` |
| `bccache.py` | 408 | `Bucket`, `BytecodeCache`, `FileSystemBytecodeCache`, `MemcachedBytecodeCache` |
| `compiler.py` | 1998 | `CodeGenerator`, `Frame`, dependency visitors, `generate()` |
| `constants.py` | 20 | `LOREM_IPSUM_WORDS` |
| `debug.py` | 191 | `rewrite_traceback_stack`, `fake_traceback` — maps tracebacks to template lines |
| `defaults.py` | 48 | Delimiters, `DEFAULT_NAMESPACE`, `DEFAULT_POLICIES` |
| `environment.py` | 1672 | `Environment`, `Template`, `TemplateModule`, `TemplateExpression`, `TemplateStream` |
| `exceptions.py` | 166 | Full `TemplateError` family (below) |
| `ext.py` | 870 | `Extension`, `InternationalizationExtension`, `ExprStmtExtension`, `LoopControlExtension`, `DebugExtension`, `extract_from_ast`, `babel_extract` |
| `filters.py` | 1873 | ~60 filter impls + `FILTERS` dict |
| `idtracking.py` | 318 | `Symbols`, `RootVisitor`, `FrameSymbolVisitor` (scope analysis) |
| `lexer.py` | 868 | `Lexer`, `Token`/`TokenStream`, `get_lexer` (cached) |
| `loaders.py` | 693 | 8 loader classes |
| `meta.py` | 112 | `find_undeclared_variables`, `find_referenced_templates` |
| `nativetypes.py` | 130 | `NativeEnvironment`, `NativeTemplate`, `native_concat` |
| `nodes.py` | 1206 | AST node classes, `EvalContext`, `NodeVisitor` |
| `optimizer.py` | 48 | Constant-folding pass (`as_const`) |
| `parser.py` | 1049 | `Parser` — full tag/statement grammar |
| `runtime.py` | 1062 | `Context`, `BlockReference`, `LoopContext`, `AsyncLoopContext`, `Macro`, `Undefined` ×4, `make_logging_undefined` |
| `sandbox.py` | 436 | `SandboxedEnvironment`, `ImmutableSandboxedEnvironment`, `unsafe`, guards, formatters |
| `tests.py` | 256 | ~25 test impls + `TESTS` dict |
| `utils.py` | 766 | `pass_context`/`pass_environment`/`pass_eval_context`, `select_autoescape`, `LRUCache`, `Cycler`, `Joiner`, `Namespace`, `htmlsafe_json_dumps`, `urlize`, `generate_lorem_ipsum`, … |
| `visitor.py` | 92 | `NodeVisitor` (`visit`/`generic_visit`) |

## Metadata

From `jinja2-3.1.6.dist-info/METADATA` (+ `WHEEL`, `RECORD` = 33 entries, `entry_points.txt` = `jinja2` Babel extractor, `licenses/LICENSE.txt`):

- **Version:** 3.1.6 (sdist 2025-03-05; wheel `py3-none-any`)
- **Requires-Python:** `>=3.7`
- **Requires-Dist:** `MarkupSafe>=2.0` (only hard dep); `Babel>=2.7 ; extra == "i18n"` (optional `i18n` extra)
- **License:** BSD — classifier `License :: OSI Approved :: BSD License`, `License-File: LICENSE.txt` (Pallets, 2007, redistribution permitted)
- **Typing:** ships `py.typed`; classifiers include `Typing :: Typed`, Production/Stable

## Module-by-module API

### `Environment` — constructor (all 22 params, pass by keyword)

```python
Environment(
    block_start_string="{}",
    variable_start_string="{{",  # … and _end/comment variants
    comment_start_string="{#",
    comment_end_string="#}",
    line_statement_prefix=None,
    line_comment_prefix=None,  # e.g. "#" for line statements
    trim_blocks=False,  # strip first newline after a block tag
    lstrip_blocks=False,  # strip leading whitespace before block tags
    newline_sequence="\n",  # one of "\n", "\r\n", "\r"
    keep_trailing_newline=False,
    extensions=(),  # import paths or Extension subclasses
    optimized=True,  # enable constant-folding optimizer
    undefined=Undefined,  # Undefined subclass for missing names
    finalize=None,  # finalize(value) post-processes every {{ … }} output
    autoescape=False,  # bool or callable(template_name|None) -> bool
    loader=None,
    cache_size=400,
    auto_reload=True,
    bytecode_cache=None,
    enable_async=False,
)
```

Key instance state: `filters` (copy of `FILTERS`), `tests`, `globals` (= `DEFAULT_NAMESPACE` copy: `range`, `dict`, `lipsum`, `cycler`, `joiner`, `namespace`), `policies` (copy of `DEFAULT_POLICIES`: `compiler.ascii_str=True`, `urlize.rel="noopener"`, `urlize.target=None`, `urlize.extra_schemes=None`, `truncate.leeway=5`, `json.dumps_function=None`, `json.dumps_kwargs={"sort_keys": True}`, `ext.i18n.trimmed=False`), `extensions`, `cache` (LRU/`dict`/None per `cache_size`: 0 = recompile always, <0 = never evict), `is_async`, `sandboxed=False`.

### `Environment` — methods

```python
env.from_string(source, globals=None, template_class=None) -> Template
env.get_template(name, parent=None, globals=None) -> Template          # raises TemplateNotFound
env.select_template(names, parent=None, globals=None) -> Template     # raises TemplatesNotFound
env.get_or_select_template(name_or_list, parent=None, globals=None)
env.compile(source, name=None, filename=None, raw=False, defer_init=False) -> CodeType | str
env.compile_expression(source, undefined_to_none=True) -> TemplateExpression  # expr(foo=1) -> value
env.parse(source, name=None, filename=None) -> nodes.Template         # AST, no codegen
env.lex(source, name=None, filename=None) -> TokenStream
env.preprocess(source, name=None, filename=None) -> str
env.call_filter(name, value, args=None, kwargs=None, context=None)
env.call_test(name, value, args=None, kwargs=None, context=None)
env.getattr(obj, attribute) / env.getitem(obj, argument)              # sandbox-aware in sandbox env
env.get_template_attribute(template_name, attribute)                  # one macro from a template
env.overlay(**overrides) -> Environment                               # copy sharing data + caches; extensions can only be added
env.extend(**attrs)                                                   # extensions register config/callbacks
env.add_extension(ext)
env.list_templates(extensions=None, filter_func=None) -> list[str]
env.compile_templates(target, extensions=None, filter_func=None, zip="deflated",
                      log_function=None, ignore_errors=True)          # AOT compile to dir (zip=None) or zip
env.join_path(template, parent) -> str                                # default: posix-style join
env.handle_exception(source=None) -> NoReturn                         # rewrites traceback to template lines, re-raises
env.is_async: bool;  env.lexer -> Lexer;  env.iter_extensions()
```

`TemplateExpression` example:

```python
expr = env.compile_expression("bitrate >= min_br")
expr(bitrate=8000, min_br=4000)  # True
env.compile_expression("missing")()  # None (undefined_to_none=True)
```

### `Template` — rendering

```python
t.render(*args, **kwargs) -> str            # dict or kwargs; sync; auto-runs coroutine if env is async
await t.render_async(*args, **kwargs) -> str
t.generate(*args, **kwargs) -> Iterator[str]        # piece-by-piece streaming
t.generate_async(*args, **kwargs) -> AsyncGenerator[str, object]
t.stream(*args, **kwargs) -> TemplateStream
t.new_context(vars, shared=False, locals=None) -> Context
t.make_module(vars=None, shared=False, locals=None) -> TemplateModule
await t.make_module_async(...)
t.module -> TemplateModule                  # cached default module
t.blocks, t.globals, t.name, t.filename
t.is_up_to_date -> bool;  t.debug_info;  t.get_corresponding_lineno(lineno)
Template(source, **env_kwargs)               # direct construction; shares a spontaneous env (lru_cache, max 10)
Template.from_code(environment, code, globals, uptodate=None)
Template.from_module_dict(environment, module_dict, globals)
```

`TemplateStream`: iterable/generator wrapper — `dump(fp, encoding=None, errors="strict")` writes to path or file object; `enable_buffering(size=5)` / `disable_buffering()`.

`TemplateModule`: imported template (`{% import "m.html" as m %}`) — exported names as attributes, `str(module)` renders body, `__html__()` returns `Markup` (**MarkupSafe type**).

`NativeTemplate`/`NativeEnvironment` (`jinja2.nativetypes`): `render()` returns a **native Python value** — single-node output returned as-is, else `ast.literal_eval` attempted, else string:

```python
from jinja2.nativetypes import NativeEnvironment

nenv = NativeEnvironment()
nenv.from_string("{{ [1, 2] }}").render()  # [1, 2]  (list, not "[1, 2]")
```

### Template language — inheritance, includes, macros

```jinja
{% extends "base.html" %}                     {# must be first tag; name may be a variable or list #}
{% block title %}Members{% endblock %}        {# override; {{ super() }} renders parent block #}
{{ self.title() }}                            {# TemplateReference: render a block by name #}
{% include ["local.html", "fallback.html"] %} {# str | list; ignore missing / without context variants #}
{% import "macros.html" as m %}{% from "m.html" import btn as button %}
{% macro btn(label, kind="primary") %}<button class="{{ kind }}">{{ label }}</button>{% endmacro %}
{% call m.dialog("hi") %}body via {{ caller() }}{% endcall %}
{% set x = 42 %}{% set ns = namespace(found=false) %}{% do mutate(x) %}
{% for u in users recursive %}{{ loop.index }}/{{ loop.length }} …{{ loop(u.children) }}{% endfor %}
{% if x is defined and x|int > 0 %}…{% elif %}…{% else %}…{% endif %}
{% with a=1 %}{% endwith %}{% filter upper %}…{% endfilter %}
{# comment #}  ## line comment (if line_comment_prefix set)  # line statements (if line_statement_prefix set)
```

`loop` (`LoopContext`): `index`/`index0`, `revindex`/`revindex0`, `first`, `last`, `length` (eagerly materializes generators), `depth`/`depth0`, `previtem`/`nextitem` (Undefined at edges), `cycle(*args)`, `changed(*values)`. Async variant `AsyncLoopContext` awaits lengths/items.

### Filters — complete list (58 names)

Every entry is `name: callable`. Signatures shown for the non-trivial ones (defaults to copy into examples):

| Filter | Signature / notes |
|---|---|
| `abs`, `count`/`length` (`len`), `attr` | `attr(obj, name)` |
| `batch` | `(value, linecount, fill_with=None)` → rows |
| `capitalize`, `upper`, `lower`, `title`, `trim(value, chars=None)`, `center(value, width=80)` | |
| `d`/`default` | `(value, default_value="", boolean=False)` — `boolean=True` also substitutes falsy values |
| `dictsort` | `(value, case_sensitive=False, by="key"\|"value")` |
| `escape`/`e` | MarkupSafe `escape` → **`Markup`** |
| `filesizeformat` | `(value, binary=False)` → `"13 kB"` — ideal for media sizes |
| `first`/`last`/`random` | return `Undefined` on empty (not IndexError); `random` needs context |
| `float`/`int` | `(value, default=0.0/0, base=10)` |
| `forceescape` | `(value)` → **`Markup`** (double-escapes) |
| `format` | `(value, *args, **kwargs)` — printf-style |
| `groupby` | `(env, value, attribute, default=None, case_sensitive=False)` — sorts first, dot-notation attrs |
| `indent` | `(s, width=4, first=False, blank=False)` — preserves **`Markup`** |
| `join` | `(eval_ctx, value, d="", attribute=None)` — autoescape-aware, may return **`Markup`** |
| `items` | `(dict|Undefined)` → pairs |
| `list`, `map` | `map(attribute=…, default=None)` or `map(filter_name, *args)` |
| `min`/`max` | `(env, value, case_sensitive=False, attribute=None)` |
| `pprint` | debug pretty-print |
| `reject`/`select` | `(ctx, value, test_name=None, *args, **kwargs)` |
| `rejectattr`/`selectattr` | `(ctx, value, attr, test_name=None, *args, **kwargs)` — no test = truthiness of attr |
| `replace` | `(eval_ctx, s, old, new, count=None)` |
| `reverse` | str or iterable |
| `round` | `(value, precision=0, method="common"\|"ceil"\|"floor")` |
| `safe` | `(value)` → **`Markup`** (marks trusted, no escaping) |
| `slice` | `(value, slices, fill_with=None)` |
| `sort` | `(env, value, reverse=False, case_sensitive=False, attribute=None)` — multi-attr via comma list |
| `string` | MarkupSafe `soft_str` |
| `striptags` | → plain `str` |
| `sum` | `(env, iterable, attribute=None, start=0)` |
| `tojson` | `(eval_ctx, value, indent=None)` → **`Markup`**, HTML-safe JSON (`<>&'` → `\uXXXX`); honors `json.dumps_function` / `json.dumps_kwargs` policies |
| `truncate` | `(env, s, length=255, killwords=False, end="...", leeway=None)` — leeway defaults to `truncate.leeway` policy (5) |
| `unique` | `(env, value, case_sensitive=False, attribute=None)` |
| `upper`/`lower`, `urlencode` | `(value)` — str, mapping, or pairs; UTF-8, `/` kept unless query-style |
| `urlize` | `(eval_ctx, value, trim_url_limit=None, nofollow=False, target=None, rel=None, extra_schemes=None)` — `urlize.*` policies supply `rel`/`target` defaults |
| `wordcount`, `wordwrap` | `wordwrap(env, s, width=79, break_long_words=True, wrapstring=None, break_on_hyphens=True)` |
| `xmlattr` | `(eval_ctx, dict, autospace=True)` → ` key="value"` string |

Filters taking `eval_ctx`/`environment`/`context` first are auto-injected — template authors just write `{{ x|join(", ") }}`. Async variants exist for `join`, `first` (`do_first`), `groupby`, `map`, `reject`, `select`, `rejectattr`, `selectattr`, `sum`, `unique`, `slice`, `batch` (picked automatically when `enable_async`).

### Tests — complete list

`odd`, `even`, `divisibleby(value, num)`, `defined`, `undefined`, `filter(env, name)` (is there a filter called…), `test(env, name)`, `none`, `boolean`, `false`, `true`, `integer`, `float`, `lower`, `upper`, `string`, `mapping`, `number`, `sequence`, `iterable`, `callable`, `sameas(value, other)`, `escaped` (is it **`Markup`**?), `in(value, seq)`, plus operator aliases `==`/`eq`/`equalto`, `!=`/`ne`, `>`/`gt`/`greaterthan`, `>=`/`ge`, `<`/`lt`/`lessthan`, `<=`/`le`.

```jinja
{% if user is defined and user.role is sameas("admin") %}…{% endif %}
{% if jobs is sequence and (job.status in ["done", "error"]) %}…{% endif %}
```

### `Undefined` hierarchy

- `Undefined(hint=None, obj=missing, name=None, exc=UndefinedError)` — falsy, `str()` → `""`, `len()` → 0, iterable-empty; any other op raises `UndefinedError`. Message: `"'foo' is undefined"` or `"'Obj' has no attribute 'x'"`.
- `ChainableUndefined` — `__getattr__`/`__getitem__` return self (safe deep chains like `{{ a.b.c|default("—") }}`).
- `DebugUndefined` — prints as `{{ foo }}` so gaps are visible in output.
- `StrictUndefined` — raises on **print, iteration, bool, ==, hash, contains** too; catches every typo at render.
- `make_logging_undefined(logger=None, base=Undefined)` → subclass logging `warning` on print/iter/bool and `error` on failure.

### Custom filters/tests/globals + context decorators

```python
from jinja2 import pass_context, pass_environment, pass_eval_context


@pass_context
def ff_cmd(ctx, job, op="convert"):  # ctx: Context — resolve/call/blocks
    ...


env.filters["ff_cmd"] = ff_cmd
env.tests["loud"] = lambda v: v > -14
env.globals["APP"] = "FFmpeg"
env.policies["truncate.leeway"] = 0
```

`Context` API: `resolve(key)`, `resolve_or_missing(key)`, `get(key, default)`, `get_all()`, `get_exported()` (for imports), `call(fn, *a, **k)` (injects context/env), `derived(locals)`, `super()`, `super` in blocks, `keys/values/items`, `in`, `[]`.

### Extensions

```python
class Extension:
    tags: set[str] = set()     # tag names this extension parses
    priority = 100
    def __init__(self, environment): ...
    def bind(self, environment)        # copy bound to an overlay env
    def preprocess(self, source, name, filename=None) -> str
    def filter_stream(self, stream) -> TokenStream | Iterable[Token]
    def parse(self, parser) -> Node | list[Node]
    def attr(self, name, lineno=None) -> ExtensionAttribute
    def call_method(self, name, args=None, kwargs=None, dyn_args=None, dyn_kwargs=None, lineno=None) -> nodes.Call
```

Built-ins (enable via `extensions=[...]`): `jinja2.ext.LoopControlExtension` (`{% break %}`/`{% continue %}`), `jinja2.ext.ExprStmtExtension` (`{% do %}`), `jinja2.ext.DebugExtension` (`{% debug %}` dumps context/filters/tests), `jinja2.ext.InternationalizationExtension` (`{% trans %}` + `{% pluralize %}`; `env.install_gettext_translations(t)`, `install_null_translations()`, `install_gettext_callables(gettext, ngettext, newstyle, pgettext, npgettext)`, `uninstall_gettext_translations(t)`, `extract_translations(source)`; sets `newstyle_gettext`, `_` global). Babel extraction: `babel_extract(fileobj, keywords, comment_tags, options)` / `extract_from_ast(ast, gettext_functions=GETTEXT_FUNCTIONS)` with `entry_points.txt` hook (`jinja2.ext:babel_extract`).

### Async

```python
env = Environment(loader=..., enable_async=True)
await env.get_template("report.html").render_async(
    jobs=jobs
)  # async filters/globals awaited; sync ones still work
async for chunk in tmpl.generate_async(**ctx):
    ...
```

Helpers: `pass_*` decorators (above); `async_variant(sync_fn)(async_fn)` dual-dispatch decorator; `auto_await`, `auto_aiter`, `auto_to_list` in `async_utils`.

### Sandbox (for untrusted templates)

```python
from jinja2.sandbox import SandboxedEnvironment, ImmutableSandboxedEnvironment, unsafe

env = SandboxedEnvironment()
```

- Blocks `_private` attrs + `is_internal_attribute` cases; `is_safe_attribute(obj, attr, value)`, `is_safe_callable(obj)` (rejects `@unsafe` / `alters_data`) — override to tighten/loosen.
- `call_binop`/`call_unop` + `intercepted_binops`/`intercepted_unops` + `binop_table`/`unop_table` (default `+ - * / // ** %`, unary `+ -`); `range` replaced by `safe_range`.
- `ImmutableSandboxedEnvironment` additionally blocks mutating methods on `list`/`set`/`dict` via `modifies_known_mutable`.
- Violations raise `SecurityError(TemplateRuntimeError)`.
- `SandboxedFormatter`/`SandboxedEscapeFormatter` route `str.format` field access through the sandbox.

### i18n

Requires `Babel` extra. `{% trans name=user, count=n %}{{ name }} has {{ count }} file{% pluralize %}{{ name }} has {{ count }} files{% endtrans %}`, `{% trans "ctx", … %}`, `_()`, `gettext/ngettext/pgettext/npgettext` globals, `newstyle_gettext` (kwargs-style `%` formatting).

### Exceptions

```python
TemplateError(Exception)  # base; .message
TemplateNotFound(
    IOError, LookupError, TemplateError
)  # .name, .templates; Undefined name -> UndefinedError
TemplatesNotFound(TemplateNotFound)  # .templates (whole tried list)
TemplateSyntaxError(
    TemplateError
)  # (message, lineno, name=None, filename=None); .source, .translated
TemplateAssertionError(TemplateSyntaxError)  # compile-time (e.g. unknown filter at parse)
TemplateRuntimeError(TemplateError)
UndefinedError(TemplateRuntimeError)
SecurityError(TemplateRuntimeError)  # sandbox violation
FilterArgumentError(TemplateRuntimeError)
```

### Loaders

`BaseLoader.get_source(env, template) -> (source, filename|None, uptodate|None)`; `load()` handles bytecode cache + compile; `list_templates()` raises `TypeError` unless supported.

```python
FileSystemLoader(searchpath, encoding="utf-8", followlinks=False)  # str | path-like | list (searched in order)
PackageLoader(package_name, package_path="templates", encoding="utf-8")
DictLoader({"report.html": "..."})            # uptodate compares mapping live
FunctionLoader(load_func)                     # fn(name) -> str | (src, filename, uptodate) | None
PrefixLoader({"screens": FileSystemLoader("t/")}, delimiter="/")   # "screens/home.html"
ChoiceLoader([DictLoader({...}), FileSystemLoader("t/")])
ModuleLoader(path)                            # AOT-compiled modules from env.compile_templates()
split_template_path(template) -> list[str]    # rejects ".." / absolute pieces
```

### Bytecode cache

```python
class BytecodeCache:  load_bytecode(bucket); dump_bytecode(bucket); clear();
    get_cache_key(name, filename=None); get_source_checksum(source);
    get_bucket(env, name, filename, source); set_bucket(bucket)
class Bucket:  key, checksum, code; load_bytecode(f); write_bytecode(f); reset(); code property
FileSystemBytecodeCache(directory=None, pattern="__jinja2_%s.cache")
MemcachedBytecodeCache(client, prefix="jinja2/bytecode/", timeout=None, ignore_memcache_errors=True)
```

### Introspection (`meta`), lexer/parser, utils

```python
from jinja2 import meta
env.parse(src) -> nodes.Template
meta.find_undeclared_variables(ast) -> set[str]     # e.g. {'bar'} — what the caller must supply
meta.find_referenced_templates(ast) -> Iterator[str | None]  # extends/include/import names; None = dynamic
```

Lexer/parser/compiler (`lexer.py`, `parser.py`, `compiler.py`, `nodes.py`, `idtracking.py`, `optimizer.py`, `visitor.py`) are public-ish but meant for tooling/extensions: `TokenStream` (`push/look/skip/expect/next_if/eos`), `Parser.parse_expression()`, `CodeGenerator`, `NodeVisitor`, `EvalContext`. Extension authors subclass `Extension` rather than touching these.

`utils`: `select_autoescape(enabled=("html","htm","xml"), disabled=(), default_for_string=True, default=False)` → callable for `autoescape=`; `is_undefined(obj)`; `clear_caches()`; `import_string("pkg:obj")`; `LRUCache(capacity)` (thread-locked); `Cycler(*items)` (`.next()/.current/.reset()`); `Joiner(sep=", ")`; `Namespace(**kw)` (assign in loops); `generate_lorem_ipsum(n=5, html=True, min=20, max=100)`; `htmlsafe_json_dumps(obj, dumps=None, **kw)` → **`Markup`**; `url_quote(obj, charset="utf-8", for_qs=False)`; `urlize(...)`; `pformat`; `object_type_repr`.

### MarkupSafe boundary (for the MarkupSafe agent)

Jinja2 **returns `markupsafe.Markup`** from: `escape`/`e` filter, `forceescape`, `safe`, `tojson` (+ `htmlsafe_json_dumps`), `Macro.__call__` (when autoescape on), `TemplateModule.__html__`, `join` (when inputs/delimiter are HTML-aware), `indent` (when input is Markup). `striptags`/`string` deliberately return plain `str`. Rule of thumb: `Markup` = "already escaped, do not escape again"; wrapping user text in `Markup`/`|safe` without escaping is the XSS hole (see Gotchas).

## App usage & correctness

**(a) Where used.** Nowhere directly — verified by grep: zero hits for `jinja`/`Jinja2`/`Environment(`/`Template(` in `src/`, `tests/`, `tools/` (excluding `__pycache__`), and `pyproject.toml` has no direct pin. Install chain from `uv.lock`:

1. `pyproject.toml` dev group → `flet-cli>=1.0.0` (build/packaging CLI only).
2. `uv.lock` `flet-cli 1.0.0` deps include `cookiecutter` (uv.lock ≈ line 333).
3. `uv.lock` `cookiecutter 2.7.1` deps include `jinja2` (uv.lock ≈ line 207).
4. `uv.lock` `jinja2 3.1.6` dep = `markupsafe` only (uv.lock ≈ lines 451–459).

So Jinja2 renders cookiecutter project scaffolds when running `flet create` / `flet build` templates. It ships in the venv but never in the app bundle's runtime path.

**(b) Misuse.** None — no direct usage exists to misuse. Indirect risk is nil: cookiecutter pins are resolved by uv and the templates it renders are Flet's own.

**(c) Underuse for v1.** Real, low-cost wins (all offline, zero new deps):

1. **Human-readable ffmpeg command previews** — `TerminalScreen`/result flows could render the built argv through a `DictLoader` template (`{{ exe }} {% for f in inputs %}-i {{ f|quote }} {% endfor %}…`) instead of string concatenation; one template serves both the preview card and copy-to-clipboard text.
2. **Changelog/release-note generation** — `src/core/changelog.py` is a hand-written `dict[str, str]`; a `tools/` script rendering per-version markdown from a data file (`{% for v, notes in releases %}### FFmpeg {{ v }}…{% endfor %}`) removes formatting drift.
3. **HTML export of probe dossiers / job reports** — `tests/test_remux_dossier.py` implies a shareable markdown dossier; a Jinja2 HTML template with `select_autoescape(["html"])` + `filesizeformat`/`round`/`join` filters yields a polished shareable report for free.
4. **Scaffolding new screens/tests** — the repo has 17 screens + ~20 test files with repetitive boilerplate; a tiny `tools/scaffold.py` using `FileSystemLoader` + `StrictUndefined` could stamp out screen/test/doc triples and fail loudly on missing variables.

## Underused APIs to adopt

| API | v1 use |
|---|---|
| `DictLoader` + `StrictUndefined` | Command-preview and report templates; typos raise instead of silently blanking |
| `select_autoescape` | Correct `autoescape=` for HTML dossier export |
| `filesizeformat`, `round`, `join(attribute=…)`, `dictsort`, `groupby`, `tojson` | Probe/job data formatting in reports |
| `meta.find_undeclared_variables` | Validate at startup that a template's required context matches what the screen supplies |
| `TemplateStream.dump(path)` | Write large HTML reports without building the whole string |
| `compile_expression` | Power-user filter strings (e.g. custom "auto-pick best stream" expressions) |
| `NativeEnvironment` | Config/preset templates that must evaluate to real Python values (bitrates, sizes) |
| `SandboxedEnvironment` | If user-supplied filename/report templates are ever accepted |
| `LoopControlExtension` (`break`/`continue`), `DebugExtension` (`{% debug %}`) | Template-side control + debugging while developing the above |

## Gotchas

1. **`autoescape=False` by default** — HTML exports must opt in (`select_autoescape`) or filenames/metadata containing `<script>` become XSS. `|safe`/`Markup()` on unescaped user data is the hole.
2. **Silent blanks** — default `Undefined` renders missing vars as `""`; use `StrictUndefined` (or at least `ChainableUndefined` + `default`) for anything user-visible so typos surface.
3. **Whitespace** — `trim_blocks`/`lstrip_blocks`/`keep_trailing_newline` all default off; command-preview templates with tags on own lines will leak stray newlines/spaces unless set.
4. **`finalize` runs on every `{{ }}`** — handy for `None → ""`, but keep it cheap; it also affects `{% %}`-adjacent output paths.
5. **Overlays share filters/tests/globals by reference binding** — configure the base env fully before `overlay()`; `add_extension` after first load is undefined behavior.
6. **`DictLoader` uptodate closure** compares against the live mapping — mutating the dict invalidates cache (good), but concurrent mutation from threads races.
7. **Spontaneous `Template(src)` envs are `lru_cache`d (10)** — prefer one shared `Environment` for repeated renders (cache_size=400 default).
8. **`length` on generators is destructive-ish** — `loop.length` materializes the iterator; pass sized lists for probe/job collections.
9. **`tojson` is HTML-safe, not JS-context-safe everywhere** — don't interpolate it into double-quoted HTML attributes (use single quotes or `|forceescape`).
10. **Sandbox ≠ bulletproofing business logic** — it guards attribute/call access, not exfiltration via allowed globals; audit `globals`/`filters` you expose to user templates.
11. **Async requires `enable_async=True` at env creation** — calling `render_async` otherwise raises `RuntimeError`; sync filters still work in async envs.
12. **Only hard dep is `MarkupSafe>=2.0`** — the `i18n`/`trans` path needs the `Babel` extra, which this venv does not install; don't use `{% trans %}` unless Babel is added.
