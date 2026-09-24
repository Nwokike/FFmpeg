# PyYAML 6.0.3 — Complete API Reference

> Import name: `yaml`. Compiled twin: top-level `_yaml` (`yaml._yaml` = `CParser`, `CEmitter` from libyaml).
> Ground truth: `.venv/Lib/site-packages/yaml/` + `pyyaml-6.0.3.dist-info/` (METADATA, RECORD, LICENSE, WHEEL, INSTALLER, REQUESTED, top_level.txt).
> Scope: YAML 1.1 parser/emitter for Python. Unicode, pickle support, extension API, marked errors.

## Files

Package dir `.../site-packages/yaml/` — 17 `.py` files (no `yaml.py`, no `version.py`; version lives in `__init__.py`). `__pycache__/` skipped.

| File | Size (B) | Role |
|---|---|---|
| `__init__.py` | 12311 | Public API: `load/load_all`, `safe_load/safe_load_all`, `full_load/full_load_all`, `unsafe_load/unsafe_load_all`, `dump/dump_all`, `safe_dump/safe_dump_all`, `scan/parse/compose(_all)`, `emit/serialize(_all)`, `add_*`, `YAMLObject` |
| `error.py` | 2533 | `Mark`, `YAMLError`, `MarkedYAMLError` |
| `tokens.py` | 2573 | Scanner token classes |
| `events.py` | 2445 | Parser event classes |
| `nodes.py` | 1440 | `ScalarNode`, `SequenceNode`, `MappingNode` |
| `reader.py` | 6794 | `Reader`, `ReaderError` — encoding detection, printable check |
| `scanner.py` | 51279 | `Scanner`, `ScannerError`, `SimpleKey` — char stream → tokens |
| `parser.py` | 25495 | `Parser`, `ParserError` — tokens → events |
| `composer.py` | 4883 | `Composer`, `ComposerError` — events → node tree |
| `constructor.py` | 28639 | `Base/Safe/Full/Unsafe/Constructor`, `ConstructorError` — nodes → Python objects |
| `resolver.py` | 9004 | `BaseResolver`, `Resolver`, `ResolverError` — tag resolution (implicit + path) |
| `serializer.py` | 4165 | `Serializer`, `SerializerError` — nodes → events |
| `representer.py` | 14190 | `Base/Safe/Representer`, `RepresenterError` — Python objects → nodes |
| `emitter.py` | 43006 | `Emitter`, `EmitterError`, `ScalarAnalysis` — events → text |
| `loader.py` | 2061 | `BaseLoader`, `SafeLoader`, `FullLoader`, `Loader`, `UnsafeLoader` (mixin compositions) |
| `dumper.py` | 2837 | `BaseDumper`, `SafeDumper`, `Dumper` (mixin compositions) |
| `cyaml.py` | 3851 | `CBaseLoader`, `CSafeLoader`, `CFullLoader`, `CUnsafeLoader`, `CLoader`, `CBaseDumper`, `CSafeDumper`, `CDumper` (CParser/CEmitter + same mixins) |
| Compiled | — | `yaml/_yaml.cp314-win_amd64.pyd` (258 560 B) — libyaml binding. `__init__` sets `__with_libyaml__ = True` if `from .cyaml import *` succeeds |

RECORD (sha256-pinned) also ships `_yaml/__init__.py`, `licenses/LICENSE`, `WHEEL`, `INSTALLER`, `top_level.txt` (`_yaml\nyaml`).

## Metadata

From `pyyaml-6.0.3.dist-info/METADATA` (+ WHEEL / LICENSE / INSTALLER / REQUESTED):

- **Name / Version:** `PyYAML 6.0.3`, `__version__ = '6.0.3'` in `yaml/__init__.py`.
- **Summary:** "YAML parser and emitter for Python". Home: https://pyyaml.org/. Source: https://github.com/yaml/pyyaml.
- **License:** MIT (`License: MIT`, classifier `OSI Approved :: MIT License`). License file: `Copyright (c) 2017-2021 Ingy döt Net; Copyright (c) 2006-2016 Kirill Simonov` — AS-IS, no warranty.
- **Requires-Python:** `>=3.8`. Classifiers list CPython + PyPy, 3.8→3.14, Dev Status 5 - Production/Stable.
- **C-extension status:** PRESENT. This install: `yaml/_yaml.cp314-win_amd64.pyd` importable; `yaml.__with_libyaml__ is True` expected. `WHEEL: Root-Is-Purelib: false, Tag: cp314-cp314-win_amd64, Generator: setuptools (80.9.0)`. Pure-Python fallback works without it (C classes simply unavailable). `top_level.txt` exposes both `yaml` and `_yaml`.
- **Installer:** `INSTALLER` = `uv`; `REQUESTED` is 0 bytes → not a direct user request (transitive, see below).
- **Spec compliance:** "complete YAML 1.1 parser" (NOT 1.2 — hence the `yes/no/on/off` bool gotcha).

