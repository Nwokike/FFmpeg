# click 8.5.0 — Complete API Reference

> Pallets "Command Line Interface Creation Kit". Composable, decorator-driven CLI toolkit:
> arbitrary command nesting, auto help pages, lazy subcommands, typed params, prompts,
> paging, progress bars, ANSI styling, shell completion, test runner.
> Installed at `.venv/Lib/site-packages/click/` (pure-Python, `py.typed` present).
> Ground truth: this file's sources + `click-8.5.0.dist-info/{METADATA,RECORD,WHEEL,licenses/LICENSE.txt}`.

---

## Files

| File | Lines | Role |
|---|---|---|
| `__init__.py` | 144 | Public re-export surface + deprecated `__getattr__` shims |
| `core.py` | 3,799 | `Context`, `Command`, `Group`, `CommandCollection`, `Parameter`, `Option`, `Argument`, `ParameterSource`, `UNSET` |
| `decorators.py` | 627 | `@command`, `@group`, `@argument`, `@option`, `confirmation_option`, `password_option`, `version_option`, `custom_version_option` (new 8.5), `help_option`, `pass_context/obj/meta_key`, `make_pass_decorator` |
| `types.py` | 1,422 | `ParamType` (+generic `ParamType[V,I]`), `Choice`, `DateTime`, `IntRange`, `FloatRange`, `BOOL`, `UUID`, `File`, `Path`, `Tuple`, `convert_type`, singletons `STRING/INT/FLOAT/BOOL/UUID/UNPROCESSED` |
| `termui.py` | 1,014 | `prompt`, `confirm`, `progressbar`, `style`, `secho`, `unstyle`, `clear`, `echo_via_pager`, `get_pager_file`, `edit`, `launch`, `getchar`, `pause` |
| `utils.py` | 688 | `echo`, `open_file`, `format_filename`, `get_app_dir`, private `_expand_args`, `_detect_program_name` |
| `testing.py` | 798 | `CliRunner`, `Result`, `isolation`, `isolated_filesystem`, `make_input_stream` |
| `exceptions.py` | 378 | `ClickException(1)`, `UsageError(2)`, `BadParameter`, `MissingParameter`, `NoSuchOption`, `NoSuchCommand` (8.4+), `BadOptionUsage`, `BadArgumentUsage`, `NoArgsIsHelpError`, `FileError`, `Abort`, `Exit` |
| `formatting.py` | 320 | `HelpFormatter`, `wrap_text`, `measure_table`, `join_options`, `FORCED_WIDTH` |
| `parser.py` | 533 | Internal `_OptionParser`, `_Option`, `_Argument`, `_ParsingState`, `_split_opt` (public `OptionParser` alias deprecated) |
| `shell_completion.py` | 801 | `CompletionItem`, `ShellComplete`, `BashComplete`, `ZshComplete`, `FishComplete`, `PowerShellComplete`, `add_completion_class`, `get_completion_class`, `split_arg_string`, `shell_complete()` |
| `globals.py` | 67 | `get_current_context`, `push_context`, `pop_context`, `resolve_color_default` |
| `_compat.py` | 590 | Streams, ANSI strip, terminal detection (private) |
| `_termui_impl.py` | 972 | `ProgressBar`, pager, `Editor`, `open_url` (private) |
| `_textwrap.py` | 188 | ANSI-aware `TextWrapper` (private) |
| `_winconsole.py` | 297 | Windows console (private; 8.5 no longer uses colorama) |
| `_utils.py` | 36 | Tiny private helpers |
| `py.typed` | 0 | PEP-561 marker — click ships inline types |

`__pycache__/` skipped (bytecode only). `RECORD` pins every file above with sha256
(except `RECORD` itself); `REQUESTED` is **empty (0 bytes)** — proof of transitive install.

---

## Metadata

From `click-8.5.0.dist-info/METADATA` (Metadata-Version 2.4):

```
Name: click
Version: 8.5.0
Summary: Composable command line interface toolkit
Requires-Python: >=3.10
License-Expression: BSD-3-Clause        # licenses/LICENSE.txt ("Copyright 2014 Pallets", BSD text)
Classifier: Development Status :: 5 - Production/Stable; OS Independent; Typing :: Typed
Project-URL: docs https://click.palletsprojects.com/ · source https://github.com/pallets/click/
```

