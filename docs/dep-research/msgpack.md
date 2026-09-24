# msgpack 1.2.2 — Complete API Reference

MessagePack binary serialization. Critical infra: Flet 1.0 syncs every Python
control to the Flutter/Dart client over msgpack (`flet` requires
`msgpack>=1.1.0`; installed 1.2.2, satisfying it). The app never imports msgpack
directly — it rides underneath every `page.update()` / event dispatch.

## Files

Package dir: `.venv/Lib/site-packages/msgpack/` — 5 files (no `.pyi` stubs;
`.py` sources are ground truth; the C extension mirrors `fallback.py`):

| File | Role |
|---|---|
| `__init__.py` | Public surface: `Packer`, `Unpacker`, `unpackb`, `pack`/`packb`, `unpack`, aliases `load`/`loads`/`dump`/`dumps`, `ExtType`, `Timestamp`, `version=(1,2,2)`, `__version__="1.2.2"`; selects `_cmsgpack` C ext unless `MSGPACK_PUREPYTHON` env is set (confirmed: runtime uses `msgpack._cmsgpack.Packer` on this machine) |
| `exceptions.py` | `UnpackException`, `BufferFull`, `OutOfData`, `FormatError(ValueError, UnpackException)`, `StackError(ValueError, UnpackException)`, `ExtraData` (attrs `.unpacked`, `.extra`), deprecated aliases `UnpackValueError=ValueError`, `PackException=Exception`, `PackValueError=ValueError`, `PackOverflowError=OverflowError` |
| `ext.py` | `ExtType(code, data)` namedtuple (code 0–127 int, data bytes); `Timestamp` (below) |
| `fallback.py` | Pure-Python reference implementation: `Packer`, `Unpacker`, `unpackb`, header table, `DEFAULT_RECURSE_LIMIT=1024` |
| `_cmsgpack.cp314-win_amd64.pyd` | Compiled C extension actually used (128 000 bytes) |

RECORD confirms exactly these 12 entries (4 dist-info + licenses/COPYING +
top_level.txt + 5 package files). `__pycache__/` skipped.

## Metadata

From `msgpack-1.2.2.dist-info/METADATA` (Metadata-Version 2.4):

- **Name / Version:** `msgpack` 1.2.2. Summary: "MessagePack serializer".
- **License:** `License-Expression: Apache-2.0` (license file `licenses/COPYING`,
  copyright INADA Naoki 2008–2011). NOT MIT — Apache-2.0 only.
- **Requires-Python:** `>=3.10` (app runs 3.14.7 — fine).
- **Extras:** NONE. No `[numpy]`, no optional dependency groups at all
  (`Provides-Extra` absent). numpy arrays are NOT natively supported — must go
  through `default=`/`ExtType` manually.
- **Installer:** `uv` (`INSTALLER` file). Wheel tag `cp314-cp314-win_amd64`,
  `Root-Is-Purelib: false` (ships native code).
- **Classifiers:** Production/Stable, OS Independent, CPython + PyPy
  (PyPy uses `fallback.py`; CPython prefers `_cmsgpack`).
- Upstream: https://github.com/msgpack/msgpack-python/, docs at
  https://msgpack-python.readthedocs.io/

## Module-by-module API

### `pack` / `packb` / `unpack` / `unpackb` (+ json/pickle aliases)

```python
msgpack.packb(o, **packer_kwargs) -> bytes
msgpack.pack(o, stream, **packer_kwargs) -> None   # stream.write(packer.pack(o))
msgpack.unpackb(packed, **unpacker_kwargs)         # raises ExtraData on trailing bytes,
                                                   # ValueError on truncated input
msgpack.unpack(stream, **unpacker_kwargs)          # stream.read() then unpackb
dumps, dump = packb, pack  # aliases; loads, load = unpackb, unpack
```

`unpackb` feeds the whole buffer into an `Unpacker(max_buffer_size=len(packed))`,
so a single truncated `packed` raises plain `ValueError("Unpack failed:
incomplete input")`, not `OutOfData`.

### `Packer` — all kwargs and semantics

```python
Packer(
    default=None,  # callable(obj)->packable; called ONCE per object (default_used flag)
    use_single_float=False,  # float32 (0xCA) instead of float64 (0xCB)
    autoreset=True,  # pack() returns bytes and clears buffer; False → use .bytes()/.reset()/.getbuffer()
    use_bin_type=True,  # bytes→bin family, str→str family + str8; False → legacy raw for both (pre-1.0 compat)
    strict_types=False,  # True: exact-type check; subclasses NOT packed; TUPLES NOT packed as lists
    datetime=False,  # True: tz-aware datetime → Timestamp ext (code -1); NAIVE datetime → ValueError
    unicode_errors="strict",
    buf_size=None,  # C-extension internal buffer only
)
```