## Module-by-module API

Pipeline (load): `Reader → Scanner → Parser → Composer → Constructor (+ Resolver)`.
Pipeline (dump): `Representer → Serializer → Emitter (+ Resolver)`.
`Loader`/`Dumper` classes are thin mixin compositions (see `loader.py`/`dumper.py`/`cyaml.py`); all behaviour lives in the stage modules.

### `yaml/__init__.py` — top-level functions

```python
def scan(stream, Loader=Loader)            # yield Token
def parse(stream, Loader=Loader)           # yield Event
def compose(stream, Loader=Loader)         # -> Node | None (first doc)
def compose_all(stream, Loader=Loader)     # yield Node
def load(stream, Loader)                   # REQUIRED positional! -> object (first doc)
def load_all(stream, Loader)               # yield object
def full_load(stream)                      # load(stream, FullLoader)
def full_load_all(stream)                  # load_all(stream, FullLoader)
def safe_load(stream)                      # load(stream, SafeLoader)
def safe_load_all(stream)                  # load_all(stream, SafeLoader)
def unsafe_load(stream)                    # load(stream, UnsafeLoader)
def unsafe_load_all(stream)                # load_all(stream, UnsafeLoader)
def emit(events, stream=None, Dumper=Dumper, canonical=None, indent=None,
         width=None, allow_unicode=None, line_break=None) -> str | None
def serialize_all(nodes, stream=None, Dumper=Dumper, canonical=None, indent=None,
                  width=None, allow_unicode=None, line_break=None, encoding=None,
                  explicit_start=None, explicit_end=None, version=None, tags=None)
def serialize(node, stream=None, Dumper=Dumper, **kwds)
def dump_all(documents, stream=None, Dumper=Dumper, default_style=None,
             default_flow_style=False, canonical=None, indent=None, width=None,
             allow_unicode=None, line_break=None, encoding=None, explicit_start=None,
             explicit_end=None, version=None, tags=None, sort_keys=True) -> str | None
def dump(data, stream=None, Dumper=Dumper, **kwds)
def safe_dump_all(documents, stream=None, **kwds)   # Dumper=SafeDumper
def safe_dump(data, stream=None, **kwds)            # Dumper=SafeDumper
def add_implicit_resolver(tag, regexp, first=None, Loader=None, Dumper=Dumper)
def add_path_resolver(tag, path, kind=None, Loader=None, Dumper=Dumper)
def add_constructor(tag, constructor, Loader=None)
def add_multi_constructor(tag_prefix, multi_constructor, Loader=None)
def add_representer(data_type, representer, Dumper=Dumper)
def add_multi_representer(data_type, multi_representer, Dumper=Dumper)
def warnings(settings=None)  # deprecated no-op, returns {}
class YAMLObject(metaclass=YAMLObjectMetaclass)  # self-marshalling; yaml_tag / yaml_loader / yaml_dumper / yaml_flow_style
```

`stream` for load-family: `str | bytes | file-like`. `stream=None` for dump-family returns `str` (or `bytes` if `encoding` set); with a stream it writes and returns `None`. `load()` with no `Loader` raises `TypeError` (since 6.0 — deliberate break to kill the RCE footgun).

Examples:

```python
import yaml

yaml.safe_load("a: 1\nb: [x, y]")
# {'a': 1, 'b': ['x', 'y']}
list(yaml.safe_load_all("---\na: 1\n---\na: 2\n"))
# [{'a': 1}, {'a': 2}]
yaml.safe_dump({"name": "café", "ports": [80, 443]}, sort_keys=False, allow_unicode=True)
# 'name: café\nports: [80, 443]\n'
yaml.safe_dump({"a": 1}, explicit_start=True)  # '---\na: 1\n'
```

### Loaders, dumpers, C variants