- **Runtime pins: NONE.** `METADATA` lists zero `Requires-Dist` — click has no dependencies.
- **Installer:** `INSTALLER` = `uv` (`uvWheel-Version: 1.0`); `WHEEL`: `Generator: flit 3.12.0`,
  `Root-Is-Purelib: true`, `Tag: py3-none-any`.
- **uv.lock:** `name = "click"`, `version = "8.5.0"`, PyPI sdist
  `click-8.5.0.tar.gz` `sha256:ba0d20…b272e34`, upload `2026-08-26`.
- **Why installed:** transitive via **`flet-cli → cookiecutter>=2.6.0 → click<9.0.0,>=7.0`**.
  Chain verified: `flet_cli-1.0.0.dist-info/METADATA` requires
  `cookiecutter>=2.6.0` (+`rich`, `watchdog`, `packaging`, `qrcode`, …);
  `cookiecutter-2.7.1.dist-info/METADATA` requires `click<9.0.0,>=7.0`
  (alongside `binaryornot`, `Jinja2`, `pyyaml`, `python-slugify`, `requests`, `arrow`, `rich`).
  Second edge: `httpx-0.28.1.dist-info/METADATA` has `Requires-Dist: click==8.*; extra == 'cli'`
  (dormant unless `httpx[cli]` is installed). App `pyproject.toml` never declares click.

---

## Module-by-module API

### 1. `click/__init__.py` — public surface

Re-exports (canonical import list): `Argument, Command, CommandCollection, Context, Group,
Option, Parameter, ParameterSource`, `argument, command, confirmation_option,
custom_version_option, group, help_option, make_pass_decorator, option, pass_context,
pass_obj, password_option, version_option`, `Abort, BadArgumentUsage, BadOptionUsage,
BadParameter, ClickException, FileError, MissingParameter, NoSuchCommand, NoSuchOption,
UsageError`, `HelpFormatter, wrap_text`, `get_current_context`, `clear, confirm,
echo_via_pager, edit, get_pager_file, getchar, launch, pause, progressbar, prompt, secho,
style, unstyle`, `BOOL, Choice, DateTime, File, FLOAT, FloatRange, INT, IntRange,
ParamType, Path, STRING, Tuple, UNPROCESSED, UUID`, `echo, format_filename, get_app_dir, open_file`.

Deprecated `__getattr__` shims (warn, remove in 9.0/9.1 — do NOT use):

```python
click.BaseCommand  # -> core._BaseCommand (use Command)
click.MultiCommand  # -> core._MultiCommand (use Group)
click.OptionParser  # -> parser._OptionParser (use optparse instead)
click.__version__  # use importlib.metadata.version("click")
click.get_binary_stream / get_text_stream  # private _get_*_stream now
```

### 2. `click.decorators` — the everyday API

```python
@click.group(name=None, cls=None, **attrs)      # -> Group; same kwargs as Command
@click.command(name=None, cls=None, **attrs)    # -> Command
@click.option(*param_decls, cls=Option, **attrs)   # forwards everything to Option()
@click.argument(*param_decls, cls=Argument, **attrs)
```

Name derivation (`command`/`group`): function name lowercased, `_`→`-`, trailing
`-command|-cmd|-group|-grp` stripped (8.2+); e.g. `init_data_command` → `init-data`.
Bare `@command` without parens supported (8.1+). Docstring becomes `help` if `help` unset.
Decorated params appended after explicit `params=[...]`. Double-converting a `Command`
raises `TypeError`.

```python
@click.pass_context          # inject ctx as first arg
@click.pass_obj              # inject ctx.obj as first arg
@click.make_pass_decorator(SomeClass, ensure=False)  # find/ensure innermost obj of type
@click.pass_meta_key("key") # (8.0+) inject ctx.meta["key"]; doc_description kw
```

Ready-made options:

```python
@click.confirmation_option("--yes", is_flag=True, callback=abort-if-false,
    expose_value=False, prompt="Do you want to continue?",
    help="Confirm the action without prompting.")
@click.password_option("--password", prompt=True, confirmation_prompt=True, hide_input=True)
@click.version_option(version=None, *decls, package_name=None, prog_name=None,
    message="%(prog)s, version %(version)s")   # auto-detects via importlib.metadata;
    # falls back to top-module→distro map (PIL→Pillow); frozen message slots by design
@click.custom_version_option(callback, *decls, **option_kwargs)  # NEW 8.5.0
    # callback(ctx) -> str; printed then ctx.exit(). For git hash / ffmpeg -version output.
@click.help_option("--help", is_flag=True, expose_value=False, is_eager=True,
    help="Show this message and exit.")
```