Type mapping (native, no `default=` needed): `None→nil`, `bool`, int (uint
up to 2⁶⁴−1, int down to −2⁶³; larger → `OverflowError`), `bytes/bytearray/
memoryview→bin`, `str→str` (UTF-8), `float→f64`, `list` AND `tuple→array`
(unless `strict_types`), `dict→map`, `ExtType`/`Timestamp→ext`. Methods:
`pack(obj)`, `pack_map_pairs(pairs)`, `pack_array_header(n)`,
`pack_map_header(n)`, `pack_ext_type(typecode, data)`, `bytes()`, `reset()`,
`getbuffer()`. Nesting limit 1024 → `ValueError("recursion limit exceeded")`.
Unsupported object without `default=` → `TypeError("Cannot serialize ...")`.

Custom-type recipe (per METADATA docs): `msgpack.packb(obj,
default=encode_fn)` + `msgpack.unpackb(p, object_hook=decode_fn)`; binary
custom types via `ExtType(code 0–127, bytes)` + `ext_hook(code, data)`.

### `Unpacker` — streaming, all kwargs

```python
Unpacker(
    file_like=None,  # object with .read(n); if given, .feed() is unusable
    read_size=0,  # file_like.read chunk (default min(max_buffer_size, 16KiB); must be <= max_buffer_size)
    use_list=True,  # False → arrays unpack to TUPLES (lighter/faster)
    raw=False,  # True → raw unpacks to BYTES; False → decode UTF-8 to str (1.0+ default)
    timestamp=0,  # 0→Timestamp obj, 1→float sec, 2→int nanos, 3→UTC datetime
    strict_map_key=True,  # only str/bytes keys (hash-DoS guard); False to allow int/other keys
    object_hook=None,  # fn(dict)->obj, applied after each map (mutually exclusive with object_pairs_hook)
    object_pairs_hook=None,  # fn([(k,v),...])->obj
    list_hook=None,  # fn(list)->obj, applied after each array
    unicode_errors="strict",
    max_buffer_size=100 * 1024 * 1024,  # 0 means 2**31-1; BufferFull when exceeded
    ext_hook=ExtType,  # fn(code, bytes)->obj
    max_str_len=-1,
    max_bin_len=-1,
    max_array_len=-1,
    max_map_len=-1,  # (defaults to max_buffer_size//2)
    max_ext_len=-1,  # all -1 → inherit max_buffer_size; breaching raises ValueError
)
```

Streaming methods: `feed(bytes)` (feed-mode only), iterate / `unpack()`
(next object), `skip()`, `read_array_header()` / `read_map_header()` (manual
element-by-element reads), `read_bytes(n)`, `tell()` (stream offset).
`OutOfData` → end of available data (iteration converts to `StopIteration`).
IMPORTANT (upstream): if `unpack()` raises anything other than `OutOfData`,
that `Unpacker` is dead — create a new one. Map keys that are `str` are
`sys.intern()`ed. `unpackb` shares all these kwargs.

### `Timestamp` — ext code −1, three wire widths

```python
Timestamp(seconds: int, nanoseconds: int = 0)  # nanoseconds in 0..999_999_999; negative times = neg sec + pos ns
```

Wire selection in `to_bytes()`: 32-bit (secs < 2³², ns==0) / 64-bit (secs fit
34 bits) / 96-bit (otherwise, `struct "!Iq"`). Conversions: `from_bytes(b)`,
`to_bytes()`, `from_unix(sec)` / `to_unix()` (float), `from_unix_nano(ns)` /
`to_unix_nano()` (int, lossless), `from_datetime(dt)` (naive treated as LOCAL
time, like `datetime.timestamp()`; aware normalized against epoch with integer
arithmetic — microsecond precision, no float drift) / `to_datetime()` (UTC,
microsecond resolution — sub-microsecond ns truncated via `//1000`). Immutable
by convention (`__slots__`), value equality + hash. Note: `Packer(datetime=True)`
packs tz-aware datetimes as `Timestamp`, but naive ones raise `ValueError` —
and stock `unpackb` returns a `Timestamp` object unless `timestamp=1/2/3`.

### `ExtType`

`ExtType(code: int 0–127, data: bytes)` — namedtuple. This is how flet smuggles
datetime/time/Duration past the Timestamp limitation (see below); unknown codes
round-trip untouched through the default `ext_hook=ExtType`.

### Exceptions — catch guide