| Class | Constructor mixin | Safe on untrusted input? |
|---|---|---|
| `SafeLoader` / `CSafeLoader` | `SafeConstructor` | YES — only basic YAML tags |
| `FullLoader` / `CFullLoader` | `FullConstructor` | Mostly — `!!python/*` scalars/collections/tuples, no `object/module/apply/new` |
| `Loader` / `UnsafeLoader` / `CLoader` / `CUnsafeLoader` | `Constructor` = `UnsafeConstructor` | NO — `__import__`, arbitrary instantiation, `object/apply` (RCE) |
| `BaseLoader` / `CBaseLoader` | `BaseConstructor` | N/A — no tag resolution, all scalars stay `str` |
| `SafeDumper` / `CSafeDumper` | `SafeRepresenter` | emits basic tags only |
| `Dumper` / `CDumper` | `Representer` (+`Serializer`) | emits `!!python/*` tags |

`Loader is UnsafeLoader` by another name (kept for back-compat; comment in source says "was always unsafe"). C variants swap the `Reader+Scanner+Parser` (load) or `Emitter` (dump) stage for `CParser`/`CEmitter` — constructor/representer/resolver logic is shared Python. `CBaseDumper.__init__`/`CSafeDumper`/`CDumper` take the full dumper kwargs (see below).

### `dump` / `dump_all` Dumper kwargs (full list, defaults)

```python
default_style = (None,)  # scalar style override: None | "'" | '"' | '|' | '>'
default_flow_style = (False,)  # False=block, True=flow, None=auto ("best style")
canonical = (None,)  # True -> canonical YAML (verbose, explicit tags)
indent = (None,)  # block indent; Emitter default 2 when None
width = (None,)  # line wrap column; Emitter default 80 when None
allow_unicode = (None,)  # False default -> non-ASCII escaped (\uXXXX); True emits raw UTF-8
line_break = (None,)  # '\n' (also '\r', '\r\n')
encoding = (None,)  # None -> str; e.g. 'utf-8' -> bytes written/returned
explicit_start = (None,)  # True emits leading `---`
explicit_end = (None,)  # True emits trailing `...`
version = (None,)  # e.g. (1, 1) emits `%YAML 1.1`
tags = (None,)  # {handle: prefix} emits `%TAG` directives
sort_keys = True  # sort mapping keys (since 5.1; False preserves insertion order)
```

`Emitter.__init__(stream, canonical=None, indent=None, width=None, allow_unicode=None, line_break=None)` — note: `encoding/version/tags/explicit_*` belong to `Serializer.__init__(encoding, explicit_start, explicit_end, version, tags)`; `default_style/flow/sort_keys` belong to `BaseRepresenter.__init__(default_style, default_flow_style, sort_keys)`.

### Multi-document streams

- `load`/`safe_load`/`full_load`/`unsafe_load`/`compose`: FIRST document only; extra docs raise `ComposerError("expected a single document in the stream...")`.
- `*_load_all` / `compose_all`: generator over ALL `---`-separated docs.
- `dump(data)` wraps to `dump_all([data])`; `dump_all(list_of_docs)` emits `---`-separated stream. `serialize_all` is the node-level equivalent.

### Custom tags / marshalling

```python
def my_ctor(loader, node):
    return MyType(loader.construct_scalar(node))


yaml.add_constructor("!mytype", my_ctor, Loader=yaml.SafeLoader)
yaml.add_multi_constructor("!prefix:", lambda loader, suffix, node: ..., Loader=yaml.SafeLoader)
yaml.add_representer(MyType, lambda dumper, data: dumper.represent_scalar("!mytype", str(data)))
yaml.add_multi_representer(Base, lambda dumper, data: ...)  # matches subclasses via MRO
yaml.add_implicit_resolver("!ver", re.compile(r"v\d+"), first=list("v"), Loader=yaml.SafeLoader)
```

Notes: `Loader=None` in `add_constructor`/`add_multi_constructor`/`add_implicit_resolver` registers on `Loader + FullLoader + UnsafeLoader` but NOT `SafeLoader` — pass `Loader=SafeLoader` explicitly to extend safe loading. `SafeConstructor.construct_undefined` raises `ConstructorError` for unknown tags; `SafeRepresenter.represent_undefined` raises `RepresenterError` for unrepresentable objects. `YAMLObject` with `yaml_tag = '!foo'` auto-registers `from_yaml`/`to_yaml` on `Loader/FullLoader/UnsafeLoader` + `Dumper`.

### Constructors resolved per level