Example — canonical hello:

```python
import click


@click.command()
@click.option("--count", default=1, help="Number of greetings.")
@click.option("--name", prompt="Your name", help="The person to greet.")
def hello(count, name):
    """Simple program that greets NAME for a total of COUNT times."""
    for _ in range(count):
        click.echo(f"Hello, {name}!")


if __name__ == "__main__":
    hello()
```

### 3. `click.core` — `Parameter` / `Option` / `Argument`

Base (all params accept these):

```python
Parameter(
    param_decls=None,
    type=None,
    required=False,
    default=UNSET,  # UNSET = "not given"
    callback=None,  # fn(ctx, param, value) -> new value; raising BadParameter attaches name
    nargs=None,  # default 1; composite types force arity
    multiple=False,  # collect repeats into tuple
    metavar=None,
    expose_value=True,
    is_eager=False,
    envvar=None,  # str | list[str]; auto-upper for options
    shell_complete=None,  # fn(ctx, param, incomplete) -> list[CompletionItem|str]
    deprecated=False,
)  # True | "reason string"; required+deprecated -> ValueError
```

`Option` adds (full kwarg list — the ones the assignment asks for):

```python
Option(
    *decls,
    show_default=None,
    prompt=False,
    confirmation_prompt=False,
    prompt_required=True,
    hide_input=False,
    is_flag=None,  # None = infer: flag_value set -> flag; bool decl -> bool flag
    flag_value=UNSET,  # activation value; UNSET resolves to True for flags
    multiple=False,
    count=False,  # count: -vvv increments from default 0
    allow_from_autoenv=True,
    type=None,
    help=None,
    hidden=False,  # hide from --help listing (still usable)
    show_choices=True,
    show_envvar=False,
    deprecated=False,
    **attrs,
)
```

Notes: `prompt=True` derives `"Name..."` text from param name; `prompt="text"` custom;
`hide_input=True` uses getpass; `confirmation_prompt=True|"Repeat..."`; `show_default`
accepts a string override (8.3.3+); bool flags get implicit `default=False`;
`expose_value=False` + eager is how `--help/--version/--yes` work.
`flag_activation_value` property, `is_bool_flag` property, `prompt_for_value(ctx)`,
`get_help_extra(ctx) -> OptionHelpExtra{default, range, ...}` support introspection.

`Argument` (positional; `multiple` forbidden — use `nargs=-1`):

```python
Argument(param_decls, required=None, help=None, **attrs)  # help added 8.5.0
# required auto: True unless default or nargs<=0 given; metavar defaults NAME.upper();
# optional shown [NAME]; nargs=-1 -> NAME... ; single decl only or TypeError
```

Useful `Parameter`/`Command` members:
`get_default(ctx, call=True)`, `consume_value(ctx, opts)`, `process_value(ctx, value)`,
`type_cast_value(ctx, value)`, `value_from_envvar(ctx)`, `get_help_record(ctx)`,
`get_error_hint(ctx)`, `to_info_dict()` (drives doc generators),
`Command.get_params(ctx)` (appends auto `--help`), duplicate-opt/name `warnings` in `__debug__`.

### 4. `click.core` — `Command`, `Group`, `Context`

```python
Command(
    name,
    context_settings=None,
    callback=None,
    params=None,
    help=None,
    epilog=None,
    short_help=None,
    options_metavar="[OPTIONS]",
    add_help_option=True,
    no_args_is_help=False,
    hidden=False,  # sealed from listing AND parent help; direct invoke still works
    deprecated=False,
)  # True | "msg ..." -> "DEPRECATED: msg" suffix everywhere
```

Lifecycle: `cmd.main(args=None, prog_name=None, standalone_mode=True,
windows_expand_args=True, **extra)` → `make_context` → `parse_args` → `invoke(ctx)`.
`standalone_mode=True` catches `ClickException/Abort` → prints → `sys.exit(code)`;
`False` re-raises (libraries/tests). `__call__(*a, **k)` = `main(*a, **k)`.
`no_args_is_help=True` prints help on bare invoke (autouse for groups without callback).
`context_settings` forwards to `Context` (e.g. `help_option_names`, `ignore_unknown_options`,
`allow_extra_args`, `token_normalize_func`).