- Packing: `TypeError` (unserializable), `OverflowError` (int > 2⁶⁴−1),
  `ValueError` (too-large str/bin/array/map, recursion limit, naive datetime
  with `datetime=True`).
- Unpacking: `ExtraData` (`.unpacked`, `.extra`), `FormatError` (bad header),
  `StackError` (too nested / RecursionError), `OutOfData` (streaming
  truncation; `unpackb` converts to `ValueError`), `BufferFull` (over
  `max_buffer_size`), `ValueError` (strict-map-key violation, `max_*_len`
  breach, bad timestamp bytes).
- `UnpackException` is NOT a catch-all (some unpack errors are plain
  `ValueError`); catch `Exception` for full coverage per the docstring.

### Cross-version compat (1.0 breaking changes — still relevant)

`use_bin_type=True` and `raw=False` are the modern defaults: bytes↔bin,
str↔str, UTF-8 assumed. Talking to pre-1.0 data/peers needs
`use_bin_type=False` + `raw=True`. `encoding=` option is GONE (UTF-8 always).
`max_buffer_size` defaults to 100 MiB (was unlimited); `strict_map_key`
defaults True. **Not supported natively, ever:** `set`/`frozenset`, arbitrary
objects, `datetime` (needs `datetime=True` or `default=`), `tuple→list`
round-trip (tuples come back as lists unless `use_list=False` gives tuples for
EVERYTHING), int-keyed dicts under `strict_map_key=True`, ints outside
[−2⁶³, 2⁶⁴−1], NaN/Infinity floats are fine (IEEE754) but JSON-interop is not.

## How flet uses msgpack (call sites)

Dependency: `flet 1.0.0` METADATA → `Requires-Dist: msgpack>=1.1.0` (hard dep,
no extra). All call sites live in `.venv/Lib/site-packages/flet/messaging/`:

| File | Direction | Call |
|---|---|---|
| `protocol.py` | codec | `configure_encode_object_for_msgpack(BaseControl)` builds the `default=` callback; `decode_ext_from_msgpack(code, data)` is the `ext_hook` |
| `flet_socket_server.py:287` / `:438` | socket transport | `msgpack.unpackb(packet[1:], ext_hook=decode_ext_from_msgpack)` / `msgpack.packb([message.action, message.body], default=...)` |
| `flet_dart_bridge_server.py:129` / `:229` | embedded native | same unpack/pack pair |
| `pyodide_connection.py:92` / `:206` | web/Pyodide | same unpack/pack pair |

Wire details:

- Every frame is `[0x00][msgpack body]` (`0x01` = raw DataChannel bytes, never
  msgpack). Socket mode prefixes a `u32 LE` length; bridge/Pyodide rely on
  message boundaries. Body is always the 2-item array
  `[message.action, message.body]`, where `message.action` is a `MessageAction`
  enum (1 REGISTER_CLIENT … 7 PYTHON_OUTPUT — int values must match Dart's
  enum) and body is a control-dataclass tree.
- The `default=` encoder: dataclasses → sparse dicts (non-default values only,
  `on_*` handlers → `True` bool, list/dict/dataclass snapshots into
  `__prev_*` for patch diffing); `Enum→value`; `datetime/date→ExtType(1,
  isoformat)`, `time→ExtType(2, "HH:MM")`, `Duration→ExtType(3, microseconds
  as int)`; **callables raise `RuntimeError`** — a method reference in a
  control field kills the whole `page.update()`, not just that control.
- The `ext_hook` decoder reverses codes 1/2/3 (+ code 4 → utf-8 str); anything
  else passes through as `ExtType`. Note flet does NOT use msgpack's native
  `Timestamp` type at all — datetimes travel as ISO strings in ExtType(1).

Consequence for this app: every `ft.observable` mutation (`AppState.jobs`,
`history`, `current_media_info`, … in `src/core/state.py`) is serialized
through this encoder on each UI refresh. Payloads must be plain
str/int/float/bool/None/list/dict/nested-dataclass. Anything exotic
(`threading.Event`, `Path`, `set`, custom class) in a control property or
observable field risks `TypeError`/`RuntimeError` on update.

## App usage & correctness

- **Zero direct imports.** `grep msgpack src/ tests/` → no hits. Correct: the
  app must NOT take its own dependency on msgpack (keep it flet's private
  transport; pin stays `flet>=1.0.0` in `pyproject.toml`).