- `SafeConstructor`: null/bool/int/float/binary/timestamp/omap/pairs/set/str/seq/map + merge-key (`<<`) flattening + `=` value tag. Int forms: `0b`, `0x`, octal `0o`/`0777`, sexagesimal `1:20`, underscores. Float: `.inf/.nan`, sexagesimal. Timestamp → `datetime.date` or `datetime.datetime` (tz-aware when offset/`Z`).
- `FullConstructor` adds: `python/none|bool|str|unicode|bytes|int|long|float|complex|list|tuple|dict`, `python/name:` multi-ctor. Resolves names ONLY from already-imported modules (`sys.modules`); state-key blacklist `^extend$`, `^__.*__$` blocks dunder injection via `__setstate__`/dict state.
- `UnsafeConstructor`/`Constructor` adds: `python/module:`, `python/object:`, `python/object/new:`, `python/object/apply:` with real `__import__`, arbitrary `cls(*args, **kwds)`, `extend`/`dictitems` application — this is the RCE vector.

Representers mirror this: `SafeRepresenter` handles None/str/bytes/bool/int/float/list/tuple/dict/set/date/datetime; `Representer` adds complex/tuple-tag/type/function/module/generic-object via `__reduce_ex__(2)` and `OrderedDict`.

### `YAMLError` hierarchy (all importable from `yaml`)

```
YAMLError (Exception)
├── MarkedYAMLError (context, context_mark, problem, problem_mark, note)
│   ├── ComposerError      (composer.py — e.g. undefined alias, duplicate anchor, multi-doc in get_single_*)
│   ├── ConstructorError   (constructor.py — bad node kind, unhashable key, unknown tag, blacklisted state key, base64)
│   ├── ParserError        (parser.py)
│   └── ScannerError       (scanner.py)
├── ReaderError            (reader.py — name, position, character, encoding, reason; NOT marked)
├── ResolverError          (resolver.py — bad path_resolver spec)
├── SerializerError        (serializer.py — open/close misuse)
├── RepresenterError       (representer.py — cannot represent object)
└── EmitterError           (emitter.py)
```

`Mark(name, index, line, column, buffer, pointer)`; `str(mark)` → `in "<name>", line L, column C:` (1-based display; stored 0-based) + `get_snippet(indent=4, max_length=75)` caret line. File-backed streams give `buffer=None` → no snippet.

### Lower-level stages (when to touch)

- `scan(stream)` → tokens (`StreamStart/End`, `Directive`, `DocumentStart/End`, `Block*/Flow*`, `Key ?`, `Value :`, `BlockEntry -`, `FlowEntry ,`, `Alias`, `Anchor`, `Tag`, `Scalar(value, plain, style)`).
- `parse(stream)` → events (`StreamStart/End`, `DocumentStart(explicit, version, tags)/End(explicit)`, `Alias`, `Scalar(anchor, tag, implicit, value, style)`, `Sequence/MappingStart(anchor, tag, implicit, flow_style)` + End).
- `compose(_all)` → `ScalarNode(tag, value, style)` / `SequenceNode` / `MappingNode(tag, value, flow_style)` with start/end marks.
- Direct use is for linters, syntax highlighters, or tag-preserving transforms; apps should stay at `safe_load/safe_dump`.

## App usage & correctness

(a) **Direct usage: NONE.** `grep -rn import yaml / from yaml / safe_load / \.ya?ml` over `src/ tests/ tools/ pyproject.toml` returns zero hits. `pyproject.toml [project] dependencies` (av, flet×7, httpx) and `[dependency-groups] dev` (flet-cli, flet-desktop, pytest, ruff) never mention yaml. No `yaml.load` anywhere → **no unsafe-load misuse in the app.**

(b) **Why it's installed — transitive chain (verified):**

```
ffmpeg (project, package=false)
 └─ dev group: flet-cli 1.0.0  (METADATA Requires-Dist: cookiecutter>=2.6.0)
     └─ cookiecutter 2.7.1     (METADATA Requires-Dist: pyyaml>=5.3.1)
         └─ pyyaml 6.0.3  ← this package
```