```python
Group(name=None, commands=None, invoke_without_command=False,
    no_args_is_help=None,     # default = not invoke_without_command
    subcommand_metavar=None,  # default "COMMAND [ARGS]..." (+CHAIN variants)
    chain=False,              # `cmd1 args cmd2 args...`; forbids optional Arguments
    result_callback=None, **kwargs)
grp.add_command(cmd, name=None)
@grp.command(*a, **k) / @grp.group(*a, **k)   # bare form allowed 8.1+
@grp.result_callback(replace=False)           # chain collector: fn(results, **ctx.params)
grp.get_command(ctx, name) / list_commands(ctx)  # override for lazy loading / plugins
```

Lazy-load recipe (dict not needed):

```python
class LazyGroup(click.Group):
    def list_commands(self, ctx):
        return ["convert", "doctor"]

    def get_command(self, ctx, name):
        if name == "convert":
            from app.cli import convert

            return convert
```

`CommandCollection(name, sources=[grp1, grp2], **kw)` merges groups; `add_source(grp)`.

```python
Context(
    command,
    parent=None,
    info_name=None,
    obj=None,
    auto_envvar_prefix=None,
    default_map=None,
    terminal_width=None,
    max_content_width=None,
    resilient_parsing=False,
    allow_extra_args=None,
    allow_interspersed_args=None,
    ignore_unknown_options=None,
    help_option_names=None,
    token_normalize_func=None,
    color=None,
    show_default=None,
)
```

Key members: `ctx.params`, `ctx.args` (+`protected_args`), `ctx.obj` (+`find_object(T)` /
`ensure_object(T)`), `ctx.meta`, `ctx.parent` / `find_root()`, `ctx.command_path`,
`ctx.invoked_subcommand`, `ctx.default_map` + `lookup_default(name)`,
`ctx.fail(msg)` (UsageError/2), `ctx.abort()` (Abort/1), `ctx.exit(code=0)`,
`ctx.invoke(fn_or_cmd, *a, **k)`, `ctx.forward(cmd, *a, **k)`,
`ctx.get_usage()/get_help()`, `ctx.make_formatter()`,
`ctx.scope(cleanup=True)` (push/pop thread-local),
`ctx.with_resource(cm)`, `ctx.call_on_close(fn)`,
`get_parameter_source(name) -> ParameterSource|None`.

```python
class ParameterSource(enum.IntEnum):  # most→least explicit; comparable (8.3.3+)
    PROMPT < COMMANDLINE < ENVIRONMENT < DEFAULT_MAP < DEFAULT
```

`to_info_dict()` on `Context` walks the whole tree — feed for `--help`-as-JSON tooling.

Hidden vs sealed: `hidden=True` removes from `--help`/completion listings but the command
still runs (`NoSuchCommand` suggestions skip it). There is no separate "sealed" flag —
"sealed" in click vocabulary = hidden + not registered under an obvious alias.

### 5. `click.types` — every param type

| Type | Ctor | Accepts / notes |
|---|---|---|
| `STRING` / `str` | singleton | bytes→decoded via argv encoding; default inference from `str` default |
| `INT` / `int` | singleton | int/index strings |
| `FLOAT` / `float` | singleton | float strings |
| `BOOL` / `bool` | singleton | `1/0 yes/no true/false on/off t/f y/n ""→False` (case-insensitive); full map at `BoolParamType.bool_states`; `str_to_bool()` helper |
| `UUID` | singleton | `uuid.UUID(value.strip())`, fail otherwise |
| `UNPROCESSED` | singleton | no conversion (bytes-safe paths) |
| `Choice(c, case_sensitive=True)` | generic `Choice[T]`; Enum members match `.name`; `normalize_choice()` overridable (8.2+) | metavar `[a\|b]` (`{a\|b}` for required args); missing msg lists choices |
| `IntRange(min,max,min_open,max_open,clamp)` | `clamp` clamps instead of failing | name "integer range" |
| `FloatRange(same)` | open bounds + clamp → `TypeError` | name "float range" |
| `DateTime(formats=None)` | default `["%Y-%m-%d","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S"]`; pass list/tuple | returns `datetime`; pass-through if already datetime |
| `File(mode="r", encoding=None, errors="strict", lazy=None, atomic=False)` | `-` = stdin/stdout; lazy auto-True for writes; atomic = write-temp-then-move; closed at ctx teardown | returns open handle |
| `Path(exists=False, file_okay=True, dir_okay=True, readable=True, writable=False, executable=False, resolve_path=False, allow_dash=False, path_type=None)` | `path_type=pathlib.Path` supported (8.0+) | returns str/bytes/Path |
| `Tuple((t1, t2…))` | composite, `arity=len`; python-tuple literal as `type=` auto-converts | `nargs` must equal arity |
| `FuncParamType(fn)` / `convert_type(ty, default)` | any callable / python type → ParamType; `tuple` → `Tuple` | subclass `ParamType` + `convert(value,param,ctx)` + `fail()` for customs; `shell_complete(ctx,param,incomplete)` for completions |