- **Observable state is msgpack-safe by construction — verified.**
  `AppState` (`src/core/state.py:114`) holds only `bool/int/str/None/dict/
  list[Job]/Job/MediaInfo`. `Job` (`state.py:87`) fields: `str op/id/paths/
  status/messages`, `params: dict[str, Any]`, `float progress`,
  `float created_at` (epoch seconds — NOT a datetime object, good),
  `finished_at: float|None`, `int` sizes. `MediaStreamInfo`/`MediaInfo`:
  `int/float/str/None`, `dict[str,str]`, `dict[str,bool]`, lists of dataclasses.
  `EngineProbe` sets (`engine_probe.py:74,137–178`: `set[str]` codecs/filters)
  never enter controls — `_load_cached`/`_save_cached` convert `set↔list` at
  the JSON boundary, and `probe_info` display strings are copied out.
- **Two residual risks (low, noted not fixed per rules):**
  1. `Job.params: dict[str, Any]` (`state.py:94`) is the one untyped hole — a
     future op stuffing a `Path`, `set`, or `datetime` into params and then
     binding it to a control prop would break that update. Convention needed:
     params stay JSON-scalars; convert at enqueue time.
  2. `engine_service.py` holds `threading.Event`s and `set`s (`_FILTERS_AVAIL`,
     cancel events) — all correctly kept out of controls/observables today,
     but any refactor that surfaces them to UI must convert first.
- **Persistence is JSON, not msgpack — verified intentional:**
  `storage_service.py` (`storage.json`, atomic tmp→bak→replace, debounced
  1 s flush) and `engine_probe_<ver>.json` cache are human-readable/debuggable
  and tiny. No change recommended for v1.0.

## Underused APIs to adopt

Post-v1.0 candidates (none block v1.0; app correctly uses zero msgpack today):

1. **Compact history/probe persistence** — `msgpack.packb(history_dict)` /
   `unpackb(..., raw=False, strict_map_key=True)` for a `history.msgpack`
   sidecar if `storage.json` grows (posterity: history entries are
   str/float/int/None — already msgpack-clean; `created_at` float needs no
   `Timestamp`). Keep JSON as primary; msgpack only if size/parse time hurts.
2. **Binary probe cache** — `engine_probe` JSON cache (`engine_probe.py:185`)
   with its set↔list conversions maps 1:1 to msgpack arrays; `use_list=False`
   on load gives tuples for free. Only if probe payload grows past trivial.
3. **Streaming large payloads** — `Unpacker.feed()` + `read_array_header()`
   pattern for any future batch import (e.g. bulk history import) instead of
   one-shot `unpackb`.
4. **`default=`/`object_hook` pattern** for `Job` serialize/deserialize if
   queue persistence is ever added: `default` converts `Job→dict`
   (dataclasses aren't native — flet's encoder does this for controls, the app
   would need its own 10-line version); `object_hook` rebuilds.
5. **What NOT to adopt:** `Packer(datetime=True)` + `timestamp=3` for app
   datetimes — flet's transport doesn't use `Timestamp`, so mixing conventions
   invites bugs; keep epoch floats (as `created_at` already does) or ISO
   strings.

## Gotchas

1. **Tuples come back as lists.** `packb((1,2))` → `unpackb` → `[1, 2]`.
   `use_list=False` flips ALL arrays to tuples — no per-field control.
2. **Sets are unserializable, period.** `TypeError`. Convert `set→sorted list`.
   (Relevant: `engine_probe` sets, `engine_service` filter sets.)
3. **Dict keys must be str/bytes** under `strict_map_key=True` (default).
   Int-keyed maps raise on unpack. `Job.params` must stay str-keyed.
4. **Naive datetimes explode** with `datetime=True` (`ValueError`); aware ones
   become `Timestamp`, which `unpackb` returns as `Timestamp`, NOT datetime,
   unless `timestamp=3`. Prefer epoch floats / ISO strings in app payloads.
5. **`default=` fires once per object** — returning another custom object does
   NOT re-invoke it (falls to `TypeError`). The fallback allows exactly one
   retry (`default_used` flag). Chain conversions yourself.
6. **`Unpacker` is single-use after failure** — any error besides `OutOfData`
   kills it; make a new one. `unpackb` trailing bytes → `ExtraData` (check
   `.unpacked`/`.extra`); truncated input → bare `ValueError`.
7. **100 MiB default cap** (`max_buffer_size`) + `strict_map_key` — right for
   network data; pass `max_buffer_size=0` only for trusted large blobs.
8. **C ext vs fallback divergence risk:** production uses `_cmsgpack`; setting
   `MSGPACK_PUREPYTHON=1` (or PyPy) swaps in `fallback.py` — same API, slower.
   Never import `msgpack.fallback` directly; go through top-level names.
9. **No numpy, no extras, no `.pyi`** — `ExtType`-wrap arrays yourself; type
   checkers see untyped defs.