`uv.lock` pins the same edges (`ffmpeg → …`, `flet-cli → cookiecutter`, `cookiecutter → pyyaml`); RECORD hash `pyyaml-6.0.3-cp314-cp314-win_amd64.whl`. `INSTALLER=uv`, `REQUESTED` empty = never directly requested. (Hypotheses rejected: jinja2's METADATA requires only markupsafe; ruff is a binary, no yaml dep. `markdown-it-py` lists pyyaml only under `rtd` extra; `watchdog` match is incidental — neither pulls it into this venv. cookiecutter consumes it for `cookiecutter.yaml` template configs during `flet create` scaffolding.)

(c) **Incidental YAML in repo:** exactly one — `.github/workflows/build-all.yml` (CI workflow for GitHub Actions). Not parsed by this package at runtime.

(d) **Misuse audit:** clean — zero call sites means zero `yaml.load`-without-Loader, zero `FullLoader`-on-untrusted-input, zero custom-constructor-on-SafeLoader accidents. If any future code parses YAML, the bar is `yaml.safe_load` / `yaml.safe_load_all` only.

(e) **Current persistence (for contrast):** `src/services/storage_service.py` uses `storage.json` (`json.load`/`json.dump indent=2`) for key-value config/history. JSON is the right call for flat prefs; YAML's win is human-authored nested docs (see next section).

## Underused APIs to adopt

Concrete v1 opportunities (all `safe_*`-only; no new runtime dep needed — already in venv, but promote to a direct dep if adopted so `uv sync --no-dev` keeps it):

1. **`presets.yaml` for encode settings** — `safe_load` a bundled asset into `EngineParams`/job dicts (H.264/H.265/AV1 × 720p/1080p/4K, crf/bitrate/audio). Human-editable, comments allowed (JSON can't). `safe_dump` a "Export preset" action.
2. **Job-queue / pipeline definitions** — multi-doc `safe_load_all` where each `---` doc is one job (input, filters, outputs). Validates with existing `test_job_queue.py` / `test_engine_params.py` fixtures.
3. **Test fixtures with media profiles** — move parametrized matrices (resolutions, codecs, subtitles, concat/crossfade cases) from inline Python lists into `tests/fixtures/*.yaml`; `safe_load` in `conftest.py`. Easier for non-devs to extend; `sort_keys=False` + `default_flow_style=False` keeps diffs clean.
4. **CI matrix authoring** — `build-all.yml` already YAML; add a checked-in `tools/ci-matrix.yaml` (arch × sdk × build-type) rendered into the workflow by a small generator script, instead of hand-editing the workflow.
5. **Crash/report structured dumps** — `safe_dump(report, explicit_start=True, allow_unicode=True, sort_keys=False)` for bug reports (device, FFmpeg build, job spec, log tail). More readable than JSON for pasted issues; round-trips via `safe_load`.
6. **Custom tags for domain types (opt-in)** — e.g. `!timestamp`/duration or `!preset` via `add_constructor(..., Loader=SafeLoader)` + `add_representer`, so fixture files stay terse without ever touching `FullLoader`.

## Gotchas

- **`load()` requires `Loader`** — `yaml.load(doc)` raises `TypeError` in 6.x. Never pass `Loader=Loader/UnsafeLoader` on untrusted text (arbitrary code exec via `!!python/object/apply`). Rule: external input → `safe_load`; trusted round-trip of python tuples → `full_load` at most.
- **`FullLoader` ≠ safe.** It still builds `!!python/tuple`, `!!python/name:os.system`, `!!python/object/new` is blocked but `apply` variants differ per subclass — treat as trusted-only.
- **YAML 1.1 bools bite:** `yes/no/on/off/true/false` (any case) → bool. Unquoted `on:` key becomes `True`. Quote literals (`"on"`) or use `BaseLoader` to keep raw strings.
- **Auto-typing surprises:** `0777` → int 511 (octal), `1:20` → 80, `2024-01-02` → `datetime.date`, `.inf/.nan` → floats, `~`/``/null` → None, `<<` merges mappings. Validate after `safe_load`.
- **Duplicate keys silently win** (last wins; composer's duplicate check is commented out). Dedupe-check manually for presets.
- **`sort_keys=True` default** reorders mappings on dump; pass `sort_keys=False` to preserve author order. `allow_unicode` defaults to off (escapes `café`); set `True` for readable presets. `width` default 80 wraps long scalars — set `width=4096`/large for long ffmpeg filter strings. `indent` must be 2–…; bad values surface as `EmitterError`.
- **`encoding='utf-8'` flips output to `bytes`** (and expects a binary stream) — omit for `str`.
- **Aliases/anchors:** dump emits `&id001/*id001` for shared objects; load honours them (recursive structures possible → billion-laughs-style DoS on hostile input; cap input size / use `SafeLoader` + size limits).
- **Errors are marked but 0-based internally:** catch `yaml.YAMLError` (covers all subclasses incl. `ReaderError`); display `str(exc)` which already renders `line+1/column+1` + caret snippet. `compose` on multi-doc raises `ComposerError`.
- **C vs Python parity:** `CSafeLoader` ≈ `SafeLoader` but faster; both installed here (`__with_libyaml__`). `safe_load` uses the pure-Python `SafeLoader` — pass `Loader=CSafeLoader` explicitly for speed on large fixtures.
- **No `yaml.version` module;** version is `yaml.__version__`. `yaml.warnings()` is a deprecated no-op.