`ParamType` generics: `ParamType[ValueT, InputT=Any]` (8.4/8.5) — `convert` carries narrowed types.

### 6. `click.exceptions` — hierarchy & exit codes

```
ClickException(msg)            exit 1  "Error: msg" on stderr
├─ UsageError(msg, ctx=None)   exit 2  prints usage + "Try 'prog --help' for help."
│  ├─ BadParameter(msg, ctx, param, param_hint)  "Invalid value for --x: ..."
│  │  └─ MissingParameter(...)  "Missing option '--x'." / "Missing argument 'IN'."
│  ├─ NoSuchOption(name, possibilities)  + difflib "Did you mean …?"
│  ├─ NoSuchCommand(name, ...)           (8.4+) same fuzzy hints
│  ├─ BadOptionUsage / BadArgumentUsage / NoArgsIsHelpError
└─ FileError(filename, hint)   "Could not open file '…': …"
Abort(RuntimeError)            silent exit 1 (Ctrl-C / confirm-decline)
Exit(code=0)                   controlled exit (ctx.exit / version / help paths)
```

`ctx.fail()` → `UsageError`; `ctx.abort()` → `Abort`.

### 7. `click.termui` + `click.utils` — output, prompts, bars, files

```python
click.echo(message=None, file=None, nl=True, err=False, color=None)
# print-replacement: encoding-safe, bytes-capable, strips ANSI when not a tty, always flushes.
click.secho(msg, file=None, nl=True, err=False, color=None, **style_kwargs)
click.style(text, fg=None, bg=None, bold=None, dim=None, underline=None,
    overline=None, italic=None, blink=None, reverse=None, strikethrough=None, reset=True)
# fg/bg: name | 0-255 | (r,g,b). Names: black red green yellow blue magenta cyan white
#   reset bright_* variants. 8.5: colorama gone; native ANSI incl. Windows.
click.unstyle(text) -> str
click.prompt(text, default=None, hide_input=False, confirmation_prompt=False,
    type=None, value_proc=None, prompt_suffix=": ", show_default=True,
    err=False, show_choices=True)   # generically typed 8.5; Ctrl-C/EOF -> Abort
click.confirm(text, default=False, abort=False, prompt_suffix=": ", show_default=True, err=False)
click.progressbar(iterable=None, length=None, label=None, hidden=False,
    show_eta=True, show_percent=None, show_pos=False, item_show_func=None,
    fill_char="#", empty_char="-", bar_template="%(label)s  [%(bar)s]  %(info)s",
    info_sep="  ", width=36, file=None, color=None, update_min_steps=1)
# with click.progressbar(items, label="Converting") as bar:
#     for f in bar: convert(f)
# manual: with click.progressbar(length=n, label="..") as bar: ...; bar.update(k, item)
click.clear()                        # clear screen
click.echo_via_pager(text|generator|fn, color=None)
click.get_pager_file(color=None)     # 8.4+ context manager yielding pager stream
click.edit(text=None, editor=None, env=None, require_save=True,
    extension=".txt", filename=None) # filename: path | PathLike | iterable (8.2/8.5+)
click.launch(url, wait=False, locate=False) -> int   # open viewer / reveal in file manager
click.getchar(echo=False) -> str
click.pause(info=None, err=False)
click.open_file(filename, mode="r", encoding=None, errors="strict", lazy=False, atomic=False)
# "-" -> stdin/stdout wrapped so `with` won't close the std stream
click.format_filename(path, shorten=False)
click.get_app_dir(app_name, roaming=True, force_posix=False)
#  Win %APPDATA%/App · mac ~/Library/Application Support/App · unix ~/.config/app
```

### 8. `click.testing` — `CliRunner`

```python
runner = click.testing.CliRunner(charset="utf-8", env=None,
    echo_stdin=False, catch_exceptions=True, capture="sys")  # "fd" POSIX-only
result = runner.invoke(cli, args=None, input=None, env=None,
    catch_exceptions=None, color=False, **extra)  # extra -> Command.main kwargs
# args: list OR shell string (shlex.split). input: str|bytes|stream -> stdin.
result.output / .stdout / .stderr   # str (8.2+: output = interleaved mix)
result.exit_code / .exception / .return_value
with runner.isolation(input=None, env=None, color=False) as (out, err, mix): ...
with runner.isolated_filesystem(temp_dir=None) as td: ...  # chdir sandbox (not thread-safe)
```

`Result.__repr__` → `<Result okay>` or `<Result <exc repr>>`.

### 9. `click.shell_completion` + `click.formatting` + `click.globals` + `click.parser`

```python
click.shell_completion.CompletionItem(value, type="plain", help=None, **meta)
# type "dir"/"file" triggers path completion; item.attr reads meta (None default)
class ShellComplete(cli, ctx_args, prog_name, complete_var): ...
class BashComplete / ZshComplete / FishComplete / PowerShellComplete(ShellComplete)
add_completion_class(cls, name=None); get_completion_class("bash"|"fish"|"zsh"|...)
split_arg_string(s) -> list[str]     # shlex-tolerant partial-line split
shell_complete(cli, ctx_args, prog_name, complete_var, instruction) -> 0|1
```

Activation pattern: `eval "$(_MYCLI_COMPLETE=bash_source mycli)"` etc. (`source`/`complete`
instructions handled by `Command._main_shell_completion`; env var conventionally
`_<PROG>_COMPLETE`). Custom types hook completions via
`ParamType.shell_complete(ctx, param, incomplete)` or per-param `shell_complete=fn`.

```python
HelpFormatter(indent_increment=2, width=None, max_width=80)
# write_usage(prog, args, prefix) / write_heading / write_text (rewrap+paragraphs) /
# write_dl(rows, col_max=30, col_spacing=2) / section(name) / indentation() / getvalue()
wrap_text(text, width=78, initial_indent="", subsequent_indent="", preserve_paragraphs=False)
# "\b"-first-line paragraph = no-rewrap block
get_current_context(silent=False)  # RuntimeError outside a command unless silent=True
push_context(ctx) / pop_context()  # Context.scope() does this for you
resolve_color_default(color)  # None -> ctx.color -> None
```

`parser._OptionParser` is internal; the old public `OptionParser` alias is deprecated.

---

## App usage & correctness

**Direct usage: exactly one file — `tools/admob.py` (line 25: `import click`).**
Zero hits in `src/`, `tests/`, `.github/` for `import click` / `from click`
(the many `on_click=` Flet matches are UI callbacks, unrelated). `tools/make_icons.py`
is Pillow-only, no click.

`tools/admob.py` — AdMob test↔prod ID manager, idiomatic small click app:

```python
@click.group()
def cli(): """Manage AdMob test/production IDs across the app."""

@cli.command("check-ids")
def check_ids(): ...          # click.echo(...) x4, click.secho(..., fg="yellow"|"green"|"red")

@cli.command("swap-ids")
@click.option("--mode", type=click.Choice(["test", "prod"]), required=True)
@click.option("--app-id", default=None, help="Production App ID (required for --mode prod)")
@click.option("--banner", default=None, ...)
@click.option("--interstitial", default=None, ...)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def swap_ids(mode, app_id, banner, interstitial, yes): ...

if __name__ == "__main__":
    sys.exit(cli())
```

APIs exercised correctly: `@group` + subcommands, `Choice` validation for `--mode`,
`is_flag` for `--yes`, `echo`/`secho(fg=…)`, `confirm("Overwrite …?")`,
`ClickException` for bad prod IDs / missing anchors (exit 1 with `Error:`),
`Abort` on declined confirm (silent exit 1). Docstring-driven help works;
`--help` per subcommand auto-generated.

**(a) Direct usage:** tools-only, correct patterns, no `src/` runtime dependency —
GUI stays click-free as it should (Flet owns the event loop).

**(b) MISUSE — one real bug + nits (all in `tools/admob.py`):**

1. **`NameError`: `_sub` vs `_subst` (breaking).** Helper defined as `_subst`
   (line 45: `def _subst(text, pattern: re.Pattern, …)`) but all three call sites use
   `_sub(...)` (lines ~116, ~131, ~145). `swap-ids` crashes with `NameError: _sub`
   after confirmation instead of writing files. Fix: rename def to `_sub` (or all calls
   to `_subst`) and add a `CliRunner` smoke test.
2. **Dead variable:** `is_test = …` (line 75) computed then `del is_test` (line 83) —
   remove both; the `MODE:` branch already covers it.
3. **`--mode prod` with `--yes` skips validation visibility:** values are validated,
   but a typo'd ID aborts only via exception text; consider `show_default`/`metavar`
   and `required` per-mode via callback, or at minimum echo the three validated IDs
   before the destructive write when `--yes` is passed.
4. **Non-atomic "atomically-ish":** sequential `write_text` on pyproject/constants/service
   can leave a half-swapped tree on crash — write temp files + `os.replace`, or stage all
   three substitutions in memory and fail before the first write (fail-fast already
   partially does this, but document it).

**(c) UNDERUSE — click is barely touched.** Available but unused: `CliRunner` (no CLI tests),
`progressbar`, typed `Path`/`File`/`IntRange`/`FloatRange`/`DateTime`/`Tuple`, `password_option` /
`confirmation_option`, `version_option`, `envvar=` + `auto_envvar_prefix`, `default_map`,
`ParameterSource`, `chain=True` groups, `result_callback`, shell completion,
`echo_via_pager`/`edit`/`launch`, `get_app_dir`, `open_file(atomic=True)`.

---

## Underused APIs to adopt

Concrete v1 CLI surface — works *alongside* `flet run` (GUI entry untouched). Proposed
`tools/ffmpeg_cli.py` (or `src/cli.py` + `pyproject [project.scripts] ffmpeg-cli`):

```python
import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("1.0.0", prog_name="ffmpeg-cli")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
@click.pass_context
def cli(ctx, as_json):
    """FFmpeg mobile companion CLI: batch convert, headless jobs, diagnostics."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json


@cli.command()
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=__import__("pathlib").Path),
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["mp4", "mkv", "mp3", "wav", "webm"]),
    default="mp4",
    show_default=True,
)
@click.option("--crf", type=click.IntRange(0, 51), default=23, show_default=True)
@click.option(
    "--preset", type=click.Choice(["ultrafast", "fast", "medium", "slow"]), default="medium"
)
@click.option("--jobs", type=click.IntRange(1, 8), default=2, show_default=True)
@click.option("--dry-run", is_flag=True, help="Print ffmpeg argv without running.")
def batch(inputs, fmt, crf, preset, jobs, dry_run):
    """Batch-convert INPUTS... headlessly (mirrors Convert screen presets)."""
    with click.progressbar(inputs, label="Converting") as bar:
        for src in bar:
            click.echo(f"{src} -> .{fmt} crf={crf} {preset} dry={dry_run}")


@cli.command()
@click.option(
    "--out",
    type=click.Path(file_okay=False, writable=True, path_type=__import__("pathlib").Path),
    default="job.json",
    show_default=True,
)
def enqueue(out):
    """Enqueue a headless job file for the app's job queue to pick up."""
    click.echo(f"queued -> {out}")


@cli.command()
@click.option("--check-admob/--no-check-admob", default=True)
def doctor(check_admob):
    """Environment diagnostics: engine probe, storage paths, AdMob alignment."""
    src = click.Context.get_parameter_source  # via get_current_context().get_parameter_source("x")
    click.secho("doctor: engine ok", fg="green")
    if check_admob:
        from click.testing import CliRunner  # reuse admob group in-process in tests

        click.echo("admob: see `uv run python tools/admob.py check-ids`")
```

Why each API earns its place:

- **`@group` + `@cli.command()` + `Choice`/`IntRange`/`Path`** — rejects bad `--crf 99`
  or missing files before spawning ffmpeg; mirrors GUI validation with zero custom code.
- **`nargs=-1` arguments + `multiple` options** — natural `inputs...` batch shape.
- **`--dry-run` flag / `--jobs` count / `--yes` confirmation_option** — destructive
  overwrites get the admob-proven confirm pattern; `-vvv` via `count=True` for verbosity.
- **`ctx.obj` dict + `@pass_context` / `make_pass_decorator`** — share `--json`/config down
  to subcommands without globals.
- **`progressbar(length=bytes)` + `bar.update(n, item)` + `item_show_func`** — byte-level
  transcode progress reusing the same widget style as long jobs.
- **`CliRunner` + `isolated_filesystem`** — headless tests for every command
  (`result.exit_code`, `.output`, `.exception`); also lets `doctor` invoke the admob group
  in-process. Fixes the `_sub` class of bug permanently.
- **`envvar="FFMPEG_…"` + `auto_envvar_prefix="FFMPEG"` + `default_map`** — CI/headless
  overrides without new flags; per-invocation config files via default_map.
- **`ParameterSource`** — `doctor --json` can report *why* a value won (CLI vs env vs default).
- **`password_option` / `prompt(hide_input, confirmation_prompt)`** — any future
  signing/upload credential input, masked + confirmed.
- **`version_option` / `custom_version_option`** — `--version` emitting app version +
  `ffmpeg -version` line + engine ABI (needs custom callback — exactly the 8.5.0 feature).
- **shell completion (`Bash/Zsh/Fish/PowerShell`)** — complete `--preset`/`--format` values
  and input paths in terminal workflows.
- **`secho`/`style`, `echo(err=True)`, `confirm(abort=True)`, `ClickException`/`Abort`** —
  consistent colored diagnostics; errors on stderr with exit 2 for usage vs 1 for runtime.
- **`open_file(atomic=True, lazy=True)` + `File` type** — safe job-file/receipt writes;
  `-` stdin/stdout convention for piping file lists.
- **`get_app_dir("FFmpeg")`, `format_filename`, `launch`, `edit`, `echo_via_pager`** —
  log/config home per OS, safe UI names, open result folder, drop into `$EDITOR` for job
  specs, page long `doctor` reports.

---

## Gotchas

1. **8.5.0 deprecations bite in v1 planning:** `click.__version__`, `BaseCommand`,
   `MultiCommand`, `OptionParser`, `get_binary_stream/get_text_stream` all warn now,
   gone in 9.0 (`__version__` 9.1). Grep tools for them before release.
2. **`UNSET` ≠ `None`:** `default=UNSET` means "no default". `get_default()` hides it as
   `None`; `flag_value=UNSET` resolves to `True` for flags. Don't test `is None` to detect
   "user passed this" — use `ctx.get_parameter_source(name)`.
3. **`required` + `deprecated` raises `ValueError` at construction;** hidden commands still
   execute (only listing/completion hides them) — don't rely on `hidden=True` for security.
4. **Flag inference surprises:** setting `flag_value=` silently flips `is_flag=True`;
   `count=True` forces default `0`; bool flags default `False`. Explicit `is_flag` avoids drift.
5. **`Choice` metavar hides values for options when `show_choices=False`;** `case_sensitive=False`
   uses `casefold()`; Enum choices match `.name`, return original member.
6. **`File("-")` and `open_file("-")` borrow stdio** — `with` won't close them (good),
   but an explicit `.close()` still will (bad in pipelines).
7. **`standalone_mode=False` re-raises** instead of exiting — required for embedding click
   in Flet/pytest; default `True` calls `sys.exit` (never call a command from GUI thread).
8. **Windows expansion:** `Command.main(windows_expand_args=True)` globs/expands on Win32 —
   disable when passing raw filtergraphs containing `*`/`~`.
9. **Progress bar invisibility:** not rendered when stdout isn't a tty or steps are
   sub-second; `hidden=False` default still writes nothing in CI — assert on `Result.output`
   with `CliRunner`, not on bar pixels.
10. **Colorama removed (8.5):** native ANSI everywhere; `color=None` auto-strips on redirect —
    pass `color=True` in tests that assert styling, `CliRunner(color=…)`.
11. **`CliRunner` is process-global (stdin/stdout/env swap), not thread-safe;**
    `capture="fd"` is POSIX-only; `isolated_filesystem` chdirs — keep CLI tests serial.
12. **Chain groups forbid optional `Argument`s;** `Tuple` requires exact `nargs==arity`;
    `FloatRange` open-bounds + `clamp` raises `TypeError`.
13. **Transitive-version risk:** click floats on `cookiecutter>=2.6.0`'s `click<9,>=7` range —
    a 9.0 release removes the deprecated aliases. Either pin `click<9` in dev deps while
    `tools/` uses it, or fix forward when 9.0 lands.
14. **App bug to fix pre-v1:** `tools/admob.py` `_sub`/`_subst` `NameError` — `swap-ids`
    is currently broken; add `tests/test_admob_cli.py` with `CliRunner().invoke(cli,
    ["check-ids"])` + isolated-filesystem `swap-ids --mode test --yes` coverage.
